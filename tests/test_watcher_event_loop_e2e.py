"""Real event waits and isolated Apply processes; no accelerated quiet interval."""
from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Event, Thread
from time import monotonic
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from patchharbor_watcher.lifecycle import WatcherStopController
from patchharbor_watcher.loop import run_repository_watcher
from patchharbor_watcher.platform import open_event_source
from tests.platform_support import project_environment
from tests.registration_support import create_repository, set_isolated_user_environment
from tests.test_api_e2e import write_package
from tests.test_watcher_scheduling import completion, target

pytestmark = [pytest.mark.e2e,
    pytest.mark.skipif(not (sys.platform.startswith('linux') or sys.platform == 'win32'), reason='native event backend required')]


class RunningWatcher:
    def __init__(self, **options):
        self.stop = WatcherStopController()
        self.subscribed = Event()
        self.errors = []
        self.options = options
        self.started_at = None
        self.thread = Thread(target=self.run, daemon=True)

    def source(self, directories):
        source = open_event_source(directories)
        self.started_at = monotonic()
        self.subscribed.set()
        return source

    def run(self):
        try:
            run_repository_watcher(log_stream=StringIO(), error_stream=StringIO(),
                stop_requested=self.stop.stop_requested, bind_wake=self.stop.bind_wake,
                source_factory=self.source, **self.options)
        except BaseException as exc:
            self.errors.append(exc)

    def __enter__(self):
        self.thread.start()
        assert self.subscribed.wait(10), self.errors
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.stop.request_stop()
        self.thread.join(20)
        if self.thread.is_alive():
            import traceback as tracebacks
            frame = sys._current_frames().get(self.thread.ident)
            if frame is not None:
                tracebacks.print_stack(frame)
            if exception is not None:
                exception.add_note('watcher did not release event handles/worker; stack printed above')
                return False
        assert not self.thread.is_alive(), 'watcher did not release event handles/worker'
        assert not self.errors, self.errors


def test_real_event_loop_preserves_changes_during_worker_and_remains_idle_after_drain(tmp_path):
    root = tmp_path / 'exchange'; root.mkdir()
    reports = root / 'reports'; reports.mkdir()
    item = root / 'incoming.partial'; item.write_bytes(b'first')
    registry = tmp_path / 'registry.json'; registry.write_bytes(b'{}')
    observed = target(root)
    targets = api.WatchTargets((observed,), registry, ())
    controls = api.WatchControlPaths(registry, (), (root,))
    first, second, release = Event(), Event(), Event()
    calls = []
    def delegate(*, exchanges):
        calls.append((monotonic(), exchanges))
        if len(calls) == 1:
            first.set()
            assert release.wait(12)
        else:
            second.set()
        return completion()
    try:
        with RunningWatcher(delegate=delegate, target_provider=lambda: targets, control_provider=lambda: controls) as watcher:
            latest_write = monotonic()
            item.write_bytes(b'last chunk')
            assert not first.wait(4.6)
            assert first.wait(5)
            assert calls[0][0] >= latest_write + 5
            during_apply = monotonic()
            item.replace(root / 'ready.zip')
            release.set()
            assert second.wait(10)
            assert calls[1][0] >= during_apply + 5
            assert all(scope == (observed,) for _, scope in calls)
            # Pure reads and existing nested directory content do not start work.
            (root / 'ready.zip').read_bytes()
            (reports / 'diagnosis.txt').write_bytes(b'nested')
            Event().wait(5.3)
            assert len(calls) == 2
    finally:
        release.set()


def test_real_event_loop_drains_multiple_bundles_and_never_retries_failed_identity(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / 'user')
    repo = create_repository(tmp_path / 'repo')
    context = api.register(repo)
    exchange = tmp_path / 'exchange'
    api.configure_exchange_directory(exchange, repository=repo)
    good, bad = exchange / 'good.data', exchange / 'bad.data'
    write_package(good, context)
    write_package(bad, context, exit_code=23)
    os.utime(good, ns=(1000000000, 1000000000))
    os.utime(bad, ns=(2000000000, 2000000000))
    reports, scopes = [], []
    drained = Event()
    def delegate(*, exchanges):
        scopes.append(exchanges)
        result = delegate_to_automatic_apply(exchanges=exchanges, environment=project_environment())
        reports.append(result)
        if result.progress.status == 'no_candidate':
            drained.set()
        return result
    with RunningWatcher(delegate=delegate) as watcher:
        assert drained.wait(35), (reports, watcher.errors)
    attempted = [r for r in reports if r.progress.status == 'attempted']
    assert len(attempted) == 2 and sorted(r.process_exit_code for r in attempted) == [0, 23]
    assert reports[-1].progress.status == 'no_candidate'
    assert all(tuple(t.directory for t in scope) == (exchange,) for scope in scopes)
    for result in attempted:
        path = Path(result.apply_result['result']['result_bundle']['path'])
        with ZipFile(path) as z:
            run = json.loads(z.read('logs/run.json'))
            assert run['execution_present'] and not run['dry_run']
            assert run['repo_id'] == str(context.repo_id)
    assert api.context(repo) == context


def test_real_event_loop_ignores_neighbor_download_until_its_own_quiet_period(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / 'user')
    repo_a, repo_b = (create_repository(tmp_path / name) for name in ('repo-a', 'repo-b'))
    a, b = tmp_path / 'a', tmp_path / 'b'
    context = api.register(repo_a); api.register(repo_b)
    api.configure_exchange_directory(a, repository=repo_a)
    api.configure_exchange_directory(b, repository=repo_b)
    write_package(a / 'ready', context)
    downloading, finished, stop_writer, neighbor_scanned = Event(), Event(), Event(), Event()
    calls = []
    writes = []
    writer_errors = []
    def writer():
        try:
            with (b / 'download.zip').open('ab') as stream:
                while not stop_writer.is_set():
                    written_at = monotonic()
                    stream.write(b'partial'); stream.flush()
                    # Windows size/last-write notifications require the OS
                    # cache to reach disk; flush() alone only drains Python.
                    os.fsync(stream.fileno())
                    writes.append(written_at)
                    downloading.set()
                    stop_writer.wait(0.15)
        except BaseException as exc:
            writer_errors.append(exc)
    def delegate(*, exchanges):
        calls.append((monotonic(), tuple(t.directory for t in exchanges)))
        if b in calls[-1][1]:
            neighbor_scanned.set()
        result = delegate_to_automatic_apply(exchanges=exchanges, environment=project_environment())
        if result.progress.status == 'attempted':
            finished.set()
        return result
    writing = Thread(target=writer, daemon=True)
    try:
        with RunningWatcher(delegate=delegate) as watcher:
            writing.start()
            assert downloading.wait(2)
            assert finished.wait(20), watcher.errors
            assert not writer_errors and len(writes) > 1, (writes, writer_errors)
            assert all(scope == (a,) for _, scope in calls), (calls, writes)
            stop_writer.set()
            writing.join(5)
            assert not writing.is_alive() and not writer_errors, writer_errors
            assert neighbor_scanned.wait(15), (calls, writes, watcher.errors)
            assert all(when >= writes[-1] + 5 for when, scope in calls if b in scope), (calls, writes)
    finally:
        stop_writer.set()
        writing.join(5)


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX signal delivery; Windows native wake/close tested separately')
@pytest.mark.parametrize('stop_signal', [signal.SIGINT, signal.SIGTERM])
def test_idle_cli_signal_wakes_native_wait_and_exits_without_worker(tmp_path, monkeypatch, stop_signal):
    set_isolated_user_environment(monkeypatch, tmp_path / 'user')
    api.repositories()
    process = subprocess.Popen([sys.executable, '-m', 'patchharbor_watcher.cli'],
        cwd=tmp_path, env=project_environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # Read a machine lifecycle record; no guessed startup sleep.
        line = process.stdout.readline()
        assert json.loads(line)['event'] == 'watcher_started'
        process.send_signal(stop_signal)
        output, errors = process.communicate(timeout=10)
        assert process.returncode == (130 if stop_signal == signal.SIGINT else 0), errors
        records = [json.loads(row) for row in output.splitlines()]
        assert [r['event'] for r in records] == ['watcher_stopped']
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()
