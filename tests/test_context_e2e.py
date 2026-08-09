from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

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


def test_context_still_fails_closed_for_an_untracked_state(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    (repository / "untracked.txt").write_text("new\n", encoding="utf-8")

    completed = run_cli(repository, "context", "--json")

    assert completed.returncode == 8
    document = json.loads(completed.stdout)
    assert document["success"] is False
    assert document["result"] is None
    assert document["process_exit_code"] == 8


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


def _context_result(repository: Path) -> dict[str, object]:
    completed = run_cli(repository, "context", "--json")
    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    result = document["result"]
    assert isinstance(result, dict)
    return result


def test_clean_fingerprint_is_independent_of_the_base_commit(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    before = _context_result(repository)

    (repository / "tracked.txt").write_text("next base\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "commit", "--quiet", "-m", "next base")
    after = _context_result(repository)

    assert before["base_commit"] != after["base_commit"]
    assert before["state_fingerprint"] == after["state_fingerprint"]
    assert before["dirty"] is False
    assert after["dirty"] is False


def test_context_preserves_a_full_sha256_base_commit(tmp_path: Path) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format="sha256",
    )
    assert run_cli(repository, "register").returncode == 0

    result = _context_result(repository)
    expected = git(repository, "rev-parse", "HEAD").stdout.strip()

    assert len(expected) == 64
    assert result["base_commit"] == expected
    assert result["state_fingerprint"] == CLEAN_FINGERPRINT


def _framed_field(name: bytes, payload: bytes) -> bytes:
    return name + b"\0" + len(payload).to_bytes(8, "big") + payload


def _expected_staged_addition_fingerprint(
    path: bytes,
    object_name: bytes,
) -> str:
    stream = b"".join(
        (
            b"PATCHHARBOR_STATE_FINGERPRINT\0",
            b"1\0",
            _framed_field(b"staged-count", (1).to_bytes(8, "big")),
            _framed_field(b"staged-path", path),
            _framed_field(b"staged-head-mode", b""),
            _framed_field(b"staged-head-object", b""),
            _framed_field(b"staged-index-mode", b"100644"),
            _framed_field(b"staged-index-object", object_name),
            _framed_field(b"unstaged-count", (0).to_bytes(8, "big")),
            _framed_field(b"untracked-count", (0).to_bytes(8, "big")),
        )
    )
    return hashlib.sha256(stream).hexdigest()[:16]


def _expected_unstaged_fingerprint(
    *,
    path: bytes,
    status: bytes,
    index_mode: bytes,
    index_object: bytes,
    worktree_kind: bytes,
    worktree_mode: bytes,
    worktree_content: bytes,
) -> str:
    stream = b"".join(
        (
            b"PATCHHARBOR_STATE_FINGERPRINT\0",
            b"1\0",
            _framed_field(b"staged-count", (0).to_bytes(8, "big")),
            _framed_field(b"unstaged-count", (1).to_bytes(8, "big")),
            _framed_field(b"unstaged-path", path),
            _framed_field(b"unstaged-status", status),
            _framed_field(b"unstaged-index-mode", index_mode),
            _framed_field(b"unstaged-index-object", index_object),
            _framed_field(b"unstaged-worktree-kind", worktree_kind),
            _framed_field(b"unstaged-worktree-mode", worktree_mode),
            _framed_field(b"unstaged-worktree-content", worktree_content),
            _framed_field(b"untracked-count", (0).to_bytes(8, "big")),
        )
    )
    return hashlib.sha256(stream).hexdigest()[:16]


@pytest.mark.parametrize("object_format", [None, "sha256"])
def test_context_reports_an_unstaged_binary_change(
    tmp_path: Path,
    object_format: str | None,
) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format=object_format,
    )
    assert run_cli(repository, "register").returncode == 0
    base_commit = git(repository, "rev-parse", "HEAD").stdout.strip()
    index_object = git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")
    content = b"changed\x00payload\xff\r\n"
    (repository / "tracked.txt").write_bytes(content)

    result = _context_result(repository)

    assert result["base_commit"] == base_commit
    assert result["dirty"] is True
    assert result["state_fingerprint"] == _expected_unstaged_fingerprint(
        path=b"tracked.txt",
        status=b"M",
        index_mode=b"100644",
        index_object=index_object,
        worktree_kind=b"regular",
        worktree_mode=b"100644",
        worktree_content=content,
    )


def test_context_reports_an_unstaged_deletion(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    index_object = git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")
    (repository / "tracked.txt").unlink()

    result = _context_result(repository)

    assert result["dirty"] is True
    assert result["state_fingerprint"] == _expected_unstaged_fingerprint(
        path=b"tracked.txt",
        status=b"D",
        index_mode=b"100644",
        index_object=index_object,
        worktree_kind=b"missing",
        worktree_mode=b"",
        worktree_content=b"",
    )


@pytest.mark.skipif(
    os.name == "nt",
    reason="executable mode is not a portable Windows working-tree behavior",
)
def test_context_reports_an_unstaged_executable_mode(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    git(repository, "config", "core.fileMode", "true")
    tracked = repository / "tracked.txt"
    index_object = git(
        repository,
        "rev-parse",
        ":tracked.txt",
    ).stdout.strip().encode("ascii")
    tracked.chmod(tracked.stat().st_mode | 0o111)

    result = _context_result(repository)

    assert result["dirty"] is True
    assert result["state_fingerprint"] == _expected_unstaged_fingerprint(
        path=b"tracked.txt",
        status=b"M",
        index_mode=b"100644",
        index_object=index_object,
        worktree_kind=b"regular",
        worktree_mode=b"100755",
        worktree_content=tracked.read_bytes(),
    )


@pytest.mark.parametrize("object_format", [None, "sha256"])
def test_context_reports_a_staged_binary_addition(
    tmp_path: Path,
    object_format: str | None,
) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format=object_format,
    )
    assert run_cli(repository, "register").returncode == 0
    base_commit = git(repository, "rev-parse", "HEAD").stdout.strip()

    (repository / "app.bin").write_bytes(b"binary\x00payload\xff\r\n")
    git(repository, "add", "app.bin")
    index_object = git(repository, "rev-parse", ":app.bin").stdout.strip()

    result = _context_result(repository)

    assert result["base_commit"] == base_commit
    assert result["dirty"] is True
    assert result["state_fingerprint"] == _expected_staged_addition_fingerprint(
        b"app.bin",
        index_object.encode("ascii"),
    )
