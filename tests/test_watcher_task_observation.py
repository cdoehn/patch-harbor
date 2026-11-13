"""Task observation contracts without UI rendering or a second execution path."""
from copy import deepcopy
import json

import pytest

from patchharbor import api
from patchharbor.monitor_live_schema import parse_live
from patchharbor_watcher.observation import live_observation
from patchharbor_watcher.protocol import LockReference, Progress
from patchharbor_watcher.scheduling import Schedule
from tests.test_watcher_polling import PollHarness
from tests.watcher_support import completion, target


IDENTITY = '00000000-0000-4000-8000-000000000001'


@pytest.mark.parametrize('kind', ['registry', 'repository', 'exchange_state'])
@pytest.mark.parametrize('executing', [False, True])
def test_execution_observation_preserves_pending_locks_without_probing_or_consuming(
    tmp_path, monkeypatch, kind, executing,
):
    watched = target(tmp_path)
    schedule = Schedule()
    schedule.replace((watched,), 10)
    lock = LockReference(kind, IDENTITY if kind == 'repository' else None)
    schedule.finish(schedule.begin((watched,)), Progress('locked', lock), 20)
    before = deepcopy(schedule.__dict__)

    def forbidden(*args, **kwargs):
        pytest.fail('observation must not acquire locks or execute Core operations')

    for name in ('execute_readiness', 'execute_next', 'execute', 'bundle'):
        monkeypatch.setattr(api, name, forbidden)
    active = (tmp_path,) if executing else ()
    facts = live_observation(schedule, (tmp_path,), executing=executing,
        control_lock=None, control_probe=None, now=21, wall=1000, active_exchanges=active)

    assert facts['phase'] == ('executing' if executing else 'watching')
    assert facts['activity_code'] == ('executing' if executing else kind + '-lock')
    assert facts['activity_status'] == ('running' if executing else 'waiting')
    assert facts['active_exchanges'] == [str(p) for p in active]
    observed, = facts['targets']
    assert observed['directory'] == str(tmp_path)
    assert observed['repository_ids'] == [IDENTITY]
    assert observed['dirty'] is True and observed['quiet_until'] == 1000
    assert observed['blocked_on'] == {'kind': kind, 'repo_id': lock.repo_id}
    assert observed['probe_at'] == 1004
    assert schedule.__dict__ == before
    assert not {'task_sha256', 'bundle_number', 'entrypoint_name', 'completed_commit'} & facts.keys()


@pytest.mark.parametrize('status,code,event', [
    ('attempted', 0, 'automatic_execute_completed'),
    ('attempted', 23, 'automatic_execute_failed'),
    ('no_candidate', 10, 'waiting_for_exchange_task'),
])
def test_polling_publishes_active_scope_until_actual_worker_completion(tmp_path, status, code, event):
    harness = PollHarness((target(tmp_path),), cycles=1)
    observed = []

    def delegate(*, exchanges):
        assert exchanges == harness.targets
        facts = deepcopy(harness.publication.data)
        assert facts['phase'] == facts['activity_code'] == 'executing'
        assert facts['watcher_mode'] == 'poll'
        assert facts['active_exchanges'] == [str(tmp_path)]
        assert facts['next_poll_at'] is None
        assert not {'run_id', 'task_sha256', 'bundle_number', 'completed_commit'} & facts.keys()
        assert harness.log.getvalue().count('automatic_execute_') == 0
        observed.append(facts)
        return completion(status, code=code)

    harness.run(delegate=delegate)
    assert len(observed) == 1 and harness.waits == [4]
    records = [json.loads(line) for line in harness.log.getvalue().splitlines()]
    operational = [r for r in records if 'execute_result' in r]
    assert len(operational) == 1 and operational[0]['event'] == event
    assert operational[0]['process_exit_code'] == code
    assert operational[0]['execute_result']['command'] == 'execute'
    assert harness.publication.data['active_exchanges'] == []
    assert harness.publication.closed


def _execution_document():
    stamp = '2026-11-11T12:00:00Z'
    return dict(format_version=3, kind='execute', instance_id=IDENTITY, pid=123,
        process_identity=None, started_at=stamp, updated_at=stamp, facts_updated_at=stamp,
        completed=False, phase='entrypoint', log_tail='', history=[],
        activity=dict(sequence=1, at=stamp, since=stamp, code='entrypoint', status='running', message=''),
        data=dict(run_id=IDENTITY, repo_id=IDENTITY, origin='manual', dry_run=False,
            task_path='/repository/task.zip', task_sha256='a' * 64,
            entrypoint_name='run.sh', bundle_number='093'))


@pytest.mark.parametrize('version', [1, 2, 4, True])
def test_old_and_unknown_live_generations_are_not_current_execute_evidence(version):
    row = _execution_document()
    name = 'execute-' + IDENTITY + '.json'
    assert parse_live(json.dumps(row).encode(), name) == row
    row['format_version'] = version
    with pytest.raises(ValueError):
        parse_live(json.dumps(row).encode(), name)


@pytest.mark.parametrize('old_field', ['patch_path', 'patch_sha256', 'apply_status'])
def test_mixed_legacy_fields_are_rejected_without_changing_task_identity(old_field):
    row = _execution_document()
    name = 'execute-' + IDENTITY + '.json'
    row['data'][old_field] = 'legacy'
    before = deepcopy(row)
    with pytest.raises(ValueError):
        parse_live(json.dumps(row).encode(), name)
    assert row == before


def test_retired_kind_is_not_an_alias_for_execute_observation():
    row = _execution_document()
    row['kind'] = 'apply'
    with pytest.raises(ValueError):
        parse_live(json.dumps(row).encode(), 'apply-' + IDENTITY + '.json')
