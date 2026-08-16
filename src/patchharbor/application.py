"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
import sys
from typing import TextIO

from patchharbor.apply_preflight import (
    PreparedPatchPackage,
    prepare_patch_package,
)
from patchharbor.apply_repository import (
    SafeResolvedRepository,
    safely_resolved_repository,
)
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    state_mismatch_error,
)
from patchharbor.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    execute_prepared_script,
    execute_script_text,
)
from patchharbor.models import (
    BundlePayload,
    BundleScript,
    InputArtifact,
    RegistryListResult,
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
from patchharbor.payload_files import write_bundle_payloads
from patchharbor.platform.errors import describe_os_error
from patchharbor.presentation import DashboardPresentation, PresentedFile
from patchharbor.registration import (
    list_registered_repositories,
    register_local_repository,
    unregister_local_repository,
)
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
)
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    select_directory_candidate,
    stdin_input_artifact,
)


@dataclass(frozen=True, slots=True)
class ApplyMutationGate:
    """All checked inputs required before the first repository mutation."""

    session: RunSession
    resolved: SafeResolvedRepository
    package: ValidatedPatchPackage
    prepared_package: PreparedPatchPackage

    def __post_init__(self) -> None:
        if not self.resolved.matches_manifest_state(self.package.manifest):
            raise ValueError("mutation gate requires the exact manifest state")

    @property
    def context(self) -> RepositoryContext:
        return self.resolved.context

    @property
    def warnings(self) -> tuple[str, ...]:
        return (*self.package.warnings, *self.prepared_package.warnings)


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
) -> RunReport:
    return create_apply_result_bundle(
        resolved.repository,
        resolved.repo_id,
        resolved.registry_snapshot,
        resolved.context,
        package.manifest,
        target=resolved.result_target,
        publication=resolved.result_publication,
        warnings=warnings,
        session=session,
        dry_run=dry_run,
        primary_outcome=primary_outcome,
        execution_log=execution_log,
    )


@contextmanager
def preflight_patch_package_repository(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    session: RunSession | None = None,
    dry_run: bool = True,
) -> Iterator[ApplyMutationGate]:
    """Yield the explicit mutation gate while private inputs and locks live."""
    actual_session = session or RunSession.start()
    manifest = package.manifest
    with safely_resolved_repository(
        manifest,
        session=actual_session,
        output_directory=output_directory,
    ) as resolved:
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
            raise report.reported_error(error)

        with ExitStack() as private_resources:
            try:
                prepared_package = private_resources.enter_context(
                    prepare_patch_package(
                        package,
                        repository=resolved.repository.value,
                    )
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
                raise report.reported_error(error) from error

            yield ApplyMutationGate(
                session=actual_session,
                resolved=resolved,
                package=package,
                prepared_package=prepared_package,
            )


def dry_run_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
) -> RunReport:
    """Complete one safe dry-run and publish its unchanged Result Bundle."""
    session = RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=session,
        dry_run=True,
    ) as mutation_gate:
        report = _complete_apply_result_bundle(
            mutation_gate.resolved,
            package,
            session=session,
            dry_run=True,
            warnings=mutation_gate.warnings,
            primary_outcome=ApplyPrimaryOutcome.dry_run_success(),
        )
        if report.process_exit_code != 0:
            raise report.reported_error()
        return report


def _prepared_payloads_for_write(
    prepared_package: PreparedPatchPackage,
) -> tuple[BundlePayload, ...]:
    payloads: list[BundlePayload] = []
    for prepared in prepared_package.payloads:
        try:
            content = prepared.path.read_bytes()
        except OSError as exc:
            raise PatchHarborError(
                "cannot read prepared patch payload: "
                f"{describe_os_error(exc)}",
                ExitCode.PAYLOAD_PREPARATION_ERROR,
            ) from exc
        if (
            len(content) != prepared.size_bytes
            or sha256(content).hexdigest() != prepared.sha256_hex
        ):
            raise PatchHarborError(
                "prepared patch payload changed before repository writing",
                ExitCode.PAYLOAD_PREPARATION_ERROR,
            )
        payloads.append(
            BundlePayload(
                relative_path=prepared.relative_path,
                content=content,
            )
        )
    return tuple(payloads)


def apply_patch_package(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output: OutputTargets | None = None,
) -> RunReport:
    """Write one validated package, run its private entrypoint, and bundle it."""
    session = RunSession.start()
    with preflight_patch_package_repository(
        package,
        output_directory=output_directory,
        session=session,
        dry_run=False,
    ) as mutation_gate:
        prepared_package = mutation_gate.prepared_package
        write_bundle_payloads(
            _prepared_payloads_for_write(prepared_package),
            cwd=mutation_gate.resolved.repository.value,
        )

        actual_output = output or OutputTargets(visible_text_stream=sys.stdout)
        try:
            with prepared_package.execution_log_path.open("w+b") as execution_log:
                exit_code = execute_prepared_script(
                    prepared_package.entrypoint.path,
                    interpreter=prepared_package.entrypoint.interpreter,
                    cwd=mutation_gate.resolved.repository.value,
                    timeout_seconds=timeout_seconds,
                    output=replace(
                        actual_output,
                        raw_output_stream=execution_log,
                    ),
                )
                execution_log.flush()
                execution_log.seek(0)
                execution_log_bytes = execution_log.read()
        except PatchHarborError:
            raise
        except OSError as exc:
            raise PatchHarborError(
                "cannot capture entrypoint output: "
                f"{describe_os_error(exc)}",
                ExitCode.EXECUTION_ERROR,
            ) from exc

        if exit_code != 0:
            raise PatchHarborError(
                f"entrypoint exited with code {exit_code}",
                ExitCode.EXECUTION_ERROR,
            )

        report = _complete_apply_result_bundle(
            mutation_gate.resolved,
            package,
            session=session,
            dry_run=False,
            warnings=mutation_gate.warnings,
            primary_outcome=ApplyPrimaryOutcome.entrypoint_success(),
            execution_log=execution_log_bytes,
        )
        if report.process_exit_code != 0:
            raise report.reported_error()
        return report


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
