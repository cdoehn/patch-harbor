"""Open existing regular files without following a leaf symlink or reparse point."""
from __future__ import annotations

import errno
import os
from pathlib import Path
import stat

from patchharbor.platform.runtime import is_windows


def _windows_open(path: Path, *, writable: bool, publication: bool = False) -> int:
    import ctypes
    from ctypes import wintypes
    import msvcrt

    class AttributeTag(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    info = kernel.GetFileInformationByHandleEx
    info.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    info.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    access = 0x80000000 | (0x40000000 if writable else 0)  # GENERIC_READ / WRITE
    if publication:
        access |= 0x00010000  # DELETE: rename exactly this pinned file handle.
    handle = create(str(path), access, 1 if publication else 7, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = AttributeTag()
        if not info(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        if attributes.attributes & (0x400 | 0x10):  # REPARSE_POINT / DIRECTORY
            raise OSError(errno.ELOOP, "regular non-reparse file required")
        flags = os.O_BINARY | (os.O_RDWR if writable else os.O_RDONLY)
        descriptor = msvcrt.open_osfhandle(handle, flags)
        handle = None  # Ownership transfers to the CRT descriptor.
        return descriptor
    finally:
        if handle is not None:
            close(handle)


def open_regular_nofollow(path: Path, *, writable: bool = False, parent_fd: int | None = None,
                         publication: bool = False) -> int:
    """Return an owned descriptor; reject special files before any content I/O."""
    metadata = (path.lstat() if parent_fd is None
                else os.stat(path, dir_fd=parent_fd, follow_symlinks=False))
    if not stat.S_ISREG(metadata.st_mode):
        raise OSError(errno.EINVAL, "regular non-link file required")
    if is_windows():
        if parent_fd is not None:
            raise ValueError("relative directory descriptors are unavailable on Windows")
        descriptor = (_windows_open(path, writable=writable, publication=True) if publication
                      else _windows_open(path, writable=writable))
    else:
        flags = os.O_RDWR if writable else os.O_RDONLY
        flags |= os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
        descriptor = (os.open(path, flags) if parent_fd is None
                      else os.open(path, flags, dir_fd=parent_fd))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(errno.EINVAL, "opened target is not a regular file")
        os.set_inheritable(descriptor, False)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise
