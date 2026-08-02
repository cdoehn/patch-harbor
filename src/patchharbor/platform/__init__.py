"""Platform-specific process-tree adapter boundary."""

from __future__ import annotations

import os
from pathlib import Path

from patchharbor.platform.lifecycle import ProcessTree, ProcessTreeTimeout


__all__ = ["ProcessTree", "ProcessTreeTimeout", "create_process_tree"]


def create_process_tree(command: list[str], *, cwd: Path) -> ProcessTree:
    """Start the process-tree implementation for the current operating system."""
    if os.name == "nt":  # pragma: no cover - exercised on Windows CI
        from patchharbor.platform.windows import WindowsProcessTree

        return WindowsProcessTree.start(command, cwd=cwd)

    from patchharbor.platform.posix import PosixProcessTree

    return PosixProcessTree.start(command, cwd=cwd)
