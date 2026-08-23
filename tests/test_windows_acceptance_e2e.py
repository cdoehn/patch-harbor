from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import zipfile

import pytest

from patchharbor.errors import ExitCode
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from tests.platform_support import (
    assert_child_process_stopped,
    cleanup_test_processes,
    normalized_path,
    project_environment,
    run_cli,
    wait_for_child_pid,
)
from tests.registration_support import (
    create_repository,
    isolated_user_environment,
    local_exclude_path,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
)


pytestmark = pytest.mark.platform

if os.name != "nt":
    pytest.skip(
        "requires native Windows filesystem and process behavior",
        allow_module_level=True,
    )

_ENGINE_ENVIRONMENT = "PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE"
_UTF8_GREETING = "Gr\u00fc\u00dfe"


def _selected_engine() -> tuple[str, str]:
    engine = os.environ.get(_ENGINE_ENVIRONMENT, "powershell.exe")
    if engine == "powershell.exe":
        return "#!powershell.exe", "Desktop"
    if engine == "pwsh":
        return "#!pwsh", "Core"
    raise AssertionError(f"unsupported Windows acceptance engine: {engine}")


def _isolated_environment(root: Path) -> dict[str, str]:
    environment = isolated_user_environment(root)
    system_temp = root / "system-temp"
    system_temp.mkdir(parents=True)
    environment.update(
        {name: str(system_temp) for name in ("TMPDIR", "TEMP", "TMP")}
    )
    return environment


def _register_context(
    repository: Path,
    environment: dict[str, str],
) -> dict[str, object]:
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
        timeout_seconds=120,
    )
    assert registered.returncode == 0

    completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
        timeout_seconds=120,
    )
    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    result = document["result"]
    assert isinstance(result, dict)
    return result


def _manifest(context: dict[str, object], entrypoint: str) -> dict[str, object]:
    return {
        "marker": PATCH_MARKER,
        "format_version": PATCH_FORMAT_VERSION,
        "repo_id": context["repo_id"],
        "base_commit": context["base_commit"],
        "state_fingerprint": context["state_fingerprint"],
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "entrypoint": entrypoint,
    }


def _write_apply_package(
    package: Path,
    context: dict[str, object],
    script: str,
) -> None:
    entrypoint = "entrypoint.data"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(
                _manifest(context, entrypoint),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(entrypoint, script.encode("utf-8"))
        archive.writestr("nested/payload.bin", b"\x00windows-payload\xff")


def _create_directory_junction(link: Path, target: Path) -> None:
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip("native Windows junction creation is unavailable")


def _process_tree_script(
    child_ready: Path,
    grandchild_ready: Path,
) -> str:
    shebang, _edition = _selected_engine()
    child_path = str(child_ready).replace("'", "''")
    grandchild_path = str(grandchild_ready).replace("'", "''")
    sleeper = base64.b64encode(
        "Start-Sleep -Seconds 60".encode("utf-16-le")
    ).decode("ascii")
    child_body = (
        "$engine = (Get-Process -Id $PID).Path; "
        "$grandchild = Start-Process -FilePath $engine "
        "-ArgumentList '-NoLogo','-NoProfile','-NonInteractive',"
        f"'-EncodedCommand','{sleeper}' -PassThru; "
        "[System.IO.File]::WriteAllText("
        f"'{grandchild_path}', [string]$grandchild.Id); "
        "Wait-Process -Id $grandchild.Id"
    )
    encoded_child = base64.b64encode(
        child_body.encode("utf-16-le")
    ).decode("ascii")
    return (
        f"{shebang}\n"
        "# PATCHHARBOR\n"
        "$engine = (Get-Process -Id $PID).Path\n"
        "$child = Start-Process -FilePath $engine "
        "-ArgumentList '-NoLogo','-NoProfile','-NonInteractive',"
        f"'-EncodedCommand','{encoded_child}' -PassThru\n"
        "[System.IO.File]::WriteAllText("
        f"'{child_path}', [string]$child.Id)\n"
        "$deadline = [DateTime]::UtcNow.AddSeconds(10)\n"
        f"while ((-not (Test-Path -LiteralPath '{grandchild_path}')) "
        "-and ([DateTime]::UtcNow -lt $deadline)) { "
        "Start-Sleep -Milliseconds 20 }\n"
        f"if (-not (Test-Path -LiteralPath '{grandchild_path}')) "
        "{ exit 91 }\n"
        "[Console]::Out.WriteLine('tree-ready')\n"
        "Wait-Process -Id $child.Id\n"
    )


def test_windows_user_paths_json_and_repository_lock_are_native(
    tmp_path: Path,
) -> None:
    environment = _isolated_environment(tmp_path / "benutzer-ä")
    repository = create_repository(tmp_path / "repository-ä")
    context = _register_context(repository, environment)

    configuration = Path(environment["APPDATA"]) / "PatchHarbor"
    state = Path(environment["LOCALAPPDATA"]) / "PatchHarbor"
    assert (configuration / "registry.json").is_file()
    assert (state / "locks").is_dir()
    assert normalized_path(context["repository_path"]) == normalized_path(
        repository
    )
    assert ".patchharbor/" in local_exclude_path(repository).read_text(
        encoding="utf-8"
    ).splitlines()

    holder = start_repository_lock_holder(
        str(context["repo_id"]),
        environment=project_environment(environment),
    )
    try:
        busy = run_cli(
            repository,
            "context",
            "--json",
            environment_overrides=environment,
            timeout_seconds=120,
        )
        assert busy.returncode == int(ExitCode.REPOSITORY_BUSY)
        assert json.loads(busy.stdout)["process_exit_code"] == int(
            ExitCode.REPOSITORY_BUSY
        )
        assert release_repository_lock_holder(holder) == 0
    finally:
        stop_repository_lock_holder(holder)

    bundled = run_cli(
        repository,
        "bundle",
        "--json",
        environment_overrides=environment,
        timeout_seconds=120,
    )
    assert bundled.returncode == 0
    bundle_document = json.loads(bundled.stdout)
    bundle_path = Path(bundle_document["result"]["result_bundle_path"])
    assert bundle_path.parent.resolve() == (state / "results").resolve()
    assert bundle_path.is_file()


def test_windows_junction_is_rejected_at_repository_boundary(
    tmp_path: Path,
) -> None:
    environment = _isolated_environment(tmp_path / "user")
    repository = create_repository(tmp_path / "repository")
    junction_target = tmp_path / "junction-target"
    junction_target.mkdir()
    _create_directory_junction(repository / ".patchharbor", junction_target)

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
        timeout_seconds=120,
    )
    assert completed.returncode == int(ExitCode.REPOSITORY_ERROR)


def test_windows_powershell_engine_uses_fixed_noninteractive_contract(
    tmp_path: Path,
) -> None:
    shebang, expected_edition = _selected_engine()
    environment = _isolated_environment(tmp_path / "user")
    probe_path = tmp_path / "engine-probe.json"
    escaped_probe = str(probe_path).replace("'", "''")
    source = tmp_path / "engine.data"
    source.write_bytes(
        (
            f"{shebang}\n"
            "# PATCHHARBOR\n"
            "$probe = [ordered]@{\n"
            "  edition = [string]$PSVersionTable.PSEdition\n"
            "  command_line = [Environment]::CommandLine\n"
            "  stdin_length = [Console]::In.ReadToEnd().Length\n"
            "  script_path = $PSCommandPath\n"
            "}\n"
            "$json = $probe | ConvertTo-Json -Compress\n"
            "[System.IO.File]::WriteAllText("
            f"'{escaped_probe}', $json, [Text.UTF8Encoding]::new($false))\n"
            f"[Console]::Out.WriteLine('{_UTF8_GREETING}')\n"
        ).encode("utf-8")
    )

    completed = run_cli(
        tmp_path,
        "fs",
        "run",
        "--plain",
        str(source),
        environment_overrides=environment,
        timeout_seconds=120,
    )

    assert completed.returncode == 0
    assert _UTF8_GREETING in completed.stdout.splitlines()
    assert "\ufffd" not in completed.stdout
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    command_line = probe["command_line"].casefold()
    assert probe["edition"] == expected_edition
    assert probe["stdin_length"] == 0
    for argument in ("-nologo", "-noprofile", "-noninteractive", "-file"):
        assert argument in command_line
    assert "-executionpolicy" not in command_line
    assert "bypass" not in command_line
    private_script = Path(probe["script_path"])
    assert private_script.suffix.casefold() == ".ps1"
    assert not private_script.exists()
    assert normalized_path(private_script.parent.parent) == normalized_path(
        environment["TEMP"]
    )


def test_windows_apply_json_is_utf8_and_execution_log_remains_raw(
    tmp_path: Path,
) -> None:
    shebang, _expected_edition = _selected_engine()
    environment = _isolated_environment(tmp_path / "benutzer-ä")
    repository = create_repository(tmp_path / "repository-ä")
    context = _register_context(repository, environment)
    package = tmp_path / "windows-apply.zip"
    _write_apply_package(
        package,
        context,
        (
            f"{shebang}\n"
            "# PATCHHARBOR\n"
            f"[Console]::Out.WriteLine('{_UTF8_GREETING}-raw')\n"
            "[System.IO.File]::WriteAllText("
            "'applied.txt', 'applied', [Text.UTF8Encoding]::new($false))\n"
        ),
    )
    output_directory = tmp_path / "resultate-ä"

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

    assert completed.returncode == 0
    assert f"{_UTF8_GREETING}-raw" not in completed.stdout
    document = json.loads(completed.stdout)
    result = document["result"]
    assert normalized_path(result["repository_path"]) == normalized_path(
        repository
    )
    bundle_path = Path(result["result_bundle"]["path"])
    assert normalized_path(bundle_path.parent) == normalized_path(
        output_directory
    )
    assert (repository / "nested" / "payload.bin").read_bytes() == (
        b"\x00windows-payload\xff"
    )
    assert (repository / "applied.txt").read_text(encoding="utf-8") == "applied"
    with zipfile.ZipFile(bundle_path) as archive:
        assert archive.read("logs/execution.log") == (
            f"{_UTF8_GREETING}-raw\r\n".encode("utf-8")
        )


def test_windows_job_object_stops_descendants_on_timeout_and_break(
    tmp_path: Path,
) -> None:
    environment = _isolated_environment(tmp_path / "user")

    timeout_child = tmp_path / "timeout-child.pid"
    timeout_grandchild = tmp_path / "timeout-grandchild.pid"
    timeout_script = tmp_path / "timeout.data"
    timeout_script.write_bytes(
        _process_tree_script(timeout_child, timeout_grandchild).encode("utf-8")
    )
    timed_out = run_cli(
        tmp_path,
        "fs",
        "run",
        "--timeout",
        "5.0",
        str(timeout_script),
        environment_overrides=environment,
        timeout_seconds=120,
    )
    timeout_child_pid = wait_for_child_pid(timeout_child)
    timeout_grandchild_pid = wait_for_child_pid(timeout_grandchild)
    try:
        assert timed_out.returncode == int(ExitCode.TIMEOUT)
        assert_child_process_stopped(timeout_child_pid)
        assert_child_process_stopped(timeout_grandchild_pid)
    finally:
        cleanup_test_processes(timeout_child_pid, timeout_grandchild_pid)

    break_child = tmp_path / "break-child.pid"
    break_grandchild = tmp_path / "break-grandchild.pid"
    break_script = tmp_path / "break.data"
    break_script.write_bytes(
        _process_tree_script(break_child, break_grandchild).encode("utf-8")
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "patchharbor.cli",
            "fs",
            "run",
            "--timeout",
            "30",
            str(break_script),
        ],
        cwd=tmp_path,
        env=project_environment(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="strict",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    break_child_pid: int | None = None
    break_grandchild_pid: int | None = None
    try:
        break_child_pid = wait_for_child_pid(break_child, timeout=10)
        break_grandchild_pid = wait_for_child_pid(break_grandchild, timeout=10)
        process.send_signal(signal.CTRL_BREAK_EVENT)
        process.communicate(timeout=30)
        assert process.returncode == int(ExitCode.INTERRUPTED)
        assert_child_process_stopped(break_child_pid)
        assert_child_process_stopped(break_grandchild_pid)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        cleanup_test_processes(break_child_pid, break_grandchild_pid)
