"""Validation of the PatchHarbor script format."""

from __future__ import annotations


REQUIRED_MARKER = "# PATCHHARBOR"


def has_required_marker(script_text: str) -> bool:
    """Return whether the exact required marker occurs as its own line."""
    return REQUIRED_MARKER in script_text.splitlines()
