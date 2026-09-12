from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import sys
import zipfile

import pytest

from patchharbor.exit_status import ExitCode

from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor_watcher.loop import (
    SharedWatcherEventState,
    WatcherPollOutcome,
    poll_shared_exchange_once,
)
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from tests.platform_support import (
    native_script,
    native_value,
    project_environment,
    run_cli,
)
from tests.registration_support import (
    create_repository,
    configured_exchange_directory,
    exchange_state_path,
    git,
    isolated_user_environment,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
)


pytestmark = pytest.mark.e2e


def _write_lock_protected_package(
    path: Path,
    context: dict[str, object],
) -> None:
    entrypoint_name = native_value("run.sh", "run.ps1")
    manifest = {
        "marker": PATCH_MARKER,
        "format_version": PATCH_FORMAT_VERSION,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "entrypoint": entrypoint_name,
    }
    entrypoint = native_script(
        "printf executed > watcher-executed.txt",
        "[System.IO.File]::WriteAllText('watcher-executed.txt', 'executed')",
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                manifest,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint_name, entrypoint.encode("utf-8"))


def test_watcher_retries_after_core_repository_lock_is_released(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    assert run_cli(
        repository,
        "register",
        environment_overrides=environment,
    ).returncode == 0
    assert run_cli(
        repository,
        "configure",
        "exchange-directory",
        str(tmp_path / "exchange"),
        environment_overrides=environment,
    ).returncode == 0
    context_completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert context_completed.returncode == 0
    context = json.loads(context_completed.stdout)["result"]
    assert isinstance(context, dict)

    exchange = configured_exchange_directory(environment)
    package = exchange / "patch.zip"
    _write_lock_protected_package(package, context)
    apply_environment = project_environment(environment)

    def delegate():
        return delegate_to_automatic_apply(
            environment=apply_environment,
        )

    holder = start_repository_lock_holder(
        str(context["repo_id"]),
        environment=apply_environment,
    )
    locked_log = StringIO()
    try:
        locked = poll_shared_exchange_once(
            exchange,
            SharedWatcherEventState(),
            delegate=delegate,
            log_stream=locked_log,
            error_stream=StringIO(),
        )
    finally:
        try:
            assert release_repository_lock_holder(holder) == 0
        finally:
            stop_repository_lock_holder(holder)

    locked_record = json.loads(locked_log.getvalue())
    locked_response = locked_record["apply_result"]
    assert locked is WatcherPollOutcome.ERROR
    assert locked_record["process_exit_code"] == int(ExitCode.REPOSITORY_BUSY)
    assert isinstance(locked_response, dict)
    assert locked_response["error"]["kind"] == "repository_busy"
    assert not (repository / "watcher-executed.txt").exists()

    retried = poll_shared_exchange_once(
        exchange,
        SharedWatcherEventState(),
        delegate=delegate,
        log_stream=StringIO(),
        error_stream=StringIO(),
    )

    assert retried is WatcherPollOutcome.APPLIED
    assert (repository / "watcher-executed.txt").read_text(
        encoding="utf-8"
    ) == "executed"
    assert package.is_file()


def _write_automatic_watcher_package(
    path: Path,
    context: dict[str, object],
) -> None:
    entrypoint_name = native_value("run.sh", "run.ps1")
    manifest = {
        "marker": PATCH_MARKER,
        "format_version": PATCH_FORMAT_VERSION,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "entrypoint": entrypoint_name,
    }
    entrypoint = native_script(
        "printf x >> watcher-automatic-runs.txt",
        "[System.IO.File]::AppendAllText('watcher-automatic-runs.txt', 'x')",
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                manifest,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint_name, entrypoint.encode("utf-8"))


def test_shared_watcher_delegates_discovery_identity_and_retry_to_core(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / ".gitignore").write_text(
        "watcher-automatic-runs.txt\n",
        encoding="utf-8",
    )
    git(repository, "add", ".gitignore")
    git(repository, "commit", "--quiet", "-m", "ignore watcher output")
    environment = isolated_user_environment(tmp_path / "user")
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    configured = run_cli(
        repository,
        "configure",
        "exchange-directory",
        str(tmp_path / "exchange"),
        environment_overrides=environment,
    )
    assert configured.returncode == 0
    exchange = configured_exchange_directory(environment)
    context_completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert context_completed.returncode == 0
    context = json.loads(context_completed.stdout)["result"]
    assert isinstance(context, dict)

    package = exchange / "chat-output.bin"
    _write_automatic_watcher_package(package, context)
    result_bundle = exchange / "repository_Result_000000_0101_abcdef.zip"
    with zipfile.ZipFile(result_bundle, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"marker": "patch-harbor-result-bundle"}),
        )
    (exchange / "unrelated.txt").write_text("other", encoding="utf-8")
    (exchange / "unfinished.crdownload").write_bytes(b"incomplete")

    apply_environment = project_environment(environment)

    def delegate():
        return delegate_to_automatic_apply(
            environment=apply_environment,
        )

    first_log = StringIO()
    first = poll_shared_exchange_once(
        exchange,
        SharedWatcherEventState(),
        delegate=delegate,
        log_stream=first_log,
        error_stream=StringIO(),
    )

    assert first is WatcherPollOutcome.APPLIED
    assert (repository / "watcher-automatic-runs.txt").read_text(
        encoding="utf-8"
    ) == "x"
    assert package.is_file()
    assert result_bundle.is_file()
    assert (exchange / "unrelated.txt").is_file()
    assert (exchange / "unfinished.crdownload").is_file()
    generated_bundles = tuple(
        path
        for path in exchange.glob("*_Result_*.zip")
        if path != result_bundle
    )
    assert len(generated_bundles) == 1

    state_document = json.loads(
        exchange_state_path(environment).read_text(encoding="utf-8")
    )
    matching_records = [
        record
        for record in state_document["entries"]
        if record["path"] == str(package.resolve())
    ]
    assert len(matching_records) == 1
    assert matching_records[0]["apply_status"] == "succeeded"

    restart_log = StringIO()
    second = poll_shared_exchange_once(
        exchange,
        SharedWatcherEventState(),
        delegate=delegate,
        log_stream=restart_log,
        error_stream=StringIO(),
    )

    assert second is WatcherPollOutcome.WAITING
    assert (repository / "watcher-automatic-runs.txt").read_text(
        encoding="utf-8"
    ) == "x"
    first_record = json.loads(first_log.getvalue())
    second_record = json.loads(restart_log.getvalue())
    assert first_record["event"] == "automatic_apply_completed"
    assert second_record["event"] == "waiting_for_exchange_patch"
    assert "input_path" not in first_record
    assert "input_sha256" not in first_record


def test_watcher_does_not_loop_after_a_failed_entrypoint(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / ".gitignore").write_text(
        "watcher-failed-runs.txt\n",
        encoding="utf-8",
    )
    git(repository, "add", ".gitignore")
    git(repository, "commit", "--quiet", "-m", "ignore watcher failure count")
    environment = isolated_user_environment(tmp_path / "user")
    assert run_cli(
        repository,
        "register",
        environment_overrides=environment,
    ).returncode == 0
    assert run_cli(
        repository,
        "configure",
        "exchange-directory",
        str(tmp_path / "exchange"),
        environment_overrides=environment,
    ).returncode == 0
    context_completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert context_completed.returncode == 0
    context = json.loads(context_completed.stdout)["result"]
    assert isinstance(context, dict)

    exchange = configured_exchange_directory(environment)
    package = exchange / "failing-watcher-patch.zip"
    entrypoint_name = native_value("run.sh", "run.ps1")
    manifest = {
        "marker": PATCH_MARKER,
        "format_version": PATCH_FORMAT_VERSION,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "entrypoint": entrypoint_name,
    }
    entrypoint = native_script(
        "printf x >> watcher-failed-runs.txt\nexit 23",
        (
            "[System.IO.File]::AppendAllText("
            "'watcher-failed-runs.txt', 'x')\nexit 23"
        ),
    )
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                manifest,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint_name, entrypoint.encode("utf-8"))

    apply_environment = project_environment(environment)

    def delegate():
        return delegate_to_automatic_apply(environment=apply_environment)

    first = poll_shared_exchange_once(
        exchange,
        SharedWatcherEventState(),
        delegate=delegate,
        log_stream=StringIO(),
        error_stream=StringIO(),
    )
    second = poll_shared_exchange_once(
        exchange,
        SharedWatcherEventState(),
        delegate=delegate,
        log_stream=StringIO(),
        error_stream=StringIO(),
    )

    assert first is WatcherPollOutcome.ERROR
    assert second is WatcherPollOutcome.WAITING
    assert (repository / "watcher-failed-runs.txt").read_text(
        encoding="utf-8"
    ) == "x"
    state_document = json.loads(
        exchange_state_path(environment).read_text(encoding="utf-8")
    )
    matching_records = [
        record
        for record in state_document["entries"]
        if record["path"] == str(package.resolve())
    ]
    assert len(matching_records) == 1
    assert matching_records[0]["apply_status"] == "failed"
