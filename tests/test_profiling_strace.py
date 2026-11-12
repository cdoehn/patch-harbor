"""Bounded strace parsing and an explicitly requested local collector."""
import json
import platform
import shutil

import pytest

from tests.profiling_support import profile_run
from tools.profiling.storage import database
from tools.profiling.tracing import assign_phase, parse_trace


def span(pid=42, **changes):
    result = dict(native_thread_id=pid, process_id='process-a', start_utc_ns=1_000_000_000,
                  end_utc_ns=2_000_000_000, start_ns=100, end_ns=1_000_000_100,
                  nodeid='test_a', phase='call', worker='gw0')
    return dict(result, **changes)


def test_trace_reassembles_wait_and_keeps_signal(tmp_path):
    path = tmp_path / 'trace.42'
    path.write_text('1.100000 read(0x3, 0x123, 0x10 <unfinished ...>\n'
                    '1.110000 --- SIGCHLD {si_signo=SIGCHLD} ---\n'
                    '1.120000 <... read resumed>) = -1 EAGAIN (Resource temporarily unavailable) <0.020000>\n'
                    '1.130000 +++ exited with 0 +++\n')
    rows = list(parse_trace(path, 42))
    assert [r['kind'] for r in rows] == ['signal', 'syscall', 'exit']
    event = rows[1]
    assert event['start_ns'] == 1_100_000_000 and event['duration_ns'] == 20_000_000
    assert event['error'] and assign_phase(event, [span()])['nodeid'] == 'test_a'


def test_phase_assignment_does_not_guess_child_or_overlapping_call():
    event = dict(pid=42, start_ns=1_100_000_000, end_ns=1_200_000_000)
    assert assign_phase(event, [span(pid=43)]) is None
    assert assign_phase(dict(event, end_ns=2_100_000_000), [span()]) is None
    assert assign_phase(event, [span(), span(process_id='reused-pid')]) is None
    assert assign_phase(event, [span(end_ns=1_100)]) is None


@pytest.mark.parametrize('body', [
    '1.000000 read(0x1, 0x2, 0x3 <unfinished ...>\n',
    '1.000000 <... read resumed>) = 0x1 <0.1>\n',
    'not a supported trace\n',
    '1.000000 read(0x1) = 0x1 <..1>\n',
    '1.000000 ' + 'x' * 65536 + '\n',
])
def test_partial_or_unsupported_trace_cannot_be_complete(tmp_path, body):
    path = tmp_path / 'trace.42'
    path.write_text(body)
    with pytest.raises(ValueError):
        list(parse_trace(path, 42))


def test_raw_process_events_preserve_fork_exec_and_exit(tmp_path):
    path = tmp_path / 'trace.42'
    path.write_text('1.100000 clone(0x0, 0x0) = 0x2b <0.001000>\n'
                    '1.200000 execve(0x123, 0x456, 0x789) = 0x0 <0.002000>\n'
                    '1.300000 exit_group(0x0) = ?\n'
                    '1.300010 +++ exited with 0 +++\n')
    rows = list(parse_trace(path, 42))
    assert rows[0]['result'] == 43 and rows[1]['result'] == 0
    assert rows[0]['group'] == rows[1]['group'] == 'process'
    assert [r['kind'] for r in rows[2:]] == ['exit_call', 'exit']


def test_strace_missing_dependency_is_recorded_without_starting_tests(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', str(tmp_path))
    test = tmp_path / 'test_never.py'
    test.write_text('raise AssertionError("must not be imported without strace")\n')
    path = tmp_path / 'history.sqlite3'
    result, document = profile_run(path, test, '--modes', 'strace')
    assert result.returncode == 2 and document['status'] == 'unavailable'
    with database(path) as connection:
        assert connection.execute('SELECT status,test_exit_code FROM measurements').fetchone() == ('unavailable', None)
        assert connection.execute('SELECT count(*) FROM phases').fetchone() == (0,)


@pytest.mark.skipif(platform.system() != 'Linux' or shutil.which('strace') is None, reason='explicit strace backend unavailable')
def test_local_strace_keeps_raw_artifacts_and_phase_evidence(tmp_path):
    test = tmp_path / 'test_trace_probe.py'
    test.write_text('def test_read():\n with open(__file__, "rb") as stream: assert stream.read(4)\n')
    path = tmp_path / 'history.sqlite3'
    result, document = profile_run(path, test, '--modes', 'strace', '--timeout', '60')
    with database(path) as connection:
        status, details, exit_code = connection.execute('SELECT status,details,test_exit_code FROM measurements').fetchone()
        details = json.loads(details)
        # Restricted containers may deny ptrace even when strace is installed.
        if status == 'unavailable':
            assert result.returncode != 0 and details['reason'] and exit_code is None
            return
        if exit_code is None:
            assert result.returncode != 0 and status == 'partial' and details['process_exit_code'] != 0
            return
        assert result.returncode == 0, document | details
        rows = connection.execute('SELECT nodeid,phase,data FROM syscalls').fetchall()
        assert rows and any(nodeid and phase == 'call' for nodeid, phase, _ in rows)
        assert all(json.loads(data)['elapsed_ns'] >= 0 for _, _, data in rows)
        assert connection.execute("SELECT count(*) FROM artifacts WHERE role LIKE 'trace.%'").fetchone()[0] > 0
        assert connection.execute('SELECT count(*) FROM python_functions').fetchone() == (0,)
