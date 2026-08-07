"""Application-independent orchestration of repository registry operations."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchharbor.errors import (
    PatchHarborError,
    registry_error,
    repository_resolution_error,
)
from patchharbor.models import (
    RegistryListResult,
    RegistryMapping,
    RegistryRepository,
    RegistrySnapshot,
    RegistryStatus,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.registry import (
    load_registry,
    registry_lock,
    remove_registry_mapping,
    set_registry_mapping,
    write_registry,
)
from patchharbor.repository import (
    apply_local_registration,
    canonicalize_repository_reference,
    inspect_local_registration,
    inspect_repository,
    registered_repository_status,
    restore_local_registration,
)
from patchharbor.user_paths import registration_user_paths


def register_local_repository(
    path: Path,
) -> tuple[RepositoryId, RepositoryPath]:
    """Register one local Git repository as one consistent mutation."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        repository = inspect_repository(path)
        snapshot = load_registry(user_paths)
        existing_id, local_state = inspect_local_registration(repository)
        repo_id = existing_id or RepositoryId.new()

        try:
            apply_local_registration(local_state, repo_id)
            write_registry(
                user_paths,
                set_registry_mapping(snapshot, repo_id, repository),
            )
        except PatchHarborError:
            try:
                restore_local_registration(local_state)
            except PatchHarborError as rollback_error:
                raise registry_error(
                    "registration failed and local state could not be restored"
                ) from rollback_error
            raise

    return repo_id, repository


def resolve_registry_snapshot(snapshot: RegistrySnapshot) -> RegistryListResult:
    """Resolve file-system status without changing the captured mappings."""
    path_counts = Counter(
        str(mapping.repository_path) for mapping in snapshot.repositories
    )
    repositories: list[RegistryRepository] = []
    for mapping in snapshot.repositories:
        status = registered_repository_status(
            mapping.repository_path,
            mapping.repo_id,
        )
        if path_counts[str(mapping.repository_path)] > 1:
            status = RegistryStatus.CONFLICT
        repositories.append(
            RegistryRepository(
                repo_id=mapping.repo_id,
                repository_path=mapping.repository_path,
                status=status,
            )
        )
    return RegistryListResult(repositories=tuple(repositories))


def list_registered_repositories() -> RegistryListResult:
    """Capture one locked snapshot, then resolve its observed statuses."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        snapshot = load_registry(user_paths)
    return resolve_registry_snapshot(snapshot)


def resolve_unregister_mapping(
    snapshot: RegistrySnapshot,
    selector: str,
    *,
    cwd: Path,
) -> RegistryMapping:
    """Resolve one exact canonical UUID or one exact canonical path."""
    try:
        selected_id = RepositoryId(selector)
    except ValueError:
        requested_path = Path(selector).expanduser()
        if not requested_path.is_absolute():
            requested_path = cwd / requested_path
        selected_path = canonicalize_repository_reference(requested_path)
        matches = tuple(
            mapping
            for mapping in snapshot.repositories
            if mapping.repository_path == selected_path
        )
        if not matches:
            raise repository_resolution_error("repository is not registered")
        if len(matches) != 1:
            raise repository_resolution_error(
                "repository path has conflicting registrations"
            )
        return matches[0]

    for mapping in snapshot.repositories:
        if mapping.repo_id == selected_id:
            return mapping
    raise repository_resolution_error("repository ID is not registered")


def unregister_local_repository(
    selector: str,
    *,
    cwd: Path,
) -> tuple[RepositoryId, RepositoryPath]:
    """Remove exactly one central mapping while preserving its local ID."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        snapshot = load_registry(user_paths)
        selected = resolve_unregister_mapping(snapshot, selector, cwd=cwd)
        write_registry(
            user_paths,
            remove_registry_mapping(snapshot, selected.repo_id),
        )
        return selected.repo_id, selected.repository_path
