"""Script input and orchestration for PatchHarbor."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import TextIO

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_file
from patchharbor.files import temporary_script_file
from patchharbor.parser import ScriptFormatError, validate_required_marker



@dataclass(frozen=True)
class ScriptSource:
    """Neutral script input handed to the parsing and execution pipeline."""

    text: str
    suffix: str


def read_script_file(script_path: Path) -> ScriptSource:
    """Read one UTF-8 script file into a neutral source value."""
    try:
        script_text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script source {script_path}: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    return ScriptSource(
        text=script_text,
        suffix=script_path.suffix,
    )


def read_script_stdin(stream: TextIO) -> ScriptSource:
    """Read standard input once into a neutral source value."""
    try:
        script_text = stream.read()
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script source standard input: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    if not script_text:
        raise PatchHarborError(
            "no script input received",
            ExitCode.USAGE_ERROR,
        )

    return ScriptSource(
        text=script_text,
        suffix=".ps1" if os.name == "nt" else ".sh",
    )


def run_script_source(
    source: ScriptSource,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Validate and run one neutral script source."""
    try:
        validate_required_marker(source.text)
    except ScriptFormatError as exc:
        raise PatchHarborError(
            str(exc),
            ExitCode.NO_VALID_SCRIPT,
        ) from exc

    try:
        with temporary_script_file(source.text, suffix=source.suffix) as temporary_path:
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
