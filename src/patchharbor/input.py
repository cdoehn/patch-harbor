"""Direct file input for PatchHarbor."""

from __future__ import annotations

from pathlib import Path

from patchharbor.execution import execute_script_file


class ScriptFileError(Exception):
    """The requested script file could not be read."""


def run_script_file(script_path: Path) -> int:
    """Read one UTF-8 script file and pass it to execution."""
    try:
        script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ScriptFileError(
            f"cannot read script file {script_path}: {exc}"
        ) from exc

    return execute_script_file(script_path)
