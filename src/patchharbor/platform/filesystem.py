"""Filesystem adapter for portable target inspection and atomic replacement."""

from __future__ import annotations

from enum import Enum, auto
import errno
import os
from pathlib import Path
import stat
import tempfile


class PathKind(Enum):
    """Portable kinds needed by PatchHarbor's file-writing policy."""

    MISSING = auto()
    REGULAR_FILE = auto()
    DIRECTORY = auto()
    SYMBOLIC_LINK = auto()
    JUNCTION = auto()
    OTHER = auto()


class MetadataSyncStatus(Enum):
    """Observed outcome of one best-effort metadata synchronization."""

    SYNCED = auto()
    UNSUPPORTED = auto()
    FAILED = auto()


class FileSystemOperationError(OSError):
    """One filesystem operation failed below the platform-neutral policy."""

    def __init__(self, operation: str, cause: OSError) -> None:
        super().__init__(operation)
        self.operation = operation
        self.cause = cause


def path_kind(path: Path) -> PathKind:
    """Inspect one path without following symbolic links."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return PathKind.MISSING
    except OSError as exc:
        raise FileSystemOperationError("cannot inspect target", exc) from exc

    junction_check = getattr(path, "is_junction", None)
    try:
        if callable(junction_check) and junction_check():
            return PathKind.JUNCTION
    except OSError as exc:
        raise FileSystemOperationError("cannot inspect target", exc) from exc

    if stat.S_ISLNK(mode):
        return PathKind.SYMBOLIC_LINK
    if stat.S_ISREG(mode):
        return PathKind.REGULAR_FILE
    if stat.S_ISDIR(mode):
        return PathKind.DIRECTORY
    return PathKind.OTHER


def create_directory(path: Path) -> None:
    """Create exactly one directory and expose a stable operation failure."""
    try:
        path.mkdir()
    except OSError as exc:
        raise FileSystemOperationError(
            "cannot create parent directory",
            exc,
        ) from exc


def atomic_replace_bytes(target: Path, content: bytes) -> None:
    """Write bytes beside the target and atomically replace the target."""
    staged_path: Path | None = None
    try:
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=".patchharbor-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                staged_path = Path(handle.name)
                handle.write(content)
        except OSError as exc:
            raise FileSystemOperationError(
                "cannot stage replacement",
                exc,
            ) from exc

        try:
            os.replace(staged_path, target)
        except OSError as exc:
            raise FileSystemOperationError(
                "cannot replace target",
                exc,
            ) from exc
        staged_path = None
    finally:
        if staged_path is not None:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass


_UNSUPPORTED_SYNC_ERRNOS = frozenset(
    error_number
    for error_number in (
        errno.EBADF,
        errno.EINVAL,
        getattr(errno, "ENOTSUP", None),
        getattr(errno, "EOPNOTSUPP", None),
    )
    if error_number is not None
)


def _sync_descriptor_best_effort(path: Path, *, directory: bool) -> MetadataSyncStatus:
    if directory and os.name == "nt":
        return MetadataSyncStatus.UNSUPPORTED

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return MetadataSyncStatus.FAILED

    status = MetadataSyncStatus.SYNCED
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            status = (
                MetadataSyncStatus.UNSUPPORTED
                if exc.errno in _UNSUPPORTED_SYNC_ERRNOS
                else MetadataSyncStatus.FAILED
            )
    finally:
        try:
            os.close(descriptor)
        except OSError:
            if status is MetadataSyncStatus.SYNCED:
                status = MetadataSyncStatus.FAILED
    return status


def sync_regular_file_best_effort(path: Path) -> MetadataSyncStatus:
    """Try to synchronize one closed regular file without promising durability."""
    return _sync_descriptor_best_effort(path, directory=False)


def sync_directory_best_effort(path: Path) -> MetadataSyncStatus:
    """Try to synchronize directory metadata where the platform supports it."""
    return _sync_descriptor_best_effort(path, directory=True)


def replace_path(source: Path, target: Path) -> None:
    """Atomically replace one path and expose a stable operation failure."""
    try:
        os.replace(source, target)
    except OSError as exc:
        raise FileSystemOperationError("cannot replace target", exc) from exc
