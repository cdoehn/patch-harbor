"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


class ScriptExecutionTimeout(Exception):
    """The script exceeded its configured execution timeout."""


def execute_script_file(
    script_path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
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

    try:
        completed = subprocess.run(
            command,
            check=False,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScriptExecutionTimeout(
            f"script timed out after {timeout_seconds:g} seconds"
        ) from exc

    return completed.returncode
