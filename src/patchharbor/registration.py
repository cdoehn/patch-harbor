"""Application-independent orchestration of repository registry operations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
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
    RegistryFileState,
    load_registry,
    load_registry_state,
    registry_lock,
    remove_registry_mapping,
    remove_registry_path_mappings,
    restore_registry_state,
    set_registry_mapping,
    write_registry,
)
from patchharbor.repository import (
    LocalRegistrationState,
    apply_local_registration,
    canonicalize_repository_reference,
    inspect_local_registration,
    inspect_repository,
    registered_repository_status,
    restore_local_registration,
)
from patchharbor.user_paths import RegistrationUserPaths, registration_user_paths


class IdentityTransitionKind(str, Enum):
    """Explicit local-identity transition selected from one locked snapshot."""

    CREATE = "create"
    KEEP = "keep"
    MOVE = "move"
    REPLACE = "replace"
    SEPARATE = "separate"


@dataclass(frozen=True)
class IdentityObservation:
    """Identity facts observed while the global registry lock is held."""

    registry_state: RegistryFileState
    repository: RepositoryPath
    local_id: RepositoryId | None
    local_state: LocalRegistrationState
    id_mapping: RegistryMapping | None
    id_mapping_status: RegistryStatus | None
    path_mappings: tuple[RegistryMapping, ...]


@dataclass(frozen=True)
class IdentityTransition:
    """One fully planned local-ID and central-registry mutation."""

    kind: IdentityTransitionKind
    observation: IdentityObservation
    repo_id: RepositoryId
    next_snapshot: RegistrySnapshot


def _mapping_for_id(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RegistryMapping | None:
    return next(
        (
            mapping
            for mapping in snapshot.repositories
            if mapping.repo_id == repo_id
        ),
        None,
    )


def _observe_identity(
    registry_state: RegistryFileState,
    repository: RepositoryPath,
    local_id: RepositoryId | None,
    local_state: LocalRegistrationState,
) -> IdentityObservation:
    snapshot = registry_state.snapshot
    id_mapping = (
        _mapping_for_id(snapshot, local_id)
        if local_id is not None
        else None
    )
    id_mapping_status: RegistryStatus | None = None
    if id_mapping is not None and id_mapping.repository_path != repository:
        id_mapping_status = registered_repository_status(
            id_mapping.repository_path,
            id_mapping.repo_id,
        )
    return IdentityObservation(
        registry_state=registry_state,
        repository=repository,
        local_id=local_id,
        local_state=local_state,
        id_mapping=id_mapping,
        id_mapping_status=id_mapping_status,
        path_mappings=tuple(
            mapping
            for mapping in snapshot.repositories
            if mapping.repository_path == repository
        ),
    )


def _plan_identity_transition(
    observation: IdentityObservation,
    *,
    new_id: bool,
) -> IdentityTransition:
    local_id = observation.local_id
    id_mapping = observation.id_mapping

    if new_id:
        kind = IdentityTransitionKind.SEPARATE
        repo_id = RepositoryId.new()
    elif local_id is None:
        kind = (
            IdentityTransitionKind.REPLACE
            if observation.path_mappings
            else IdentityTransitionKind.CREATE
        )
        repo_id = RepositoryId.new()
    elif id_mapping is None:
        kind = IdentityTransitionKind.CREATE
        repo_id = local_id
    elif id_mapping.repository_path == observation.repository:
        kind = IdentityTransitionKind.KEEP
        repo_id = local_id
    elif observation.id_mapping_status is RegistryStatus.MISSING:
        kind = IdentityTransitionKind.MOVE
        repo_id = local_id
    else:
        raise repository_resolution_error(
            "repository ID is already registered to another existing path"
        )

    next_snapshot = remove_registry_path_mappings(
        observation.registry_state.snapshot,
        observation.repository,
    )
    next_snapshot = set_registry_mapping(
        next_snapshot,
        repo_id,
        observation.repository,
    )
    return IdentityTransition(
        kind=kind,
        observation=observation,
        repo_id=repo_id,
        next_snapshot=next_snapshot,
    )


def _restore_identity_transition(
    paths: RegistrationUserPaths,
    transition: IdentityTransition,
) -> None:
    failures: list[BaseException] = []
    try:
        restore_local_registration(transition.observation.local_state)
    except PatchHarborError as exc:
        failures.append(exc)
    try:
        restore_registry_state(paths, transition.observation.registry_state)
    except PatchHarborError as exc:
        failures.append(exc)
    if failures:
        raise registry_error(
            "registration failed and the previous identity state could not "
            "be fully restored"
        ) from failures[0]


def _commit_identity_transition(
    paths: RegistrationUserPaths,
    transition: IdentityTransition,
) -> None:
    try:
        apply_local_registration(
            transition.observation.local_state,
            transition.repo_id,
        )
        write_registry(paths, transition.next_snapshot)
    except BaseException as primary_error:
        try:
            _restore_identity_transition(paths, transition)
        except PatchHarborError as rollback_error:
            raise registry_error(
                "registration failed and local identity or registry state "
                "may be inconsistent"
            ) from rollback_error
        raise primary_error


def register_local_repository(
    path: Path,
    *,
    new_id: bool = False,
) -> tuple[RepositoryId, RepositoryPath]:
    """Register one local Git repository as one consistent mutation."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        repository = inspect_repository(path)
        registry_state = load_registry_state(user_paths)
        existing_id, local_state = inspect_local_registration(repository)
        observation = _observe_identity(
            registry_state,
            repository,
            existing_id,
            local_state,
        )
        transition = _plan_identity_transition(
            observation,
            new_id=new_id,
        )
        _commit_identity_transition(user_paths, transition)

    return transition.repo_id, repository


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
