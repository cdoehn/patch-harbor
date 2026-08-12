"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

import json
from pathlib import Path
import stat
from typing import TextIO
import zipfile

from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_text
from patchharbor.models import (
    BundleScript,
    InputArtifact,
    GitObjectFormat,
    GitObjectId,
    RegistryListResult,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.output import OutputTargets
from patchharbor.parser import parse_script
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
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    select_directory_candidate,
    stdin_input_artifact,
)


_PATCH_MANIFEST_NAME = "patch.json"
_PATCH_MARKER = "patch-harbor"
_PATCH_FORMAT_VERSION = 1
_PATCH_MANIFEST_FIELDS = frozenset(
    {
        "marker",
        "format_version",
        "repo_id",
        "base_commit",
        "state_fingerprint",
        "fingerprint_algorithm",
        "entrypoint",
    }
)


def _patch_package_error(message: str) -> PatchHarborError:
    return PatchHarborError(message, ExitCode.PATCH_PACKAGE_ERROR)


def _patch_source_error(path: Path, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"cannot read patch package {path}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


def _regular_zip_file(entry: zipfile.ZipInfo) -> bool:
    if entry.is_dir():
        return False
    if entry.create_system != 3:
        return True
    file_type = stat.S_IFMT(entry.external_attr >> 16)
    return file_type in (0, stat.S_IFREG)


def _unique_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite_number(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def _read_patch_manifest(
    archive: zipfile.ZipFile,
    *,
    package_path: Path,
    resource_policy: ResourcePolicy,
) -> bytes:
    matching = [
        entry
        for entry in archive.infolist()
        if entry.orig_filename == _PATCH_MANIFEST_NAME
    ]
    if len(matching) != 1 or not _regular_zip_file(matching[0]):
        raise _patch_package_error(
            "patch package must contain exactly one regular root patch.json"
        )

    entry = matching[0]
    if entry.file_size > resource_policy.max_content_bytes:
        raise _patch_package_error("patch.json exceeds the content size limit")
    try:
        with archive.open(entry, "r") as stream:
            payload = stream.read(resource_policy.max_content_bytes + 1)
    except (
        NotImplementedError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
    ) as exc:
        raise _patch_package_error(
            f"cannot read patch.json from {package_path}: {exc}"
        ) from exc
    if len(payload) > resource_policy.max_content_bytes:
        raise _patch_package_error("patch.json exceeds the content size limit")
    return payload


def _parse_patch_manifest(payload: bytes) -> dict[str, object]:
    if payload.startswith(b"\xef\xbb\xbf"):
        raise _patch_package_error("patch.json must be UTF-8 without a BOM")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _patch_package_error("patch.json is not valid UTF-8") from exc

    try:
        document = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_non_finite_number,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise _patch_package_error("patch.json is not one valid JSON object") from exc

    if type(document) is not dict:
        raise _patch_package_error("patch.json must contain one JSON object")
    if set(document) != _PATCH_MANIFEST_FIELDS:
        raise _patch_package_error(
            "patch.json must contain exactly the seven format-1 fields"
        )

    marker = document["marker"]
    if type(marker) is not str or marker != _PATCH_MARKER:
        raise _patch_package_error("patch.json marker is invalid")

    format_version = document["format_version"]
    if type(format_version) is not int or format_version != _PATCH_FORMAT_VERSION:
        raise _patch_package_error("patch.json format_version is invalid")

    repo_id = document["repo_id"]
    if type(repo_id) is not str:
        raise _patch_package_error("patch.json repo_id is invalid")
    try:
        RepositoryId(repo_id)
    except ValueError as exc:
        raise _patch_package_error("patch.json repo_id is invalid") from exc

    base_commit = document["base_commit"]
    if type(base_commit) is not str:
        raise _patch_package_error("patch.json base_commit is invalid")
    try:
        object_format = GitObjectFormat.for_hex_length(len(base_commit))
        GitObjectId(base_commit, object_format)
    except ValueError as exc:
        raise _patch_package_error("patch.json base_commit is invalid") from exc

    fingerprint = document["state_fingerprint"]
    if (
        type(fingerprint) is not str
        or len(fingerprint) != 16
        or fingerprint != fingerprint.lower()
        or any(character not in "0123456789abcdef" for character in fingerprint)
    ):
        raise _patch_package_error("patch.json state_fingerprint is invalid")

    algorithm = document["fingerprint_algorithm"]
    if type(algorithm) is not str or algorithm != FINGERPRINT_ALGORITHM:
        raise _patch_package_error("patch.json fingerprint_algorithm is invalid")

    entrypoint = document["entrypoint"]
    if (
        type(entrypoint) is not str
        or not entrypoint
        or entrypoint == _PATCH_MANIFEST_NAME
    ):
        raise _patch_package_error("patch.json entrypoint is invalid")

    return document


def validate_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> dict[str, object]:
    """Validate one format-1 patch package without mutating a repository."""
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
            raise _patch_package_error("patch package is not a ZIP archive")
        with zipfile.ZipFile(path, "r") as archive:
            manifest_payload = _read_patch_manifest(
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
        zipfile.BadZipFile,
    ) as exc:
        raise _patch_package_error(
            f"patch package is not readable: {exc}"
        ) from exc

    return _parse_patch_manifest(manifest_payload)


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
