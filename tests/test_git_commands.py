from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from patchharbor import git_commands
from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError


def test_git_queries_use_one_canonical_non_interactive_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setenv("GIT_INDEX_FILE", "redirected")
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "external-tool")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "color.ui")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "always")
    monkeypatch.setattr(git_commands.subprocess, "run", fake_run)

    assert git_commands.run_git_bytes(
        "status",
        "-z",
        cwd=tmp_path.resolve(),
    ) == raw_stdout
    assert captured["cwd"] == tmp_path.resolve()
    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["stdout"] is subprocess.PIPE
    assert captured["stderr"] is subprocess.PIPE
    assert "encoding" not in captured
    assert "text" not in captured

    command = captured["command"]
    assert command == [
        "git",
        "--no-pager",
        "-c",
        "color.ui=false",
        "-c",
        "diff.external=",
        "-c",
        "diff.renames=false",
        "-c",
        "status.renames=false",
        "status",
        "-z",
    ]
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["LC_ALL"] == "C"
    assert environment["LANG"] == "C"
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"
    assert environment["GIT_PAGER"] == "cat"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_EXTERNAL_DIFF",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_KEY_0",
        "GIT_CONFIG_VALUE_0",
    ):
        assert name not in environment


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [
        (1, b"", False),
        (0, b"false\0", False),
        (0, b"true\0", True),
    ],
)
def test_missing_and_explicit_boolean_config_values_are_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    stdout: bytes,
    expected: bool,
) -> None:
    def fake_run(
        command: list[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            command,
            returncode,
            stdout=stdout,
            stderr=b"",
        )

    monkeypatch.setattr(git_commands.subprocess, "run", fake_run)

    assert (
        git_commands.read_boolean_config(
            tmp_path.resolve(),
            "core.sparseCheckout",
        )
        is expected
    )


def test_malformed_boolean_config_is_a_repository_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=b"maybe\0",
            stderr=b"",
        )

    monkeypatch.setattr(git_commands.subprocess, "run", fake_run)

    with pytest.raises(PatchHarborError) as captured:
        git_commands.read_boolean_config(
            tmp_path.resolve(),
            "core.sparseCheckout",
        )

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR


def test_nul_record_parser_preserves_path_bytes_and_rejects_truncation() -> None:
    assert git_commands.nul_records(
        b"a\x00path-\xff\x00",
        "paths",
    ) == (b"a", b"path-\xff")

    with pytest.raises(PatchHarborError) as captured:
        git_commands.nul_records(b"not-terminated", "paths")

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
