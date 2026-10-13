"""Windows creation/change times from an already owned file handle."""
from __future__ import annotations

from dataclasses import dataclass
import os
import sys

from patchharbor.platform.runtime import is_windows


def legacy_windows_stat() -> bool:
    """Only CPython before 3.12 lacks a separate creation-time stat field."""
    return is_windows() and sys.version_info < (3, 12)


def windows_creation_time(metadata: os.stat_result) -> int:
    birth = getattr(metadata, "st_birthtime_ns", None)
    if birth is not None:
        return birth
    if legacy_windows_stat():
        # CPython 3.10/3.11 path stat exposes FILETIME creation in st_ctime.
        # This value must never be used as the handle's change-time proof.
        return metadata.st_ctime_ns
    raise OSError("Windows creation-time metadata is unavailable")


@dataclass(frozen=True)
class WindowsFileTimes:
    creation_ns: int
    write_ns: int
    change_ns: int
    attributes: int


@dataclass(frozen=True)
class WindowsDescriptorMetadata:
    """Keep native identity/size/mode; expose separate birth and change times."""
    original: os.stat_result
    st_birthtime_ns: int
    st_ctime_ns: int

    def __getattr__(self, name):
        return getattr(self.original, name)

    @property
    def st_birthtime(self) -> float:
        return self.st_birthtime_ns / 1_000_000_000

    @property
    def st_ctime(self) -> float:
        return self.st_ctime_ns / 1_000_000_000


def windows_file_times(descriptor: int) -> WindowsFileTimes:
    """Read FILE_BASIC_INFO without reopening a pathname or changing a file."""
    import ctypes
    from ctypes import wintypes
    import msvcrt

    class BasicInfo(ctypes.Structure):
        _fields_ = [("creation", ctypes.c_longlong), ("access", ctypes.c_longlong),
                    ("write", ctypes.c_longlong), ("change", ctypes.c_longlong),
                    ("attributes", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel.GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    query.restype = wintypes.BOOL
    info = BasicInfo()
    if not query(msvcrt.get_osfhandle(descriptor), 0, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    # FILETIME units are 100 ns since 1601; use integer conversion throughout.
    epoch_ns = 11644473600 * 1_000_000_000
    return WindowsFileTimes(info.creation * 100 - epoch_ns, info.write * 100 - epoch_ns,
                            info.change * 100 - epoch_ns, info.attributes)
