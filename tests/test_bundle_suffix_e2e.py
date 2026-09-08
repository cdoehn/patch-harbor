from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import re
import zipfile

import pytest

from patchharbor.application import configure_bundle_suffix
from patchharbor.errors import PatchHarborError
from patchharbor.exchange import classify_exchange_artifact, ExchangeArtifactKind
from patchharbor.result_bundle import create_manual_result_bundle
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from patchharbor_watcher.loop import SharedWatcherEventState, poll_shared_exchange_once, WatcherPollOutcome
from tests.platform_support import native_script, native_value, project_environment, run_cli
from tests.registration_support import create_repository, user_configuration_path
from tests.test_exchange_e2e import _configure_user, _register_context, _manifest, _write_package

pytestmark = pytest.mark.e2e


def _configured(tmp_path: Path):
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    configured = run_cli(
        repository, "configure", "bundle-suffix", ".txt", environment_overrides=environment,
    )
    assert configured.returncode == 0, configured.stderr
    return repository, environment, exchange, context


def _assert_result(path: Path, suffix: str) -> dict[str, object]:
    assert path.is_file()
    assert re.fullmatch(r"repository_Result_\d{6}_\d{4}_[a-f0-9]{6}\.zip" + re.escape(suffix), path.name)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        context = json.loads(archive.read("context.json"))
        assert context["bundle_suffix"] == suffix
        assert len(context["repo_id"]) == 36
        assert len(context["base_commit"]) == 40
        assert len(context["state_fingerprint"]) == 16
        assert json.loads(archive.read("manifest.json"))["format_version"] == 1
    return context


def _write_no_mutation_package(path: Path, context: dict[str, object], *, fail_once: bool = False) -> None:
    # The external prerequisite changes; repository state does not.
    body = native_script(
        'test -f "$PH_SUFFIX_READY" || exit 23' if fail_once else 'exit 0',
        'if (-not (Test-Path $env:PH_SUFFIX_READY)) { exit 23 }; exit 0' if fail_once else 'exit 0',
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps(_manifest(context)))
        archive.writestr(native_value("run.sh", "run.ps1"), body)


@pytest.mark.parametrize("explicit_output", [False, True])
def test_bundle_and_clear_use_persisted_suffix_across_processes(tmp_path: Path, explicit_output: bool) -> None:
    repository, environment, exchange, _ = _configured(tmp_path)
    output = tmp_path / "other-results" if explicit_output else exchange
    arguments = ("--output-dir", str(output)) if explicit_output else ()
    shown = run_cli(repository, "configure", "show", environment_overrides=environment)
    assert shown.returncode == 0
    assert "bundle_suffix: .txt" in shown.stdout
    first = run_cli(repository, "bundle", "--json", *arguments, environment_overrides=environment)
    assert first.returncode == 0, first.stderr
    first_path = Path(json.loads(first.stdout)["result"]["result_bundle_path"])
    assert first_path.parent == output.resolve()
    _assert_result(first_path, ".txt")
    cleared = run_cli(repository, "configure", "bundle-suffix", "--clear", environment_overrides=environment)
    assert cleared.returncode == 0, cleared.stderr
    assert "bundle_suffix: \n" in cleared.stdout
    second = run_cli(repository, "bundle", "--json", *arguments, environment_overrides=environment)
    assert second.returncode == 0, second.stderr
    _assert_result(Path(json.loads(second.stdout)["result"]["result_bundle_path"]), "")
    assert first_path.exists()  # Never retroactively rename existing bundles.


@pytest.mark.parametrize("arguments", [(), (".txt", "--clear"), ("--suffix", ".txt")])
def test_configure_rejects_ambiguous_or_missing_suffix_argument(tmp_path: Path, arguments) -> None:
    environment, _ = _configure_user(tmp_path)
    path = user_configuration_path(environment)
    previous = path.read_bytes()
    completed = run_cli(tmp_path, "configure", "bundle-suffix", *arguments, environment_overrides=environment)
    assert completed.returncode == 2
    assert path.read_bytes() == previous


@pytest.mark.parametrize("command", ["bundle", "apply"])
def test_no_per_invocation_suffix_option_is_added(tmp_path: Path, command: str) -> None:
    completed = run_cli(tmp_path, command, "--suffix", ".txt")
    assert completed.returncode == 2
    help_result = run_cli(tmp_path, command, "--help")
    assert "--suffix" not in help_result.stdout


@pytest.mark.parametrize("explicit_package", [False, True])
@pytest.mark.parametrize("extension", [".zip", ".zip.txt"])
def test_apply_accepts_old_and_suffixed_packages_and_publishes_suffixed_result(
    tmp_path: Path, explicit_package: bool, extension: str,
) -> None:
    repository, environment, exchange, context = _configured(tmp_path)
    package = exchange / ("patch" + extension)
    _write_package(package, context)
    before = package.read_bytes()
    arguments = (str(package),) if explicit_package else ()
    completed = run_cli(repository, "apply", "--json", *arguments, environment_overrides=environment)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (repository / "automatic-result.txt").read_text() == "selected"
    result = json.loads(completed.stdout)["result"]
    _assert_result(Path(result["result_bundle"]["path"]), ".txt")
    assert package.read_bytes() == before
    assert classify_exchange_artifact(package).kind is ExchangeArtifactKind.PATCH_PACKAGE


def test_suffix_metadata_does_not_change_state_binding_or_cli_json_schema(tmp_path: Path) -> None:
    repository, environment, _, before = _configured(tmp_path)
    after = json.loads(run_cli(repository, "context", "--json", environment_overrides=environment).stdout)
    assert after["output_version"] == 1
    assert after["result"] == before
    bundle = run_cli(repository, "bundle", "--json", environment_overrides=environment)
    full_context = _assert_result(Path(json.loads(bundle.stdout)["result"]["result_bundle_path"]), ".txt")
    for key in ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm"):
        assert full_context[key] == before[key]


def test_parameterless_failed_retry_and_successful_replay_remain_intact(tmp_path: Path) -> None:
    repository, environment, exchange, context = _configured(tmp_path)
    ready = tmp_path / "ready"
    environment["PH_SUFFIX_READY"] = str(ready)
    package = exchange / "retry.zip.txt"
    _write_no_mutation_package(package, context, fail_once=True)
    failed = run_cli(repository, "apply", "--json", environment_overrides=environment)
    assert failed.returncode == 23, failed.stdout + failed.stderr
    failed_result = json.loads(failed.stdout)["result"]
    failed_context = _assert_result(Path(failed_result["result_bundle"]["path"]), ".txt")
    assert failed_context["state_fingerprint"] == context["state_fingerprint"]
    ready.touch()
    retried = run_cli(repository, "apply", "--json", environment_overrides=environment)
    assert retried.returncode == 0, retried.stdout + retried.stderr
    _assert_result(Path(json.loads(retried.stdout)["result"]["result_bundle"]["path"]), ".txt")
    third = run_cli(repository, "apply", "--json", environment_overrides=environment)
    assert third.returncode == 10


def test_watcher_accepts_suffixed_patch_but_does_not_loop_after_failure(tmp_path: Path) -> None:
    _, environment, exchange, context = _configured(tmp_path)
    environment["PH_SUFFIX_READY"] = str(tmp_path / "never-ready")
    _write_no_mutation_package(exchange / "watcher.zip.txt", context, fail_once=True)
    apply_environment = project_environment(environment)
    def delegate():
        return delegate_to_automatic_apply(environment=apply_environment)
    state = SharedWatcherEventState()
    first_log = StringIO()
    first = poll_shared_exchange_once(exchange, state, delegate=delegate, log_stream=first_log, error_stream=StringIO())
    assert first is WatcherPollOutcome.ERROR
    assert json.loads(first_log.getvalue())["process_exit_code"] == 23
    bundles = tuple(exchange.glob("*_Result_*.zip.txt"))
    assert len(bundles) == 1
    _assert_result(bundles[0], ".txt")
    second = poll_shared_exchange_once(exchange, state, delegate=delegate, log_stream=StringIO(), error_stream=StringIO())
    assert second is WatcherPollOutcome.WAITING
    assert tuple(exchange.glob("*_Result_*.zip.txt")) == bundles


@pytest.mark.parametrize("explicit_output", [False, True])
def test_suffix_change_during_capture_never_publishes_inconsistent_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_output: bool,
) -> None:
    import patchharbor.result_bundle_capture as capture_module
    repository, environment, exchange, _ = _configured(tmp_path)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    output = tmp_path / "explicit-results" if explicit_output else None
    original = capture_module.capture_base_bundle_entries
    def capture_then_change(*args, **kwargs):
        captured = original(*args, **kwargs)
        configure_bundle_suffix(".data")
        return captured
    monkeypatch.setattr(capture_module, "capture_base_bundle_entries", capture_then_change)
    with pytest.raises(PatchHarborError, match="bundle suffix changed"):
        create_manual_result_bundle(repository, output_directory=output)
    assert not tuple((output or exchange).glob("*_Result_*"))


def test_newest_valid_suffixed_patch_is_selected_only_for_current_repository(tmp_path: Path) -> None:
    repository, environment, exchange, context = _configured(tmp_path)
    other = create_repository(tmp_path / "other")
    other_context = _register_context(other, environment)
    old = exchange / "old.zip.txt"
    newest_valid = exchange / "new.zip.txt"
    mismatch = exchange / "mismatch.zip.txt"
    foreign = exchange / "foreign.zip.txt"
    _write_package(old, context, result_text="old")
    _write_package(newest_valid, context, result_text="new")
    _write_package(mismatch, {**context, "state_fingerprint": "0" * 16}, result_text="mismatch")
    _write_package(foreign, other_context, result_text="foreign")
    for index, path in enumerate((old, newest_valid, mismatch, foreign)):
        value = 1_700_000_000_000_000_000 + index * 1_000_000_000
        os.utime(path, ns=(value, value))
    completed = run_cli(repository, "apply", "--json", environment_overrides=environment)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (repository / "automatic-result.txt").read_text() == "new"
    assert not (other / "automatic-result.txt").exists()


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("explicit_output", [False, True])
def test_apply_result_suffix_covers_dry_run_and_output_override(
    tmp_path: Path, dry_run: bool, explicit_output: bool,
) -> None:
    repository, environment, exchange, context = _configured(tmp_path)
    package = exchange / "patch.zip.txt"
    _write_package(package, context)
    output = tmp_path / "explicit-results" if explicit_output else exchange
    arguments = ["apply", "--json", str(package)]
    if dry_run:
        arguments.append("--dry-run")
    if explicit_output:
        arguments.extend(("--output-dir", str(output)))
    completed = run_cli(repository, *arguments, environment_overrides=environment)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result_path = Path(json.loads(completed.stdout)["result"]["result_bundle"]["path"])
    assert result_path.parent == output.resolve()
    _assert_result(result_path, ".txt")
    assert (repository / "automatic-result.txt").exists() is not dry_run


def test_old_suffixed_patch_is_still_accepted_after_suffix_is_cleared(tmp_path: Path) -> None:
    repository, environment, exchange, context = _configured(tmp_path)
    package = exchange / "patch.zip.txt"
    _write_package(package, context)
    assert run_cli(repository, "configure", "bundle-suffix", "--clear", environment_overrides=environment).returncode == 0
    completed = run_cli(repository, "apply", "--json", environment_overrides=environment)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    _assert_result(Path(json.loads(completed.stdout)["result"]["result_bundle"]["path"]), "")
