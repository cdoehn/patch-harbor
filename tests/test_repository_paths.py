from __future__ import annotations

import os
from pathlib import Path

import pytest

from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.errors import ErrorKind, PatchHarborError
from patchharbor.git_capture import read_head_object_id
from patchharbor.models import RepositoryPath
from patchharbor.repository_paths import (
    RepositoryRelativePath,
    validate_repository_paths,
)
from patchharbor.repository_state import capture_repository_state
from tests.registration_support import create_repository, git


def _assert_unsupported(callable_object) -> None:
    with pytest.raises(PatchHarborError) as captured:
        callable_object()

    assert exit_code_for_error(captured.value) is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    assert captured.value.error_kind is ErrorKind.UNSUPPORTED_REPOSITORY_STATE


def _capture(repository: Path) -> None:
    resolved = RepositoryPath(repository.resolve())
    capture_repository_state(resolved, read_head_object_id(resolved))


def test_repository_path_keeps_original_bytes_and_separate_portable_views(
) -> None:
    raw = "Folder/Straße.txt".encode("utf-8")

    path = RepositoryRelativePath(raw)

    assert path.original_bytes == raw
    assert path.decoded == "Folder/Straße.txt"
    assert path.parts == ("Folder", "Straße.txt")
    assert path.collision_key == "folder/strasse.txt"


def test_repository_path_resolution_uses_the_validated_posix_parts(
    tmp_path: Path,
) -> None:
    repository = RepositoryPath(tmp_path.resolve())
    path = RepositoryRelativePath(b"nested/file.bin")

    assert path.resolve_from(repository) == (
        tmp_path.resolve() / "nested" / "file.bin"
    )


@pytest.mark.parametrize(
    "path",
    [
        b"",
        b".",
        b"/absolute.txt",
        b"directory//file.txt",
        b"directory/./file.txt",
        b"directory/../file.txt",
        b"invalid-\xff.txt",
        b"control-\x00.txt",
        b"control-\x01.txt",
        b"control-\x7f.txt",
        b"bad<name.txt",
        b"bad>name.txt",
        b"bad:name.txt",
        b'bad"name.txt',
        b"bad\\name.txt",
        b"bad|name.txt",
        b"bad?name.txt",
        b"bad*name.txt",
        b"trailing.",
        b"trailing ",
        b"nested/.GiT/config",
        b"nested/.PATCHHARBOR/id",
    ],
)
def test_portable_repository_paths_reject_unsafe_segments(path: bytes) -> None:
    _assert_unsupported(lambda: validate_repository_paths((path,)))


@pytest.mark.parametrize(
    "device_name",
    [
        "CON",
        "prn.txt",
        "AuX.log",
        "nul",
        *(f"COM{number}.txt" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
        "ConIn$.txt",
        "CONOUT$",
        "clock$.log",
    ],
)
def test_portable_repository_paths_reject_windows_device_names(
    device_name: str,
) -> None:
    _assert_unsupported(
        lambda: validate_repository_paths(
            (f"nested/{device_name}".encode("utf-8"),)
        )
    )


def test_portable_repository_paths_use_casefold_without_normalization() -> None:
    validate_repository_paths(
        (
            "é.txt".encode("utf-8"),
            "e\u0301.txt".encode("utf-8"),
            b"COM10.txt",
            b"LPT0.txt",
            b".gitignore",
        )
    )

    _assert_unsupported(
        lambda: validate_repository_paths(
            ("Straße.txt".encode("utf-8"), b"STRASSE.TXT")
        )
    )


@pytest.mark.parametrize("source", ["base", "index", "untracked"])
@pytest.mark.e2e
def test_repository_state_validates_the_union_of_git_paths(
    tmp_path: Path,
    source: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    target = repository / source / ".PatchHarbor" / "payload.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"payload\x00bytes")

    if source in ("base", "index"):
        git(repository, "add", target.relative_to(repository).as_posix())
    if source == "base":
        git(repository, "commit", "--quiet", "-m", "non-portable base path")

    _assert_unsupported(lambda: _capture(repository))


@pytest.mark.skipif(
    os.name == "nt",
    reason="requires two casefold-colliding names in one working tree",
)
@pytest.mark.e2e
def test_repository_state_rejects_casefold_collisions_across_sources(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / "Straße.txt").write_bytes(b"base")
    git(repository, "add", "Straße.txt")
    git(repository, "commit", "--quiet", "-m", "casefold base")
    (repository / "STRASSE.TXT").write_bytes(b"untracked")

    _assert_unsupported(lambda: _capture(repository))


@pytest.mark.skipif(
    os.name == "nt",
    reason="requires a POSIX file name that is not valid UTF-8",
)
@pytest.mark.e2e
def test_repository_state_rejects_non_utf8_git_paths(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    raw_path = os.fsencode(repository) + b"/invalid-\xff.bin"
    descriptor = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(b"raw path")

    _assert_unsupported(lambda: _capture(repository))
