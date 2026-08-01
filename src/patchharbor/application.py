"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_text
from patchharbor.models import InputArtifact
from patchharbor.parser import ParsedScript
from patchharbor.payload_files import prepare_payload_files, write_payload_files
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    select_directory_candidate,
)


def _execute_parsed_script(
    script: ParsedScript,
    *,
    suffix: str,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    prepared_payloads, _payload_warnings = prepare_payload_files(
        (payload.name, payload.text) for payload in script.payload_files
    )
    write_payload_files(prepared_payloads, cwd=cwd)
    return execute_script_text(
        script.text,
        suffix=suffix,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )


def run_input_artifact(
    artifact: InputArtifact,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Resolve and execute every script in one input artifact."""
    bundle = resolve_patch_bundle(artifact)
    last_exit_code = 0
    for bundle_script in bundle.scripts:
        last_exit_code = _execute_parsed_script(
            bundle_script.script,
            suffix=bundle_script.suffix,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        if last_exit_code != 0:
            return last_exit_code
    return last_exit_code


def _is_directory_candidate(path: Path) -> bool:
    try:
        resolve_patch_bundle(file_input_artifact(path))
        return True
    except PatchHarborError:
        return False


def discover_directory_candidates(
    directory: Path,
) -> tuple[DirectoryCandidate, ...]:
    """Return sorted regular files that resolve to a PatchBundle."""
    return tuple(
        candidate
        for candidate in list_directory_entries(directory)
        if _is_directory_candidate(candidate.path)
    )


def _run_selected_candidate(
    candidate: DirectoryCandidate,
    *,
    cwd: Path,
    timeout_seconds: float,
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
    )


def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    selection_input: TextIO,
    selection_output: TextIO,
) -> int:
    """Run a script/ZIP file or select one from a directory."""
    if not path.is_dir():
        return run_input_artifact(
            file_input_artifact(path),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )

    candidates = discover_directory_candidates(path)
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
    )
