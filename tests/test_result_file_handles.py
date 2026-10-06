"""No-follow publication handles and observable stable-read failure categories."""
import os
from types import SimpleNamespace

import pytest

from patchharbor.platform import file_handles, filesystem
from patchharbor.platform.file_handles import open_regular_nofollow
from patchharbor import result_bundle_publication as publication
from tests.test_result_verification import destination, sleeps
from tests.test_result_bundle_publication import _publish


def symlink_or_skip(link, target):
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")


def test_native_read_and_write_handles_close_without_leaks(tmp_path):
    path = tmp_path / "file"
    path.write_bytes(b"before")
    descriptor = open_regular_nofollow(path, writable=True)
    assert os.get_inheritable(descriptor) is False
    with os.fdopen(descriptor, "r+b") as stream:
        assert stream.read() == b"before"
        stream.seek(0)
        stream.write(b"after!")
    with pytest.raises(OSError):
        os.fstat(descriptor)
    descriptor = open_regular_nofollow(path)
    with os.fdopen(descriptor, "rb") as stream:
        assert stream.read() == b"after!"


def test_native_open_rejects_symlink_and_directory(tmp_path):
    path = tmp_path / "file"
    path.write_bytes(b"secret")
    link = tmp_path / "link"
    symlink_or_skip(link, path)
    for target in (link, tmp_path):
        with pytest.raises(OSError):
            open_regular_nofollow(target)
    assert path.read_bytes() == b"secret"


@pytest.mark.parametrize("operation", ["sync", "read"])
def test_owned_handle_rejects_replacement_even_with_identical_content(tmp_path, operation):
    path = tmp_path / "file"
    path.write_bytes(b"same bytes")
    original = path.stat()
    path.rename(tmp_path / "original")
    path.write_bytes(b"same bytes")
    with pytest.raises(filesystem.FileSystemOperationError):
        if operation == "sync":
            filesystem.sync_regular_file_best_effort(path, expected_identity=original)
        else:
            filesystem.read_stable_regular_file_with_sha256(path, retained_content_limit=100,
                allow_path_identity_fallback=True, expected_identity=original)
    assert path.read_bytes() == b"same bytes"


def test_reader_cannot_resolve_replaced_temporary_symlink_to_original(destination, sleeps, monkeypatch):
    displaced = destination.temporary_path.with_name("original")
    probe = displaced.with_name("probe")
    symlink_or_skip(probe, displaced)
    probe.unlink()
    original = publication.read_result_reference
    def replace_then_read(path, **kwargs):
        path.rename(displaced)
        path.symlink_to(displaced)
        return original(path, **kwargs)
    monkeypatch.setattr(publication, "read_result_reference", replace_then_read)
    with pytest.raises(publication.PatchHarborError):
        _publish(destination)
    assert sleeps == [] and destination.temporary_path.is_symlink()
    assert displaced.is_file() and not destination.final_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX open race; Windows uses CreateFileW")
@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
def test_sync_open_rejects_last_moment_special_file(destination, sleeps, monkeypatch, replacement):
    original_open = file_handles.os.open
    displaced = destination.temporary_path.with_name("original")
    changed = False
    def race(path, flags, *args, **kwargs):
        nonlocal changed
        if path == destination.temporary_path and not changed:
            changed = True
            path.rename(displaced)
            if replacement == "symlink":
                path.symlink_to(displaced)
            else:
                os.mkfifo(path)
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(file_handles.os, "open", race)
    with pytest.raises(publication.PatchHarborError):
        _publish(destination)
    assert changed and sleeps == []
    assert displaced.is_file() and not destination.final_path.exists()
    assert destination.temporary_path.lstat()


def adjusted(info, **changes):
    values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
    return SimpleNamespace(**(values | changes))


@pytest.mark.parametrize("category", ["initial-open-state-mismatch", "current-path-state-mismatch",
    "descriptor-state-changed", "final-path-state-mismatch", "size-mismatch", "path-missing"])
def test_stable_reader_reports_actual_mismatch_without_weakening_checks(tmp_path, monkeypatch, category):
    path = tmp_path / "file"
    path.write_bytes(b"unchanged")
    original_path = filesystem._inspect_path_without_following
    original_fstat = filesystem.os.fstat
    paths = 0
    descriptors = 0
    def inspect(target):
        nonlocal paths
        info = original_path(target)
        paths += 1
        if category == "path-missing":
            return None
        if category == "size-mismatch":
            return adjusted(info, st_size=info.st_size + 1)
        if (category == "current-path-state-mismatch" and paths == 2
                or category == "final-path-state-mismatch" and paths == 3):
            return adjusted(info, st_mtime_ns=info.st_mtime_ns + 1)
        return info
    def fstat(fd):
        nonlocal descriptors
        info = original_fstat(fd)
        descriptors += 1
        if category == "size-mismatch" or category == "initial-open-state-mismatch" and descriptors == 1:
            return adjusted(info, st_size=info.st_size + 1)
        if category == "descriptor-state-changed" and descriptors == 2:
            return adjusted(info, st_ctime_ns=info.st_ctime_ns + 1)
        return info
    monkeypatch.setattr(filesystem, "_inspect_path_without_following", inspect)
    monkeypatch.setattr(filesystem.os, "fstat", fstat)
    with pytest.raises(filesystem.FileChangedDuringRead) as caught:
        filesystem.read_stable_regular_file_with_sha256(path, retained_content_limit=100,
                                                      allow_path_identity_fallback=True)
    assert caught.value.category == category
    assert all(type(value) is int for metadata in caught.value.metadata.values() for value in metadata.values())


def test_owned_reader_bounds_actual_bytes_even_if_size_metadata_lags(tmp_path, monkeypatch):
    path = tmp_path / "file"
    path.write_bytes(b"a" * 100)
    identity = path.stat()
    original_path = filesystem._inspect_path_without_following
    original_fstat = filesystem.os.fstat
    monkeypatch.setattr(filesystem, "_inspect_path_without_following",
                        lambda target: adjusted(original_path(target), st_size=1))
    monkeypatch.setattr(filesystem.os, "fstat", lambda fd: adjusted(original_fstat(fd), st_size=1))
    with pytest.raises(filesystem.FileReadLimitExceeded):
        filesystem.read_stable_regular_file_with_sha256(path, retained_content_limit=10,
            expected_identity=identity, max_bytes=10, allow_path_identity_fallback=True)
