"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


def execute_script_file(script_path: Path) -> int:
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

    return subprocess.run(command, check=False).returncode
