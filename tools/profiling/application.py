"""Local baseline capture, durable history and read-only reports."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import sqlite3
import statistics
import subprocess
import time
import uuid

from tools.test_policy import PROJECT_ROOT, process_exit_code
from tools.test_runner import prepare_invocation
from tools.timing_model import case_timings, read_telemetry

APPLICATION_ID = 0x50485032
SCHEMA_VERSION = 1
MODES = ('baseline',)
KINDS = ('fixtures', 'fixture_uses', 'processes', 'python_functions', 'python_callers',
         'memory_observations', 'syscalls', 'findings')
MAX_ROWS = 250_000


def utc():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def local_path(path):
    path = Path(os.path.abspath(path))
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('diagnostic paths must not be symbolic links')
    return path


def validate_database(connection):
    if connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
        raise ValueError('not a PatchHarbor profiling database')
    if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
        raise ValueError('unsupported profiling schema; existing history left untouched')
    if connection.execute('SELECT identity FROM schema_meta').fetchall() != [('patchharbor-local-profile',)]:
        raise ValueError('invalid profiling schema identity')
    if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
        raise ValueError('damaged profiling database')


@contextmanager
def database(path, *, writable=False):
    path = local_path(path)
    new = not path.exists()
    if new and not writable:
        raise ValueError('profiling database does not exist')
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    elif not path.is_file():
        raise ValueError('profiling database is not a regular file')
    connection = sqlite3.connect(path.as_uri() + ('?mode=rw' if writable else '?mode=ro'),
                                 uri=True, timeout=.5)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        if new:
            connection.execute('PRAGMA journal_mode=DELETE')
            connection.execute('PRAGMA synchronous=FULL')
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
                connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
                connection.execute('CREATE TABLE schema_meta(identity TEXT NOT NULL)')
                connection.execute("INSERT INTO schema_meta VALUES('patchharbor-local-profile')")
                connection.execute('CREATE TABLE runs(id TEXT PRIMARY KEY, started TEXT NOT NULL, ended TEXT, status TEXT NOT NULL, metadata TEXT NOT NULL)')
                connection.execute('CREATE TABLE measurements(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), mode TEXT NOT NULL, iteration INTEGER NOT NULL, warmup INTEGER NOT NULL, status TEXT NOT NULL, test_exit_code INTEGER, elapsed_s REAL, details TEXT NOT NULL)')
                connection.execute('CREATE TABLE phases(measurement_id TEXT NOT NULL REFERENCES measurements(id), nodeid TEXT NOT NULL, worker TEXT, phase TEXT NOT NULL, state TEXT NOT NULL, outcome TEXT, duration_s REAL)')
                connection.execute('CREATE INDEX phase_lookup ON phases(measurement_id,nodeid,phase)')
                connection.execute('CREATE TABLE artifacts(measurement_id TEXT NOT NULL REFERENCES measurements(id), path TEXT NOT NULL, role TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL)')
                for name in KINDS:
                    connection.execute(f'CREATE TABLE {name}(measurement_id TEXT NOT NULL REFERENCES measurements(id), nodeid TEXT, phase TEXT, worker TEXT, data TEXT NOT NULL)')
                    connection.execute(f'CREATE INDEX {name}_lookup ON {name}(measurement_id,nodeid,phase)')
        validate_database(connection)
        if not writable:
            connection.execute('PRAGMA query_only=ON')
        yield connection
    finally:
        connection.close()


def selection_facts(selection):
    files = {}
    total = 0
    for selector in selection:
        path = Path(selector.split('::', 1)[0]).resolve()
        if not path.exists():
            raise ValueError('selected test does not exist: ' + selector)
        candidates = path.rglob('*.py') if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError('selected source must be a regular file')
            if candidate.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('selected source file is too large')
            total += candidate.stat().st_size
            if total > 256 * 1024 * 1024:
                raise ValueError('selected source bytes exceed the inventory budget')
            files[str(candidate)] = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if len(files) > 100_000:
                raise ValueError('selected source inventory is too large')
        for parent in (path.parent, *path.parents):
            for name in ('conftest.py', 'pytest.ini', 'pyproject.toml'):
                candidate = parent / name
                if candidate.is_file():
                    if candidate.is_symlink() or candidate.stat().st_size > 32 * 1024 * 1024:
                        raise ValueError('unsafe or oversized adjacent test configuration')
                    files[str(candidate)] = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if parent == PROJECT_ROOT or parent.parent == parent:
                break
    return {'files': files, 'sha256': hashlib.sha256(encoded(files).encode()).hexdigest()}


def provenance(selection, options):
    from tools.test_evidence import input_binding
    def git(*args):
        try:
            result = subprocess.run(['git', '-C', str(PROJECT_ROOT), *args], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip() if result.returncode == 0 else None
    return {'binding': input_binding(), 'commit': git('rev-parse', 'HEAD'),
            'dirty': bool(git('status', '--porcelain=v1')), 'selection': selection,
            'selection_sources': selection_facts(selection), 'options': options,
            'host': {'system': platform.system(), 'release': platform.release(),
                     'machine': platform.machine(), 'hostname': platform.node(),
                     'python': platform.python_version()}, 'tool_version': 1}


def stop_process(process):
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=5)


def artifact_size(directory):
    size, count = 0, 0
    for path in directory.rglob('*'):
        if path.is_symlink():
            raise ValueError('linked profiling artifact')
        if path.is_file():
            size += path.stat().st_size
            count += 1
    return size, count


def wait_child(command, environment, directory, timeout, max_bytes):
    started = time.monotonic()
    with (directory / 'process.log').open('xb') as stream:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=environment, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=os.name == 'posix')
        status, reason = 'complete', None
        try:
            while process.poll() is None:
                size, count = artifact_size(directory)
                if time.monotonic() - started > timeout or size > max_bytes or count > 4096:
                    status, reason = 'partial', 'time or artifact budget exceeded'
                    stop_process(process)
                    break
                time.sleep(.1)
        except KeyboardInterrupt:
            status, reason = 'interrupted', 'user interruption'
            stop_process(process)
        except BaseException:
            stop_process(process)
            raise
    size, count = artifact_size(directory)
    if status == 'complete' and (size > max_bytes or count > 4096):
        status, reason = 'partial', 'artifact budget exceeded'
    return process_exit_code(process.returncode), status, reason, time.monotonic() - started


def store_report(connection, measurement, report, expected_binding):
    if report.get('binding') != expected_binding:
        raise ValueError('test report source binding changed')
    telemetry = read_telemetry(report)
    cases = case_timings(report)
    if len(cases) > MAX_ROWS:
        raise ValueError('too many observed tests')
    for case in cases:
        for phase, value in case['phases'].items():
            connection.execute('INSERT INTO phases VALUES(?,?,?,?,?,?,?)',
                (measurement, case['nodeid'], case['worker'], phase, value['state'], value['outcome'], value['duration_s']))
    summaries = list(telemetry['workers'].values())
    if telemetry['controller'] is not None:
        summaries.append(telemetry['controller'])
    for summary in summaries:
        connection.execute('INSERT INTO processes VALUES(?,?,?,?,?)',
            (measurement, None, None, summary['worker'], encoded(summary)))
        for fixture in summary['fixtures']:
            connection.execute('INSERT INTO fixtures VALUES(?,?,?,?,?)',
                (measurement, None, 'setup', summary['worker'], encoded(fixture)))
            for nodeid in fixture['consumers']:
                connection.execute('INSERT INTO fixture_uses VALUES(?,?,?,?,?)',
                    (measurement, nodeid, 'setup', summary['worker'], encoded({'fixture_id': fixture['id']})))
    return telemetry['status']


def capture(connection, run_id, mode, iteration, warmup, directory, metadata, args):
    identity = str(uuid.uuid4())
    output = directory / identity
    output.mkdir(mode=0o700)
    with connection:
        connection.execute('INSERT INTO measurements VALUES(?,?,?,?,?,?,?,?,?)',
            (identity, run_id, mode, iteration, int(warmup), 'running', None, None, '{}'))
    report_path = output / 'test-report.json'
    command, environment = prepare_invocation(['--workers', args.workers, '--durations', '0',
        '--report', str(report_path), '--', *metadata['selection']], environment=os.environ)
    environment['PYTHONPATH'] = os.pathsep.join((str(PROJECT_ROOT), str(PROJECT_ROOT / 'src')))
    environment.pop('PYTEST_XDIST_AUTO_NUM_WORKERS', None)
    environment['PH_TEST_PROCESS_PARENT_PID'] = str(os.getpid())
    environment['PH_TEST_PROCESS_START_NS'] = str(time.perf_counter_ns())
    environment['PH_TEST_PROCESS_START_UTC'] = utc()
    code, status, reason, elapsed = wait_child(command, environment, output, args.timeout, args.max_bytes)
    details = {'reason': reason, 'command': command, 'collector': mode, 'process_exit_code': code,
               'scope': 'pytest phases; subprocess CPU and native memory are not measured',
               'artifact_directory': str(output)}
    test_exit = None
    try:
        from tools.test_evidence import input_binding
        if input_binding() != metadata['binding'] or selection_facts(metadata['selection']) != metadata['selection_sources']:
            raise ValueError('source inputs changed during measurement')
        if not report_path.is_file() or report_path.stat().st_size > min(args.max_bytes, 64 * 1024 * 1024):
            raise ValueError('missing or oversized test report')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if type(report.get('exitstatus')) is not int:
            raise ValueError('test exit status is unknown')
        test_exit = report['exitstatus']
        if code == 0:
            from tools.test_results import validate
            validate(report)
        with connection:
            observed = store_report(connection, identity, report, metadata['binding'])
        if observed != 'complete' and status == 'complete':
            status, details['reason'] = 'partial', 'incomplete phase telemetry'
    except (OSError, ValueError, KeyError, TypeError) as exc:
        if status == 'complete':
            status = 'partial'
        details['report_error'] = str(exc)
    with connection:
        for path in sorted(output.iterdir()):
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= args.max_bytes:
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                connection.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?)',
                    (identity, path.relative_to(directory.parent.parent).as_posix(), path.name,
                     digest.hexdigest(), path.stat().st_size, status))
        connection.execute('UPDATE measurements SET status=?,test_exit_code=?,elapsed_s=?,details=? WHERE id=?',
                           (status, test_exit, elapsed, encoded(details), identity))
    return (code if status == 'complete' else 130 if status == 'interrupted' else 2), status


def run(args):
    if args.workers != 'auto' and (not args.workers.isdecimal() or int(args.workers) < 1):
        raise ValueError('workers must be auto or a positive integer')
    selection = args.selection[1:] if args.selection[:1] == ['--'] else args.selection
    if not selection or any(not s or s.startswith('-') for s in selection):
        raise ValueError('run requires explicit test paths or node IDs after --')
    modes = args.modes.split(',')
    if not modes or len(set(modes)) != len(modes) or any(mode not in MODES for mode in modes):
        raise ValueError('unsupported or duplicate profiling mode')
    selection = [str(Path(s.split('::', 1)[0]).resolve()) + ('::' + s.split('::', 1)[1] if '::' in s else '') for s in selection]
    identity = str(uuid.uuid4())
    path = local_path(args.database)
    options = {key: getattr(args, key) for key in ('workers', 'repetitions', 'profile_repetitions', 'warmups', 'timeout', 'max_bytes')}
    metadata = provenance(selection, dict(options, modes=modes))
    with database(path, writable=True) as connection:
        directory = local_path(path.parent / 'runs' / identity)
        directory.mkdir(parents=True, mode=0o700, exist_ok=False)
        with connection:
            connection.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (identity, utc(), None, 'running', encoded(metadata)))
        exit_code, status = 0, 'complete'
        try:
            for mode in modes:
                repetitions = args.repetitions if mode == 'baseline' else args.profile_repetitions
                for iteration in range(args.warmups + repetitions):
                    code, measured = capture(connection, identity, mode, iteration,
                                             iteration < args.warmups, directory, metadata, args)
                    if code and not exit_code:
                        exit_code = code
                    if measured != 'complete':
                        status = measured
                    if measured == 'interrupted':
                        raise KeyboardInterrupt
            if exit_code and status == 'complete':
                status = 'failed'
        except KeyboardInterrupt:
            exit_code, status = 130, 'interrupted'
        except (OSError, ValueError, sqlite3.Error) as exc:
            metadata['tool_error'] = str(exc)
            exit_code, status = exit_code or 2, 'partial'
        with connection:
            connection.execute('UPDATE runs SET ended=?,status=?,metadata=? WHERE id=?',
                               (utc(), status, encoded(metadata), identity))
    return {'run_id': identity, 'database': str(path), 'status': status,
            'exit_code': exit_code or (0 if status == 'complete' else 2)}, exit_code or (0 if status == 'complete' else 2)


def load_run(connection, identity):
    row = connection.execute('SELECT id,started,ended,status,metadata FROM runs ORDER BY rowid DESC LIMIT 1').fetchone() if identity == 'latest' else connection.execute('SELECT id,started,ended,status,metadata FROM runs WHERE id=?', (identity,)).fetchone()
    if row is None:
        raise ValueError('unknown profiling run')
    return dict(zip(('run_id', 'started', 'ended', 'status', 'metadata'), (*row[:4], json.loads(row[4]))))


def rankings(connection, identity, phase):
    groups = {}
    for nodeid, seconds in connection.execute('SELECT p.nodeid,p.duration_s FROM phases p JOIN measurements m ON m.id=p.measurement_id WHERE m.run_id=? AND m.mode=? AND m.warmup=0 AND m.status=? AND p.phase=? AND p.state=? AND p.duration_s IS NOT NULL',
                                              (identity, 'baseline', 'complete', phase, 'measured')):
        groups.setdefault(nodeid, []).append(seconds)
    return sorted(({'nodeid': key, 'phase': phase, 'samples': len(values), 'median_s': statistics.median(values),
                    'min_s': min(values), 'max_s': max(values)} for key, values in groups.items()),
                  key=lambda row: (-row['median_s'], row['nodeid']))


def report_run(args):
    with database(args.database) as connection:
        result = load_run(connection, args.run)
        result['ranking'] = rankings(connection, result['run_id'], args.phase)[:args.top]
        result['measurements'] = [dict(zip(('id', 'mode', 'warmup', 'status', 'test_exit_code', 'elapsed_s', 'details'), (*row[:6], json.loads(row[6]))))
            for row in connection.execute('SELECT id,mode,warmup,status,test_exit_code,elapsed_s,details FROM measurements WHERE run_id=? ORDER BY rowid', (result['run_id'],))]
    return result


def compare_runs(args):
    with database(args.database) as connection:
        before, after = (load_run(connection, identity) for identity in (args.before, args.after))
        for run_info in (before, after):
            if run_info['status'] != 'complete':
                raise ValueError('comparison requires complete successful runs')
        for key in ('host', 'selection', 'options'):
            if before['metadata'][key] != after['metadata'][key]:
                raise ValueError('incomparable run ' + key)
        a, b = ({row['nodeid']: row for row in rankings(connection, r['run_id'], args.phase)} for r in (before, after))
        if not a or set(a) != set(b):
            raise ValueError('comparison needs the same measured baseline cases')
        rows = [{'nodeid': nodeid, 'phase': args.phase, 'before': a[nodeid], 'after': b[nodeid],
                 'difference_s': b[nodeid]['median_s'] - a[nodeid]['median_s']} for nodeid in sorted(a)]
        return {'before': before, 'after': after, 'comparisons': rows,
                'limitation': 'Observed baseline difference; no causal speedup or savings claim.'}


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be positive and finite')
    return number


def count(value):
    number = int(value)
    if not 1 <= number <= 1000:
        raise argparse.ArgumentTypeError('must be between 1 and 1000')
    return number


def parser():
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = result.add_subparsers(dest='command', required=True)
    capture_parser = commands.add_parser('run', allow_abbrev=False)
    capture_parser.add_argument('--database', type=Path, default=PROJECT_ROOT / 'build/test-profile/measurements.sqlite3')
    capture_parser.add_argument('--modes', default='baseline')
    capture_parser.add_argument('--workers', default='auto')
    capture_parser.add_argument('--repetitions', type=count, default=5)
    capture_parser.add_argument('--profile-repetitions', type=count, default=1)
    capture_parser.add_argument('--warmups', type=int, default=1, choices=range(0, 101))
    capture_parser.add_argument('--timeout', type=positive, default=3600.)
    capture_parser.add_argument('--max-bytes', type=int, default=64 * 1024 * 1024)
    capture_parser.add_argument('selection', nargs=argparse.REMAINDER)
    for name in ('report', 'compare'):
        read = commands.add_parser(name, allow_abbrev=False)
        read.add_argument('--database', type=Path, default=PROJECT_ROOT / 'build/test-profile/measurements.sqlite3')
        read.add_argument('--phase', choices=('setup', 'call', 'teardown'), default='call')
        read.add_argument('--format', choices=('json',), default='json')
        if name == 'report':
            read.add_argument('--run', default='latest')
            read.add_argument('--top', type=count, default=10)
        else:
            read.add_argument('--before', required=True)
            read.add_argument('--after', required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'run':
            if args.max_bytes < 1024 or args.max_bytes > 4 * 1024**3:
                raise ValueError('artifact budget must be between 1 KiB and 4 GiB')
            result, code = run(args)
        else:
            result, code = (report_run(args) if args.command == 'report' else compare_runs(args)), 0
        print(encoded(result))
        return code
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(encoded({'status': 'error', 'error': str(exc)}))
        return 2
