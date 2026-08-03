"""Application orchestration for one PatchHarbor runner request."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from patchharbor.bundles import resolve_patch_bundle
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_text
from patchharbor.models import BundleScript, InputArtifact
from patchharbor.parser import parse_script
from patchharbor.payload_files import (
    prepare_payload_files,
    write_bundle_payloads,
    write_payload_files,
)
from patchharbor.sources import (
    DirectoryCandidate,
    file_input_artifact,
    list_directory_entries,
    select_directory_candidate,
    stdin_input_artifact,
)


def _execute_bundle_script(
    bundle_script: BundleScript,
    *,
    cwd: Path,
    timeout_seconds: float,
    output_stream: TextIO | None = None,
    plain_output_stream: TextIO | None = None,
    log_stream: TextIO | None = None,
) -> int:
    parsed_script = parse_script(bundle_script.text)
    prepared_payloads, _payload_warnings = prepare_payload_files(
        (payload.name, payload.text) for payload in parsed_script.payload_files
    )
    write_payload_files(prepared_payloads, cwd=cwd)

    output_options: dict[str, TextIO] = {}
    if output_stream is not None:
        output_options["output_stream"] = output_stream
    if plain_output_stream is not None:
        output_options["plain_output_stream"] = plain_output_stream
    if log_stream is not None:
        output_options["log_stream"] = log_stream

    return execute_script_text(
        parsed_script.text,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        **output_options,
    )


def run_input_artifact(
    artifact: InputArtifact,
    *,
    cwd: Path,
    timeout_seconds: float,
    output_stream: TextIO | None = None,
    plain_output_stream: TextIO | None = None,
    log_stream: TextIO | None = None,
) -> int:
    """Resolve and execute every script in one input artifact."""
    bundle = resolve_patch_bundle(artifact)
    write_bundle_payloads(bundle.payloads, cwd=cwd)
    last_exit_code = 0
    for bundle_script in bundle.scripts:
        last_exit_code = _execute_bundle_script(
            bundle_script,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output_stream=output_stream,
            plain_output_stream=plain_output_stream,
            log_stream=log_stream,
        )
        if last_exit_code != 0:
            return last_exit_code
    return last_exit_code


def run_standard_input(
    stream: TextIO,
    *,
    cwd: Path,
    timeout_seconds: float,
    output_stream: TextIO | None = None,
    plain_output_stream: TextIO | None = None,
    log_stream: TextIO | None = None,
) -> int:
    """Own the temporary stdin artifact for exactly one runner request."""
    with stdin_input_artifact(stream) as artifact:
        return run_input_artifact(
            artifact,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output_stream=output_stream,
            plain_output_stream=plain_output_stream,
            log_stream=log_stream,
        )


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
    output_stream: TextIO | None = None,
    plain_output_stream: TextIO | None = None,
    log_stream: TextIO | None = None,
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
        output_stream=output_stream,
        plain_output_stream=plain_output_stream,
        log_stream=log_stream,
    )


def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    selection_input: TextIO,
    selection_output: TextIO,
    output_stream: TextIO | None = None,
    plain_output_stream: TextIO | None = None,
    log_stream: TextIO | None = None,
) -> int:
    """Run a script/ZIP file or select one from a directory."""
    if not path.is_dir():
        return run_input_artifact(
            file_input_artifact(path),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output_stream=output_stream,
            plain_output_stream=plain_output_stream,
            log_stream=log_stream,
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
        output_stream=output_stream,
        plain_output_stream=plain_output_stream,
        log_stream=log_stream,
    )
