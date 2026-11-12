"""Large trace indexes preserve ambiguity, clock and reused-thread semantics."""
import pytest

from tests.test_profiling_strace import span
from tools.profiling.trace_model import PhaseIndex, assign_phase


@pytest.mark.parametrize('rows', [
    [], [span()], [span(), span(pid=43)],
    [span(), span(start_utc_ns=1_200_000_000, start_ns=200_000_100)],
    [span(), span(process_id='reused')],
    [span(), span(process_id='reused', end_ns=1)],
    [span(end_ns=1)],
    [span(), span(start_utc_ns=2_000_000_000, end_utc_ns=3_000_000_000)],
])
def test_index_agrees_with_conservative_assignment(rows):
    index = PhaseIndex(rows)
    for pid in (42, 43, 99):
        for start in (0, 1_000_000_000, 1_100_000_000, 1_500_000_000, 2_000_000_000):
            for duration in (0, 100_000_000, 1_000_000_000):
                event = dict(pid=pid, start_ns=start, end_ns=start + duration)
                assert index.assign(event) == assign_phase(event, rows)


def test_full_suite_index_resolves_last_phase_and_keeps_children_unassigned():
    rows = [span(pid=42 + i % 12, nodeid=f'test_{i // 3}', phase=('setup','call','teardown')[i % 3],
                 start_utc_ns=i * 1_000_000_000, end_utc_ns=(i + 1) * 1_000_000_000)
            for i in range(15_000)]
    index = PhaseIndex(rows)
    last = rows[-1]
    event = dict(pid=last['native_thread_id'], start_ns=last['start_utc_ns'] + 1,
                 end_ns=last['end_utc_ns'] - 1)
    assert index.assign(event) == last
    assert index.assign(dict(event, pid=9999)) is None
