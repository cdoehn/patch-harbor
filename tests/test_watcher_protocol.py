"""Strict private worker scope/progress round trips and Core isolation."""
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from patchharbor import api
from patchharbor_watcher import worker
from patchharbor_watcher.apply_boundary import ApplyCompletion, delegate_to_automatic_apply
from patchharbor_watcher.protocol import MAX_REQUEST_BYTES, Progress, decode_scope, encode_scope, read_progress
from tests.registration_support import create_repository, set_isolated_user_environment


def test_empty_and_global_scope_remain_distinct():
    assert decode_scope(encode_scope(())) == []
    assert decode_scope(encode_scope(None)) is None


@pytest.mark.parametrize('raw', [b'[]', b'{}', b'{"version":1,"version":1,"exchanges":[]}',
    b'{"version":true,"exchanges":[]}', b'{"version":1,"exchanges":{}}',
    b'{"version":1,"exchanges":NaN}',
    # pytest copies the node ID into PYTEST_CURRENT_TEST; keep the large payload
    # out of that environment variable so Windows can reach the test body.
    pytest.param(b'x' * (MAX_REQUEST_BYTES + 1), id='oversized-request')])
def test_invalid_worker_scope_never_calls_core(monkeypatch, raw):
    monkeypatch.setattr(api, 'apply_next', lambda **kw: pytest.fail('invalid request reached Core'))
    with pytest.raises((ValueError, TypeError)):
        worker.main(request=raw, stdout=StringIO(), stderr=StringIO())


def test_scoped_worker_passes_full_physical_binding_to_public_api(monkeypatch, tmp_path):
    target = api.ExchangeWatchTarget(tmp_path, 17, 19, (api.RepositoryId('00000000-0000-4000-8000-000000000001'),))
    calls = []
    def apply(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(automatic=api.AutomaticApplyResult(api.AutomaticApplyStatus.NO_CANDIDATE),
            apply_json_envelope=lambda: {'command': 'apply', 'process_exit_code': 10},
            process_exit_code=10, result_bundle=SimpleNamespace(status=api.ResultBundleStatus.NOT_ATTEMPTED, emergency_diagnostics_path=None))
    monkeypatch.setattr(api, 'apply_next', apply)
    output = StringIO()
    assert worker.main(request=encode_scope((target,)), stdout=output, stderr=StringIO()) == 10
    assert calls == [{'exchanges': (target,)}]
    assert read_progress(json.loads(output.getvalue())['watcher_progress']) == Progress('no_candidate')


@pytest.mark.parametrize('document', [None, {}, {'version': True, 'status': 'no_candidate', 'blocked_on': None},
    {'version': 1, 'status': 'locked', 'blocked_on': None},
    {'version': 1, 'status': 'attempted', 'blocked_on': {'kind': 'registry', 'repo_id': None}},
    {'version': 1, 'status': 'locked', 'blocked_on': {'kind': 'repository', 'repo_id': 'truncated'}},
    {'version': 1, 'status': 'no_candidate', 'blocked_on': None, 'extra': 1}])
def test_invalid_progress_is_error_and_never_guessed_from_console_text(document):
    response = {'watcher_progress': document, 'error': {'kind': 'patch_package_error',
                'message': 'no state-bound patch package matches a registered repository'}}
    assert ApplyCompletion(10, response, None, '').progress == Progress('error')


def test_transport_sends_scope_as_private_stdin_without_new_signal_or_shell_boundary(monkeypatch, tmp_path):
    from patchharbor_watcher import apply_boundary
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=10, stdout=b'{"command":"apply"}', stderr=b'')
    monkeypatch.setattr(apply_boundary.subprocess, 'run', run)
    delegate_to_automatic_apply(exchanges=())
    command, kwargs = calls[0]
    assert command == list(apply_boundary.DEFAULT_APPLY_COMMAND)
    assert decode_scope(kwargs['input']) == []
    assert not {'shell', 'start_new_session', 'creationflags', 'timeout'} & kwargs.keys()


def test_core_exposes_missing_exchange_hint_without_creating_or_approving_it(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path / 'user')
    repo = create_repository(tmp_path / 'repo')
    api.register(repo)
    exchange = tmp_path / 'exchange'
    api.configure_exchange_directory(exchange, repository=repo)
    exchange.rmdir()
    controls = api.watch_control_paths()
    assert controls.exchange_paths == (exchange,)
    with pytest.raises(api.PatchHarborError):
        api.watch_targets()
    assert not exchange.exists()
