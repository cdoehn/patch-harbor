"""Result completion and receipts for manual bundles and Apply attempts.

Primary outcomes, publication errors and already published receipts stay distinct.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from patchharbor.progress import activity
from patchharbor.apply_mutation import ApplyMutationGate
from patchharbor.apply_repository import SafeResolvedRepository
from patchharbor.archive_git import completed_commit_for_context
from patchharbor.errors import PatchHarborError
from patchharbor.execution import ScriptExecutionResult
from patchharbor.models import GitObjectId, RepositoryContext
from patchharbor.patch_package import ValidatedPatchPackage
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
)
from patchharbor.result_bundle import (
    ManualResultBundle,
    create_apply_result_bundle,
    create_manual_result_bundle,
)
from patchharbor.result_resources import PinnedResultResources
from patchharbor.run_report import ApplyPrimaryOutcome, RunReport, RunSession
from patchharbor.application_exchange import _maintain_bundle_exchange


def _complete_apply_result_bundle(
    resolved: SafeResolvedRepository,
    package: ValidatedPatchPackage,
    *,
    session: RunSession,
    resources: PinnedResultResources,
    dry_run: bool,
    warnings: tuple[str, ...],
    primary_outcome: ApplyPrimaryOutcome,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    activity("BUNDLE", "Capture and publish the current Apply Result Bundle", "heading")
    return create_apply_result_bundle(
        resolved.repository,
        resolved.repo_id,
        resolved.registry_snapshot,
        actual_context if actual_context is not None else resolved.context,
        package.manifest,
        target=resolved.result_target,
        publication=resolved.result_publication,
        warnings=warnings,
        session=session,
        resources=resources,
        dry_run=dry_run,
        primary_outcome=primary_outcome,
        execution_log=execution_log,
        package_sha256=package.package_sha256,
        before_publish=before_result_publication,
    )


def _complete_mutation_result_bundle(
    mutation_gate: ApplyMutationGate,
    *,
    primary_outcome: ApplyPrimaryOutcome,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    """Complete one apply result from the single checked mutation gate."""
    return _complete_apply_result_bundle(
        mutation_gate.resolved,
        mutation_gate.package,
        session=mutation_gate.session,
        resources=mutation_gate.result_resources,
        dry_run=mutation_gate.dry_run,
        warnings=mutation_gate.warnings,
        primary_outcome=primary_outcome,
        execution_log=execution_log,
        actual_context=actual_context,
        before_result_publication=before_result_publication,
    )


def _publish_attempt_outcome(
    mutation_gate: ApplyMutationGate,
    publisher: Callable[[bool, GitObjectId | None], None] | None,
    *,
    succeeded: bool,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
    completed_report: RunReport | None = None,
) -> None:
    """Persist one automatic outcome or complete it as a PatchHarbor failure."""
    if publisher is None:
        return
    try:
        completed_commit = None
        if succeeded:
            # This optional receipt must never turn execution success into a
            # claim that a commit exists when state/history capture is unclear.
            try:
                resolved = mutation_gate.resolved
                after = repository_context_from_snapshot(
                    resolved.repository, resolved.repo_id,
                    capture_consistent_repository_snapshot(resolved.repository),
                )
                completed_commit = completed_commit_for_context(resolved.context, after)
            except (PatchHarborError, OSError, ValueError):
                pass
        publisher(succeeded, completed_commit)
    except PatchHarborError as error:
        if completed_report is not None:
            # The successful execution bundle is already published and pinned.
            # Do not overwrite it or attempt another bundle with the same name.
            report = RunReport.completed_apply(
                timing=completed_report.timing, dry_run=completed_report.dry_run,
                context=completed_report.context, repository=completed_report.repository,
                repo_id=completed_report.repo_id, warnings=completed_report.warnings,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
                result_bundle=completed_report.result_bundle,
            )
        else:
            report = _complete_mutation_result_bundle(
                mutation_gate,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
                execution_log=execution_log,
                actual_context=actual_context,
            )
        raise report.reported_error() from error


def _complete_entrypoint_execution(
    mutation_gate: ApplyMutationGate,
    execution: ScriptExecutionResult,
    *,
    publish_attempt_outcome: Callable[[bool, GitObjectId | None], None] | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    """Publish one execution result before unwinding the shared apply scope."""
    primary_outcome = ApplyPrimaryOutcome.from_execution_result(
        entrypoint_started=execution.entrypoint_started,
        entrypoint_exit_code=execution.entrypoint_exit_code,
        patchharbor_error=execution.patchharbor_error,
    )
    report = _complete_mutation_result_bundle(
        mutation_gate,
        primary_outcome=primary_outcome,
        execution_log=(execution.output if execution.entrypoint_started else None),
        before_result_publication=before_result_publication,
    )
    _publish_attempt_outcome(
        mutation_gate,
        publish_attempt_outcome,
        succeeded=primary_outcome.result.success,
        execution_log=(execution.output if execution.entrypoint_started else None),
        completed_report=report,
    )

    if execution.patchharbor_error is not None:
        raise report.reported_error()
    if primary_outcome.result.success and report.completion_tool_error is not None:
        raise report.reported_error()
    return report


def bundle_repository(
    path: Path,
    *,
    output_directory: Path | None = None,
) -> ManualResultBundle:
    """Create one manual Result Bundle for a registered repository."""
    _maintain_bundle_exchange(path)
    return create_manual_result_bundle(
        path,
        output_directory=output_directory,
    )
