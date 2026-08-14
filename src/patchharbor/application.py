"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import tempfile
from typing import TextIO

from patchharbor.apply_repository import safely_resolved_repository
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    state_mismatch_error,
)
from patchharbor.execution import execute_script_text
from patchharbor.interpreters import resolve_interpreter, select_interpreter
from patchharbor.models import (
    BundleScript,
    InputArtifact,
    RegistryListResult,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.output import OutputTargets
from patchharbor.parser import ScriptFormatError, parse_script
from patchharbor.patch_manifest import PatchManifest
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_package as _resolve_patch_package,
    validate_patch_package as _validate_patch_package,
)
from patchharbor.payload_files import write_bundle_payloads
from patchharbor.physical_paths import is_physically_within
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


@dataclass(frozen=True, slots=True)
class ApplyPreflightResult:
    """One repository context plus informational entrypoint warnings."""

    context: RepositoryContext
    warnings: tuple[str, ...]


def _preflight_error(message: str, exit_code: ExitCode) -> PatchHarborError:
    return PatchHarborError(message, exit_code)


def _private_resource_path(root: Path, relative_path: str) -> Path:
    return root.joinpath(*relative_path.split("/"))


def _write_private_resource(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor: int | None = None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _verified_private_resource(
    root: Path,
    relative_path: str,
    content: bytes,
    *,
    failure_exit: ExitCode,
) -> Path:
    target = _private_resource_path(root, relative_path)
    expected_size = len(content)
    expected_hash = sha256(content).digest()
    try:
        _write_private_resource(target, content)
        observed = target.read_bytes()
    except OSError as exc:
        raise _preflight_error(
            f"cannot prepare private package resource: {describe_os_error(exc)}",
            failure_exit,
        ) from exc
    if (
        len(observed) != expected_size
        or sha256(observed).digest() != expected_hash
    ):
        raise _preflight_error(
            "private package resource does not match the validated ZIP entry",
            failure_exit,
        )
    return target


@contextmanager
def _prepared_patch_package(
    package: ValidatedPatchPackage,
    *,
    repository: Path,
) -> Iterator[tuple[str, ...]]:
    try:
        system_temp = Path(tempfile.gettempdir()).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _preflight_error(
            f"cannot resolve the private system temporary directory: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc
    if is_physically_within(
        system_temp,
        repository,
        candidate_must_exist=True,
        root_must_exist=True,
    ):
        raise _preflight_error(
            "private apply temporary directory is inside the repository",
            ExitCode.EXECUTION_ERROR,
        )

    try:
        with tempfile.TemporaryDirectory(
            prefix="patchharbor-apply-",
            dir=system_temp,
        ) as raw_directory:
            private_root = Path(raw_directory).resolve(strict=True)
            entrypoint_path = _verified_private_resource(
                private_root / "entrypoint",
                package.entrypoint.relative_path,
                package.entrypoint.content,
                failure_exit=ExitCode.EXECUTION_ERROR,
            )
            try:
                parsed = parse_script(
                    entrypoint_path.read_text(encoding="utf-8")
                )
            except (UnicodeError, ScriptFormatError) as exc:
                raise _preflight_error(
                    "patch package entrypoint is not a valid PatchHarbor script",
                    ExitCode.NO_VALID_SCRIPT,
                ) from exc

            interpreter = select_interpreter(parsed.text)
            resolve_interpreter(interpreter)

            payload_root = private_root / "payloads"
            for payload in package.payloads:
                _verified_private_resource(
                    payload_root,
                    payload.relative_path,
                    payload.content,
                    failure_exit=ExitCode.PAYLOAD_PREPARATION_ERROR,
                )
            yield parsed.warnings
    except PatchHarborError:
        raise
    except OSError as exc:
        raise _preflight_error(
            f"cannot prepare private patch resources: {describe_os_error(exc)}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


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


def preflight_patch_package_repository(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
) -> ApplyPreflightResult:
    """Resolve, lock, compare, and preflight one repository patch package."""
    session = RunSession.start()
    manifest = package.manifest
    with safely_resolved_repository(
        manifest,
        session=session,
        output_directory=output_directory,
    ) as resolved:
        context = resolved.context
        if resolved.matches_manifest_state(manifest):
            with _prepared_patch_package(
                package,
                repository=resolved.repository.value,
            ) as warnings:
                return ApplyPreflightResult(
                    context=context,
                    warnings=warnings,
                )

        report = create_state_mismatch_result_bundle(
            resolved.repository,
            resolved.repo_id,
            resolved.registry_snapshot,
            context,
            manifest,
            target=resolved.result_target,
            publication=resolved.result_publication,
            warnings=package.warnings,
            session=session,
        )
        bundle_result = report.result_bundle
        raise state_mismatch_error(
            "patch package does not match the resolved repository state",
            emergency_diagnostics_path=(
                bundle_result.emergency_diagnostics_path
            ),
            emergency_diagnostics_failed=(
                bundle_result.status is ResultBundleStatus.FAILED
                and bundle_result.emergency_diagnostics_path is None
            ),
            run_report=report,
        )


def validate_patch_package_repository(
    package: ValidatedPatchPackage,
    *,
    output_directory: Path | None = None,
) -> RepositoryContext:
    """Validate one package against its repository and preflight resources."""
    return preflight_patch_package_repository(
        package,
        output_directory=output_directory,
    ).context


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
