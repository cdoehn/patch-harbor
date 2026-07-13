"""Direct file input for PatchHarbor."""

from __future__ import annotations

from pathlib import Path

from patchharbor.execution import execute_script_file
from patchharbor.parser import ScriptFormatError, validate_required_marker


class ScriptInputError(Exception):
    """The requested script source could not be loaded or validated."""


def run_script_file(script_path: Path) -> int:
    """Read and validate one UTF-8 script file, then pass it to execution."""
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

    return execute_script_file(script_path)
