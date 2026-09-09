"""Pure portable naming policy for the optional Exchange archive child."""

from __future__ import annotations

import re


DEFAULT_ARCHIVE_DIRECTORY = "PatchHarbor-Archive"
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def validate_archive_directory(value: object) -> str:
    """Accept one portable child name, or the empty disabling value; never a path."""
    if type(value) is not str:
        raise ValueError("archive directory must be a string")
    if not value:
        return value
    if (
        re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value) is None
        or value in {".", ".."}
        or value.endswith(".")
        or value.split(".", 1)[0].upper() in _RESERVED_NAMES
    ):
        raise ValueError(
            "archive directory must be one portable folder name inside Exchange "
            "(no paths, traversal, trailing dots or reserved device names)"
        )
    return value
