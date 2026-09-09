"""Pinned directory operations and no-clobber renames for Exchange maintenance.

No copy/unlink fallback: an unsupported atomic rename leaves the source intact.
Windows gets no Hidden attribute; leading dots are ordinary name characters.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
import ctypes
import errno
import os
from pathlib import Path
import stat
import sys

from patchharbor.platform.filesystem import (
    FileChangedDuringRead, PathKind, path_kind, read_stable_regular_file_with_sha256,
    sync_directory_best_effort,
)
from patchharbor.platform.paths import physically_canonicalize
from patchharbor.platform.runtime import is_windows


@dataclass(frozen=True)
class ArchiveLocation:
    exchange: Path
    directory: Path
    exchange_stat: os.stat_result
    directory_stat: os.stat_result
    exchange_fd: int | None = None
    directory_fd: int | None = None

    def revalidate(self) -> None:
        for path, metadata in ((self.exchange, self.exchange_stat),
                               (self.directory, self.directory_stat)):
            if (path_kind(path) is not PathKind.DIRECTORY
                or physically_canonicalize(path, must_exist=True) != path
                or not os.path.samestat(path.lstat(), metadata)):
                raise OSError("archive directory identity changed")
        if self.directory.parent != self.exchange:
            raise OSError("archive must remain a direct Exchange child")


def _open_directory(path: Path, *, parent_fd: int | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    return os.open(path, flags, dir_fd=parent_fd)


def _pin_windows_directory(path: Path) -> tuple[object, object]:
    """Deny delete sharing while maintenance uses this physical directory."""
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    # FILE_READ_ATTRIBUTES, FILE_SHARE_READ|WRITE (not DELETE), OPEN_EXISTING,
    # BACKUP_SEMANTICS|OPEN_REPARSE_POINT. No attributes are changed.
    handle = create(str(path), 0x80, 0x3, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    if path_kind(path) is not PathKind.DIRECTORY:
        close(handle)
        raise OSError("archive directory is a reparse point or not a directory")
    return handle, close


@contextmanager
def open_archive_location(exchange: Path, child_name: str) -> Iterator[ArchiveLocation]:
    """Create/open only a direct, non-link child of the physical Exchange root."""
    if not child_name or child_name in {".", ".."} or any(c in child_name for c in "/\\:\0"):
        raise ValueError("archive location requires a child name, not a path")
    if (not exchange.is_absolute() or path_kind(exchange) is not PathKind.DIRECTORY
        or physically_canonicalize(exchange, must_exist=True) != exchange):
        raise OSError("Exchange root is not a stable physical directory")
    archive = exchange / child_name
    with ExitStack() as stack:
        root_stat = exchange.lstat()
        if is_windows():
            # Pin ancestors as well, so an ancestor rename cannot redirect the
            # absolute Windows path while the handles are open.
            for parent in reversed((exchange, *exchange.parents)):
                handle, close = _pin_windows_directory(parent)
                stack.callback(close, handle)
            try:
                archive.mkdir()
            except FileExistsError:
                pass
            if path_kind(archive) is not PathKind.DIRECTORY:
                raise OSError("archive child must not be a link, junction or file")
            handle, close = _pin_windows_directory(archive)
            stack.callback(close, handle)
            location = ArchiveLocation(exchange, archive, root_stat, archive.lstat())
        else:
            root_fd = _open_directory(exchange)
            stack.callback(os.close, root_fd)
            if not os.path.samestat(os.fstat(root_fd), root_stat):
                raise OSError("Exchange root changed while opening it")
            try:
                os.mkdir(child_name, mode=0o755, dir_fd=root_fd)
            except FileExistsError:
                pass
            child_fd = _open_directory(Path(child_name), parent_fd=root_fd)
            stack.callback(os.close, child_fd)
            location = ArchiveLocation(exchange, archive, root_stat, os.fstat(child_fd),
                                       root_fd, child_fd)
        location.revalidate()
        yield location


def _rename_no_replace(location: ArchiveLocation, source_name: str, target_name: str) -> None:
    if is_windows():
        # os.rename on Windows fails if the target exists; never os.replace.
        os.rename(location.exchange / source_name, location.directory / target_name)
        return
    if not sys.platform.startswith("linux"):
        raise OSError(errno.ENOTSUP, "no safe no-replace rename on this platform")
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise OSError(errno.ENOTSUP, "renameat2 is unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(location.exchange_fd, os.fsencode(source_name), location.directory_fd,
              os.fsencode(target_name), 1) != 0:  # RENAME_NOREPLACE
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), str(location.directory / target_name))


def move_archive_file(
    location: ArchiveLocation, source: Path, *, target_name: str, expected_sha256: str,
    verify_eligibility: Callable[[], None],
) -> Path:
    """Rehash the source, recheck pinned directories, then rename without replacing."""
    if (source.parent != location.exchange or Path(target_name).name != target_name
        or not target_name or any(c in target_name for c in "/\\:\0")
        or target_name in {".", ".."}):
        raise ValueError("archive move must stay within its pinned directories")
    location.revalidate()
    if path_kind(source) is not PathKind.REGULAR_FILE:
        raise OSError("archive source is not a regular file")
    before = source.lstat()
    snapshot = read_stable_regular_file_with_sha256(
        source, retained_content_limit=1, allow_path_identity_fallback=True,
    )
    after = source.lstat()
    if (
        snapshot.sha256 != expected_sha256
        or not stat.S_ISREG(after.st_mode)
        or not os.path.samestat(before, after)
        or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    ):
        raise FileChangedDuringRead
    verify_eligibility()
    location.revalidate()
    final = source.lstat()
    if (not os.path.samestat(after, final)
        or not stat.S_ISREG(final.st_mode)
        or (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        != (final.st_size, final.st_mtime_ns, final.st_ctime_ns)):
        raise FileChangedDuringRead
    _rename_no_replace(location, source.name, target_name)
    sync_directory_best_effort(location.directory)
    sync_directory_best_effort(location.exchange)
    return location.directory / target_name
