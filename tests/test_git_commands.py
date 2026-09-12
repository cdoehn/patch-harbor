from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

import pytest

from patchharbor import git_commands
from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.errors import ErrorKind, PatchHarborError
from tests.registration_support import create_repository, git


def test_git_queries_ignore_redirecting_process_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    redirected = create_repository(tmp_path / "redirected")

    monkeypatch.setenv("GIT_DIR", str(redirected / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(redirected))
    monkeypatch.setenv("GIT_INDEX_FILE", str(redirected / ".git" / "index"))
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "must-not-run")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.bare")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")

    output = git_commands.run_git_bytes(
        "rev-parse",
        "--show-toplevel",
        cwd=repository,
    )

    observed_root = Path(output.decode("utf-8", errors="strict").strip())
    assert observed_root.resolve() == repository.resolve()


def test_git_query_preserves_binary_input_and_raw_stdout(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    payload = b"raw\x00input\xff\r\n"
    head = git(repository, "rev-parse", "HEAD").stdout.strip()
    object_format = "sha1" if len(head) == 40 else "sha256"
    digest = hashlib.new(object_format)
    digest.update(f"blob {len(payload)}\0".encode("ascii"))
    digest.update(payload)

    output = git_commands.run_git_bytes(
        "hash-object",
        "--stdin",
        cwd=repository,
        input_bytes=payload,
    )

    assert output == f"{digest.hexdigest()}\n".encode("ascii")


@pytest.mark.parametrize("stderr", [b"first git diagnostic", b"other\xffdiagnostic"])
def test_git_failures_share_one_repository_error_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stderr: bytes,
) -> None:
    def fake_run(
        command: list[str],
        **_options: object,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            command,
            128,
            stdout=b"",
            stderr=stderr,
        )

    monkeypatch.setattr(git_commands.subprocess, "run", fake_run)

    with pytest.raises(PatchHarborError) as captured:
        git_commands.run_git_bytes("status", cwd=tmp_path.resolve())

    assert exit_code_for_error(captured.value) is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR


@pytest.mark.parametrize(
    ("configured_value", "expected"),
    [
        (None, False),
        ("false", False),
        ("true", True),
    ],
)
def test_missing_and_explicit_boolean_config_values_are_canonical(
    tmp_path: Path,
    configured_value: str | None,
    expected: bool,
) -> None:
    repository = create_repository(tmp_path / "repository")
    if configured_value is not None:
        git(repository, "config", "feature.enabled", configured_value)

    assert (
        git_commands.read_boolean_config(
            repository,
            "feature.enabled",
        )
        is expected
    )


def test_malformed_boolean_config_is_a_repository_error(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    git(repository, "config", "feature.enabled", "maybe")

    with pytest.raises(PatchHarborError) as captured:
        git_commands.read_boolean_config(
            repository,
            "feature.enabled",
        )

    assert exit_code_for_error(captured.value) is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR


def test_nul_record_parser_preserves_path_bytes_and_rejects_truncation() -> None:
    assert git_commands.nul_records(
        b"a\x00path-\xff\x00",
        "paths",
    ) == (b"a", b"path-\xff")

    with pytest.raises(PatchHarborError) as captured:
        git_commands.nul_records(b"not-terminated", "paths")

    assert exit_code_for_error(captured.value) is ExitCode.REPOSITORY_ERROR
