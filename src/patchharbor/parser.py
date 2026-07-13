"""Parsing rules for the PatchHarbor script format."""

from __future__ import annotations


REQUIRED_MARKER = "# PATCHHARBOR"


class ScriptFormatError(ValueError):
    """The script does not satisfy the required PatchHarbor format."""


def validate_required_marker(script_text: str) -> None:
    """Require the exact marker as a complete normalized line."""
    if REQUIRED_MARKER not in script_text.splitlines():
        raise ScriptFormatError(
            f"missing required marker line: {REQUIRED_MARKER}"
        )
