from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID, uuid4

import pytest

from tests.platform_support import create_symlink_or_skip, run_cli
from tests.registration_support import (
    create_repository,
    git,
    isolated_user_environment,
    local_exclude_path,
)


pytestmark = pytest.mark.e2e


def _registry_path(environment: dict[str, str]) -> Path:
    if os.name == "nt":
        return Path(environment["APPDATA"]) / "PatchHarbor" / "registry.json"
    return Path(environment["XDG_CONFIG_HOME"]) / "patchharbor" / "registry.json"


def _registry_lock_path(environment: dict[str, str]) -> Path:
    if os.name == "nt":
        return (
            Path(environment["LOCALAPPDATA"])
            / "PatchHarbor"
            / "locks"
            / "registry.lock"
        )
    return (
        Path(environment["XDG_STATE_HOME"])
        / "patchharbor"
        / "locks"
        / "registry.lock"
    )


@pytest.mark.parametrize("explicit_path", [False, True])
def test_register_creates_identity_registry_and_clean_git_state(
    tmp_path: Path,
    explicit_path: bool,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    invocation_directory = repository if not explicit_path else tmp_path
    arguments = (str(repository),) if explicit_path else ()
    gitignore_path = repository / ".gitignore"
    gitignore_before = gitignore_path.read_bytes() if gitignore_path.exists() else None

    completed = run_cli(
        invocation_directory,
        "register",
        *arguments,
        environment_overrides=environment,
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

    registry = json.loads(_registry_path(environment).read_text(encoding="utf-8"))
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
    environment = isolated_user_environment(tmp_path / "user")

    completed = run_cli(
        tmp_path,
        "register",
        str(link),
        environment_overrides=environment,
    )

    assert completed.returncode == 0
    repo_id = (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()
    registry = json.loads(_registry_path(environment).read_text(encoding="utf-8"))
    assert registry["repositories"][repo_id] == str(repository.resolve())


def test_register_rejects_a_repository_without_a_commit(tmp_path: Path) -> None:
    repository = create_repository(
        tmp_path / "repository",
        with_commit=False,
    )
    environment = isolated_user_environment(tmp_path / "user")

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert not (repository / ".patchharbor").exists()
    assert not _registry_path(environment).exists()


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
    environment = isolated_user_environment(tmp_path / "user")

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert not (repository / ".patchharbor").exists()
    assert not _registry_path(environment).exists()


def test_register_respects_the_global_registry_lock(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    lock_path = _registry_lock_path(environment)
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("occupied\n", encoding="ascii")

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert not (repository / ".patchharbor").exists()
    assert not _registry_path(environment).exists()


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
    environment = isolated_user_environment(tmp_path / "user")

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert not _registry_path(environment).exists()
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
    environment = isolated_user_environment(tmp_path / "user")

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert not _registry_path(environment).exists()
    assert not (target / "id").exists()


def _registered_id(repository: Path) -> str:
    return (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ).strip()


def test_registry_list_json_reports_sorted_real_repository_statuses(
    tmp_path: Path,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")
    ok_repository = create_repository(tmp_path / "ok-repository")
    missing_repository = create_repository(tmp_path / "missing-repository")
    conflict_repository = create_repository(tmp_path / "conflict-repository")

    for repository in (
        conflict_repository,
        ok_repository,
        missing_repository,
    ):
        completed = run_cli(
            tmp_path,
            "register",
            str(repository),
            environment_overrides=environment,
        )
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

    completed = run_cli(
        tmp_path,
        "registry",
        "list",
        "--json",
        environment_overrides=environment,
    )

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
    environment = isolated_user_environment(tmp_path / "user")
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    id_path = repository / ".patchharbor" / "id"
    repo_id = _registered_id(repository)
    id_bytes = id_path.read_bytes()

    completed = run_cli(
        tmp_path,
        "unregister",
        repo_id,
        environment_overrides=environment,
    )

    assert completed.returncode == 0
    registry = json.loads(_registry_path(environment).read_text(encoding="utf-8"))
    assert registry == {"format_version": 1, "repositories": {}}
    assert id_path.read_bytes() == id_bytes

    listed = run_cli(
        tmp_path,
        "registry",
        "list",
        "--json",
        environment_overrides=environment,
    )
    assert listed.returncode == 0
    assert json.loads(listed.stdout)["result"] == {"repositories": []}


def test_unregister_by_path_can_remove_a_missing_repository_mapping(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    repository_path = repository.resolve()
    shutil.rmtree(repository)

    completed = run_cli(
        tmp_path,
        "unregister",
        str(repository_path),
        environment_overrides=environment,
    )

    assert completed.returncode == 0
    registry = json.loads(_registry_path(environment).read_text(encoding="utf-8"))
    assert registry == {"format_version": 1, "repositories": {}}


def test_unregister_unknown_id_preserves_registry_and_local_identity(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    registry_path = _registry_path(environment)
    registry_before = registry_path.read_bytes()
    id_path = repository / ".patchharbor" / "id"
    id_before = id_path.read_bytes()

    completed = run_cli(
        tmp_path,
        "unregister",
        str(uuid4()),
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert registry_path.read_bytes() == registry_before
    assert id_path.read_bytes() == id_before


def test_unregister_selector_is_exact_and_uuid_shaped_paths_are_explicit(
    tmp_path: Path,
) -> None:
    directory_name = str(uuid4())
    repository = create_repository(tmp_path / directory_name)
    environment = isolated_user_environment(tmp_path / "user")
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    registry_path = _registry_path(environment)
    registry_before = registry_path.read_bytes()
    registered_id = _registered_id(repository)

    id_prefix = run_cli(
        tmp_path,
        "unregister",
        registered_id[:8],
        environment_overrides=environment,
    )
    bare_uuid_path = run_cli(
        tmp_path,
        "unregister",
        directory_name,
        environment_overrides=environment,
    )

    assert id_prefix.returncode == 8
    assert bare_uuid_path.returncode == 8
    assert registry_path.read_bytes() == registry_before

    explicit_path = f".{os.sep}{directory_name}"
    completed = run_cli(
        tmp_path,
        "unregister",
        explicit_path,
        environment_overrides=environment,
    )

    assert completed.returncode == 0
    assert json.loads(registry_path.read_text(encoding="utf-8")) == {
        "format_version": 1,
        "repositories": {},
    }


def test_registry_list_reads_only_while_holding_the_global_lock(
    tmp_path: Path,
) -> None:
    environment = isolated_user_environment(tmp_path / "user")
    lock_path = _registry_lock_path(environment)
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("occupied\n", encoding="ascii")

    completed = run_cli(
        tmp_path,
        "registry",
        "list",
        "--json",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
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
    assert document["command"] == "registry.list"
    assert document["success"] is False
    assert document["result"] is None
    assert document["process_exit_code"] == 8
    assert set(document["error"]) == {
        "kind",
        "message",
        "patchharbor_error_code",
        "emergency_diagnostics_path",
    }
    assert document["error"]["kind"] == "registry_error"
    assert isinstance(document["error"]["message"], str)
    assert document["error"]["patchharbor_error_code"] == 8
    assert document["error"]["emergency_diagnostics_path"] is None


def test_unregister_respects_the_global_registry_lock(tmp_path: Path) -> None:
    repository = create_repository(tmp_path / "repository")
    environment = isolated_user_environment(tmp_path / "user")
    registered = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )
    assert registered.returncode == 0
    registry_path = _registry_path(environment)
    registry_before = registry_path.read_bytes()
    id_path = repository / ".patchharbor" / "id"
    id_before = id_path.read_bytes()
    lock_path = _registry_lock_path(environment)
    lock_path.write_text("occupied\n", encoding="ascii")

    completed = run_cli(
        tmp_path,
        "unregister",
        _registered_id(repository),
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert registry_path.read_bytes() == registry_before
    assert id_path.read_bytes() == id_before
