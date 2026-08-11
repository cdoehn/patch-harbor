"""Orchestrate one manual PatchHarbor Result Bundle request."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4
import zipfile

from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.git_objects import capture_base_bundle_entries
from patchharbor.git_patches import capture_change_patches
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
from patchharbor.result_bundle_snapshot import (
    ResultBundleSnapshot,
    build_result_bundle_snapshot,
)
from patchharbor.result_bundle_writer import write_result_bundle
from patchharbor.user_paths import registration_user_paths


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
    snapshot: RegistrySnapshot,
    repository: RepositoryPath,
) -> RepositoryId:
    repo_id, _ = inspect_local_registration(repository)
    if repo_id is None:
        raise result_bundle_error("repository has no local PatchHarbor identity")
    _require_registered_mapping(snapshot, repo_id, repository)
    return repo_id


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_result_directory_outside_repositories(
    directory: Path,
    snapshot: RegistrySnapshot,
) -> None:
    for mapping in snapshot.repositories:
        repository_root = mapping.repository_path.value
        if directory == repository_root or _is_within(
            directory,
            repository_root,
        ):
            raise result_bundle_error(
                "Result Bundle directory overlaps a registered repository"
            )


def _result_directory(
    requested: Path,
    snapshot: RegistrySnapshot,
) -> Path:
    try:
        candidate = physically_canonicalize(requested, must_exist=False)
        _require_result_directory_outside_repositories(candidate, snapshot)
        candidate.mkdir(parents=True, exist_ok=True)
        directory = physically_canonicalize(candidate, must_exist=True)
        _require_result_directory_outside_repositories(directory, snapshot)
        if not directory.is_dir():
            raise OSError("Result Bundle path is not a directory")
        return directory
    except PatchHarborError:
        raise
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error("cannot create the Result Bundle directory") from exc


_REQUIRED_RESULT_BUNDLE_ENTRIES = frozenset(
    (
        "manifest.json",
        "context.json",
        "changes/staged.patch",
        "changes/unstaged.patch",
        "logs/run.json",
    )
)


def _verify_result_bundle(path: Path) -> None:
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            names = archive.namelist()
            if any(
                names.count(name) != 1
                for name in _REQUIRED_RESULT_BUNDLE_ENTRIES
            ):
                raise result_bundle_error(
                    "Result Bundle is missing a required entry"
                )
            if archive.testzip() is not None:
                raise result_bundle_error("Result Bundle failed its CRC check")
    except PatchHarborError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise result_bundle_error("cannot verify the Result Bundle") from exc


def _publish_result_bundle(
    final_path: Path,
    *,
    manifest: dict[str, object],
    context_document: dict[str, object],
    run_document: dict[str, object],
    snapshot: ResultBundleSnapshot,
) -> None:
    temporary_path = final_path.with_name(
        f".{final_path.name}.{uuid4()}.tmp"
    )
    try:
        if final_path.exists() or final_path.is_symlink():
            raise result_bundle_error("Result Bundle destination already exists")
        write_result_bundle(
            temporary_path,
            manifest=manifest,
            context_document=context_document,
            run_document=run_document,
            snapshot=snapshot,
        )
        _verify_result_bundle(temporary_path)
        os.replace(temporary_path, final_path)
    except PatchHarborError:
        raise
    except OSError as exc:
        raise result_bundle_error("cannot publish the Result Bundle") from exc
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


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

    with ExitStack() as repository_scope:
        with registry_lock(paths):
            registry_snapshot = load_registry(paths)
            repository = inspect_repository_root(path)
            repo_id = _registered_identity(registry_snapshot, repository)
            result_directory = _result_directory(
                output_directory or paths.result_directory,
                registry_snapshot,
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
            _require_result_directory_outside_repositories(
                result_directory,
                locked_registry,
            )

        snapshot = capture_consistent_repository_snapshot(locked_repository)
        context = repository_context_from_snapshot(
            locked_repository,
            locked_id,
            snapshot,
        )
        base_entries = capture_base_bundle_entries(
            locked_repository,
            context.base_commit,
        )
        change_patches = capture_change_patches(
            locked_repository,
            context.base_commit,
        )
        bundle_snapshot = build_result_bundle_snapshot(
            base_entries=(
                (
                    entry.path.original_bytes,
                    entry.mode,
                    entry.object_id,
                    entry.content,
                )
                for entry in base_entries
            ),
            staged_patch=change_patches.staged,
            unstaged_patch=change_patches.unstaged,
            untracked_entries=(
                (record.path, record.mode, record.content)
                for record in snapshot.state.untracked
            ),
        )
        final_snapshot = capture_consistent_repository_snapshot(
            locked_repository
        )
        final_context = repository_context_from_snapshot(
            locked_repository,
            locked_id,
            final_snapshot,
        )
        if final_snapshot != snapshot or final_context != context:
            raise result_bundle_error(
                "repository changed while the Result Bundle was captured"
            )

        filename_timestamp = started.strftime("%Y%m%d_%H%M%S")
        result_path = result_directory / (
            f"patchharbor_result_{filename_timestamp}_{run_id}.zip"
        )

        ended = _utc_now()
        created_at = _timestamp(started)
        _publish_result_bundle(
            result_path,
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

    return ManualResultBundle(run_id=run_id, context=context, path=result_path)
