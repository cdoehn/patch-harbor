"""Live observations follow actual native execution and remain optional."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import shlex
import time

import pytest

from patchharbor import api
from patchharbor import monitor_live, monitor_live_storage, monitor_live_schema
from patchharbor.output import ProcessOutputCapture
from tests.test_monitor import registered
from tests.exchange_support import _write_custom_package


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.03)
    pytest.fail('live observation did not arrive')


def instance(identity):
    return next(iter(api.monitor_live(instance_id=identity)['instances']), None)


def test_watcher_instances_have_independent_files_and_shutdown(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)

    def updated(publication, phase, directory):
        row = instance(publication.instance_id)
        if row and row['phase'] == phase and row['data'].get('targets') == [{'directory': directory}]:
            return row
        return None

    first, second = api.watcher_observation(), api.watcher_observation()
    try:
        # A valid initial observation exists before any target update is published.
        for publication in (first, second):
            initial = wait_for(lambda: instance(publication.instance_id))
            assert initial['phase'] == 'starting' and 'targets' not in initial['data']
        first.update(phase='watching', targets=[{'directory': '/one'}])
        second.update(phase='applying', targets=[{'directory': '/two'}])
        first_row = wait_for(lambda: updated(first, 'watching', '/one'))
        second_row = wait_for(lambda: updated(second, 'applying', '/two'))
        assert first_row['instance_id'] != second_row['instance_id']
        assert first_row['live'] and second_row['live']
        assert not first_row['completed'] and not second_row['completed']
        first.close()
        final = wait_for(lambda: (row if row['completed'] else None)
                         if (row := instance(first.instance_id)) else None)
        assert not final['live'] and final['data']['targets'] == first_row['data']['targets']
        remaining = wait_for(lambda: updated(second, 'applying', '/two'))
        assert remaining['live'] and not remaining['completed']
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize('startup_delay', [0, 8.5], ids=['native-start', 'delayed-start'])
def test_actual_apply_publishes_effective_timeout_output_and_result(tmp_path, monkeypatch, startup_delay):
    if startup_delay:
        from patchharbor import execution
        create_process_tree = execution.create_process_tree
        def delayed_start(*args, **kwargs):
            # Reproduce startup taking longer than the old observation deadline.
            time.sleep(startup_delay)
            return create_process_tree(*args, **kwargs)
        monkeypatch.setattr(execution, 'create_process_tree', delayed_start)
    (root, context), = registered(tmp_path, monkeypatch)
    path = tmp_path / 'exchange' / 'live.zip'
    ready, release = tmp_path / 'entrypoint-ready', tmp_path / 'entrypoint-release'
    powershell_ready = str(ready).replace("'", "''")
    powershell_release = str(release).replace("'", "''")
    requested_timeout = 30
    _write_custom_package(path, {k: str(getattr(context, k)) for k in ('repo_id', 'base_commit', 'state_fingerprint')},
        posix_entrypoint=(
            f"printf 'live-start'; : > {shlex.quote(str(ready))}\n"
            f"while [ ! -f {shlex.quote(str(release))} ]; do sleep .03; done\n"
            "printf '\\nlive-end\\n'"),
        powershell_entrypoint=(
            "[Console]::Out.Write('live-start'); [Console]::Out.Flush()\n"
            f"[System.IO.File]::WriteAllText('{powershell_ready}', 'ready')\n"
            f"while (-not (Test-Path -LiteralPath '{powershell_release}')) {{ Start-Sleep -Milliseconds 30 }}\n"
            "[Console]::Out.WriteLine('live-end')"))
    events = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(api.execute, path, timeout=requested_timeout, observer=events.append)
        try:
            # Preflight and native interpreter startup have no test performance
            # deadline. Once ready, the real entrypoint stays alive until observed.
            while not ready.exists():
                if future.done():
                    report = future.result()
                    pytest.fail(f'Apply ended before entrypoint readiness: {report.primary_result.as_document()}')
                time.sleep(.03)
            row = wait_for(lambda: next((r for r in api.monitor_live()['instances']
                if r['kind'] == 'execute' and r['data'].get('effective_timeout_seconds') == requested_timeout), None))
            observed = wait_for(lambda: (r if 'live-start' in r.get('log_tail', '') else None)
                                if (r := instance(row['instance_id'])) else None)
            assert observed['live'] and not observed['completed']
            assert 'live-end' not in observed['log_tail'] and not future.done()
        finally:
            release.touch()
        # Result publication is functional work, not part of the observation budget.
        report = future.result()
    assert report.success and events
    final = wait_for(lambda: (r if r.get('completed') else None) if (r := instance(row['instance_id'])) else None)
    assert final['data']['primary_result']['entrypoint_exit_code'] == 0
    assert final['data']['result_status'] == 'created'
    assert final['data']['run_id'] == str(report.run_id)
    assert 'live-end' in final['log_tail']
    assert final['data']['repo_id'] == str(context.repo_id)


def test_optional_chunk_observer_cannot_change_required_raw_output():
    original, destination = b'raw\x00bytes\n', BytesIO()
    def broken(_):
        raise OSError('optional view failed')
    capture = ProcessOutputCapture(BytesIO(original), raw_output_stream=destination, chunk_observer=broken)
    capture.start()
    capture.finish()
    assert destination.getvalue() == original


def test_publication_io_failure_cannot_fail_apply(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    path = tmp_path / 'exchange' / 'simple.zip'
    _write_custom_package(path, {k: str(getattr(context, k)) for k in ('repo_id', 'base_commit', 'state_fingerprint')},
        posix_entrypoint='exit 0', powershell_entrypoint='exit 0')
    monkeypatch.setattr(monitor_live, 'atomic_replace_bytes', lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
    report = api.execute(path)
    assert report.success and report.primary_result.entrypoint_exit_code == 0


def test_uninitialized_live_read_creates_nothing(tmp_path, monkeypatch):
    from tests.registration_support import isolated_user_environment
    for key, value in isolated_user_environment(tmp_path).items():
        monkeypatch.setenv(key, value)
    assert not api.monitor_live()['instances']
    assert list(tmp_path.iterdir()) == []


def test_pid_reuse_and_expired_heartbeat_never_become_active(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone, timedelta
    registered(tmp_path, monkeypatch)
    publication = api.watcher_observation()
    wait_for(lambda: instance(publication.instance_id))
    publication.close()
    publication.thread.join(timeout=3)
    path = publication.paths.state_directory / 'monitor-v1' / ('watcher-' + publication.instance_id + '.json')
    row = json.loads(path.read_bytes())
    row['completed'] = False
    row['updated_at'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(row))
    native = monitor_live_storage.process_identity
    monkeypatch.setattr(monitor_live_storage, 'process_identity', lambda pid: 'different-process-birth')
    assert instance(publication.instance_id)['stale'] and not instance(publication.instance_id)['live']
    monkeypatch.setattr(monitor_live_storage, 'process_identity', native)
    row['updated_at'] = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    path.write_text(json.dumps(row))
    assert instance(publication.instance_id)['stale']


def test_slow_writer_does_not_block_producer_and_close_is_eventually_published(tmp_path, monkeypatch):
    from threading import Event
    registered(tmp_path, monkeypatch)
    entered, release = Event(), Event()
    original = monitor_live.atomic_replace_bytes
    def slow(*args, **kwargs):
        entered.set()
        release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(monitor_live, 'atomic_replace_bytes', slow)
    publication = api.watcher_observation()
    assert entered.wait(3)
    start = time.monotonic()
    for _ in range(100):
        publication.append(b'x' * 65536)
        publication.update(phase='watching')
    publication.close()
    assert time.monotonic() - start < .5
    assert len(publication.tail) == 32768
    release.set()
    publication.thread.join(timeout=3)
    assert not publication.thread.is_alive()
    assert instance(publication.instance_id)['completed']


def test_malformed_live_source_is_isolated_from_valid_peer(tmp_path, monkeypatch):
    import json
    registered(tmp_path, monkeypatch)
    publication = api.watcher_observation()
    wait_for(lambda: instance(publication.instance_id))
    try:
        directory = publication.paths.state_directory / 'monitor-v1'
        (directory / 'execute-bad.json').write_text('{"format_version":1,"pid":-1}')
        result = api.monitor_live()
        assert result['errors']
        assert any(r['instance_id'] == publication.instance_id for r in result['instances'])
        source = directory / ('watcher-' + publication.instance_id + '.json')
        row = json.loads(source.read_bytes())
        row['data'] = {'targets': [{'directory': 'x', 'quiet_until': 'NaN'}]}
        with pytest.raises(ValueError):
            monitor_live_schema.parse_live(json.dumps(row).encode(), source.name)
    finally:
        publication.close()


def test_concurrent_real_applies_keep_run_and_repository_identity(tmp_path, monkeypatch):
    entries = registered(tmp_path, monkeypatch, ('one', 'two'))
    paths = []
    for root, context in entries:
        path = tmp_path / 'exchange' / (root.name + '.zip')
        _write_custom_package(path, {k: str(getattr(context, k)) for k in ('repo_id', 'base_commit', 'state_fingerprint')},
            posix_entrypoint='sleep .6; exit 0', powershell_entrypoint='Start-Sleep -Milliseconds 600; exit 0')
        paths.append(path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(api.execute, p) for p in paths]
        reports = [future.result(timeout=15) for future in futures]
    # Existing Core locks may reject one concurrent admission; observation must
    # preserve both actual outcomes and never merge their identities.
    assert any(r.success for r in reports)
    rows = wait_for(lambda: (rows if len(rows) == 2 and all(r['completed'] for r in rows) else None)
                    if (rows := api.monitor_live()['instances']) else None)
    assert {r['data']['run_id'] for r in rows} == {str(r.run_id) for r in reports}
    assert {r['data'].get('repo_id') for r in rows if r['data'].get('repo_id')} <= {str(c.repo_id) for _, c in entries}
    by_run = {str(r.run_id): r for r in reports}
    for row in rows:
        assert row['data']['primary_result'] == by_run[row['data']['run_id']].primary_result.as_document()
    assert len({r['instance_id'] for r in rows}) == 2


def test_live_distinguishes_exit_zero_from_failed_result_publication(tmp_path, monkeypatch):
    import patchharbor.result_bundle_publication as publication
    from patchharbor.monitor_session import result_semantic
    (root, context), = registered(tmp_path, monkeypatch)
    path = tmp_path / 'exchange' / 'success.zip'
    _write_custom_package(path, {k: str(getattr(context, k)) for k in ('repo_id', 'base_commit', 'state_fingerprint')},
        posix_entrypoint='exit 0', powershell_entrypoint='exit 0')
    def fail(*args, **kwargs):
        raise OSError('injected Result publication failure')
    monkeypatch.setattr(publication, '_verify_result_bundle', fail)
    report = api.execute(path)
    assert report.primary_result.entrypoint_exit_code == 0 and not report.success
    row = wait_for(lambda: next((r for r in api.monitor_live()['instances'] if r['completed']), None))
    assert row['data']['result_status'] == 'failed'
    assert result_semantic(row['data']) == 'dirty'


def test_observation_directory_cannot_be_an_exchange(tmp_path, monkeypatch):
    (root, _), = registered(tmp_path, monkeypatch)
    from patchharbor.user_paths import raw_registration_user_paths
    paths = raw_registration_user_paths()
    api.configure_exchange_directory(paths.state_directory, repository=root)
    publication = api.watcher_observation()
    publication.thread.join(timeout=3)
    publication.close()
    assert not (paths.state_directory / 'monitor-v1').exists()


def test_retention_only_removes_old_completed_observations(tmp_path, monkeypatch):
    import json
    from uuid import uuid4
    registered(tmp_path, monkeypatch)
    publication = api.watcher_observation()
    wait_for(lambda: instance(publication.instance_id))
    publication.close()
    publication.thread.join(timeout=3)
    directory = publication.paths.state_directory / 'monitor-v1'
    original = directory / ('watcher-' + publication.instance_id + '.json')
    template = json.loads(original.read_bytes())
    for index in range(132):
        identity = str(uuid4())
        row = {**template, 'instance_id': identity, 'completed': index != 0}
        (directory / ('watcher-' + identity + '.json')).write_text(json.dumps(row))
    protected = directory / 'do-not-touch.txt'
    protected.write_text('other state')
    monitor_live_storage.prune_completed(directory)
    documents = [json.loads(path.read_bytes()) for path in directory.glob('watcher-*.json')]
    assert sum(row['completed'] for row in documents) == 128
    assert sum(not row['completed'] for row in documents) == 1
    assert protected.read_text() == 'other state'


def test_watcher_publishes_observed_targets_and_quiet_deadlines(tmp_path):
    from patchharbor_watcher.loop import run_repository_watcher
    from tests.test_watcher_scheduling import Harness, InlineWorker
    h = Harness(tmp_path)
    updates = []
    class Recorder:
        def update(self, **value): updates.append(value)
        def close(self): updates.append({'closed': True})
    h.at(3)
    run_repository_watcher(delegate=h.delegate, log_stream=h.log, error_stream=h.errors,
        stop_requested=h.controller.stop_requested, bind_wake=h.controller.bind_wake,
        target_provider=h.provider, control_provider=lambda: h.controls,
        readiness=h.readiness, source_factory=h.factory, clock=h.clock,
        worker_factory=InlineWorker, publication_factory=Recorder)
    assert any(row.get('phase') == 'applying' for row in updates)
    target = next(row['targets'][0] for row in updates if row.get('targets'))
    assert target['directory'] == str(h.a) and target['quiet_until'] > 0
    assert target['blocked_on'] is None
    assert updates[-2:] == [{'phase': 'stopped'}, {'closed': True}]
