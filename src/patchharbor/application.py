"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import TextIO

from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    repository_resolution_error,
    state_mismatch_error,
)
from patchharbor.execution import execute_script_text
from patchharbor.models import (
    BundleScript,
    InputArtifact,
    RegistryListResult,
    RegistrySnapshot,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.locks import registry_lock, repository_lock
from patchharbor.output import OutputTargets
from patchharbor.parser import parse_script
from patchharbor.patch_manifest import PatchManifest
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_package as _resolve_patch_package,
    validate_patch_package as _validate_patch_package,
)
from patchharbor.payload_files import write_bundle_payloads
from patchharbor.presentation import DashboardPresentation, PresentedFile
from patchharbor.registration import (
    list_registered_repositories,
    register_local_repository,
    unregister_local_repository,
)
from patchharbor.registry import load_registry
from patchharbor.repository import (
    inspect_repository,
    require_local_repository_identity,
)
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    capture_repository_context,
    repository_context_from_snapshot,
    require_clean_repository,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.result_bundle import (
    ManualResultBundle,
    create_manual_result_bundle,
    create_state_mismatch_result_bundle,
)
from patchharbor.run_report import ResultBundleStatus, RunSession
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    select_directory_candidate,
    stdin_input_artifact,
)
from patchharbor.user_paths import registration_user_paths


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


def _repository_path_for_id(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RepositoryPath:
    id_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repo_id == repo_id
    )
    if len(id_matches) != 1:
        raise repository_resolution_error("repository ID is not registered")
    selected = id_matches[0]
    path_matches = tuple(
        mapping
        for mapping in snapshot.repositories
        if mapping.repository_path == selected.repository_path
    )
    if len(path_matches) != 1 or path_matches[0].repo_id != repo_id:
        raise repository_resolution_error(
            "repository path has conflicting registrations"
        )
    return selected.repository_path


def _inspect_registered_repository(
    snapshot: RegistrySnapshot,
    repo_id: RepositoryId,
) -> RepositoryPath:
    expected_path = _repository_path_for_id(snapshot, repo_id)
    repository = inspect_repository(expected_path.value)
    if repository != expected_path:
        raise repository_resolution_error(
            "registered repository path no longer identifies the same repository"
        )
    require_local_repository_identity(repository, repo_id)
    return repository


@contextmanager
def _locked_apply_repository(
    repo_id: RepositoryId,
) -> Iterator[tuple[RepositoryPath, RegistrySnapshot]]:
    paths = registration_user_paths()
    with ExitStack() as repository_scope:
        with registry_lock(paths):
            initial_snapshot = load_registry(paths)
            repository = _inspect_registered_repository(
                initial_snapshot,
                repo_id,
            )
            repository_scope.enter_context(repository_lock(paths, repo_id))

            locked_snapshot = load_registry(paths)
            locked_repository = _inspect_registered_repository(
                locked_snapshot,
                repo_id,
            )
            if locked_repository != repository:
                raise repository_resolution_error(
                    "repository path changed while acquiring its lock"
                )

        yield locked_repository, locked_snapshot


def _manifest_state_mismatch(
    manifest: PatchManifest,
    context: RepositoryContext,
) -> str | None:
    if (
        manifest.base_commit.object_format
        is not context.base_commit.object_format
    ):
        return "patch package base commit uses a different Git object format"
    if manifest.base_commit != context.base_commit:
        return "patch package base commit does not match repository HEAD"
    if manifest.fingerprint_algorithm != context.fingerprint_algorithm:
        return "patch package fingerprint algorithm does not match repository context"
    if manifest.state_fingerprint != context.state_fingerprint:
        return "patch package fingerprint does not match repository state"
    return None


def validate_patch_package_repository(
    package: ValidatedPatchPackage,
) -> RepositoryContext:
    """Resolve, lock, and compare the repository named by one patch package."""
    session = RunSession.start()
    manifest = package.manifest
    with _locked_apply_repository(manifest.repo_id) as (
        repository,
        registry_snapshot,
    ):
        snapshot = capture_consistent_repository_snapshot(repository)
        context = repository_context_from_snapshot(
            repository,
            manifest.repo_id,
            snapshot,
        )
        mismatch = _manifest_state_mismatch(manifest, context)
        if mismatch is None:
            return context

        report = create_state_mismatch_result_bundle(
            repository,
            manifest.repo_id,
            registry_snapshot,
            context,
            manifest,
            warnings=package.warnings,
            session=session,
        )
        bundle_result = report.result_bundle
        raise state_mismatch_error(
            mismatch,
            emergency_diagnostics_path=(
                bundle_result.emergency_diagnostics_path
            ),
            emergency_diagnostics_failed=(
                bundle_result.status is ResultBundleStatus.FAILED
                and bundle_result.emergency_diagnostics_path is None
            ),
            run_report=report,
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
