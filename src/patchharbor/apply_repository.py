"""Resolve one patch manifest to an exact, locked local repository."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from patchharbor.progress import activity

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

    def matches_manifest_state(self, manifest: PatchManifest) -> bool:
        """Whether the manifest names this exact resolved repository state."""
        return (
            manifest.repo_id == self.repo_id
            and manifest.base_commit == self.context.base_commit
            and manifest.fingerprint_algorithm
            == self.context.fingerprint_algorithm
            and manifest.state_fingerprint == self.context.state_fingerprint
        )


def _repository_path_for_id(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RepositoryPath:
    selected = None
    for mapping in snapshot.repositories:
        if mapping.repo_id != repo_id:
            continue
        if selected is not None:
            raise repository_resolution_error(
                "repository ID has conflicting registrations"
            )
        selected = mapping
    if selected is None:
        raise repository_resolution_error("repository ID is not registered")
    if any(
        mapping.repo_id != repo_id
        and mapping.repository_path == selected.repository_path
        for mapping in snapshot.repositories
    ):
        raise repository_resolution_error(
            "repository path has conflicting registrations"
        )
    return selected.repository_path


def _inspect_repository_identity(
    expected_path: RepositoryPath,
    repo_id: RepositoryId,
) -> RepositoryPath:
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
    activity("REPO", "Resolve exact repository instance and reserve Result destination")
    paths = registration_user_paths()
    with ExitStack() as repository_scope:
        with registry_lock(paths):
            initial_registry = load_registry(paths)
            expected_repository = _repository_path_for_id(
                initial_registry,
                manifest.repo_id,
            )
            target = prepare_result_bundle_target(
                output_directory,
                initial_registry,
                paths,
                filename=result_bundle_filename(
                    session,
                    repository_name=expected_repository.value.name,
                ),
            )
            publication = reserve_result_bundle_publication(
                target.final_path,
                run_id=session.run_id,
            )
            repository_scope.callback(
                release_result_bundle_publication,
                publication,
            )

            repository = _inspect_repository_identity(
                expected_repository,
                manifest.repo_id,
            )

            activity("LOCK", f"Acquire repository lock: {repository}")
            lock_path = repository_lock_path(paths, manifest.repo_id)
            repository_scope.enter_context(
                repository_lock(paths, manifest.repo_id)
            )

            activity("LOCK", "Repository lock held; revalidate registration and identity", "success")
            locked_registry = load_registry(paths)
            locked_path = _repository_path_for_id(
                locked_registry,
                manifest.repo_id,
            )
            if locked_path != repository:
                raise repository_resolution_error(
                    "repository path changed while acquiring its lock"
                )
            locked_repository = _inspect_repository_identity(
                locked_path,
                manifest.repo_id,
            )
            revalidate_result_bundle_target(target, locked_registry, paths)

        activity("STATE", f"Capture locked repository context: {locked_repository}")
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
