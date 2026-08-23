from __future__ import annotations

import errno
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

import patchharbor.platform.filesystem as filesystem_module
from patchharbor.platform.errors import describe_os_error
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    MetadataSyncStatus,
    PathKind,
    UnsupportedFileTypeError,
    path_kind,
    read_stable_regular_file,
    replace_path,
    sync_directory_best_effort,
    sync_regular_file_best_effort,
)
from patchharbor.platform.locking import (
    LockUnavailable,
    exclusive_file_lock,
)
from patchharbor.platform.runtime import is_windows


@pytest.mark.parametrize(
    ("os_name", "expected"),
    (("posix", False), ("nt", True)),
)
def test_windows_detection_is_resolved_at_the_platform_boundary(
    os_name: str,
    expected: bool,
) -> None:
    assert is_windows(os_name=os_name) is expected


def test_unknown_python_os_family_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="unsupported operating system family"):
        is_windows(os_name="unknown")


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (PermissionError(), "permission denied"),
        (FileNotFoundError(), "path not found"),
        (FileExistsError(), "path already exists"),
        (NotADirectoryError(), "parent is not a directory"),
        (IsADirectoryError(), "target is a directory"),
        (OSError(errno.ENOSPC, "native wording"), "no space left on device"),
        (OSError(errno.EROFS, "native wording"), "read-only filesystem"),
        (OSError(errno.ENAMETOOLONG, "native wording"), "path is too long"),
        (OSError(errno.EBUSY, "native wording"), "resource is busy"),
        (OSError(), "operating-system operation failed"),
    ),
)
def test_os_error_descriptions_are_platform_neutral(
    error: OSError,
    expected: str,
) -> None:
    assert describe_os_error(error) == expected


def test_windows_path_and_descriptor_metadata_share_birth_time_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path_metadata = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o644,
        st_size=7,
        st_mtime_ns=100,
        st_birthtime_ns=50,
        st_ctime_ns=50,
    )
    opened_metadata = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o666,
        st_size=7,
        st_mtime_ns=100,
        st_birthtime_ns=50,
        st_ctime_ns=75,
    )
    changed_descriptor = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o666,
        st_size=7,
        st_mtime_ns=100,
        st_birthtime_ns=50,
        st_ctime_ns=80,
    )
    monkeypatch.setattr(filesystem_module, "is_windows", lambda: True)
    monkeypatch.setattr(
        filesystem_module.os.path,
        "samestat",
        lambda _first, _second: True,
    )

    assert filesystem_module._same_path_and_open_file_state(
        path_metadata,
        opened_metadata,
    )
    assert not filesystem_module._same_open_file_state(
        opened_metadata,
        changed_descriptor,
    )


def test_stable_regular_file_reader_preserves_bytes_and_final_metadata(
    tmp_path: Path,
) -> None:
    target = tmp_path / "payload.bin"
    content = b"binary\x00payload\xff\r\n"
    target.write_bytes(content)

    snapshot = read_stable_regular_file(target)

    assert snapshot.content == content
    assert snapshot.executable is False


def test_stable_regular_file_reader_rejects_non_regular_targets(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()

    with pytest.raises(UnsupportedFileTypeError):
        read_stable_regular_file(directory)


def test_path_kind_does_not_follow_symbolic_links(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    regular = tmp_path / "regular"
    directory = tmp_path / "directory"
    regular.write_bytes(b"data")
    directory.mkdir()

    assert path_kind(missing) is PathKind.MISSING
    assert path_kind(regular) is PathKind.REGULAR_FILE
    assert path_kind(directory) is PathKind.DIRECTORY
    assert PathKind.JUNCTION is not PathKind.DIRECTORY


def test_filesystem_operation_error_exposes_stable_operation() -> None:
    cause = PermissionError("native platform wording")
    error = FileSystemOperationError("cannot replace target", cause)

    assert str(error) == "cannot replace target"
    assert error.cause is cause


def test_advisory_lock_uses_ownership_instead_of_file_existence(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "persistent.lock"
    lock_path.write_bytes(b"leftover metadata\n")

    with exclusive_file_lock(lock_path):
        with pytest.raises(LockUnavailable):
            with exclusive_file_lock(lock_path):
                raise AssertionError("the same advisory lock must stay exclusive")

    with exclusive_file_lock(lock_path):
        assert lock_path.is_file()


def test_best_effort_metadata_sync_reports_actual_platform_support(
    tmp_path: Path,
) -> None:
    regular_file = tmp_path / "result.zip"
    regular_file.write_bytes(b"result bundle bytes")

    file_status = sync_regular_file_best_effort(regular_file)
    directory_status = sync_directory_best_effort(tmp_path)

    assert file_status is not MetadataSyncStatus.FAILED
    assert directory_status is not MetadataSyncStatus.FAILED
    if is_windows():
        assert directory_status is MetadataSyncStatus.UNSUPPORTED


def test_replace_path_does_not_fallback_to_cross_filesystem_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "temporary.zip"
    target = tmp_path / "result.zip"
    source.write_bytes(b"verified bundle")

    def reject_cross_device_replace(_source: object, _target: object) -> None:
        raise OSError(errno.EXDEV, "cross-device link")

    monkeypatch.setattr(
        filesystem_module.os,
        "replace",
        reject_cross_device_replace,
    )

    with pytest.raises(FileSystemOperationError) as captured:
        replace_path(source, target)

    assert captured.value.cause.errno == errno.EXDEV
    assert source.read_bytes() == b"verified bundle"
    assert not target.exists()
