"""Filesystem adapter for portable target inspection and atomic replacement."""

from __future__ import annotations

from enum import Enum, auto
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
