from __future__ import annotations

import base64
import json
import os
import shlex
from collections.abc import Mapping
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import pytest

from tests.platform_support import (
    REQUIRED_MARKER,
    assert_child_process_stopped,
    cleanup_test_processes,
    log_path_from_stderr as _log_path_from_stderr,
    normalized_path,
    project_environment,
    run_cli as _run_cli,
    run_cli_bytes as _run_cli_bytes,
    wait_for_child_pid,
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


def _process_tree_script(
    child_ready_path: Path,
    grandchild_ready_path: Path,
    *,
    exit_parent: bool = False,
) -> str:
    """Build one script whose child owns a long-running grandchild."""
    if os.name == "nt":
        escaped_child = str(child_ready_path).replace("'", "''")
        escaped_grandchild = str(grandchild_ready_path).replace("'", "''")
        child_command = (
            "$grandchild = Start-Process "
            "-FilePath (Join-Path $PSHOME 'powershell.exe') "
            "-ArgumentList '-NoLogo','-NoProfile','-NonInteractive',"
            "'-Command','Start-Sleep -Seconds 60' -PassThru; "
            "[System.IO.File]::WriteAllText("
            f"'{escaped_grandchild}', [string]$grandchild.Id); "
            "Wait-Process -Id $grandchild.Id"
        )
        encoded_child = base64.b64encode(
            child_command.encode("utf-16-le")
        ).decode("ascii")
        parent_tail = "exit 0" if exit_parent else "Wait-Process -Id $child.Id"
        return (
            f"{REQUIRED_MARKER}\n"
            "$child = Start-Process "
            "-FilePath (Join-Path $PSHOME 'powershell.exe') "
            "-ArgumentList '-NoLogo','-NoProfile','-NonInteractive',"
            f"'-EncodedCommand','{encoded_child}' -PassThru\n"
            f"[System.IO.File]::WriteAllText('{escaped_child}', "
            "[string]$child.Id)\n"
            "$deadline = [DateTime]::UtcNow.AddSeconds(5)\n"
            f"while ((-not (Test-Path -LiteralPath '{escaped_grandchild}')) "
            "-and ([DateTime]::UtcNow -lt $deadline)) { "
            "Start-Sleep -Milliseconds 20 }\n"
            f"if (-not (Test-Path -LiteralPath '{escaped_grandchild}')) "
            "{ exit 91 }\n"
            f"{parent_tail}\n"
        )

    child_ready = shlex.quote(str(child_ready_path))
    grandchild_ready = shlex.quote(str(grandchild_ready_path))
    child_command = (
        "sleep 60 & "
        "grandchild_pid=$!; "
        f"printf '%s' \"$grandchild_pid\" > {grandchild_ready}; "
        "wait \"$grandchild_pid\""
    )
    parent_tail = "exit 0" if exit_parent else 'wait "$child_pid"'
    return (
        f"{REQUIRED_MARKER}\n"
        f"bash -c {shlex.quote(child_command)} &\n"
        "child_pid=$!\n"
        f"printf '%s' \"$child_pid\" > {child_ready}\n"
        "counter=0\n"
        f"while [ ! -s {grandchild_ready} ] "
        '&& [ "$counter" -lt 250 ]; do\n'
        "    sleep 0.02\n"
        "    counter=$((counter + 1))\n"
        "done\n"
        f"[ -s {grandchild_ready} ] || exit 91\n"
        f"{parent_tail}\n"
    )



def test_fs_run_rejects_empty_standard_input(tmp_path: Path) -> None:
    completed = _run_cli(tmp_path, "fs", "run", input_text="")

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == "patchharbor: no script input received\n"


def test_fs_run_help_is_limited_to_public_arguments(tmp_path: Path) -> None:
    completed = _run_cli(tmp_path, "fs", "run", "--help")

    assert completed.returncode == 0
    help_text = " ".join(completed.stdout.split())
    assert (
        "Run generated Bash or PowerShell scripts from a file, "
        "ZIP PatchBundle, directory, or standard input."
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
    temporary_root = Path(tempfile.gettempdir()).resolve()
    assert temporary_path.resolve(strict=False).is_relative_to(temporary_root)
    assert temporary_path.parent.name.startswith("patchharbor-script-")
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
        escaped_observed_path = str(observed_path).replace("'", "''")
        script_body = (
            "[System.IO.File]::WriteAllText("
            f"'{escaped_observed_path}', $PSCommandPath)\n"
            "Start-Sleep -Seconds 60\n"
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
        "5",
    )

    recorded_path = observed_path.read_text(encoding="utf-8").strip()
    assert recorded_path
    temporary_path = Path(recorded_path)
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


def test_normal_script_exit_does_not_leave_descendant_processes(
    tmp_path: Path,
) -> None:
    child_ready_path = tmp_path / "normal-child.pid"
    grandchild_ready_path = tmp_path / "normal-grandchild.pid"
    script_path = _script_path(tmp_path, "normal-child-tree")
    script_path.write_text(
        _process_tree_script(
            child_ready_path,
            grandchild_ready_path,
            exit_parent=True,
        ),
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)
    child_pid: int | None = None
    grandchild_pid: int | None = None
    try:
        child_pid = wait_for_child_pid(child_ready_path)
        grandchild_pid = wait_for_child_pid(grandchild_ready_path)

        assert completed.returncode == 0
        assert_child_process_stopped(child_pid)
        assert_child_process_stopped(grandchild_pid)
    finally:
        cleanup_test_processes(child_pid, grandchild_pid)


def test_timeout_stops_the_complete_child_process_tree(
    tmp_path: Path,
) -> None:
    child_ready_path = tmp_path / "timeout-child.pid"
    grandchild_ready_path = tmp_path / "timeout-grandchild.pid"
    script_path = _script_path(tmp_path, "timeout-child-tree")
    script_path.write_text(
        _process_tree_script(child_ready_path, grandchild_ready_path),
        encoding="utf-8",
    )

    completed = _run_patchharbor(
        script_path,
        tmp_path,
        "--timeout",
        "1.5",
    )
    child_pid: int | None = None
    grandchild_pid: int | None = None
    try:
        child_pid = wait_for_child_pid(child_ready_path)
        grandchild_pid = wait_for_child_pid(grandchild_ready_path)

        assert completed.returncode == 124
        assert_child_process_stopped(child_pid)
        assert_child_process_stopped(grandchild_pid)
    finally:
        cleanup_test_processes(child_pid, grandchild_pid)


def test_keyboard_interrupt_stops_the_complete_child_process_tree(
    tmp_path: Path,
) -> None:
    child_ready_path = tmp_path / "interrupt-child.pid"
    grandchild_ready_path = tmp_path / "interrupt-grandchild.pid"
    script_path = _script_path(tmp_path, "interrupt-child-tree")
    script_path.write_text(
        _process_tree_script(child_ready_path, grandchild_ready_path),
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
child_ready_path = Path(sys.argv[2])
grandchild_ready_path = Path(sys.argv[3])
cwd = Path(sys.argv[4])


def interrupt_when_tree_is_ready() -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        ready_paths = (child_ready_path, grandchild_ready_path)
        if all(
            path.exists() and path.read_text(encoding="utf-8").strip()
            for path in ready_paths
        ):
            _thread.interrupt_main()
            return
        time.sleep(0.02)
    _thread.interrupt_main()


threading.Thread(target=interrupt_when_tree_is_ready, daemon=True).start()
try:
    result = execute_script_text(
        script_path.read_text(encoding="utf-8"),
        cwd=cwd,
        timeout_seconds=30,
    )
except PatchHarborError as exc:
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
            str(child_ready_path),
            str(grandchild_ready_path),
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
    child_pid: int | None = None
    grandchild_pid: int | None = None
    try:
        child_pid = wait_for_child_pid(child_ready_path)
        grandchild_pid = wait_for_child_pid(grandchild_ready_path)

        assert completed.returncode == 130
        assert_child_process_stopped(child_pid)
        assert_child_process_stopped(grandchild_pid)
    finally:
        cleanup_test_processes(child_pid, grandchild_pid)


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
        assert normalized_path(log_path.parent) == normalized_path(
            tempfile.gettempdir()
        )
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
