from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4
import zipfile

import pytest

from patchharbor.exit_status import ExitCode

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
    exchange_state_path,
    git,
    isolated_user_environment,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
    user_configuration_path,
)


pytestmark = pytest.mark.e2e


_MANUAL_NO_MATCH = (
    "no state-bound patch package matches the current registered repository"
)
_AUTOMATIC_NO_MATCH = (
    "no state-bound patch package matches a registered repository"
)
_CURRENT_REPOSITORY_ERROR = (
    "current directory is not inside a uniquely registered PatchHarbor repository"
)


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



def _write_custom_package(
    path: Path,
    context: dict[str, object],
    *,
    posix_entrypoint: str,
    powershell_entrypoint: str,
    payloads: dict[str, bytes] | None = None,
) -> None:
    entrypoint_name = native_value("run.sh", "run.ps1")
    entrypoint = native_script(posix_entrypoint, powershell_entrypoint)
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
        for relative_path, content in (payloads or {}).items():
            archive.writestr(relative_path, content)


def _exchange_records(environment: dict[str, str]) -> list[dict[str, object]]:
    document = json.loads(
        exchange_state_path(environment).read_text(encoding="utf-8")
    )
    assert document["format_version"] == 4
    records = document["entries"]
    assert isinstance(records, list)
    return records


def _identity_record(
    environment: dict[str, str],
    path: Path,
    content_hash: str | None = None,
) -> dict[str, object]:
    expected_hash = content_hash or sha256(path.read_bytes()).hexdigest()
    matches = [
        record
        for record in _exchange_records(environment)
        if record["path"] == str(path.resolve())
        and record["sha256"] == expected_hash
    ]
    assert len(matches) == 1
    return matches[0]


def _ignore_automatic_outputs(repository: Path) -> None:
    (repository / ".gitignore").write_text(
        "automatic-result.txt\nautomatic-runs.txt\nfiles/\n",
        encoding="utf-8",
    )
    git(repository, "add", ".gitignore")
    git(repository, "commit", "--quiet", "-m", "ignore automatic outputs")


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


def _parameterless_apply(
    cwd: Path,
    environment: dict[str, str],
    *,
    dry_run: bool = False,
    automatic: bool = False,
):
    cwd.mkdir(exist_ok=True)
    arguments = ["apply", "--json"]
    if dry_run:
        arguments.append("--dry-run")
    if automatic:
        arguments.append("--automatic")
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


def _assert_unresolved_repository_failure(completed) -> None:
    assert completed.returncode == int(ExitCode.REPOSITORY_ERROR)
    envelope = json.loads(completed.stdout)
    assert envelope["command"] == "apply"
    assert envelope["success"] is False
    assert envelope["error"] == {
        "kind": "repository_resolution_error",
        "message": _CURRENT_REPOSITORY_ERROR,
        "patchharbor_error_code": int(ExitCode.REPOSITORY_ERROR),
        "emergency_diagnostics_path": None,
    }
    assert envelope["result"]["repository_resolved"] is False
    assert envelope["result"]["result_bundle"] == {
        "attempted": False,
        "status": "not_attempted",
        "path": None,
        "emergency_diagnostics_path": None,
    }


def test_dry_run_from_repository_subdirectory_discovers_top_level_package(
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

    caller = repository / "tests" / "unit"
    caller.mkdir(parents=True)
    completed = _parameterless_apply(
        caller,
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


def test_manual_parameterless_apply_only_selects_current_repository_package(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    first = create_repository(tmp_path / "first")
    second = create_repository(tmp_path / "second")
    first_context = _register_context(first, environment)
    second_context = _register_context(second, environment)
    first_package = exchange / "first.zip"
    second_package = exchange / "second.zip"
    _write_package(first_package, first_context, result_text="first")
    _write_package(second_package, second_context, result_text="second")

    completed = _parameterless_apply(first, environment)

    assert completed.returncode == 0
    result = json.loads(completed.stdout)["result"]
    assert result["repository_path"] == str(first.resolve())
    assert result["repo_id"] == first_context["repo_id"]
    assert (first / "automatic-result.txt").read_text(encoding="utf-8") == "first"
    assert not (second / "automatic-result.txt").exists()
    assert _identity_record(environment, first_package)["apply_status"] == "succeeded"
    assert _identity_record(environment, second_package)["apply_status"] is None


def test_newer_foreign_repository_package_is_irrelevant_to_manual_apply(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    first = create_repository(tmp_path / "first")
    second = create_repository(tmp_path / "second")
    first_context = _register_context(first, environment)
    second_context = _register_context(second, environment)
    first_package = exchange / "first-older.zip"
    second_package = exchange / "second-newer.zip"
    _write_package(first_package, first_context, result_text="first")
    _write_package(second_package, second_context, result_text="second")
    os.utime(first_package, ns=(1_700_000_000_100_000_000,) * 2)
    os.utime(second_package, ns=(1_700_000_000_900_000_000,) * 2)

    completed = _parameterless_apply(first, environment)

    assert completed.returncode == 0
    assert (first / "automatic-result.txt").read_text(encoding="utf-8") == "first"
    assert not (second / "automatic-result.txt").exists()
    assert _identity_record(environment, first_package)["apply_status"] == "succeeded"
    assert _identity_record(environment, second_package)["apply_status"] is None


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

    completed = _parameterless_apply(repository, environment)

    _assert_unresolved_selection_failure(
        completed,
        message=_MANUAL_NO_MATCH,
    )
    assert not (repository / "automatic-result.txt").exists()
    assert not tuple(exchange.glob("*_Result_*.zip"))


def test_multiple_matching_candidates_select_the_newest_mtime_ns(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    first = exchange / "aaa-newest-by-mtime.zip"
    second = exchange / "zzz-older-by-mtime.zip"
    _write_package(first, context, result_text="newest")
    _write_package(second, context, result_text="older")
    os.utime(first, ns=(1_700_000_000_200_000_000,) * 2)
    os.utime(second, ns=(1_700_000_000_100_000_000,) * 2)

    completed = _parameterless_apply(repository, environment)

    assert completed.returncode == 0
    assert (repository / "automatic-result.txt").read_text(
        encoding="utf-8"
    ) == "newest"
    assert _identity_record(environment, first)["apply_status"] == "succeeded"
    assert _identity_record(environment, second)["apply_status"] is None


def test_newer_state_mismatch_does_not_block_older_matching_package(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    matching = exchange / "older-matching.zip"
    mismatched = exchange / "newer-mismatched.zip"
    _write_package(matching, context, result_text="matching")
    mismatched_context = dict(context)
    mismatched_context["state_fingerprint"] = "0" * 16
    if mismatched_context["state_fingerprint"] == context["state_fingerprint"]:
        mismatched_context["state_fingerprint"] = "1" * 16
    _write_package(mismatched, mismatched_context, result_text="mismatched")
    os.utime(matching, ns=(1_700_000_000_100_000_000,) * 2)
    os.utime(mismatched, ns=(1_700_000_000_900_000_000,) * 2)

    completed = _parameterless_apply(repository, environment)

    assert completed.returncode == 0
    assert (repository / "automatic-result.txt").read_text(
        encoding="utf-8"
    ) == "matching"
    assert _identity_record(environment, matching)["apply_status"] == "succeeded"
    assert _identity_record(environment, mismatched)["apply_status"] is None


@pytest.mark.parametrize(
    "creation_order",
    (("alpha.zip", "zulu.zip"), ("zulu.zip", "alpha.zip")),
)
def test_equal_mtime_uses_deterministic_normalized_filename_tie_breaker(
    tmp_path: Path,
    creation_order: tuple[str, str],
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    for filename in creation_order:
        _write_package(
            exchange / filename,
            context,
            result_text=filename.removesuffix(".zip"),
        )
    tied_mtime_ns = 1_700_000_000_300_000_000
    for package in exchange.glob("*.zip"):
        os.utime(package, ns=(tied_mtime_ns, tied_mtime_ns))

    completed = _parameterless_apply(repository, environment)

    assert completed.returncode == 0
    assert (repository / "automatic-result.txt").read_text(
        encoding="utf-8"
    ) == "alpha"
    assert _identity_record(
        environment, exchange / "alpha.zip"
    )["apply_status"] == "succeeded"
    assert _identity_record(
        environment, exchange / "zulu.zip"
    )["apply_status"] is None


def test_newer_succeeded_package_does_not_block_older_eligible_package(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    older = exchange / "older-eligible.zip"
    newer = exchange / "newer-first.zip"
    _write_custom_package(
        older,
        context,
        posix_entrypoint="printf o >> automatic-runs.txt",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'o')"
        ),
    )
    _write_custom_package(
        newer,
        context,
        posix_entrypoint="printf n >> automatic-runs.txt",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'n')"
        ),
    )
    os.utime(older, ns=(1_700_000_000_100_000_000,) * 2)
    os.utime(newer, ns=(1_700_000_000_900_000_000,) * 2)

    first = _parameterless_apply(repository, environment)
    second = _parameterless_apply(repository, environment)

    assert first.returncode == 0
    assert second.returncode == 0
    assert (repository / "automatic-runs.txt").read_text(encoding="utf-8") == "no"
    assert _identity_record(environment, newer)["apply_status"] == "succeeded"
    assert _identity_record(environment, older)["apply_status"] == "succeeded"


def test_explicit_patch_path_bypasses_exchange_candidate_selection(
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


def test_unregistered_current_repository_does_not_fall_back_to_other_package(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    registered = create_repository(tmp_path / "registered")
    registered_context = _register_context(registered, environment)
    package = exchange / "registered-repository.zip"
    _write_package(package, registered_context, result_text="must-not-run")
    unregistered = create_repository(tmp_path / "unregistered")

    completed = _parameterless_apply(unregistered, environment)

    _assert_unresolved_repository_failure(completed)
    assert not (registered / "automatic-result.txt").exists()
    assert not (unregistered / "automatic-result.txt").exists()
    assert not exchange_state_path(environment).exists()


def test_explicit_patch_path_may_target_another_registered_repository(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    current = create_repository(tmp_path / "current")
    target = create_repository(tmp_path / "target")
    _register_context(current, environment)
    target_context = _register_context(target, environment)
    package = exchange / "explicit-target.zip"
    _write_package(package, target_context, result_text="target")

    completed = run_cli(
        current,
        "apply",
        "--json",
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == 0
    result = json.loads(completed.stdout)["result"]
    assert result["repository_path"] == str(target.resolve())
    assert result["repo_id"] == target_context["repo_id"]
    assert (target / "automatic-result.txt").read_text(encoding="utf-8") == "target"
    assert not (current / "automatic-result.txt").exists()


def test_automatic_parameterless_apply_remains_global_across_repositories(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    first = create_repository(tmp_path / "first")
    second = create_repository(tmp_path / "second")
    first_context = _register_context(first, environment)
    second_context = _register_context(second, environment)
    first_package = exchange / "first-older.zip"
    second_package = exchange / "second-newer.zip"
    _write_package(first_package, first_context, result_text="first")
    _write_package(second_package, second_context, result_text="second")
    os.utime(first_package, ns=(1_700_000_000_100_000_000,) * 2)
    os.utime(second_package, ns=(1_700_000_000_900_000_000,) * 2)

    completed = _parameterless_apply(
        tmp_path / "watcher-caller",
        environment,
        automatic=True,
    )

    assert completed.returncode == 0
    result = json.loads(completed.stdout)["result"]
    assert result["repository_path"] == str(second.resolve())
    assert result["repo_id"] == second_context["repo_id"]
    assert not (first / "automatic-result.txt").exists()
    assert (second / "automatic-result.txt").read_text(encoding="utf-8") == "second"
    assert _identity_record(environment, first_package)["apply_status"] is None
    assert _identity_record(environment, second_package)["apply_status"] == "succeeded"


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
def test_parameterless_apply_requires_valid_exchange_configuration(
    tmp_path: Path,
    configuration_state: str,
    expected_message: str,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    if configuration_state == "invalid":
        path = user_configuration_path(environment)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    completed = _parameterless_apply(repository, environment)

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


def test_manual_selection_fails_closed_when_current_repository_is_busy(
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
        completed = _parameterless_apply(
            repository,
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
    assert not tuple(exchange.glob("*_Result_*.zip"))
    assert not (repository / "automatic-result.txt").exists()


def test_dry_run_does_not_consume_but_parameterless_apply_does(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    package = exchange / "retryable.package"
    _write_custom_package(
        package,
        context,
        posix_entrypoint="printf x >> automatic-runs.txt",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'x')"
        ),
        payloads={"files/generated.bin": b"payload"},
    )

    first_dry_run = _parameterless_apply(
        repository,
        environment,
        dry_run=True,
    )
    second_dry_run = _parameterless_apply(
        repository,
        environment,
        dry_run=True,
    )

    assert first_dry_run.returncode == 0
    assert second_dry_run.returncode == 0
    assert _identity_record(environment, package)["apply_status"] is None
    assert not (repository / "automatic-runs.txt").exists()

    applied = _parameterless_apply(repository, environment)

    assert applied.returncode == 0
    assert _identity_record(environment, package)["apply_status"] == "succeeded"
    assert (repository / "automatic-runs.txt").read_text(encoding="utf-8") == "x"

    repeated = _parameterless_apply(repository, environment)
    _assert_unresolved_selection_failure(
        repeated,
        message=_MANUAL_NO_MATCH,
    )
    assert (repository / "automatic-runs.txt").read_text(encoding="utf-8") == "x"

    explicit = run_cli(
        tmp_path,
        "apply",
        "--json",
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert explicit.returncode == 0
    assert (repository / "automatic-runs.txt").read_text(encoding="utf-8") == "xx"
    assert package.is_file()


def test_changed_bytes_at_the_same_exchange_path_are_a_new_identity(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    package = exchange / "replaced.package"
    _write_custom_package(
        package,
        context,
        posix_entrypoint="printf 1 >> automatic-runs.txt",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', '1')"
        ),
    )
    first_hash = sha256(package.read_bytes()).hexdigest()

    first = _parameterless_apply(repository, environment)
    assert first.returncode == 0

    _write_custom_package(
        package,
        context,
        posix_entrypoint="printf 2 >> automatic-runs.txt",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', '2')"
        ),
    )
    second_hash = sha256(package.read_bytes()).hexdigest()
    assert second_hash != first_hash

    second = _parameterless_apply(repository, environment)

    assert second.returncode == 0
    assert (repository / "automatic-runs.txt").read_text(encoding="utf-8") == "12"
    assert (
        _identity_record(environment, package, first_hash)["apply_status"]
        == "succeeded"
    )
    assert (
        _identity_record(environment, package, second_hash)["apply_status"]
        == "succeeded"
    )
    assert package.is_file()


def test_preflight_failure_remains_retryable_without_attempt_mark(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    context = _register_context(repository, environment)
    package = exchange / "invalid-entrypoint.package"
    entrypoint_name = native_value("run.sh", "run.ps1")
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(_manifest(context), separators=(",", ":")).encode(
                "utf-8"
            ),
        )
        archive.writestr(entrypoint_name, b"not a PatchHarbor script\n")

    first = _parameterless_apply(repository, environment)
    second = _parameterless_apply(repository, environment)

    assert first.returncode == int(ExitCode.NO_VALID_SCRIPT)
    assert second.returncode == int(ExitCode.NO_VALID_SCRIPT)
    assert _identity_record(environment, package)["apply_status"] is None
    assert package.is_file()


def test_failed_parameterless_apply_can_be_retried_manually_and_then_succeeds(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    trigger = tmp_path / "external-prerequisite.ready"
    package = exchange / "retry-after-external-fix.package"
    posix_trigger = str(trigger).replace("'", "'\"'\"'")
    powershell_trigger = str(trigger).replace("'", "''")
    _write_custom_package(
        package,
        context,
        posix_entrypoint=(
            f"test -f '{posix_trigger}' || exit 23\n"
            "printf x >> automatic-runs.txt"
        ),
        powershell_entrypoint=(
            f"if (-not (Test-Path -LiteralPath '{powershell_trigger}')) "
            "{ exit 23 }\n"
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'x')"
        ),
    )

    first = _parameterless_apply(repository, environment)

    assert first.returncode == 23
    assert _identity_record(environment, package)["apply_status"] == "failed"
    assert git(repository, "status", "--porcelain").stdout == ""
    current = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert current.returncode == 0
    assert json.loads(current.stdout)["result"] == context

    trigger.write_text("ready\n", encoding="utf-8")
    second = _parameterless_apply(repository, environment)

    assert second.returncode == 0
    assert _identity_record(environment, package)["apply_status"] == "succeeded"
    assert (repository / "automatic-runs.txt").read_text(
        encoding="utf-8"
    ) == "x"

    third = _parameterless_apply(
        tmp_path / "third-automatic",
        environment,
        automatic=True,
    )
    _assert_unresolved_selection_failure(
        third,
        message=_AUTOMATIC_NO_MATCH,
    )
    assert (repository / "automatic-runs.txt").read_text(
        encoding="utf-8"
    ) == "x"


def test_failed_newer_automatic_candidate_does_not_block_older_package(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    older = exchange / "older-success.zip"
    newer = exchange / "newer-failure.zip"
    _write_custom_package(
        older,
        context,
        posix_entrypoint="printf o >> automatic-runs.txt",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'o')"
        ),
    )
    _write_custom_package(
        newer,
        context,
        posix_entrypoint="printf f >> automatic-runs.txt\nexit 23",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'f')\n"
            "exit 23"
        ),
    )
    os.utime(older, ns=(1_700_000_000_100_000_000,) * 2)
    os.utime(newer, ns=(1_700_000_000_900_000_000,) * 2)

    first = _parameterless_apply(
        tmp_path / "automatic-first",
        environment,
        automatic=True,
    )
    second = _parameterless_apply(
        tmp_path / "automatic-second",
        environment,
        automatic=True,
    )

    assert first.returncode == 23
    assert second.returncode == 0
    assert (repository / "automatic-runs.txt").read_text(encoding="utf-8") == "fo"
    assert _identity_record(environment, newer)["apply_status"] == "failed"
    assert _identity_record(environment, older)["apply_status"] == "succeeded"


def test_automatic_apply_does_not_repeat_a_failed_package(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    package = exchange / "watcher-failure.package"
    _write_custom_package(
        package,
        context,
        posix_entrypoint="printf x >> automatic-runs.txt\nexit 23",
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'x')\n"
            "exit 23"
        ),
    )

    first = _parameterless_apply(
        tmp_path / "automatic-first",
        environment,
        automatic=True,
    )
    second = _parameterless_apply(
        tmp_path / "automatic-second",
        environment,
        automatic=True,
    )

    assert first.returncode == 23
    _assert_unresolved_selection_failure(
        second,
        message=_AUTOMATIC_NO_MATCH,
    )
    assert _identity_record(environment, package)["apply_status"] == "failed"
    assert (repository / "automatic-runs.txt").read_text(
        encoding="utf-8"
    ) == "x"


@pytest.mark.parametrize("repository_change", ("base_commit", "state_fingerprint"))
def test_failed_manual_retry_still_requires_the_original_repository_state(
    tmp_path: Path,
    repository_change: str,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    package = exchange / "entrypoint-failure.package"
    _write_custom_package(
        package,
        context,
        posix_entrypoint="exit 23",
        powershell_entrypoint="exit 23",
    )
    failed = _parameterless_apply(repository, environment)

    assert failed.returncode == 23
    assert _identity_record(environment, package)["apply_status"] == "failed"
    assert git(repository, "status", "--porcelain").stdout == ""

    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
    if repository_change == "base_commit":
        git(repository, "add", "tracked.txt")
        git(repository, "commit", "--quiet", "-m", "change repository state")

    mismatched = _parameterless_apply(repository, environment)

    _assert_unresolved_selection_failure(
        mismatched,
        message=_MANUAL_NO_MATCH,
    )
    assert _identity_record(environment, package)["apply_status"] == "failed"
    assert package.is_file()


def test_result_bundle_failure_still_consumes_automatic_identity(
    tmp_path: Path,
) -> None:
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repository")
    _ignore_automatic_outputs(repository)
    context = _register_context(repository, environment)
    package = exchange / "bundle-failure.package"
    output_directory = tmp_path / "results"
    posix_output = str(output_directory).replace("'", "'\"'\"'")
    powershell_output = str(output_directory).replace("'", "''")
    _write_custom_package(
        package,
        context,
        posix_entrypoint=(
            "printf x >> automatic-runs.txt\n"
            f"rm -rf -- '{posix_output}'\n"
            f"printf blocked > '{posix_output}'"
        ),
        powershell_entrypoint=(
            "[System.IO.File]::AppendAllText('automatic-runs.txt', 'x')\n"
            f"Remove-Item -LiteralPath '{powershell_output}' -Recurse -Force\n"
            f"[System.IO.File]::WriteAllText('{powershell_output}', 'blocked')"
        ),
    )

    failed = run_cli(
        repository,
        "apply",
        "--json",
        "--output-dir",
        str(output_directory),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert failed.returncode == int(ExitCode.RESULT_BUNDLE_ERROR)
    assert _identity_record(environment, package)["apply_status"] == "succeeded"
    assert (repository / "automatic-runs.txt").read_text(encoding="utf-8") == "x"
    assert output_directory.is_file()

    repeated = _parameterless_apply(repository, environment)
    _assert_unresolved_selection_failure(
        repeated,
        message=_MANUAL_NO_MATCH,
    )
    assert package.is_file()
