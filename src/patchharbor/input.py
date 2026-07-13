"""Direct file input for PatchHarbor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.execution import ExecutionResult, run_script_file


@dataclass(frozen=True, slots=True)
class InputError:
    """A user-facing failure while loading a script source."""

    message: str


@dataclass(frozen=True, slots=True)
class FileRunResult:
    """Outcome of loading and running one direct script file."""

    execution: ExecutionResult | None = None
    error: InputError | None = None


def run_file(script_path: Path) -> FileRunResult:
    """Load one UTF-8 script file and pass it to execution."""
    try:
        script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return FileRunResult(
            error=InputError(f"cannot read script file {script_path}: {exc}")
        )

    return FileRunResult(execution=run_script_file(script_path))
