"""Portable validation for relative paths stored in ZIP PatchBundles."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


MAX_BUNDLE_PATH_CHARS = 512
MAX_BUNDLE_SEGMENT_CHARS = 128
_SEGMENT_PATTERN = re.compile(
    rf"^[A-Za-z0-9._-]{{1,{MAX_BUNDLE_SEGMENT_CHARS}}}$"
)
_RESERVED_INTERNAL_SEGMENTS = {".git", ".patchharbor"}
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class BundlePathError(ValueError):
    """One archive member path is unsafe or conflicts with another member."""


@dataclass
class _PathNode:
    path: str
    is_directory: bool
    explicit: bool


def is_safe_path_segment(segment: str) -> bool:
    """Return whether one path segment is portable across Linux and Windows."""
    if _SEGMENT_PATTERN.fullmatch(segment) is None:
        return False
    if segment in {".", ".."} or segment.endswith((".", " ")):
        return False
    return segment.split(".", 1)[0].upper() not in _WINDOWS_RESERVED_NAMES


def normalize_bundle_path(raw_path: str, *, is_directory: bool = False) -> str:
    """Validate and normalize one POSIX-style ZIP member path."""
    if not raw_path:
        raise BundlePathError("empty member path")
    if "\\" in raw_path:
        raise BundlePathError(f"backslash is not allowed in {raw_path!r}")

    if is_directory:
        if not raw_path.endswith("/"):
            raise BundlePathError(
                f"directory member {raw_path!r} must end with '/'"
            )
        candidate = raw_path[:-1]
    else:
        if raw_path.endswith("/"):
            raise BundlePathError(
                f"file member {raw_path!r} must not end with '/'"
            )
        candidate = raw_path

    if not candidate or candidate.startswith("/"):
        raise BundlePathError(f"absolute or empty path {raw_path!r}")
    if len(candidate) > MAX_BUNDLE_PATH_CHARS:
        raise BundlePathError(
            f"member path {raw_path!r} exceeds {MAX_BUNDLE_PATH_CHARS} characters"
        )

    segments = candidate.split("/")
    for segment in segments:
        if not is_safe_path_segment(segment):
            raise BundlePathError(
                f"unsafe path segment {segment!r} in {raw_path!r}"
            )
        if segment.casefold() in _RESERVED_INTERNAL_SEGMENTS:
            raise BundlePathError(
                f"reserved internal path segment {segment!r} in {raw_path!r}"
            )
    return "/".join(segments)


def is_safe_bundle_path(relative_path: str) -> bool:
    """Return whether a file path is a safe normalized bundle target."""
    try:
        normalize_bundle_path(relative_path)
    except BundlePathError:
        return False
    return True


def validate_bundle_member_paths(
    members: Iterable[tuple[str, bool]],
) -> tuple[str, ...]:
    """Validate all archive paths and reject portable tree ambiguities."""
    nodes: dict[str, _PathNode] = {}
    normalized_members: list[str] = []

    def register(path: str, *, is_directory: bool, explicit: bool) -> None:
        key = path.casefold()
        existing = nodes.get(key)
        if existing is None:
            nodes[key] = _PathNode(path, is_directory, explicit)
            return

        if existing.path != path:
            raise BundlePathError(
                f"case-insensitive path collision between "
                f"{existing.path!r} and {path!r}"
            )
        if existing.is_directory != is_directory:
            raise BundlePathError(
                f"file/directory path collision at {path!r}"
            )
        if explicit and existing.explicit:
            raise BundlePathError(f"duplicate member path {path!r}")
        if explicit:
            existing.explicit = True

    for raw_path, is_directory in members:
        normalized = normalize_bundle_path(
            raw_path,
            is_directory=is_directory,
        )
        segments = normalized.split("/")
        for index in range(1, len(segments)):
            register(
                "/".join(segments[:index]),
                is_directory=True,
                explicit=False,
            )
        register(
            normalized,
            is_directory=is_directory,
            explicit=True,
        )
        normalized_members.append(normalized)

    return tuple(normalized_members)
