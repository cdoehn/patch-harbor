"""Filesystem adapter for portable target inspection and atomic replacement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from hashlib import sha256
import errno
import os
from pathlib import Path
import stat
import tempfile

from patchharbor.platform.runtime import is_windows


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


class FileChangedDuringRead(RuntimeError):
    """A path no longer identifies the same regular file during one read."""


class UnsupportedFileTypeError(RuntimeError):
    """A path at a regular-file boundary has an unsupported type."""


@dataclass(frozen=True, slots=True)
class StableRegularFile:
    """Byte-exact content and portable executable state of one stable file."""

    content: bytes
    executable: bool


@dataclass(frozen=True, slots=True)
class StableRegularFileHash:
    """Stable full-file identity with content retained only below one limit."""

    content: bytes | None
    executable: bool
    size: int
    sha256: str


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


def _path_and_descriptor_signature(metadata: os.stat_result) -> tuple[int, ...]:
    common = (
        stat.S_IFMT(metadata.st_mode),
        metadata.st_size,
        metadata.st_mtime_ns,
    )
    if is_windows():
        # Windows path stat and descriptor fstat expose different ctime
        # semantics; birth time is stable across both views of one file.
        return (*common, metadata.st_birthtime_ns)
    return (*common, stat.S_IMODE(metadata.st_mode), metadata.st_ctime_ns)


def _descriptor_signature(metadata: os.stat_result) -> tuple[int, ...]:
    common = _path_and_descriptor_signature(metadata)
    if is_windows():
        # Descriptor ctime is the Windows change time and catches mutation
        # while the file remains open.
        return (*common, metadata.st_ctime_ns)
    return common


def _portable_content_signature(metadata: os.stat_result) -> tuple[int, ...]:
    """Metadata that path and descriptor views should expose consistently."""
    return (
        stat.S_IFMT(metadata.st_mode),
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _same_path_and_open_file_state(
    path_metadata: os.stat_result,
    opened_metadata: os.stat_result,
    *,
    allow_path_identity_fallback: bool,
) -> bool:
    if os.path.samestat(path_metadata, opened_metadata) and (
        _path_and_descriptor_signature(path_metadata)
        == _path_and_descriptor_signature(opened_metadata)
    ):
        return True
    return allow_path_identity_fallback and (
        _portable_content_signature(path_metadata)
        == _portable_content_signature(opened_metadata)
    )


def _same_open_file_state(
    first: os.stat_result,
    second: os.stat_result,
) -> bool:
    return os.path.samestat(first, second) and (
        _descriptor_signature(first) == _descriptor_signature(second)
    )


def _inspect_path_without_following(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise FileSystemOperationError("cannot inspect target", exc) from exc


def _require_regular_file(metadata: os.stat_result) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        raise UnsupportedFileTypeError


def _regular_path_metadata(path: Path) -> os.stat_result:
    metadata = _inspect_path_without_following(path)
    if metadata is None:
        raise FileChangedDuringRead
    _require_regular_file(metadata)
    return metadata


def _read_stable_regular_file(
    path: Path,
    *,
    retained_content_limit: int | None,
    calculate_sha256: bool,
    allow_path_identity_fallback: bool,
) -> tuple[bytes | None, bool, int, str | None]:
    initial_metadata = _regular_path_metadata(path)

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened_metadata = os.fstat(descriptor)
        _require_regular_file(opened_metadata)
        if not _same_path_and_open_file_state(
            initial_metadata,
            opened_metadata,
            allow_path_identity_fallback=allow_path_identity_fallback,
        ):
            raise FileChangedDuringRead

        current_metadata = _regular_path_metadata(path)
        if not _same_path_and_open_file_state(
            current_metadata,
            opened_metadata,
            allow_path_identity_fallback=allow_path_identity_fallback,
        ):
            raise FileChangedDuringRead

        hasher = sha256() if calculate_sha256 else None
        retained: bytearray | None = bytearray()
        size = 0
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            while chunk := handle.read(1024 * 1024):
                size += len(chunk)
                if hasher is not None:
                    hasher.update(chunk)
                if retained is not None:
                    if (
                        retained_content_limit is None
                        or size <= retained_content_limit
                    ):
                        retained.extend(chunk)
                    else:
                        retained = None
            finished_metadata = os.fstat(handle.fileno())
    except (FileChangedDuringRead, UnsupportedFileTypeError):
        raise
    except OSError as exc:
        raise FileSystemOperationError("cannot read target", exc) from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass

    final_metadata = _regular_path_metadata(path)
    if (
        not _same_open_file_state(opened_metadata, finished_metadata)
        or not _same_path_and_open_file_state(
            final_metadata,
            finished_metadata,
            allow_path_identity_fallback=allow_path_identity_fallback,
        )
        or size != finished_metadata.st_size
    ):
        raise FileChangedDuringRead

    return (
        bytes(retained) if retained is not None else None,
        bool(finished_metadata.st_mode & 0o111),
        size,
        hasher.hexdigest() if hasher is not None else None,
    )


def read_stable_regular_file(path: Path) -> StableRegularFile:
    """Read one regular file without following links and reject path races."""
    content, executable, _size, _digest = _read_stable_regular_file(
        path,
        retained_content_limit=None,
        calculate_sha256=False,
        allow_path_identity_fallback=False,
    )
    if content is None:
        raise RuntimeError("unlimited stable file read discarded its content")
    return StableRegularFile(content=content, executable=executable)


def read_stable_regular_file_with_sha256(
    path: Path,
    *,
    retained_content_limit: int,
    allow_path_identity_fallback: bool = False,
) -> StableRegularFileHash:
    """Hash a stable regular file while bounding retained in-memory content.

    The opt-in fallback accepts matching type, size, and mtime when a virtual
    filesystem does not expose comparable path and descriptor identities. It
    remains unsuitable as a sole trust decision and is reserved for callers
    that subsequently re-open and verify the complete content hash.
    """
    if (
        isinstance(retained_content_limit, bool)
        or not isinstance(retained_content_limit, int)
        or retained_content_limit <= 0
    ):
        raise ValueError("retained_content_limit must be a positive integer")
    content, executable, size, digest = _read_stable_regular_file(
        path,
        retained_content_limit=retained_content_limit,
        calculate_sha256=True,
        allow_path_identity_fallback=allow_path_identity_fallback,
    )
    if digest is None:
        raise RuntimeError("stable hashed file read did not produce a digest")
    return StableRegularFileHash(
        content=content,
        executable=executable,
        size=size,
        sha256=digest,
    )


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


def _sync_descriptor_best_effort(
    path: Path,
    *,
    directory: bool,
) -> MetadataSyncStatus:
    if directory and is_windows():
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
