"""Core compatibility without weakening failure, ownership or file-state checks."""
from dataclasses import replace
import ast
import errno
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from patchharbor import compat
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.exit_status import exit_code_for_error
from patchharbor.platform import file_times, filesystem, private_directory
from patchharbor.platform.file_times import WindowsFileTimes, WindowsDescriptorMetadata
from patchharbor.platform.pack_output import OwnedPackFile
from patchharbor import patch_pack as core
from tests.pack_support import request_files, pack
from tests.windows_creation_support import assert_private_creation


def test_core_watcher_imports_and_type_hints_do_not_need_typing_self(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src"
    program = """
import builtins, sys, typing
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'typing' and 'Self' in fromlist:
        raise ImportError('typing.Self is unavailable in 3.10')
    return original(name, globals, locals, fromlist, level)
builtins.__import__ = guarded
from patchharbor import api, cli
from patchharbor.platform.lifecycle import ProcessTree
from patchharbor_watcher import open_event_source, cli as watcher_cli
hints = typing.get_type_hints(ProcessTree.__enter__)
assert hints['self'] is hints['return']
for name in api.__all__:
    getattr(api, name)
assert typing.get_type_hints(api.pack_patch)['return'] is api.PatchPackResult
assert callable(cli.main) and callable(watcher_cli.main) and callable(open_event_source)
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", program, str(source)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_runtime_sources_use_python_310_grammar():
    source = Path(__file__).resolve().parents[1] / "src"
    for path in source.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("kind", ["tool", "os", "interrupt"])
def test_notes_keep_primary_exception_identity_category_and_cause(monkeypatch, native, kind):
    if not native:
        monkeypatch.setattr(compat, "_NATIVE_ADD_NOTE", None)
    error = (PatchHarborError("primary", FailureReason.SOURCE_ERROR) if kind == "tool"
             else OSError(errno.EACCES, "primary") if kind == "os" else KeyboardInterrupt())
    cause = LookupError("original cause")
    error.__cause__ = cause
    args = error.args
    for note in ("first cleanup", "second cleanup"):
        compat.add_exception_note(error, note)
    assert error.args == args and error.__cause__ is cause
    assert error.__notes__ == ["first cleanup", "second cleanup"]
    if kind == "tool":
        assert error.reason is FailureReason.SOURCE_ERROR
        assert int(exit_code_for_error(error)) == 4
    if kind == "os":
        assert error.errno == errno.EACCES


@pytest.mark.parametrize("primary", ["output", "interrupt"])
def test_pack_cleanup_keeps_notes_and_primary_error_without_add_note(request_files, monkeypatch, primary):
    monkeypatch.setattr(compat, "_NATIVE_ADD_NOTE", None)
    failure = OSError("publication failed") if primary == "output" else KeyboardInterrupt()
    cleanup = OwnedPackFile.cleanup
    def reject(self, name):
        raise failure
    def clean(self):
        return (*cleanup(self), "controlled cleanup warning")
    monkeypatch.setattr(OwnedPackFile, "publish", reject)
    monkeypatch.setattr(OwnedPackFile, "cleanup", clean)
    with pytest.raises(PatchHarborError) as caught:
        pack(request_files)
    error = caught.value
    assert error.reason is (FailureReason.PAYLOAD_PREPARATION_ERROR if primary == "output"
                            else FailureReason.INTERRUPTED)
    assert error.__cause__ is failure
    assert error.__notes__ == ["controlled cleanup warning"]
    assert not list(request_files[2].iterdir())


def test_pack_reference_close_failure_preserves_primary_error_without_add_note(request_files, monkeypatch):
    monkeypatch.setattr(compat, "_NATIVE_ADD_NOTE", None)
    opened = core.open_regular_nofollow
    close = os.close
    reference_fd = None
    primary = PatchHarborError("source failed", FailureReason.SOURCE_ERROR)
    def track(path):
        nonlocal reference_fd
        reference_fd = opened(path)
        return reference_fd
    def close_then_fail(fd):
        close(fd)
        if fd == reference_fd:
            raise OSError("close diagnostic")
    def fail(*args, **kwargs):
        raise primary
    monkeypatch.setattr(core, "open_regular_nofollow", track)
    monkeypatch.setattr(core, "capture_sources", fail)
    monkeypatch.setattr(os, "close", close_then_fail)
    with pytest.raises(PatchHarborError) as caught:
        pack(request_files)
    assert caught.value is primary
    assert primary.reason is FailureReason.SOURCE_ERROR
    assert len(primary.__notes__) == 1
    assert not list(request_files[2].iterdir())


def _metadata(**changes):
    values = dict(st_dev=4, st_ino=5, st_mode=stat.S_IFREG | 0o600,
        st_size=10, st_nlink=1, st_mtime_ns=200, st_ctime_ns=100, st_file_attributes=32,
    )
    return SimpleNamespace(**(values | changes))


@pytest.fixture
def legacy_metadata(monkeypatch):
    monkeypatch.setattr(filesystem, "is_windows", lambda: True)
    monkeypatch.setattr(filesystem, "legacy_windows_stat", lambda: True)
    monkeypatch.setattr(file_times, "legacy_windows_stat", lambda: True)
    return WindowsFileTimes(100, 200, 300, 32)


@pytest.mark.parametrize("change", [None, "creation_ns", "write_ns", "change_ns", "attributes"])
def test_legacy_handle_capture_requires_stable_native_times(monkeypatch, legacy_metadata, change):
    before = legacy_metadata
    after = before if change is None else replace(before, **{change: getattr(before, change) + 1})
    states = iter([before, after])
    raw = _metadata()
    monkeypatch.setattr(filesystem, "windows_file_times", lambda fd: next(states))
    monkeypatch.setattr(filesystem.os, "fstat", lambda fd: raw)
    if change is not None:
        with pytest.raises(filesystem.FileChangedDuringRead) as caught:
            filesystem.capture_descriptor_metadata(99)
        assert caught.value.category == "descriptor-state-changed"
    else:
        captured = filesystem.capture_descriptor_metadata(99)
        assert captured.st_ctime_ns == 300 and captured.st_birthtime_ns == 100
        assert captured.st_ctime == 300 / 1_000_000_000
        assert os.path.samestat(captured, raw) and captured.st_size == raw.st_size
        assert filesystem._same_path_and_open_file_state(raw, captured, allow_path_identity_fallback=False)


@pytest.mark.parametrize("field", ["st_ctime_ns", "st_mtime_ns", "st_file_attributes"])
def test_legacy_stat_cannot_disagree_with_native_handle(monkeypatch, legacy_metadata, field):
    raw = _metadata()
    setattr(raw, field, getattr(raw, field) + 1)
    monkeypatch.setattr(filesystem, "windows_file_times", lambda fd: legacy_metadata)
    monkeypatch.setattr(filesystem.os, "fstat", lambda fd: raw)
    with pytest.raises(filesystem.FileChangedDuringRead):
        filesystem.capture_descriptor_metadata(99)


def test_missing_native_change_time_is_terminal(monkeypatch, legacy_metadata):
    def unavailable(fd):
        raise OSError(errno.ENOTSUP, "native primitive unavailable")
    monkeypatch.setattr(filesystem, "windows_file_times", unavailable)
    with pytest.raises(OSError) as caught:
        filesystem.capture_descriptor_metadata(99)
    assert caught.value.errno == errno.ENOTSUP
    with pytest.raises(OSError):
        filesystem._same_open_file_state(_metadata(), _metadata())


def test_legacy_creation_time_does_not_hide_same_size_restored_mtime_change(legacy_metadata):
    raw = _metadata()
    before = WindowsDescriptorMetadata(raw, 100, 300)
    after = WindowsDescriptorMetadata(raw, 100, 301)
    assert os.path.samestat(before, after) and before.st_size == after.st_size
    assert before.st_mtime_ns == after.st_mtime_ns and before.st_birthtime_ns == after.st_birthtime_ns
    assert not filesystem._same_open_file_state(before, after)
    replaced = _metadata()
    replaced.st_ino += 1
    assert not filesystem._same_path_and_open_file_state(replaced, after, allow_path_identity_fallback=False)


@pytest.mark.parametrize("mode,attributes,tag,expected", [
    (stat.S_IFDIR, 0x400, 0xA0000003, filesystem.PathKind.JUNCTION),
    (stat.S_IFREG, 0x400, 0x80000000, filesystem.PathKind.OTHER),
    (stat.S_IFDIR, 0x400, 0, filesystem.PathKind.OTHER),
    (stat.S_IFLNK, 0x400, 0xA000000C, filesystem.PathKind.SYMBOLIC_LINK),
    (stat.S_IFDIR, 0x10, 0, filesystem.PathKind.DIRECTORY),
])
def test_path_classification_rejects_reparse_points_without_pathlib_junction(mode, attributes, tag, expected):
    path = SimpleNamespace(lstat=lambda: SimpleNamespace(st_mode=mode,
                           st_file_attributes=attributes, st_reparse_tag=tag))
    assert filesystem.path_kind(path) is expected


def test_regular_reader_rejects_unknown_reparse_before_open(tmp_path, monkeypatch):
    path = tmp_path / "regular"
    path.write_bytes(b"untouched")
    monkeypatch.setattr(filesystem, "_inspect_path_without_following",
                        lambda path: _metadata(st_file_attributes=0x400))
    def forbidden(*args, **kwargs):
        pytest.fail("reparse file was opened")
    monkeypatch.setattr(filesystem.os, "open", forbidden)
    with pytest.raises(filesystem.UnsupportedFileTypeError):
        filesystem.read_stable_regular_file_bounded(path, max_bytes=100)
    assert path.read_bytes() == b"untouched"


def test_native_handle_time_conversion_uses_integer_precision_and_does_not_reopen(monkeypatch):
    import ctypes
    calls = []
    ticks = 11644473600 * 10_000_000
    def query(handle, kind, output, size):
        calls.append((handle, kind, size))
        output._obj.creation = ticks + 1
        output._obj.write = ticks + 23
        output._obj.change = ticks + 45
        output._obj.attributes = 32
        return True
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k:
                        SimpleNamespace(GetFileInformationByHandleEx=query), raising=False)
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(get_osfhandle=lambda fd: 123))
    assert file_times.windows_file_times(7) == WindowsFileTimes(100, 2300, 4500, 32)
    assert len(calls) == 1 and calls[0][:2] == (123, 0)


@pytest.mark.parametrize("existing", ["directory", "file"])
def test_private_directory_does_not_repair_or_replace_existing_path(tmp_path, existing):
    path = tmp_path / "owned"
    path.mkdir() if existing == "directory" else path.write_bytes(b"keep")
    before = path.stat()
    with pytest.raises(FileExistsError):
        private_directory.create_private_directory(path)
    after = path.stat()
    assert os.path.samestat(before, after) and before.st_mode == after.st_mode
    if existing == "file":
        assert path.read_bytes() == b"keep"


def test_windows_private_reservation_retries_only_collisions(tmp_path, monkeypatch):
    monkeypatch.setattr(private_directory, "is_windows", lambda: True)
    tokens = iter(["occupied", "free"])
    monkeypatch.setattr(private_directory.secrets, "token_hex", lambda count: next(tokens))
    calls = []
    def create(path):
        calls.append(path)
        if path.name == "request-occupied":
            raise FileExistsError()
        path.mkdir()
    monkeypatch.setattr(private_directory, "create_private_directory", create)
    path = private_directory.create_private_temporary_directory(tmp_path, "request-")
    assert path.name == "request-free" and len(calls) == 2
    def denied(path):
        raise PermissionError("no private ACL support")
    monkeypatch.setattr(private_directory, "create_private_directory", denied)
    monkeypatch.setattr(private_directory.secrets, "token_hex", lambda count: "denied")
    with pytest.raises(PermissionError):
        private_directory.create_private_temporary_directory(tmp_path, "request-")
    assert not (tmp_path / "request-denied").exists()


@pytest.mark.parametrize("failure", [None, "thread", "token", "size", "info", "sid", "convert", "create"])
@pytest.mark.parametrize("impersonated", [False, True])
def test_private_windows_creation_never_uses_permissive_acl_on_failure(tmp_path, monkeypatch, failure, impersonated):
    assert_private_creation(private_directory._windows_create_private_directory,
                            tmp_path, monkeypatch, failure, impersonated)
