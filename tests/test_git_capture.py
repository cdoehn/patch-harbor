from __future__ import annotations

from pathlib import Path
import os
import subprocess

import pytest

from patchharbor import git_capture
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryPath
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


def test_staged_modification_and_deletion_compare_head_with_index(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / "deleted.txt").write_text("remove me\n", encoding="utf-8")
    git(repository, "add", "deleted.txt")
    git(repository, "commit", "--quiet", "-m", "second base")
    tracked_head = git(
        repository,
        "rev-parse",
        "HEAD:tracked.txt",
    ).stdout.strip()
    deleted_head = git(
        repository,
        "rev-parse",
        "HEAD:deleted.txt",
    ).stdout.strip()

    (repository / "tracked.txt").write_text("staged change\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "rm", "--quiet", "deleted.txt")

    records = {record.path: record for record in _staged_records(repository)}

    modified = records[b"tracked.txt"]
    assert modified.head_mode == b"100644"
    assert modified.head_object == tracked_head.encode("ascii")
    assert modified.index_mode == b"100644"
    assert modified.index_object == git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")

    deleted = records[b"deleted.txt"]
    assert deleted.head_mode == b"100644"
    assert deleted.head_object == deleted_head.encode("ascii")
    assert deleted.index_mode == b""
    assert deleted.index_object == b""


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
