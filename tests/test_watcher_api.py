"""Functional API/worker contracts; no terminal presentation assertions."""
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from patchharbor import api
from patchharbor import application
from patchharbor_watcher import cli as watcher_cli
from patchharbor_watcher import worker
from tests.platform_support import create_symlink_or_skip
from tests.registration_support import create_repository, set_isolated_user_environment


@pytest.mark.parametrize("code", [0, 10, 11, 23, 124, 130])
def test_worker_calls_public_automatic_api_once_and_transports_report(monkeypatch, code):
    calls = []
    envelope = {"output_version": 1, "command": "apply", "success": code == 0,
                "result": {"opaque": "Größe / 日本語"}, "error": None,
                "process_exit_code": code}
    report = SimpleNamespace(
        apply_json_envelope=lambda: envelope,
        process_exit_code=code,
        result_bundle=SimpleNamespace(
            emergency_diagnostics_path=None, status=api.ResultBundleStatus.NOT_ATTEMPTED,
        ),
    )

    def automatic(*args, **kwargs):
        calls.append((args, kwargs))
        return report

    monkeypatch.setattr(api, "apply_next", automatic)
    output = StringIO()
    assert worker.main(stdout=output, stderr=StringIO()) == code
    assert calls == [((), {})]  # no path, no manual retry, no visible script sinks
    assert json.loads(output.getvalue()) == envelope
    # JSON is the machine transport, not a test of rendered console output.
    output.getvalue().encode("ascii")


@pytest.mark.parametrize("failure", [RuntimeError("unexpected"), KeyboardInterrupt()])
def test_worker_never_disguises_unexpected_errors_as_idle(monkeypatch, failure):
    def automatic():
        raise failure
    monkeypatch.setattr(api, "apply_next", automatic)
    with pytest.raises(type(failure)):
        worker.main(stdout=StringIO(), stderr=StringIO())


def test_watcher_startup_validates_registry_not_global_configuration(monkeypatch):
    calls = []
    monkeypatch.setattr(api, "repositories", lambda: calls.append("registry") or ())
    monkeypatch.setattr(api, "configuration", lambda **kw: pytest.fail("global configuration read"))
    monkeypatch.setattr(watcher_cli, "run_repository_watcher", lambda **kw: calls.append("loop"))
    assert watcher_cli.main([], stdout=StringIO(), stderr=StringIO()) == 0
    assert calls == ["registry", "loop"]


@pytest.mark.parametrize("revalidate", [False, True])
def test_configuration_facade_preserves_repository_and_recheck(monkeypatch, tmp_path, revalidate):
    calls = []
    settings = SimpleNamespace(exchange_directory=tmp_path, bundle_suffix="", archive_directory="Archive")
    def local(repository, **kwargs):
        calls.append((repository, kwargs))
        return tmp_path / "config.json", settings
    monkeypatch.setattr(application, "repository_configuration", local)
    assert api.configuration(tmp_path, revalidate=revalidate).exchange_directory == tmp_path
    assert calls == [(tmp_path, {"revalidate": revalidate})]


@pytest.mark.parametrize("value", [None, 1, "yes", object()])
def test_configuration_recheck_requires_boolean_before_core(monkeypatch, value):
    monkeypatch.setattr(application, "repository_configuration", lambda *a, **kw: pytest.fail("invalid options reached Core"))
    with pytest.raises(TypeError):
        api.configuration(revalidate=value)


def test_application_rechecks_loaded_local_configuration(monkeypatch, tmp_path):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repo = create_repository(tmp_path / "repo")
    api.register(repo)
    api.configure_exchange_directory(tmp_path / "exchange", repository=repo)
    calls = []
    original = application.revalidate_exchange_directory
    def recheck(settings):
        calls.append(settings)
        return original(settings)
    monkeypatch.setattr(application, "revalidate_exchange_directory", recheck)
    application.repository_configuration(repo)
    assert calls == []
    application.repository_configuration(repo, revalidate=True)
    assert len(calls) == 1


def test_recheck_rejects_target_replacement_between_load_and_use(monkeypatch, tmp_path):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repo = create_repository(tmp_path / "repo")
    api.register(repo)
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange, repository=repo)
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    original_load = application.load_configuration
    def replace_after_load(paths, **kwargs):
        settings = original_load(paths, **kwargs)
        exchange.rename(tmp_path / "old-exchange")
        create_symlink_or_skip(exchange, replacement, target_is_directory=True)
        return settings
    monkeypatch.setattr(application, "load_configuration", replace_after_load)
    with pytest.raises(api.PatchHarborError) as captured:
        api.configuration(repo, revalidate=True)
    assert captured.value.error_kind is api.ErrorKind.CONFIGURATION_ERROR
    assert list(replacement.iterdir()) == []


def test_watcher_validation_never_creates_missing_exchange(monkeypatch, tmp_path):
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repo = create_repository(tmp_path / "repo")
    api.register(repo)
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange, repository=repo)
    exchange.rmdir()
    report = api.apply_next()
    assert report.process_exit_code != 0
    assert not exchange.exists()
