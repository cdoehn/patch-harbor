from __future__ import annotations

import json
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


def test_context_fails_closed_for_a_dirty_state(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    assert run_cli(repository, "register").returncode == 0
    (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")

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
