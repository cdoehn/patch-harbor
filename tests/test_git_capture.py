from __future__ import annotations

from pathlib import Path
import os
import subprocess

import pytest

from patchharbor import git_capture
from patchharbor.errors import ExitCode, PatchHarborError
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


def test_git_boundary_returns_bytes_under_a_controlled_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = RepositoryPath(tmp_path.resolve())
    captured: dict[str, object] = {}
    raw_stdout = b"raw\x00\xffbytes\n"

    def fake_run(
        command: list[str],
        **options: object,
    ) -> subprocess.CompletedProcess[bytes]:
        captured["command"] = command
        captured.update(options)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=raw_stdout,
            stderr=b"",
        )

    monkeypatch.setenv("GIT_DIR", "redirected")
    monkeypatch.setenv("GIT_WORK_TREE", "redirected")
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "external-tool")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "color.ui")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "always")
    monkeypatch.setattr(git_capture.subprocess, "run", fake_run)

    assert git_capture.run_git_bytes(repository, "status", "-z") == raw_stdout
    assert captured["cwd"] == repository.value
    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["stdout"] is subprocess.PIPE
    assert captured["stderr"] is subprocess.PIPE
    assert "encoding" not in captured
    assert "text" not in captured

    command = captured["command"]
    assert command[:6] == [
        "git",
        "--no-pager",
        "-c",
        "color.ui=false",
        "-c",
        "diff.external=",
    ]
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["LC_ALL"] == "C"
    assert environment["LANG"] == "C"
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"
    assert "GIT_DIR" not in environment
    assert "GIT_WORK_TREE" not in environment
    assert "GIT_EXTERNAL_DIFF" not in environment
    assert "GIT_CONFIG_COUNT" not in environment
    assert "GIT_CONFIG_KEY_0" not in environment
    assert "GIT_CONFIG_VALUE_0" not in environment


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
    ("tree", "index"),
    [
        (b"100644 tree " + b"1" * 40 + b"\tentry\0", b""),
        (b"120000 blob " + b"1" * 40 + b"\tentry\0", b""),
        (b"100644 blob " + b"1" * 39 + b"\tentry\0", b""),
        (b"100644 blob " + b"A" * 40 + b"\tentry\0", b""),
        (
            b"100644 blob " + b"1" * 40 + b"\tz\0"
            b"100644 blob " + b"2" * 40 + b"\ta\0",
            b"",
        ),
        (b"", b"120000 " + b"1" * 40 + b" 0\tentry\0"),
        (b"", b"100644 " + b"1" * 39 + b" 0\tentry\0"),
        (b"", b"100644 " + b"A" * 40 + b" 0\tentry\0"),
        (b"", b"100644 " + b"1" * 40 + b" 1\tentry\0"),
        (
            b"",
            b"100644 " + b"1" * 40 + b" 0\tz\0"
            b"100644 " + b"2" * 40 + b" 0\ta\0",
        ),
    ],
)
def test_staged_capture_rejects_unsupported_raw_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tree: bytes,
    index: bytes,
) -> None:
    with pytest.raises(PatchHarborError) as captured:
        _records_from_raw_git_state(
            tmp_path,
            monkeypatch,
            tree=tree,
            index=index,
        )

    assert captured.value.exit_code == ExitCode.REPOSITORY_ERROR


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

    assert captured.value.exit_code == ExitCode.REPOSITORY_ERROR


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
