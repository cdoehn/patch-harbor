"""Result-2 producer integration through actual registered fixture repositories."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from patchharbor import api
import patchharbor.application as application
import patchharbor.result_bundle as result_bundle
import patchharbor.result_resources as resources
from patchharbor.result_reader import read_result_reference
from patchharbor.runtime_artifact import RuntimeArtifact, RuntimeProvision
from patchharbor.runtime_wheel import CHAT_PATH, sha256
from tests.platform_support import native_script, native_value
from tests.registration_support import create_repository, git
from tests.test_runtime_artifact import prepared, _capture, _recipe


@pytest.fixture(scope="module")
def artifact(prepared):
    raw = _capture(prepared)
    return RuntimeArtifact(_recipe(prepared), raw, sha256(raw), prepared[CHAT_PATH])


@pytest.fixture
def repository(tmp_path):
    repository = create_repository(tmp_path / "foreign-project")
    api.register(repository)
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange, repository=repository)
    return repository, exchange


def package(repository, exchange, *, exit_code=0):
    context = api.context(repository)
    entrypoint = native_value("run.sh", "run.ps1")
    manifest = {"marker": "patch-harbor", "format_version": 1,
                **{key: str(getattr(context, key)) for key in
                   ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")},
                "entrypoint": entrypoint}
    path = exchange / "test-patch.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps(manifest))
        archive.writestr(entrypoint, native_script(f"exit {exit_code}", f"exit {exit_code}"))
    return path


@pytest.mark.parametrize("route", ["bundle", "apply", "dry_run", "failure", "watcher"])
def test_all_result_routes_embed_same_producer_runtime(repository, artifact, monkeypatch, route):
    root, exchange = repository
    calls = []
    def capture(self):
        calls.append(True)
        return RuntimeProvision("embedded", None, artifact)
    monkeypatch.setattr(resources.RuntimeProvider, "capture", capture)
    before = git(root, "rev-parse", "HEAD").stdout
    patch = package(root, exchange, exit_code=27 if route == "failure" else 0)
    if route == "bundle":
        report = api.bundle(root).report
    elif route == "watcher":
        report = api.apply_next()
    else:
        report = api.apply(patch, dry_run=route == "dry_run")
    assert len(calls) == 1
    assert report.process_exit_code == (27 if route == "failure" else 0)
    facts, _ = read_result_reference(report.result_bundle.path)
    assert facts.format_version == 2 and facts.runtime.status == "embedded"
    assert facts.runtime.wheel.sha256 == artifact.wheel_sha256
    assert facts.runtime.content_id == artifact.recipe.content_id
    assert facts.context.repository_path == str(root)
    assert facts.dry_run == (route == "dry_run")
    assert facts.primary_result.entrypoint_started == (route not in {"bundle", "dry_run"})
    assert not facts.warnings
    with ZipFile(report.result_bundle.path) as archive:
        assert archive.read(facts.runtime.wheel.path) == artifact.wheel_bytes
        assert {name for name in archive.namelist() if name.startswith("runtime/")} == {
            facts.runtime.wheel.path, "runtime/runtime.json"}
        assert not any(name.startswith("base/runtime/") for name in archive.namelist())
    assert git(root, "rev-parse", "HEAD").stdout == before
    assert not git(root, "status", "--porcelain").stdout


@pytest.mark.parametrize("reason,expected", [
    ("source_not_prepared", "source_not_prepared"), ("source_changed", "source_changed"),
    ("resources_missing", "artifact_missing"), ("resources_invalid", "artifact_corrupt"),
    ("resource_limit", "resource_limit"),
])
def test_runtime_failure_preserves_actual_failed_apply_and_log(repository, monkeypatch, reason, expected):
    root, exchange = repository
    monkeypatch.setattr(resources.RuntimeProvider, "capture",
                        lambda self: RuntimeProvision("unavailable", reason, None))
    report = api.apply(package(root, exchange, exit_code=23))
    assert report.process_exit_code == 23
    facts, _ = read_result_reference(report.result_bundle.path)
    assert facts.runtime.status == "unavailable" and facts.runtime.reason == expected
    assert facts.warnings and facts.primary_result.entrypoint_exit_code == 23
    with ZipFile(report.result_bundle.path) as archive:
        assert "logs/execution.log" in archive.namelist()
        assert len([name for name in archive.namelist() if name.startswith("base/")]) > 0
        assert {name for name in archive.namelist() if name.startswith("runtime/")} == {"runtime/runtime.json"}


def test_runtime_and_template_are_pinned_before_actual_entrypoint(repository, artifact, monkeypatch):
    root, exchange = repository
    calls = []
    def capture(self):
        calls.append(True)
        return RuntimeProvision("embedded", None, artifact)
    monkeypatch.setattr(resources.RuntimeProvider, "capture", capture)
    execute = application.execute_prepared_script_with_log
    def changed_installation(*args, **kwargs):
        import patchharbor.chat_instructions as chat
        assert calls == [True]
        monkeypatch.setattr(resources.RuntimeProvider, "capture", lambda self: pytest.fail("late runtime capture"))
        monkeypatch.setattr(resources, "load_chat_template", lambda: pytest.fail("late template read"))
        monkeypatch.setattr(chat, "load_chat_template", lambda: pytest.fail("late template read"))
        return execute(*args, **kwargs)
    monkeypatch.setattr(application, "execute_prepared_script_with_log", changed_installation)
    report = api.apply(package(root, exchange))
    assert report.process_exit_code == 0
    facts, _ = read_result_reference(report.result_bundle.path)
    assert facts.runtime.wheel.sha256 == artifact.wheel_sha256
    with ZipFile(report.result_bundle.path) as archive:
        # Template byte identity is a provenance contract, not a prose snapshot.
        assert archive.read("CHAT_INSTRUCTIONS.md").endswith(artifact.chat_template)


def test_runtime_budget_falls_back_without_losing_snapshot(repository, artifact, monkeypatch):
    from functools import partial
    from patchharbor.resource_policy import ResourcePolicy
    root, exchange = repository
    monkeypatch.setattr(resources.RuntimeProvider, "capture", lambda self: RuntimeProvision("embedded", None, artifact))
    monkeypatch.setattr(result_bundle, "runtime_fits", partial(resources.runtime_fits,
                        policy=ResourcePolicy(max_zip_total_bytes=128 * 1024)))
    report = api.apply(package(root, exchange))
    assert report.process_exit_code == 0
    facts, _ = read_result_reference(report.result_bundle.path)
    assert facts.runtime.status == "unavailable" and facts.runtime.reason == "resource_limit"
    assert facts.warnings and facts.base_entries


def test_missing_mandatory_template_remains_a_result_error(repository, monkeypatch):
    from patchharbor.errors import result_bundle_error
    root, exchange = repository
    def missing():
        raise result_bundle_error("missing canonical template")
    monkeypatch.setattr(resources, "load_chat_template", missing)
    monkeypatch.setattr(resources.RuntimeProvider, "capture",
                        lambda self: RuntimeProvision("unavailable", "resources_missing", None))
    report = api.apply(package(root, exchange, exit_code=27))
    assert report.primary_result.entrypoint_exit_code == 27
    assert report.result_bundle.status is api.ResultBundleStatus.FAILED
    assert report.result_bundle.emergency_diagnostics_path.is_dir()
    assert not tuple(exchange.glob("*_Result_*.zip"))
