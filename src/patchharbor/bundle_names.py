"""Portable suffix policy for outer ZIP filenames, never archive members."""

from __future__ import annotations

import re


MAX_BUNDLE_SUFFIX_LENGTH = 32
_SUFFIX_PATTERN = re.compile(rf"[A-Za-z0-9._-]{{1,{MAX_BUNDLE_SUFFIX_LENGTH}}}")
_BROWSER_TEMP_SUFFIXES = (
    ".crdownload", ".download", ".opdownload", ".part", ".partial", ".tmp",
)


def is_browser_temporary_name(name: str) -> bool:
    """Recognize common incomplete browser-download names."""
    return name.casefold().endswith(_BROWSER_TEMP_SUFFIXES)


def validate_bundle_suffix(value: object) -> str:
    """Validate a literal portable suffix; the empty string disables it."""
    if type(value) is not str:
        raise ValueError("bundle suffix must be a string")
    if value == "":
        return value
    if (
        _SUFFIX_PATTERN.fullmatch(value) is None
        or value.endswith(".")
        or ".." in value
        or not any(character.isalnum() for character in value)
    ):
        raise ValueError(
            "bundle suffix must contain 1-32 ASCII letters, digits, dots, "
            "underscores or hyphens, include a letter or digit, "
            "and contain neither '..' nor a trailing dot"
        )
    if is_browser_temporary_name(value):
        raise ValueError("bundle suffix must not use a temporary download extension")
    return value


def append_bundle_suffix(filename: str, suffix: str) -> str:
    """Append the configured suffix exactly once to a base ZIP filename."""
    if not filename.lower().endswith(".zip"):
        raise ValueError("bundle base filename must end with .zip")
    return filename + validate_bundle_suffix(suffix)
