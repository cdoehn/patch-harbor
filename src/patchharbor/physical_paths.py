"""Physical path canonicalization used at trust boundaries."""

from __future__ import annotations

from pathlib import Path


def physically_canonicalize(path: Path, *, must_exist: bool) -> Path:
    """Resolve one user or Git path to its physical absolute target."""
    return path.expanduser().resolve(strict=must_exist)


def _canonical_path_is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


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
    return _canonical_path_is_within(physical_candidate, physical_root)


def physical_paths_overlap(
    first: Path,
    second: Path,
    *,
    first_must_exist: bool,
    second_must_exist: bool,
) -> bool:
    """Whether two physical paths contain one another in either direction."""
    physical_first = physically_canonicalize(
        first,
        must_exist=first_must_exist,
    )
    physical_second = physically_canonicalize(
        second,
        must_exist=second_must_exist,
    )
    return _canonical_path_is_within(
        physical_first,
        physical_second,
    ) or _canonical_path_is_within(
        physical_second,
        physical_first,
    )
