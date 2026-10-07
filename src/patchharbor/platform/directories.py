"""Shared read-only directory handles for bounded, anchored filesystem operations."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

from patchharbor.platform.filesystem import PathKind, path_kind


def open_directory_nofollow(path: Path, *, parent_fd: int | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    return os.open(path, flags, dir_fd=parent_fd)


def pin_windows_directory(path: Path) -> tuple[object, object]:
    """Deny delete sharing while an operation uses this physical directory."""
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
        raise OSError("directory is a reparse point or not a directory")
    return handle, close
