"""Stable public descriptions for operating-system failures."""

from __future__ import annotations

import errno


def describe_os_error(error: OSError) -> str:
    """Return a platform-neutral semantic description for one OS failure."""
    error_number = getattr(error, "errno", None)
    if isinstance(error, PermissionError) or error_number in {
        errno.EACCES,
        errno.EPERM,
    }:
        return "permission denied"
    if isinstance(error, FileNotFoundError) or error_number == errno.ENOENT:
        return "path not found"
    if isinstance(error, FileExistsError) or error_number == errno.EEXIST:
        return "path already exists"
    if isinstance(error, NotADirectoryError) or error_number == errno.ENOTDIR:
        return "parent is not a directory"
    if isinstance(error, IsADirectoryError) or error_number == errno.EISDIR:
        return "target is a directory"
    if isinstance(error, TimeoutError) or error_number == errno.ETIMEDOUT:
        return "operation timed out"
    if error_number == errno.ENOSPC:
        return "no space left on device"
    if error_number == errno.EROFS:
        return "read-only filesystem"
    if error_number == errno.ENAMETOOLONG:
        return "path is too long"
    if error_number == errno.EBUSY:
        return "resource is busy"
    return "operating-system operation failed"
