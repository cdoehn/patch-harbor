"""Portable advisory file-lock lifecycle for PatchHarbor-owned locks."""

from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import time
from typing import Iterator

from patchharbor.platform.runtime import is_windows


class LockUnavailable(Exception):
    """The requested advisory lock is currently owned by another process."""


class LockOperationError(OSError):
    """One operating-system lock operation failed."""

    def __init__(self, operation: str, cause: OSError) -> None:
        super().__init__(operation)
        self.operation = operation
        self.cause = cause


def _prepare_windows_lock_byte(descriptor: int) -> None:
    if os.fstat(descriptor).st_size == 0:
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, b"\0")
    os.lseek(descriptor, 0, os.SEEK_SET)


def _try_acquire(descriptor: int) -> bool:
    if is_windows():  # pragma: no cover - exercised on Windows CI
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
    if is_windows():  # pragma: no cover - exercised on Windows CI
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


@contextmanager
def exclusive_file_lock(
    path: Path,
    *,
    wait_seconds: float,
    retry_interval_seconds: float = 0.02,
) -> Iterator[None]:
    """Own one advisory lock through a single acquisition and cleanup path."""
    if wait_seconds < 0:
        raise ValueError("wait_seconds must not be negative")
    if retry_interval_seconds <= 0:
        raise ValueError("retry_interval_seconds must be positive")

    descriptor = -1
    acquired = False
    try:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        except OSError as exc:
            raise LockOperationError("cannot open lock file", exc) from exc

        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                acquired = _try_acquire(descriptor)
            except OSError as exc:
                raise LockOperationError("cannot acquire file lock", exc) from exc
            if acquired:
                break

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LockUnavailable
            time.sleep(min(retry_interval_seconds, remaining))

        yield
    finally:
        if descriptor >= 0:
            if acquired:
                try:
                    _release(descriptor)
                except OSError:
                    pass
            try:
                os.close(descriptor)
            except OSError:
                pass
