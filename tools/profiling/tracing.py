"""Explicit Linux strace capture and conservative phase correlation."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import json
import platform
import re
import shutil
import subprocess

from tools.profiling.common import encoded

LINE = re.compile(r'^(\d+\.\d+)\s+(.*)$')
CALL = re.compile(r'^([A-Za-z_][A-Za-z_0-9]*)\((.*)\)\s+=\s+(.*?)\s+<([0-9.]+)>$')
RESUMED = re.compile(r'^<\.\.\. ([A-Za-z_][A-Za-z_0-9]*) resumed>(.*)$')


def nanoseconds(raw):
    try:
        value = Decimal(raw)
        if not value.is_finite() or value < 0 or value > Decimal('100000000000'):
            raise ValueError('invalid strace time')
        return int(value * 1_000_000_000)
    except InvalidOperation:
        raise ValueError('invalid strace decimal time') from None


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


def syscall_group(name):
    if name.startswith(('open', 'stat', 'lstat', 'fstat', 'access', 'readlink', 'unlink', 'rename', 'mkdir', 'getdents')):
        return 'filesystem'
    if name.startswith(('read', 'write', 'close', 'dup', 'fcntl', 'ioctl', 'lseek', 'poll', 'select', 'epoll', 'fsync')):
        return 'io'
    if name.startswith(('clone', 'fork', 'vfork', 'exec', 'wait', 'exit')):
        return 'process'
    if name.startswith(('mmap', 'munmap', 'mprotect', 'mremap', 'brk', 'madvise')):
        return 'memory'
    if name.startswith(('futex', 'nanosleep', 'clock_nanosleep')):
        return 'synchronization'
    if name.startswith(('socket', 'connect', 'accept', 'send', 'recv', 'bind', 'listen')):
        return 'network'
    return 'other'


def parse_trace(path, pid):
    """Stream one -ff file, retaining unfinished/resumed calls and process events."""
    pending = None
    with path.open(encoding='utf-8', errors='strict') as stream:
        line_number = 0
        while True:
            line = stream.readline(65537)
            if not line:
                break
            line_number += 1
            if len(line) > 65536:
                raise ValueError('oversized strace line')
            match = LINE.match(line.rstrip('\n'))
            if not match:
                raise ValueError(f'unsupported strace line {line_number}')
            start = nanoseconds(match[1])
            body = match[2]
            if body.startswith(('--- ', '+++ ')):
                yield {'kind': 'signal' if body.startswith('--- ') else 'exit', 'pid': pid, 'start_ns': start}
                continue
            if body.endswith('<unfinished ...>'):
                if pending is not None:
                    raise ValueError('overlapping unfinished strace calls')
                pending = (start, body[:-len('<unfinished ...>')])
                continue
            resumed = RESUMED.match(body)
            if resumed:
                if pending is None or not pending[1].startswith(resumed[1] + '('):
                    raise ValueError('orphan resumed strace call')
                start, prefix = pending
                pending = None
                body = prefix + resumed[2]
            if re.match(r'^exit(_group)?\(.*\)\s+=\s+\?$', body):
                yield {'kind': 'exit_call', 'pid': pid, 'start_ns': start}
                continue
            call = CALL.match(body)
            if not call:
                raise ValueError(f'unsupported syscall at strace line {line_number}')
            duration = nanoseconds(call[4])
            result = call[3].split()[0]
            try:
                returned = int(result, 0)
            except ValueError:
                returned = None
            yield {'kind': 'syscall', 'pid': pid, 'start_ns': start, 'end_ns': start + duration,
                   'name': call[1], 'duration_ns': duration, 'result': returned,
                   'error': bool(re.search(r'\bE[A-Z0-9]+\b', call[3])), 'group': syscall_group(call[1])}
    if pending is not None:
        raise ValueError('truncated unfinished strace call')


def assign_phase(event, spans):
    matches = []
    for span in spans:
        if span['native_thread_id'] != event['pid']:
            continue
        # UTC is needed for strace, but monotonic duration detects clock jumps.
        if abs((span['end_utc_ns'] - span['start_utc_ns']) - (span['end_ns'] - span['start_ns'])) > 50_000_000:
            continue
        if span['start_utc_ns'] <= event['start_ns'] and event['end_ns'] <= span['end_utc_ns']:
            matches.append(span)
    if len(matches) != 1:
        return None
    # A reused numeric TID without a proven lifetime is deliberately unassigned.
    if len({s['process_id'] for s in spans if s['native_thread_id'] == event['pid']}) != 1:
        return None
    return matches[0]


def import_trace(connection, measurement, directory, *, max_bytes):
    spans = [json.loads(row[0]) for row in connection.execute(
        'SELECT data FROM processes WHERE measurement_id=? AND phase IS NOT NULL', (measurement,))]
    files = sorted(directory.glob('trace.*'))
    if not files or len(files) > 4096:
        raise ValueError('strace produced no usable files or too many processes')
    total = sum(path.stat().st_size for path in files)
    if total > max_bytes or any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError('unsafe or excessive strace artifacts')
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
            if count > 1_000_000:
                raise ValueError('strace event budget exceeded')
            if event['kind'] != 'syscall':
                process_events.append(dict(event, exec_segment=segment))
                if len(groups) + len(process_events) > 250_000:
                    raise ValueError('normalized strace row budget exceeded')
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
            if len(groups) + len(process_events) > 250_000:
                raise ValueError('normalized strace row budget exceeded')
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
