from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import zipfile

import pytest

from patchharbor.errors import ExitCode
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from tests.platform_support import (
    native_script,
    native_value,
    normalized_path,
    project_environment,
    run_cli,
)
from tests.registration_support import (
    create_repository,
    git,
    isolated_user_environment,
    probe_repository_lock,
    local_exclude_path,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
)


pytestmark = pytest.mark.e2e


def _register_context(
    repository: Path,
    user_root: Path,
) -> tuple[dict[str, str], dict[str, object]]:
    environment = isolated_user_environment(user_root)
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
    return environment, result


def _manifest(context: dict[str, object]) -> dict[str, object]:
    return {
        "marker": PATCH_MARKER,
        "format_version": PATCH_FORMAT_VERSION,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "entrypoint": "run.sh",
    }


def _write_package(
    path: Path,
    manifest: dict[str, object],
) -> None:
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
        archive.writestr(
            "run.sh",
            "# PATCHHARBOR\nprintf executed > executed.txt\n",
        )
        archive.writestr("files/payload.bin", b"\x00payload\xff")


def _write_apply_package(
    path: Path,
    context: dict[str, object],
) -> str:
    entrypoint_name = native_value("run.sh", "run.ps1")
    manifest = _manifest(context)
    manifest["entrypoint"] = entrypoint_name
    entrypoint = native_script(
        "if IFS= read -r _value; then exit 41; fi\n"
        "printf '1\n' >> entrypoint-starts.txt\n"
        "pwd > entrypoint-cwd.txt\n"
        "printf 'stdout-line\n'\n"
        "printf 'stderr-line\n' >&2",
        "$inputLine = [Console]::In.ReadLine()\n"
        "if ($null -ne $inputLine) { exit 41 }\n"
        "[System.IO.File]::AppendAllText('entrypoint-starts.txt', \"1`n\")\n"
        "[System.IO.File]::WriteAllText("
        "'entrypoint-cwd.txt', (Get-Location).Path)\n"
        "$stdout = [Console]::OpenStandardOutput()\n"
        "$stdoutBytes = [System.Text.Encoding]::UTF8.GetBytes("
        '"stdout-line`n")\n'
        "$stdout.Write($stdoutBytes, 0, $stdoutBytes.Length)\n"
        "$stderr = [Console]::OpenStandardError()\n"
        "$stderrBytes = [System.Text.Encoding]::UTF8.GetBytes("
        '"stderr-line`n")\n'
        "$stderr.Write($stderrBytes, 0, $stderrBytes.Length)",
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
        archive.writestr("files/payload.bin", b"\x00new\xff")
        archive.writestr("nested/new.bin", b"\x10nested\x00")
    return entrypoint_name


def _write_execution_package(
    path: Path,
    context: dict[str, object],
    entrypoint: str,
) -> None:
    entrypoint_name = native_value("run.sh", "run.ps1")
    manifest = _manifest(context)
    manifest["entrypoint"] = entrypoint_name

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


def _run_dry_run(
    package: Path,
    caller: Path,
    environment: dict[str, str],
    *,
    json_output: bool = False,
    output_directory: Path | None = None,
):
    caller.mkdir(exist_ok=True)
    arguments = ["apply", "--dry-run"]
    if json_output:
        arguments.append("--json")
    if output_directory is not None:
        arguments.extend(("--output-dir", str(output_directory)))
    arguments.append(str(package))
    return run_cli(
        caller,
        *arguments,
        environment_overrides=environment,
    )


def _result_directory(environment: dict[str, str]) -> Path:
    if os.name == "nt":
        return Path(environment["LOCALAPPDATA"]) / "PatchHarbor" / "results"
    return Path(environment["XDG_STATE_HOME"]) / "patchharbor" / "results"


def _result_bundles(environment: dict[str, str]) -> tuple[Path, ...]:
    directory = _result_directory(environment)
    if not directory.exists():
        return ()
    return tuple(sorted(directory.glob("patchharbor_result_*.zip")))


def _different_hex(value: str) -> str:
    replacement = "0" if value[0] != "0" else "1"
    return replacement + value[1:]


def _assert_repository_unmodified(repository: Path) -> None:
    assert not (repository / "executed.txt").exists()
    assert not (repository / "files" / "payload.bin").exists()


def _repository_files(repository: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in repository.rglob("*"):
        relative = path.relative_to(repository)
        if relative.parts[0] == ".git" or not path.is_file():
            continue
        files[relative.as_posix()] = path.read_bytes()
    return files


def test_apply_writes_expected_bytes_runs_once_and_bundles_state(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked_payload = repository / "files" / "payload.bin"
    tracked_payload.parent.mkdir()
    tracked_payload.write_bytes(b"old")
    git(repository, "add", "files/payload.bin")
    git(repository, "commit", "--quiet", "-m", "add payload")

    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "patch.zip"
    entrypoint_name = _write_apply_package(package, context)
    output_directory = tmp_path / "results"
    caller = tmp_path / "caller"
    caller.mkdir()

    completed = run_cli(
        caller,
        "apply",
        "--json",
        "--output-dir",
        str(output_directory),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == 0
    envelope = json.loads(completed.stdout)
    assert envelope["success"] is True
    result = envelope["result"]
    assert isinstance(result, dict)

    assert tracked_payload.read_bytes() == b"\x00new\xff"
    assert (repository / "nested" / "new.bin").read_bytes() == (
        b"\x10nested\x00"
    )
    assert (repository / "entrypoint-starts.txt").read_text(
        encoding="utf-8"
    ).splitlines() == ["1"]
    assert normalized_path(
        (repository / "entrypoint-cwd.txt").read_text(encoding="utf-8").strip()
    ) == normalized_path(repository)
    assert not (repository / entrypoint_name).exists()

    bundle_result = result["result_bundle"]
    assert isinstance(bundle_result, dict)
    bundle_path = Path(bundle_result["path"])
    assert bundle_path.parent == output_directory.resolve()
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        committed_payload = archive.read("base/files/payload.bin")
        unstaged_patch = archive.read("changes/unstaged.patch")
        execution_log = archive.read("logs/execution.log")
        bundled_new_file = archive.read("untracked/nested/new.bin")
        bundled_starts = archive.read("untracked/entrypoint-starts.txt")

    assert committed_payload == b"old"
    assert unstaged_patch
    assert b"stdout-line\n" in execution_log
    assert b"stderr-line\n" in execution_log
    assert bundled_new_file == b"\x10nested\x00"
    assert bundled_starts.decode("utf-8").splitlines() == ["1"]
    assert "untracked/entrypoint-cwd.txt" in names
    assert f"untracked/{entrypoint_name}" not in names


@pytest.mark.parametrize("force_plain", (False, True))
def test_apply_noninteractive_output_is_sanitized_while_log_remains_raw(
    tmp_path: Path,
    force_plain: bool,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "visible-output.zip"
    raw_output = b"visible-\x1b[31mred\x1b[0m-\x08safe\n"
    entrypoint_name = native_value("run.sh", "run.ps1")
    manifest = _manifest(context)
    manifest["entrypoint"] = entrypoint_name
    entrypoint = native_script(
        "printf 'visible-\\033[31mred\\033[0m-\\010safe\\n'",
        "$bytes = [byte[]]("
        "0x76,0x69,0x73,0x69,0x62,0x6C,0x65,0x2D,"
        "0x1B,0x5B,0x33,0x31,0x6D,0x72,0x65,0x64,"
        "0x1B,0x5B,0x30,0x6D,0x2D,0x08,0x73,0x61,0x66,0x65,0x0A)\n"
        "$stream = [Console]::OpenStandardOutput()\n"
        "$stream.Write($bytes, 0, $bytes.Length)\n"
        "$stream.Flush()",
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

    output_directory = tmp_path / "results"
    arguments = ["apply"]
    if force_plain:
        arguments.append("--plain")
    arguments.extend(("--output-dir", str(output_directory), str(package)))

    completed = run_cli(
        tmp_path,
        *arguments,
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == 0
    assert "visible-red-safe\n" in completed.stdout
    assert "\x1b" not in completed.stdout
    assert "\x08" not in completed.stdout
    assert completed.stderr == ""
    bundles = tuple(output_directory.glob("patchharbor_result_*.zip"))
    assert len(bundles) == 1
    with zipfile.ZipFile(bundles[0]) as archive:
        assert archive.read("logs/execution.log") == raw_output


def test_apply_returns_exact_nonzero_exit_and_bundles_execution_log(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "nonzero.zip"
    _write_execution_package(
        package,
        context,
        native_script(
            "printf 'entrypoint-output\\n'\nexit 23",
            "[Console]::Out.WriteLine('entrypoint-output')\nexit 23",
        ),
    )
    output_directory = tmp_path / "results"
    caller = tmp_path / "caller"
    caller.mkdir()

    completed = run_cli(
        caller,
        "apply",
        "--json",
        "--output-dir",
        str(output_directory),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == 23
    envelope = json.loads(completed.stdout)
    assert envelope["success"] is False
    assert envelope["error"] is None
    assert envelope["process_exit_code"] == 23
    result = envelope["result"]
    assert result["primary_result"] == {
        "kind": "entrypoint_exit",
        "entrypoint_started": True,
        "entrypoint_exit_code": 23,
        "timed_out": False,
        "interrupted": False,
        "patchharbor_error_code": None,
    }
    bundle_path = Path(result["result_bundle"]["path"])
    with zipfile.ZipFile(bundle_path) as archive:
        execution_log = archive.read("logs/execution.log")
        run_report = json.loads(archive.read("logs/run.json"))

    assert execution_log == b"entrypoint-output\n"
    assert run_report["primary_result"]["kind"] == "entrypoint_exit"
    assert run_report["primary_result"]["entrypoint_exit_code"] == 23
    assert run_report["process_exit_code"] == 23


def test_apply_timeout_bundles_output_and_exit_code(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "timeout.zip"
    _write_execution_package(
        package,
        context,
        native_script(
            "printf 'entrypoint-output\\n'\nsleep 60",
            "[Console]::Out.WriteLine('entrypoint-output')\n"
            "Start-Sleep -Seconds 60",
        ),
    )
    output_directory = tmp_path / "results"
    caller = tmp_path / "caller"
    caller.mkdir()

    completed = run_cli(
        caller,
        "apply",
        "--json",
        "--timeout",
        "1.0",
        "--output-dir",
        str(output_directory),
        str(package),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == int(ExitCode.TIMEOUT)
    envelope = json.loads(completed.stdout)
    assert envelope["process_exit_code"] == int(ExitCode.TIMEOUT)
    result = envelope["result"]
    assert result["primary_result"] == {
        "kind": "timeout",
        "entrypoint_started": True,
        "entrypoint_exit_code": None,
        "timed_out": True,
        "interrupted": False,
        "patchharbor_error_code": int(ExitCode.TIMEOUT),
    }
    bundle_path = Path(result["result_bundle"]["path"])
    with zipfile.ZipFile(bundle_path) as archive:
        execution_log = archive.read("logs/execution.log")
        run_report = json.loads(archive.read("logs/run.json"))

    assert execution_log == b"entrypoint-output\n"
    assert run_report["primary_result"]["kind"] == "timeout"
    assert run_report["primary_result"]["timed_out"] is True
    assert run_report["process_exit_code"] == int(ExitCode.TIMEOUT)


def test_apply_interrupt_bundles_output_and_exit_code(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "interrupt.zip"
    _write_execution_package(
        package,
        context,
        native_script(
            "printf 'entrypoint-output\\nentrypoint-ready\\n'\nsleep 60",
            "[Console]::Out.WriteLine('entrypoint-output')\n"
            "[Console]::Out.WriteLine('entrypoint-ready')\n"
            "Start-Sleep -Seconds 60",
        ),
    )
    output_directory = tmp_path / "results"
    report_path = tmp_path / "interrupt-report.json"
    runner_path = tmp_path / "interrupt-apply.py"
    runner_path.write_text(
        """\
from __future__ import annotations
import _thread
import io
import json
from pathlib import Path
import sys
import threading

from patchharbor.application import apply_patch_package, resolve_patch_package
from patchharbor.errors import PatchHarborError
from patchharbor.output import OutputTargets
from patchharbor.run_report import RunReport

package = Path(sys.argv[1])
output_directory = Path(sys.argv[2])
report_path = Path(sys.argv[3])
interrupt_requested = threading.Event()


def interrupt_on_ready(lines: tuple[str, ...], _discarded: int) -> None:
    if interrupt_requested.is_set():
        return
    if any(line.rstrip("\\r\\n") == "entrypoint-ready" for line in lines):
        interrupt_requested.set()
        _thread.interrupt_main()


try:
    report = apply_patch_package(
        resolve_patch_package(package),
        output_directory=output_directory,
        timeout_seconds=30,
        output=OutputTargets(
            visible_text_stream=io.StringIO(),
            line_observer=interrupt_on_ready,
        ),
    )
except PatchHarborError as error:
    report = error.run_report
    if not isinstance(report, RunReport):
        raise
    report_path.write_text(
        json.dumps(
            {
                "process_exit_code": report.process_exit_code,
                "result": report.apply_result(),
            }
        ),
        encoding="utf-8",
    )
    raise SystemExit(report.process_exit_code)
report_path.write_text(
    json.dumps(
        {
            "process_exit_code": report.process_exit_code,
            "result": report.apply_result(),
        }
    ),
    encoding="utf-8",
)
raise SystemExit(report.process_exit_code)
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(runner_path),
            str(package),
            str(output_directory),
            str(report_path),
        ],
        cwd=tmp_path,
        env=project_environment(environment),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == int(ExitCode.INTERRUPTED)
    completion = json.loads(report_path.read_text(encoding="utf-8"))
    assert completion["process_exit_code"] == int(ExitCode.INTERRUPTED)
    result = completion["result"]
    assert result["primary_result"] == {
        "kind": "interrupted",
        "entrypoint_started": True,
        "entrypoint_exit_code": None,
        "timed_out": False,
        "interrupted": True,
        "patchharbor_error_code": int(ExitCode.INTERRUPTED),
    }
    bundle_path = Path(result["result_bundle"]["path"])
    with zipfile.ZipFile(bundle_path) as archive:
        execution_log = archive.read("logs/execution.log")
        run_report = json.loads(archive.read("logs/run.json"))

    assert execution_log == b"entrypoint-output\nentrypoint-ready\n"
    assert run_report["primary_result"]["kind"] == "interrupted"
    assert run_report["primary_result"]["interrupted"] is True
    assert run_report["process_exit_code"] == int(ExitCode.INTERRUPTED)


def test_dry_run_json_publishes_unchanged_snapshot_without_execution(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "patch.zip"
    _write_package(package, _manifest(context))
    output_directory = tmp_path / "results"
    before = _repository_files(repository)

    completed = _run_dry_run(
        package,
        tmp_path / "caller",
        environment,
        json_output=True,
        output_directory=output_directory,
    )

    assert completed.returncode == 0
    envelope = json.loads(completed.stdout)
    assert set(envelope) == {
        "output_version",
        "command",
        "success",
        "result",
        "error",
        "process_exit_code",
    }
    assert envelope["command"] == "apply"
    assert envelope["success"] is True
    assert envelope["error"] is None
    assert envelope["process_exit_code"] == 0
    result = envelope["result"]
    assert isinstance(result, dict)
    assert result["repository_resolved"] is True
    assert result["repo_id"] == context["repo_id"]
    assert result["repository_path"] == str(repository.resolve())
    assert result["primary_result"] == {
        "kind": "dry_run_success",
        "entrypoint_started": False,
        "entrypoint_exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "patchharbor_error_code": None,
    }
    bundle_result = result["result_bundle"]
    assert bundle_result["attempted"] is True
    assert bundle_result["status"] == "created"
    assert bundle_result["emergency_diagnostics_path"] is None
    bundle_path = Path(bundle_result["path"])
    assert bundle_path.parent == output_directory.resolve()
    assert bundle_path.is_file()
    assert not tuple(output_directory.glob(".*.tmp"))

    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        result_manifest = json.loads(archive.read("manifest.json"))
        actual_context = json.loads(archive.read("context.json"))
        run_report = json.loads(archive.read("logs/run.json"))

    assert "logs/execution.log" not in names
    assert result_manifest["dry_run"] is True
    assert result_manifest["entrypoint_started"] is False
    assert result_manifest["execution_present"] is False
    assert result_manifest["primary_result"] == "dry_run_success"
    assert result_manifest["result_bundle_status"] == "created"
    assert actual_context["repo_id"] == context["repo_id"]
    assert actual_context["base_commit"] == context["base_commit"]
    assert actual_context["state_fingerprint"] == context["state_fingerprint"]
    assert run_report["dry_run"] is True
    assert run_report["execution_present"] is False
    assert run_report["primary_result"] == {
        "kind": "dry_run_success",
        "success": True,
        "patchharbor_error_code": None,
        "entrypoint_started": False,
        "entrypoint_exit_code": None,
        "timed_out": False,
        "interrupted": False,
    }
    assert run_report["result_bundle"] == {
        "attempted": True,
        "status": "created",
        "error": None,
    }
    assert run_report["process_exit_code"] == 0
    assert (
        result["run_id"]
        == result_manifest["run_id"]
        == run_report["run_id"]
    )
    assert (
        result["primary_result"]["kind"]
        == result_manifest["primary_result"]
        == run_report["primary_result"]["kind"]
    )
    assert (
        result["result_bundle"]["status"]
        == result_manifest["result_bundle_status"]
        == run_report["result_bundle"]["status"]
    )
    assert _repository_files(repository) == before
    _assert_repository_unmodified(repository)


def test_matching_manifest_resolves_exact_registered_repository_without_mutation(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "patch.zip"
    _write_package(package, _manifest(context))

    completed = _run_dry_run(package, tmp_path / "caller", environment)

    assert completed.returncode == 0
    _assert_repository_unmodified(repository)


def test_unknown_repository_id_is_rejected_before_snapshot(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    manifest = _manifest(context)
    manifest["repo_id"] = str(uuid4())
    package = tmp_path / "unknown.zip"
    _write_package(package, manifest)

    completed = _run_dry_run(
        package,
        tmp_path / "caller",
        environment,
        json_output=True,
    )

    assert completed.returncode == int(ExitCode.REPOSITORY_ERROR)
    envelope = json.loads(completed.stdout)
    result = envelope["result"]
    assert result["repository_resolved"] is False
    assert result["repo_id"] is None
    assert result["repository_path"] is None
    assert result["primary_result"] == {
        "kind": "repository_error",
        "entrypoint_started": False,
        "entrypoint_exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "patchharbor_error_code": int(ExitCode.REPOSITORY_ERROR),
    }
    assert result["result_bundle"] == {
        "attempted": False,
        "status": "not_attempted",
        "path": None,
        "emergency_diagnostics_path": None,
    }
    assert envelope["error"]["patchharbor_error_code"] == int(
        ExitCode.REPOSITORY_ERROR
    )
    assert _result_bundles(environment) == ()
    _assert_repository_unmodified(repository)


@pytest.mark.parametrize(
    "local_conflict",
    ("different-id", "missing-exclude", "tracked-reserved-path"),
)
def test_local_repository_identity_conflict_is_rejected_before_snapshot(
    tmp_path: Path,
    local_conflict: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / f"{local_conflict}.zip"
    _write_package(package, _manifest(context))

    if local_conflict == "different-id":
        (repository / ".patchharbor" / "id").write_text(
            f"{uuid4()}\n",
            encoding="ascii",
        )
    elif local_conflict == "missing-exclude":
        exclude = local_exclude_path(repository)
        lines = exclude.read_bytes().splitlines(keepends=True)
        exclude.write_bytes(
            b"".join(
                line
                for line in lines
                if line.rstrip(b"\r\n") != b".patchharbor/"
            )
        )
    else:
        git(repository, "add", "-f", ".patchharbor/id")

    completed = _run_dry_run(package, tmp_path / "caller", environment)

    assert completed.returncode == int(ExitCode.REPOSITORY_ERROR)
    assert _result_bundles(environment) == ()
    _assert_repository_unmodified(repository)


@pytest.mark.parametrize(
    "mismatch",
    ("base-commit", "object-format", "fingerprint"),
)
def test_state_mismatch_returns_nine_and_bundles_actual_repository_state(
    tmp_path: Path,
    mismatch: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    manifest = _manifest(context)
    if mismatch == "base-commit":
        manifest["base_commit"] = _different_hex(str(context["base_commit"]))
    elif mismatch == "object-format":
        manifest["base_commit"] = "a" * 64
    else:
        manifest["state_fingerprint"] = _different_hex(
            str(context["state_fingerprint"])
        )
    package = tmp_path / f"{mismatch}.zip"
    _write_package(package, manifest)

    completed = _run_dry_run(
        package,
        tmp_path / "caller",
        environment,
        json_output=True,
    )

    assert completed.returncode == int(ExitCode.STATE_MISMATCH)
    envelope = json.loads(completed.stdout)
    assert envelope["command"] == "apply"
    assert envelope["success"] is False
    assert envelope["process_exit_code"] == int(ExitCode.STATE_MISMATCH)
    assert envelope["result"]["primary_result"]["kind"] == "state_mismatch"
    assert envelope["result"]["result_bundle"]["status"] == "created"
    assert envelope["error"]["patchharbor_error_code"] == int(
        ExitCode.STATE_MISMATCH
    )
    _assert_repository_unmodified(repository)
    bundles = _result_bundles(environment)
    assert len(bundles) == 1

    with zipfile.ZipFile(bundles[0]) as archive:
        names = set(archive.namelist())
        result_manifest = json.loads(archive.read("manifest.json"))
        actual_context = json.loads(archive.read("context.json"))
        run_report = json.loads(archive.read("logs/run.json"))

    assert "logs/execution.log" not in names
    assert actual_context["repo_id"] == context["repo_id"]
    assert actual_context["base_commit"] == context["base_commit"]
    assert actual_context["state_fingerprint"] == context["state_fingerprint"]
    assert actual_context["fingerprint_algorithm"] == FINGERPRINT_ALGORITHM
    assert result_manifest["expected_base_commit"] == manifest["base_commit"]
    assert result_manifest["actual_base_commit"] == context["base_commit"]
    assert (
        result_manifest["expected_state_fingerprint"]
        == manifest["state_fingerprint"]
    )
    assert (
        result_manifest["actual_state_fingerprint"]
        == context["state_fingerprint"]
    )
    assert (
        result_manifest["expected_fingerprint_algorithm"]
        == manifest["fingerprint_algorithm"]
    )
    assert (
        result_manifest["actual_fingerprint_algorithm"]
        == FINGERPRINT_ALGORITHM
    )
    assert run_report["operation"] == "apply"
    assert run_report["dry_run"] is True
    assert run_report["repository_resolved"] is True
    assert run_report["primary_result"] == {
        "kind": "state_mismatch",
        "success": False,
        "patchharbor_error_code": int(ExitCode.STATE_MISMATCH),
        "entrypoint_started": False,
        "entrypoint_exit_code": None,
        "timed_out": False,
        "interrupted": False,
    }
    assert run_report["result_bundle"] == {
        "attempted": True,
        "status": "created",
        "error": None,
    }
    assert run_report["process_exit_code"] == int(ExitCode.STATE_MISMATCH)
    assert (
        envelope["result"]["run_id"]
        == result_manifest["run_id"]
        == run_report["run_id"]
    )
    assert (
        envelope["result"]["primary_result"]["kind"]
        == result_manifest["primary_result"]
        == run_report["primary_result"]["kind"]
    )
    assert (
        envelope["result"]["result_bundle"]["status"]
        == result_manifest["result_bundle_status"]
        == run_report["result_bundle"]["status"]
    )


def test_state_mismatch_uses_physically_resolved_output_directory(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    manifest = _manifest(context)
    manifest["state_fingerprint"] = _different_hex(
        str(context["state_fingerprint"])
    )
    package = tmp_path / "mismatch.zip"
    _write_package(package, manifest)
    physical_output = tmp_path / "physical-results"
    physical_output.mkdir()
    requested_output = physical_output
    if os.name != "nt":
        requested_output = tmp_path / "result-link"
        requested_output.symlink_to(
            physical_output,
            target_is_directory=True,
        )
    caller = tmp_path / "caller"
    caller.mkdir()

    completed = run_cli(
        caller,
        "apply",
        "--dry-run",
        "--output-dir",
        str(requested_output),
        str(package),
        environment_overrides=environment,
    )

    assert completed.returncode == int(ExitCode.STATE_MISMATCH)
    assert len(tuple(physical_output.glob("patchharbor_result_*.zip"))) == 1
    assert not tuple(physical_output.glob(".*.tmp"))
    assert _result_bundles(environment) == ()
    _assert_repository_unmodified(repository)


def test_busy_repository_is_rejected_before_safe_resolution(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _register_context(repository, tmp_path / "user")
    package = tmp_path / "busy.zip"
    _write_package(package, _manifest(context))
    holder = start_repository_lock_holder(
        str(context["repo_id"]),
        environment=project_environment(environment),
    )
    try:
        completed = _run_dry_run(package, tmp_path / "caller", environment)
    finally:
        try:
            assert release_repository_lock_holder(holder) == 0
        finally:
            stop_repository_lock_holder(holder)

    assert completed.returncode == int(ExitCode.REPOSITORY_BUSY)
    assert _result_bundles(environment) == ()
    _assert_repository_unmodified(repository)


def test_repo_id_is_the_only_repository_selection_key(
    tmp_path: Path,
) -> None:
    left_parent = tmp_path / "left"
    right_parent = tmp_path / "right"
    left_parent.mkdir()
    right_parent.mkdir()
    first = create_repository(left_parent / "project")
    second = create_repository(right_parent / "project")
    for repository in (first, second):
        git(repository, "branch", "-M", "shared")
        git(
            repository,
            "remote",
            "add",
            "origin",
            "https://example.invalid/shared.git",
        )

    user_root = tmp_path / "user"
    environment, first_context = _register_context(first, user_root)
    _same_environment, second_context = _register_context(second, user_root)
    package = tmp_path / "project.zip"
    _write_package(package, _manifest(second_context))
    holder = start_repository_lock_holder(
        str(second_context["repo_id"]),
        environment=project_environment(environment),
    )
    try:
        completed = _run_dry_run(package, first, environment)
    finally:
        try:
            assert release_repository_lock_holder(holder) == 0
        finally:
            stop_repository_lock_holder(holder)

    assert completed.returncode == int(ExitCode.REPOSITORY_BUSY)
    assert probe_repository_lock(
        str(first_context["repo_id"]),
        project_environment(environment),
    ) == 0
    _assert_repository_unmodified(first)
    _assert_repository_unmodified(second)
