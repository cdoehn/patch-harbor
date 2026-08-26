"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import TextIO

from patchharbor.apply_mutation import (
    ApplyMutationGate,
    apply_payload_mutation,
)
from patchharbor.apply_preflight import prepare_patch_package
from patchharbor.apply_repository import (
    SafeResolvedRepository,
    safely_resolved_repository,
)
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.configuration import (
    UserConfiguration,
    load_configuration,
    prepare_exchange_directory,
    resolve_exchange_directory_candidate,
    revalidate_exchange_directory,
    write_prepared_configuration,
)
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    configuration_error,
    registry_error,
    state_mismatch_error,
)
from patchharbor.exchange_paths import (
    ExchangePathPolicyError,
    require_exchange_outside_registry,
)
from patchharbor.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    ScriptExecutionResult,
    execute_prepared_script_with_log,
    execute_script_text,
)
from patchharbor.locks import registry_lock
from patchharbor.models import (
    BundleScript,
    InputArtifact,
    RegistryListResult,
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.output import OutputTargets
from patchharbor.parser import parse_script
from patchharbor.patch_manifest import PatchManifest
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_package as _resolve_patch_package,
    validate_patch_package as _validate_patch_package,
)
from patchharbor.payload_files import (
    validate_bundle_payload_targets,
    write_bundle_payloads,
)
from patchharbor.presentation import DashboardPresentation, PresentedFile
from patchharbor.registration import (
    list_registered_repositories,
    register_local_repository,
    unregister_local_repository,
)
from patchharbor.registry import load_registry
from patchharbor.repository_state import (
    capture_repository_context,
    require_clean_repository,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.result_bundle import (
    ManualResultBundle,
    create_apply_result_bundle,
    create_manual_result_bundle,
)
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
    select_directory_candidate,
    stdin_input_artifact,
)
from patchharbor.user_paths import configuration_user_paths


def _require_exchange_configuration_allowed(
    exchange_directory: Path,
    registry_snapshot: RegistrySnapshot,
    *,
    exchange_must_exist: bool,
) -> None:
    try:
        require_exchange_outside_registry(
            exchange_directory,
            registry_snapshot,
            exchange_must_exist=exchange_must_exist,
        )
    except ExchangePathPolicyError as exc:
        raise configuration_error(str(exc)) from exc


def configure_exchange_directory(path: Path) -> tuple[Path, UserConfiguration]:
    """Persist one registry-safe shared exchange directory under the global lock."""
    paths = configuration_user_paths()
    candidate = resolve_exchange_directory_candidate(path)
    with registry_lock(paths):
        expected_registry = load_registry(paths)
        _require_exchange_configuration_allowed(
            candidate,
            expected_registry,
            exchange_must_exist=False,
        )
        configuration = prepare_exchange_directory(paths, path)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory,
            expected_registry,
            exchange_must_exist=True,
        )

        current_registry = load_registry(paths)
        if current_registry != expected_registry:
            raise registry_error(
                "repository registry changed while configuring exchange directory"
            )
        configuration = revalidate_exchange_directory(configuration)
        _require_exchange_configuration_allowed(
            configuration.exchange_directory,
            current_registry,
            exchange_must_exist=True,
        )
        return (
            paths.configuration_path,
            write_prepared_configuration(paths, configuration),
        )


def shared_configuration() -> tuple[Path, UserConfiguration]:
    """Return the currently persisted shared user configuration."""
    paths = configuration_user_paths()
    return paths.configuration_path, load_configuration(paths)


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


def _complete_apply_result_bundle(
    resolved: SafeResolvedRepository,
    package: ValidatedPatchPackage,
    *,
    session: RunSession,
    dry_run: bool,
    warnings: tuple[str, ...],
    primary_outcome: ApplyPrimaryOutcome,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
) -> RunReport:
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
        dry_run=dry_run,
        primary_outcome=primary_outcome,
        execution_log=execution_log,
    )


def _complete_mutation_result_bundle(
    mutation_gate: ApplyMutationGate,
    *,
    primary_outcome: ApplyPrimaryOutcome,
    execution_log: bytes | None = None,
    actual_context: RepositoryContext | None = None,
) -> RunReport:
    """Complete one apply result from the single checked mutation gate."""
    return _complete_apply_result_bundle(
        mutation_gate.resolved,
        mutation_gate.package,
        session=mutation_gate.session,
        dry_run=mutation_gate.dry_run,
        warnings=mutation_gate.warnings,
        primary_outcome=primary_outcome,
        execution_log=execution_log,
        actual_context=actual_context,
    )


@contextmanager
def preflight_patch_package_repository(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    session: RunSession | None = None,
    dry_run: bool = True,
    output: OutputTargets | None = None,
    presentation: DashboardPresentation | None = None,
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

        if presentation is not None:
            presentation.update_repository(
                repository_name=str(resolved.repository),
                repository_context=(
                    f"repo_id: {resolved.repo_id} · "
                    f"base: {str(resolved.context.base_commit)[:12]} · "
                    f"state: {resolved.context.state_fingerprint}"
                ),
            )

        if not resolved.matches_manifest_state(manifest):
            error = state_mismatch_error(
                "patch package does not match the resolved repository state"
            )
            report = _complete_apply_result_bundle(
                resolved,
                package,
                session=actual_session,
                dry_run=dry_run,
                warnings=package.warnings,
                primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
            )
            raise report.reported_error()

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
                    dry_run=dry_run,
                    warnings=package.warnings,
                    primary_outcome=ApplyPrimaryOutcome.from_tool_error(error),
                )
                raise report.reported_error() from error

            if output is not None:
                output.write_warnings(prepared_package.warnings)

            if presentation is not None:
                presentation.begin_script(
                    script_name=package.entrypoint.relative_path,
                    script_index=1,
                    script_total=1,
                    messages=tuple(
                        (message.name, message.text)
                        for message in prepared_package.entrypoint.script.messages
                    ),
                    warnings=prepared_package.warnings,
                )

            yield ApplyMutationGate(
                session=actual_session,
                resolved=resolved,
                package=package,
                prepared_package=prepared_package,
                dry_run=dry_run,
            )


def dry_run_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    presentation: DashboardPresentation | None = None,
) -> RunReport:
    """Complete one safe dry-run and publish its unchanged Result Bundle."""
    actual_session = session or RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=actual_session,
        dry_run=True,
        output=output,
        presentation=presentation,
    ) as mutation_gate:
        report = _complete_mutation_result_bundle(
            mutation_gate,
            primary_outcome=ApplyPrimaryOutcome.dry_run_success(),
        )
        if report.process_exit_code != 0:
            raise report.reported_error()
        return report


def _require_payload_mutation(mutation_gate: ApplyMutationGate) -> None:
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
    )

    if execution.patchharbor_error is not None:
        raise report.reported_error()
    if primary_outcome.result.success and report.process_exit_code != 0:
        raise report.reported_error()
    return report


def apply_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    presentation: DashboardPresentation | None = None,
) -> RunReport:
    """Write one validated package, run its private entrypoint, and bundle it."""
    actual_session = session or RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=actual_session,
        dry_run=False,
        output=output,
        presentation=presentation,
    ) as mutation_gate:
        _require_payload_mutation(mutation_gate)
        prepared_package = mutation_gate.prepared_package
        execution = execute_prepared_script_with_log(
            prepared_package.entrypoint.path,
            interpreter=prepared_package.entrypoint.interpreter,
            cwd=mutation_gate.resolved.repository.value,
            timeout_seconds=timeout_seconds,
            execution_log_path=prepared_package.execution_log_path,
            output=output,
        )
        return _complete_entrypoint_execution(mutation_gate, execution)


def run_apply_path(
    path: Path,
    *,
    dry_run: bool,
    output_directory: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
    session: RunSession | None = None,
    presentation: DashboardPresentation | None = None,
) -> RunReport:
    """Run one Apply request through a single public application boundary."""
    actual_session = session or RunSession.start()
    try:
        package = resolve_patch_package(path)
    except PatchHarborError as error:
        return unresolved_apply_report(
            session=actual_session,
            dry_run=dry_run,
            error=error,
        )

    if presentation is not None:
        presentation.begin_request(
            source_name=str(path),
            repository_name="resolving…",
            repository_context=f"repo_id: {package.manifest.repo_id}",
            bundle_files=(
                PresentedFile(
                    name=package.entrypoint.relative_path,
                    size_bytes=len(package.entrypoint.content),
                    kind="entrypoint",
                ),
                *(
                    PresentedFile(
                        name=payload.relative_path,
                        size_bytes=len(payload.content),
                        kind="payload",
                    )
                    for payload in package.payloads
                ),
            ),
            script_total=1,
            warnings=package.warnings,
        )
    if output is not None:
        output.write_warnings(package.warnings)

    try:
        if dry_run:
            return dry_run_patch_package(
                package,
                output_directory=output_directory,
                output=output,
                session=actual_session,
                presentation=presentation,
            )
        return apply_patch_package(
            package,
            output_directory=output_directory,
            timeout_seconds=timeout_seconds,
            output=output,
            session=actual_session,
            presentation=presentation,
        )
    except PatchHarborError as error:
        report = error.run_report
        if isinstance(report, RunReport):
            return report
        return unresolved_apply_report(
            session=actual_session,
            dry_run=dry_run,
            warnings=package.warnings,
            error=error,
        )


def register_repository(
    path: Path,
    *,
    new_id: bool = False,
) -> RepositoryContext:
    """Register one local Git repository and return its current context."""
    repository = require_clean_repository(path)
    _repo_id, repository_path = register_local_repository(
        repository.value,
        new_id=new_id,
    )
    return capture_repository_context(repository_path.value)


def repository_context(path: Path) -> RepositoryContext:
    """Return the current reproducible context of one registered repository."""
    return capture_repository_context(path)


def bundle_repository(
    path: Path,
    *,
    output_directory: Path | None = None,
) -> ManualResultBundle:
    """Create one manual Result Bundle for a registered repository."""
    return create_manual_result_bundle(
        path,
        output_directory=output_directory,
    )


def registered_repositories() -> RegistryListResult:
    """Return one structured view of all registered local instances."""
    return list_registered_repositories()


def unregister_repository(
    selector: str,
    *,
    cwd: Path,
) -> tuple[RepositoryId, RepositoryPath]:
    """Remove one central repository mapping."""
    return unregister_local_repository(selector, cwd=cwd)


def _execute_bundle_script(
    bundle_script: BundleScript,
    *,
    script_index: int,
    script_total: int,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
    presentation: DashboardPresentation | None = None,
) -> int:
    parsed_script = parse_script(bundle_script.text)
    script_warnings = parsed_script.warnings
    if presentation is not None:
        presentation.begin_script(
            script_name=bundle_script.display_name,
            script_index=script_index,
            script_total=script_total,
            messages=tuple(
                (message.name, message.text)
                for message in parsed_script.messages
            ),
            warnings=script_warnings,
        )
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
    presentation: DashboardPresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Resolve and execute every script in one input artifact."""
    bundle = resolve_patch_bundle(artifact, policy=resource_policy)
    if presentation is not None:
        presentation.begin_request(
            source_name=artifact.display_name,
            bundle_files=tuple(
                PresentedFile(
                    name=payload.relative_path,
                    size_bytes=len(payload.content),
                    kind="bundle",
                )
                for payload in bundle.payloads
            ),
            script_total=len(bundle.scripts),
            warnings=bundle.warnings,
        )
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
            presentation=presentation,
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
    presentation: DashboardPresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Own the temporary stdin artifact for exactly one runner request."""
    with stdin_input_artifact(stream, policy=resource_policy) as artifact:
        return run_input_artifact(
            artifact,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
            presentation=presentation,
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
        return True
    except PatchHarborError:
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
    presentation: DashboardPresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    if candidate.path.is_symlink() or not candidate.path.is_file():
        raise PatchHarborError(
            f"selected script is no longer available: {candidate.display_name}",
            ExitCode.SOURCE_ERROR,
        )

    return run_input_artifact(
        file_input_artifact(candidate.path),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
        presentation=presentation,
        resource_policy=resource_policy,
    )


def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    selection_input: TextIO,
    selection_output: TextIO,
    output: OutputTargets | None = None,
    presentation: DashboardPresentation | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> int:
    """Run a script/ZIP file or select one from a directory."""
    if not path.is_dir():
        return run_input_artifact(
            file_input_artifact(path),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
            presentation=presentation,
            resource_policy=resource_policy,
        )

    candidates = discover_directory_candidates(
        path,
        resource_policy=resource_policy,
    )
    if not candidates:
        raise PatchHarborError(
            f"no PatchHarbor scripts found in directory {path}",
            ExitCode.NO_VALID_SCRIPT,
        )
    selected = select_directory_candidate(
        candidates,
        input_stream=selection_input,
        output_stream=selection_output,
    )
    return _run_selected_candidate(
        selected,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        output=output,
        presentation=presentation,
        resource_policy=resource_policy,
    )
