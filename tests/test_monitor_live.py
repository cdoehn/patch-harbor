"""Live observations follow actual native execution and remain optional."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import time

import pytest

from patchharbor import api
from patchharbor import monitor_live
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
    first, second = api.watcher_observation(), api.watcher_observation()
    try:
        first.update(phase='watching', targets=[{'directory': '/one'}])
        second.update(phase='applying', targets=[{'directory': '/two'}])
        wait_for(lambda: instance(first.instance_id))
        wait_for(lambda: instance(second.instance_id))
        assert instance(first.instance_id)['data']['targets'] != instance(second.instance_id)['data']['targets']
        assert instance(first.instance_id)['live']
        first.close()
        wait_for(lambda: instance(first.instance_id)['completed'])
        assert instance(second.instance_id)['live']
    finally:
        first.close()
        second.close()


def test_actual_apply_publishes_effective_timeout_output_and_result(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    path = tmp_path / 'exchange' / 'live.zip'
    _write_custom_package(path, {k: str(getattr(context, k)) for k in ('repo_id', 'base_commit', 'state_fingerprint')},
        posix_entrypoint="printf 'live-start'; sleep 1; printf '\\nlive-end\\n'",
        powershell_entrypoint="[Console]::Out.Write('live-start'); Start-Sleep -Milliseconds 1000; [Console]::Out.WriteLine('live-end')")
    events = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(api.apply, path, timeout=7, observer=events.append)
        row = wait_for(lambda: next((r for r in api.monitor_live()['instances']
            if r['kind'] == 'apply' and r['data'].get('effective_timeout_seconds') == 7), None))
        observed = wait_for(lambda: (r if 'live-start' in r.get('log_tail', '') else None)
                            if (r := instance(row['instance_id'])) else None)
        assert observed['live'] and not observed['completed']
        report = future.result(timeout=10)
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
    report = api.apply(path)
    assert report.success and report.primary_result.entrypoint_exit_code == 0


def test_uninitialized_live_read_creates_nothing(tmp_path, monkeypatch):
    from tests.registration_support import isolated_user_environment
    for key, value in isolated_user_environment(tmp_path).items():
        monkeypatch.setenv(key, value)
    assert not api.monitor_live()['instances']
    assert list(tmp_path.iterdir()) == []
