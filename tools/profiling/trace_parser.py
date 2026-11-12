"""Bounded streaming parser for the explicitly recorded strace dialect."""
from decimal import Decimal, InvalidOperation
import re

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
