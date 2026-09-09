from __future__ import annotations

import errno
from hashlib import sha256
from pathlib import Path

import pytest

from patchharbor.archive_files import archive_verified_file
from patchharbor.archive_policy import DEFAULT_ARCHIVE_DIRECTORY, validate_archive_directory
from patchharbor.exchange_state import ExchangeFileIdentity
from patchharbor.platform.archive import open_archive_location
import patchharbor.platform.archive as platform_archive
from patchharbor.platform.filesystem import FileChangedDuringRead


@pytest.mark.parametrize("name", ["PatchHarbor-Archive", ".PatchHarbor-Archive", "Archive_123", ""])
def test_archive_name_is_a_portable_child_or_disabled(name):
    assert validate_archive_directory(name) == name
    assert DEFAULT_ARCHIVE_DIRECTORY == "PatchHarbor-Archive"


@pytest.mark.parametrize("name", ["/tmp/archive", "../archive", "..", ".", "a/b", "a\\b",
                                 "C:\\archive", "C:archive", "//server/share", "archive.",
                                 "CON", "NUL.txt", "COM1", "A\nB", "\0", "x" * 129,
                                 None, False, 123, " archive"])
def test_archive_name_rejects_paths_traversal_and_ambiguous_names(name):
    with pytest.raises(ValueError):
        validate_archive_directory(name)


def _identity(path: Path):
    return ExchangeFileIdentity(path.resolve(), sha256(path.read_bytes()).hexdigest())


def test_collision_never_overwrites_existing_archive_file(tmp_path):
    source = tmp_path / "bundle.zip.txt"
    source.write_bytes(b"new verified bundle")
    identity = _identity(source)
    with open_archive_location(tmp_path, DEFAULT_ARCHIVE_DIRECTORY) as location:
        occupied = location.directory / source.name
        occupied.write_bytes(b"older archive")
        destination = archive_verified_file(location, identity, verify_eligibility=lambda: None)
        assert destination != occupied
        assert destination.read_bytes() == b"new verified bundle"
        assert occupied.read_bytes() == b"older archive"
    assert not source.exists()


@pytest.mark.parametrize("error_number", [errno.EACCES, errno.EXDEV, errno.ENOSPC, errno.ENOTSUP])
def test_failed_move_leaves_source_untouched(tmp_path, monkeypatch, error_number):
    source = tmp_path / "bundle.zip"
    source.write_bytes(b"important")
    identity = _identity(source)
    def fail(*_arguments):
        raise OSError(error_number, "simulated move failure")
    monkeypatch.setattr(platform_archive, "_rename_no_replace", fail)
    with open_archive_location(tmp_path, DEFAULT_ARCHIVE_DIRECTORY) as location:
        with pytest.raises(OSError):
            archive_verified_file(location, identity, verify_eligibility=lambda: None)
        assert not list(location.directory.iterdir())
    assert source.read_bytes() == b"important"


def test_changed_source_is_not_moved(tmp_path):
    source = tmp_path / "bundle.zip"
    source.write_bytes(b"old")
    identity = _identity(source)
    source.write_bytes(b"replacement")
    with open_archive_location(tmp_path, DEFAULT_ARCHIVE_DIRECTORY) as location:
        with pytest.raises(FileChangedDuringRead):
            archive_verified_file(location, identity, verify_eligibility=lambda: None)
    assert source.read_bytes() == b"replacement"


def test_eligibility_is_rechecked_after_hashing_before_rename(tmp_path):
    source = tmp_path / "bundle.zip"
    source.write_bytes(b"preserve me")
    def no_longer_eligible():
        raise ValueError("Git state changed")
    with open_archive_location(tmp_path, DEFAULT_ARCHIVE_DIRECTORY) as location:
        with pytest.raises(ValueError, match="Git state changed"):
            archive_verified_file(location, _identity(source), verify_eligibility=no_longer_eligible)
    assert source.read_bytes() == b"preserve me"


def test_changed_source_during_final_eligibility_check_is_not_moved(tmp_path):
    source = tmp_path / "bundle.zip"
    source.write_bytes(b"before")
    identity = _identity(source)
    with open_archive_location(tmp_path, DEFAULT_ARCHIVE_DIRECTORY) as location:
        with pytest.raises(FileChangedDuringRead):
            archive_verified_file(location, identity,
                                  verify_eligibility=lambda: source.write_bytes(b"after"))
    assert source.read_bytes() == b"after"


def test_archive_symlink_cannot_redirect_a_move(tmp_path):
    exchange = tmp_path / "exchange"
    exchange.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (exchange / DEFAULT_ARCHIVE_DIRECTORY).symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(OSError):
        with open_archive_location(exchange, DEFAULT_ARCHIVE_DIRECTORY):
            pytest.fail("link must never become the archive target")
    assert list(outside.iterdir()) == []


def test_archive_directory_replacement_is_detected(tmp_path):
    if platform_archive.is_windows():
        pytest.skip("Windows directory handles prevent replacement while open")
    with open_archive_location(tmp_path, DEFAULT_ARCHIVE_DIRECTORY) as location:
        location.directory.rename(tmp_path / "renamed")
        location.directory.mkdir()
        with pytest.raises(OSError, match="identity changed"):
            location.revalidate()
