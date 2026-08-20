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


def test_watcher_delegates_stable_file_to_real_apply_stub_process(
    tmp_path: Path,
) -> None:
    input_directory = tmp_path / "incoming"
    input_directory.mkdir()
    patch_path = input_directory / "patch.bin"
    patch_path.write_bytes(b"byte-exact-input\x00")

    calls_path = tmp_path / "calls.jsonl"
    stub_path = tmp_path / "apply_stub.py"
    stub_path.write_text(
        """\
import json
import os
from pathlib import Path
import sys

with Path(os.environ["PATCHHARBOR_WATCHER_TEST_CALLS"]).open(
    "a", encoding="utf-8"
) as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps({"stub": "applied", "input_path": sys.argv[-1]}))
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PATCHHARBOR_WATCHER_TEST_CALLS"] = str(calls_path)

    stop_requested = False
    completed_poll_cycles = 0
    watcher_stdout = StringIO()
    watcher_stderr = StringIO()

    def delegate(path: Path):
        return delegate_to_apply(
            path,
            apply_command=(sys.executable, str(stub_path)),
            environment=environment,
        )

    def complete_poll_cycle(_timeout_seconds: float) -> None:
        nonlocal completed_poll_cycles, stop_requested
        completed_poll_cycles += 1
        stop_requested = completed_poll_cycles == 2

    run_watcher(
        input_directory,
        delegate=delegate,
        poll_interval_seconds=1.0,
        log_stream=watcher_stdout,
        error_stream=watcher_stderr,
        stop_requested=lambda: stop_requested,
        wait_between_polls=complete_poll_cycle,
    )

    assert completed_poll_cycles == 2
    calls = [
        json.loads(line)
        for line in calls_path.read_text(encoding="utf-8").splitlines()
    ]
    assert calls == [["apply", "--json", str(patch_path)]]

    records = [json.loads(line) for line in watcher_stdout.getvalue().splitlines()]
    assert len(records) == 1
    assert records[0]["input_path"] == str(patch_path)
    assert records[0]["process_exit_code"] == 0
    assert records[0]["apply_response_is_json_object"] is True
    assert records[0]["apply_result"] == {
        "stub": "applied",
        "input_path": str(patch_path),
    }
    assert records[0]["invalid_apply_response"] is None
    assert watcher_stderr.getvalue() == ""


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
