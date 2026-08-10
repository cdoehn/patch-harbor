from __future__ import annotations

from pathlib import Path

import pytest

from patchharbor import repository_state
from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.git_capture import read_head_object_id
from patchharbor.models import RepositoryPath
from patchharbor.repository_paths import RepositoryRelativePath
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    capture_repository_state,
)
from tests.registration_support import create_repository, git


pytestmark = pytest.mark.e2e


def _capture(repository: Path):
    resolved = RepositoryPath(repository.resolve())
    return capture_repository_state(
        resolved,
        read_head_object_id(resolved),
    )


def test_repository_state_capture_is_reusable_without_cli_or_registration(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")

    assert _capture(repository).dirty is False

    (repository / "staged.txt").write_bytes(b"staged\x00bytes\n")
    git(repository, "add", "staged.txt")
    (repository / "tracked.txt").write_bytes(b"unstaged\r\n")
    (repository / "untracked.bin").write_bytes(b"untracked\x00\xff")

    state = _capture(repository)

    assert state.dirty is True
    assert tuple(record.path for record in state.staged) == (b"staged.txt",)
    assert tuple(record.path for record in state.unstaged) == (b"tracked.txt",)
    assert tuple(record.path for record in state.untracked) == (b"untracked.bin",)


def test_reusable_state_capture_applies_the_unsupported_state_guard(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    git(repository, "config", "core.sparseCheckout", "true")

    with pytest.raises(PatchHarborError) as captured:
        _capture(repository)

    assert captured.value.exit_code is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    assert captured.value.error_kind is ErrorKind.UNSUPPORTED_REPOSITORY_STATE


def test_consistent_snapshot_rejects_a_repository_change_during_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    resolved = RepositoryPath(repository.resolve())
    original_reader = repository_state.read_untracked_records
    changed = False

    def read_then_change(
        repository_path: RepositoryPath,
        paths: tuple[RepositoryRelativePath, ...],
    ):
        nonlocal changed
        records = original_reader(repository_path, paths)
        if not changed:
            changed = True
            (repository / "tracked.txt").write_bytes(b"changed during capture\n")
        return records

    monkeypatch.setattr(
        repository_state,
        "read_untracked_records",
        read_then_change,
    )

    with pytest.raises(PatchHarborError) as captured:
        capture_consistent_repository_snapshot(resolved)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR

    monkeypatch.setattr(
        repository_state,
        "read_untracked_records",
        original_reader,
    )
    assert capture_consistent_repository_snapshot(resolved).state.dirty is True
