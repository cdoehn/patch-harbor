"""Create private directories atomically, including older Windows Pythons."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import secrets
import tempfile

from patchharbor.platform.runtime import is_windows


def _windows_create_private_directory(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", ctypes.c_void_p),
                    ("inherit", wintypes.BOOL)]

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)

    def function(library, name, result, args):
        fn = getattr(library, name)
        fn.restype, fn.argtypes = result, args
        return fn

    close = function(kernel, "CloseHandle", wintypes.BOOL, [wintypes.HANDLE])
    free = function(kernel, "LocalFree", ctypes.c_void_p, [ctypes.c_void_p])
    thread = function(kernel, "GetCurrentThread", wintypes.HANDLE, [])
    process = function(kernel, "GetCurrentProcess", wintypes.HANDLE, [])
    open_thread = function(security, "OpenThreadToken", wintypes.BOOL,
                           [wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER(wintypes.HANDLE)])
    open_process = function(security, "OpenProcessToken", wintypes.BOOL,
                            [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)])
    token_info = function(security, "GetTokenInformation", wintypes.BOOL,
                          [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                           ctypes.POINTER(wintypes.DWORD)])
    sid_text = function(security, "ConvertSidToStringSidW", wintypes.BOOL,
                        [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)])
    convert = function(security, "ConvertStringSecurityDescriptorToSecurityDescriptorW", wintypes.BOOL,
                       [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
                        ctypes.POINTER(wintypes.DWORD)])
    create = function(kernel, "CreateDirectoryW", wintypes.BOOL,
                      [wintypes.LPCWSTR, ctypes.POINTER(SecurityAttributes)])
    with ExitStack() as stack:
        token = wintypes.HANDLE()
        if not open_thread(thread(), 0x8, True, ctypes.byref(token)):  # TOKEN_QUERY
            if ctypes.get_last_error() != 1008:  # ERROR_NO_TOKEN only
                raise ctypes.WinError(ctypes.get_last_error())
            if not open_process(process(), 0x8, ctypes.byref(token)):
                raise ctypes.WinError(ctypes.get_last_error())
        stack.callback(close, token)
        size = wintypes.DWORD()
        if token_info(token, 1, None, 0, ctypes.byref(size)) or ctypes.get_last_error() != 122:
            raise ctypes.WinError(ctypes.get_last_error())  # ERROR_INSUFFICIENT_BUFFER
        buffer = ctypes.create_string_buffer(size.value)
        if not token_info(token, 1, buffer, size, ctypes.byref(size)):  # TokenUser
            raise ctypes.WinError(ctypes.get_last_error())
        user = SidAndAttributes.from_buffer(buffer)
        sid = wintypes.LPWSTR()
        if not sid_text(user.sid, ctypes.byref(sid)):
            raise ctypes.WinError(ctypes.get_last_error())
        stack.callback(free, sid)
        # Protected DACL; only this effective user and administrators, inherited
        # by files/subdirectories. No permissive-create / later chmod interval.
        sddl = "D:P(A;OICI;FA;;;" + sid.value + ")(A;OICI;FA;;;BA)"
        descriptor = ctypes.c_void_p()
        if not convert(sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        stack.callback(free, descriptor)
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        if not create(str(path), ctypes.byref(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())


def create_private_directory(path: Path) -> None:
    """Create exactly one absent directory; never change existing ACLs."""
    if is_windows():
        _windows_create_private_directory(path)
    else:
        path.mkdir(mode=0o700)


def create_private_temporary_directory(root: Path, prefix: str) -> Path:
    if not is_windows():
        return Path(tempfile.mkdtemp(prefix=prefix, dir=root))
    for _ in range(100):
        path = root / (prefix + secrets.token_hex(16))
        try:
            create_private_directory(path)
        except FileExistsError:
            continue
        return path
    raise FileExistsError("cannot reserve a private request directory")
