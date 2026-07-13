from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys



PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MARKER = "# PATCHHARBOR"


def _run_patchharbor(script_path: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
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
            str(script_path),
        ],
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_fs_run_executes_a_real_script_file_with_required_marker(
    tmp_path: Path,
) -> None:
    if os.name == "nt":
        script_path = tmp_path / "hello.ps1"
        script_path.write_text(
            f'{REQUIRED_MARKER}\nWrite-Output "patchharbor-e2e"\n',
            encoding="utf-8",
        )
    else:
        script_path = tmp_path / "hello.sh"
        script_path.write_text(
            f'{REQUIRED_MARKER}\nprintf "%s\\n" "patchharbor-e2e"\n',
            encoding="utf-8",
        )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 0
    assert completed.stdout == "patchharbor-e2e\n"
    assert completed.stderr == ""


def test_fs_run_rejects_script_without_required_marker(tmp_path: Path) -> None:
    sentinel_path = tmp_path / "must-not-exist"
    if os.name == "nt":
        script_path = tmp_path / "missing-marker.ps1"
        script_path.write_text(
            f'Set-Content -Path "{sentinel_path}" -Value "executed"\n',
            encoding="utf-8",
        )
    else:
        script_path = tmp_path / "missing-marker.sh"
        script_path.write_text(
            f'printf executed > "{sentinel_path}"\n',
            encoding="utf-8",
        )

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == (
        "patchharbor: missing required marker line: # PATCHHARBOR\n"
    )
    assert not sentinel_path.exists()


def test_message_line_does_not_replace_required_marker(tmp_path: Path) -> None:
    script_path = tmp_path / ("message.ps1" if os.name == "nt" else "message.sh")
    script_path.write_text("# PATCHHARBOR MESSAGE note\n", encoding="utf-8")

    completed = _run_patchharbor(script_path, tmp_path)

    assert completed.returncode == 2
    assert "missing required marker line" in completed.stderr
