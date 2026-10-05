"""Real Linux/Windows filesystem events; no CLI activation or polling fallback."""
from __future__ import annotations

import os
from pathlib import Path
import sys
from threading import Event, Thread
from time import monotonic

import pytest

from patchharbor_watcher import open_event_source
from patchharbor_watcher.events import (
    DirectoryEvent, EventBackendError, EventErrorKind, EventKind,
)
from tests.platform_support import create_symlink_or_skip

pytestmark = [pytest.mark.platform,
    pytest.mark.skipif(not (sys.platform.startswith("linux") or sys.platform == "win32"), reason="native Linux/Windows events required")]


def receive(source, predicate):
    deadline = monotonic() + 5
    seen = []
    while monotonic() < deadline:
        seen.extend(source.read(max(0, deadline - monotonic())))
        if any(predicate(event) for event in seen):
            return tuple(seen)
    pytest.fail(f"native event missing: {seen}")


def drain(source):
    for _ in range(100):
        if not source.read(0):
            return
    pytest.fail("event receiver did not drain")


@pytest.mark.parametrize("operation", ["create", "write", "rename", "delete", "mkdir", "chmod"])
def test_real_direct_entry_changes(operation, tmp_path):
    root = tmp_path / "exchange"
    root.mkdir()
    item = root / "bundle"
    item.write_bytes(b"initial")
    with open_event_source((root,)) as source:
        expected = item.name
        if operation == "create":
            expected = "new.partial"
            (root / expected).write_bytes(b"partial")
        elif operation == "write":
            with item.open("ab") as stream:
                stream.write(b"another chunk")
                stream.flush()
                os.fsync(stream.fileno())
        elif operation == "rename":
            expected = "published.zip"
            item.rename(root / expected)
        elif operation == "delete":
            item.unlink()
        elif operation == "mkdir":
            expected = "new-folder"
            (root / expected).mkdir()
        else:
            item.chmod(0o400)
        try:
            seen = receive(source, lambda event: event.directory == root and event.name == expected)
            assert all(event.directory == root for event in seen)
        finally:
            if item.exists():
                item.chmod(0o600)


def test_reads_atime_and_nested_writes_do_not_produce_exchange_changes(tmp_path):
    root = tmp_path / "exchange"
    root.mkdir()
    nested = root / "reports"
    nested.mkdir()
    item = root / "bundle.zip"
    item.write_bytes(b"content")
    with open_event_source((root,)) as source:
        assert item.read_bytes() == b"content"
        assert item.stat().st_size == 7
        list(root.iterdir())
        (nested / "diagnosis").write_text("only a nested report")
        assert source.read(0.2) == ()


@pytest.mark.parametrize("ancestor", [False, True])
def test_real_root_or_ancestor_replacement_invalidates_subscription(tmp_path, ancestor):
    parent = tmp_path / "parent"
    root = parent / "exchange"
    root.mkdir(parents=True)
    with open_event_source((root,)) as source:
        moved = parent if ancestor else root
        moved.rename(moved.with_name("moved"))
        moved.mkdir()
        seen = receive(source, lambda event: event.kind is EventKind.ROOT_INVALIDATED and event.directory == root)
        assert DirectoryEvent(EventKind.ROOT_INVALIDATED, root) in seen


def test_real_atomic_control_file_replace_and_independent_roots(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "config.json").write_text("old")
    with open_event_source((first, second, first)) as source:
        temporary = first / "next"
        temporary.write_text("new")
        temporary.replace(first / "config.json")
        seen = receive(source, lambda event: event.directory == first and event.name == "config.json")
        assert all(event.directory == first for event in seen)
        drain(source)
        (second / "bundle").write_bytes(b"content")
        assert any(event.directory == second for event in receive(source, lambda event: event.directory == second))


@pytest.mark.parametrize("close", [False, True])
def test_idle_wait_is_interrupted_without_periodic_scanning(tmp_path, close):
    source = open_event_source((tmp_path,))
    entered, completed = Event(), Event()
    returned = []
    def read():
        entered.set()
        returned.append(source.read())
        completed.set()
    reader = Thread(target=read, daemon=True)
    reader.start()
    try:
        assert entered.wait(2)
        assert not completed.wait(0.1)
        source.close() if close else source.wake()
        reader.join(5)
        assert not reader.is_alive() and completed.is_set() and returned == [()]
    finally:
        source.close()
        reader.join(5)
    source.close()
    source.wake()
    assert source.read(0) == ()


def test_invalid_missing_and_linked_roots_fail_before_activation(tmp_path):
    with pytest.raises(EventBackendError) as error:
        open_event_source((tmp_path / "missing",))
    assert error.value.kind is EventErrorKind.INVALID_TARGET
    alias = tmp_path / "alias"
    root = tmp_path / "physical"
    root.mkdir()
    create_symlink_or_skip(alias, root, target_is_directory=True)
    with pytest.raises(EventBackendError) as error:
        open_event_source((alias,))
    assert error.value.kind is EventErrorKind.INVALID_TARGET


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="inotify boundary injection")
@pytest.mark.parametrize("mask", [0x4000, 0x8000, 0x2000])
def test_linux_overflow_and_watch_loss_are_structured(tmp_path, monkeypatch, mask):
    from types import SimpleNamespace
    from patchharbor_watcher.platform import linux
    from tests.test_watcher_events import inotify_record
    with open_event_source((tmp_path,)) as source:
        wd = next(wd for wd, path in source._watches.items() if path == tmp_path)
        raw = inotify_record(-1 if mask == linux.IN_Q_OVERFLOW else wd, mask, None)
        monkeypatch.setattr(source._selector, "select", lambda timeout: [(SimpleNamespace(fd=source._fd), 1)])
        original_read = os.read
        monkeypatch.setattr(linux.os, "read", lambda fd, size: raw if fd == source._fd else original_read(fd, size))
        expected = (DirectoryEvent(EventKind.OVERFLOW, None) if mask == linux.IN_Q_OVERFLOW
                    else DirectoryEvent(EventKind.ROOT_INVALIDATED, tmp_path))
        assert source.read(0) == (expected,)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux descriptor lifecycle")
def test_linux_close_releases_all_native_descriptors(tmp_path):
    source = open_event_source((tmp_path,))
    descriptors = [source._fd, source._wake_read, source._wake_write, source._selector.fileno()]
    source.close()
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="inotify resource failures")
def test_linux_partial_initialization_closes_pipe_selector_and_event_fd(tmp_path, monkeypatch):
    import ctypes
    import errno
    from patchharbor_watcher.platform import linux
    library = ctypes.CDLL(None, use_errno=True)
    descriptors, selectors = [], []
    class Function:
        def __init__(self, call):
            self.call = call
        def __call__(self, *args):
            return self.call(*args)
    real_init = library.inotify_init1
    def init(flags):
        fd = real_init(flags)
        descriptors.append(fd)
        return fd
    def fail(*args):
        ctypes.set_errno(errno.ENOSPC)
        return -1
    library.inotify_init1 = Function(init)
    library.inotify_add_watch = Function(fail)
    monkeypatch.setattr(linux.ctypes, "CDLL", lambda *args, **kwargs: library)
    real_pipe, real_selector = os.pipe2, linux.selectors.DefaultSelector
    def pipe(flags):
        pair = real_pipe(flags)
        descriptors.extend(pair)
        return pair
    def selector():
        result = real_selector()
        selectors.append(result)
        return result
    monkeypatch.setattr(linux.os, "pipe2", pipe)
    monkeypatch.setattr(linux.selectors, "DefaultSelector", selector)
    with pytest.raises(EventBackendError) as caught:
        open_event_source((tmp_path,))
    assert caught.value.kind is EventErrorKind.IO and caught.value.native_code == errno.ENOSPC
    assert len(descriptors) == 3
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)
    with pytest.raises(ValueError):
        selectors[0].fileno()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="inotify stream failures")
@pytest.mark.parametrize("failure", ["io", "eof", "truncated"])
def test_linux_receive_failure_does_not_masquerade_as_idle(tmp_path, monkeypatch, failure):
    import errno
    from types import SimpleNamespace
    from patchharbor_watcher.platform import linux
    with open_event_source((tmp_path,)) as source:
        real_read = os.read
        def read(fd, size):
            if fd != source._fd:
                return real_read(fd, size)
            if failure == "io":
                raise OSError(errno.EIO, "device failure")
            return b"" if failure == "eof" else b"x"
        monkeypatch.setattr(source._selector, "select", lambda timeout: [(SimpleNamespace(fd=source._fd), 1)])
        monkeypatch.setattr(linux.os, "read", read)
        with pytest.raises(EventBackendError) as caught:
            source.read(0)
        assert caught.value.kind is (EventErrorKind.INVALID_EVENT if failure == "truncated" else EventErrorKind.IO)
