from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_fs_run_executes_a_real_script_file(tmp_path: Path) -> None:
    if os.name == "nt":
        script_path = tmp_path / "hello.ps1"
        script_path.write_text(
            'Write-Output "patchharbor-e2e"\n',
            encoding="utf-8",
        )
    else:
        script_path = tmp_path / "hello.sh"
        script_path.write_text(
            'printf "%s\\n" "patchharbor-e2e"\n',
            encoding="utf-8",
        )

    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else os.pathsep.join((source_path, existing_pythonpath))
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "patchharbor.cli",
            "fs",
            "run",
            str(script_path),
        ],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "patchharbor-e2e\n"
    assert completed.stderr == ""
