"""Capture the reproducible state of one registered Git repository."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

from patchharbor.errors import PatchHarborError, repository_resolution_error
from patchharbor.git_capture import (
    read_base_and_index_paths,
    read_head_object_id,
    read_staged_records,
    read_unstaged_records,
    read_untracked_paths,
    read_untracked_records,
    require_supported_repository_state,
)
from patchharbor.git_commands import run_git_bytes
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    GitObjectId,
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
    RepositorySnapshot,
    RepositoryState,
)
from patchharbor.registry import load_registry
from patchharbor.repository import (
    inspect_local_registration,
    inspect_repository,
    inspect_repository_root,
)
from patchharbor.repository_paths import validate_repository_paths
from patchharbor.state_fingerprint import (
    FINGERPRINT_ALGORITHM,
    encode_staged_record,
    encode_unstaged_record,
    encode_untracked_record,
    state_fingerprint_digest,
)
from patchharbor.user_paths import RegistrationUserPaths, registration_user_paths


def _error(message: str) -> PatchHarborError:
    return repository_resolution_error(message)


def _require_clean_for_registration(repository: RepositoryPath) -> None:
    status = run_git_bytes(
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        ".",
        ":(exclude).patchharbor",
        cwd=repository.value,
    )
    if status:
        raise _error("repository state is not clean")


def _require_registered_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
    repository: RepositoryPath,
) -> None:
    id_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repo_id == repo_id
    )
    path_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repository_path == repository
    )
    if len(id_matches) != 1 or id_matches[0].repository_path != repository:
        raise _error("repository identity is not registered for this path")
    if len(path_matches) != 1 or path_matches[0].repo_id != repo_id:
        raise _error("repository path has conflicting registrations")


def _registered_identity(
    paths: RegistrationUserPaths,
    repository: RepositoryPath,
) -> RepositoryId:
    repo_id, _ = inspect_local_registration(repository)
    if repo_id is None:
        raise _error("repository has no local PatchHarbor identity")
    _require_registered_mapping(load_registry(paths), repo_id, repository)
    return repo_id


def require_clean_repository(path: Path) -> RepositoryPath:
    """Resolve one repository and reject mutations before registration."""
    repository = inspect_repository(path)
    _require_clean_for_registration(repository)
    return repository


def capture_repository_state(
    repository: RepositoryPath,
    base_commit: GitObjectId,
) -> RepositoryState:
    """Validate and capture all supported non-HEAD repository state."""
    require_supported_repository_state(repository)
    raw_untracked_paths = read_untracked_paths(repository)
    validated_paths = validate_repository_paths(
        (
            *read_base_and_index_paths(repository, base_commit),
            *raw_untracked_paths,
        )
    )
    paths_by_bytes = {path.original_bytes: path for path in validated_paths}
    untracked_paths = tuple(
        paths_by_bytes[raw_path]
        for raw_path in raw_untracked_paths
    )
    return RepositoryState(
        staged=read_staged_records(repository, base_commit),
        unstaged=read_unstaged_records(
            repository,
            base_commit.object_format,
        ),
        untracked=read_untracked_records(repository, untracked_paths),
    )


def capture_repository_snapshot(
    repository: RepositoryPath,
) -> RepositorySnapshot:
    """Capture one complete base commit and supported non-HEAD state."""
    base_commit = read_head_object_id(repository)
    return RepositorySnapshot(
        base_commit=base_commit,
        state=capture_repository_state(repository, base_commit),
    )


def capture_consistent_repository_snapshot(
    repository: RepositoryPath,
) -> RepositorySnapshot:
    """Return one stable snapshot or reject concurrent repository changes."""
    first = capture_repository_snapshot(repository)
    second = capture_repository_snapshot(repository)
    if first != second:
        raise _error("repository changed while being read")
    return second


def repository_context_from_snapshot(
    repository: RepositoryPath,
    repo_id: RepositoryId,
    snapshot: RepositorySnapshot,
) -> RepositoryContext:
    """Build one context from an immutable, already captured snapshot."""
    state = snapshot.state
    encoded_staged = tuple(
        encode_staged_record(
            path=record.path,
            head_mode=record.head_mode,
            head_object=record.head_object,
            index_mode=record.index_mode,
            index_object=record.index_object,
        )
        for record in state.staged
    )
    encoded_unstaged = tuple(
        encode_unstaged_record(
            path=record.path,
            status=record.status,
            index_mode=record.index_mode,
            index_object=record.index_object,
            worktree_kind=record.worktree_kind,
            worktree_mode=record.worktree_mode,
            worktree_content=record.worktree_content,
        )
        for record in state.unstaged
    )
    encoded_untracked = tuple(
        encode_untracked_record(
            path=record.path,
            mode=record.mode,
            content=record.content,
        )
        for record in state.untracked
    )
    return RepositoryContext(
        repo_id=repo_id,
        repository_path=repository,
        base_commit=snapshot.base_commit,
        dirty=state.dirty,
        state_fingerprint=state_fingerprint_digest(
            staged_records=encoded_staged,
            unstaged_records=encoded_unstaged,
            untracked_records=encoded_untracked,
        )[:16],
        fingerprint_algorithm=FINGERPRINT_ALGORITHM,
    )


def capture_repository_context(path: Path) -> RepositoryContext:
    """Capture one registered repository and release its lock after capture."""
    paths = registration_user_paths()
    with ExitStack() as repository_scope:
        with registry_lock(paths):
            repository = inspect_repository_root(path)
            repo_id = _registered_identity(paths, repository)
            repository_scope.enter_context(repository_lock(paths, repo_id))

            locked_repository = inspect_repository_root(repository.value)
            if locked_repository != repository:
                raise _error("repository path changed while acquiring its lock")
            locked_id = _registered_identity(paths, locked_repository)
            if locked_id != repo_id:
                raise _error("repository identity changed while acquiring its lock")

        snapshot = capture_consistent_repository_snapshot(locked_repository)

    return repository_context_from_snapshot(
        locked_repository,
        locked_id,
        snapshot,
    )
