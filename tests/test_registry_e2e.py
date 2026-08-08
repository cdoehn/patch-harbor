from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID, uuid4

import pytest

from tests.platform_support import (
    create_symlink_or_skip,
    project_environment,
    run_cli,
)
from tests.registration_support import (
    create_repository,
    git,
    isolated_user_environment,
    local_exclude_path,
    release_registry_lock_holder,
    release_repository_lock_holder,
    start_registry_lock_holder,
    start_repository_lock_holder,
    stop_registry_lock_holder,
    stop_repository_lock_holder,
)


pytestmark = pytest.mark.e2e


def _registry_path() -> Path:
    if os.name == "nt":
        return Path(os.environ["APPDATA"]) / "PatchHarbor" / "registry.json"
    return Path(os.environ["XDG_CONFIG_HOME"]) / "patchharbor" / "registry.json"


def _registry_lock_path() -> Path:
    if os.name == "nt":
        return (
            Path(os.environ["LOCALAPPDATA"])
            / "PatchHarbor"
            / "locks"
            / "registry.lock"
        )
    return (
        Path(os.environ["XDG_STATE_HOME"])
        / "patchharbor"
        / "locks"
        / "registry.lock"
    )


@pytest.fixture(autouse=True)
def isolate_registry_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolate registry state for every E2E behavior test."""
    for name, value in isolated_user_environment(tmp_path / "user").items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize("explicit_path", [False, True])
def test_register_creates_identity_registry_and_clean_git_state(
    tmp_path: Path,
    explicit_path: bool,
) -> None:
    repository = create_repository(tmp_path / "repository")
    invocation_directory = repository if not explicit_path else tmp_path
    arguments = (str(repository),) if explicit_path else ()
    gitignore_path = repository / ".gitignore"
    gitignore_before = gitignore_path.read_bytes() if gitignore_path.exists() else None

    completed = run_cli(
        invocation_directory,
        "register",
        *arguments,
    )

    assert completed.returncode == 0
    id_path = repository / ".patchharbor" / "id"
    assert id_path.is_file()
    assert not id_path.is_symlink()
    id_content = id_path.read_text(encoding="ascii")
    assert id_content.endswith("\n")
    repo_id = id_content[:-1]
    parsed_id = UUID(repo_id)
    assert parsed_id.version == 4
    assert str(parsed_id) == repo_id

    registry = json.loads(_registry_path().read_text(encoding="utf-8"))
    assert registry["format_version"] == 1
    assert registry["repositories"][repo_id] == str(repository.resolve())

    exclude_lines = local_exclude_path(repository).read_bytes().splitlines()
    assert b".patchharbor/" in exclude_lines
    git(repository, "check-ignore", "--quiet", ".patchharbor/id")
    assert git(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).stdout == ""
    if gitignore_before is None:
        assert not gitignore_path.exists()
    else:
        assert gitignore_path.read_bytes() == gitignore_before


def test_register_physically_canonicalizes_an_explicit_repository_path(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    link = tmp_path / "repository-link"
    create_symlink_or_skip(link, repository, target_is_directory=True)

    completed = run_cli(tmp_path, "register", str(link))

    assert completed.returncode == 0
    repo_id = (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()
    registry = json.loads(_registry_path().read_text(encoding="utf-8"))
    assert registry["repositories"][repo_id] == str(repository.resolve())


def test_register_rejects_a_repository_without_a_commit(tmp_path: Path) -> None:
    repository = create_repository(
        tmp_path / "repository",
        with_commit=False,
    )

    completed = run_cli(repository, "register")

    assert completed.returncode == 8
    assert not (repository / ".patchharbor").exists()
    assert not _registry_path().exists()


@pytest.mark.parametrize("location", ["base", "index"])
def test_register_rejects_reserved_tracked_path_segments(
    tmp_path: Path,
    location: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    reserved_file = repository / "nested" / ".PatchHarbor" / "blocked.txt"
    reserved_file.parent.mkdir(parents=True)
    reserved_file.write_text("blocked\n", encoding="utf-8")
    git(repository, "add", reserved_file.relative_to(repository).as_posix())
    if location == "base":
        git(repository, "commit", "--quiet", "-m", "reserved path")

    completed = run_cli(repository, "register")

    assert completed.returncode == 8
    assert not (repository / ".patchharbor").exists()
    assert not _registry_path().exists()


def test_register_respects_the_global_registry_lock(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    holder = start_registry_lock_holder(environment=project_environment())
    try:
        completed = run_cli(repository, "register")

        assert completed.returncode == 8
        assert not (repository / ".patchharbor").exists()
        assert not _registry_path().exists()
    finally:
        assert release_registry_lock_holder(holder) == 0
        stop_registry_lock_holder(holder)


def test_leftover_registry_lock_file_does_not_block_registration(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    lock_path = _registry_lock_path()
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("left over by a terminated process\n", encoding="ascii")

    completed = run_cli(repository, "register")

    assert completed.returncode == 0
    assert (repository / ".patchharbor" / "id").is_file()
    assert _registry_path().is_file()


@pytest.mark.parametrize("internal_kind", ["regular-file", "symlink"])
def test_register_rejects_a_non_directory_internal_path(
    tmp_path: Path,
    internal_kind: str,
) -> None:
    repository = create_repository(tmp_path / "repository")
    internal = repository / ".patchharbor"
    target = tmp_path / "external-target"
    if internal_kind == "regular-file":
        internal.write_bytes(b"not a directory\n")
    else:
        target.mkdir()
        create_symlink_or_skip(
            internal,
            target,
            target_is_directory=True,
        )

    completed = run_cli(repository, "register")

    assert completed.returncode == 8
    assert not _registry_path().exists()
    if internal_kind == "regular-file":
        assert internal.read_bytes() == b"not a directory\n"
    else:
        assert internal.is_symlink()
        assert not (target / "id").exists()


@pytest.mark.skipif(os.name != "nt", reason="requires Windows junction support")
def test_register_rejects_a_junction_as_internal_directory(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    target = tmp_path / "junction-target"
    target.mkdir()
    internal = repository / ".patchharbor"
    completed_link = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/s",
            "/c",
            f'mklink /J "{internal}" "{target}"',
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed_link.returncode != 0:
        pytest.skip("requires Windows junction creation support")

    completed = run_cli(repository, "register")

    assert completed.returncode == 8
    assert not _registry_path().exists()
    assert not (target / "id").exists()


def _registered_id(repository: Path) -> str:
    return (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()


def _registry_repositories() -> dict[str, str]:
    document = json.loads(_registry_path().read_text(encoding="utf-8"))
    repositories = document["repositories"]
    assert isinstance(repositories, dict)
    return repositories


def _create_repository_with_copied_identity(
    source: Path,
    destination: Path,
) -> Path:
    copied = create_repository(destination)
    copied_identity = copied / ".patchharbor" / "id"
    copied_identity.parent.mkdir()
    copied_identity.write_bytes(
        (source / ".patchharbor" / "id").read_bytes()
    )
    return copied


def test_registering_the_same_instance_again_is_idempotent(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    first = run_cli(repository, "register")
    assert first.returncode == 0
    repo_id = _registered_id(repository)
    registry_before = _registry_path().read_bytes()
    exclude_before = local_exclude_path(repository).read_bytes()

    second = run_cli(repository, "register")

    assert second.returncode == 0
    assert _registered_id(repository) == repo_id
    assert _registry_path().read_bytes() == registry_before
    assert local_exclude_path(repository).read_bytes() == exclude_before


def test_register_moves_an_identity_when_the_old_path_is_missing(
    tmp_path: Path,
) -> None:
    original = create_repository(tmp_path / "original")
    registered = run_cli(original, "register")
    assert registered.returncode == 0
    repo_id = _registered_id(original)
    old_path = original.resolve()
    moved = tmp_path / "moved"
    original.rename(moved)

    completed = run_cli(tmp_path, "register", str(moved))

    assert completed.returncode == 0
    assert not old_path.exists()
    assert _registered_id(moved) == repo_id
    assert _registry_repositories() == {
        repo_id: str(moved.resolve()),
    }


def test_register_rejects_a_copied_identity_while_both_paths_exist(
    tmp_path: Path,
) -> None:
    original = create_repository(tmp_path / "original")
    registered = run_cli(original, "register")
    assert registered.returncode == 0
    repo_id = _registered_id(original)
    registry_before = _registry_path().read_bytes()
    copied = _create_repository_with_copied_identity(
        original,
        tmp_path / "copied",
    )

    completed = run_cli(tmp_path, "register", str(copied))

    assert completed.returncode == 8
    assert _registry_path().read_bytes() == registry_before
    assert _registered_id(original) == repo_id
    assert _registered_id(copied) == repo_id


def test_register_replaces_a_lost_identity_and_removes_the_old_path_mapping(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    old_id = _registered_id(repository)
    (repository / ".patchharbor" / "id").unlink()

    completed = run_cli(repository, "register")

    assert completed.returncode == 0
    new_id = _registered_id(repository)
    assert new_id != old_id
    assert _registry_repositories() == {
        new_id: str(repository.resolve()),
    }


def test_register_reuses_a_local_identity_after_unregister(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    repo_id = _registered_id(repository)

    unregistered = run_cli(tmp_path, "unregister", repo_id)
    assert unregistered.returncode == 0

    completed = run_cli(repository, "register")

    assert completed.returncode == 0
    assert _registered_id(repository) == repo_id
    assert _registry_repositories() == {
        repo_id: str(repository.resolve()),
    }


def test_register_new_id_separates_a_copied_instance(
    tmp_path: Path,
) -> None:
    original = create_repository(tmp_path / "original")
    registered = run_cli(original, "register")
    assert registered.returncode == 0
    original_id = _registered_id(original)
    copied = _create_repository_with_copied_identity(
        original,
        tmp_path / "copied",
    )

    completed = run_cli(
        tmp_path,
        "register",
        "--new-id",
        str(copied),
    )

    assert completed.returncode == 0
    copied_id = _registered_id(copied)
    assert copied_id != original_id
    assert _registered_id(original) == original_id
    assert _registry_repositories() == {
        original_id: str(original.resolve()),
        copied_id: str(copied.resolve()),
    }


def test_registry_list_json_reports_sorted_real_repository_statuses(
    tmp_path: Path,
) -> None:
    ok_repository = create_repository(tmp_path / "ok-repository")
    missing_repository = create_repository(tmp_path / "missing-repository")
    conflict_repository = create_repository(tmp_path / "conflict-repository")

    for repository in (
        conflict_repository,
        ok_repository,
        missing_repository,
    ):
        completed = run_cli(tmp_path, "register", str(repository))
        assert completed.returncode == 0

    repository_ids = {
        ok_repository: _registered_id(ok_repository),
        missing_repository: _registered_id(missing_repository),
        conflict_repository: _registered_id(conflict_repository),
    }
    missing_path = str(missing_repository.resolve())
    shutil.rmtree(missing_repository)
    (conflict_repository / ".patchharbor" / "id").write_text(
        f"{uuid4()}\n",
        encoding="ascii",
        newline="\n",
    )

    completed = run_cli(tmp_path, "registry", "list", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    expected_entries = sorted(
        [
            {
                "repo_id": repository_ids[ok_repository],
                "repository_path": str(ok_repository.resolve()),
                "status": "ok",
            },
            {
                "repo_id": repository_ids[missing_repository],
                "repository_path": missing_path,
                "status": "missing",
            },
            {
                "repo_id": repository_ids[conflict_repository],
                "repository_path": str(conflict_repository.resolve()),
                "status": "conflict",
            },
        ],
        key=lambda entry: entry["repo_id"].encode("ascii"),
    )
    assert document == {
        "output_version": 1,
        "command": "registry.list",
        "success": True,
        "result": {"repositories": expected_entries},
        "error": None,
        "process_exit_code": 0,
    }


def test_unregister_by_id_removes_only_the_central_mapping(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    id_path = repository / ".patchharbor" / "id"
    repo_id = _registered_id(repository)
    id_bytes = id_path.read_bytes()

    completed = run_cli(tmp_path, "unregister", repo_id)

    assert completed.returncode == 0
    registry = json.loads(_registry_path().read_text(encoding="utf-8"))
    assert registry == {"format_version": 1, "repositories": {}}
    assert id_path.read_bytes() == id_bytes

    listed = run_cli(tmp_path, "registry", "list", "--json")
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["result"] == {"repositories": []}


def test_unregister_by_path_can_remove_a_missing_repository_mapping(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    repository_path = repository.resolve()
    shutil.rmtree(repository)

    completed = run_cli(tmp_path, "unregister", str(repository_path))

    assert completed.returncode == 0
    registry = json.loads(_registry_path().read_text(encoding="utf-8"))
    assert registry == {"format_version": 1, "repositories": {}}


def test_unregister_unknown_id_preserves_registry_and_local_identity(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    registry_path = _registry_path()
    registry_before = registry_path.read_bytes()
    id_path = repository / ".patchharbor" / "id"
    id_before = id_path.read_bytes()

    completed = run_cli(tmp_path, "unregister", str(uuid4()))

    assert completed.returncode == 8
    assert registry_path.read_bytes() == registry_before
    assert id_path.read_bytes() == id_before


def test_unregister_selector_is_exact_and_uuid_shaped_paths_are_explicit(
    tmp_path: Path,
) -> None:
    directory_name = str(uuid4())
    repository = create_repository(tmp_path / directory_name)
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    registry_path = _registry_path()
    registry_before = registry_path.read_bytes()
    registered_id = _registered_id(repository)

    id_prefix = run_cli(tmp_path, "unregister", registered_id[:8])
    bare_uuid_path = run_cli(tmp_path, "unregister", directory_name)

    assert id_prefix.returncode == 8
    assert bare_uuid_path.returncode == 8
    assert registry_path.read_bytes() == registry_before

    explicit_path = f".{os.sep}{directory_name}"
    completed = run_cli(tmp_path, "unregister", explicit_path)

    assert completed.returncode == 0
    assert json.loads(registry_path.read_text(encoding="utf-8")) == {
        "format_version": 1,
        "repositories": {},
    }


def test_registry_list_reads_only_while_holding_the_global_lock(
    tmp_path: Path,
) -> None:
    holder = start_registry_lock_holder(environment=project_environment())
    try:
        completed = run_cli(tmp_path, "registry", "list", "--json")

        assert completed.returncode == 8
        document = json.loads(completed.stdout)
        error = document["error"]
        assert isinstance(error, dict)
        assert isinstance(error.get("message"), str)
        assert document == {
            "output_version": 1,
            "command": "registry.list",
            "success": False,
            "result": None,
            "error": {
                "kind": "registry_error",
                "message": error["message"],
                "patchharbor_error_code": 8,
                "emergency_diagnostics_path": None,
            },
            "process_exit_code": 8,
        }
    finally:
        assert release_registry_lock_holder(holder) == 0
        stop_registry_lock_holder(holder)


def test_unregister_respects_the_global_registry_lock(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    registry_path = _registry_path()
    registry_before = registry_path.read_bytes()
    id_path = repository / ".patchharbor" / "id"
    id_before = id_path.read_bytes()
    holder = start_registry_lock_holder(environment=project_environment())
    try:
        completed = run_cli(tmp_path, "unregister", _registered_id(repository))

        assert completed.returncode == 8
        assert registry_path.read_bytes() == registry_before
        assert id_path.read_bytes() == id_before
    finally:
        assert release_registry_lock_holder(holder) == 0
        stop_registry_lock_holder(holder)



def test_register_new_id_rejects_a_busy_repository_without_mutation(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    repo_id = _registered_id(repository)
    registry_before = _registry_path().read_bytes()
    id_before = (repository / ".patchharbor" / "id").read_bytes()
    environment = project_environment()
    holder = start_repository_lock_holder(
        repo_id,
        environment=environment,
    )
    try:
        completed = run_cli(repository, "register", "--new-id")

        assert completed.returncode == 12
        assert _registry_path().read_bytes() == registry_before
        assert (repository / ".patchharbor" / "id").read_bytes() == id_before

        assert release_repository_lock_holder(holder) == 0
        retry = run_cli(repository, "register", "--new-id")
        assert retry.returncode == 0
        assert _registered_id(repository) != repo_id
    finally:
        stop_repository_lock_holder(holder)


def test_unregister_rejects_a_busy_repository_without_mutation(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    registered = run_cli(repository, "register")
    assert registered.returncode == 0
    repo_id = _registered_id(repository)
    registry_before = _registry_path().read_bytes()
    id_path = repository / ".patchharbor" / "id"
    id_before = id_path.read_bytes()
    holder = start_repository_lock_holder(
        repo_id,
        environment=project_environment(),
    )
    try:
        completed = run_cli(tmp_path, "unregister", repo_id)

        assert completed.returncode == 12
        assert _registry_path().read_bytes() == registry_before
        assert id_path.read_bytes() == id_before

        assert release_repository_lock_holder(holder) == 0
        retry = run_cli(tmp_path, "unregister", repo_id)
        assert retry.returncode == 0
        assert _registry_repositories() == {}
    finally:
        stop_repository_lock_holder(holder)
