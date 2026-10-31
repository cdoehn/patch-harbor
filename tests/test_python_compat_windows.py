"""Actual Windows primitives; Linux simulations are not native proof."""
import os
from pathlib import Path
import subprocess
from time import sleep

import pytest

from patchharbor.platform import filesystem, private_directory
from patchharbor.platform.file_handles import open_regular_nofollow
from patchharbor.platform.file_times import windows_file_times
from patchharbor import temporary_resources
from tests.windows_private_support import assert_private_dacl

pytestmark = [pytest.mark.platform, pytest.mark.skipif(os.name != "nt", reason="native Windows primitives")]


@pytest.mark.proof('windows.handle-change')
def test_native_legacy_handle_adapter_detects_real_change_with_restored_mtime(tmp_path, monkeypatch):
    path = tmp_path / "same-size.bin"
    path.write_bytes(b"original")
    identity = path.stat()
    # Exercise the old-interpreter adapter even in an existing newer CI lane.
    monkeypatch.setattr(filesystem, "legacy_windows_stat", lambda: True)
    descriptor = open_regular_nofollow(path)
    try:
        before = filesystem.capture_descriptor_metadata(descriptor)
        native_before = windows_file_times(descriptor)
        # Separate native clock ticks, as in the bootstrap mutation fixture.
        # File time updates must be observed after the writing handle closes.
        sleep(0.05)
        with path.open("wb") as writer:
            writer.write(b"modified")
            writer.flush()
            os.fsync(writer.fileno())
        os.utime(path, ns=(identity.st_atime_ns, identity.st_mtime_ns))
        native_after = windows_file_times(descriptor)
        assert native_after.change_ns != native_before.change_ns, (native_before, native_after)
        after = filesystem.capture_descriptor_metadata(descriptor)
        assert before.st_ctime_ns == native_before.change_ns
        assert after.st_ctime_ns == native_after.change_ns
        assert path.read_bytes() == b"modified"
        assert before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
        assert os.path.samestat(before, after) and before.st_birthtime_ns == after.st_birthtime_ns
        assert windows_file_times(descriptor).change_ns == after.st_ctime_ns
        assert not filesystem._same_open_file_state(before, after)
        assert filesystem._same_path_and_open_file_state(path.lstat(), after, allow_path_identity_fallback=False)
    finally:
        os.close(descriptor)
    with pytest.raises(OSError):
        os.fstat(descriptor)


@pytest.mark.proof('windows.junction')
def test_native_junction_is_rejected_without_new_pathlib_api(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "junction"
    created = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                             capture_output=True, timeout=30)
    assert created.returncode == 0, (created.stdout, created.stderr)
    try:
        monkeypatch.delattr(Path, "is_junction", raising=False)
        assert filesystem.path_kind(link) is filesystem.PathKind.JUNCTION
        from tests.runtime_permissions import _owned_paths
        with pytest.raises(ValueError):
            _owned_paths(link, tmp_path)
        from patchharbor.platform.directories import pin_windows_directory
        with pytest.raises(OSError):
            pin_windows_directory(link)
    finally:
        link.rmdir()
    assert target.is_dir()


@pytest.mark.proof('windows.private-dacl', parameter='kind')
@pytest.mark.parametrize("kind", ["named", "random"])
def test_native_private_request_dacl_is_protected_and_inherited(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(temporary_resources, "system_temporary_directory", lambda: tmp_path)
    path = temporary_resources.create_private_request_directory(
        **({"name": "private-request"} if kind == "named" else {"prefix": "private-request-"}))
    child = path / "child"
    child.write_bytes(b"private")
    try:
        assert_private_dacl(path, child, tmp_path)
        with pytest.raises(FileExistsError):
            private_directory.create_private_directory(path)
        assert child.read_bytes() == b"private"
    finally:
        temporary_resources.remove_private_request_directory(path)
    assert not path.exists()
