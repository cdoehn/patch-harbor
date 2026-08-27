from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import sys
import zipfile

import pytest

from patchharbor.errors import ExitCode
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor_watcher.loop import (
    poll_input_directory_once,
    run_watcher,
)
from patchharbor_watcher.state import ProcessedFileStore, StabilityTracker
from patchharbor_watcher.apply_boundary import delegate_to_apply
from tests.platform_support import (
    native_script,
    native_value,
    project_environment,
    run_cli,
)
from tests.registration_support import (
    create_repository,
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


def test_watcher_delegation_is_stopped_by_the_core_repository_lock(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
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
    context_completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert context_completed.returncode == 0
    context_envelope = json.loads(context_completed.stdout)
    context = context_envelope["result"]
    assert isinstance(context, dict)

    incoming = tmp_path / "incoming"
    incoming.mkdir()
    package = incoming / "patch.zip"
    _write_lock_protected_package(package, context)
    log = StringIO()
    stability = StabilityTracker()
    processed = ProcessedFileStore.in_memory(incoming.resolve())
    apply_environment = project_environment(environment)

    def delegate(path: Path):
        return delegate_to_apply(
            path,
            apply_command=(sys.executable, "-m", "patchharbor.cli"),
            environment=apply_environment,
        )

    holder = start_repository_lock_holder(
        str(context["repo_id"]),
        environment=apply_environment,
    )
    try:
        first = poll_input_directory_once(
            incoming,
            stability,
            processed,
            delegate=delegate,
            log_stream=log,
            error_stream=StringIO(),
        )
        second = poll_input_directory_once(
            incoming,
            stability,
            processed,
            delegate=delegate,
            log_stream=log,
            error_stream=StringIO(),
        )
    finally:
        try:
            assert release_repository_lock_holder(holder) == 0
        finally:
            stop_repository_lock_holder(holder)

    records = [json.loads(line) for line in log.getvalue().splitlines()]
    assert (first, second) == (0, 1)
    assert len(records) == 1
    assert records[0]["process_exit_code"] == int(ExitCode.REPOSITORY_BUSY)
    assert not (repository / "watcher-executed.txt").exists()
