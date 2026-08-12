"""Orchestrate one manual PatchHarbor Result Bundle request."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from time import monotonic
from uuid import UUID, uuid4

from patchharbor.errors import PatchHarborError, result_bundle_error
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


def _create_private_run_directory(run_id: UUID) -> Path:
    """Create one private per-run diagnostics directory in the system temp."""
    temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    run_directory = temporary_root / f"patchharbor-{run_id}"
    run_directory.mkdir(mode=0o700)
    return run_directory.resolve(strict=True)


def _write_run_document(
    run_directory: Path,
    document: dict[str, object],
) -> None:
    """Atomically store one structured run report in the private run directory."""
    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    destination = run_directory / "run.json"
    temporary = run_directory / ".run.json.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _remove_private_run_directory(run_directory: Path) -> None:
    try:
        shutil.rmtree(run_directory)
    except OSError:
        pass


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
    context: RepositoryContext | None,
    repository: RepositoryPath | None,
    repo_id: RepositoryId | None,
    started_at: str,
    ended_at: str,
    duration_seconds: float,
    bundle_status: str,
    bundle_error: str | None,
    process_exit_code: int,
) -> dict[str, object]:
    resolved_repository = context.repository_path if context is not None else repository
    resolved_repo_id = context.repo_id if context is not None else repo_id
    succeeded = process_exit_code == 0
    repository_resolved = (
        resolved_repository is not None and resolved_repo_id is not None
    )
    bundle_attempted = succeeded or repository_resolved
    effective_bundle_status = (
        bundle_status if bundle_attempted else "not_attempted"
    )
    return {
        "run_id": str(run_id),
        "operation": "bundle",
        "dry_run": False,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "repository_resolved": repository_resolved,
        "repo_id": None if resolved_repo_id is None else str(resolved_repo_id),
        "repository_path": (
            None if resolved_repository is None else str(resolved_repository)
        ),
        "base_commit": (
            None if context is None else str(context.base_commit)
        ),
        "state_fingerprint": (
            None if context is None else context.state_fingerprint
        ),
        "fingerprint_algorithm": (
            None if context is None else context.fingerprint_algorithm
        ),
        "warnings": [],
        "execution_present": False,
        "primary_result": {
            "kind": "success" if succeeded else "execution_error",
            "success": succeeded,
            "patchharbor_error_code": (
                None if succeeded else 11
            ),
            "entrypoint_started": False,
            "entrypoint_exit_code": None,
            "timed_out": False,
            "interrupted": False,
        },
        "result_bundle": {
            "attempted": bundle_attempted,
            "status": effective_bundle_status,
            "error": bundle_error,
        },
        "process_exit_code": process_exit_code,
    }


def _preserve_emergency_diagnostics(
    run_directory: Path,
    run_document: dict[str, object],
) -> tuple[Path | None, bool]:
    """Best-effort preserve run.json and report whether rescue itself failed."""
    try:
        _write_run_document(run_directory, run_document)
        return run_directory.resolve(strict=True), False
    except (OSError, RuntimeError, TypeError, ValueError):
        _remove_private_run_directory(run_directory)
        return None, True


def _manual_bundle_failure(
    error: PatchHarborError,
    *,
    run_id: UUID,
    run_directory: Path,
    context: RepositoryContext | None,
    repository: RepositoryPath | None,
    repo_id: RepositoryId | None,
    started_at: str,
    started_monotonic: float,
) -> PatchHarborError:
    ended = _utc_now()
    run_document = _run_document(
        run_id=run_id,
        context=context,
        repository=repository,
        repo_id=repo_id,
        started_at=started_at,
        ended_at=_timestamp(ended),
        duration_seconds=max(0.0, monotonic() - started_monotonic),
        bundle_status="failed",
        bundle_error=str(error),
        process_exit_code=11,
    )
    emergency_path, rescue_failed = _preserve_emergency_diagnostics(
        run_directory,
        run_document,
    )
    return result_bundle_error(
        str(error),
        emergency_diagnostics_path=emergency_path,
        emergency_diagnostics_failed=rescue_failed,
    )


def create_manual_result_bundle(
    path: Path,
    *,
    output_directory: Path | None = None,
) -> ManualResultBundle:
    """Create one Result Bundle for a registered supported repository."""
    started = _utc_now()
    started_at = _timestamp(started)
    started_monotonic = monotonic()
    run_id = uuid4()
    try:
        run_directory = _create_private_run_directory(run_id)
    except (OSError, RuntimeError) as exc:
        raise result_bundle_error(
            "cannot create emergency diagnostics for the Result Bundle",
            emergency_diagnostics_failed=True,
        ) from exc

    context: RepositoryContext | None = None
    resolved_repository: RepositoryPath | None = None
    resolved_repo_id: RepositoryId | None = None
    try:
        paths = registration_user_paths()
        filename_timestamp = started.strftime("%Y%m%d_%H%M%S")
        filename = f"patchharbor_result_{filename_timestamp}_{run_id}.zip"

        with ExitStack() as repository_scope:
            with registry_lock(paths):
                registry_snapshot = load_registry(paths)
                repository = inspect_repository_root(path)
                repo_id = _registered_identity(registry_snapshot, repository)
                resolved_repository = repository
                resolved_repo_id = repo_id
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
            run_document = _run_document(
                run_id=run_id,
                context=context,
                repository=resolved_repository,
                repo_id=resolved_repo_id,
                started_at=started_at,
                ended_at=_timestamp(ended),
                duration_seconds=max(0.0, monotonic() - started_monotonic),
                bundle_status="created",
                bundle_error=None,
                process_exit_code=0,
            )
            _write_run_document(run_directory, run_document)
            publication = prepare_result_bundle_publication(
                target.final_path,
                run_id=run_id,
            )
            published = publish_result_bundle(
                publication,
                manifest=_manifest_document(
                    run_id=run_id,
                    context=context,
                    created_at=started_at,
                    snapshot=bundle_snapshot,
                ),
                context_document=_context_document(
                    context,
                    created_at=started_at,
                ),
                run_document=run_document,
                snapshot=bundle_snapshot,
            )
    except PatchHarborError as exc:
        raise _manual_bundle_failure(
            exc,
            run_id=run_id,
            run_directory=run_directory,
            context=context,
            repository=resolved_repository,
            repo_id=resolved_repo_id,
            started_at=started_at,
            started_monotonic=started_monotonic,
        ) from exc
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        wrapped = result_bundle_error("cannot create the Result Bundle")
        raise _manual_bundle_failure(
            wrapped,
            run_id=run_id,
            run_directory=run_directory,
            context=context,
            repository=resolved_repository,
            repo_id=resolved_repo_id,
            started_at=started_at,
            started_monotonic=started_monotonic,
        ) from exc

    _remove_private_run_directory(run_directory)
    return ManualResultBundle(
        run_id=run_id,
        context=context,
        path=published.path,
        publication_durability=published.durability,
    )
