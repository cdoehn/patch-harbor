"""Orchestrate one manual PatchHarbor Result Bundle request."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import os
from pathlib import Path
from uuid import UUID

from patchharbor.errors import (
    ErrorKind,
    ExitCode,
    PatchHarborError,
    repository_resolution_error,
    result_bundle_error,
)
from patchharbor.json_document import serialize_json_document
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.models import (
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.patch_manifest import PatchManifest
from patchharbor.registry import load_registry
from patchharbor.repository import inspect_local_registration, inspect_repository_root
from patchharbor.result_bundle_capture import capture_result_bundle
from patchharbor.result_bundle_publication import (
    PublicationDurability,
    ResultBundlePublication,
    prepare_result_bundle_publication,
    publish_result_bundle,
    result_bundle_filename,
)
from patchharbor.result_bundle_snapshot import ResultBundleSnapshot
from patchharbor.result_bundle_target import (
    ResultBundleTarget,
    prepare_result_bundle_target,
    revalidate_result_bundle_target,
)
from patchharbor.run_report import (
    ApplyPrimaryOutcome,
    PrimaryResult,
    PrimaryResultKind,
    ResultBundleResult,
    ResultBundleStatus,
    RunOperation,
    RunReport,
    RunSession,
)
from patchharbor.temporary_resources import (
    create_private_request_directory,
    remove_private_request_directory,
)
from patchharbor.user_paths import registration_user_paths


_RESULT_MARKER = "patch-harbor-result-bundle"
_RESULT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ManualResultBundle:
    """One successfully created manual Result Bundle."""

    report: RunReport
    publication_durability: PublicationDurability

    @property
    def run_id(self) -> UUID:
        return self.report.run_id

    @property
    def context(self) -> RepositoryContext:
        context = self.report.context
        if context is None:
            raise RuntimeError("successful manual bundle has no repository context")
        return context

    @property
    def path(self) -> Path:
        path = self.report.result_bundle.path
        if path is None:
            raise RuntimeError("successful manual bundle has no published path")
        return path


def _create_private_run_directory(run_id: UUID) -> Path:
    """Create one private per-run diagnostics directory in the system temp."""
    return create_private_request_directory(name=f"patchharbor-{run_id}")


def _write_run_document(
    run_directory: Path,
    report: RunReport,
) -> None:
    """Atomically store one structured run report in the private run directory."""
    payload = serialize_json_document(report.as_run_document()).encode("utf-8")
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
    remove_private_request_directory(run_directory)


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
        raise repository_resolution_error(
            "repository identity is not registered for this path"
        )
    if len(path_matches) != 1 or path_matches[0].repo_id != repo_id:
        raise repository_resolution_error(
            "repository path has conflicting registrations"
        )


def _registered_identity(
    snapshot: RegistrySnapshot,
    repository: RepositoryPath,
) -> RepositoryId:
    repo_id, _ = inspect_local_registration(repository)
    if repo_id is None:
        raise repository_resolution_error(
            "repository has no local PatchHarbor identity"
        )
    _require_registered_mapping(snapshot, repo_id, repository)
    return repo_id


def _manifest_document(
    *,
    report: RunReport,
    snapshot: ResultBundleSnapshot,
    expected_manifest: PatchManifest | None = None,
) -> dict[str, object]:
    context = report.context
    if context is None:
        raise ValueError("successful Result Bundle report has no context")
    document: dict[str, object] = {
        "marker": _RESULT_MARKER,
        "format_version": _RESULT_FORMAT_VERSION,
        "created_at": report.timing.started_at_text,
        "run_id": report.run_id_text,
        "repo_id": str(context.repo_id),
        "base_commit": str(context.base_commit),
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm,
        "dirty": context.dirty,
        "dry_run": report.dry_run,
        "entrypoint_started": report.primary_result.entrypoint_started,
        "execution_present": report.execution_present,
        "primary_result": report.primary_result.kind_text,
        "result_bundle_status": report.result_bundle.status_text,
        **snapshot.manifest_entries(),
    }
    if expected_manifest is not None:
        document.update(
            {
                "expected_base_commit": str(expected_manifest.base_commit),
                "actual_base_commit": str(context.base_commit),
                "expected_state_fingerprint": (
                    expected_manifest.state_fingerprint
                ),
                "actual_state_fingerprint": context.state_fingerprint,
                "expected_fingerprint_algorithm": (
                    expected_manifest.fingerprint_algorithm
                ),
                "actual_fingerprint_algorithm": (
                    context.fingerprint_algorithm
                ),
            }
        )
    return document


def _context_document(report: RunReport) -> dict[str, object]:
    context = report.context
    if context is None:
        raise ValueError("successful Result Bundle report has no context")
    return {
        "repo_id": str(context.repo_id),
        "base_commit": str(context.base_commit),
        "dirty": context.dirty,
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm,
        "created_at": report.timing.started_at_text,
    }


def _primary_kind_for_error(error: PatchHarborError) -> PrimaryResultKind:
    if error.error_kind is ErrorKind.REPOSITORY_BUSY:
        return PrimaryResultKind.REPOSITORY_BUSY
    if error.error_kind in {
        ErrorKind.REGISTRY_ERROR,
        ErrorKind.REPOSITORY_RESOLUTION_ERROR,
        ErrorKind.UNSUPPORTED_REPOSITORY_STATE,
    }:
        return PrimaryResultKind.REPOSITORY_ERROR
    return PrimaryResultKind.EXECUTION_ERROR


def _preserve_emergency_diagnostics(
    run_directory: Path,
    report: RunReport,
) -> tuple[Path | None, bool]:
    """Best-effort preserve run.json and report whether rescue itself failed."""
    try:
        _write_run_document(run_directory, report)
        return run_directory.resolve(strict=True), False
    except (OSError, RuntimeError, TypeError, ValueError):
        _remove_private_run_directory(run_directory)
        return None, True


def _manual_bundle_failure(
    error: PatchHarborError,
    *,
    session: RunSession,
    run_directory: Path,
    context: RepositoryContext | None,
    repository: RepositoryPath | None,
    repo_id: RepositoryId | None,
) -> PatchHarborError:
    repository_resolved = repository is not None and repo_id is not None
    bundle_result = (
        ResultBundleResult.failed(str(error))
        if repository_resolved
        else ResultBundleResult.not_attempted(str(error))
    )
    report = RunReport(
        timing=session.finish(),
        operation=RunOperation.BUNDLE,
        dry_run=False,
        context=context,
        repository=repository,
        repo_id=repo_id,
        warnings=(),
        primary_result=PrimaryResult.tool_failure(
            kind=_primary_kind_for_error(error),
            patchharbor_error_code=int(error.exit_code),
        ),
        result_bundle=bundle_result,
        process_exit_code=int(ExitCode.RESULT_BUNDLE_ERROR),
    )
    emergency_path, rescue_failed = _preserve_emergency_diagnostics(
        run_directory,
        report,
    )
    report = report.with_result_bundle(
        report.result_bundle.with_emergency_diagnostics(emergency_path)
    )
    return PatchHarborError(
        str(error),
        ExitCode.RESULT_BUNDLE_ERROR,
        error_kind=error.error_kind,
        emergency_diagnostics_path=emergency_path,
        emergency_diagnostics_failed=rescue_failed,
        run_report=report,
    )


def _apply_report(
    *,
    session: RunSession,
    dry_run: bool,
    repository: RepositoryPath,
    repo_id: RepositoryId,
    context: RepositoryContext,
    warnings: tuple[str, ...],
    primary_outcome: ApplyPrimaryOutcome,
    result_bundle: ResultBundleResult,
) -> RunReport:
    process_exit_code = primary_outcome.exit_code
    if (
        primary_outcome.result.success
        and result_bundle.status is ResultBundleStatus.FAILED
    ):
        process_exit_code = int(ExitCode.RESULT_BUNDLE_ERROR)
    return RunReport(
        timing=session.finish(),
        operation=RunOperation.APPLY,
        dry_run=dry_run,
        context=context,
        repository=repository,
        repo_id=repo_id,
        warnings=warnings,
        primary_result=primary_outcome.result,
        result_bundle=result_bundle,
        process_exit_code=process_exit_code,
    )


def create_apply_result_bundle(
    repository: RepositoryPath,
    repo_id: RepositoryId,
    registry_snapshot: RegistrySnapshot,
    actual_context: RepositoryContext,
    expected_manifest: PatchManifest,
    *,
    target: ResultBundleTarget,
    publication: ResultBundlePublication,
    warnings: tuple[str, ...],
    session: RunSession,
    dry_run: bool,
    primary_outcome: ApplyPrimaryOutcome,
) -> RunReport:
    """Attempt one apply Result Bundle while the repository lock is held."""
    try:
        run_directory = _create_private_run_directory(session.run_id)
    except (OSError, RuntimeError):
        return _apply_report(
            session=session,
            dry_run=dry_run,
            repository=repository,
            repo_id=repo_id,
            context=actual_context,
            warnings=warnings,
            primary_outcome=primary_outcome,
            result_bundle=ResultBundleResult.failed(
                "cannot create emergency diagnostics for the Result Bundle"
            ),
        )

    try:
        captured = capture_result_bundle(repository, repo_id)
        revalidate_result_bundle_target(target, registry_snapshot)
        report = _apply_report(
            session=session,
            dry_run=dry_run,
            repository=repository,
            repo_id=repo_id,
            context=captured.context,
            warnings=warnings,
            primary_outcome=primary_outcome,
            result_bundle=ResultBundleResult.created(target.final_path),
        )
        _write_run_document(run_directory, report)
        publish_result_bundle(
            publication,
            manifest=_manifest_document(
                report=report,
                snapshot=captured.bundle_snapshot,
                expected_manifest=expected_manifest,
            ),
            context_document=_context_document(report),
            run_report=report,
            snapshot=captured.bundle_snapshot,
        )
    except PatchHarborError as exc:
        report = _apply_report(
            session=session,
            dry_run=dry_run,
            repository=repository,
            repo_id=repo_id,
            context=actual_context,
            warnings=warnings,
            primary_outcome=primary_outcome,
            result_bundle=ResultBundleResult.failed(str(exc)),
        )
        emergency_path, rescue_failed = _preserve_emergency_diagnostics(
            run_directory,
            report,
        )
        if rescue_failed:
            return report
        return report.with_result_bundle(
            report.result_bundle.with_emergency_diagnostics(emergency_path)
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        report = _apply_report(
            session=session,
            dry_run=dry_run,
            repository=repository,
            repo_id=repo_id,
            context=actual_context,
            warnings=warnings,
            primary_outcome=primary_outcome,
            result_bundle=ResultBundleResult.failed(
                "cannot create the Result Bundle"
            ),
        )
        emergency_path, rescue_failed = _preserve_emergency_diagnostics(
            run_directory,
            report,
        )
        if rescue_failed:
            return report
        return report.with_result_bundle(
            report.result_bundle.with_emergency_diagnostics(emergency_path)
        )

    _remove_private_run_directory(run_directory)
    return report


def create_manual_result_bundle(
    path: Path,
    *,
    output_directory: Path | None = None,
) -> ManualResultBundle:
    """Create one Result Bundle for a registered supported repository."""
    session = RunSession.start()
    try:
        run_directory = _create_private_run_directory(session.run_id)
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
        filename = result_bundle_filename(session)

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
                    raise repository_resolution_error(
                        "repository path changed while acquiring its lock"
                    )
                locked_registry = load_registry(paths)
                locked_id = _registered_identity(locked_registry, locked_repository)
                if locked_id != repo_id:
                    raise repository_resolution_error(
                        "repository identity changed while acquiring its lock"
                    )
                revalidate_result_bundle_target(target, locked_registry)

            captured = capture_result_bundle(locked_repository, locked_id)
            revalidate_result_bundle_target(target, locked_registry)
            context = captured.context
            bundle_snapshot = captured.bundle_snapshot
            report = RunReport(
                timing=session.finish(),
                operation=RunOperation.BUNDLE,
                dry_run=False,
                context=context,
                repository=resolved_repository,
                repo_id=resolved_repo_id,
                warnings=(),
                primary_result=PrimaryResult.success_result(),
                result_bundle=ResultBundleResult.created(target.final_path),
                process_exit_code=0,
            )
            _write_run_document(run_directory, report)
            publication = prepare_result_bundle_publication(
                target.final_path,
                run_id=session.run_id,
            )
            published = publish_result_bundle(
                publication,
                manifest=_manifest_document(
                    report=report,
                    snapshot=bundle_snapshot,
                ),
                context_document=_context_document(report),
                run_report=report,
                snapshot=bundle_snapshot,
            )
    except PatchHarborError as exc:
        raise _manual_bundle_failure(
            exc,
            session=session,
            run_directory=run_directory,
            context=context,
            repository=resolved_repository,
            repo_id=resolved_repo_id,
        ) from exc
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        wrapped = result_bundle_error("cannot create the Result Bundle")
        raise _manual_bundle_failure(
            wrapped,
            session=session,
            run_directory=run_directory,
            context=context,
            repository=resolved_repository,
            repo_id=resolved_repo_id,
        ) from exc

    _remove_private_run_directory(run_directory)
    return ManualResultBundle(
        report=report,
        publication_durability=published.durability,
    )
