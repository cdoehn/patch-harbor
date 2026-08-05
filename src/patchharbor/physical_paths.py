"""Physical path canonicalization used at repository trust boundaries."""

from __future__ import annotations

from pathlib import Path


def physically_canonicalize(path: Path, *, must_exist: bool) -> Path:
    """Resolve one user or Git path to its physical absolute target."""
    return path.expanduser().resolve(strict=must_exist)
