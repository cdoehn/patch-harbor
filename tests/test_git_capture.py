from __future__ import annotations

from pathlib import Path
import os

import pytest

from patchharbor import git_capture
from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryPath,
    StagedRecord,
)
from tests.registration_support import create_repository, git


@pytest.mark.parametrize(
    ("object_format", "value"),
    [
        (GitObjectFormat.SHA1, "a" * 40),
        (GitObjectFormat.SHA256, "b" * 64),
    ],
)
def test_git_object_id_models_complete_supported_formats(
    object_format: GitObjectFormat,
    value: str,
) -> None:
    object_id = GitObjectId(value=value, object_format=object_format)

    assert str(object_id) == value
    assert GitObjectFormat.for_hex_length(len(value)) is object_format


@pytest.mark.parametrize(
    ("object_format", "value"),
    [
        (GitObjectFormat.SHA1, "a" * 39),
        (GitObjectFormat.SHA1, "A" * 40),
        (GitObjectFormat.SHA256, "z" * 64),
        (GitObjectFormat.SHA256, "b" * 63),
    ],
)
def test_git_object_id_rejects_incomplete_or_noncanonical_values(
    object_format: GitObjectFormat,
    value: str,
) -> None:
    with pytest.raises(ValueError):
        GitObjectId(value=value, object_format=object_format)


@pytest.mark.parametrize(
    ("raw", "object_format"),
    [
        (b"1" * 40 + b"\n", GitObjectFormat.SHA1),
        (b"2" * 64 + b"\n", GitObjectFormat.SHA256),
    ],
)
def test_head_capture_preserves_the_complete_object_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
    object_format: GitObjectFormat,
) -> None:
    repository = RepositoryPath(tmp_path.resolve())
    monkeypatch.setattr(git_capture, "run_git_bytes", lambda *_args: raw)

    object_id = git_capture.read_head_object_id(repository)

    assert object_id.object_format is object_format
    assert object_id.value.encode("ascii") == raw.rstrip(b"\n")


def _staged_records(repository: Path):
    resolved = RepositoryPath(repository.resolve())
    return git_capture.read_staged_records(
        resolved,
        git_capture.read_head_object_id(resolved),
    )


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


def _records_from_raw_git_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    tree: bytes,
    index: bytes,
    object_format: GitObjectFormat = GitObjectFormat.SHA1,
) -> tuple[StagedRecord, ...]:
    outputs = iter((tree, index))
    monkeypatch.setattr(
        git_capture,
        "run_git_bytes",
        lambda *_args: next(outputs),
    )
    object_name = "a" * object_format.object_id_hex_length
    return git_capture.read_staged_records(
        RepositoryPath(tmp_path.resolve()),
        GitObjectId(value=object_name, object_format=object_format),
    )


@pytest.mark.parametrize(
    ("tree", "index", "expected_exit_code"),
    [
        (
            b"100644 tree " + b"1" * 40 + b"\tentry\0",
            b"",
            ExitCode.UNSUPPORTED_REPOSITORY_STATE,
        ),
        (
            b"120000 blob " + b"1" * 40 + b"\tentry\0",
            b"",
            ExitCode.UNSUPPORTED_REPOSITORY_STATE,
        ),
        (
            b"100644 blob " + b"1" * 39 + b"\tentry\0",
            b"",
            ExitCode.REPOSITORY_ERROR,
        ),
        (
            b"100644 blob " + b"A" * 40 + b"\tentry\0",
            b"",
            ExitCode.REPOSITORY_ERROR,
        ),
        (
            b"100644 blob " + b"1" * 40 + b"\tz\0"
            b"100644 blob " + b"2" * 40 + b"\ta\0",
            b"",
            ExitCode.REPOSITORY_ERROR,
        ),
        (
            b"",
            b"120000 " + b"1" * 40 + b" 0\tentry\0",
            ExitCode.UNSUPPORTED_REPOSITORY_STATE,
        ),
        (
            b"",
            b"100644 " + b"1" * 39 + b" 0\tentry\0",
            ExitCode.REPOSITORY_ERROR,
        ),
        (
            b"",
            b"100644 " + b"A" * 40 + b" 0\tentry\0",
            ExitCode.REPOSITORY_ERROR,
        ),
        (
            b"",
            b"100644 " + b"1" * 40 + b" 1\tentry\0",
            ExitCode.UNSUPPORTED_REPOSITORY_STATE,
        ),
        (
            b"",
            b"100644 " + b"1" * 40 + b" 0\tz\0"
            b"100644 " + b"2" * 40 + b" 0\ta\0",
            ExitCode.REPOSITORY_ERROR,
        ),
    ],
)
def test_staged_capture_rejects_unsupported_raw_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tree: bytes,
    index: bytes,
    expected_exit_code: ExitCode,
) -> None:
    with pytest.raises(PatchHarborError) as captured:
        _records_from_raw_git_state(
            tmp_path,
            monkeypatch,
            tree=tree,
            index=index,
        )

    assert captured.value.exit_code is expected_exit_code


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
        _staged_records(repository)

    assert (
        captured.value.exit_code
        is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    )


def _unstaged_records(repository: Path):
    resolved = RepositoryPath(repository.resolve())
    return git_capture.read_unstaged_records(
        resolved,
        git_capture.read_head_object_id(resolved).object_format,
    )


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


def _assert_repository_capture_error(
    captured: pytest.ExceptionInfo[PatchHarborError],
) -> None:
    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR


def _assert_unsupported_repository_state(
    captured: pytest.ExceptionInfo[PatchHarborError],
) -> None:
    assert (
        captured.value.exit_code
        is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    )
    assert (
        captured.value.error_kind
        is ErrorKind.UNSUPPORTED_REPOSITORY_STATE
    )


@pytest.mark.parametrize("status", [b"A", b"T", b"U"])
def test_unstaged_capture_accepts_only_modified_and_deleted_statuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: bytes,
) -> None:
    object_name = b"1" * GitObjectFormat.SHA1.object_id_hex_length
    raw = b"".join(
        (
            b":100644 100644 ",
            object_name,
            b" ",
            b"0" * GitObjectFormat.SHA1.object_id_hex_length,
            b" ",
            status,
            b"\0tracked.txt\0",
        )
    )
    monkeypatch.setattr(
        git_capture,
        "run_git_bytes",
        lambda *_args, **_kwargs: raw,
    )

    with pytest.raises(PatchHarborError) as captured:
        git_capture.read_unstaged_records(
            RepositoryPath(tmp_path.resolve()),
            GitObjectFormat.SHA1,
        )

    _assert_unsupported_repository_state(captured)


def test_malformed_unstaged_git_data_is_a_repository_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        git_capture,
        "run_git_bytes",
        lambda *_args, **_kwargs: b"malformed-without-nul",
    )

    with pytest.raises(PatchHarborError) as captured:
        git_capture.read_unstaged_records(
            RepositoryPath(tmp_path.resolve()),
            GitObjectFormat.SHA1,
        )

    _assert_repository_capture_error(captured)


@pytest.mark.skipif(
    os.name == "nt",
    reason="creating symbolic links is not generally available on Windows",
)
def test_unstaged_capture_never_follows_a_symbolic_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    target = tmp_path / "target.txt"
    target.write_bytes(b"must not be captured\n")
    tracked.unlink()
    tracked.symlink_to(target)
    object_name = git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")
    raw = b"".join(
        (
            b":100644 100644 ",
            object_name,
            b" ",
            b"0" * len(object_name),
            b" M\0tracked.txt\0",
        )
    )
    outputs = iter((raw, b"false\0"))
    monkeypatch.setattr(
        git_capture,
        "run_git_bytes",
        lambda *_args, **_kwargs: next(outputs),
    )

    with pytest.raises(PatchHarborError) as captured:
        git_capture.read_unstaged_records(
            RepositoryPath(repository.resolve()),
            GitObjectFormat.for_hex_length(len(object_name)),
        )

    _assert_unsupported_repository_state(captured)


def test_deleted_tracked_path_must_really_be_missing(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    tracked.unlink()
    tracked.mkdir()

    with pytest.raises(PatchHarborError) as captured:
        _unstaged_records(repository)

    _assert_unsupported_repository_state(captured)


def test_unstaged_read_failure_is_categorized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"changed\n")
    resolved = RepositoryPath(repository.resolve())
    object_format = git_capture.read_head_object_id(resolved).object_format
    real_open = os.open

    def denied_open(path: os.PathLike[str], flags: int, *args: int) -> int:
        if os.fspath(path) == os.fspath(tracked):
            raise PermissionError("injected read denial")
        return real_open(path, flags, *args)

    monkeypatch.setattr(git_capture.os, "open", denied_open)

    with pytest.raises(PatchHarborError) as captured:
        git_capture.read_unstaged_records(resolved, object_format)

    _assert_repository_capture_error(captured)


def test_unstaged_file_replacement_during_capture_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"first changed content\n")
    resolved = RepositoryPath(repository.resolve())
    object_format = git_capture.read_head_object_id(resolved).object_format
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
        git_capture.read_unstaged_records(resolved, object_format)

    assert replaced is True
    _assert_repository_capture_error(captured)


def _untracked_records(repository: Path):
    return git_capture.read_untracked_records(
        RepositoryPath(repository.resolve())
    )


def test_untracked_capture_preserves_sorted_paths_modes_and_bytes(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    nested = repository / "nested"
    nested.mkdir()
    (repository / "z-empty.bin").write_bytes(b"")
    (repository / "a-binary.bin").write_bytes(
        b"binary\x00payload\xff\r\n"
    )
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


def test_untracked_capture_rejects_a_non_utf8_git_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        git_capture,
        "run_git_bytes",
        lambda *_args, **_kwargs: b"invalid-\xff.bin\0",
    )

    with pytest.raises(PatchHarborError) as captured:
        git_capture.read_untracked_records(
            RepositoryPath(tmp_path.resolve())
        )

    _assert_repository_capture_error(captured)


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
        _untracked_records(repository)

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
        _untracked_records(repository)

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
