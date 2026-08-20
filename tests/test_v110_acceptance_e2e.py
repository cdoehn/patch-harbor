"""Complete public acceptance workflows for PatchHarbor 1.1.0."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import sys
import zipfile

import pytest

from patchharbor.errors import ExitCode
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor_watcher.apply_boundary import delegate_to_apply
from patchharbor_watcher.loop import poll_input_directory_once
from patchharbor_watcher.state import ProcessedFileStore, StabilityTracker
from tests.platform_support import (
    native_script,
    native_value,
    project_environment,
    run_cli,
)
from tests.registration_support import (
    create_repository,
    isolated_user_environment,
)


pytestmark = pytest.mark.acceptance


def _register_and_context(
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
    envelope = json.loads(completed.stdout)
    result = envelope["result"]
    assert isinstance(result, dict)
    return result


def _write_patch_package(
    path: Path,
    context: dict[str, object],
    *,
    entrypoint: str,
    payloads: dict[str, bytes] | None = None,
) -> str:
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
        for relative_path, content in (payloads or {}).items():
            archive.writestr(relative_path, content)
    return entrypoint_name


def _result_bundle_path(envelope: dict[str, object]) -> Path:
    result = envelope["result"]
    assert isinstance(result, dict)
    bundle = result["result_bundle"]
    assert isinstance(bundle, dict)
    path = bundle["path"]
    assert isinstance(path, str)
    return Path(path)


def test_v110_acceptance_complete_repository_workflow(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    context = _register_and_context(repository, environment)

    manual_results = tmp_path / "manual-results"
    manual = run_cli(
        repository,
        "bundle",
        "--json",
        "--output-dir",
        str(manual_results),
        environment_overrides=environment,
        timeout_seconds=120,
    )
    assert manual.returncode == 0
    manual_envelope = json.loads(manual.stdout)
    manual_bundle = Path(manual_envelope["result"]["result_bundle_path"])
    assert manual_bundle.is_file()
    with zipfile.ZipFile(manual_bundle) as archive:
        initial_bundle_context = json.loads(archive.read("context.json"))
        assert archive.read("base/tracked.txt") == b"base\n"
        assert "logs/execution.log" not in archive.namelist()
    assert initial_bundle_context["base_commit"] == context["base_commit"]
    assert (
        initial_bundle_context["state_fingerprint"]
        == context["state_fingerprint"]
    )

    package = tmp_path / "workflow.zip"
    entrypoint_name = _write_patch_package(
        package,
        context,
        entrypoint=native_script(
            "printf 'accepted\\n'\n"
            "printf 'entrypoint-ran\\n' > applied.txt",
            "[Console]::Out.WriteLine('accepted')\n"
            "[System.IO.File]::WriteAllText("
            "'applied.txt', \"entrypoint-ran`n\")",
        ),
        payloads={"tracked.txt": b"patched\n", "nested/payload.bin": b"\x00v110\xff"},
    )
    caller = tmp_path / "caller"
    caller.mkdir()

    dry_run = run_cli(
        caller,
        "apply",
        "--dry-run",
        "--json",
        "--output-dir",
        str(tmp_path / "dry-results"),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )
    assert dry_run.returncode == 0
    dry_envelope = json.loads(dry_run.stdout)
    assert dry_envelope["result"]["primary_result"]["kind"] == "dry_run_success"
    assert (repository / "tracked.txt").read_bytes() == b"base\n"
    assert not (repository / "nested").exists()
    assert not (repository / "applied.txt").exists()
    with zipfile.ZipFile(_result_bundle_path(dry_envelope)) as archive:
        assert "logs/execution.log" not in archive.namelist()
        assert json.loads(archive.read("context.json"))["dirty"] is False

    applied = run_cli(
        caller,
        "apply",
        "--json",
        "--output-dir",
        str(tmp_path / "apply-results"),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )
    assert applied.returncode == 0
    applied_envelope = json.loads(applied.stdout)
    assert applied_envelope["result"]["primary_result"]["kind"] == "success"
    assert (repository / "tracked.txt").read_bytes() == b"patched\n"
    assert (repository / "nested" / "payload.bin").read_bytes() == b"\x00v110\xff"
    assert (repository / "applied.txt").read_text(encoding="utf-8") == (
        "entrypoint-ran\n"
    )
    assert not (repository / entrypoint_name).exists()

    with zipfile.ZipFile(_result_bundle_path(applied_envelope)) as archive:
        names = set(archive.namelist())
        final_context = json.loads(archive.read("context.json"))
        assert archive.read("base/tracked.txt") == b"base\n"
        assert archive.read("changes/unstaged.patch")
        assert archive.read("untracked/nested/payload.bin") == b"\x00v110\xff"
        assert archive.read("untracked/applied.txt") == b"entrypoint-ran\n"
        assert b"accepted\n" in archive.read("logs/execution.log")
    assert "logs/run.json" in names
    assert final_context["dirty"] is True
    assert final_context["state_fingerprint"] != context["state_fingerprint"]


def test_v110_acceptance_state_mismatch_writes_nothing_and_bundles_actual_state(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    context = _register_and_context(repository, environment)
    package = tmp_path / "mismatch.zip"
    _write_patch_package(
        package,
        context,
        entrypoint=native_script(
            "printf unexpected > should-not-run.txt",
            "[System.IO.File]::WriteAllText("
            "'should-not-run.txt', 'unexpected')",
        ),
        payloads={"payload.bin": b"must-not-be-written"},
    )
    (repository / "tracked.txt").write_bytes(b"local-change\n")

    completed = run_cli(
        tmp_path,
        "apply",
        "--json",
        "--output-dir",
        str(tmp_path / "results"),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == int(ExitCode.STATE_MISMATCH)
    envelope = json.loads(completed.stdout)
    assert envelope["result"]["primary_result"]["kind"] == "state_mismatch"
    assert not (repository / "payload.bin").exists()
    assert not (repository / "should-not-run.txt").exists()
    assert (repository / "tracked.txt").read_bytes() == b"local-change\n"

    with zipfile.ZipFile(_result_bundle_path(envelope)) as archive:
        actual_context = json.loads(archive.read("context.json"))
        result_manifest = json.loads(archive.read("manifest.json"))
        assert "logs/execution.log" not in archive.namelist()
    assert actual_context["dirty"] is True
    assert actual_context["state_fingerprint"] != context["state_fingerprint"]
    assert result_manifest["expected_state_fingerprint"] == context[
        "state_fingerprint"
    ]
    assert result_manifest["actual_state_fingerprint"] == actual_context[
        "state_fingerprint"
    ]


def test_v110_acceptance_entrypoint_failure_preserves_exit_and_result_bundle(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    context = _register_and_context(repository, environment)
    package = tmp_path / "entrypoint-failure.zip"
    _write_patch_package(
        package,
        context,
        entrypoint=native_script(
            "printf 'acceptance-failure\\n'\n"
            "printf started > started.txt\n"
            "exit 23",
            "[Console]::Out.WriteLine('acceptance-failure')\n"
            "[System.IO.File]::WriteAllText('started.txt', 'started')\n"
            "exit 23",
        ),
        payloads={"payload.bin": b"written-before-entrypoint"},
    )

    completed = run_cli(
        tmp_path,
        "apply",
        "--json",
        "--output-dir",
        str(tmp_path / "results"),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == 23
    envelope = json.loads(completed.stdout)
    assert envelope["error"] is None
    assert envelope["result"]["primary_result"]["kind"] == "entrypoint_exit"
    assert envelope["result"]["primary_result"]["entrypoint_exit_code"] == 23
    assert (repository / "payload.bin").read_bytes() == b"written-before-entrypoint"
    assert (repository / "started.txt").read_text(encoding="utf-8") == "started"

    with zipfile.ZipFile(_result_bundle_path(envelope)) as archive:
        execution_log = archive.read("logs/execution.log")
        run_report = json.loads(archive.read("logs/run.json"))
        assert archive.read("untracked/payload.bin") == b"written-before-entrypoint"
        assert archive.read("untracked/started.txt") == b"started"
    assert b"acceptance-failure\n" in execution_log
    assert run_report["primary_result"]["kind"] == "entrypoint_exit"
    assert run_report["process_exit_code"] == 23


def test_v110_acceptance_bundle_failure_after_success_returns_eleven(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    private_temp = tmp_path / "system-temp"
    private_temp.mkdir()
    environment.update(
        {name: str(private_temp) for name in ("TMPDIR", "TEMP", "TMP")}
    )
    context = _register_and_context(repository, environment)
    package = tmp_path / "bundle-failure.zip"
    output_directory = tmp_path / "results"
    posix_result_path = str(output_directory).replace("'", "'\"'\"'")
    powershell_result_path = str(output_directory).replace("'", "''")
    _write_patch_package(
        package,
        context,
        entrypoint=native_script(
            "printf 'bundle-failure-diagnostics\n'\n"
            "printf completed > completed.txt\n"
            f"rm -rf -- '{posix_result_path}'\n"
            f"printf blocked > '{posix_result_path}'",
            "[Console]::Out.WriteLine('bundle-failure-diagnostics')\n"
            "[System.IO.File]::WriteAllText('completed.txt', 'completed')\n"
            f"Remove-Item -LiteralPath '{powershell_result_path}' "
            "-Recurse -Force\n"
            f"[System.IO.File]::WriteAllText("
            f"'{powershell_result_path}', 'blocked')",
        ),
        payloads={"payload.bin": b"primary-success"},
    )

    completed = run_cli(
        tmp_path,
        "apply",
        "--json",
        "--output-dir",
        str(output_directory),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == int(ExitCode.RESULT_BUNDLE_ERROR)
    envelope = json.loads(completed.stdout)
    result = envelope["result"]
    assert result["primary_result"]["kind"] == "success"
    assert result["result_bundle"]["status"] == "failed"
    assert result["result_bundle"]["path"] is None
    assert (repository / "payload.bin").read_bytes() == b"primary-success"
    assert (repository / "completed.txt").read_text(encoding="utf-8") == "completed"
    assert output_directory.is_file()

    emergency_path = Path(result["result_bundle"]["emergency_diagnostics_path"])
    assert emergency_path.is_dir()
    assert b"bundle-failure-diagnostics\n" in (
        emergency_path / "execution.log"
    ).read_bytes()
    emergency_run = json.loads(
        (emergency_path / "run.json").read_text(encoding="utf-8")
    )
    assert emergency_run["primary_result"]["kind"] == "success"
    assert emergency_run["result_bundle"]["status"] == "failed"
    assert emergency_run["process_exit_code"] == int(ExitCode.RESULT_BUNDLE_ERROR)

def test_v110_acceptance_watcher_delegates_to_real_apply_once(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    context = _register_and_context(repository, environment)
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    package = incoming / "watcher-package.zip"
    _write_patch_package(
        package,
        context,
        entrypoint=native_script(
            "printf watcher-applied > watcher-applied.txt",
            "[System.IO.File]::WriteAllText("
            "'watcher-applied.txt', 'watcher-applied')",
        ),
        payloads={"watcher-payload.bin": b"watcher-payload"},
    )
    package_bytes = package.read_bytes()
    stability = StabilityTracker()
    processed = ProcessedFileStore.in_memory(incoming.resolve())
    log_stream = StringIO()
    error_stream = StringIO()
    apply_environment = project_environment(environment)

    def delegate(path: Path):
        return delegate_to_apply(
            path,
            apply_command=(sys.executable, "-m", "patchharbor.cli"),
            environment=apply_environment,
        )

    delegated = [
        poll_input_directory_once(
            incoming,
            stability,
            processed,
            delegate=delegate,
            log_stream=log_stream,
            error_stream=error_stream,
        )
        for _ in range(3)
    ]

    assert delegated == [0, 1, 0]
    assert package.read_bytes() == package_bytes
    assert (repository / "watcher-payload.bin").read_bytes() == b"watcher-payload"
    assert (repository / "watcher-applied.txt").read_text(encoding="utf-8") == (
        "watcher-applied"
    )
    records = [json.loads(line) for line in log_stream.getvalue().splitlines()]
    assert len(records) == 1
    assert records[0]["process_exit_code"] == 0
    apply_envelope = records[0]["apply_result"]
    assert isinstance(apply_envelope, dict)
    assert apply_envelope["command"] == "apply"
    assert apply_envelope["success"] is True
    assert _result_bundle_path(apply_envelope).is_file()
    assert error_stream.getvalue() == ""
