"""Small operating-system boundary used by platform-neutral modules."""

from __future__ import annotations

import os
import shutil


_SUPPORTED_OS_NAMES = frozenset({"nt", "posix"})


def is_windows(*, os_name: str | None = None) -> bool:
    """Return whether the current or supplied supported Python OS is Windows."""
    selected = os.name if os_name is None else os_name
    if selected not in _SUPPORTED_OS_NAMES:
        raise RuntimeError(f"unsupported operating system family: {selected}")
    return selected == "nt"


def find_executable(executable: str) -> str | None:
    """Resolve one executable through the platform PATH rules."""
    return shutil.which(executable)
