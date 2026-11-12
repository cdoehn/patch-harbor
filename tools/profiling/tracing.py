"""Explicit strace command and single-controller import of bounded evidence."""
from collections import defaultdict
import json
import platform
import shutil
import subprocess

from tools.profiling.common import encoded
from tools.profiling.budgets import default_limits, require_budget
from tools.profiling.trace_parser import parse_trace
from tools.profiling.trace_model import assign_phase


def trace_command(command, output):
    executable = shutil.which('strace') if platform.system() == 'Linux' else None
    if executable is None:
        raise ValueError('strace unavailable on this host; install it separately to opt in')
    info = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=5, check=False)
    help_text = subprocess.run([executable, '--help'], capture_output=True, text=True, timeout=5, check=False)
    if info.returncode or help_text.returncode or '--kill-on-exit' not in help_text.stdout:
        raise ValueError('strace lacks the required child cleanup capability')
    return ([executable, '-ff', '-ttt', '-T', '-s', '64', '-e', 'raw=all', '-e', 'trace=all',
             '-I', '1', '--kill-on-exit', '-o', str(output / 'trace'), '--', *command],
            {'version': info.stdout.splitlines()[0], 'arguments': 'raw addresses; no decoded buffers',
             'scope': 'new test process and descendants only; syscall elapsed time is not CPU time'})


def import_trace(connection, measurement, directory, *, max_bytes, limits=None):
    limits = default_limits() if limits is None else limits
    spans = [json.loads(row[0]) for row in connection.execute(
        'SELECT data FROM processes WHERE measurement_id=? AND phase IS NOT NULL', (measurement,))]
    files = sorted(directory.glob('trace.*'))
    if not files:
        raise ValueError('strace produced no usable files')
    require_budget('strace process files', len(files), limits.artifact_files, '--max-files')
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError('unsafe strace artifacts')
    total = sum(path.stat().st_size for path in files)
    require_budget('strace bytes', total, max_bytes, '--max-bytes')
    groups = defaultdict(lambda: {'count': 0, 'errors': 0, 'elapsed_ns': 0})
    process_events = []
    count = 0
    for path in files:
        if not path.suffix[1:].isdigit():
            raise ValueError('invalid strace process identity')
        pid = int(path.suffix[1:])
        segment = 0
        for event in parse_trace(path, pid):
            count += 1
            require_budget('strace events', count, limits.trace_events)
            if event['kind'] != 'syscall':
                process_events.append(dict(event, exec_segment=segment))
                require_budget('normalized strace rows', len(groups) + len(process_events), limits.trace_rows)
                continue
            if event['name'] in ('execve', 'execveat') and event['result'] == 0:
                segment += 1
                process_events.append(dict(event, exec_segment=segment))
            if event['name'] in ('clone', 'clone3', 'fork', 'vfork') and event['result'] is not None and event['result'] > 0:
                process_events.append(dict(event, child_pid=event['result'], exec_segment=segment,
                                           child_kind='unknown process or thread'))
            span = assign_phase(event, spans)
            key = (pid, segment, span['nodeid'] if span else None, span['phase'] if span else None,
                   span['worker'] if span else None, event['name'], event['group'])
            aggregate = groups[key]
            aggregate['count'] += 1
            aggregate['errors'] += int(event['error'])
            aggregate['elapsed_ns'] += event['duration_ns']
            require_budget('normalized strace rows', len(groups) + len(process_events), limits.trace_rows)
    for (pid, segment, nodeid, phase, worker, name, group), totals in groups.items():
        data = dict(totals, pid=pid, exec_segment=segment, syscall=name, group=group,
                    attribution='observed interval' if phase else 'unassigned',
                    scope='syscall elapsed time, may overlap across processes; not CPU time')
        connection.execute('INSERT INTO syscalls VALUES(?,?,?,?,?)',
                           (measurement, nodeid, phase, worker, encoded(data)))
    for event in process_events:
        connection.execute('INSERT INTO processes VALUES(?,?,?,?,?)',
                           (measurement, None, None, None, encoded(event)))
    return {'events': count, 'process_files': len(files), 'groups': len(groups),
            'unassigned_groups': sum(key[3] is None for key in groups),
            'scope': 'Only a unique instrumented thread interval is assigned; other activity stays unassigned.'}
