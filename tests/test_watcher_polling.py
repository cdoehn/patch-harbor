"""Polling cadence, scope refresh, failure recovery and interruptible lifetime."""
from io import StringIO
import json
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from patchharbor_watcher.lifecycle import WatcherStopController
from patchharbor_watcher.polling import run_polling_watcher
from tests.watcher_support import completion, target


class Publication:
    def __init__(self):
        self.rows, self.data, self.closed = [], {}, False

    def update(self, **facts):
        self.data.update(facts)
        self.rows.append(dict(self.data))

    def close(self):
        self.closed = True


class PollHarness:
    def __init__(self, targets=(), cycles=2):
        self.now, self.cycles = 100.0, cycles
        self.targets, self.waits, self.calls = targets, [], []
        self.publication = Publication()
        self.log, self.errors = StringIO(), StringIO()

    def wait(self, seconds):
        self.waits.append(seconds)
        self.now += seconds
        return self.stopped()

    def stopped(self):
        return len(self.waits) >= self.cycles

    def delegate(self, *, exchanges):
        self.calls.append((self.now, exchanges))
        self.now += 3  # Discovery/Execute takes time; it must never overlap a poll.
        return completion()

    def run(self, **options):
        defaults = dict(delegate=self.delegate, target_provider=lambda: SimpleNamespace(exchanges=self.targets),
                        log_stream=self.log, error_stream=self.errors, stop_requested=self.stopped,
                        wait=self.wait, publication_factory=lambda: self.publication,
                        clock=lambda: self.now, wall_clock=lambda: 1000 + self.now)
        run_polling_watcher(**(defaults | options))


def test_default_poll_runs_immediately_and_waits_four_seconds_after_completion(tmp_path):
    h = PollHarness((target(tmp_path),), cycles=3)
    h.run()
    assert [at for at, _ in h.calls] == [100, 107, 114]
    assert h.waits == [4, 4, 4]
    assert all(scope == h.targets for _, scope in h.calls)
    waiting = [r for r in h.publication.rows if r.get('activity_code') == 'poll-wait']
    assert waiting[0]['next_poll_at'] == 1107
    assert waiting[0]['watcher_mode'] == 'poll' and waiting[0]['poll_interval_seconds'] == 4
    assert waiting[0]['subscriptions'] == []
    assert h.publication.data['next_poll_at'] is None and h.publication.closed


def test_fractional_poll_refreshes_targets_after_each_completed_check(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'; a.mkdir(); b.mkdir()
    scopes = [(target(a),), (target(b),)]
    h = PollHarness()
    h.run(interval=.125, target_provider=lambda: SimpleNamespace(exchanges=scopes[len(h.calls)]))
    assert [scope for _, scope in h.calls] == scopes
    assert h.waits == [.125, .125]
    assert h.publication.data['targets'][0]['directory'] == str(b)


def test_empty_registry_is_rechecked_and_very_large_wait_remains_interruptible():
    h = PollHarness(cycles=1)
    h.run(interval=1e100)
    assert not h.calls and h.waits == [86400]
    assert h.publication.closed


def test_configuration_failure_is_not_applied_and_recovers_on_next_poll(tmp_path):
    h = PollHarness((target(tmp_path),), cycles=3)
    reads = []
    def targets():
        reads.append(h.now)
        if len(reads) < 3:
            raise OSError('exchange unavailable')
        return SimpleNamespace(exchanges=h.targets)
    h.run(target_provider=targets)
    assert reads == [100, 104, 108]
    assert len(h.calls) == 1 and h.calls[0][0] == 108
    assert len(h.errors.getvalue().splitlines()) == 1
    assert h.publication.data['last_error'] is None


@pytest.mark.parametrize('result', [completion('error', code=1), completion('attempted', code=23)])
def test_worker_failures_keep_the_interval_and_remain_observable(tmp_path, result):
    h = PollHarness((target(tmp_path),))
    calls = []
    def delegate(**scope):
        calls.append(scope)
        return result
    h.run(delegate=delegate)
    assert len(calls) == 2 and h.waits == [4, 4]
    assert any(r.get('activity_status') == 'failure' for r in h.publication.rows)


def test_stop_before_start_or_after_scope_refresh_prevents_worker(tmp_path):
    h = PollHarness((target(tmp_path),))
    h.run(stop_requested=lambda: True)
    assert not h.calls and not h.waits and h.publication.closed
    stopped = False
    def targets():
        nonlocal stopped
        stopped = True
        return SimpleNamespace(exchanges=h.targets)
    h.run(target_provider=targets, stop_requested=lambda: stopped)
    assert not h.calls and not h.waits


def test_stop_wakes_idle_poll_even_with_huge_interval():
    stop, waiting = WatcherStopController(), Event()
    publication = Publication()
    errors = []
    def wait(seconds):
        waiting.set()
        return stop.wait(seconds)
    def run():
        try:
            run_polling_watcher(delegate=lambda **kw: pytest.fail('unexpected worker'),
                target_provider=lambda: SimpleNamespace(exchanges=()), interval=1e100,
                wait=wait, stop_requested=stop.stop_requested, publication_factory=lambda: publication,
                log_stream=StringIO(), error_stream=StringIO())
        except BaseException as exc:
            errors.append(exc)
    thread = Thread(target=run, daemon=True); thread.start()
    try:
        assert waiting.wait(5)
    finally:
        stop.request_stop(); thread.join(5)
    assert not thread.is_alive() and not errors and publication.closed


def test_stop_during_apply_waits_for_that_worker_and_never_starts_another(tmp_path):
    stop = WatcherStopController()
    entered, release = Event(), Event()
    h = PollHarness((target(tmp_path),))
    calls, errors = [], []
    def delegate(**scope):
        calls.append(scope); entered.set()
        assert release.wait(5)
        return completion('attempted', code=0)
    def run():
        try:
            h.run(delegate=delegate, stop_requested=stop.stop_requested, wait=stop.wait)
        except BaseException as exc:
            errors.append(exc)
    thread = Thread(target=run, daemon=True); thread.start()
    try:
        assert entered.wait(5)
        stop.request_stop()
        assert thread.is_alive() and not h.publication.closed
    finally:
        release.set(); thread.join(5)
    assert not thread.is_alive() and not errors and len(calls) == 1 and h.publication.closed


@pytest.mark.parametrize('interval', [0, -1, float('nan'), float('inf'), -float('inf'), True, '4', None])
def test_invalid_interval_fails_before_any_publication_or_discovery(interval):
    h = PollHarness()
    with pytest.raises((TypeError, ValueError)):
        h.run(interval=interval)
    assert not h.publication.rows and not h.calls and not h.waits


def test_unexpected_worker_exception_closes_observation(tmp_path):
    h = PollHarness((target(tmp_path),))
    def fail(**scope):
        raise RuntimeError('worker unavailable')
    with pytest.raises(RuntimeError):
        h.run(delegate=fail)
    assert h.publication.closed and h.publication.data['last_error'] == 'worker unavailable'


@pytest.mark.parametrize('changes,valid', [({}, True), ({'poll_interval_seconds': .125}, True),
    ({'next_poll_at': None}, True), ({'poll_interval_seconds': None}, False),
    ({'poll_interval_seconds': True}, False), ({'poll_interval_seconds': 0}, False),
    ({'poll_interval_seconds': float('inf')}, False), ({'next_poll_at': 'later'}, False),
    ({'next_poll_at': -1}, False), ({'watcher_mode': 'unknown'}, False)])
def test_polling_observation_has_validated_machine_readable_interval_and_deadline(changes, valid):
    from patchharbor.monitor_live_schema import parse_live
    identity = '00000000-0000-4000-8000-000000000001'
    stamp = '2026-11-10T12:00:00Z'
    row = dict(format_version=3, kind='watcher', instance_id=identity, pid=123,
        process_identity=None, started_at=stamp, updated_at=stamp, facts_updated_at=stamp,
        completed=False, phase='watching', log_tail='', history=[],
        activity=dict(sequence=1, at=stamp, since=stamp, code='poll-wait', status='waiting', message='poll'),
        data=dict(watcher_mode='poll', poll_interval_seconds=4, next_poll_at=1794312004))
    row['data'].update(changes)
    if valid:
        assert parse_live(json.dumps(row).encode(), 'watcher-'+identity+'.json')['data'] == row['data']
    else:
        with pytest.raises(ValueError):
            parse_live(json.dumps(row).encode(), 'watcher-'+identity+'.json')
