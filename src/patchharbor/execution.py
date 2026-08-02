"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.interpreters import (
    InterpreterSpec,
    build_interpreter_command,
    resolve_interpreter,
    select_interpreter,
)
from patchharbor.platform import ProcessTreeTimeout, create_process_tree


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
    """Run one staged script through the platform process-tree contract."""
    command = build_interpreter_command(
        interpreter,
        executable_path,
        script_path,
    )

    try:
        process_tree = create_process_tree(command, cwd=cwd)
    except OSError as exc:
        raise PatchHarborError(
            f"cannot start script interpreter: {exc}",
            ExitCode.INTERPRETER_ERROR,
        ) from exc

    try:
        with process_tree:
            try:
                return_code = process_tree.wait(
                    timeout_seconds=timeout_seconds
                )
            except ProcessTreeTimeout as exc:
                process_tree.stop(graceful=True)
                raise PatchHarborError(
                    f"script timed out after {timeout_seconds:g} seconds",
                    ExitCode.TIMEOUT,
                ) from exc
            except KeyboardInterrupt as exc:
                process_tree.stop(graceful=True)
                raise PatchHarborError(
                    "script aborted by user",
                    ExitCode.INTERRUPTED,
                ) from exc

            # The root may exit while descendants remain. The lifecycle owns
            # those processes and removes them before the result is returned.
            process_tree.stop(graceful=False)
            return return_code
    except PatchHarborError:
        raise
    except OSError as exc:
        raise PatchHarborError(
            f"cannot control script process tree: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc
