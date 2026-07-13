"""Direct file input for PatchHarbor."""

from __future__ import annotations

from pathlib import Path

from patchharbor.execution import execute_script_file
from patchharbor.script_format import REQUIRED_MARKER, has_required_marker


class ScriptFileError(Exception):
    """The requested script file could not be loaded or validated."""


def run_script_file(script_path: Path) -> int:
    """Read and validate one UTF-8 script file, then pass it to execution."""
    try:
        script_text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ScriptFileError(
            f"cannot read script file {script_path}: {exc}"
        ) from exc

    if not has_required_marker(script_text):
        raise ScriptFileError(f"missing required marker line: {REQUIRED_MARKER}")

    return execute_script_file(script_path)
