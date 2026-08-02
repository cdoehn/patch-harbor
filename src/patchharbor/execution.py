"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile
from typing import TextIO

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.interpreters import (
    InterpreterSpec,
    build_interpreter_command,
    resolve_interpreter,
    select_interpreter,
)
from patchharbor.output import ProcessOutputCapture
from patchharbor.platform import ProcessState, create_process_tree


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


def _write_visible_output(
    lines: tuple[str, ...],
    *,
    destination: TextIO,
) -> None:
    for line in lines:
        destination.write(line)
    destination.flush()


def execute_script_text(
    script_text: str,
    *,
    cwd: Path,
    timeout_seconds: float,
    output_stream: TextIO | None = None,
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
                output_stream=output_stream,
            )
    except PatchHarborError:
        raise
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


def _finish_capture_after_process_error(capture: ProcessOutputCapture) -> None:
    """Drain the now-closed process pipe without hiding the primary failure."""
    if not capture.started or capture.finished:
        return
    try:
        capture.finish()
    except OSError:
        pass


def execute_script_file(
    script_path: Path,
    *,
    interpreter: InterpreterSpec,
    executable_path: str,
    cwd: Path,
    timeout_seconds: float,
    output_stream: TextIO | None = None,
) -> int:
    """Run one staged script and show its last five merged output lines."""
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

    capture = ProcessOutputCapture(process_tree.output_stream)

    try:
        with process_tree:
            capture.start()
            result = process_tree.run(timeout_seconds=timeout_seconds)
            capture.finish()
            _write_visible_output(
                capture.visible_lines,
                destination=(
                    sys.stdout if output_stream is None else output_stream
                ),
            )

            if result.state is ProcessState.TIMED_OUT:
                raise PatchHarborError(
                    f"script timed out after {timeout_seconds:g} seconds",
                    ExitCode.TIMEOUT,
                )
            if result.state is ProcessState.INTERRUPTED:
                raise PatchHarborError(
                    "script aborted by user",
                    ExitCode.INTERRUPTED,
                )
            if result.state is not ProcessState.EXITED:
                raise OSError("script process tree returned no terminal result")
            if result.return_code is None:
                raise OSError("script process tree returned no exit code")
            return result.return_code
    except PatchHarborError:
        _finish_capture_after_process_error(capture)
        raise
    except OSError as exc:
        _finish_capture_after_process_error(capture)
        raise PatchHarborError(
            f"cannot control script process tree: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc
