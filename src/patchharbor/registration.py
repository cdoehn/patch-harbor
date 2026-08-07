"""Application-independent orchestration of repository registry operations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto
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
    restore_registry_state,
    replace_registry_mapping,
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


class _IdentityState(Enum):
    """Observed relationship between one local ID and the registry."""

    LOCAL_ID_MISSING = auto()
    ID_UNMAPPED = auto()
    REGISTERED_HERE = auto()
    REGISTERED_PATH_MISSING = auto()
    REGISTERED_ELSEWHERE = auto()


class _IdentityAction(Enum):
    """Mutation selected for one observed identity state."""

    NEW_ID = auto()
    KEEP_ID = auto()
    REJECT = auto()


_IDENTITY_TRANSITIONS = {
    _IdentityState.LOCAL_ID_MISSING: _IdentityAction.NEW_ID,
    _IdentityState.ID_UNMAPPED: _IdentityAction.KEEP_ID,
    _IdentityState.REGISTERED_HERE: _IdentityAction.KEEP_ID,
    _IdentityState.REGISTERED_PATH_MISSING: _IdentityAction.KEEP_ID,
    _IdentityState.REGISTERED_ELSEWHERE: _IdentityAction.REJECT,
}


@dataclass(frozen=True)
class _IdentityTransition:
    """One fully planned local-ID and central-registry mutation."""

    registry_state: RegistryFileState
    local_state: LocalRegistrationState
    repo_id: RepositoryId
    next_snapshot: RegistrySnapshot


def _identity_state(
    snapshot: RegistrySnapshot,
    repository: RepositoryPath,
    local_id: RepositoryId | None,
) -> _IdentityState:
    if local_id is None:
        return _IdentityState.LOCAL_ID_MISSING

    id_mapping = next(
        (
            mapping
            for mapping in snapshot.repositories
            if mapping.repo_id == local_id
        ),
        None,
    )
    if id_mapping is None:
        return _IdentityState.ID_UNMAPPED
    if id_mapping.repository_path == repository:
        return _IdentityState.REGISTERED_HERE
    if (
        registered_repository_status(
            id_mapping.repository_path,
            local_id,
        )
        is RegistryStatus.MISSING
    ):
        return _IdentityState.REGISTERED_PATH_MISSING
    return _IdentityState.REGISTERED_ELSEWHERE


def _plan_identity_transition(
    registry_state: RegistryFileState,
    repository: RepositoryPath,
    local_id: RepositoryId | None,
    local_state: LocalRegistrationState,
    *,
    new_id: bool,
) -> _IdentityTransition:
    state = _identity_state(
        registry_state.snapshot,
        repository,
        local_id,
    )
    action = (
        _IdentityAction.NEW_ID
        if new_id
        else _IDENTITY_TRANSITIONS[state]
    )
    if action is _IdentityAction.REJECT:
        raise repository_resolution_error(
            "repository ID is already registered to another existing path"
        )

    repo_id = RepositoryId.new() if action is _IdentityAction.NEW_ID else local_id
    if repo_id is None:
        raise AssertionError("identity transition selected no repository ID")

    return _IdentityTransition(
        registry_state=registry_state,
        local_state=local_state,
        repo_id=repo_id,
        next_snapshot=replace_registry_mapping(
            registry_state.snapshot,
            repo_id,
            repository,
        ),
    )


def _restore_identity_transition(
    paths: RegistrationUserPaths,
    transition: _IdentityTransition,
) -> None:
    failures: list[BaseException] = []
    try:
        restore_local_registration(transition.local_state)
    except PatchHarborError as exc:
        failures.append(exc)
    try:
        restore_registry_state(paths, transition.registry_state)
    except PatchHarborError as exc:
        failures.append(exc)
    if failures:
        raise registry_error(
            "registration failed and the previous identity state could not "
            "be fully restored"
        ) from failures[0]


def _commit_identity_transition(
    paths: RegistrationUserPaths,
    transition: _IdentityTransition,
) -> None:
    try:
        apply_local_registration(
            transition.local_state,
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
        local_id, local_state = inspect_local_registration(repository)
        transition = _plan_identity_transition(
            registry_state,
            repository,
            local_id,
            local_state,
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
