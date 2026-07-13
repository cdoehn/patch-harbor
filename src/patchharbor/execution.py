"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result returned after the script process has finished."""

    exit_code: int


def run_script_file(script_path: Path) -> ExecutionResult:
    """Run one script file with the platform default interpreter."""
    if os.name == "nt":
        command = [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script_path),
        ]
    else:
        command = ["bash", str(script_path)]

    completed = subprocess.run(command, check=False)
    return ExecutionResult(exit_code=completed.returncode)
