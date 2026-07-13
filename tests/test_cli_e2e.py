from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKER = "# PATCHHARBOR"


def _run_cli(
    cwd: Path,
    *arguments: str,
    environment_overrides: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else os.pathsep.join((source_path, existing_pythonpath))
    )
    if environment_overrides:
        environment.update(environment_overrides)

    standard_input = (
        {"stdin": subprocess.DEVNULL}
        if input_text is None
        else {"input": input_text}
    )
    return subprocess.run(
        [sys.executable, "-m", "patchharbor.cli", *arguments],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        **standard_input,
    )


def _run_patchharbor(
    script_path: Path,
    cwd: Path,
    *run_arguments: str,
    environment_overrides: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run_cli(
        cwd,
        "fs",
        "run",
        *run_arguments,
        str(script_path),
        environment_overrides=environment_overrides,
    )


def test_fs_run_rejects_empty_standard_input(tmp_path: Path) -> None:
    completed = _run_cli(tmp_path, "fs", "run")

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == "patchharbor: no script input received\n"


def test_fs_run_reads_script_from_standard_input(tmp_path: Path) -> None:
    script_text = (
        f"{REQUIRED_MARKER}\n"
        'printf "%s\\n" "stdin-e2e"\n'
        if os.name != "nt"
        else f'{REQUIRED_MARKER}\nWrite-Output "stdin-e2e"\n'
    )

    completed = _run_cli(
        tmp_path,
        "fs",
        "run",
        input_text=script_text,
    )

    assert completed.returncode == 0
    assert completed.stdout == "stdin-e2e\n"
    assert completed.stderr == ""


def test_fs_run_help_is_limited_to_public_arguments(tmp_path: Path) -> None:
    completed = _run_cli(tmp_path, "fs", "run", "--help")

    assert completed.returncode == 0
    assert "Run one Bash or PowerShell script from PATH or standard input." in completed.stdout
    assert "--timeout SECONDS" in completed.stdout
    assert "default: 300" in completed.stdout
    assert "--log" not in completed.stdout
    assert "--plain" not in completed.stdout
    assert "--no-color" not in completed.stdout


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

    assert completed.returncode == 5
    assert completed.stdout == ""
    assert completed.stderr.startswith(
        "patchharbor: cannot start script interpreter:"
    )
