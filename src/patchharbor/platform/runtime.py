"""Small operating-system boundary used by platform-neutral modules."""

from __future__ import annotations

from enum import Enum
import os
import shutil


class PlatformFamily(Enum):
    """Operating-system families supported by PatchHarbor."""

    POSIX = "posix"
    WINDOWS = "windows"


def platform_family(*, os_name: str | None = None) -> PlatformFamily:
    """Return the supported family for the current or supplied Python OS name."""
    selected = os.name if os_name is None else os_name
    return PlatformFamily.WINDOWS if selected == "nt" else PlatformFamily.POSIX


def find_executable(executable: str) -> str | None:
    """Resolve one executable through the platform PATH rules."""
    return shutil.which(executable)
