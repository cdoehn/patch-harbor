"""Nonrecursive inotify receiver, interrupted through a private wake pipe."""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import selectors
import struct
import sys

from patchharbor_watcher.events import (
    DirectoryEvent, EventBackendError, EventBatch, EventErrorKind, EventKind,
    SourceLifecycle, WatchPlan, deadline_for, remaining,
)

IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_UNMOUNT = 0x00002000
IN_Q_OVERFLOW = 0x00004000
IN_IGNORED = 0x00008000
IN_ONLYDIR = 0x01000000
IN_DONT_FOLLOW = 0x02000000
IN_ISDIR = 0x40000000
MEMBERSHIP = IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE
CHANGES = IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE | MEMBERSHIP
INVALIDATED = IN_DELETE_SELF | IN_MOVE_SELF | IN_UNMOUNT | IN_IGNORED
WATCH_MASK = CHANGES | IN_DELETE_SELF | IN_MOVE_SELF | IN_ONLYDIR | IN_DONT_FOLLOW
_HEADER = struct.Struct("=iIII")


def decode_events(data: bytes) -> tuple[tuple[int, int, str | None], ...]:
    """Validate every complete kernel record, keeping undecodable POSIX names."""
    events = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < _HEADER.size:
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "truncated inotify header")
        wd, mask, _cookie, length = _HEADER.unpack_from(data, offset)
        offset += _HEADER.size
        if length > len(data) - offset:
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "truncated inotify name")
        raw = data[offset:offset + length]
        offset += length
        if raw and (b"\0" not in raw or b"/" in raw.split(b"\0", 1)[0]):
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "invalid inotify name")
        name = raw.split(b"\0", 1)[0].decode(sys.getfilesystemencoding(), errors="surrogateescape") if raw else None
        if name in ("", ".", ".."):
            raise EventBackendError(EventErrorKind.INVALID_EVENT, "invalid inotify entry")
        events.append((wd, mask, name))
    return tuple(events)


class LinuxEventSource(SourceLifecycle):
    def __init__(self, directories: tuple[Path, ...]):
        super().__init__()
        if not sys.platform.startswith("linux"):
            raise EventBackendError(EventErrorKind.UNSUPPORTED, "inotify requires Linux")
        self._plan = WatchPlan(directories)
        self._fd = self._wake_read = self._wake_write = -1
        self._selector = None
        self._watches: dict[int, Path] = {}
        try:
            self._selector = selectors.DefaultSelector()
            libc = ctypes.CDLL(None, use_errno=True)
            init = libc.inotify_init1
            init.argtypes, init.restype = [ctypes.c_int], ctypes.c_int
            add = libc.inotify_add_watch
            add.argtypes, add.restype = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32], ctypes.c_int
            self._fd = init(os.O_NONBLOCK | os.O_CLOEXEC)
            if self._fd < 0:
                raise OSError(ctypes.get_errno(), "inotify_init1 failed")
            self._wake_read, self._wake_write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
            self._selector.register(self._fd, selectors.EVENT_READ)
            self._selector.register(self._wake_read, selectors.EVENT_READ)
            for directory in self._plan.directories:
                wd = add(self._fd, os.fsencode(directory), WATCH_MASK)
                if wd < 0:
                    raise OSError(ctypes.get_errno(), "inotify_add_watch failed")
                if wd in self._watches and self._watches[wd] != directory:
                    raise EventBackendError(EventErrorKind.INVALID_TARGET, "ambiguous physical watch alias")
                self._watches[wd] = directory
            self._plan.revalidate()
        except BaseException as exc:
            self._dispose()
            if isinstance(exc, AttributeError):
                raise EventBackendError(EventErrorKind.UNSUPPORTED, "inotify API is unavailable") from exc
            if isinstance(exc, OSError):
                kind = EventErrorKind.UNSUPPORTED if exc.errno in (errno.ENOSYS, errno.ENOTSUP) else EventErrorKind.IO
                raise EventBackendError(kind, "cannot initialize inotify", native_code=exc.errno) from exc
            raise

    def read(self, timeout: float | None = None) -> tuple[DirectoryEvent, ...]:
        deadline = deadline_for(timeout)
        with self._reader:
            try:
                while not self._closing:
                    ready = self._selector.select(remaining(deadline))
                    if not ready or self._closing:
                        return ()
                    if any(key.fd == self._wake_read for key, _ in ready):
                        try:
                            os.read(self._wake_read, 65536)
                        except BlockingIOError:
                            pass
                        return ()
                    batch = EventBatch()
                    try:
                        data = os.read(self._fd, 65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        raise EventBackendError(EventErrorKind.IO, "inotify stream ended")
                    for wd, mask, name in decode_events(data):
                        if mask & IN_Q_OVERFLOW:
                            batch.add((DirectoryEvent(EventKind.OVERFLOW, None),))
                            continue
                        directory = self._watches.get(wd)
                        if directory is None:
                            raise EventBackendError(EventErrorKind.INVALID_EVENT, "unknown inotify watch")
                        if mask & INVALIDATED:
                            batch.add(self._plan.invalidated(directory))
                        elif mask & CHANGES:
                            batch.add(self._plan.route(directory, name, membership=bool(mask & MEMBERSHIP),
                                child_directory_metadata=bool(name and mask & IN_ISDIR and not mask & (MEMBERSHIP | IN_ATTRIB))))
                    if batch.result():
                        return batch.result()
                    if deadline is not None and remaining(deadline) == 0:
                        return ()
            except OSError as exc:
                if not self._closing:
                    raise EventBackendError(EventErrorKind.IO, "inotify receive failed", native_code=exc.errno) from exc
            return ()

    def wake(self) -> None:
        with self._state:
            if self._wake_write >= 0:
                try:
                    os.write(self._wake_write, b"\0")
                except BlockingIOError:
                    pass  # A full pipe already guarantees a pending wakeup.

    def _dispose(self) -> None:
        if self._selector is not None:
            self._selector.close()
        with self._state:
            for name in ("_fd", "_wake_read", "_wake_write"):
                fd = getattr(self, name)
                if fd >= 0:
                    os.close(fd)
                    setattr(self, name, -1)
            self._closed = True

    def close(self) -> None:
        with self._closer:
            if self._closed:
                return
            self._closing = True
            self.wake()
            with self._reader:
                self._dispose()
