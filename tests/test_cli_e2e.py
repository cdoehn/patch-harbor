from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKER = "# PATCHHARBOR"


def _run_patchharbor(
    script_path: Path,
    cwd: Path,
    *run_arguments: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else os.pathsep.join((source_path, existing_pythonpath))
    )

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "patchharbor.cli",
            "fs",
            "run",
            *run_arguments,
            str(script_path),
        ],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _script_path(tmp_path: Path, stem: str) -> Path:
    return tmp_path / (f"{stem}.ps1" if os.name == "nt" else f"{stem}.sh")


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

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == (
        "patchharbor: missing required marker line: # PATCHHARBOR\n"
    )
    assert not sentinel_path.exists()


def test_message_line_does_not_replace_required_marker(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "message")
    script_path.write_text("# PATCHHARBOR MESSAGE note\n", encoding="utf-8")

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 2
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


def test_script_exit_code_is_returned(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "exit-code")
    script_path.write_text(
        f"{REQUIRED_MARKER}\nexit 23\n",
        encoding="utf-8",
    )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 23


def test_timeout_returns_124(tmp_path: Path) -> None:
    script_path = _script_path(tmp_path, "timeout")
    if os.name == "nt":
        script_body = "while ($true) {}\n"
    else:
        script_body = "while :; do :; done\n"
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

    assert completed.returncode == 124
    assert completed.stderr == "patchharbor: script timed out after 0.05 seconds\n"


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
