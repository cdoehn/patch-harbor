"""Script input and orchestration for PatchHarbor."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_file
from patchharbor.files import temporary_script_file
from patchharbor.parser import ScriptFormatError, validate_required_marker


def _run_script_text(
    script_text: str,
    *,
    suffix: str,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    try:
        validate_required_marker(script_text)
    except ScriptFormatError as exc:
        raise PatchHarborError(
            str(exc),
            ExitCode.NO_VALID_SCRIPT,
        ) from exc

    try:
        with temporary_script_file(script_text, suffix=suffix) as temporary_path:
            return execute_script_file(
                temporary_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


def run_script_file(
    script_path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Read and run one UTF-8 script file."""
    try:
        script_text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script file {script_path}: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    return _run_script_text(
        script_text,
        suffix=script_path.suffix,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )


def run_script_stdin(
    stream: TextIO,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Read standard input once and run it as one script."""
    try:
        script_text = stream.read()
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script from standard input: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    if not script_text:
        raise PatchHarborError(
            "no script input received",
            ExitCode.USAGE_ERROR,
        )

    return _run_script_text(
        script_text,
        suffix=".ps1" if os.name == "nt" else ".sh",
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )
