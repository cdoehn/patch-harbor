"""Explicit source-safe bundle orchestration using the existing native Result core."""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path

from patchharbor.errors import LockBusyError, PatchHarborError, registry_error, repository_busy_error
from patchharbor.git_commands import safe_git_queries
from patchharbor.result_bundle import ManualResultBundle, _publication_documents
from patchharbor.result_bundle_publication import prepare_result_bundle_publication, publish_result_bundle, result_bundle_filename
from patchharbor.result_bundle_target import ResultBundleTarget
from patchharbor.result_resources import capture_result_resources
from patchharbor.run_report import RunSession, RunReport, RunOperation, PrimaryResult, ResultBundleResult
from patchharbor.safe_capture import capture_safe_result
from patchharbor.safe_export_paths import BoundDirectory, bound_lock
from patchharbor.safe_export_plan import converted_error, revalidate_plan
from patchharbor.safe_export_types import SafeExportPlan, SafeExportError, SafeExportErrorCode, require_host
from patchharbor.watch_contract import ApplyLock, ApplyLockKind


def _write_diagnostic(directory: BoundDirectory, name: str, data: dict):
    fd = directory.create(name)
    with os.fdopen(fd, 'wb') as stream:
        stream.write((json.dumps(data, sort_keys=True) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())


def _cleanup_diagnostics(parent: BoundDirectory, directory: BoundDirectory):
    # Only this request's fixed diagnostic file exists on the success path.
    directory.verify()
    for name in ('run.json',):
        path = directory.io_path(name)
        directory.remove_owned(name, path.lstat())
    os.rmdir(directory.path.name, dir_fd=parent.fd)


def _export_reference(path: Path, *, plan: SafeExportPlan, output_directory: Path | None, lifecycle: dict) -> ManualResultBundle:
    require_host()
    if not isinstance(plan, SafeExportPlan):
        raise TypeError('safe bundle requires a SafeExportPlan')
    if output_directory is not None:
        if Path(os.path.abspath(output_directory.expanduser())) != plan.output_directory:
            raise ValueError('output_directory differs from the safe export plan')
    session = RunSession.start()
    diagnostics = None
    published_path = None
    with safe_git_queries(), ExitStack() as scope:
        try:
            source = revalidate_plan(plan, path)
            output = scope.enter_context(BoundDirectory(plan.output_directory))
            locks = scope.enter_context(BoundDirectory(plan.lock_paths[0].parent))
            lock_checks = []
            for lock_path, kind in zip(plan.lock_paths, (ApplyLockKind.REGISTRY, ApplyLockKind.REPOSITORY)):
                busy = registry_error('repository registry is busy') if kind is ApplyLockKind.REGISTRY else repository_busy_error()
                lock_checks.append(scope.enter_context(bound_lock(locks, lock_path.name,
                    busy_error=LockBusyError(busy, ApplyLock(kind, source.repo_id if kind is ApplyLockKind.REPOSITORY else None)))))
            source = revalidate_plan(plan, path)
            output.verify()
            diagnostic_name = '.patchharbor-safe-' + str(session.run_id)
            diagnostics = scope.enter_context(output.create_directory(diagnostic_name))
            resources = capture_result_resources()
            captured = capture_safe_result(source.repository, source.repo_id)
            if captured.context != plan.context:
                raise SafeExportError(SafeExportErrorCode.STALE, 'captured source differs from the approved safe plan')
            filename = result_bundle_filename(session, repository_name=source.repository.value.name) + source.configuration.bundle_suffix
            target = ResultBundleTarget(output.path, output.path / filename, False,
                source.configuration.bundle_suffix, source.configuration.exchange_directory, source.configuration_paths)
            report = RunReport(timing=session.finish(), operation=RunOperation.BUNDLE, dry_run=False,
                context=captured.context, repository=source.repository, repo_id=source.repo_id, warnings=(),
                primary_result=PrimaryResult.success_result(), result_bundle=ResultBundleResult.created(target.final_path))
            documents = _publication_documents(report, target, captured.bundle_snapshot, resources)
            publication = prepare_result_bundle_publication(output.io_path(filename), run_id=session.run_id)
            def before_publish():
                revalidate_plan(plan, path)
                output.verify()
                diagnostics.verify()
                for check in lock_checks:
                    check()
            published = publish_result_bundle(publication, manifest=documents.manifest,
                context_document=documents.context, handoff=documents.handoff, run_report=documents.report,
                snapshot=captured.bundle_snapshot, runtime=documents.runtime,
                before_atomic_publish=before_publish, directory_guard=output)
            published_path = target.final_path
            lifecycle['published_path'] = published_path
            _write_diagnostic(diagnostics, 'run.json', documents.report.as_run_document())
            try:
                _cleanup_diagnostics(output, diagnostics)
            except (OSError, PatchHarborError) as exc:
                raise SafeExportError(SafeExportErrorCode.CLEANUP, 'safe export cleanup failed',
                                      published_path=published_path) from exc
            return ManualResultBundle(documents.report, published.durability)
        except LockBusyError:
            raise
        except (PatchHarborError, OSError, RuntimeError, ValueError, KeyboardInterrupt, SystemExit) as exc:
            error = converted_error(exc, writing=True)
            error.published_path = getattr(exc, 'published_path', None) or published_path
            lifecycle['published_path'] = error.published_path
            if diagnostics is not None:
                error.emergency_diagnostics_path = diagnostics.current_path()
                try:
                    _write_diagnostic(diagnostics, 'failure.json', {
                        'safe_export_contract': 1, 'run_id': str(session.run_id), 'code': error.code.value,
                        'published_path': str(error.published_path) if error.published_path else None})
                except (OSError, PatchHarborError):
                    error.emergency_diagnostics_failed = True
            if error is exc:
                raise
            raise error from exc


def export_reference(path: Path, *, plan: SafeExportPlan, output_directory: Path | None = None) -> ManualResultBundle:
    lifecycle = {}
    try:
        return _export_reference(path, plan=plan, output_directory=output_directory, lifecycle=lifecycle)
    except OSError as exc:
        # ExitStack failures happen after the inner handler has completed.
        raise SafeExportError(SafeExportErrorCode.CLEANUP, 'safe export resource release failed',
                              published_path=lifecycle.get('published_path')) from exc
