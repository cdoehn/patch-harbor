from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from patchharbor import git_capture
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryPath


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
