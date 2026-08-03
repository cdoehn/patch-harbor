from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

import pytest

from tests.platform_support import (
    REQUIRED_MARKER,
    log_path_from_stderr as _log_path_from_stderr,
    project_environment,
    run_cli as _run_cli,
    run_cli_bytes as _run_cli_bytes,
)


pytestmark = pytest.mark.e2e


def _run_patchharbor(
    script_path: Path,
    cwd: Path,
    *run_arguments: str,
    environment_overrides: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run_cli(
        cwd,
        "fs",
        "run",
        *run_arguments,
        str(script_path),
        environment_overrides=environment_overrides,
        input_text=input_text,
    )


def _child_process_script(ready_path: Path, *, exit_parent: bool = False) -> str:
    if os.name == "nt":
        encoded_command = (
            "UwB0AGEAcgB0AC0AUwBsAGUAZQBwACAALQBTAGUAYwBvAG4AZABzACAANgAwAA=="
        )
        parent_tail = "exit 0" if exit_parent else "Wait-Process -Id $child.Id"
        escaped_ready = str(ready_path).replace("'", "''")
        return (
            f"{REQUIRED_MARKER}\n"
            "$child = Start-Process "
            "-FilePath (Join-Path $PSHOME 'powershell.exe') "
            "-ArgumentList '-NoLogo','-NoProfile','-NonInteractive',"
            f"'-EncodedCommand','{encoded_command}' -PassThru\n"
            f"Set-Content -LiteralPath '{escaped_ready}' "
            "-Value $child.Id -NoNewline\n"
            f"{parent_tail}\n"
        )

    parent_tail = "exit 0" if exit_parent else 'wait "$child_pid"'
    return (
        f"{REQUIRED_MARKER}\n"
        "sleep 60 &\n"
        "child_pid=$!\n"
        f"printf '%s' \"$child_pid\" > \"{ready_path}\"\n"
        f"{parent_tail}\n"
    )


def _wait_for_child_pid(ready_path: Path, *, timeout: float = 5.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ready_path.exists():
            value = ready_path.read_text(encoding="utf-8").strip()
            if value:
                return int(value)
        time.sleep(0.02)
    raise AssertionError(f"child PID was not written to {ready_path}")


def _pid_is_running(pid: int) -> bool:
    if os.name != "nt":
        stat_path = Path(f"/proc/{pid}/stat")
        try:
            fields = stat_path.read_text(encoding="utf-8").split()
        except FileNotFoundError:
            return False
        if len(fields) > 2 and fields[2] == "Z":
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _kill_test_pid(pid: int) -> None:
    if not _pid_is_running(pid):
        return
    if os.name != "nt":
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
        return

    import ctypes
    from ctypes import wintypes

    process_terminate = 0x0001
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_terminate, False, pid)
    if handle:
        try:
            kernel32.TerminateProcess(handle, 1)
        finally:
            kernel32.CloseHandle(handle)


def _assert_child_process_stopped(pid: int, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_is_running(pid):
            return
        time.sleep(0.05)
    _kill_test_pid(pid)
    raise AssertionError(f"child process {pid} survived PatchHarbor")


def test_fs_run_rejects_empty_standard_input(tmp_path: Path) -> None:
    completed = _run_cli(tmp_path, "fs", "run")

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == "patchharbor: no script input received\n"


def test_fs_run_help_is_limited_to_public_arguments(tmp_path: Path) -> None:
    completed = _run_cli(tmp_path, "fs", "run", "--help")

    assert completed.returncode == 0
    help_text = " ".join(completed.stdout.split())
    assert (
        "Run Bash or PowerShell scripts from a file, ZIP PatchBundle, "
        "directory, or standard input."
    ) in help_text
    assert (
        "Oversized inputs and unsafe ZIP PatchBundles are rejected "
        "before any script starts."
    ) in help_text
    assert "--timeout SECONDS" in completed.stdout
    assert "default: 300" in completed.stdout
    assert "--plain" in completed.stdout
    assert "--no-color" in completed.stdout
    assert "--log" in completed.stdout


def _script_path(tmp_path: Path, stem: str) -> Path:
    return tmp_path / (f"{stem}.ps1" if os.name == "nt" else f"{stem}.sh")


def test_fs_run_honors_a_supported_platform_shebang(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "explicit-interpreter.txt"
    if os.name == "nt":
        shebang = "#!powershell.exe"
        script_body = 'Write-Output "explicit-interpreter"\n'
    else:
        shebang = "#!/usr/bin/env bash"
        script_body = 'printf "%s\\n" "explicit-interpreter"\n'
    script_path.write_text(
        f"{shebang}\n{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "explicit-interpreter\n"
    assert completed.stderr == ""


def test_fs_run_rejects_unknown_shebang_before_execution(
    tmp_path: Path,
) -> None:
    sentinel_path = tmp_path / "must-not-exist"
    script_path = tmp_path / "unknown-interpreter.txt"
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        f"{REQUIRED_MARKER}\n"
        f'open({str(sentinel_path)!r}, "w").write("executed")\n',
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 5
    assert completed.stdout == ""
    assert completed.stderr == (
        "patchharbor: unsupported script interpreter in shebang: "
        "/usr/bin/env python3\n"
    )
    assert not sentinel_path.exists()


def test_fs_run_executes_a_real_script_file_with_required_marker(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "hello")
    if os.name == "nt":
        script_body = 'Write-Output "patchharbor-e2e"\n'
    else:
        script_body = 'printf "%s\\n" "patchharbor-e2e"\n'
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "patchharbor-e2e\n"
    assert completed.stderr == ""


def test_fs_run_rejects_script_without_required_marker(tmp_path: Path) -> None:
    sentinel_path = tmp_path / "must-not-exist"
    script_path = _script_path(tmp_path, "missing-marker")
    if os.name == "nt":
        script_body = f'Set-Content -Path "{sentinel_path}" -Value "executed"\n'
    else:
        script_body = f'printf executed > "{sentinel_path}"\n'
    script_path.write_text(script_body, encoding="utf-8")

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 3
    assert completed.stdout == ""
    assert completed.stderr == (
        "patchharbor: missing required marker line: # PATCHHARBOR\n"
    )
    assert not sentinel_path.exists()


def test_message_line_does_not_replace_required_marker(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "message")
    script_path.write_text("# PATCHHARBOR MESSAGE note\n", encoding="utf-8")

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 3
    assert "missing required marker line" in completed.stderr


def test_script_runs_in_the_original_working_directory(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "cwd")
    if os.name == "nt":
        script_body = "Write-Output (Get-Location).Path\n"
    else:
        script_body = "pwd\n"
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert Path(completed.stdout.strip()).resolve() == tmp_path.resolve()


def test_child_stdin_is_closed(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "stdin")
    if os.name == "nt":
        script_body = (
            "$value = [Console]::In.ReadLine()\n"
            'if ($null -eq $value) { Write-Output "closed"; exit 0 }\n'
            "exit 19\n"
        )
    else:
        script_body = (
            'if read -r value; then exit 19; fi\n'
            'printf "%s\\n" "closed"\n'
        )
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "closed\n"


def test_temporary_script_is_removed_after_execution(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "temporary-path")
    if os.name == "nt":
        script_body = "Write-Output $PSCommandPath\n"
    else:
        script_body = 'printf "%s\\n" "$0"\n'
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    temporary_path = Path(completed.stdout.strip())
    assert completed.returncode == 0
    assert temporary_path.parent == Path(tempfile.gettempdir())
    assert not temporary_path.exists()


def test_missing_source_is_reported_before_process_start(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "missing")

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 4
    assert completed.stdout == ""
    assert "patchharbor: cannot read script source" in completed.stderr


def test_temporary_script_is_removed_after_timeout(tmp_path: Path) -> None:
    observed_path = tmp_path / "temporary-path.txt"
    script_path = _script_path(tmp_path, "timeout-cleanup")
    if os.name == "nt":
        script_body = (
            f'Set-Content -Path "{observed_path}" -Value $PSCommandPath\n'
            "while ($true) {}\n"
        )
    else:
        script_body = (
            f'printf "%s\\n" "$0" > "{observed_path}"\n'
            "while :; do :; done\n"
        )
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(
        script_path,
        tmp_path,
        "--timeout",
        "0.05",
    )

    temporary_path = Path(observed_path.read_text(encoding="utf-8").strip())
    assert completed.returncode == 124
    assert not temporary_path.exists()


def test_missing_interpreter_is_reported_as_tool_error(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "missing-interpreter")
    script_path.write_text(
        f"{REQUIRED_MARKER}\n",
        encoding="utf-8",
    )

    completed = _run_patchharbor(
        script_path,
        tmp_path,
        environment_overrides={"PATH": "", "PATHEXT": ""},
    )

    executable = "powershell.exe" if os.name == "nt" else "bash"
    assert completed.returncode == 5
    assert completed.stdout == ""
    assert completed.stderr == (
        f"patchharbor: script interpreter not found: {executable}\n"
    )


def _write_named_script(path: Path, output: str, *, exit_code: int = 0) -> None:
    if os.name == "nt":
        body = f'Write-Output "{output}"\nexit {exit_code}\n'
    else:
        body = f'printf "%s\\n" "{output}"\nexit {exit_code}\n'
    path.write_text(f"{REQUIRED_MARKER}\n{body}", encoding="utf-8")


def test_directory_with_one_candidate_runs_without_prompt(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _write_named_script(_script_path(inbox, "only"), "automatic")

    completed = _run_patchharbor(inbox, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "automatic\n"
    assert completed.stderr == ""


def test_empty_directory_selection_aborts(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _write_named_script(_script_path(inbox, "first"), "first")
    _write_named_script(_script_path(inbox, "second"), "second")

    completed = _run_patchharbor(inbox, tmp_path, input_text="\n")

    assert completed.returncode == 2
    assert "Select [1-2]:" in completed.stdout
    assert completed.stderr == "patchharbor: no script selected\n"


def test_directory_without_candidates_is_rejected(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "plain.txt").write_text("not a script\n", encoding="utf-8")
    (inbox / "nested").mkdir()

    completed = _run_patchharbor(inbox, tmp_path)

    assert completed.returncode == 3
    assert completed.stdout == ""
    assert completed.stderr == (
        f"patchharbor: no PatchHarbor scripts found in directory {inbox}\n"
    )


def test_invalid_directory_selection_is_retried(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    first = _script_path(inbox, "first")
    second = _script_path(inbox, "second")
    _write_named_script(first, "first")
    _write_named_script(second, "second")
    os.utime(first, ns=(200, 200))
    os.utime(second, ns=(100, 100))

    completed = _run_patchharbor(
        inbox,
        tmp_path,
        input_text="wrong\n２\n2\n",
    )

    assert completed.returncode == 0
    assert completed.stdout.count("Enter 1-2.") == 2
    assert completed.stdout.endswith("second\n")
    assert completed.stderr == ""


def _zip_script_text(output: str, *, exit_code: int = 0) -> str:
    if os.name == "nt":
        body = f'Write-Output "{output}"\nexit {exit_code}\n'
    else:
        body = f'printf "%s\\n" "{output}"\nexit {exit_code}\n'
    return f"{REQUIRED_MARKER}\n{body}"


def test_zip_scripts_run_in_stored_archive_order(tmp_path: Path) -> None:
    archive_path = tmp_path / "scripts.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("z-first.sh", _zip_script_text("first"))
        archive.writestr("a-second.sh", _zip_script_text("second"))

    completed = _run_patchharbor(archive_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "first\nsecond\n"
    assert completed.stderr == ""


def test_fs_run_reads_zip_patchbundle_from_standard_input_in_archive_order(
    tmp_path: Path,
) -> None:
    from io import BytesIO

    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("z-first.sh", _zip_script_text("first"))
        archive.writestr("a-second.sh", _zip_script_text("second"))

    completed = _run_cli_bytes(
        tmp_path,
        "fs",
        "run",
        input_bytes=archive_bytes.getvalue(),
    )

    assert completed.returncode == 0
    assert completed.stdout.decode().splitlines() == ["first", "second"]
    assert completed.stderr == b""


def test_zip_execution_stops_after_first_failed_script(tmp_path: Path) -> None:
    archive_path = tmp_path / "scripts.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "first.sh",
            _zip_script_text("first", exit_code=17),
        )
        archive.writestr("second.sh", _zip_script_text("second"))

    completed = _run_patchharbor(archive_path, tmp_path)

    assert completed.returncode == 17
    assert completed.stdout == "first\n"
    assert completed.stderr == ""


def test_zip_transfers_entries_without_required_marker(tmp_path: Path) -> None:
    archive_path = tmp_path / "scripts.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("notes.txt", "not a script\n")
        archive.writestr("run.sh", _zip_script_text("ran"))

    completed = _run_patchharbor(archive_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "ran\n"
    assert completed.stderr == ""
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == (
        "not a script\n"
    )


def test_markerless_script_file_is_transferred_but_never_executed(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "markerless-script.zip"
    if os.name == "nt":
        payload_name = "helper.ps1"
        payload_content = 'Set-Content -LiteralPath "unexpected.txt" -Value "ran"\n'
        valid_name = "run.ps1"
        valid_script = f"{REQUIRED_MARKER}\nexit 0\n"
    else:
        payload_name = "helper.sh"
        payload_content = 'printf "%s\n" ran > unexpected.txt\n'
        valid_name = "run.sh"
        valid_script = f"{REQUIRED_MARKER}\nexit 0\n"

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(payload_name, payload_content)
        archive.writestr(valid_name, valid_script)

    completed = _run_patchharbor(archive_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert (tmp_path / payload_name).read_text(encoding="utf-8") == payload_content
    assert not (tmp_path / "unexpected.txt").exists()


def test_empty_zip_has_a_clear_tool_error(tmp_path: Path) -> None:
    archive_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive_path, "w"):
        pass

    completed = _run_patchharbor(archive_path, tmp_path)

    assert completed.returncode == 3
    assert completed.stdout == ""
    assert completed.stderr == (
        f"patchharbor: no valid PatchHarbor scripts found in ZIP archive "
        f"{archive_path}\n"
    )


def test_corrupt_zip_is_distinct_from_missing_marker(tmp_path: Path) -> None:
    archive_path = tmp_path / "broken.zip"
    archive_path.write_bytes(b"PK\x03\x04broken")

    completed = _run_patchharbor(archive_path, tmp_path)

    assert completed.returncode == 4
    assert completed.stdout == ""
    assert completed.stderr.startswith(
        f"patchharbor: cannot read ZIP archive {archive_path}:"
    )


def test_metadata_and_multiple_messages_do_not_change_execution(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "informational-data")
    if os.name == "nt":
        command = 'Write-Output "ran"\n'
    else:
        command = 'printf "%s\\n" "ran"\n'
    script_path.write_text(
        "\n".join(
            (
                REQUIRED_MARKER,
                "# PATCHHARBOR META author=Christian",
                "# PATCHHARBOR META build.V1=ready",
                "# PATCHHARBOR MESSAGE First.1 START",
                "# One",
                "# PATCHHARBOR MESSAGE First.1 END",
                "# PATCHHARBOR MESSAGE second2 START",
                "# Two",
                "# PATCHHARBOR MESSAGE second2 END",
                command.rstrip("\n"),
                "",
            )
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "ran\n"
    assert completed.stderr == ""


def test_damaged_message_does_not_prevent_script_execution(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "damaged-message")
    if os.name == "nt":
        script_body = 'Write-Output "still-runs"\n'
    else:
        script_body = 'printf "%s\\n" "still-runs"\n'
    script_path.write_text(
        "\n".join(
            (
                REQUIRED_MARKER,
                "# PATCHHARBOR MESSAGE Note START",
                "# ignored",
                "# PATCHHARBOR MESSAGE Wrong END",
                script_body.rstrip("\n"),
                "",
            )
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "still-runs\n"


def test_metadata_cannot_change_execution_controls(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "informational-meta")
    if os.name == "nt":
        script_body = 'Start-Sleep -Milliseconds 20\nWrite-Output "unchanged"\n'
    else:
        script_body = 'sleep 0.02\nprintf "%s\\n" "unchanged"\n'
    script_path.write_text(
        "\n".join(
            (
                REQUIRED_MARKER,
                "# PATCHHARBOR META timeout=0.001",
                "# PATCHHARBOR META interpreter=missing-command",
                "# PATCHHARBOR META environment.TEST=injected",
                script_body.rstrip("\n"),
                "",
            )
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "unchanged\n"


def _file_payload_script(
    *,
    files: list[tuple[str, list[str]]],
    command: str,
) -> str:
    lines = [REQUIRED_MARKER]
    for name, content_lines in files:
        lines.append(f"# PATCHHARBOR FILE {name} START")
        lines.extend("#" if line == "" else f"# {line}" for line in content_lines)
        lines.append(f"# PATCHHARBOR FILE {name} END")
    lines.extend((command.rstrip("\n"), ""))
    return "\n".join(lines)


def test_file_block_creates_file_before_execution(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "create-file")
    if os.name == "nt":
        command = (
            'if (-not (Test-Path -LiteralPath "created.txt" -PathType Leaf)) '
            '{ exit 31 }\nWrite-Output "ran"\n'
        )
    else:
        command = '[ -f created.txt ] || exit 31\nprintf "%s\\n" "ran"\n'
    script_path.write_text(
        _file_payload_script(
            files=[("created.txt", ["first line", "", "third line"])],
            command=command,
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "ran\n"
    assert (tmp_path / "created.txt").read_text(encoding="utf-8") == (
        "first line\n\nthird line"
    )


def test_file_block_overwrites_existing_regular_file_before_execution(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old", encoding="utf-8")
    script_path = _script_path(tmp_path, "overwrite-file")
    if os.name == "nt":
        command = (
            'if ([System.IO.File]::ReadAllText("existing.txt") -ne "new value") '
            '{ exit 32 }\nWrite-Output "ran"\n'
        )
    else:
        command = (
            '[ "$(cat existing.txt)" = "new value" ] || exit 32\n'
            'printf "%s\\n" "ran"\n'
        )
    script_path.write_text(
        _file_payload_script(
            files=[("existing.txt", ["new value"])],
            command=command,
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "ran\n"
    assert target.read_text(encoding="utf-8") == "new value"


def test_multiple_file_blocks_keep_base64_as_plain_text(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "multiple-files")
    if os.name == "nt":
        command = (
            'if (-not (Test-Path -LiteralPath "first.txt" -PathType Leaf)) '
            '{ exit 33 }\n'
            'if (-not (Test-Path -LiteralPath "payload.b64" -PathType Leaf)) '
            '{ exit 34 }\n'
            'Write-Output "ran"\n'
        )
    else:
        command = (
            '[ -f first.txt ] || exit 33\n'
            '[ -f payload.b64 ] || exit 34\n'
            'printf "%s\\n" "ran"\n'
        )
    script_path.write_text(
        _file_payload_script(
            files=[
                ("first.txt", ["one"]),
                ("payload.b64", ["SGVsbG8gUGF0Y2hIYXJib3Ih"]),
            ],
            command=command,
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "ran\n"
    assert (tmp_path / "first.txt").read_text(encoding="utf-8") == "one"
    assert (tmp_path / "payload.b64").read_text(encoding="utf-8") == (
        "SGVsbG8gUGF0Y2hIYXJib3Ih"
    )


def test_damaged_file_block_does_not_prevent_execution(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "damaged-file")
    if os.name == "nt":
        command = 'Write-Output "still-runs"\n'
    else:
        command = 'printf "%s\\n" "still-runs"\n'
    script_path.write_text(
        "\n".join(
            (
                REQUIRED_MARKER,
                "# PATCHHARBOR FILE broken.txt START",
                "# ignored",
                "# PATCHHARBOR FILE wrong.txt END",
                command.rstrip("\n"),
                "",
            )
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "still-runs\n"
    assert not (tmp_path / "broken.txt").exists()


def test_unsafe_file_name_is_ignored_before_execution(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"outside-{tmp_path.name}.txt"
    outside.unlink(missing_ok=True)
    script_path = _script_path(tmp_path, "unsafe-file-name")
    if os.name == "nt":
        command = 'Write-Output "still-runs"\n'
    else:
        command = 'printf "%s\\n" "still-runs"\n'
    unsafe_name = f"../{outside.name}"
    script_path.write_text(
        _file_payload_script(
            files=[(unsafe_name, ["must not be written"])],
            command=command,
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "still-runs\n"
    assert not outside.exists()


def test_non_regular_file_target_prevents_execution(tmp_path: Path) -> None:
    target = tmp_path / "blocked.txt"
    target.mkdir()
    sentinel = tmp_path / "must-not-exist"
    script_path = _script_path(tmp_path, "blocked-file")
    if os.name == "nt":
        command = f'Set-Content -LiteralPath "{sentinel}" -Value executed\n'
    else:
        command = f'printf executed > "{sentinel}"\n'
    script_path.write_text(
        _file_payload_script(
            files=[("blocked.txt", ["replacement"])],
            command=command,
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 6
    assert completed.stdout == ""
    assert "target is not a regular file" in completed.stderr
    assert not sentinel.exists()
    assert target.is_dir()


def test_normal_script_exit_does_not_leave_a_child_process(
    tmp_path: Path,
) -> None:
    ready_path = tmp_path / "normal-child.pid"
    script_path = _script_path(tmp_path, "normal-child-tree")
    script_path.write_text(
        _child_process_script(ready_path, exit_parent=True),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)
    child_pid = _wait_for_child_pid(ready_path)

    assert completed.returncode == 0
    _assert_child_process_stopped(child_pid)


def test_timeout_stops_the_complete_child_process_tree(
    tmp_path: Path,
) -> None:
    ready_path = tmp_path / "timeout-child.pid"
    script_path = _script_path(tmp_path, "timeout-child-tree")
    script_path.write_text(
        _child_process_script(ready_path),
        encoding="utf-8",
    )

    completed = _run_patchharbor(
        script_path,
        tmp_path,
        "--timeout",
        "1.5",
    )
    child_pid = _wait_for_child_pid(ready_path)

    assert completed.returncode == 124
    assert completed.stderr == "patchharbor: script timed out after 1.5 seconds\n"
    _assert_child_process_stopped(child_pid)


def test_keyboard_interrupt_stops_the_complete_child_process_tree(
    tmp_path: Path,
) -> None:
    ready_path = tmp_path / "interrupt-child.pid"
    script_path = _script_path(tmp_path, "interrupt-child-tree")
    script_path.write_text(
        _child_process_script(ready_path),
        encoding="utf-8",
    )
    runner_path = tmp_path / "interrupt-runner.py"
    runner_path.write_text(
        """\
from __future__ import annotations
import _thread
from pathlib import Path
import sys
import threading
import time

from patchharbor.errors import PatchHarborError
from patchharbor.execution import execute_script_text

script_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
cwd = Path(sys.argv[3])


def interrupt_when_child_is_ready() -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if ready_path.exists() and ready_path.read_text(encoding="utf-8").strip():
            _thread.interrupt_main()
            return
        time.sleep(0.02)
    _thread.interrupt_main()


threading.Thread(target=interrupt_when_child_is_ready, daemon=True).start()
try:
    result = execute_script_text(
        script_path.read_text(encoding="utf-8"),
        cwd=cwd,
        timeout_seconds=30,
    )
except PatchHarborError as exc:
    print(f"patchharbor: {exc}", file=sys.stderr)
    raise SystemExit(int(exc.exit_code))
raise SystemExit(result)
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(runner_path),
            str(script_path),
            str(ready_path),
            str(tmp_path),
        ],
        cwd=tmp_path,
        env=project_environment(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    child_pid = _wait_for_child_pid(ready_path)

    assert completed.returncode == 130
    assert completed.stderr == "patchharbor: script aborted by user\n"
    _assert_child_process_stopped(child_pid)


def test_fs_run_non_tty_streams_complete_large_output(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "large-output")
    if os.name == "nt":
        script_body = (
            "1..20000 | ForEach-Object { "
            '[Console]::Out.WriteLine(("line-{0:D4}" -f $_)) }\n'
        )
    else:
        script_body = (
            'number=1\n'
            'while [ "$number" -le 20000 ]; do\n'
            '    printf "line-%04d\\n" "$number"\n'
            '    number=$((number + 1))\n'
            'done\n'
        )
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    output_lines = completed.stdout.splitlines()
    assert len(output_lines) == 20_000
    assert output_lines[:3] == ["line-0001", "line-0002", "line-0003"]
    assert output_lines[-3:] == ["line-19998", "line-19999", "line-20000"]
    assert completed.stderr == ""


def test_fs_run_merges_stdout_and_stderr_in_write_order(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "merged-output")
    if os.name == "nt":
        script_body = (
            '[Console]::Out.WriteLine("stdout-1")\n'
            '[Console]::Out.Flush()\n'
            '[Console]::Error.WriteLine("stderr-1")\n'
            '[Console]::Error.Flush()\n'
            '[Console]::Out.WriteLine("stdout-2")\n'
            '[Console]::Out.Flush()\n'
            '[Console]::Error.WriteLine("stderr-2")\n'
            '[Console]::Error.Flush()\n'
        )
    else:
        script_body = (
            'printf "%s\\n" "stdout-1"\n'
            'printf "%s\\n" "stderr-1" >&2\n'
            'printf "%s\\n" "stdout-2"\n'
            'printf "%s\\n" "stderr-2" >&2\n'
        )
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == [
        "stdout-1",
        "stderr-1",
        "stdout-2",
        "stderr-2",
    ]
    assert completed.stderr == ""


def test_fs_run_handles_long_and_unterminated_output_from_fast_script(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "fast-output")
    long_line = "x" * 20_000
    if os.name == "nt":
        script_body = (
            f'[Console]::Out.WriteLine("{long_line}")\n'
            '[Console]::Out.Write("final-without-newline")\n'
        )
    else:
        script_body = (
            f"printf '%s\\n' '{long_line}'\n"
            "printf '%s' 'final-without-newline'\n"
        )
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == f"{long_line}\nfinal-without-newline"
    assert completed.stderr == ""


def test_fs_run_replaces_invalid_utf8_from_script_output(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "invalid-utf8-output")
    if os.name == "nt":
        script_body = (
            "$bytes = [byte[]](0x62,0x61,0x64,0x2D,0xFF,0x0A)\n"
            "$stream = [Console]::OpenStandardOutput()\n"
            "$stream.Write($bytes, 0, $bytes.Length)\n"
            "$stream.Flush()\n"
        )
    else:
        script_body = "printf 'bad-\\377\\n'\n"
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "bad-�\n"
    assert completed.stderr == ""


def test_fs_run_log_contains_complete_output_and_run_metadata(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "logged-output")
    if os.name == "nt":
        script_body = (
            '1..12 | ForEach-Object { '
            '[Console]::Out.WriteLine(("logged-{0:D2}" -f $_)) }\n'
        )
    else:
        script_body = (
            'number=1\n'
            'while [ "$number" -le 12 ]; do\n'
            '    printf "logged-%02d\\n" "$number"\n'
            '    number=$((number + 1))\n'
            'done\n'
        )
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(
        script_path,
        tmp_path,
        "--log",
        "--no-color",
    )

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == [
        f"logged-{number:02d}" for number in range(1, 13)
    ]
    prefix = "patchharbor: log: "
    assert completed.stderr.startswith(prefix)
    log_path = Path(completed.stderr.removeprefix(prefix).strip())
    try:
        assert log_path.parent == Path(tempfile.gettempdir())
        log_text = log_path.read_text(encoding="utf-8")
        assert "PatchHarbor run log\n" in log_text
        expected_cwd = json.dumps(str(tmp_path), ensure_ascii=False)
        assert f"working_directory: {expected_cwd}\n" in log_text
        assert "timeout_seconds: 300\n" in log_text
        assert "plain_output:" not in log_text
        assert "color_enabled:" not in log_text
        assert "--- output ---\n" in log_text
        assert "logged-01\n" in log_text
        assert "logged-12\n" in log_text
        assert "--- result ---\n" in log_text
        assert "exit_code: 0\n" in log_text
    finally:
        log_path.unlink(missing_ok=True)


def test_fs_run_log_preserves_raw_invalid_utf8_while_plain_output_is_safe(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "raw-invalid-log")
    if os.name == "nt":
        script_body = (
            "$bytes = [byte[]](0x72,0x61,0x77,0x2D,0xFF,0x0A)\n"
            "$stream = [Console]::OpenStandardOutput()\n"
            "$stream.Write($bytes, 0, $bytes.Length)\n"
            "$stream.Flush()\n"
        )
    else:
        script_body = "printf 'raw-\\377\\n'\n"
    script_path.write_text(
        f"{REQUIRED_MARKER}\n{script_body}",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path, "--log")

    assert completed.returncode == 0
    assert completed.stdout == "raw-�\n"
    log_path = _log_path_from_stderr(completed.stderr)
    try:
        log_bytes = log_path.read_bytes()
        assert b"raw-\xff\n" in log_bytes
        assert "raw-�\n".encode() not in log_bytes
        assert b"exit_code: 0\n" in log_bytes
    finally:
        log_path.unlink(missing_ok=True)


def test_fs_run_log_is_closed_and_complete_after_tool_error(
    tmp_path: Path,
) -> None:
    script_path = _script_path(tmp_path, "logged-tool-error")
    script_path.write_text("echo missing marker\n", encoding="utf-8")

    completed = _run_patchharbor(script_path, tmp_path, "--log")

    assert completed.returncode == 3
    assert "missing required marker line" in completed.stderr
    log_path = _log_path_from_stderr(completed.stderr)
    try:
        log_text = log_path.read_text(encoding="utf-8")
        assert "PatchHarbor run log\n" in log_text
        assert "--- result ---\n" in log_text
        assert "exit_code: 3\n" in log_text
        assert 'tool_error: "missing required marker line: # PATCHHARBOR"\n' in log_text
    finally:
        log_path.unlink(missing_ok=True)
