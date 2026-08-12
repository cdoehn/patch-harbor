"""Orchestrate one manual PatchHarbor Result Bundle request."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4

from patchharbor.errors import result_bundle_error
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.registry import load_registry
from patchharbor.repository import inspect_local_registration, inspect_repository_root
from patchharbor.result_bundle_capture import capture_result_bundle
from patchharbor.result_bundle_publication import (
    PublicationDurability,
    prepare_result_bundle_publication,
    publish_result_bundle,
)
from patchharbor.result_bundle_snapshot import ResultBundleSnapshot
from patchharbor.result_bundle_target import (
    prepare_result_bundle_target,
    revalidate_result_bundle_target,
)
from patchharbor.user_paths import registration_user_paths


_RESULT_MARKER = "patch-harbor-result-bundle"
_RESULT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ManualResultBundle:
    """One successfully created manual Result Bundle."""

    run_id: UUID
    context: RepositoryContext
    path: Path
    publication_durability: PublicationDurability


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_registered_mapping(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
    repository: RepositoryPath,
) -> None:
    id_matches = tuple(
        mapping for mapping in snapshot.repositories if mapping.repo_id == repo_id
    )
    path_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repository_path == repository
    )
    if len(id_matches) != 1 or id_matches[0].repository_path != repository:
        raise result_bundle_error("repository identity is not registered for this path")
    if len(path_matches) != 1 or path_matches[0].repo_id != repo_id:
        raise result_bundle_error("repository path has conflicting registrations")


def _registered_identity(
    snapshot: RegistrySnapshot,
    repository: RepositoryPath,
) -> RepositoryId:
    repo_id, _ = inspect_local_registration(repository)
    if repo_id is None:
        raise result_bundle_error("repository has no local PatchHarbor identity")
    _require_registered_mapping(snapshot, repo_id, repository)
    return repo_id


def _manifest_document(
    *,
    run_id: UUID,
    context: RepositoryContext,
    created_at: str,
    snapshot: ResultBundleSnapshot,
) -> dict[str, object]:
    return {
        "marker": _RESULT_MARKER,
        "format_version": _RESULT_FORMAT_VERSION,
        "created_at": created_at,
        "run_id": str(run_id),
        "repo_id": str(context.repo_id),
        "base_commit": str(context.base_commit),
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm,
        "dirty": context.dirty,
        "dry_run": False,
        "execution_present": False,
        "primary_result": "success",
        "result_bundle_status": "created",
        **snapshot.manifest_entries(),
    }


def _context_document(
    context: RepositoryContext,
    *,
    created_at: str,
) -> dict[str, object]:
    return {
        "repo_id": str(context.repo_id),
        "base_commit": str(context.base_commit),
        "dirty": context.dirty,
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm,
        "created_at": created_at,
    }


def _run_document(
    *,
    run_id: UUID,
    context: RepositoryContext,
    started_at: str,
    ended_at: str,
    duration_seconds: float,
) -> dict[str, object]:
    return {
        "run_id": str(run_id),
        "operation": "bundle",
        "dry_run": False,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "repository_resolved": True,
        "repo_id": str(context.repo_id),
        "repository_path": str(context.repository_path),
        "base_commit": str(context.base_commit),
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm,
        "execution_present": False,
        "primary_result": {
            "kind": "success",
            "success": True,
            "patchharbor_error_code": None,
            "entrypoint_started": False,
            "entrypoint_exit_code": None,
            "timed_out": False,
            "interrupted": False,
        },
        "result_bundle": {
            "attempted": True,
            "status": "created",
            "error": None,
        },
        "process_exit_code": 0,
    }


def create_manual_result_bundle(
    path: Path,
    *,
    output_directory: Path | None = None,
) -> ManualResultBundle:
    """Create one Result Bundle for a registered supported repository."""
    started = _utc_now()
    started_monotonic = monotonic()
    run_id = uuid4()
    paths = registration_user_paths()
    filename_timestamp = started.strftime("%Y%m%d_%H%M%S")
    filename = f"patchharbor_result_{filename_timestamp}_{run_id}.zip"

    with ExitStack() as repository_scope:
        with registry_lock(paths):
            registry_snapshot = load_registry(paths)
            repository = inspect_repository_root(path)
            repo_id = _registered_identity(registry_snapshot, repository)
            target = prepare_result_bundle_target(
                output_directory or paths.result_directory,
                registry_snapshot,
                filename=filename,
            )
            repository_scope.enter_context(repository_lock(paths, repo_id))

            locked_repository = inspect_repository_root(repository.value)
            if locked_repository != repository:
                raise result_bundle_error(
                    "repository path changed while acquiring its lock"
                )
            locked_registry = load_registry(paths)
            locked_id = _registered_identity(locked_registry, locked_repository)
            if locked_id != repo_id:
                raise result_bundle_error(
                    "repository identity changed while acquiring its lock"
                )
            revalidate_result_bundle_target(target, locked_registry)

        captured = capture_result_bundle(locked_repository, locked_id)
        revalidate_result_bundle_target(target, locked_registry)
        context = captured.context
        bundle_snapshot = captured.bundle_snapshot
        ended = _utc_now()
        created_at = _timestamp(started)
        publication = prepare_result_bundle_publication(
            target.final_path,
            run_id=run_id,
        )
        published = publish_result_bundle(
            publication,
            manifest=_manifest_document(
                run_id=run_id,
                context=context,
                created_at=created_at,
                snapshot=bundle_snapshot,
            ),
            context_document=_context_document(
                context,
                created_at=created_at,
            ),
            run_document=_run_document(
                run_id=run_id,
                context=context,
                started_at=created_at,
                ended_at=_timestamp(ended),
                duration_seconds=max(0.0, monotonic() - started_monotonic),
            ),
            snapshot=bundle_snapshot,
        )

    return ManualResultBundle(
        run_id=run_id,
        context=context,
        path=published.path,
        publication_durability=published.durability,
    )
