"""Exclusive process-safe lock for one registered repository identity."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from patchharbor.errors import (
    repository_busy_error,
    repository_resolution_error,
)
from patchharbor.models import RepositoryId
from patchharbor.platform.locking import (
    LockOperationError,
    LockUnavailable,
    exclusive_file_lock,
)
from patchharbor.user_paths import RegistrationUserPaths


DEFAULT_REPOSITORY_LOCK_WAIT_SECONDS = 2.0


def repository_lock_path(
    paths: RegistrationUserPaths,
    repo_id: RepositoryId,
) -> Path:
    """Return the stable lock-file path for one canonical repository ID."""
    try:
        canonical_id = RepositoryId(str(repo_id))
    except ValueError as exc:
        raise repository_resolution_error(
            "repository ID is not a canonical UUID v4"
        ) from exc
    if canonical_id != repo_id:
        raise repository_resolution_error(
            "repository ID is not a canonical UUID v4"
        )
    return paths.lock_directory / f"repository-{canonical_id}.lock"


@contextmanager
def repository_lock(
    paths: RegistrationUserPaths,
    repo_id: RepositoryId,
    *,
    wait_seconds: float = DEFAULT_REPOSITORY_LOCK_WAIT_SECONDS,
) -> Iterator[None]:
    """Hold one repository lock or fail with the public busy exit code."""
    lock = exclusive_file_lock(
        repository_lock_path(paths, repo_id),
        wait_seconds=wait_seconds,
    )
    try:
        lock.__enter__()
    except LockUnavailable as exc:
        raise repository_busy_error() from exc
    except LockOperationError as exc:
        raise repository_resolution_error(
            f"{exc.operation}: {exc.cause}"
        ) from exc

    try:
        yield
    finally:
        lock.__exit__(None, None, None)
