"""Physical path canonicalization used at trust boundaries."""

from __future__ import annotations

from pathlib import Path


def physically_canonicalize(path: Path, *, must_exist: bool) -> Path:
    """Resolve one user or Git path to its physical absolute target."""
    return path.expanduser().resolve(strict=must_exist)


def is_physically_within(
    candidate: Path,
    root: Path,
    *,
    candidate_must_exist: bool,
    root_must_exist: bool,
) -> bool:
    """Whether one physical path is identical to or below another one."""
    physical_candidate = physically_canonicalize(
        candidate,
        must_exist=candidate_must_exist,
    )
    physical_root = physically_canonicalize(
        root,
        must_exist=root_must_exist,
    )
    try:
        physical_candidate.relative_to(physical_root)
    except ValueError:
        return False
    return True
