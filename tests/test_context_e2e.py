from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from patchharbor.models import RepositoryContext
from patchharbor.repository_state import capture_repository_context
from tests.platform_support import project_environment, run_cli
from tests.registration_support import (
    create_repository,
    git,
    isolated_user_environment,
    release_repository_lock_holder,
    start_repository_lock_holder,
    stop_repository_lock_holder,
)


pytestmark = pytest.mark.e2e


CLEAN_FINGERPRINT = "7c9d2a24e397e0e5"


@pytest.fixture(autouse=True)
def isolate_context_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in isolated_user_environment(tmp_path / "user").items():
        monkeypatch.setenv(name, value)


def _registered_id(repository: Path) -> str:
    return (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()


@pytest.mark.parametrize("explicit_path", [False, True])
def test_context_json_reports_the_registered_clean_state(
    tmp_path: Path,
    explicit_path: bool,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0

    invocation_directory = tmp_path if explicit_path else repository
    arguments = (str(repository),) if explicit_path else ()
    completed = run_cli(
        invocation_directory,
        "context",
        *arguments,
        "--json",
    )

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert set(document) == {
        "output_version",
        "command",
        "success",
        "result",
        "error",
        "process_exit_code",
    }
    assert document["output_version"] == 1
    assert document["command"] == "context"
    assert document["success"] is True
    assert document["error"] is None
    assert document["process_exit_code"] == 0

    result = document["result"]
    assert isinstance(result, dict)
    assert set(result) == {
        "repo_id",
        "repository_path",
        "base_commit",
        "dirty",
        "state_fingerprint",
        "fingerprint_algorithm",
    }
    assert result == {
        "repo_id": _registered_id(repository),
        "repository_path": str(repository.resolve()),
        "base_commit": git(repository, "rev-parse", "HEAD").stdout.strip(),
        "dirty": False,
        "state_fingerprint": CLEAN_FINGERPRINT,
        "fingerprint_algorithm": "patchharbor-state-v1",
    }


def test_context_rejects_an_unregistered_repository(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")

    completed = run_cli(repository, "context", "--json")

    assert completed.returncode == 8
    document = json.loads(completed.stdout)
    assert document["success"] is False
    assert document["result"] is None
    assert document["process_exit_code"] == 8
    assert document["error"]["kind"] == "repository_resolution_error"
    assert document["error"]["patchharbor_error_code"] == 8


def test_context_matches_the_normative_untracked_reference_vector(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    (repository / "note.txt").write_bytes(b"hello\n")

    result = _captured_context(repository)

    assert result.dirty is True
    assert result.state_fingerprint == "05fe268b93ee2ea1"


def test_context_excludes_ignored_and_internal_untracked_files(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / ".gitignore").write_text("ignored.bin\n", encoding="utf-8")
    git(repository, "add", ".gitignore")
    git(repository, "commit", "--quiet", "-m", "ignore fixture")
    assert run_cli(repository, "register").returncode == 0
    clean = _captured_context(repository)
    (repository / "ignored.bin").write_bytes(b"ignored\x00payload")
    (repository / ".patchharbor" / "transient.bin").write_bytes(
        b"internal\x00payload"
    )

    excluded = _captured_context(repository)

    assert excluded.dirty is False
    assert excluded.state_fingerprint == clean.state_fingerprint


def test_register_rejects_a_dirty_state_before_creating_identity(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")

    completed = run_cli(repository, "register")

    assert completed.returncode == 8
    assert not (repository / ".patchharbor").exists()


def test_context_respects_the_repository_lock(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    repo_id = _registered_id(repository)
    holder = start_repository_lock_holder(
        repo_id,
        environment=project_environment(),
    )
    try:
        completed = run_cli(repository, "context", "--json")
        assert completed.returncode == 12
        document = json.loads(completed.stdout)
        assert document["success"] is False
        assert document["result"] is None
        assert document["process_exit_code"] == 12
        assert document["error"]["kind"] == "repository_busy"
        assert release_repository_lock_holder(holder) == 0

        retry = run_cli(repository, "context", "--json")
        assert retry.returncode == 0
    finally:
        stop_repository_lock_holder(holder)


def _captured_context(repository: Path) -> RepositoryContext:
    return capture_repository_context(repository)


def test_clean_fingerprint_is_independent_of_the_base_commit(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    before = _captured_context(repository)

    (repository / "tracked.txt").write_text("next base\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "commit", "--quiet", "-m", "next base")
    after = _captured_context(repository)

    assert before.base_commit != after.base_commit
    assert before.state_fingerprint == after.state_fingerprint
    assert before.dirty is False
    assert after.dirty is False


def test_untracked_fingerprint_is_independent_of_the_base_commit(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    (repository / "note.txt").write_bytes(b"hello\n")
    before = _captured_context(repository)

    (repository / "tracked.txt").write_text("next base\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "commit", "--quiet", "-m", "next base")
    after = _captured_context(repository)

    assert before.base_commit != after.base_commit
    assert before.state_fingerprint == after.state_fingerprint
    assert before.dirty is True
    assert after.dirty is True


def test_context_preserves_a_full_sha256_base_commit(tmp_path: Path) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format="sha256",
    )
    assert run_cli(repository, "register").returncode == 0

    result = _captured_context(repository)
    expected = git(repository, "rev-parse", "HEAD").stdout.strip()

    assert len(expected) == 64
    assert str(result.base_commit) == expected
    assert result.state_fingerprint == CLEAN_FINGERPRINT


@pytest.mark.parametrize("object_format", [None, "sha256"])
def test_context_fingerprint_tracks_unstaged_binary_bytes_and_line_endings(
    tmp_path: Path,
    object_format: str | None,
) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format=object_format,
    )
    assert run_cli(repository, "register").returncode == 0
    clean = _captured_context(repository)
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"changed\x00payload\xff\r\n")

    with_crlf = _captured_context(repository)
    tracked.write_bytes(b"changed\x00payload\xff\n")
    with_lf = _captured_context(repository)

    assert with_crlf.base_commit == clean.base_commit
    assert with_lf.base_commit == clean.base_commit
    assert with_crlf.dirty is True
    assert with_lf.dirty is True
    assert with_crlf.state_fingerprint != clean.state_fingerprint
    assert with_lf.state_fingerprint != with_crlf.state_fingerprint


def test_context_fingerprint_distinguishes_modification_and_deletion(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    clean = _captured_context(repository)
    tracked = repository / "tracked.txt"
    tracked.write_bytes(b"changed\n")
    modified = _captured_context(repository)
    tracked.unlink()
    deleted = _captured_context(repository)

    assert modified.dirty is True
    assert deleted.dirty is True
    assert modified.state_fingerprint != clean.state_fingerprint
    assert deleted.state_fingerprint != clean.state_fingerprint
    assert deleted.state_fingerprint != modified.state_fingerprint


@pytest.mark.skipif(
    os.name == "nt",
    reason="executable mode is not a portable Windows working-tree behavior",
)
def test_context_fingerprint_tracks_an_unstaged_executable_mode(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    git(repository, "config", "core.fileMode", "true")
    clean = _captured_context(repository)
    tracked = repository / "tracked.txt"
    tracked.chmod(tracked.stat().st_mode | 0o111)

    executable = _captured_context(repository)

    assert executable.base_commit == clean.base_commit
    assert executable.dirty is True
    assert executable.state_fingerprint != clean.state_fingerprint


@pytest.mark.parametrize("object_format", [None, "sha256"])
def test_context_fingerprint_tracks_a_staged_binary_addition(
    tmp_path: Path,
    object_format: str | None,
) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format=object_format,
    )
    assert run_cli(repository, "register").returncode == 0
    clean = _captured_context(repository)
    (repository / "app.bin").write_bytes(b"binary\x00payload\xff\r\n")
    git(repository, "add", "app.bin")

    staged = _captured_context(repository)

    assert staged.base_commit == clean.base_commit
    assert staged.dirty is True
    assert staged.state_fingerprint != clean.state_fingerprint


def test_context_combines_staged_unstaged_and_untracked_state(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0

    (repository / "staged.bin").write_bytes(b"staged\x00")
    git(repository, "add", "staged.bin")
    (repository / "tracked.txt").write_bytes(b"unstaged\r\n")
    (repository / "untracked.bin").write_bytes(b"untracked\xff")

    combined = _captured_context(repository)
    assert combined.dirty is True

    git(repository, "reset", "--hard", "HEAD")
    (repository / "staged.bin").unlink(missing_ok=True)
    (repository / "untracked.bin").unlink()
    clean = _captured_context(repository)

    assert combined.state_fingerprint != clean.state_fingerprint
    assert clean.dirty is False
