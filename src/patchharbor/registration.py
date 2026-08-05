"""Application-independent orchestration of one repository registration."""

from __future__ import annotations

from pathlib import Path

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import RegisteredRepository, RepositoryId
from patchharbor.registry import load_registry, registry_lock, write_registry
from patchharbor.repository import (
    apply_local_registration,
    inspect_local_registration,
    inspect_repository,
    restore_local_registration,
)
from patchharbor.user_paths import registration_user_paths


def _error(message: str) -> PatchHarborError:
    return PatchHarborError(message, ExitCode.REPOSITORY_ERROR)


def register_local_repository(path: Path) -> RegisteredRepository:
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
        except PatchHarborError as exc:
            try:
                restore_local_registration(local_state)
            except PatchHarborError as rollback_error:
                raise _error(
                    "registration failed and local state could not be restored"
                ) from rollback_error
            raise

    return RegisteredRepository(repo_id=repo_id, path=repository)
