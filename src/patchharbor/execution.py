"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import tempfile

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.interpreters import (
    InterpreterSpec,
    build_interpreter_command,
    resolve_interpreter,
    select_interpreter,
)


DEFAULT_TIMEOUT_SECONDS = 300.0


@contextmanager
def _temporary_script_file(script_text: str, *, suffix: str) -> Iterator[Path]:
    """Write script text to a secure system-temp file and remove it afterwards."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-",
        suffix=suffix,
        text=True,
    )
    script_path = Path(raw_path)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(script_text)
        yield script_path
    finally:
        script_path.unlink(missing_ok=True)


def execute_script_text(
    script_text: str,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Stage and execute script text with a supported interpreter."""
    selected = select_interpreter(script_text)
    executable_path = resolve_interpreter(selected)

    try:
        with _temporary_script_file(
            script_text,
            suffix=selected.script_suffix,
        ) as script_path:
            return execute_script_file(
                script_path,
                interpreter=selected,
                executable_path=executable_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


def execute_script_file(
    script_path: Path,
    *,
    interpreter: InterpreterSpec,
    executable_path: str,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Run one staged script with an already resolved interpreter."""
    command = build_interpreter_command(
        interpreter,
        executable_path,
        script_path,
    )

    try:
        completed = subprocess.run(
            command,
            check=False,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise PatchHarborError(
            f"script timed out after {timeout_seconds:g} seconds",
            ExitCode.TIMEOUT,
        ) from exc
    except OSError as exc:
        raise PatchHarborError(
            f"cannot start script interpreter: {exc}",
            ExitCode.INTERPRETER_ERROR,
        ) from exc

    return completed.returncode
