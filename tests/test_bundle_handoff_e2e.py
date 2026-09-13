from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from patchharbor.bundle_handoff import CHAT_INSTRUCTIONS_NAME, ENVIRONMENT_NAME, PATCH_HANDOFF_DIRECTORY
from patchharbor.chat_instructions import render_chat_handoff
from patchharbor.errors import PatchHarborError
import patchharbor.result_bundle_handoff as result_handoff_module
from patchharbor.result_bundle import create_manual_result_bundle
from tests.platform_support import PROJECT_ROOT, native_script, native_value, run_cli
from tests.registration_support import create_repository, git, user_configuration_path
from tests.test_exchange_e2e import _configure_user, _register_context, _manifest


pytestmark = pytest.mark.e2e


def _bundle(repository: Path, environment: dict[str, str], *arguments: str):
    completed = run_cli(repository, "bundle", "--json", *arguments, environment_overrides=environment)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    path = Path(json.loads(completed.stdout)["result"]["result_bundle_path"])
    return path, _read_result(path)


def _read_result(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        for name in (CHAT_INSTRUCTIONS_NAME, ENVIRONMENT_NAME):
            assert archive.namelist().count(name) == 1
        environment = json.loads(archive.read(ENVIRONMENT_NAME))
        context = json.loads(archive.read("context.json"))
        instructions = archive.read(CHAT_INSTRUCTIONS_NAME).decode("utf-8")
        assert instructions.endswith((PROJECT_ROOT / CHAT_INSTRUCTIONS_NAME).read_text(encoding="utf-8"))
        assert environment["bundle_type"] == "Result"
        assert environment["bundle_filename"] == path.name
        assert environment["bundle_suffix"] == context["bundle_suffix"]
        for field in ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm"):
            assert environment["repository_context"][field] == context[field]
            assert context[field] in instructions
        # Metadata roundtrips exactly between machine and Markdown data blocks.
        data = instructions.split("```json\n", 1)[1].split("\n```", 1)[0]
        assert json.loads(data) == environment
        assert "base/environment.json" not in archive.namelist()
        return environment


def _write_patch(path: Path, context: dict[str, object], environment: dict[str, object], *, fail_once: bool = False, root_payload: bool = False) -> None:
    target_data = {**environment, "bundle_type": "Patch", "bundle_filename": path.name}
    handoff = render_chat_handoff(target_data)
    entrypoint = native_script(
        'test -f "$PH_HANDOFF_READY" || exit 23' if fail_once else "exit 0",
        'if (-not (Test-Path $env:PH_HANDOFF_READY)) { exit 23 }; exit 0' if fail_once else "exit 0",
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps(_manifest(context)))
        archive.writestr(native_value("run.sh", "run.ps1"), entrypoint)
        for name, raw in handoff.entries(patch=True):
            archive.writestr(name, raw)
        if root_payload:
            archive.writestr(CHAT_INSTRUCTIONS_NAME, "actual project documentation\n")


def test_manual_bundle_embeds_current_environment_without_touching_repository(tmp_path: Path) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _register_context(repository, environment)
    assert not (repository / CHAT_INSTRUCTIONS_NAME).exists()
    path, data = _bundle(repository, environment)
    assert path.parent == exchange
    assert data["repository_path"] == str(repository.resolve())
    assert data["repository_name"] == repository.name
    assert data["exchange_directory"] == data["output_directory"] == str(exchange)
    assert data["runtime"]["python_version"]
    assert data["runtime"]["patchharbor_version"] == "1.2.0"
    assert data["filename_timezone"] == "UTC"
    assert data["filename_schemas"]["Patch"].endswith(".zip<bundle_suffix>")
    assert git(repository, "status", "--porcelain").stdout == ""
    assert not (repository / CHAT_INSTRUCTIONS_NAME).exists()
    assert not (repository / ENVIRONMENT_NAME).exists()
    assert not (repository / PATCH_HANDOFF_DIRECTORY).exists()


def test_fresh_configuration_and_explicit_output_are_not_confused(tmp_path: Path) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _register_context(repository, environment)
    first_path, first = _bundle(repository, environment)
    assert run_cli(repository, "configure", "bundle-suffix", ".txt", environment_overrides=environment).returncode == 0
    new_exchange = tmp_path / "new-exchange"
    assert run_cli(repository, "configure", "exchange-directory", str(new_exchange), environment_overrides=environment).returncode == 0
    output = tmp_path / "explicit-output"
    second_path, second = _bundle(repository, environment, "--output-dir", str(output))
    assert second["exchange_directory"] == str(new_exchange.resolve())
    assert second["output_directory"] == str(output.resolve())
    assert second["bundle_suffix"] == ".txt"
    assert second_path.name.endswith(".zip.txt")
    assert first["exchange_directory"] == str(exchange)
    assert first["bundle_suffix"] == ""
    assert _read_result(first_path) == first  # no sidecar/stale regeneration
    assert first["run_id"] != second["run_id"]
    assert run_cli(repository, "configure", "bundle-suffix", "--clear", environment_overrides=environment).returncode == 0
    _, third = _bundle(repository, environment)
    assert third["bundle_suffix"] == ""
    assert third["output_directory"] == str(new_exchange.resolve())


@pytest.mark.parametrize("configuration", ["absent", "malformed"])
def test_explicit_output_recovers_without_inventing_exchange(tmp_path: Path, configuration: str) -> None:
    environment, _ = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _register_context(repository, environment)
    config_path = user_configuration_path(environment)
    if configuration == "absent":
        config_path.unlink()
    else:
        config_path.write_text("invalid config")
    output = tmp_path / "recovery"
    _, data = _bundle(repository, environment, "--output-dir", str(output))
    assert data["exchange_directory"] is None
    assert data["output_directory"] == str(output.resolve())
    assert data["bundle_suffix"] == ""


@pytest.mark.parametrize("automatic", [False, True])
def test_apply_failure_retry_and_dry_run_all_embed_fresh_handoff(tmp_path: Path, automatic: bool) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    _, initial = _bundle(repository, environment)
    patch = exchange / "patch.zip"
    _write_patch(patch, context, initial, fail_once=True)
    environment["PH_HANDOFF_READY"] = str(tmp_path / "external-ready")
    cwd = tmp_path if automatic else repository
    origin = ("--automatic",) if automatic else ()
    dry_run = run_cli(cwd, "apply", "--json", "--dry-run", *origin, environment_overrides=environment)
    assert dry_run.returncode == 0, dry_run.stderr + dry_run.stdout
    dry_doc = json.loads(dry_run.stdout)
    _read_result(Path(dry_doc["result"]["result_bundle"]["path"]))
    failed = run_cli(cwd, "apply", "--json", *origin, environment_overrides=environment)
    assert failed.returncode == 23, failed.stdout + failed.stderr
    doc = json.loads(failed.stdout)
    # Apply error JSON exposes the Result Bundle path in the result as before.
    result_path = Path(doc["result"]["result_bundle"]["path"])
    result_data = _read_result(result_path)
    assert result_data["repository_path"] == str(repository.resolve())
    assert result_data["repository_context"] == initial["repository_context"]
    assert git(repository, "status", "--porcelain").stdout == ""
    assert not (repository / PATCH_HANDOFF_DIRECTORY).exists()
    if automatic:
        repeated = run_cli(cwd, "apply", "--json", *origin, environment_overrides=environment)
        assert repeated.returncode == 10
    Path(environment["PH_HANDOFF_READY"]).touch()
    success = run_cli(repository, "apply", "--json", environment_overrides=environment)
    assert success.returncode == 0, success.stdout + success.stderr
    fresh = _read_result(Path(json.loads(success.stdout)["result"]["result_bundle"]["path"]))
    assert fresh["run_id"] != result_data["run_id"]
    assert git(repository, "status", "--porcelain").stdout == ""
    assert run_cli(repository, "apply", "--json", environment_overrides=environment).returncode == 10


def test_explicit_foreign_repo_uses_target_facts_and_metadata_is_not_payload(tmp_path: Path) -> None:
    environment, exchange = _configure_user(tmp_path)
    repo_a = create_repository(tmp_path / "repo-a")
    repo_b = create_repository(tmp_path / "repo-b")
    _register_context(repo_a, environment)
    context_b = _register_context(repo_b, environment)
    _, data_b = _bundle(repo_b, environment)
    patch = exchange / "foreign.zip"
    _write_patch(patch, context_b, data_b, root_payload=True)
    completed = run_cli(repo_a, "apply", "--json", str(patch), environment_overrides=environment)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    actual = _read_result(Path(json.loads(completed.stdout)["result"]["result_bundle"]["path"]))
    assert actual["repository_path"] == str(repo_b.resolve())
    assert (repo_b / CHAT_INSTRUCTIONS_NAME).read_text() == "actual project documentation\n"
    assert not (repo_b / PATCH_HANDOFF_DIRECTORY).exists()
    assert not (repo_a / CHAT_INSTRUCTIONS_NAME).exists()
    assert git(repo_a, "status", "--porcelain").stdout == ""


def test_watcher_regenerates_local_handoff_and_does_not_loop(tmp_path: Path) -> None:
    from io import StringIO
    from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
    from patchharbor_watcher.loop import SharedWatcherEventState, WatcherPollOutcome, poll_shared_exchange_once
    from tests.platform_support import project_environment

    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "watcher-repository")
    context = _register_context(repository, environment)
    _, initial = _bundle(repository, environment)
    environment["PH_HANDOFF_READY"] = str(tmp_path / "not-ready")
    _write_patch(exchange / "watcher.zip", context, initial, fail_once=True)
    apply_environment = project_environment(environment)
    def delegate():
        return delegate_to_automatic_apply(environment=apply_environment)
    state = SharedWatcherEventState()
    before = set(exchange.glob("*_Result_*.zip"))
    assert poll_shared_exchange_once(exchange, state, delegate=delegate, log_stream=StringIO(), error_stream=StringIO()) is WatcherPollOutcome.ERROR
    after = set(exchange.glob("*_Result_*.zip"))
    (result,) = after - before
    data = _read_result(result)
    assert data["repository_path"] == str(repository.resolve())
    assert data["run_id"] != initial["run_id"]
    assert poll_shared_exchange_once(exchange, state, delegate=delegate, log_stream=StringIO(), error_stream=StringIO()) is WatcherPollOutcome.WAITING
    assert set(exchange.glob("*_Result_*.zip")) == after
    assert git(repository, "status", "--porcelain").stdout == ""


def test_configuration_change_during_handoff_is_revalidated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from patchharbor.application import configure_bundle_suffix
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _register_context(repository, environment)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    real_capture = result_handoff_module.capture_runtime_environment
    def capture_and_change():
        observed = real_capture()
        configure_bundle_suffix(".txt")
        return observed
    monkeypatch.setattr(result_handoff_module, "capture_runtime_environment", capture_and_change)
    with pytest.raises(PatchHarborError, match="bundle suffix changed"):
        create_manual_result_bundle(repository)
    assert not list(exchange.glob("*_Result_*"))
    assert not list(exchange.glob(".*.tmp"))


def test_template_failure_publishes_no_incomplete_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import patchharbor.chat_instructions as template_module
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _register_context(repository, environment)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(template_module, "_template_path", lambda: tmp_path / "missing-template.md")
    with pytest.raises(PatchHarborError, match="chat-instructions template"):
        create_manual_result_bundle(repository)
    assert not list(exchange.glob("*_Result_*"))
    assert not list(exchange.glob(".*.tmp"))
    assert git(repository, "status", "--porcelain").stdout == ""


@pytest.mark.parametrize("line_ending", [b"\r\n", b"\r"], ids=["crlf", "cr"])
def test_result_bundle_normalizes_generated_instructions_not_repository_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, line_ending: bytes,
) -> None:
    import patchharbor.chat_instructions as template_module
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    git(repository, "config", "core.autocrlf", "false")
    repository_bytes = b"project-owned instructions\r\nkeep these exact bytes\r\n"
    (repository / CHAT_INSTRUCTIONS_NAME).write_bytes(repository_bytes)
    git(repository, "add", CHAT_INSTRUCTIONS_NAME)
    git(repository, "commit", "--quiet", "-m", "project instructions with CRLF")
    context = _register_context(repository, environment)
    template = tmp_path / "installed-template.md"
    template_bytes = b"canonical" + line_ending + b"contract" + line_ending
    template.write_bytes(template_bytes)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(template_module, "_template_path", lambda: template)
    create_manual_result_bundle(repository)
    paths = list(exchange.glob("*_Result_*.zip"))
    assert len(paths) == 1
    with zipfile.ZipFile(paths[0]) as archive:
        assert archive.testzip() is None
        generated = archive.read(CHAT_INSTRUCTIONS_NAME)
        assert b"\r" not in generated
        assert generated.endswith(b"canonical\ncontract\n")
        assert archive.read("base/" + CHAT_INSTRUCTIONS_NAME) == repository_bytes
        result_context = json.loads(archive.read("context.json"))
        for key in ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm"):
            assert result_context[key] == context[key]
    assert template.read_bytes() == template_bytes
    assert (repository / CHAT_INSTRUCTIONS_NAME).read_bytes() == repository_bytes
    assert git(repository, "status", "--porcelain").stdout == ""
