"""Application facade and script-input orchestration.

The public API delegates configuration, discovery, Execute and Result workflows
to their owning modules through this stable facade.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from patchharbor.progress import (
    PackageFile,
    RequestStarted,
    ScriptPrepared,
    activity,
    emit,
)
from patchharbor.bundles import resolve_script_bundle
from patchharbor.configuration import RepositoryConfiguration
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.execution import DEFAULT_TIMEOUT_SECONDS, execute_script_text
from patchharbor.models import BundleScript, InputArtifact
from patchharbor.output import OutputTargets
from patchharbor.task_manifest import TaskManifest
from patchharbor.task_inspection import (
    TaskInspection,
    TaskValidationResult,
    inspect_task as _inspect_task,
    validate_task as _validate_task,
)
from patchharbor.task_package import validate_task_bundle as _validate_task_bundle
from patchharbor.payload_files import write_bundle_payloads
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    stdin_input_artifact,
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
    execute_readiness,
    watch_control_paths,
    watch_targets,
)
from patchharbor.application_execute import (
    execute_task_bundle,
    dry_run_task_bundle,
    preflight_task_bundle_repository,
    resolve_task_bundle,
    run_execute_path,
    run_guarded_execute_path,
)
from patchharbor.application_results import (
    bundle_repository,
)


def validate_task_bundle(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> TaskManifest:
    """Validate one complete patch package through the package boundary."""
    return _validate_task_bundle(path, resource_policy=resource_policy)


def inspect_task(path: Path) -> TaskInspection:
    """Read package facts without entering the Execute lifecycle."""
    return _inspect_task(path)


def validate_task(path: Path, *, repository: Path | None = None,
                   reference_bundle: Path | None = None) -> TaskValidationResult:
    """Validate an explicitly supplied package; no implicit repository selection."""
    return _validate_task(path, repository=repository, reference_bundle=reference_bundle)


def _execute_bundle_script(
    bundle_script: BundleScript,
    *,
    script_index: int,
    script_total: int,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
) -> int:
    parsed_script = bundle_script.parsed
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
    bundle = resolve_script_bundle(artifact, policy=resource_policy)
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
        resolve_script_bundle(
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
    """Return sorted regular files that resolve to a ScriptBundle."""
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
