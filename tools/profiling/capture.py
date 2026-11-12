"""Local profiling capture; no implicit collection or network access."""
from __future__ import annotations

import hashlib
from dataclasses import asdict
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import sqlite3
import subprocess
import time
import uuid

from tools.profiling.common import encoded, local_path, utc
from tools.profiling.budgets import default_limits, exceeded, require_budget
from tools.profiling.storage import database, store_report
from tools.test_policy import PROJECT_ROOT, process_exit_code
from tools.test_runner import prepare_invocation

MODES = ('baseline', 'cprofile', 'memory', 'strace')


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
                     'python': platform.python_version()}, 'tool_version': 1,
            'dependencies': {name: importlib.metadata.version(name) for name in ('pytest', 'pytest-xdist')},
            'collector_sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(Path(__file__).parent.glob('*.py'))}}


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


def wait_child(command, environment, directory, timeout, max_bytes, max_files=None):
    max_files = default_limits().artifact_files if max_files is None else max_files
    started = time.monotonic()

    def limit_reason(size, count):
        return (exceeded('elapsed seconds', time.monotonic() - started, timeout, '--timeout')
                or exceeded('artifact bytes', size, max_bytes, '--max-bytes')
                or exceeded('artifact files', count, max_files, '--max-files'))

    with (directory / 'process.log').open('xb') as stream:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=environment, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=os.name == 'posix')
        status, reason = 'complete', None
        try:
            while process.poll() is None:
                size, count = artifact_size(directory)
                reason = limit_reason(size, count)
                if reason:
                    status = 'partial'
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
    if status == 'complete':
        reason = limit_reason(size, count)
        if reason:
            status = 'partial'
    return process_exit_code(process.returncode), status, reason, time.monotonic() - started


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
    if mode in ('cprofile', 'memory', 'strace'):
        command.extend(['-p', 'tools.profiling.collector'])
        environment.update(PH_PROFILE_MODE=mode, PH_PROFILE_DIRECTORY=str(output), PH_PROFILE_MEASUREMENT=identity,
                           PH_PROFILE_LIMITS=encoded(asdict(args.limits)))
    trace_info = None
    unavailable = None
    if mode == 'strace':
        from tools.profiling.tracing import trace_command
        try:
            command, trace_info = trace_command(command, output)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            unavailable = str(exc)
    if unavailable:
        code, status, reason, elapsed = 2, 'unavailable', unavailable, 0.
    else:
        code, status, reason, elapsed = wait_child(command, environment, output, args.timeout,
                                                  args.max_bytes, args.max_files)
    details = {'reason': reason, 'command': command, 'collector': mode, 'process_exit_code': code,
               'scope': 'pytest phases; subprocess CPU and native memory are not measured',
               'artifact_directory': str(output), 'strace': trace_info, 'budgets': asdict(args.limits)}
    test_exit = None
    try:
        from tools.test_evidence import input_binding
        if input_binding() != metadata['binding'] or selection_facts(metadata['selection']) != metadata['selection_sources']:
            raise ValueError('source inputs changed during measurement')
        if not report_path.is_file() or report_path.is_symlink():
            raise ValueError('missing or unsafe test report')
        require_budget('test report bytes', report_path.stat().st_size,
                       min(args.max_bytes, args.limits.report_bytes), '--max-bytes / --budget-scale')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if type(report.get('exitstatus')) is not int:
            raise ValueError('test exit status is unknown')
        test_exit = report['exitstatus']
        if code == 0:
            from tools.test_results import validate
            validate(report)
        with connection:
            observed = store_report(connection, identity, report, metadata['binding'])
            if mode in ('cprofile', 'memory', 'strace') and status == 'complete':
                from tools.profiling.python_data import import_python
                details['phase_collector'] = import_python(connection, identity, output, mode,
                                                           max_bytes=args.max_bytes, limits=args.limits)
                if mode == 'strace':
                    from tools.profiling.tracing import import_trace
                    details['syscalls'] = import_trace(connection, identity, output,
                                                       max_bytes=args.max_bytes, limits=args.limits)
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
        if status == 'complete' and not warmup:
            from tools.profiling.findings import derive_findings
            derive_findings(connection, identity, mode)
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
    options = {key: getattr(args, key) for key in ('workers', 'repetitions', 'profile_repetitions',
                                                  'warmups', 'timeout', 'max_bytes', 'max_files', 'budget_scale')}
    options['budgets'] = asdict(args.limits)
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
