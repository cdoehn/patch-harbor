from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.models import RepositoryId, RepositoryPath
from patchharbor.registration import (
    list_registered_repositories,
    register_local_repository,
)
from patchharbor.registry import (
    registry_lock,
    registry_snapshot,
    write_registry,
)
from patchharbor.repository import (
    apply_local_registration,
    inspect_local_registration,
    inspect_repository,
)
from patchharbor.user_paths import (
    RegistrationUserPaths,
    registration_user_paths,
)
from tests.registration_support import (
    create_repository,
    git,
    local_exclude_path,
    set_isolated_user_environment,
)


def test_failed_registry_publication_restores_all_local_registration_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    exclude_path = local_exclude_path(repository)
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
    assert git(repository, "status", "--porcelain=v1").stdout == ""


def test_repository_id_replacement_preserves_the_previous_file_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_path = create_repository(tmp_path / "repository")
    repository = inspect_repository(repository_path)
    internal = repository_path / ".patchharbor"
    internal.mkdir()
    original_id = RepositoryId.new()
    id_path = internal / "id"
    id_path.write_text(f"{original_id}\n", encoding="ascii", newline="\n")
    exclude_path = local_exclude_path(repository_path)
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
        write_registry(paths, registry_snapshot(entries))

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


def test_registry_status_resolution_runs_after_snapshot_lock_is_released(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    register_local_repository(repository)
    user_paths = registration_user_paths()
    observed_lock_reacquisition = False

    from patchharbor.repository import registered_repository_status as real_status

    def resolve_status(*args: object, **kwargs: object):
        nonlocal observed_lock_reacquisition
        with registry_lock(user_paths):
            observed_lock_reacquisition = True
        return real_status(*args, **kwargs)

    monkeypatch.setattr(
        "patchharbor.registration.registered_repository_status",
        resolve_status,
    )

    result = list_registered_repositories()

    assert observed_lock_reacquisition is True
    assert len(result.repositories) == 1
    assert result.repositories[0].repository_path.value == repository.resolve()


def test_registration_user_path_failures_use_the_registry_error_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    else:
        monkeypatch.delenv("HOME", raising=False)

    with pytest.raises(PatchHarborError) as captured:
        registration_user_paths()

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REGISTRY_ERROR
