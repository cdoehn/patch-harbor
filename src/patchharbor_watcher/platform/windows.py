"""Flat ReadDirectoryChangesW subscriptions on one I/O completion port.

Imports safely on other platforms. Pending buffers/OVERLAPPED objects remain
alive until cancellation has completed; closing a source wakes its idle reader.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
import math
from pathlib import Path
import stat
import struct
import sys

from patchharbor_watcher.events import (
    DirectoryEvent, EventBackendError, EventBatch, EventErrorKind, EventKind,
    SourceLifecycle, WatchPlan, deadline_for, remaining,
)

_DWORD = ctypes.c_uint32
_BOOL = ctypes.c_int32
_HANDLE = ctypes.c_void_p
_ULONG_PTR = ctypes.c_size_t
_BUFFER_BYTES = 65536
_FILTER = 0x01 | 0x02 | 0x04 | 0x08 | 0x10 | 0x100  # Never LAST_ACCESS.
_HEADER = struct.Struct("<III")


class _Overlapped(ctypes.Structure):
    _fields_ = [("Internal", _ULONG_PTR), ("InternalHigh", _ULONG_PTR),
                ("Offset", _DWORD), ("OffsetHigh", _DWORD), ("hEvent", _HANDLE)]


def decode_events(data: bytes) -> tuple[tuple[int, str], ...]:
    """Decode a bounded FILE_NOTIFY_INFORMATION chain, rejecting bad offsets."""
    result = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < _HEADER.size:
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "truncated Windows event header")
        following, action, size = _HEADER.unpack_from(data, offset)
        end = offset + _HEADER.size + size
        if not size or size % 2 or end > len(data) or action not in (1, 2, 3, 4, 5):
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "invalid Windows event record")
        name = data[offset + _HEADER.size:end].decode("utf-16-le", errors="surrogatepass")
        if name in (".", "..") or any(char in name for char in ("/", "\\", "\0")):
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "non-flat Windows event name")
        result.append((action, name))
        if not following:
            # A final record may include DWORD alignment padding only.
            if len(data) - end > 3:
                raise EventBackendError(EventErrorKind.INVALID_EVENT, "trailing Windows event data")
            return tuple(result)
        if following % 4 or following < _HEADER.size + size or offset + following >= len(data):
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "invalid Windows event offset")
        offset += following
    return tuple(result)


def _native_error(message: str, code: int) -> EventBackendError:
    kind = EventErrorKind.UNSUPPORTED if code in (1, 50, 120) else EventErrorKind.IO
    return EventBackendError(kind, message, native_code=code)


class _Kernel32:
    """Only this boundary loads Win32; fixed-width structures are testable elsewhere."""
    def __init__(self):
        if sys.platform != "win32":
            raise EventBackendError(EventErrorKind.UNSUPPORTED, "directory completion ports require Windows")
        self.dll = ctypes.WinDLL("kernel32", use_last_error=True)
        pointer = ctypes.POINTER(_Overlapped)
        declarations = {
            "CreateFileW": ([ctypes.c_wchar_p, _DWORD, _DWORD, _HANDLE, _DWORD, _DWORD, _HANDLE], _HANDLE),
            "CreateIoCompletionPort": ([_HANDLE, _HANDLE, _ULONG_PTR, _DWORD], _HANDLE),
            "ReadDirectoryChangesW": ([_HANDLE, _HANDLE, _DWORD, _BOOL, _DWORD,
                                        ctypes.POINTER(_DWORD), pointer, _HANDLE], _BOOL),
            "GetQueuedCompletionStatus": ([_HANDLE, ctypes.POINTER(_DWORD), ctypes.POINTER(_ULONG_PTR),
                                            ctypes.POINTER(pointer), _DWORD], _BOOL),
            "PostQueuedCompletionStatus": ([_HANDLE, _DWORD, _ULONG_PTR, pointer], _BOOL),
            "CancelIoEx": ([_HANDLE, pointer], _BOOL),
            "CloseHandle": ([_HANDLE], _BOOL),
        }
        for name, (arguments, result) in declarations.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = arguments, result

    def create_port(self):
        port = self.dll.CreateIoCompletionPort(_HANDLE(-1), None, 0, 1)
        if not port:
            raise _native_error("cannot create completion port", ctypes.get_last_error())
        return port

    def open(self, directory: Path):
        handle = self.dll.CreateFileW(str(directory), 0x0001, 0x0007, None, 3,
                                     0x02000000 | 0x40000000 | 0x00200000, None)
        if handle == _HANDLE(-1).value:
            raise _native_error("cannot open directory event handle", ctypes.get_last_error())
        return handle

    def associate(self, handle, port, key):
        if not self.dll.CreateIoCompletionPort(handle, port, key, 0):
            raise _native_error("cannot associate event handle", ctypes.get_last_error())

    def arm(self, watch):
        ctypes.memset(ctypes.byref(watch.overlapped), 0, ctypes.sizeof(watch.overlapped))
        # Keep ownership if a Python interruption follows a successful native
        # queue operation, before control returns from the ctypes call.
        watch.pending = True
        if not self.dll.ReadDirectoryChangesW(watch.handle, watch.buffer, _BUFFER_BYTES,
                False, _FILTER, None, ctypes.byref(watch.overlapped), None):
            watch.pending = False
            raise _native_error("cannot subscribe to directory changes", ctypes.get_last_error())

    def receive(self, port, timeout):
        count, key, overlapped = _DWORD(), _ULONG_PTR(), ctypes.POINTER(_Overlapped)()
        milliseconds = 0xFFFFFFFF if timeout is None else min(0xFFFFFFFE, math.ceil(timeout * 1000))
        success = self.dll.GetQueuedCompletionStatus(port, ctypes.byref(count), ctypes.byref(key),
                                                    ctypes.byref(overlapped), milliseconds)
        error = 0 if success else ctypes.get_last_error()
        address = ctypes.cast(overlapped, _HANDLE).value
        if not success and address is None:
            if error == 258:  # WAIT_TIMEOUT; count/key are undefined.
                return None
            raise _native_error("completion port receive failed", error)
        return key.value, count.value, error, address

    def wake(self, port):
        if not self.dll.PostQueuedCompletionStatus(port, 0, 0, None):
            raise _native_error("cannot wake completion port", ctypes.get_last_error())

    def cancel(self, watch):
        if watch.pending:
            # Cancellation only requests completion. NOT_FOUND means the
            # operation already completed; its IOCP packet must still be read.
            cancelled = self.dll.CancelIoEx(watch.handle, ctypes.byref(watch.overlapped))
            error = 0 if cancelled else ctypes.get_last_error()
            if error not in (0, 1168):
                raise _native_error("cannot cancel directory events", error)

    def close(self, handle):
        if not self.dll.CloseHandle(handle):
            raise _native_error("cannot close event handle", ctypes.get_last_error())


@dataclass
class _Watch:
    directory: Path
    handle: object
    buffer: object = field(default_factory=lambda: (_DWORD * (_BUFFER_BYTES // 4))())
    overlapped: _Overlapped = field(default_factory=_Overlapped)
    pending: bool = False


class WindowsEventSource(SourceLifecycle):
    def __init__(self, directories: tuple[Path, ...], *, _kernel=None):
        super().__init__()
        self._kernel = _Kernel32() if _kernel is None else _kernel
        self._plan = WatchPlan(directories)
        self._port = None
        self._watches: dict[int, _Watch] = {}
        self._wake_pending = False
        try:
            self._port = self._kernel.create_port()
            for key, directory in enumerate(self._plan.directories, 1):
                watch = _Watch(directory, self._kernel.open(directory))
                self._watches[key] = watch  # Own the handle before any fallible operation.
                self._kernel.associate(watch.handle, self._port, key)
                self._kernel.arm(watch)
            self._plan.revalidate()
        except BaseException:
            self._dispose()
            raise

    def _completed_watch(self, completion):
        key, _, error, address = completion
        if key == 0 and address is None and not error:
            with self._state:
                self._wake_pending = False
            return None
        watch = self._watches.get(key)
        if watch is None or address != ctypes.addressof(watch.overlapped) or not watch.pending:
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "unknown directory completion")
        # Receipt, including ERROR_OPERATION_ABORTED, ends native ownership.
        # Do this even if a concurrent close has already set _closing.
        watch.pending = False
        return watch

    def read(self, timeout: float | None = None) -> tuple[DirectoryEvent, ...]:
        deadline = deadline_for(timeout)
        with self._reader:
            while not self._closing:
                completion = self._kernel.receive(self._port, remaining(deadline))
                if completion is None:
                    return ()
                watch = self._completed_watch(completion)
                if watch is None or self._closing:
                    return ()
                _, count, error, _ = completion
                if error in (2, 3, 5):
                    return self._plan.invalidated(watch.directory)
                if error not in (0, 1022):  # ERROR_NOTIFY_ENUM_DIR is lost notification data.
                    raise _native_error("directory event request failed", error)
                if count > _BUFFER_BYTES:
                    raise EventBackendError(EventErrorKind.INVALID_EVENT, "oversized directory completion")
                # Copy before rearming: the OS may immediately reuse this buffer.
                data = ctypes.string_at(watch.buffer, count) if not error else b""
                with self._state:
                    if not self._closing:
                        self._kernel.arm(watch)
                if error == 1022 or count == 0:
                    return tuple(DirectoryEvent(EventKind.OVERFLOW, event.directory)
                                 for event in self._plan.invalidated(watch.directory))
                batch = EventBatch()
                for action, name in decode_events(data):
                    directory_metadata = False
                    if action == 3:
                        try:
                            directory_metadata = stat.S_ISDIR((watch.directory / name).lstat().st_mode)
                        except OSError:
                            pass  # Disappearance is relevant; do not suppress it.
                    batch.add(self._plan.route(watch.directory, name, membership=action != 3,
                                               child_directory_metadata=directory_metadata))
                if batch.result():
                    return batch.result()
                if timeout != 0 and deadline is not None and remaining(deadline) == 0:
                    return ()
            return ()

    def wake(self) -> None:
        with self._state:
            if self._port is not None and not self._wake_pending:
                self._kernel.wake(self._port)
                self._wake_pending = True

    def _dispose(self) -> None:
        failures = []
        for watch in self._watches.values():
            try:
                self._kernel.cancel(watch)
            except EventBackendError as exc:
                failures.append(exc)
        # IOCP requests complete through this port, not GetOverlappedResult on
        # the directory handle. Drain both cancellations and requests which
        # completed before CancelIoEx; never rearm while disposing.
        while any(watch.pending for watch in self._watches.values()):
            completion = self._kernel.receive(self._port, None)
            if completion is not None:
                self._completed_watch(completion)
        for key, watch in tuple(self._watches.items()):
            if not watch.pending:
                try:
                    self._kernel.close(watch.handle)
                    del self._watches[key]
                except EventBackendError as exc:
                    failures.append(exc)
        with self._state:
            if self._port is not None and not self._watches:
                self._kernel.close(self._port)
                self._port = None
            self._closed = self._port is None
        if failures:
            raise failures[0]

    def close(self) -> None:
        with self._closer:
            if self._closed:
                return
            self._closing = True
            self.wake()
            with self._reader:
                self._dispose()
