"""Central reasons and helpers for genuinely platform-dependent tests."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest


REQUIRES_POSIX_SPECIAL_FILES = pytest.mark.skipif(
    os.name == "nt",
    reason="requires POSIX special-file support",
)
REQUIRES_BASH_DOCKER_RUNNER = pytest.mark.skipif(
    os.name == "nt",
    reason="requires the Bash-based Docker integration runner",
)
REQUIRES_POWERSHELL_7 = pytest.mark.skipif(
    shutil.which("pwsh") is None,
    reason="requires the PowerShell 7 executable 'pwsh'",
)


def create_symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    """Create one symlink or skip with one stable cross-platform reason."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError):
        pytest.skip("requires symlink creation permission on this platform")
