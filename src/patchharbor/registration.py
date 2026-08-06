"""Application-independent orchestration of repository registry operations."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import (
    RegistryRepository,
    RegistryStatus,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.registry import load_registry, registry_lock, write_registry
from patchharbor.repository import (
    apply_local_registration,
    canonicalize_repository_reference,
    inspect_local_registration,
    inspect_repository,
    registered_repository_status,
    restore_local_registration,
)
from patchharbor.user_paths import registration_user_paths


def _error(message: str) -> PatchHarborError:
    return PatchHarborError(message, ExitCode.REPOSITORY_ERROR)


def register_local_repository(
    path: Path,
) -> tuple[RepositoryId, RepositoryPath]:
    """Register one local Git repository as one consistent mutation."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        repository = inspect_repository(path)
        repositories = load_registry(user_paths)
        existing_id, local_state = inspect_local_registration(repository)
        repo_id = existing_id or RepositoryId.new()

        try:
            apply_local_registration(local_state, repo_id)
            repositories[repo_id] = repository
            write_registry(user_paths, repositories)
        except PatchHarborError:
            try:
                restore_local_registration(local_state)
            except PatchHarborError as rollback_error:
                raise _error(
                    "registration failed and local state could not be restored"
                ) from rollback_error
            raise

    return repo_id, repository


def list_registered_repositories() -> tuple[RegistryRepository, ...]:
    """Read one locked registry snapshot and resolve every mapping status."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        repositories = load_registry(user_paths)
        path_counts = Counter(str(path) for path in repositories.values())
        result: list[RegistryRepository] = []
        for repo_id, repository_path in sorted(
            repositories.items(),
            key=lambda item: str(item[0]).encode("ascii"),
        ):
            status = registered_repository_status(repository_path, repo_id)
            if path_counts[str(repository_path)] > 1:
                status = RegistryStatus.CONFLICT
            result.append(
                RegistryRepository(
                    repo_id=repo_id,
                    repository_path=repository_path,
                    status=status,
                )
            )
        return tuple(result)


def unregister_local_repository(
    selector: str,
    *,
    cwd: Path,
) -> tuple[RepositoryId, RepositoryPath]:
    """Remove exactly one central mapping while preserving its local ID."""
    user_paths = registration_user_paths()
    with registry_lock(user_paths):
        repositories = load_registry(user_paths)
        try:
            selected_id = RepositoryId(selector)
        except ValueError:
            requested_path = Path(selector).expanduser()
            if not requested_path.is_absolute():
                requested_path = cwd / requested_path
            selected_path = canonicalize_repository_reference(requested_path)
            matches = tuple(
                (repo_id, repository_path)
                for repo_id, repository_path in repositories.items()
                if repository_path == selected_path
            )
            if not matches:
                raise _error("repository is not registered")
            if len(matches) != 1:
                raise _error("repository path has conflicting registrations")
            selected_id, selected_path = matches[0]
        else:
            try:
                selected_path = repositories[selected_id]
            except KeyError as exc:
                raise _error("repository ID is not registered") from exc

        del repositories[selected_id]
        write_registry(user_paths, repositories)
        return selected_id, selected_path
