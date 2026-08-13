"""Resolve one patch manifest to an exact, locked local repository."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from patchharbor.errors import repository_resolution_error
from patchharbor.locks import (
    registry_lock,
    repository_lock,
    repository_lock_path,
)
from patchharbor.models import (
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.patch_manifest import PatchManifest
from patchharbor.registry import load_registry
from patchharbor.repository import (
    inspect_repository,
    require_local_repository_identity,
)
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
)
from patchharbor.result_bundle_publication import (
    ResultBundlePublication,
    release_result_bundle_publication,
    reserve_result_bundle_publication,
    result_bundle_filename,
)
from patchharbor.result_bundle_target import (
    ResultBundleTarget,
    prepare_result_bundle_target,
    revalidate_result_bundle_target,
)
from patchharbor.run_report import RunSession
from patchharbor.user_paths import registration_user_paths


@dataclass(frozen=True, slots=True)
class SafeResolvedRepository:
    """One exact repository context proven while its lock remains held."""

    repository: RepositoryPath
    repo_id: RepositoryId
    registry_lock_path: Path
    repository_lock_path: Path
    registry_snapshot: RegistrySnapshot
    context: RepositoryContext
    result_target: ResultBundleTarget
    result_publication: ResultBundlePublication

    def __post_init__(self) -> None:
        if self.context.repository_path != self.repository:
            raise ValueError("resolved repository conflicts with its context")
        if self.context.repo_id != self.repo_id:
            raise ValueError("resolved repository ID conflicts with its context")
        if not self.registry_lock_path.is_absolute():
            raise ValueError("registry lock path must be absolute")
        if not self.repository_lock_path.is_absolute():
            raise ValueError("repository lock path must be absolute")
        if self.result_target.final_path != self.result_publication.final_path:
            raise ValueError("Result Bundle target and publication disagree")
        if not self.result_publication.reserved:
            raise ValueError("apply Result Bundle publication must be reserved")


def _repository_path_for_id(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RepositoryPath:
    id_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repo_id == repo_id
    )
    if len(id_matches) != 1:
        raise repository_resolution_error("repository ID is not registered")
    selected = id_matches[0]
    path_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repository_path == selected.repository_path
    )
    if len(path_matches) != 1 or path_matches[0].repo_id != repo_id:
        raise repository_resolution_error(
            "repository path has conflicting registrations"
        )
    return selected.repository_path


def _inspect_registered_repository(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RepositoryPath:
    expected_path = _repository_path_for_id(snapshot, repo_id)
    repository = inspect_repository(expected_path.value)
    if repository != expected_path:
        raise repository_resolution_error(
            "registered repository path no longer identifies the same repository"
        )
    require_local_repository_identity(repository, repo_id)
    return repository


@contextmanager
def safely_resolved_repository(
    manifest: PatchManifest,
    *,
    session: RunSession,
    output_directory: Path | None = None,
) -> Iterator[SafeResolvedRepository]:
    """Yield one exact context while its repository lock and output hold live."""
    paths = registration_user_paths()
    with ExitStack() as repository_scope:
        with registry_lock(paths):
            initial_registry = load_registry(paths)
            expected_repository = _repository_path_for_id(
                initial_registry,
                manifest.repo_id,
            )
            target = prepare_result_bundle_target(
                output_directory or paths.result_directory,
                initial_registry,
                filename=result_bundle_filename(session),
            )
            publication = reserve_result_bundle_publication(
                target.final_path,
                run_id=session.run_id,
            )
            repository_scope.callback(
                release_result_bundle_publication,
                publication,
            )

            repository = _inspect_registered_repository(
                initial_registry,
                manifest.repo_id,
            )
            if repository != expected_repository:
                raise repository_resolution_error(
                    "registered repository path changed during validation"
                )

            lock_path = repository_lock_path(paths, manifest.repo_id)
            repository_scope.enter_context(
                repository_lock(paths, manifest.repo_id)
            )

            locked_registry = load_registry(paths)
            locked_repository = _inspect_registered_repository(
                locked_registry,
                manifest.repo_id,
            )
            if locked_repository != repository:
                raise repository_resolution_error(
                    "repository path changed while acquiring its lock"
                )
            revalidate_result_bundle_target(target, locked_registry)

        snapshot = capture_consistent_repository_snapshot(locked_repository)
        context = repository_context_from_snapshot(
            locked_repository,
            manifest.repo_id,
            snapshot,
        )
        yield SafeResolvedRepository(
            repository=locked_repository,
            repo_id=manifest.repo_id,
            registry_lock_path=paths.registry_lock_path,
            repository_lock_path=lock_path,
            registry_snapshot=locked_registry,
            context=context,
            result_target=target,
            result_publication=publication,
        )
