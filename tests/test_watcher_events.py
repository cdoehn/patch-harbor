"""Deterministic native-event parsing, bounded routing and Win32 lifetime tests."""
from __future__ import annotations

import ctypes
import importlib
from pathlib import Path
from queue import Empty, Queue
import struct
from threading import Event, Thread
from types import SimpleNamespace

import pytest

import patchharbor_watcher.events as events
import patchharbor_watcher.platform as native_events
from patchharbor_watcher.events import (
    DirectoryEvent, EventBackendError, EventBatch, EventErrorKind, EventKind, WatchPlan,
)
from patchharbor_watcher.platform import linux, windows


def inotify_record(wd=1, mask=linux.IN_CREATE, name=b"file"):
    raw = b"" if name is None else name + b"\0"
    raw += b"\0" * (-len(raw) % 4)
    return struct.pack("=iIII", wd, mask, 0, len(raw)) + raw


def windows_records(*records):
    result = []
    for index, (action, name) in enumerate(records):
        raw = name.encode("utf-16-le", errors="surrogatepass")
        size = 12 + len(raw)
        following = size + (-size % 4) if index < len(records) - 1 else 0
        result.append(struct.pack("<III", following, action, len(raw)) + raw + (b"\0" * (following - size) if following else b""))
    return b"".join(result)


def test_decoders_preserve_native_unicode_rename_pairs_and_overflow():
    raw = inotify_record(name=b"raw-\xff") + inotify_record(mask=linux.IN_MOVED_FROM, name=b"old")
    raw += inotify_record(mask=linux.IN_MOVED_TO, name=b"new") + inotify_record(-1, linux.IN_Q_OVERFLOW, None)
    assert linux.decode_events(raw) == ((1, linux.IN_CREATE, "raw-\udcff"),
        (1, linux.IN_MOVED_FROM, "old"), (1, linux.IN_MOVED_TO, "new"), (-1, linux.IN_Q_OVERFLOW, None))
    assert windows.decode_events(windows_records((4, "alt-ß"), (5, "neu-😀"), (3, "lone-\udcff"))) == (
        (4, "alt-ß"), (5, "neu-😀"), (3, "lone-\udcff"))


@pytest.mark.parametrize("raw", [b"x", struct.pack("=iIII", 1, 2, 0, 100),
    struct.pack("=iIII", 1, 2, 0, 4) + b"abcd", inotify_record(name=b"../x"), inotify_record(name=b"..")])
def test_malformed_inotify_records_fail_closed(raw):
    with pytest.raises(EventBackendError) as error:
        linux.decode_events(raw)
    assert error.value.kind is EventErrorKind.INVALID_EVENT


@pytest.mark.parametrize("raw", [b"x", struct.pack("<III", 0, 1, 20),
    struct.pack("<III", 0, 1, 1) + b"x", windows_records((99, "x")),
    windows_records((1, "..")), windows_records((1, "sub/file")), windows_records((1, "sub\\file")),
    windows_records((1, "nul\0name")), windows_records((1, "x")) + b"junk",
    struct.pack("<III", 4, 1, 2) + b"x\0", struct.pack("<III", 15, 1, 2) + b"x\0\0\0next"])
def test_malformed_windows_records_fail_closed(raw):
    with pytest.raises(EventBackendError) as error:
        windows.decode_events(raw)
    assert error.value.kind is EventErrorKind.INVALID_EVENT


def test_plan_is_flat_deduplicated_and_guards_ancestors_without_enumeration(tmp_path, monkeypatch):
    root = tmp_path / "parent/root"
    root.mkdir(parents=True)
    def forbidden(*args, **kwargs):
        pytest.fail("native setup must not enumerate directories")
    monkeypatch.setattr(Path, "iterdir", forbidden)
    plan = WatchPlan((root, root))
    assert plan.roots == (root,)
    assert set(plan.directories) == {root, *root.parents}
    assert plan.route(root.parent, "unrelated", membership=True) == ()
    assert plan.route(root.parent, root.name) == ()  # Directory mtime alone is not replacement.
    assert plan.route(root.parent, root.name, membership=True) == (DirectoryEvent(EventKind.ROOT_INVALIDATED, root),)
    assert plan.route(root.parent.parent, root.parent.name, membership=True) == (DirectoryEvent(EventKind.ROOT_INVALIDATED, root),)
    assert plan.route(root, "reports", child_directory_metadata=True) == ()
    assert plan.route(root, "reports", membership=True) == (DirectoryEvent(EventKind.CHANGED, root, "reports"),)
    root.rename(root.with_name("moved"))
    root.mkdir()
    assert plan.route(root.parent, root.name) == (DirectoryEvent(EventKind.ROOT_INVALIDATED, root),)
    with pytest.raises(EventBackendError) as error:
        plan.revalidate()
    assert error.value.kind is EventErrorKind.INVALID_TARGET


def test_event_flood_is_coalesced_with_bounded_memory(tmp_path):
    batch = EventBatch()
    same = DirectoryEvent(EventKind.CHANGED, tmp_path, "same")
    for _ in range(10000):
        batch.add((same,))
    assert batch.result() == (same,)
    for index in range(10000):
        batch.add((DirectoryEvent(EventKind.CHANGED, tmp_path, str(index)),))
    assert batch.result() == (DirectoryEvent(EventKind.OVERFLOW, None),)


@pytest.mark.parametrize("value", [True, "1", -1, float("nan"), float("inf")])
def test_timeout_rejects_invalid_values(value):
    with pytest.raises((TypeError, ValueError)):
        events.deadline_for(value)


def test_foreign_platform_imports_are_safe_and_factory_has_no_poll_fallback(monkeypatch):
    monkeypatch.setattr(native_events.sys, "platform", "unsupported")
    importlib.reload(linux)
    importlib.reload(windows)
    with pytest.raises(EventBackendError) as error:
        native_events.open_event_source(())
    assert error.value.kind is EventErrorKind.UNSUPPORTED
    with pytest.raises(EventBackendError):
        linux.LinuxEventSource(())
    with pytest.raises(EventBackendError):
        windows.WindowsEventSource(())


class FakeKernel:
    """Completion transport double; buffers/overlapped structs are real ctypes."""
    def __init__(self, failure=None):
        self.queue = Queue()
        self.handles = {}
        self.keys = {}
        self.calls = []
        self.failure = failure
        self.entered = Event()
        self.overwrite_on_arm = False

    def create_port(self):
        self.calls.append(("port", 100))
        return 100

    def open(self, directory):
        if self.failure == "open" and self.handles:
            raise EventBackendError(EventErrorKind.IO, "open failed")
        handle = 101 + len(self.handles)
        self.handles[handle] = directory
        self.calls.append(("open", handle))
        return handle

    def associate(self, handle, port, key):
        self.keys[handle] = key
        if self.failure == "associate" and len(self.handles) == 2:
            raise EventBackendError(EventErrorKind.IO, "associate failed")

    def arm(self, watch):
        if self.failure == "arm" and len(self.handles) == 2:
            raise EventBackendError(EventErrorKind.IO, "arm failed")
        assert not watch.pending
        watch.pending = True
        self.calls.append(("arm", watch.handle))
        if self.overwrite_on_arm:
            ctypes.memset(watch.buffer, 0x58, ctypes.sizeof(watch.buffer))

    def receive(self, port, timeout):
        self.entered.set()
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None

    def wake(self, port):
        self.calls.append(("wake", port))
        self.queue.put((0, 0, 0, None))

    def cancel_and_wait(self, watch):
        self.calls.append(("cancel_wait", watch.handle))
        watch.pending = False

    def close(self, handle):
        self.calls.append(("close", handle))

    def send(self, source, directory, data=b"", error=0):
        key, watch = next((key, watch) for key, watch in source._watches.items() if watch.directory == directory)
        ctypes.memmove(watch.buffer, data, len(data))
        self.queue.put((key, len(data), error, ctypes.addressof(watch.overlapped)))


@pytest.mark.parametrize("failure", ["open", "associate", "arm", "revalidate"])
def test_windows_partial_subscription_failure_releases_completed_resources(tmp_path, monkeypatch, failure):
    kernel = FakeKernel(failure)
    if failure == "revalidate":
        def changed(self):
            raise EventBackendError(EventErrorKind.INVALID_TARGET, "changed")
        monkeypatch.setattr(WatchPlan, "revalidate", changed)
    with pytest.raises(EventBackendError):
        windows.WindowsEventSource((tmp_path,), _kernel=kernel)
    opened = {handle for action, handle in kernel.calls if action in ("port", "open")}
    closed = [handle for action, handle in kernel.calls if action == "close"]
    assert set(closed) == opened and len(closed) == len(opened)
    for handle in kernel.handles:
        assert kernel.calls.index(("cancel_wait", handle)) < kernel.calls.index(("close", handle))


def test_windows_copies_completed_bytes_before_rearm_and_filters_nested_directory_metadata(tmp_path):
    (tmp_path / "reports").mkdir()
    kernel = FakeKernel()
    with windows.WindowsEventSource((tmp_path,), _kernel=kernel) as source:
        kernel.overwrite_on_arm = True
        kernel.send(source, tmp_path, windows_records((3, "reports"), (1, "bundle.zip")))
        assert source.read(0) == (DirectoryEvent(EventKind.CHANGED, tmp_path, "bundle.zip"),)
        kernel.send(source, tmp_path, windows_records((2, "reports")))
        assert source.read(0) == (DirectoryEvent(EventKind.CHANGED, tmp_path, "reports"),)
        kernel.send(source, tmp_path.parent, windows_records((4, tmp_path.name)))
        assert source.read(0) == (DirectoryEvent(EventKind.ROOT_INVALIDATED, tmp_path),)


@pytest.mark.parametrize("code", [0, 1022])
def test_windows_overflow_requires_rescan_and_rearms(tmp_path, code):
    kernel = FakeKernel()
    with windows.WindowsEventSource((tmp_path,), _kernel=kernel) as source:
        kernel.send(source, tmp_path, error=code)
        assert source.read(0) == (DirectoryEvent(EventKind.OVERFLOW, tmp_path),)
        assert all(w.pending for w in source._watches.values())


@pytest.mark.parametrize("code", [2, 3, 5])
def test_windows_lost_root_is_invalidated_without_rearming_dead_handle(tmp_path, code):
    kernel = FakeKernel()
    with windows.WindowsEventSource((tmp_path,), _kernel=kernel) as source:
        kernel.send(source, tmp_path, error=code)
        assert source.read(0) == (DirectoryEvent(EventKind.ROOT_INVALIDATED, tmp_path),)
        assert not next(w for w in source._watches.values() if w.directory == tmp_path).pending


@pytest.mark.parametrize("code,kind", [(1, EventErrorKind.UNSUPPORTED), (87, EventErrorKind.IO), (995, EventErrorKind.IO)])
def test_windows_backend_failures_are_structured_and_not_idle(tmp_path, code, kind):
    kernel = FakeKernel()
    with windows.WindowsEventSource((tmp_path,), _kernel=kernel) as source:
        kernel.send(source, tmp_path, error=code)
        with pytest.raises(EventBackendError) as caught:
            source.read(0)
        assert caught.value.kind is kind and caught.value.native_code == code


def test_windows_idle_wake_close_and_double_close_are_synchronized(tmp_path):
    kernel = FakeKernel()
    source = windows.WindowsEventSource((tmp_path,), _kernel=kernel)
    returned = []
    reader = Thread(target=lambda: returned.append(source.read()), daemon=True)
    reader.start()
    assert kernel.entered.wait(2)
    source.close()
    reader.join(2)
    assert not reader.is_alive() and returned == [()]
    calls = list(kernel.calls)
    source.close()
    source.wake()
    assert kernel.calls == calls and source.read(0) == ()
    assert kernel.calls[-1] == ("close", 100)


def test_windows_wakes_are_coalesced_until_consumed(tmp_path):
    kernel = FakeKernel()
    with windows.WindowsEventSource((tmp_path,), _kernel=kernel) as source:
        for _ in range(10000):
            source.wake()
        assert kernel.calls.count(("wake", 100)) == 1
        assert source.read() == ()
        source.wake()
        assert kernel.calls.count(("wake", 100)) == 2


def test_windows_native_call_uses_nonrecursive_aligned_buffer_and_no_access_filter(tmp_path):
    kernel = object.__new__(windows._Kernel32)
    calls = []
    kernel.dll = SimpleNamespace(ReadDirectoryChangesW=lambda *args: calls.append(args) or 1)
    watch = windows._Watch(tmp_path, 123)
    kernel.arm(watch)
    handle, buffer, size, subtree, mask, count, overlap, callback = calls[0]
    assert handle == 123 and ctypes.addressof(buffer) % 4 == 0 and size <= 65536
    assert not subtree and not mask & 0x20 and mask & 0x100 and mask & 0x10
    assert count is None and callback is None and overlap is not None and watch.pending
    assert ctypes.sizeof(windows._DWORD) == 4
    assert ctypes.sizeof(windows._Overlapped) == (32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 20)


@pytest.mark.parametrize("cancelled,error", [(1, 0), (0, 1168), (0, 5)])
def test_windows_cancellation_always_waits_before_releasing_buffer(tmp_path, monkeypatch, cancelled, error):
    kernel = object.__new__(windows._Kernel32)
    calls = []
    def cancel(*args):
        calls.append("cancel")
        return cancelled
    def completed(*args):
        assert args[-1] is True
        calls.append("completed")
        return 0  # ERROR_OPERATION_ABORTED is also a completed operation.
    kernel.dll = SimpleNamespace(CancelIoEx=cancel, GetOverlappedResult=completed)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    watch = windows._Watch(tmp_path, 123, pending=True)
    if error == 5:
        with pytest.raises(EventBackendError):
            kernel.cancel_and_wait(watch)
    else:
        kernel.cancel_and_wait(watch)
    assert calls == ["cancel", "completed"] and not watch.pending


@pytest.mark.parametrize("interrupted", [False, True])
def test_windows_arm_retains_buffer_ownership_until_native_failure_is_certain(tmp_path, monkeypatch, interrupted):
    kernel = object.__new__(windows._Kernel32)
    watch = windows._Watch(tmp_path, 123)
    def subscribe(*args):
        assert watch.pending
        if interrupted:
            raise KeyboardInterrupt
        return 0
    kernel.dll = SimpleNamespace(ReadDirectoryChangesW=subscribe)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    with pytest.raises(KeyboardInterrupt if interrupted else EventBackendError):
        kernel.arm(watch)
    assert watch.pending is interrupted


def test_nonblocking_windows_barrier_drains_unrelated_completions_before_return(tmp_path):
    root = tmp_path / 'exchange'
    root.mkdir()
    kernel = FakeKernel()
    with windows.WindowsEventSource((root,), _kernel=kernel) as source:
        kernel.send(source, root.parent, windows_records((1, 'unrelated')))
        kernel.send(source, root, windows_records((1, 'bundle.zip')))
        assert source.read(0) == (DirectoryEvent(EventKind.CHANGED, root, 'bundle.zip'),)
