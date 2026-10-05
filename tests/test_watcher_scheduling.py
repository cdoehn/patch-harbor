"""Deterministic quiet deadlines, generation ownership and lock-only wakeups."""
from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from patchharbor import api
from patchharbor.errors import configuration_error
from patchharbor_watcher.apply_boundary import ApplyCompletion
from patchharbor_watcher.events import DirectoryEvent, EventBackendError, EventErrorKind, EventKind
from patchharbor_watcher.lifecycle import WatcherStopController
from patchharbor_watcher.loop import run_repository_watcher
from patchharbor_watcher.protocol import LockReference, Progress
from patchharbor_watcher.scheduling import Schedule


def completion(status='no_candidate', lock=None, code=10):
    return ApplyCompletion(code, {'command': 'apply', 'success': code == 0,
        'process_exit_code': code, 'error': None, 'watcher_progress': {
            'version': 1, 'status': status, 'blocked_on': None if lock is None else {
                'kind': lock.kind, 'repo_id': lock.repo_id}}}, None, '')


def target(path):
    identity = path.stat()
    return api.ExchangeWatchTarget(path, identity.st_dev, identity.st_ino, (api.RepositoryId('00000000-0000-4000-8000-000000000001'),))


class InlineWorker:
    def __init__(self, *, target, args, name):
        self.target, self.args = target, args
    def start(self):
        self.target(*self.args)
    def join(self):
        pass


class Harness:
    def __init__(self, tmp_path):
        self.a, self.b = tmp_path / 'a', tmp_path / 'b'
        self.a.mkdir(); self.b.mkdir()
        self.registry = tmp_path / 'registry.json'
        self.registry.write_text('{}')
        self.controls = api.WatchControlPaths(self.registry, (), (self.a, self.b))
        self.targets = (target(self.a),)
        self.now, self.timeline, self.calls, self.reads, self.sources = 0.0, [], [], [], []
        self.probes, self.fail, self.woken = [], None, False
        self.controller = WatcherStopController()
        self.log, self.errors = StringIO(), StringIO()
        self.on_apply = lambda targets: completion()
        self.on_probe = lambda lock: None

    def clock(self):
        return self.now

    def provider(self):
        if self.fail:
            raise self.fail
        return api.WatchTargets(self.targets, self.registry, ())

    def at(self, when, directory=None, name='bundle', kind=EventKind.CHANGED, action=None):
        self.timeline.append((when, DirectoryEvent(kind, directory or self.a, name), action))
        self.timeline.sort(key=lambda item: item[0])

    def factory(self, directories):
        owner = self
        class Source:
            closed = False
            def read(self, timeout=None):
                owner.reads.append((owner.now, timeout))
                if owner.timeline and owner.timeline[0][0] <= owner.now:
                    when, event, action = owner.timeline.pop(0)
                    if action:
                        action()
                    return (event,)
                if owner.woken:
                    owner.woken = False
                    return ()
                if timeout == 0:
                    return ()
                if timeout is None and not owner.timeline:
                    owner.controller.request_stop()
                    return ()
                due = float('inf') if timeout is None else owner.now + timeout
                if owner.timeline and owner.timeline[0][0] <= due:
                    owner.now = owner.timeline[0][0]
                    return self.read(0)
                owner.now = due
                return ()
            def wake(self):
                owner.woken = True
            def close(self):
                self.closed = True
        source = Source()
        self.sources.append((directories, source))
        return source

    def delegate(self, *, exchanges):
        self.calls.append((self.now, exchanges))
        return self.on_apply(exchanges)

    def readiness(self, lock):
        self.probes.append((self.now, lock))
        return self.on_probe(lock)

    def run(self):
        run_repository_watcher(delegate=self.delegate, log_stream=self.log, error_stream=self.errors,
            stop_requested=self.controller.stop_requested, bind_wake=self.controller.bind_wake,
            target_provider=self.provider, control_provider=lambda: self.controls,
            readiness=self.readiness, source_factory=self.factory, clock=self.clock,
            worker_factory=InlineWorker)
        assert all(source.closed for _, source in self.sources)


def test_initial_quiet_period_resets_and_idle_has_no_recurring_deadline(tmp_path):
    h = Harness(tmp_path)
    h.at(3); h.at(7)
    h.run()
    assert [t for t, _ in h.calls] == [12]
    assert h.reads[-1] == (12, None)
    assert not h.probes


def test_already_queued_event_wins_over_expiring_timer(tmp_path):
    h = Harness(tmp_path)
    h.at(5)
    h.run()
    assert [t for t, _ in h.calls] == [10]


def test_busy_root_does_not_delay_an_independent_quiet_root(tmp_path):
    h = Harness(tmp_path)
    h.targets = (target(h.a), target(h.b))
    h.at(3, h.b); h.at(7, h.b)
    h.run()
    assert [(t, tuple(v.directory for v in targets)) for t, targets in h.calls] == [(5, (h.a,)), (12, (h.b,))]


def test_events_during_apply_survive_completion_of_the_previous_generation(tmp_path):
    h = Harness(tmp_path)
    def apply(targets):
        if len(h.calls) == 1:
            h.now = 6
            h.at(6)
        return completion()
    h.on_apply = apply
    h.run()
    assert [t for t, _ in h.calls] == [5, 11]


def test_confirmed_attempt_drains_existing_work_then_goes_idle(tmp_path):
    h = Harness(tmp_path)
    outcomes = iter([completion('attempted', code=23), completion('attempted', code=0), completion()])
    h.on_apply = lambda targets: next(outcomes)
    h.run()
    assert [t for t, _ in h.calls] == [5, 5, 5]
    assert h.reads[-1] == (5, None)


def test_lock_uses_readiness_backoff_without_scan_and_resumes_after_release(tmp_path):
    h = Harness(tmp_path)
    lock = LockReference('exchange_state')
    h.on_apply = lambda targets: completion('locked', lock) if len(h.calls) == 1 else completion()
    h.on_probe = lambda known: lock if len(h.probes) == 1 else None
    h.run()
    assert [t for t, _ in h.calls] == [5, 20]
    assert h.probes == [(10, lock), (20, lock)]


def test_readiness_backoff_caps_at_300_and_changes_keep_the_quiet_condition(tmp_path):
    s = Schedule(); t = target(tmp_path)
    s.replace((t,), 0); snapshot = s.begin(s.ready(5))
    lock = LockReference('registry')
    s.finish(snapshot, Progress('locked', lock), 5)
    now = 5
    for delay in (5, 10, 20, 40, 80, 160, 300, 300):
        assert s.timeout(now) == delay
        now += delay
        assert s.probes(now) == (lock,) and s.ready(now) == ()
        s.probed(lock, lock, now)
    s.changed(tmp_path, now)
    s.probed(lock, None, now)
    assert s.ready(now + 4.999) == () and s.ready(now + 5) == (t,)


def test_configuration_switch_discards_old_scope_and_initializes_new_one(tmp_path):
    h = Harness(tmp_path)
    h.at(7, h.registry.parent, h.registry.name, action=lambda: setattr(h, 'targets', (target(h.b),)))
    h.run()
    assert [(t, targets[0].directory) for t, targets in h.calls] == [(5, h.a), (12, h.b)]
    assert len(h.sources) == 2


def test_broken_configuration_suspends_apply_until_repair_event(tmp_path):
    h = Harness(tmp_path)
    h.at(2, h.registry.parent, h.registry.name, action=lambda: setattr(h, 'fail', configuration_error('broken')))
    h.at(9, h.registry.parent, h.registry.name, action=lambda: setattr(h, 'fail', None))
    h.run()
    assert [t for t, _ in h.calls] == [14]
    assert h.errors.getvalue()


def test_root_loss_and_return_rebuild_identity_before_another_full_quiet_period(tmp_path):
    h = Harness(tmp_path)
    def remove():
        h.a.rmdir(); h.fail = configuration_error('missing')
    def restore():
        h.a.mkdir(); h.targets = (target(h.a),); h.fail = None
    h.at(2, kind=EventKind.ROOT_INVALIDATED, action=remove)
    h.at(9, h.a.parent, h.a.name, action=restore)
    h.run()
    assert [t for t, _ in h.calls] == [14]


def test_initially_missing_root_is_observed_using_core_restoration_hint(tmp_path):
    h = Harness(tmp_path)
    h.a.rmdir(); h.fail = configuration_error('missing at startup')
    def restore():
        h.a.mkdir(); h.targets = (target(h.a),); h.fail = None
    h.at(8, h.a.parent, h.a.name, action=restore)
    h.run()
    assert [t for t, _ in h.calls] == [13]


def test_overflow_rebinds_and_restarts_quiet_period(tmp_path):
    h = Harness(tmp_path)
    h.at(4, kind=EventKind.OVERFLOW)
    h.run()
    assert [t for t, _ in h.calls] == [9] and len(h.sources) == 2


@pytest.mark.parametrize('status', ['error', 'dry_run'])
def test_no_speculative_followup_without_consumed_identity(tmp_path, status):
    h = Harness(tmp_path)
    h.on_apply = lambda targets: completion(status)
    h.run()
    assert len(h.calls) == 1


def test_stop_prevents_next_worker_and_closes_all_sources(tmp_path):
    h = Harness(tmp_path)
    h.at(5, action=h.controller.request_stop)
    h.run()
    assert h.calls == []


def test_worker_exception_propagates_and_releases_resources(tmp_path):
    h = Harness(tmp_path)
    def fail(targets):
        raise OSError('worker failed')
    h.on_apply = fail
    with pytest.raises(OSError):
        h.run()
    assert all(source.closed for _, source in h.sources)


def test_backend_failure_is_not_idle_or_a_polling_fallback(tmp_path):
    h = Harness(tmp_path)
    def fail():
        raise EventBackendError(EventErrorKind.IO, 'backend stopped')
    h.at(2, action=fail)
    with pytest.raises(EventBackendError):
        h.run()
    assert h.calls == [] and all(source.closed for _, source in h.sources)


def test_registry_lock_during_refresh_uses_readiness_and_then_new_start_deadline(tmp_path):
    from patchharbor.errors import LockBusyError, repository_busy_error
    h = Harness(tmp_path)
    h.fail = LockBusyError(repository_busy_error(), api.ApplyLock(api.ApplyLockKind.REGISTRY))
    def available(lock):
        h.fail = None
        return None
    h.on_probe = available
    h.run()
    assert h.probes == [(5, LockReference('registry'))]
    assert [t for t, _ in h.calls] == [10]


def test_rebinding_during_apply_prevents_old_idle_completion_from_clearing_new_work(tmp_path):
    h = Harness(tmp_path)
    def apply(targets):
        if len(h.calls) == 1:
            h.now = 6
            h.at(6, h.registry.parent, h.registry.name,
                 action=lambda: setattr(h, 'targets', (target(h.b),)))
        return completion()
    h.on_apply = apply
    h.run()
    assert [(t, scope[0].directory) for t, scope in h.calls] == [(5, h.a), (11, h.b)]


def test_stop_during_worker_prevents_progress_driven_followup(tmp_path):
    h = Harness(tmp_path)
    def apply(targets):
        h.controller.request_stop()
        return completion('attempted', code=0)
    h.on_apply = apply
    h.run()
    assert len(h.calls) == 1
