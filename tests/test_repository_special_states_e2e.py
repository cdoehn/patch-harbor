from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from tests.platform_support import create_symlink_or_skip, run_cli
from tests.registration_support import (
    create_repository,
    git,
    isolated_user_environment,
)


pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def isolate_repository_state_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in isolated_user_environment(tmp_path / "user").items():
        monkeypatch.setenv(name, value)


def _register(repository: Path) -> None:
    assert run_cli(repository, "register").returncode == 0


def _assert_context_rejects_unsupported_state(repository: Path) -> None:
    completed = run_cli(repository, "context", "--json")

    assert completed.returncode == 13
    document = json.loads(completed.stdout)
    assert document["success"] is False
    assert document["result"] is None
    assert document["process_exit_code"] == 13
    error = document["error"]
    assert isinstance(error, dict)
    assert error["kind"] == "unsupported_repository_state"
    assert error["patchharbor_error_code"] == 13


def _run_git_with_input(
    repository: Path,
    *arguments: str,
    input_bytes: bytes,
) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return completed.stdout


def _write_blob(repository: Path, content: bytes) -> str:
    return _run_git_with_input(
        repository,
        "hash-object",
        "-w",
        "--stdin",
        input_bytes=content,
    ).decode("ascii").strip()


def test_context_rejects_unresolved_merge_stages(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    base = git(repository, "rev-parse", "HEAD:tracked.txt").stdout.strip()
    ours = _write_blob(repository, b"ours\n")
    theirs = _write_blob(repository, b"theirs\n")
    git(repository, "update-index", "--force-remove", "tracked.txt")
    _run_git_with_input(
        repository,
        "update-index",
        "--index-info",
        input_bytes=(
            f"100644 {base} 1\ttracked.txt\n"
            f"100644 {ours} 2\ttracked.txt\n"
            f"100644 {theirs} 3\ttracked.txt\n"
        ).encode("ascii"),
    )

    _assert_context_rejects_unsupported_state(repository)


@pytest.mark.parametrize(
    "index_flag",
    ["--assume-unchanged", "--skip-worktree"],
)
def test_context_rejects_unsupported_index_flags(
    tmp_path: Path,
    index_flag: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    git(repository, "update-index", index_flag, "tracked.txt")

    _assert_context_rejects_unsupported_state(repository)


def test_context_rejects_intent_to_add(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    (repository / "planned.txt").write_text("planned\n", encoding="utf-8")
    git(repository, "add", "--intent-to-add", "planned.txt")

    _assert_context_rejects_unsupported_state(repository)


@pytest.mark.parametrize(
    "configuration_name",
    ["core.sparseCheckout", "index.sparse"],
)
def test_context_rejects_sparse_repository_modes(
    tmp_path: Path,
    configuration_name: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    git(repository, "config", configuration_name, "true")

    _assert_context_rejects_unsupported_state(repository)


@pytest.mark.parametrize(
    ("mode", "object_expression", "path"),
    [
        ("120000", "HEAD:tracked.txt", "link-entry"),
        ("160000", "HEAD", "gitlink-entry"),
    ],
)
@pytest.mark.parametrize("committed", [False, True])
def test_context_rejects_tracked_symlink_and_gitlink_modes(
    tmp_path: Path,
    mode: str,
    object_expression: str,
    path: str,
    committed: bool,
) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    object_name = git(repository, "rev-parse", object_expression).stdout.strip()
    git(
        repository,
        "update-index",
        "--add",
        "--cacheinfo",
        f"{mode},{object_name},{path}",
    )
    if committed:
        git(repository, "commit", "--quiet", "-m", "special base entry")

    _assert_context_rejects_unsupported_state(repository)


def test_context_rejects_a_special_type_at_a_tracked_path(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    tracked = repository / "tracked.txt"
    tracked.unlink()
    tracked.mkdir()

    _assert_context_rejects_unsupported_state(repository)


def test_context_rejects_an_untracked_symbolic_link(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    create_symlink_or_skip(repository / "link.bin", outside)

    _assert_context_rejects_unsupported_state(repository)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFOs")
def test_context_rejects_an_untracked_fifo(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    _register(repository)
    os.mkfifo(repository / "events.pipe")

    _assert_context_rejects_unsupported_state(repository)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="requires POSIX FIFOs")
def test_context_ignores_a_special_entry_excluded_by_git(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / ".gitignore").write_text("ignored.pipe\n", encoding="utf-8")
    git(repository, "add", ".gitignore")
    git(repository, "commit", "--quiet", "-m", "ignore special fixture")
    _register(repository)
    os.mkfifo(repository / "ignored.pipe")

    completed = run_cli(repository, "context", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["success"] is True
    assert document["result"]["dirty"] is False
