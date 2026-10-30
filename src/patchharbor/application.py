"""Application facade and orchestration for one PatchHarbor runner request.

Configuration and Exchange discovery are delegated to their workflow modules.
The public Python API continues to enter through this facade.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from patchharbor.progress import (
    PackageFile,
    RepositoryResolved,
    RequestStarted,
    ScriptPrepared,
    activity,
    emit,
)
from patchharbor.apply_mutation import (
    ApplyMutationGate,
    MutationFailureKind,
    apply_payload_mutation,
)
from patchharbor.apply_preflight import prepare_patch_package
from patchharbor.apply_repository import (
    SafeResolvedRepository,
    safely_resolved_repository,
)
from patchharbor.archive_git import completed_commit_for_context
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.configuration import RepositoryConfiguration
from patchharbor.errors import (
    FailureReason,
    PatchHarborError,
    LockBusyError,
    NoEligiblePatchError,
    state_mismatch_error,
)
from patchharbor.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    ScriptExecutionResult,
    execute_prepared_script_with_log,
    execute_script_text,
)
from patchharbor.models import BundleScript, GitObjectId, InputArtifact, RepositoryContext
from patchharbor.output import OutputTargets
from patchharbor.parser import parse_script
from patchharbor.patch_manifest import PatchManifest
from patchharbor.patch_inspection import (
    PatchInspection,
    PatchValidationResult,
    inspect_patch as _inspect_patch,
    validate_patch as _validate_patch,
)
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_package as _resolve_patch_package,
    validate_patch_package as _validate_patch_package,
)
from patchharbor.payload_files import (
    validate_bundle_payload_targets,
    write_bundle_payloads,
)
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.result_bundle import (
    ManualResultBundle,
    create_apply_result_bundle,
    create_manual_result_bundle,
)
from patchharbor.result_resources import PinnedResultResources, capture_result_resources
from patchharbor.run_report import (
    ApplyPrimaryOutcome,
    RunReport,
    RunSession,
    unresolved_apply_report,
)
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    stdin_input_artifact,
)
from patchharbor.watch_contract import (
    AutomaticApplyResult,
    AutomaticApplyStatus,
    ExchangeWatchTarget,
)
from patchharbor.application_configuration import (
    configure_archive_directory,
    configure_bundle_suffix,
    configure_exchange_directory,
    register_repository,
    registered_repositories,
    repository_configuration,
    repository_context,
    unregister_repository,
)
from patchharbor.application_exchange import (
    DiscoveredExchangePatch,
    _automatic_exchange_discovery_scope,
    _maintain_bundle_exchange,
    _maintain_explicit_exchange,
    _manual_exchange_discovery_scope,
    apply_readiness,
    discover_exchange_patch,
    watch_control_paths,
    watch_targets,
)


def resolve_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ValidatedPatchPackage:
    """Resolve one complete patch package through the package boundary."""
    return _resolve_patch_package(path, resource_policy=resource_policy)


def validate_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> PatchManifest:
    """Validate one complete patch package through the package boundary."""
    return _validate_patch_package(path, resource_policy=resource_policy)


def inspect_patch(path: Path) -> PatchInspection:
    """Read package facts without entering the Apply lifecycle."""
    return _inspect_patch(path)


def validate_patch(path: Path, *, repository: Path | None = None,
                   reference_bundle: Path | None = None) -> PatchValidationResult:
    """Validate an explicitly supplied package; no implicit repository selection."""
    return _validate_patch(path, repository=repository, reference_bundle=reference_bundle)


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


@contextmanager
def preflight_patch_package_repository(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    session: RunSession | None = None,
    dry_run: bool = True,
    output: OutputTargets | None = None,
    before_mutation: Callable[[], None] | None = None,
) -> Iterator[ApplyMutationGate]:
    """Yield the explicit mutation gate while private inputs and locks live."""
    actual_session = session or RunSession.start()
    manifest = package.manifest
    with ExitStack() as repository_scope:
        try:
            resolved = repository_scope.enter_context(
                safely_resolved_repository(
                    manifest,
                    session=actual_session,
                    output_directory=output_directory,
                )
            )
        except PatchHarborError as error:
            report = unresolved_apply_report(
                session=actual_session,
                dry_run=dry_run,
                warnings=package.warnings,
                error=error,
            )
            raise report.reported_error() from error

        # Pin the running producer before payload writes, entrypoint execution,
        # or observer callbacks can change the installation/source checkout.
        resources = capture_result_resources()
        emit(RepositoryResolved(resolved.context))

        activity("BINDING", f"Compare full manifest binding: base {str(manifest.base_commit)}, "
                 f"state {str(manifest.state_fingerprint)}", identifiers=(str(manifest.base_commit), str(manifest.state_fingerprint),))
        if not resolved.matches_manifest_state(manifest):
            activity("BINDING", "Manifest and repository state differ; mutation refused", "error")
            error = state_mismatch_error(
                "patch package does not match the resolved repository state"
            )
            report = _complete_apply_result_bundle(
                resolved,
                package,
                session=actual_session,
                resources=resources,
                dry_run=dry_run,
                warnings=package.warnings,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
            )
            raise report.reported_error()

        activity("BINDING", "Repository binding matches", "success")
        with ExitStack() as private_resources:
            try:
                prepared_package = private_resources.enter_context(
                    prepare_patch_package(
                        package,
                        repository=resolved.repository.value,
                    )
                )
                validate_bundle_payload_targets(
                    prepared_package.payloads,
                    cwd=resolved.repository.value,
                )
            except PatchHarborError as error:
                report = _complete_apply_result_bundle(
                    resolved,
                    package,
                    session=actual_session,
                    resources=resources,
                    dry_run=dry_run,
                    warnings=package.warnings,
                    primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
                )
                raise report.reported_error() from error

            if output is not None:
                output.write_warnings(prepared_package.warnings)

            emit(ScriptPrepared(
                name=package.entrypoint.relative_path,
                index=1, total=1,
                messages=tuple(
                    (message.name, message.text)
                    for message in prepared_package.entrypoint.script.messages
                ),
                warnings=prepared_package.warnings,
            ))

            yield ApplyMutationGate(
                session=actual_session,
                resolved=resolved,
                package=package,
                prepared_package=prepared_package,
                dry_run=dry_run,
                result_resources=resources,
                before_mutation=before_mutation,
            )


def dry_run_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
) -> RunReport:
    """Complete one safe dry-run and publish its unchanged Result Bundle."""
    actual_session = session or RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=actual_session,
        dry_run=True,
        output=output,
    ) as mutation_gate:
        activity("DRY-RUN", "Validation complete; no payload write or entrypoint execution", "success")
        report = _complete_mutation_result_bundle(
            mutation_gate,
            primary_outcome=ApplyPrimaryOutcome.dry_run_success(),
        )
        if report.completion_tool_error is not None:
            raise report.reported_error()
        return report


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


def _require_payload_mutation(
    mutation_gate: ApplyMutationGate,
    *,
    publish_attempt_outcome: Callable[[bool, GitObjectId | None], None] | None = None,
) -> None:
    """Complete a failed mutation as the primary apply result."""
    try:
        result = apply_payload_mutation(mutation_gate)
    except PatchHarborError as error:
        report = _complete_mutation_result_bundle(
            mutation_gate,
            primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
        )
        raise report.reported_error() from error

    if result.success:
        return
    if result.failure_kind is not MutationFailureKind.STATE_MISMATCH:
        _publish_attempt_outcome(
            mutation_gate,
            publish_attempt_outcome,
            succeeded=False,
            actual_context=result.context,
        )
    error = result.error
    if error is None:
        raise RuntimeError("failed mutation result has no error")
    report = _complete_mutation_result_bundle(
        mutation_gate,
        primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
        actual_context=result.context,
    )
    raise report.reported_error()


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


def apply_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    before_mutation: Callable[[], None] | None = None,
    publish_attempt_outcome: Callable[[bool, GitObjectId | None], None] | None = None,
    before_result_publication: Callable[[str], None] | None = None,
) -> RunReport:
    """Write one validated package, run its private entrypoint, and bundle it."""
    actual_session = session or RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=actual_session,
        dry_run=False,
        output=output,
        before_mutation=before_mutation,
    ) as mutation_gate:
        _require_payload_mutation(
            mutation_gate,
            publish_attempt_outcome=publish_attempt_outcome,
        )
        prepared_package = mutation_gate.prepared_package
        execution = execute_prepared_script_with_log(
            prepared_package.entrypoint.path,
            interpreter=prepared_package.entrypoint.interpreter,
            cwd=mutation_gate.resolved.repository.value,
            timeout_seconds=timeout_seconds,
            execution_log_path=prepared_package.execution_log_path,
            output=output,
        )
        return _complete_entrypoint_execution(
            mutation_gate,
            execution,
            publish_attempt_outcome=publish_attempt_outcome,
            before_result_publication=before_result_publication,
        )


def run_apply_path(
    path: Path | None,
    *,
    dry_run: bool,
    output_directory: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    automatic: bool = False,
    current_directory: Path | None = None,
    exchanges: tuple[ExchangeWatchTarget, ...] | None = None,
) -> RunReport:
    """Run one Apply request through a single public application boundary."""
    actual_session = session or RunSession.start()
    if exchanges is not None and (not automatic or path is not None):
        raise ValueError("Exchange watch scope requires automatic parameterless Apply")
    attempted = False

    def finish(report: RunReport, error: PatchHarborError | None = None) -> RunReport:
        if not automatic:
            return report
        status = AutomaticApplyStatus.ERROR
        blocked_on = None
        if attempted:
            status = AutomaticApplyStatus.ATTEMPTED
        elif isinstance(error, NoEligiblePatchError):
            status = AutomaticApplyStatus.NO_CANDIDATE
        elif dry_run and report.success:
            status = AutomaticApplyStatus.DRY_RUN
        else:
            # Completion may wrap a pre-mutation lock failure to attach its
            # Result Bundle. Follow explicit causes, never diagnostic text.
            cause: BaseException | None = error
            seen: set[int] = set()
            while cause is not None and id(cause) not in seen:
                seen.add(id(cause))
                if isinstance(cause, LockBusyError):
                    status, blocked_on = AutomaticApplyStatus.LOCKED, cause.lock
                    break
                cause = cause.__cause__
        return replace(report, automatic=AutomaticApplyResult(status, blocked_on))

    def publish_attempt() -> None:
        nonlocal attempted
        assert discovered is not None
        discovered.publish_attempt(str(actual_session.run_id))
        attempted = True

    try:
        discovered: DiscoveredExchangePatch | None = None
        if path is None:
            scope = (
                _automatic_exchange_discovery_scope(exchanges)
                if automatic
                else _manual_exchange_discovery_scope(
                    Path.cwd() if current_directory is None else current_directory
                )
            )
            discovered = discover_exchange_patch(scope, archive=not dry_run, output=output)
            selected_path = discovered.artifact.path
            package = discovered.package
        else:
            selected_path = path
            package = resolve_patch_package(selected_path)
            if not dry_run:
                discovered = _maintain_explicit_exchange(package, selected_path, output=output)
    except PatchHarborError as error:
        return finish(unresolved_apply_report(
            session=actual_session,
            dry_run=dry_run,
            error=error,
        ), error)

    emit(RequestStarted(
        source_name=str(selected_path),
        requested_repo_id=str(package.manifest.repo_id),
        files=(
            PackageFile(package.entrypoint.relative_path,
                        len(package.entrypoint.content), "entrypoint"),
            *(PackageFile(payload.relative_path, len(payload.content), "payload")
              for payload in package.payloads),
        ),
        script_total=1,
        warnings=package.warnings,
    ))
    if output is not None:
        output.write_warnings(package.warnings)

    try:
        if dry_run:
            return finish(dry_run_patch_package(
                package,
                output_directory=output_directory,
                output=output,
                session=actual_session,
            ))
        return finish(apply_patch_package(
            package,
            output_directory=output_directory,
            timeout_seconds=timeout_seconds,
            output=output,
            session=actual_session,
            before_mutation=(
                publish_attempt
                if discovered is not None
                else None
            ),
            before_result_publication=(
                (lambda digest: discovered.publish_result_digest(str(actual_session.run_id), digest))
                if discovered is not None else None
            ),
            publish_attempt_outcome=(
                (lambda succeeded, commit: discovered.publish_outcome(
                    succeeded, commit, run_id=str(actual_session.run_id),
                ))
                if discovered is not None
                else None
            ),
        ))
    except PatchHarborError as error:
        report = error.run_report
        if isinstance(report, RunReport):
            return finish(report, error)
        return finish(unresolved_apply_report(
            session=actual_session,
            dry_run=dry_run,
            warnings=package.warnings,
            error=error,
        ), error)


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


def _execute_bundle_script(
    bundle_script: BundleScript,
    *,
    script_index: int,
    script_total: int,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
) -> int:
    parsed_script = parse_script(bundle_script.text)
    script_warnings = parsed_script.warnings
    emit(ScriptPrepared(
        name=bundle_script.display_name,
        index=script_index, total=script_total,
        messages=tuple((message.name, message.text) for message in parsed_script.messages),
        warnings=script_warnings,
    ))
    if output is not None:
        output.write_warnings(script_warnings)
    return execute_script_text(
        parsed_script.text,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
    )


def run_input_artifact(
    artifact: InputArtifact,
    *,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Resolve and execute every script in one input artifact."""
    bundle = resolve_patch_bundle(artifact, policy=resource_policy)
    emit(RequestStarted(
        source_name=artifact.display_name,
        files=tuple(PackageFile(payload.relative_path, len(payload.content), "bundle")
                    for payload in bundle.payloads),
        script_total=len(bundle.scripts), warnings=bundle.warnings,
    ))
    if output is not None:
        output.write_warnings(bundle.warnings)
    write_bundle_payloads(bundle.payloads, cwd=cwd)
    last_exit_code = 0
    script_total = len(bundle.scripts)
    for script_index, bundle_script in enumerate(bundle.scripts, start=1):
        last_exit_code = _execute_bundle_script(
            bundle_script,
            script_index=script_index,
            script_total=script_total,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
        )
        if last_exit_code != 0:
            return last_exit_code
    return last_exit_code


def run_standard_input(
    stream: TextIO,
    *,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Own the temporary stdin artifact for exactly one runner request."""
    with stdin_input_artifact(stream, policy=resource_policy) as artifact:
        return run_input_artifact(
            artifact,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
            resource_policy=resource_policy,
        )


def _is_directory_candidate(
    path: Path,
    resource_policy: ResourcePolicy,
) -> bool:
    try:
        resolve_patch_bundle(
            file_input_artifact(path),
            policy=resource_policy,
        )
        activity("SELECT", f"Manual input candidate is executable: {path.name}", "success")
        return True
    except PatchHarborError as exc:
        activity("SKIP", f"{path.name}: not a valid manual input ({exc})", "detail")
        return False


def discover_directory_candidates(
    directory: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[DirectoryCandidate, ...]:
    """Return sorted regular files that resolve to a PatchBundle."""
    return tuple(
        candidate
        for candidate in list_directory_entries(directory)
        if _is_directory_candidate(candidate.path, resource_policy)
    )


def _run_selected_candidate(
    candidate: DirectoryCandidate,
    *,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    if candidate.path.is_symlink() or not candidate.path.is_file():
        raise PatchHarborError(
            f"selected script is no longer available: {candidate.display_name}",
            FailureReason.SOURCE_ERROR,
        )

    return run_input_artifact(
        file_input_artifact(candidate.path),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
        resource_policy=resource_policy,
    )


def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    select_candidate: Callable[[tuple[DirectoryCandidate, ...]], DirectoryCandidate] | None = None,
    output: OutputTargets | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Run a script/ZIP file or select one from a directory."""
    if not path.is_dir():
        return run_input_artifact(
            file_input_artifact(path),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
            resource_policy=resource_policy,
        )

    candidates = discover_directory_candidates(
        path,
        resource_policy=resource_policy,
    )
    if not candidates:
        raise PatchHarborError(
            f"no PatchHarbor scripts found in directory {path}",
            FailureReason.NO_VALID_SCRIPT,
        )
    if len(candidates) == 1:
        selected = candidates[0]
    elif select_candidate is None:
        raise PatchHarborError(
            "multiple scripts found; an explicit candidate selector is required",
            FailureReason.USAGE_ERROR,
        )
    else:
        selected = select_candidate(candidates)
        if selected not in candidates:
            raise PatchHarborError("selector returned an unknown candidate", FailureReason.USAGE_ERROR)
    activity("SELECT", f"Selected manual candidate: {selected.display_name}", "success")
    return _run_selected_candidate(
        selected,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
        resource_policy=resource_policy,
    )
