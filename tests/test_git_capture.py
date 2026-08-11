from __future__ import annotations

import os
from pathlib import Path

import pytest

from patchharbor import git_capture
from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.models import RepositoryPath, RepositoryState
from patchharbor.repository_state import capture_repository_state
from tests.registration_support import create_repository, git


pytestmark = pytest.mark.e2e


def _repository_state(repository: Path) -> RepositoryState:
    resolved = RepositoryPath(repository.resolve())
    return capture_repository_state(
        resolved,
        git_capture.read_head_object_id(resolved),
    )


def _staged_records(repository: Path):
    return _repository_state(repository).staged


def _unstaged_records(repository: Path):
    return _repository_state(repository).unstaged


def _untracked_records(repository: Path):
    return _repository_state(repository).untracked


def _assert_repository_capture_error(
    captured: pytest.ExceptionInfo[PatchHarborError],
) -> None:
    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR


def _assert_unsupported_repository_state(
    captured: pytest.ExceptionInfo[PatchHarborError],
) -> None:
    assert captured.value.exit_code is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    assert captured.value.error_kind is ErrorKind.UNSUPPORTED_REPOSITORY_STATE


@pytest.mark.parametrize("object_format", [None, "sha256"])
def test_staged_additions_preserve_binary_blob_ids_and_byte_order(
    tmp_path: Path,
    object_format: str | None,
) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format=object_format,
    )
    (repository / "z.bin").write_bytes(b"z\x00\xff\r\n")
    (repository / "a.bin").write_bytes(b"a\x00\xfe\n")
    git(repository, "add", "z.bin", "a.bin")

    records = _staged_records(repository)

    assert tuple(record.path for record in records) == (b"a.bin", b"z.bin")
    for record in records:
        path = record.path.decode("ascii")
        expected_object = git(repository, "rev-parse", f":{path}").stdout.strip()
        assert record.head_mode == b""
        assert record.head_object == b""
        assert record.index_mode == b"100644"
        assert record.index_object == expected_object.encode("ascii")


def test_staged_transitions_compare_base_and_index(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / "deleted.txt").write_text("remove me\n", encoding="utf-8")
    (repository / "renamed-from.txt").write_text("move me\n", encoding="utf-8")
    git(repository, "add", "deleted.txt", "renamed-from.txt")
    git(repository, "commit", "--quiet", "-m", "second base")

    head_objects = {
        path: git(repository, "rev-parse", f"HEAD:{path}").stdout.strip().encode(
            "ascii"
        )
        for path in ("tracked.txt", "deleted.txt", "renamed-from.txt")
    }
    (repository / "tracked.txt").write_text("staged change\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "rm", "--quiet", "deleted.txt")
    git(repository, "mv", "renamed-from.txt", "renamed-to.txt")

    records = {record.path: record for record in _staged_records(repository)}

    modified = records[b"tracked.txt"]
    assert (modified.head_mode, modified.head_object) == (
        b"100644",
        head_objects["tracked.txt"],
    )
    assert modified.index_mode == b"100644"
    assert modified.index_object == git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")

    deleted = records[b"deleted.txt"]
    assert (deleted.head_mode, deleted.head_object) == (
        b"100644",
        head_objects["deleted.txt"],
    )
    assert (deleted.index_mode, deleted.index_object) == (b"", b"")

    renamed_from = records[b"renamed-from.txt"]
    assert (renamed_from.head_mode, renamed_from.head_object) == (
        b"100644",
        head_objects["renamed-from.txt"],
    )
    assert (renamed_from.index_mode, renamed_from.index_object) == (b"", b"")

    renamed_to = records[b"renamed-to.txt"]
    assert (renamed_to.head_mode, renamed_to.head_object) == (b"", b"")
    assert (renamed_to.index_mode, renamed_to.index_object) == (
        b"100644",
        head_objects["renamed-from.txt"],
    )


@pytest.mark.skipif(
    os.name == "nt",
    reason="executable mode is not a portable Windows working-tree behavior",
)
def test_staged_mode_change_is_distinct_from_blob_content(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    git(repository, "config", "core.fileMode", "true")
    tracked = repository / "tracked.txt"
    tracked.chmod(tracked.stat().st_mode | 0o111)
    git(repository, "add", "tracked.txt")

    records = _staged_records(repository)

    assert len(records) == 1
    record = records[0]
    assert record.path == b"tracked.txt"
    assert record.head_mode == b"100644"
    assert record.index_mode == b"100755"
    assert record.head_object == record.index_object


@pytest.mark.skipif(
    os.name == "nt",
    reason="executable mode is not a portable Windows working-tree behavior",
)
def test_matching_staged_and_worktree_mode_is_not_an_unstaged_change(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    git(repository, "config", "core.fileMode", "true")
    tracked = repository / "tracked.txt"
    git(repository, "update-index", "--chmod=+x", "tracked.txt")
    tracked.chmod(tracked.stat().st_mode | 0o111)

    state = _repository_state(repository)

    assert len(state.staged) == 1
    assert state.unstaged == ()


def test_index_rejects_a_non_blob_object_even_with_a_file_mode(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tree_object = git(repository, "rev-parse", "HEAD^{tree}").stdout.strip()
    git(
        repository,
        "update-index",
        "--add",
        "--cacheinfo",
        f"100644,{tree_object},tree-as-file",
    )

    with pytest.raises(PatchHarborError) as captured:
        _repository_state(repository)

    _assert_unsupported_repository_state(captured)


@pytest.mark.parametrize("object_format", [None, "sha256"])
def test_unstaged_change_preserves_index_identity_and_worktree_bytes(
    tmp_path: Path,
    object_format: str | None,
) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format=object_format,
    )
    tracked = repository / "tracked.txt"
    content = b"changed\x00payload\xff\r\n"
    tracked.write_bytes(content)

    records = _unstaged_records(repository)

    assert len(records) == 1
    record = records[0]
    assert record.path == b"tracked.txt"
    assert record.status == b"M"
    assert record.index_mode == b"100644"
    assert record.index_object == git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")
    assert record.worktree_kind == b"regular"
    assert record.worktree_mode == b"100644"
    assert record.worktree_content == content


def test_unstaged_deletion_records_a_missing_worktree_side(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    index_object = git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")
    (repository / "tracked.txt").unlink()

    records = _unstaged_records(repository)

    assert len(records) == 1
    record = records[0]
    assert record.path == b"tracked.txt"
    assert record.status == b"D"
    assert record.index_mode == b"100644"
    assert record.index_object == index_object
    assert record.worktree_kind == b"missing"
    assert record.worktree_mode == b""
    assert record.worktree_content == b""


@pytest.mark.skipif(
    os.name == "nt",
    reason="executable mode is not a portable Windows working-tree behavior",
)
@pytest.mark.parametrize(
    ("core_file_mode", "expected_mode"),
    [("true", b"100755"), ("false", b"100644")],
)
def test_unstaged_worktree_mode_respects_core_file_mode(
    tmp_path: Path,
    core_file_mode: str,
    expected_mode: bytes,
) -> None:
    repository = create_repository(tmp_path / "repository")
    git(repository, "config", "core.fileMode", core_file_mode)
    tracked = repository / "tracked.txt"
    tracked.chmod(tracked.stat().st_mode | 0o111)
    tracked.write_bytes(b"mode and content changed\n")

    records = _unstaged_records(repository)

    assert len(records) == 1
    record = records[0]
    assert record.status == b"M"
    assert record.index_mode == b"100644"
    assert record.worktree_mode == expected_mode
    assert record.worktree_content == tracked.read_bytes()


@pytest.mark.skipif(
    os.name == "nt",
    reason="creating symbolic links is not generally available on Windows",
)
def test_unstaged_capture_never_follows_a_symbolic_link(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"must not be captured\n")
    tracked.unlink()
    tracked.symlink_to(outside)

    with pytest.raises(PatchHarborError) as captured:
        _repository_state(repository)

    _assert_unsupported_repository_state(captured)


def test_deleted_tracked_path_must_really_be_missing(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    tracked.unlink()
    tracked.mkdir()

    with pytest.raises(PatchHarborError) as captured:
        _repository_state(repository)

    _assert_unsupported_repository_state(captured)


def test_unstaged_read_failure_is_categorized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"changed\n")
    real_open = os.open

    def denied_open(path: os.PathLike[str], flags: int, *args: int) -> int:
        if os.fspath(path) == os.fspath(tracked):
            raise PermissionError("injected read denial")
        return real_open(path, flags, *args)

    monkeypatch.setattr(git_capture.os, "open", denied_open)

    with pytest.raises(PatchHarborError) as captured:
        _repository_state(repository)

    _assert_repository_capture_error(captured)


def test_unstaged_file_replacement_during_capture_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"first changed content\n")
    real_open = os.open
    replaced = False

    def replacing_open(path: os.PathLike[str], flags: int, *args: int) -> int:
        nonlocal replaced
        if not replaced and os.fspath(path) == os.fspath(tracked):
            replaced = True
            tracked.replace(repository / "original.txt")
            tracked.write_bytes(b"replacement content\n")
        return real_open(path, flags, *args)

    monkeypatch.setattr(git_capture.os, "open", replacing_open)

    with pytest.raises(PatchHarborError) as captured:
        _repository_state(repository)

    assert replaced is True
    _assert_repository_capture_error(captured)


def test_untracked_capture_preserves_sorted_paths_modes_and_bytes(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    nested = repository / "nested"
    nested.mkdir()
    (repository / "z-empty.bin").write_bytes(b"")
    (repository / "a-binary.bin").write_bytes(b"binary\x00payload\xff\r\n")
    (nested / "é.txt").write_bytes(b"utf8 path\x00payload\n")

    records = _untracked_records(repository)

    assert tuple(record.path for record in records) == (
        b"a-binary.bin",
        "nested/é.txt".encode("utf-8"),
        b"z-empty.bin",
    )
    by_path = {record.path: record for record in records}
    assert by_path[b"a-binary.bin"].mode == b"100644"
    assert by_path[b"a-binary.bin"].content == b"binary\x00payload\xff\r\n"
    assert by_path["nested/é.txt".encode("utf-8")].content == (
        b"utf8 path\x00payload\n"
    )
    assert by_path[b"z-empty.bin"].content == b""


@pytest.mark.skipif(
    os.name == "nt",
    reason="executable mode is not a portable Windows working-tree behavior",
)
def test_untracked_capture_respects_an_executable_mode(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    git(repository, "config", "core.fileMode", "true")
    script = repository / "run.sh"
    script.write_bytes(b"#!/bin/sh\n")
    script.chmod(script.stat().st_mode | 0o111)

    records = _untracked_records(repository)

    assert len(records) == 1
    assert records[0].path == b"run.sh"
    assert records[0].mode == b"100755"
    assert records[0].content == b"#!/bin/sh\n"


@pytest.mark.skipif(
    os.name == "nt",
    reason="creating symbolic links is not generally available on Windows",
)
def test_untracked_capture_never_follows_a_symbolic_link(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"must not be captured")
    (repository / "link.bin").symlink_to(outside)

    with pytest.raises(PatchHarborError) as captured:
        _repository_state(repository)

    _assert_unsupported_repository_state(captured)


def test_untracked_file_replacement_during_capture_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    target = repository / "new.bin"
    target.write_bytes(b"first content")
    real_open = os.open
    replaced = False

    def replacing_open(path: os.PathLike[str], flags: int, *args: int) -> int:
        nonlocal replaced
        if not replaced and os.fspath(path) == os.fspath(target):
            replaced = True
            target.replace(repository / "original.bin")
            target.write_bytes(b"replacement")
        return real_open(path, flags, *args)

    monkeypatch.setattr(git_capture.os, "open", replacing_open)

    with pytest.raises(PatchHarborError) as captured:
        _repository_state(repository)

    assert replaced is True
    _assert_repository_capture_error(captured)


def test_unstaged_capture_is_stable_under_diff_configuration(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"configured diff must not change raw state\n")
    baseline = _unstaged_records(repository)

    git(repository, "config", "color.ui", "always")
    git(repository, "config", "diff.renames", "true")
    git(repository, "config", "status.renames", "true")
    git(repository, "config", "diff.external", "must-not-run")
    git(repository, "config", "diff.fixture.textconv", "must-not-run")
    (repository / ".gitattributes").write_text(
        "tracked.txt diff=fixture\n",
        encoding="utf-8",
    )

    assert _unstaged_records(repository) == baseline
