from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4
import zipfile

import pytest

from patchharbor.errors import ExitCode
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from tests.platform_support import (
    native_script,
    native_value,
    project_environment,
    run_cli,
)
from tests.registration_support import (
    configured_exchange_directory,
    create_repository,
    isolated_user_environment,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
    user_configuration_path,
)


pytestmark = pytest.mark.e2e


def _configure_user(tmp_path: Path) -> tuple[dict[str, str], Path]:
    environment = isolated_user_environment(tmp_path / "user")
    exchange = tmp_path / "exchange"
    completed = run_cli(
        tmp_path,
        "configure",
        "exchange-directory",
        str(exchange),
        environment_overrides=environment,
    )
    assert completed.returncode == 0
    assert configured_exchange_directory(environment) == exchange.resolve()
    return environment, exchange.resolve()


def _register_context(
    repository: Path,
    environment: dict[str, str],
) -> dict[str, object]:
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert completed.returncode == 0
    result = json.loads(completed.stdout)["result"]
    assert isinstance(result, dict)
    return result


def _manifest(context: dict[str, object]) -> dict[str, object]:
    return {
        "marker": PATCH_MARKER,
        "format_version": PATCH_FORMAT_VERSION,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "entrypoint": native_value("run.sh", "run.ps1"),
    }


def _write_package(
    path: Path,
    context: dict[str, object],
    *,
    result_text: str = "selected",
) -> None:
    entrypoint_name = native_value("run.sh", "run.ps1")
    entrypoint = native_script(
        f"printf {result_text} > automatic-result.txt",
        (
            "[System.IO.File]::WriteAllText("
            f"'automatic-result.txt', '{result_text}')"
        ),
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                _manifest(context),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint_name, entrypoint.encode("utf-8"))
        archive.writestr("files/generated.bin", b"payload")


def _write_result_bundle_marker(path: Path, *, include_patch: bool = False) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "marker": "patch-harbor-result-bundle",
                    "format_version": 1,
                },
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        if include_patch:
            archive.writestr("patch.json", b"{}")


def _automatic_apply(
    cwd: Path,
    environment: dict[str, str],
    *,
    dry_run: bool = False,
):
    cwd.mkdir(exist_ok=True)
    arguments = ["apply", "--json"]
    if dry_run:
        arguments.append("--dry-run")
    return run_cli(
        cwd,
        *arguments,
        environment_overrides=environment,
        timeout_seconds=120,
    )


def _assert_unresolved_selection_failure(
    completed,
    *,
    message: str,
) -> None:
    assert completed.returncode == int(ExitCode.PATCH_PACKAGE_ERROR)
    envelope = json.loads(completed.stdout)
    assert envelope["command"] == "apply"
    assert envelope["success"] is False
    assert envelope["error"] == {
        "kind": "patch_package_error",
        "message": message,
        "patchharbor_error_code": int(ExitCode.PATCH_PACKAGE_ERROR),
        "emergency_diagnostics_path": None,
    }
    assert envelope["result"]["repository_resolved"] is False
    assert envelope["result"]["result_bundle"] == {
        "attempted": False,
        "status": "not_attempted",
        "path": None,
        "emergency_diagnostics_path": None,
    }


def test_dry_run_discovers_one_content_classified_top_level_package(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)

    _write_package(exchange / "download-without-extension", context)
    _write_package(exchange / "unfinished.crdownload", context)
    _write_result_bundle_marker(
        exchange / "looks-like-patch.zip",
        include_patch=True,
    )
    (exchange / "direct.sh").write_text(
        "# PATCHHARBOR\nprintf direct\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(exchange / "foreign.zip", "w") as archive:
        archive.writestr("payload.txt", b"foreign")
    nested = exchange / "nested"
    nested.mkdir()
    _write_package(nested / "nested.zip", context)
    if os.name != "nt":
        (exchange / "package-link").symlink_to(
            exchange / "download-without-extension"
        )

    completed = _automatic_apply(
        tmp_path / "unrelated-caller",
        environment,
        dry_run=True,
    )

    assert completed.returncode == 0
    result = json.loads(completed.stdout)["result"]
    assert result["repository_path"] == str(repository.resolve())
    assert result["repo_id"] == context["repo_id"]
    assert result["primary_result"]["kind"] == "dry_run_success"
    bundle_path = Path(result["result_bundle"]["path"])
    assert bundle_path.parent == exchange
    assert bundle_path.is_file()
    assert not (repository / "automatic-result.txt").exists()
    assert not (repository / "files" / "generated.bin").exists()


def test_automatic_apply_selects_by_repo_id_and_current_state_across_repositories(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    first = create_repository(tmp_path / "first")
    second = create_repository(tmp_path / "second")
    first_context = _register_context(first, environment)
    second_context = _register_context(second, environment)

    _write_package(exchange / "stale-first.zip", first_context, result_text="stale")
    (first / "changed-after-context.txt").write_text("dirty\n", encoding="utf-8")
    _write_package(
        exchange / "matching-second.bin",
        second_context,
        result_text="second",
    )

    completed = _automatic_apply(tmp_path / "caller", environment)

    assert completed.returncode == 0
    result = json.loads(completed.stdout)["result"]
    assert result["repository_path"] == str(second.resolve())
    assert result["repo_id"] == second_context["repo_id"]
    assert (second / "automatic-result.txt").read_text(encoding="utf-8") == "second"
    assert (second / "files" / "generated.bin").read_bytes() == b"payload"
    assert not (first / "automatic-result.txt").exists()


def test_no_matching_candidate_fails_without_repository_mutation_or_bundle(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)

    stale_context = dict(context)
    stale_context["state_fingerprint"] = "0" * 16
    if stale_context["state_fingerprint"] == context["state_fingerprint"]:
        stale_context["state_fingerprint"] = "1" * 16
    _write_package(exchange / "stale.zip", stale_context)

    unknown_context = dict(context)
    unknown_context["repo_id"] = str(uuid4())
    _write_package(exchange / "unknown.zip", unknown_context)

    completed = _automatic_apply(tmp_path / "caller", environment)

    _assert_unresolved_selection_failure(
        completed,
        message="no state-bound patch package matches a registered repository",
    )
    assert not (repository / "automatic-result.txt").exists()
    assert not tuple(exchange.glob("patchharbor_result_*.zip"))


def test_multiple_matching_candidates_fail_without_guessing_or_mutation(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    _write_package(exchange / "first.zip", context, result_text="first")
    _write_package(exchange / "second.zip", context, result_text="second")

    completed = _automatic_apply(tmp_path / "caller", environment)

    _assert_unresolved_selection_failure(
        completed,
        message=(
            "multiple state-bound patch packages match registered repositories; "
            "pass PATCH_ZIP explicitly"
        ),
    )
    assert not (repository / "automatic-result.txt").exists()
    assert not (repository / "files" / "generated.bin").exists()
    assert not tuple(exchange.glob("patchharbor_result_*.zip"))


def test_explicit_patch_path_overrides_ambiguous_exchange_candidates(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    _write_package(exchange / "first.zip", context, result_text="first")
    _write_package(exchange / "second.zip", context, result_text="second")
    explicit = tmp_path / "explicit.package"
    _write_package(explicit, context, result_text="explicit")

    completed = run_cli(
        tmp_path,
        "apply",
        "--json",
        str(explicit),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == 0
    assert (
        repository / "automatic-result.txt"
    ).read_text(encoding="utf-8") == "explicit"


@pytest.mark.parametrize(
    ("configuration_state", "expected_message"),
    (
        ("missing", "configuration does not exist"),
        (
            "invalid",
            "configuration must contain exactly the two format-1 fields",
        ),
    ),
)
def test_automatic_apply_requires_valid_exchange_configuration(
    tmp_path: Path,
    configuration_state: str,
    expected_message: str,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")
    if configuration_state == "invalid":
        path = user_configuration_path(environment)
        path.parent.mkdir(parents=True)
        path.write_text("{}\n", encoding="utf-8")

    completed = _automatic_apply(tmp_path / "caller", environment)

    assert completed.returncode == int(ExitCode.SOURCE_ERROR)
    envelope = json.loads(completed.stdout)
    assert envelope["success"] is False
    assert envelope["error"] == {
        "kind": "configuration_error",
        "message": expected_message,
        "patchharbor_error_code": int(ExitCode.SOURCE_ERROR),
        "emergency_diagnostics_path": None,
    }
    assert envelope["result"]["repository_resolved"] is False
    assert envelope["result"]["result_bundle"]["attempted"] is False


def test_automatic_selection_fails_closed_when_candidate_repository_is_busy(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    _write_package(exchange / "matching.zip", context)
    holder = start_repository_lock_holder(
        str(context["repo_id"]),
        environment=project_environment(environment),
    )
    try:
        completed = _automatic_apply(
            tmp_path / "caller",
            environment,
            dry_run=True,
        )
    finally:
        try:
            assert release_repository_lock_holder(holder) == 0
        finally:
            stop_repository_lock_holder(holder)

    assert completed.returncode == int(ExitCode.REPOSITORY_BUSY)
    envelope = json.loads(completed.stdout)
    assert envelope["success"] is False
    assert envelope["error"]["kind"] == "repository_busy"
    assert envelope["result"]["repository_resolved"] is False
    assert not tuple(exchange.glob("patchharbor_result_*.zip"))
    assert not (repository / "automatic-result.txt").exists()
