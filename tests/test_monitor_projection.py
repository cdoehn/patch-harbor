"""Shared factual visibility and outcome semantics, independent of rendering."""
from copy import deepcopy

import pytest

from patchharbor.monitor_projection import observe, result_outcome
from patchharbor.monitor_session import result_semantic
from patchharbor.monitor_status import active_runs
from tests.test_monitor_activity import document, NOW


def test_completed_observation_cannot_remain_active_despite_stale_live_flag():
    value = document()
    row = value['live_view']['instances'][0]
    row['completed'] = True
    before = deepcopy(value)
    projected = observe(row, value, NOW)
    assert projected.completed and not projected.current and not projected.stale
    assert projected.status == 'unknown'
    assert not active_runs(value, now=NOW)
    assert projected.operation.task_sha256 == row['data']['task_sha256']
    assert projected.operation.bundle_number == '082'
    assert value == before


@pytest.mark.parametrize('data,outcome,semantic', [
    ({'primary_result': {'success': True}, 'result_status': 'created'}, 'success', 'clean'),
    ({'primary_result': {'success': True}, 'result_status': 'failed'}, 'failure', 'dirty'),
    ({'primary_result': {'success': False}, 'result_status': 'created'}, 'failure', 'dirty'),
    ({'primary_result': {'success': True}, 'stale': True}, 'unknown', 'unknown'),
    ({'replay_status': 'failed'}, 'failure', 'dirty'),
    ({}, 'unknown', 'unknown'),
])
def test_shared_result_outcome_preserves_failure_and_uncertainty(data, outcome, semantic):
    assert result_outcome(data) == outcome
    assert result_semantic(data) == semantic
    assert result_outcome(data, uncertain=True) == 'unknown'
