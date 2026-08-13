"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from dataclasses import dataclass
from io import DEFAULT_BUFFER_SIZE
from pathlib import Path
import stat
from typing import TextIO
import zipfile

from patchharbor.bundle_paths import (
    BundlePathError,
    normalize_bundle_path,
    validate_bundle_member_paths,
)
from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    patch_package_error,
)
from patchharbor.execution import execute_script_text
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
from patchharbor.patch_manifest import (
    PATCH_MANIFEST_NAME,
    PatchManifest,
    parse_patch_manifest,
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
from patchharbor.result_bundle import ManualResultBundle, create_manual_result_bundle
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    select_directory_candidate,
    stdin_input_artifact,
)


def _patch_source_error(path: Path, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"cannot read patch package {path}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


def _unsafe_patch_zip(path: Path, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"unsafe or unreadable patch ZIP {path}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


@dataclass(frozen=True, slots=True)
class ValidatedPatchPackage:
    """One fully read and classified format-1 patch package."""

    manifest: PatchManifest
    entrypoint: BundlePayload
    payloads: tuple[BundlePayload, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ValidatedPatchMember:
    entry: zipfile.ZipInfo
    relative_path: str
    is_directory: bool


@dataclass(slots=True)
class _PatchZipReadBudget:
    package_path: Path
    resource_policy: ResourcePolicy
    total_bytes_read: int = 0

    def validate_declared_entries(
        self,
        entries: list[zipfile.ZipInfo],
    ) -> None:
        if len(entries) > self.resource_policy.max_zip_entries:
            raise _unsafe_patch_zip(
                self.package_path,
                "ZIP entry count exceeds the resource limit",
            )

        declared_total = 0
        for entry in entries:
            if entry.file_size > self.resource_policy.max_content_bytes:
                raise _unsafe_patch_zip(
                    self.package_path,
                    f"ZIP entry {entry.orig_filename!r} exceeds "
                    "the content size limit",
                )
            declared_total += entry.file_size
            if declared_total > self.resource_policy.max_zip_total_bytes:
                raise _unsafe_patch_zip(
                    self.package_path,
                    "ZIP uncompressed data exceeds the total size limit",
                )

    def read_member(
        self,
        archive: zipfile.ZipFile,
        member: _ValidatedPatchMember,
    ) -> bytes:
        chunks: list[bytes] = []
        entry_bytes_read = 0
        try:
            with archive.open(member.entry, "r") as stream:
                while chunk := stream.read(DEFAULT_BUFFER_SIZE):
                    entry_bytes_read += len(chunk)
                    self.total_bytes_read += len(chunk)
                    if (
                        entry_bytes_read
                        > self.resource_policy.max_content_bytes
                    ):
                        raise _unsafe_patch_zip(
                            self.package_path,
                            f"ZIP entry {member.relative_path!r} exceeds "
                            "the content size limit while reading",
                        )
                    if (
                        self.total_bytes_read
                        > self.resource_policy.max_zip_total_bytes
                    ):
                        raise _unsafe_patch_zip(
                            self.package_path,
                            "ZIP uncompressed data exceeds the total size "
                            "limit while reading",
                        )
                    chunks.append(chunk)
        except PatchHarborError:
            raise
        except (
            NotImplementedError,
            OSError,
            RuntimeError,
            zipfile.BadZipFile,
        ) as exc:
            raise _unsafe_patch_zip(
                self.package_path,
                f"cannot read ZIP entry {member.relative_path!r}: {exc}",
            ) from exc

        if entry_bytes_read != member.entry.file_size:
            raise _unsafe_patch_zip(
                self.package_path,
                f"ZIP entry {member.relative_path!r} size changed while "
                "reading",
            )
        return b"".join(chunks)


def _patch_member_is_directory(
    entry: zipfile.ZipInfo,
    *,
    package_path: Path,
) -> bool:
    if entry.create_system != 3:
        if entry.is_dir() and entry.file_size != 0:
            raise _unsafe_patch_zip(
                package_path,
                f"directory ZIP entry {entry.orig_filename!r} has content",
            )
        return entry.is_dir()

    file_type = stat.S_IFMT(entry.external_attr >> 16)
    if entry.is_dir():
        if entry.file_size != 0:
            raise _unsafe_patch_zip(
                package_path,
                f"directory ZIP entry {entry.orig_filename!r} has content",
            )
        if file_type not in (0, stat.S_IFDIR):
            raise _unsafe_patch_zip(
                package_path,
                f"unsupported ZIP entry type for {entry.orig_filename!r}",
            )
        return True

    if file_type not in (0, stat.S_IFREG):
        raise _unsafe_patch_zip(
            package_path,
            f"unsupported ZIP entry type for {entry.orig_filename!r}",
        )
    return False


def _validate_patch_members(
    entries: list[zipfile.ZipInfo],
    *,
    package_path: Path,
) -> tuple[_ValidatedPatchMember, ...]:
    member_kinds = tuple(
        (
            entry,
            _patch_member_is_directory(entry, package_path=package_path),
        )
        for entry in entries
    )
    try:
        relative_paths = validate_bundle_member_paths(
            (entry.orig_filename, is_directory)
            for entry, is_directory in member_kinds
        )
    except BundlePathError as exc:
        raise _unsafe_patch_zip(package_path, exc) from exc

    return tuple(
        _ValidatedPatchMember(
            entry=entry,
            relative_path=relative_path,
            is_directory=is_directory,
        )
        for (entry, is_directory), relative_path in zip(
            member_kinds,
            relative_paths,
            strict=True,
        )
    )


def _read_and_classify_patch_package(
    archive: zipfile.ZipFile,
    *,
    package_path: Path,
    resource_policy: ResourcePolicy,
) -> ValidatedPatchPackage:
    entries = archive.infolist()
    budget = _PatchZipReadBudget(package_path, resource_policy)
    budget.validate_declared_entries(entries)
    members = _validate_patch_members(entries, package_path=package_path)

    manifest_members = tuple(
        member
        for member in members
        if not member.is_directory
        and member.relative_path == PATCH_MANIFEST_NAME
    )
    if len(manifest_members) != 1:
        raise patch_package_error(
            "patch package must contain exactly one regular root patch.json"
        )

    contents: dict[str, bytes] = {}
    for member in members:
        if member.is_directory:
            continue
        contents[member.relative_path] = budget.read_member(archive, member)

    manifest = parse_patch_manifest(contents[PATCH_MANIFEST_NAME])
    try:
        entrypoint_path = normalize_bundle_path(manifest.entrypoint)
    except BundlePathError as exc:
        raise _unsafe_patch_zip(package_path, exc) from exc

    entrypoint_members = tuple(
        member
        for member in members
        if not member.is_directory
        and member.relative_path == entrypoint_path
    )
    if len(entrypoint_members) != 1:
        raise patch_package_error(
            "patch.json entrypoint must reference exactly one regular ZIP entry"
        )

    entrypoint = BundlePayload(
        relative_path=entrypoint_path,
        content=contents[entrypoint_path],
    )
    payloads = tuple(
        BundlePayload(
            relative_path=member.relative_path,
            content=contents[member.relative_path],
        )
        for member in members
        if not member.is_directory
        and member.relative_path not in {
            PATCH_MANIFEST_NAME,
            entrypoint_path,
        }
    )

    warnings = tuple(
        warning
        for item in (entrypoint, *payloads)
        if (
            warning := resource_policy.large_content_warning(
                f"ZIP entry {item.relative_path!r}",
                len(item.content),
            )
        )
        is not None
    )
    return ValidatedPatchPackage(
        manifest=manifest,
        entrypoint=entrypoint,
        payloads=payloads,
        warnings=warnings,
    )


def resolve_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ValidatedPatchPackage:
    """Read, validate, and classify one format-1 patch package."""
    try:
        metadata = path.stat()
    except OSError as exc:
        raise _patch_source_error(path, describe_os_error(exc)) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise _patch_source_error(path, "not a regular file")
    if metadata.st_size > resource_policy.max_input_artifact_bytes:
        raise _patch_source_error(path, "input artifact exceeds the size limit")

    try:
        if not zipfile.is_zipfile(path):
            raise patch_package_error("patch package is not a ZIP archive")
        with zipfile.ZipFile(path, "r") as archive:
            return _read_and_classify_patch_package(
                archive,
                package_path=path,
                resource_policy=resource_policy,
            )
    except PatchHarborError:
        raise
    except (
        NotImplementedError,
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise _unsafe_patch_zip(path, exc) from exc


def validate_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> PatchManifest:
    """Validate one complete package and return its typed manifest."""
    return resolve_patch_package(
        path,
        resource_policy=resource_policy,
    ).manifest


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
