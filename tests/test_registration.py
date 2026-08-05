from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import RepositoryId, RepositoryPath
from patchharbor.registration import register_local_repository
from patchharbor.registry import registry_lock, write_registry
from patchharbor.repository import (
    apply_local_registration,
    inspect_local_registration,
    inspect_repository,
)
from patchharbor.user_paths import RegistrationUserPaths


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
    )


def _create_repository(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "--quiet")
    _git(path, "config", "user.name", "PatchHarbor Test")
    _git(path, "config", "user.email", "patchharbor@example.invalid")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "--quiet", "-m", "base")
    return path


def _set_isolated_user_environment(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> None:
    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(root / "appdata"))
        monkeypatch.setenv("LOCALAPPDATA", str(root / "localappdata"))
    else:
        monkeypatch.setenv("HOME", str(root / "home"))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(root / "config"))
        monkeypatch.setenv("XDG_STATE_HOME", str(root / "state"))


def _local_exclude_path(repository: Path) -> Path:
    raw = _git(
        repository,
        "rev-parse",
        "--git-path",
        "info/exclude",
    ).stdout.strip()
    path = Path(raw)
    return (repository / path).resolve() if not path.is_absolute() else path.resolve()


def test_failed_registry_publication_restores_all_local_registration_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _create_repository(tmp_path / "repository")
    _set_isolated_user_environment(monkeypatch, tmp_path / "user")
    exclude_path = _local_exclude_path(repository)
    exclude_before = exclude_path.read_bytes()

    def fail_registry_publication(*_args: object, **_kwargs: object) -> None:
        raise PatchHarborError("injected registry failure", ExitCode.REPOSITORY_ERROR)

    monkeypatch.setattr(
        "patchharbor.registration.write_registry",
        fail_registry_publication,
    )

    with pytest.raises(PatchHarborError) as captured:
        register_local_repository(repository)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert not (repository / ".patchharbor").exists()
    assert exclude_path.read_bytes() == exclude_before
    assert _git(repository, "status", "--porcelain=v1").stdout == ""


def test_repository_id_replacement_preserves_the_previous_file_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_path = _create_repository(tmp_path / "repository")
    repository = inspect_repository(repository_path)
    internal = repository_path / ".patchharbor"
    internal.mkdir()
    original_id = RepositoryId.new()
    id_path = internal / "id"
    id_path.write_text(f"{original_id}\n", encoding="ascii", newline="\n")
    exclude_path = _local_exclude_path(repository_path)
    existing = exclude_path.read_bytes()
    separator = b"" if existing.endswith(b"\n") else b"\n"
    exclude_path.write_bytes(existing + separator + b".patchharbor/\n")
    _, state = inspect_local_registration(repository)

    def fail_replace(_source: object, _target: object) -> None:
        raise PermissionError("injected replace failure")

    monkeypatch.setattr("patchharbor.platform.filesystem.os.replace", fail_replace)

    with pytest.raises(PatchHarborError) as captured:
        apply_local_registration(state, RepositoryId.new())

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert id_path.read_text(encoding="ascii") == f"{original_id}\n"
    assert not tuple(internal.glob(".patchharbor-*.tmp"))


def test_registry_replacement_preserves_the_previous_snapshot_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = tmp_path / "configuration"
    locks = tmp_path / "locks"
    configuration.mkdir()
    locks.mkdir()
    paths = RegistrationUserPaths(configuration, locks)
    old_id = RepositoryId.new()
    old_path = RepositoryPath((tmp_path / "old").resolve())
    previous = {
        "format_version": 1,
        "repositories": {str(old_id): str(old_path)},
    }
    previous_bytes = (
        json.dumps(previous, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    paths.registry_path.write_bytes(previous_bytes)

    def fail_replace(_source: object, _target: object) -> None:
        raise PermissionError("injected replace failure")

    monkeypatch.setattr("patchharbor.platform.filesystem.os.replace", fail_replace)
    new_id = RepositoryId.new()
    entries = {
        old_id: old_path,
        new_id: RepositoryPath((tmp_path / "new").resolve()),
    }

    with pytest.raises(PatchHarborError) as captured:
        write_registry(paths, entries)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert paths.registry_path.read_bytes() == previous_bytes
    assert not tuple(configuration.glob(".patchharbor-*.tmp"))


def test_registry_lock_is_removed_when_acquisition_setup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = tmp_path / "configuration"
    locks = tmp_path / "locks"
    configuration.mkdir()
    locks.mkdir()
    paths = RegistrationUserPaths(configuration, locks)

    def fail_pid_write(_descriptor: int, _content: bytes) -> int:
        raise PermissionError("injected lock write failure")

    monkeypatch.setattr("patchharbor.registry.os.write", fail_pid_write)

    with pytest.raises(PatchHarborError) as captured:
        with registry_lock(paths):
            raise AssertionError("lock body must not run")

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert not paths.registry_lock_path.exists()
