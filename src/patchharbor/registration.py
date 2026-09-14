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
from patchharbor.configuration import (
    RepositoryConfiguration,
    RepositoryConfigurationPaths, initialize_configuration, load_configuration,
)
from patchharbor.exchange_paths import (
    ExchangePathPolicyError,
    require_repository_outside_exchange,
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
from patchharbor.locks import registry_lock, repository_lock
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


@dataclass(frozen=True)
class _RegistrationObservation:
    """Repository, registry, and local identity observed under one lock set."""

    repository: RepositoryPath
    registry_state: RegistryFileState
    configuration: RepositoryConfiguration | None
    local_id: RepositoryId | None
    local_state: LocalRegistrationState


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
    replacement_id: RepositoryId | None = None,
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

    if action is _IdentityAction.NEW_ID:
        repo_id = replacement_id or RepositoryId.new()
    else:
        repo_id = local_id
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


def _require_registration_exchange_allowed(
    repository: RepositoryPath,
    configuration: RepositoryConfiguration | None,
) -> None:
    if configuration is None or configuration.exchange_directory is None:
        return
    try:
        require_repository_outside_exchange(
            repository,
            configuration.exchange_directory,
        )
    except ExchangePathPolicyError as exc:
        raise repository_resolution_error(str(exc)) from exc


def _observe_registration(
    paths: RegistrationUserPaths,
    path: Path,
) -> _RegistrationObservation:
    repository = inspect_repository(path)
    registry_state = load_registry_state(paths)
    local_id, local_state = inspect_local_registration(repository)
    # A pre-existing identity or mapping is never an implicit migration trigger.
    if local_id is None:
        if local_state.configuration_content is not None or any(
            m.repository_path == repository for m in registry_state.snapshot.repositories
        ):
            raise repository_resolution_error("local repository identity is missing; manual setup is required")
        configuration = None
    else:
        configuration = load_configuration(
            RepositoryConfigurationPaths(repository, local_id), validate_directory=False,
        )
    _require_registration_exchange_allowed(repository, configuration)
    # Preserve the separation rule for ALL configured repositories, not just self.
    for mapping in registry_state.snapshot.repositories:
        if mapping.repository_path == repository:
            continue
        if registered_repository_status(mapping.repository_path, mapping.repo_id) is not RegistryStatus.OK:
            continue
        other = load_configuration(
            RepositoryConfigurationPaths(mapping.repository_path, mapping.repo_id),
            validate_directory=False,
        )
        _require_registration_exchange_allowed(repository, other)
    return _RegistrationObservation(
        repository=repository,
        registry_state=registry_state,
        configuration=configuration,
        local_id=local_id,
        local_state=local_state,
    )


def _revalidate_registration_exchange(
    paths: RegistrationUserPaths,
    expected: _RegistrationObservation,
) -> None:
    observed = _observe_registration(paths, expected.repository.value)
    current = observed.configuration
    if observed.local_id != expected.local_id or observed.local_state != expected.local_state:
        raise repository_resolution_error("local registration changed while registering repository")
    if current != expected.configuration:
        raise repository_resolution_error(
            "exchange configuration changed while registering repository"
        )
    _require_registration_exchange_allowed(expected.repository, current)


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
        if transition.local_state.id_content is None:
            initialize_configuration(RepositoryConfigurationPaths(
                RepositoryPath(transition.local_state.internal_directory.parent), transition.repo_id,
            ))
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


def _new_identity_lock_id(
    snapshot: RegistrySnapshot,
    repository: RepositoryPath,
    local_id: RepositoryId | None,
    new_id: RepositoryId,
) -> RepositoryId:
    """Select the existing identity affected by an explicit replacement."""
    if local_id is not None:
        return local_id
    path_ids = tuple(
        mapping.repo_id
        for mapping in snapshot.repositories
        if mapping.repository_path == repository
    )
    if len(path_ids) > 1:
        raise repository_resolution_error(
            "repository path has conflicting registrations"
        )
    return path_ids[0] if path_ids else new_id


def _revalidate_new_identity_transition(
    paths: RegistrationUserPaths,
    path: Path,
    expected: _RegistrationObservation,
    *,
    replacement_id: RepositoryId,
    locked_id: RepositoryId,
) -> _IdentityTransition:
    """Re-read every identity boundary while both required locks are held."""
    observed = _observe_registration(paths, path)
    if observed.repository != expected.repository:
        raise repository_resolution_error(
            "repository path changed while acquiring its lock"
        )
    if observed.registry_state.snapshot != expected.registry_state.snapshot:
        raise repository_resolution_error(
            "repository registry changed while acquiring its lock"
        )
    if observed.local_id != expected.local_id:
        raise repository_resolution_error(
            "repository ID changed while acquiring its lock"
        )
    if observed.configuration != expected.configuration:
        raise repository_resolution_error(
            "exchange configuration changed while acquiring repository lock"
        )

    transition = _plan_identity_transition(
        observed.registry_state,
        observed.repository,
        observed.local_id,
        observed.local_state,
        new_id=True,
        replacement_id=replacement_id,
    )
    affected_id = _new_identity_lock_id(
        observed.registry_state.snapshot,
        observed.repository,
        observed.local_id,
        transition.repo_id,
    )
    if affected_id != locked_id:
        raise repository_resolution_error(
            "repository identity changed while acquiring its lock"
        )
    return transition


def register_local_repository(
    path: Path,
    *,
    new_id: bool = False,
) -> tuple[RepositoryId, RepositoryPath]:
    """Register one local Git repository as one consistent mutation."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        observed = _observe_registration(user_paths, path)
        transition = _plan_identity_transition(
            observed.registry_state,
            observed.repository,
            observed.local_id,
            observed.local_state,
            new_id=new_id,
        )
        if new_id:
            affected_id = _new_identity_lock_id(
                observed.registry_state.snapshot,
                observed.repository,
                observed.local_id,
                transition.repo_id,
            )
            with repository_lock(user_paths, affected_id):
                transition = _revalidate_new_identity_transition(
                    user_paths,
                    path,
                    observed,
                    replacement_id=transition.repo_id,
                    locked_id=affected_id,
                )
                _revalidate_registration_exchange(user_paths, observed)
                _commit_identity_transition(user_paths, transition)
        else:
            _revalidate_registration_exchange(user_paths, observed)
            _commit_identity_transition(user_paths, transition)

    return transition.repo_id, observed.repository


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


def _revalidate_unregister_mapping(
    paths: RegistrationUserPaths,
    selected: RegistryMapping,
) -> RegistrySnapshot:
    """Revalidate mapping, physical repository path, and local ID under locks."""
    snapshot = load_registry(paths)
    current = next(
        (
            mapping
            for mapping in snapshot.repositories
            if mapping.repo_id == selected.repo_id
        ),
        None,
    )
    if current != selected:
        raise repository_resolution_error(
            "repository registry changed while acquiring its lock"
        )

    repository = inspect_repository(selected.repository_path.value)
    if repository != selected.repository_path:
        raise repository_resolution_error(
            "repository path changed while acquiring its lock"
        )
    local_id, _ = inspect_local_registration(repository)
    if local_id != selected.repo_id:
        raise repository_resolution_error(
            "repository ID changed while acquiring its lock"
        )
    return snapshot


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
        next_snapshot = remove_registry_mapping(snapshot, selected.repo_id)
        status = registered_repository_status(
            selected.repository_path,
            selected.repo_id,
        )
        if status is RegistryStatus.MISSING:
            write_registry(user_paths, next_snapshot)
        else:
            with repository_lock(user_paths, selected.repo_id):
                locked_snapshot = _revalidate_unregister_mapping(
                    user_paths,
                    selected,
                )
                write_registry(
                    user_paths,
                    remove_registry_mapping(
                        locked_snapshot,
                        selected.repo_id,
                    ),
                )
        return selected.repo_id, selected.repository_path
