"""Full-suite capacities and explicit local overrides without allocating them."""
import json
import os
import sys

import pytest

from tools.profiling.application import parser
from tools.profiling.budgets import requested_limits
from tools.profiling.capture import wait_child


def limits(*options):
    return requested_limits(parser().parse_args(['run', *options, '--', 'tests']))


def test_default_capacity_covers_full_suite_with_tenfold_reserve():
    budget = limits()
    # Last accepted run: 3,968 collected tests, 11,890 phase events,
    # 32,385,431 report bytes. A cProfile phase writes JSON plus raw pstats.
    assert budget.report_bytes >= 10 * 32_385_431
    assert budget.collector_records >= 10 * (3 * 5000 + 2 * (256 + 1))
    assert budget.artifact_files >= 10 * (2 * (3 * 5000 + 514) + 100_000)
    assert budget.profile_rows >= 10 * 5000 * 3 * 1000
    assert budget.artifact_bytes >= 10 * 32 * 1024**3
    assert budget.timeout_s >= 10 * 12 * 3600
    assert budget.trace_events >= 10 * 100_000_000


def test_large_explicit_budget_is_accepted_and_scaling_keeps_overrides():
    budget = limits('--budget-scale', '2', '--max-bytes', str(1024**4),
                    '--timeout', '.2', '--max-files', '7')
    assert budget.artifact_bytes == 1024**4  # former 4 GiB ceiling removed
    assert budget.timeout_s == .2 and budget.artifact_files == 7
    assert budget.profile_rows == 2 * limits().profile_rows
    assert budget.record_bytes == 2 * limits().record_bytes


@pytest.mark.parametrize('option,value', [('--budget-scale','0'), ('--max-files','-1'),
                                        ('--max-bytes','0'), ('--timeout','nan')])
def test_invalid_operational_budget_is_rejected(option, value):
    with pytest.raises(SystemExit):
        limits(option, value)


def test_artifact_minimum_is_still_enforced():
    with pytest.raises(ValueError, match='at least 1 KiB'):
        limits('--max-bytes', '1023')


def test_capture_accepts_more_than_old_file_ceiling(tmp_path):
    command = [sys.executable, '-I', '-B', '-c',
               'from pathlib import Path\n'
               f'root=Path({str(tmp_path)!r})\n'
               'for i in range(4100): (root/str(i)).write_bytes(b"x")\n']
    code, status, reason, _ = wait_child(command, os.environ.copy(), tmp_path, 60, 1024**2)
    assert (code, status, reason) == (0, 'complete', None)
    assert len(list(tmp_path.iterdir())) == 4101


@pytest.mark.parametrize('budget,expected', [('files', '--max-files'), ('bytes', '--max-bytes')])
def test_explicit_artifact_budget_reports_the_actual_boundary(tmp_path, budget, expected):
    command = [sys.executable, '-I', '-B', '-c',
               'from pathlib import Path\n'
               f'root=Path({str(tmp_path)!r})\n'
               '(root/"a").write_bytes(b"x"*2048)\n(root/"b").touch()\n']
    _, status, reason, _ = wait_child(command, os.environ.copy(), tmp_path, 60,
                                     1024 if budget == 'bytes' else 4096,
                                     2 if budget == 'files' else 100)
    assert status == 'partial' and expected in reason
    assert 'observed=' in reason and 'limit=' in reason


def test_effective_budgets_are_retained_in_local_history(tmp_path):
    from tests.profiling_support import profile_run
    from tools.profiling.storage import database
    test = tmp_path / 'test_probe.py'
    test.write_text('def test_probe(): pass\n')
    path = tmp_path / 'profile.sqlite3'
    result, _ = profile_run(path, test, '--budget-scale', '2', '--max-files', '50000')
    assert result.returncode == 0, result.stdout + result.stderr
    with database(path) as connection:
        metadata = json.loads(connection.execute('SELECT metadata FROM runs').fetchone()[0])
        details = json.loads(connection.execute('SELECT details FROM measurements').fetchone()[0])
    assert metadata['options']['budgets'] == details['budgets']
    assert details['budgets']['artifact_files'] == 50000
    assert details['budgets']['profile_rows'] == 2 * limits().profile_rows
