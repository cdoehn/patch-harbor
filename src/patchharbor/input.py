"""Direct file input for PatchHarbor."""

from __future__ import annotations

from pathlib import Path

from patchharbor.execution import ScriptExecutionTimeout, execute_script_file
from patchharbor.files import temporary_script_file
from patchharbor.parser import ScriptFormatError, validate_required_marker


class ScriptInputError(Exception):
    """The requested script source could not be loaded or validated."""


class ScriptTimeoutError(ScriptInputError):
    """The validated script exceeded its configured timeout."""


def run_script_file(
    script_path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Read, validate, prepare, and execute one UTF-8 script file."""
    try:
        script_text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ScriptInputError(
            f"cannot read script file {script_path}: {exc}"
        ) from exc

    try:
        validate_required_marker(script_text)
    except ScriptFormatError as exc:
        raise ScriptInputError(str(exc)) from exc

    try:
        with temporary_script_file(
            script_text,
            suffix=script_path.suffix,
        ) as temporary_path:
            return execute_script_file(
                temporary_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
    except ScriptExecutionTimeout as exc:
        raise ScriptTimeoutError(str(exc)) from exc
    except OSError as exc:
        raise ScriptInputError(f"cannot prepare temporary script: {exc}") from exc
