"""Exclusive process-safe lock for one registered repository identity."""

from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import time
from typing import Iterator

from patchharbor.errors import (
    repository_busy_error,
    repository_resolution_error,
)
from patchharbor.models import RepositoryId
from patchharbor.user_paths import RegistrationUserPaths


DEFAULT_REPOSITORY_LOCK_WAIT_SECONDS = 2.0
_RETRY_INTERVAL_SECONDS = 0.02


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


def _prepare_windows_lock_byte(descriptor: int) -> None:
    if os.fstat(descriptor).st_size == 0:
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, b"\0")
    os.lseek(descriptor, 0, os.SEEK_SET)


def _try_acquire(descriptor: int) -> bool:
    if os.name == "nt":
        import msvcrt

        _prepare_windows_lock_byte(descriptor)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return False
            raise
        return True

    import fcntl

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _release(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


@contextmanager
def repository_lock(
    paths: RegistrationUserPaths,
    repo_id: RepositoryId,
    *,
    wait_seconds: float = DEFAULT_REPOSITORY_LOCK_WAIT_SECONDS,
) -> Iterator[None]:
    """Hold one repository lock or fail with the public busy exit code."""
    if wait_seconds < 0:
        raise ValueError("wait_seconds must not be negative")

    lock_path = repository_lock_path(paths, repo_id)
    descriptor = -1
    acquired = False
    try:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_RDWR,
                0o600,
            )
        except OSError as exc:
            raise repository_resolution_error(
                f"cannot open repository lock: {exc}"
            ) from exc

        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                acquired = _try_acquire(descriptor)
            except OSError as exc:
                raise repository_resolution_error(
                    f"cannot acquire repository lock: {exc}"
                ) from exc
            if acquired:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise repository_busy_error()
            time.sleep(min(_RETRY_INTERVAL_SECONDS, remaining))

        yield
    finally:
        if descriptor >= 0:
            if acquired:
                try:
                    _release(descriptor)
                except OSError:
                    pass
            os.close(descriptor)
