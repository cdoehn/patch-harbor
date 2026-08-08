from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Iterator

import pytest

from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.models import RepositoryId, RepositoryPath
from patchharbor.registration import (
    list_registered_repositories,
    register_local_repository,
    unregister_local_repository,
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


def test_registry_lock_is_reusable_after_body_failure(tmp_path: Path) -> None:
    configuration = tmp_path / "configuration"
    locks = tmp_path / "locks"
    configuration.mkdir()
    locks.mkdir()
    paths = RegistrationUserPaths(configuration, locks)

    with pytest.raises(RuntimeError, match="injected body failure"):
        with registry_lock(paths):
            raise RuntimeError("injected body failure")

    with registry_lock(paths):
        assert paths.registry_lock_path.is_file()


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


def test_identity_and_registry_publication_share_the_global_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    observed: list[str] = []

    from patchharbor.repository import (
        apply_local_registration as real_apply_local_registration,
    )
    from patchharbor.registry import write_registry as real_write_registry

    def assert_registry_is_locked() -> None:
        with pytest.raises(PatchHarborError) as captured:
            with registry_lock(paths):
                raise AssertionError("nested registry lock must not be acquired")
        assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR

    def apply_while_locked(*args: object, **kwargs: object) -> None:
        assert_registry_is_locked()
        observed.append("local")
        real_apply_local_registration(*args, **kwargs)

    def write_while_locked(*args: object, **kwargs: object) -> None:
        assert_registry_is_locked()
        observed.append("registry")
        real_write_registry(*args, **kwargs)

    monkeypatch.setattr(
        "patchharbor.registration.apply_local_registration",
        apply_while_locked,
    )
    monkeypatch.setattr(
        "patchharbor.registration.write_registry",
        write_while_locked,
    )

    register_local_repository(repository)

    assert observed == ["local", "registry"]
    with registry_lock(paths):
        assert paths.registry_lock_path.is_file()


def test_new_id_revalidates_local_identity_after_repository_lock_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    original_id, _ = register_local_repository(repository)
    paths = registration_user_paths()
    registry_before = paths.registry_path.read_bytes()
    id_path = repository / ".patchharbor" / "id"
    externally_changed_id = RepositoryId.new()

    @contextmanager
    def mutate_before_yield(*_args: object, **_kwargs: object) -> Iterator[None]:
        id_path.write_text(
            f"{externally_changed_id}\n",
            encoding="ascii",
            newline="\n",
        )
        yield

    monkeypatch.setattr(
        "patchharbor.registration.repository_lock",
        mutate_before_yield,
    )

    with pytest.raises(PatchHarborError) as captured:
        register_local_repository(repository, new_id=True)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR
    assert id_path.read_text(encoding="ascii") == f"{externally_changed_id}\n"
    assert paths.registry_path.read_bytes() == registry_before
    assert str(original_id).encode("ascii") in registry_before


def test_unregister_revalidates_registry_mapping_after_repository_lock_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    replacement = create_repository(tmp_path / "replacement")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repo_id, _ = register_local_repository(repository)
    paths = registration_user_paths()
    replacement_path = RepositoryPath(replacement.resolve())
    externally_changed_snapshot = registry_snapshot(
        {repo_id: replacement_path}
    )

    @contextmanager
    def mutate_before_yield(*_args: object, **_kwargs: object) -> Iterator[None]:
        write_registry(paths, externally_changed_snapshot)
        yield

    monkeypatch.setattr(
        "patchharbor.registration.repository_lock",
        mutate_before_yield,
    )

    with pytest.raises(PatchHarborError) as captured:
        unregister_local_repository(str(repo_id), cwd=tmp_path)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR
    persisted = json.loads(paths.registry_path.read_text(encoding="utf-8"))
    assert persisted["repositories"] == {
        str(repo_id): str(replacement_path),
    }
    assert (repository / ".patchharbor" / "id").read_text(
        encoding="ascii"
    ) == f"{repo_id}\n"


def test_failure_after_registry_publication_restores_exact_previous_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    register_local_repository(repository)
    paths = registration_user_paths()
    id_path = repository / ".patchharbor" / "id"
    exclude_path = local_exclude_path(repository)
    id_before = id_path.read_bytes()
    exclude_before = exclude_path.read_bytes()
    registry_before = paths.registry_path.read_bytes()

    from patchharbor.registry import write_registry as real_write_registry

    def publish_then_fail(*args: object, **kwargs: object) -> None:
        real_write_registry(*args, **kwargs)
        raise PatchHarborError(
            "injected post-publication failure",
            ExitCode.REPOSITORY_ERROR,
        )

    monkeypatch.setattr(
        "patchharbor.registration.write_registry",
        publish_then_fail,
    )

    with pytest.raises(PatchHarborError):
        register_local_repository(repository, new_id=True)

    assert id_path.read_bytes() == id_before
    assert exclude_path.read_bytes() == exclude_before
    assert paths.registry_path.read_bytes() == registry_before
    assert not tuple(paths.configuration_directory.glob(".patchharbor-*.tmp"))
    assert not tuple((repository / ".patchharbor").glob(".patchharbor-*.tmp"))


def test_failed_identity_rollback_is_reported_as_registry_inconsistency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = create_repository(tmp_path / "repository")
    set_isolated_user_environment(monkeypatch, tmp_path / "user")

    from patchharbor.repository import (
        apply_local_registration as real_apply_local_registration,
    )

    def mutate_then_fail(*args: object, **kwargs: object) -> None:
        real_apply_local_registration(*args, **kwargs)
        raise PatchHarborError(
            "injected mutation failure",
            ExitCode.REPOSITORY_ERROR,
        )

    def fail_local_restore(*_args: object, **_kwargs: object) -> None:
        raise PatchHarborError(
            "injected rollback failure",
            ExitCode.REPOSITORY_ERROR,
        )

    monkeypatch.setattr(
        "patchharbor.registration.apply_local_registration",
        mutate_then_fail,
    )
    monkeypatch.setattr(
        "patchharbor.registration.restore_local_registration",
        fail_local_restore,
    )

    with pytest.raises(PatchHarborError) as captured:
        register_local_repository(repository)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REGISTRY_ERROR


def test_registry_persistence_rejects_a_noncanonical_repository_id(
    tmp_path: Path,
) -> None:
    configuration = tmp_path / "configuration"
    locks = tmp_path / "locks"
    configuration.mkdir()
    locks.mkdir()
    paths = RegistrationUserPaths(configuration, locks)
    invalid_id = object.__new__(RepositoryId)
    object.__setattr__(invalid_id, "value", str(RepositoryId.new()).upper())
    repository_path = RepositoryPath((tmp_path / "repository").resolve())

    from patchharbor.models import RegistryMapping, RegistrySnapshot

    snapshot = RegistrySnapshot(
        repositories=(
            RegistryMapping(
                repo_id=invalid_id,
                repository_path=repository_path,
            ),
        )
    )

    with pytest.raises(PatchHarborError) as captured:
        write_registry(paths, snapshot)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REGISTRY_ERROR
    assert not paths.registry_path.exists()


def test_local_identity_persistence_rejects_a_noncanonical_repository_id(
    tmp_path: Path,
) -> None:
    repository_path = create_repository(tmp_path / "repository")
    repository = inspect_repository(repository_path)
    _, state = inspect_local_registration(repository)
    invalid_id = object.__new__(RepositoryId)
    object.__setattr__(invalid_id, "value", str(RepositoryId.new()).upper())
    exclude_before = state.exclude_path.read_bytes()

    with pytest.raises(PatchHarborError) as captured:
        apply_local_registration(state, invalid_id)

    assert captured.value.exit_code is ExitCode.REPOSITORY_ERROR
    assert captured.value.error_kind is ErrorKind.REPOSITORY_RESOLUTION_ERROR
    assert not state.internal_directory.exists()
    assert state.exclude_path.read_bytes() == exclude_before
