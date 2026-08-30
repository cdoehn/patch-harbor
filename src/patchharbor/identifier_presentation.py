"""Compact presentation of long technical identifiers."""

from __future__ import annotations


IDENTIFIER_PREFIX_LENGTH = 6
_IDENTIFIER_ELLIPSIS = "…"


def shorten_identifier(
    value: object,
    *,
    with_ellipsis: bool = True,
) -> str:
    """Return a six-character identifier prefix for human-facing output."""
    text = str(value)
    if len(text) <= IDENTIFIER_PREFIX_LENGTH:
        return text
    suffix = _IDENTIFIER_ELLIPSIS if with_ellipsis else ""
    return f"{text[:IDENTIFIER_PREFIX_LENGTH]}{suffix}"
