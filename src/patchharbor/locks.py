"""Application-facing registry and repository lock contracts."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from patchharbor.errors import (
    PatchHarborError,
    registry_error,
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


@contextmanager
def _application_lock(
    path: Path,
    *,
    unavailable_error: PatchHarborError,
    operation_error: Callable[[str], PatchHarborError],
) -> Iterator[None]:
    """Map one portable advisory lock to one application-level contract."""
    lock = exclusive_file_lock(path)
    try:
        lock.__enter__()
    except LockUnavailable as exc:
        raise unavailable_error from exc
    except LockOperationError as exc:
        raise operation_error(f"{exc.operation}: {exc.cause}") from exc

    try:
        yield
    finally:
        lock.__exit__(None, None, None)



@contextmanager
def registry_lock(paths: RegistrationUserPaths) -> Iterator[None]:
    """Hold the single global registry lock without trusting file absence."""
    with _application_lock(
        paths.registry_lock_path,
        unavailable_error=registry_error("repository registry is busy"),
        operation_error=registry_error,
    ):
        yield


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
) -> Iterator[None]:
    """Hold one repository lock or fail with the public busy exit code."""
    with _application_lock(
        repository_lock_path(paths, repo_id),
        unavailable_error=repository_busy_error(),
        operation_error=repository_resolution_error,
    ):
        yield
