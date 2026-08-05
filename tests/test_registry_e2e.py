from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from uuid import UUID

import pytest

from tests.platform_support import create_symlink_or_skip, run_cli


pytestmark = pytest.mark.e2e


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
    )


def _create_repository(path: Path, *, with_commit: bool = True) -> Path:
    path.mkdir()
    _git(path, "init", "--quiet")
    _git(path, "config", "user.name", "PatchHarbor Test")
    _git(path, "config", "user.email", "patchharbor@example.invalid")
    if with_commit:
        (path / "tracked.txt").write_text("base\n", encoding="utf-8")
        _git(path, "add", "tracked.txt")
        _git(path, "commit", "--quiet", "-m", "base")
    return path


def _isolated_user_environment(root: Path) -> dict[str, str]:
    if os.name == "nt":
        return {
            "APPDATA": str(root / "appdata"),
            "LOCALAPPDATA": str(root / "localappdata"),
        }
    return {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_STATE_HOME": str(root / "state"),
    }


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


def _local_exclude_path(repository: Path) -> Path:
    raw_path = _git(
        repository,
        "rev-parse",
        "--git-path",
        "info/exclude",
    ).stdout.strip()
    path = Path(raw_path)
    if not path.is_absolute():
        path = repository / path
    return path.resolve()


@pytest.mark.parametrize("explicit_path", [False, True])
def test_register_creates_identity_registry_and_clean_git_state(
    tmp_path: Path,
    explicit_path: bool,
) -> None:
    repository = _create_repository(tmp_path / "repository")
    environment = _isolated_user_environment(tmp_path / "user")
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

    exclude_lines = _local_exclude_path(repository).read_bytes().splitlines()
    assert b".patchharbor/" in exclude_lines
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", ".patchharbor/id"],
        cwd=repository,
        check=False,
    )
    assert ignored.returncode == 0
    assert _git(
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
    repository = _create_repository(tmp_path / "repository")
    link = tmp_path / "repository-link"
    create_symlink_or_skip(link, repository, target_is_directory=True)
    environment = _isolated_user_environment(tmp_path / "user")

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
    repository = _create_repository(
        tmp_path / "repository",
        with_commit=False,
    )
    environment = _isolated_user_environment(tmp_path / "user")

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
    repository = _create_repository(tmp_path / "repository")
    reserved_file = repository / "nested" / ".PatchHarbor" / "blocked.txt"
    reserved_file.parent.mkdir(parents=True)
    reserved_file.write_text("blocked\n", encoding="utf-8")
    _git(repository, "add", reserved_file.relative_to(repository).as_posix())
    if location == "base":
        _git(repository, "commit", "--quiet", "-m", "reserved path")
    environment = _isolated_user_environment(tmp_path / "user")

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert not (repository / ".patchharbor").exists()
    assert not _registry_path(environment).exists()


def test_register_respects_the_global_registry_lock(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path / "repository")
    environment = _isolated_user_environment(tmp_path / "user")
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
    repository = _create_repository(tmp_path / "repository")
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
    environment = _isolated_user_environment(tmp_path / "user")

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
    repository = _create_repository(tmp_path / "repository")
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
    environment = _isolated_user_environment(tmp_path / "user")

    completed = run_cli(
        repository,
        "register",
        environment_overrides=environment,
    )

    assert completed.returncode == 8
    assert not _registry_path(environment).exists()
    assert not (target / "id").exists()
