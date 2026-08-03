"""Platform adapters for process, filesystem, runtime, and error semantics."""

from __future__ import annotations

from pathlib import Path

from patchharbor.platform.lifecycle import (
    ProcessResult,
    ProcessState,
    ProcessTree,
)
from patchharbor.platform.runtime import PlatformFamily, platform_family


__all__ = [
    "ProcessResult",
    "ProcessState",
    "ProcessTree",
    "create_process_tree",
]


def create_process_tree(command: list[str], *, cwd: Path) -> ProcessTree:
    """Start the process-tree implementation for the current operating system."""
    if platform_family() is PlatformFamily.WINDOWS:  # pragma: no cover
        from patchharbor.platform.windows import WindowsProcessTree

        return WindowsProcessTree.start(command, cwd=cwd)

    from patchharbor.platform.posix import PosixProcessTree

    return PosixProcessTree.start(command, cwd=cwd)
