from __future__ import annotations

import errno
from pathlib import Path

import pytest

from patchharbor.platform.errors import describe_os_error
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    path_kind,
)
from patchharbor.platform.runtime import PlatformFamily, platform_family


@pytest.mark.parametrize(
    ("os_name", "expected"),
    (("posix", PlatformFamily.POSIX), ("nt", PlatformFamily.WINDOWS)),
)
def test_runtime_family_is_resolved_at_the_platform_boundary(
    os_name: str,
    expected: PlatformFamily,
) -> None:
    assert platform_family(os_name=os_name) is expected


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


def test_path_kind_does_not_follow_symbolic_links(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    regular = tmp_path / "regular"
    directory = tmp_path / "directory"
    regular.write_bytes(b"data")
    directory.mkdir()

    assert path_kind(missing) is PathKind.MISSING
    assert path_kind(regular) is PathKind.REGULAR_FILE
    assert path_kind(directory) is PathKind.DIRECTORY


def test_filesystem_operation_error_exposes_stable_operation() -> None:
    cause = PermissionError("native platform wording")
    error = FileSystemOperationError(
        "cannot replace target",
        Path("target"),
        cause,
    )

    assert str(error) == "cannot replace target"
    assert error.cause is cause
