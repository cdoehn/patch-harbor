"""Apply orchestration: resolution, preflight, mutation and execution.

Repository locks and private inputs live through Result completion.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from patchharbor.apply_admission import AdmissionCallback, ApplyAdmissionPolicy
from patchharbor.errors import FailureReason, repository_resolution_error
from pathlib import Path

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
from patchharbor.apply_repository import safely_resolved_repository
from patchharbor.errors import (
    PatchHarborError,
    LockBusyError,
    NoEligiblePatchError,
    state_mismatch_error,
)
from patchharbor.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    execute_prepared_script_with_log,
)
from patchharbor.models import GitObjectId
from patchharbor.output import OutputTargets
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_package as _resolve_patch_package,
)
from patchharbor.payload_files import validate_bundle_payload_targets
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.result_resources import capture_result_resources
from patchharbor.run_report import (
    ApplyPrimaryOutcome,
    RunReport,
    RunSession,
    unresolved_apply_report,
)
from patchharbor.watch_contract import (
    AutomaticApplyResult,
    AutomaticApplyStatus,
    ExchangeWatchTarget,
)
from patchharbor.application_exchange import (
    DiscoveredExchangePatch,
    _automatic_exchange_discovery_scope,
    _maintain_explicit_exchange,
    _manual_exchange_discovery_scope,
    discover_exchange_patch,
)
from patchharbor.application_results import (
    _complete_apply_result_bundle,
    _complete_mutation_result_bundle,
    _publish_attempt_outcome,
    _complete_entrypoint_execution,
)


def resolve_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ValidatedPatchPackage:
    """Resolve one complete patch package through the package boundary."""
    return _resolve_patch_package(path, resource_policy=resource_policy)


@contextmanager
def preflight_patch_package_repository(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    session: RunSession | None = None,
    dry_run: bool = True,
    output: OutputTargets | None = None,
    before_mutation: Callable[[], None] | None = None,
    admission_policy: ApplyAdmissionPolicy | None = None,
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

        def reported_preflight_failure(error: PatchHarborError) -> PatchHarborError:
            # Both failures occur before a mutation gate exists. Keep their
            # publication inside the resolved repository/resource lifetime.
            report = _complete_apply_result_bundle(
                resolved,
                package,
                session=actual_session,
                resources=resources,
                dry_run=dry_run,
                warnings=package.warnings,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
            )
            return report.reported_error()

        activity("BINDING", f"Compare full manifest binding: base {str(manifest.base_commit)}, "
                 f"state {str(manifest.state_fingerprint)}", identifiers=(str(manifest.base_commit), str(manifest.state_fingerprint),))
        if not resolved.matches_manifest_state(manifest):
            activity("BINDING", "Manifest and repository state differ; mutation refused", "error")
            error = state_mismatch_error(
                "patch package does not match the resolved repository state"
            )
            raise reported_preflight_failure(error)

        activity("BINDING", "Repository binding matches", "success")
        with ExitStack() as private_resources:
            try:
                if admission_policy is not None:
                    admission_policy.check_target(resolved)
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
                if admission_policy is not None:
                    admission_policy.authorize(package, resolved)
            except PatchHarborError as error:
                raise reported_preflight_failure(error) from error

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
    admission_policy: ApplyAdmissionPolicy | None = None,
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
        admission_policy=admission_policy,
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
    admission_policy: ApplyAdmissionPolicy | None = None,
) -> RunReport:
    """Run one Apply request through a single public application boundary."""
    actual_session = session or RunSession.start()
    if exchanges is not None and (not automatic or path is not None):
        raise ValueError("Exchange watch scope requires automatic parameterless Apply")
    if admission_policy is not None and (path is None or dry_run or automatic):
        raise ValueError("guarded Apply requires one explicit, actual request")
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
        if admission_policy is not None:
            try:
                target = admission_policy.expected_repository.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise repository_resolution_error("cannot resolve explicitly expected repository") from exc
            admission_policy = replace(admission_policy, expected_repository=target)
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
            if admission_policy is not None and package.package_sha256 != admission_policy.expected_sha256:
                raise PatchHarborError("captured package SHA-256 differs from expected bytes", FailureReason.SOURCE_ERROR)
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
            admission_policy=admission_policy,
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


def run_guarded_apply_path(
    path: Path, *, expected_sha256: str, expected_repository: Path, admission: AdmissionCallback,
    output_directory: Path | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
) -> RunReport:
    """Supply explicit host conditions to the single existing Apply workflow."""
    return run_apply_path(path, dry_run=False, output_directory=output_directory,
        timeout_seconds=timeout_seconds, output=output,
        admission_policy=ApplyAdmissionPolicy(expected_sha256, expected_repository, admission))
