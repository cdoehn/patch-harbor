"""Orchestrate one manual PatchHarbor Result Bundle request."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4

from patchharbor.errors import result_bundle_error
from patchharbor.git_objects import (
    capture_base_bundle_entries,
    capture_change_patches,
)
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.physical_paths import physically_canonicalize
from patchharbor.registry import load_registry
from patchharbor.repository import inspect_local_registration, inspect_repository_root
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
)
from patchharbor.result_bundle_writer import write_result_bundle
from patchharbor.user_paths import RegistrationUserPaths, registration_user_paths


_RESULT_MARKER = "patch-harbor-result-bundle"
_RESULT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ManualResultBundle:
    """One successfully created manual Result Bundle."""

    run_id: UUID
    context: RepositoryContext
    path: Path


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
    paths: RegistrationUserPaths,
    repository: RepositoryPath,
) -> RepositoryId:
    repo_id, _ = inspect_local_registration(repository)
    if repo_id is None:
        raise result_bundle_error("repository has no local PatchHarbor identity")
    _require_registered_mapping(load_registry(paths), repo_id, repository)
    return repo_id


def _default_result_directory(paths: RegistrationUserPaths) -> Path:
    directory = paths.result_directory
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return physically_canonicalize(directory, must_exist=True)
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error("cannot create the Result Bundle directory") from exc


def _manifest_document(
    *,
    run_id: UUID,
    context: RepositoryContext,
    created_at: str,
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


def create_manual_result_bundle(path: Path) -> ManualResultBundle:
    """Create one Result Bundle for a registered supported repository."""
    started = _utc_now()
    started_monotonic = monotonic()
    run_id = uuid4()
    paths = registration_user_paths()

    with ExitStack() as repository_scope:
        with registry_lock(paths):
            repository = inspect_repository_root(path)
            repo_id = _registered_identity(paths, repository)
            repository_scope.enter_context(repository_lock(paths, repo_id))

            locked_repository = inspect_repository_root(repository.value)
            if locked_repository != repository:
                raise result_bundle_error(
                    "repository path changed while acquiring its lock"
                )
            locked_id = _registered_identity(paths, locked_repository)
            if locked_id != repo_id:
                raise result_bundle_error(
                    "repository identity changed while acquiring its lock"
                )

        snapshot = capture_consistent_repository_snapshot(locked_repository)
        context = repository_context_from_snapshot(
            locked_repository,
            locked_id,
            snapshot,
        )
        if snapshot.state.untracked:
            raise result_bundle_error(
                "Result Bundles with untracked files are not supported yet"
            )

        base_entries = capture_base_bundle_entries(
            locked_repository,
            context.base_commit,
        )
        change_patches = capture_change_patches(
            locked_repository,
            context.base_commit,
        )
        result_directory = _default_result_directory(paths)
        filename_timestamp = started.strftime("%Y%m%d_%H%M%S")
        result_path = result_directory / (
            f"patchharbor_result_{filename_timestamp}_{run_id}.zip"
        )

        ended = _utc_now()
        created_at = _timestamp(started)
        write_result_bundle(
            result_path,
            manifest=_manifest_document(
                run_id=run_id,
                context=context,
                created_at=created_at,
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
            base_entries=base_entries,
            staged_patch=change_patches.staged,
            unstaged_patch=change_patches.unstaged,
        )

    return ManualResultBundle(run_id=run_id, context=context, path=result_path)
