"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sys

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.interpreters import (
    InterpreterSpec,
    build_interpreter_command,
    resolve_script_interpreter,
)
from patchharbor.output import OutputTargets, ProcessOutputCapture
from patchharbor.platform import ProcessState, create_process_tree
from patchharbor.platform.errors import describe_os_error
from patchharbor.temporary_resources import (
    private_request_directory,
    write_private_bytes,
)


DEFAULT_TIMEOUT_SECONDS = 300.0


@contextmanager
def _temporary_script_file(script_text: str, *, suffix: str) -> Iterator[Path]:
    """Write one script inside the shared private request lifecycle."""
    with private_request_directory(prefix="patchharbor-script-") as directory:
        script_path = directory / f"script{suffix}"
        write_private_bytes(script_path, script_text.encode("utf-8"))
        yield script_path


def execute_script_text(
    script_text: str,
    *,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
) -> int:
    """Stage and execute script text with a supported interpreter."""
    resolved = resolve_script_interpreter(script_text)

    try:
        with _temporary_script_file(
            script_text,
            suffix=resolved.spec.script_suffix,
        ) as script_path:
            return _execute_staged_script(
                script_path,
                interpreter=resolved.spec,
                executable_path=resolved.executable_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                output=output,
            )
    except PatchHarborError:
        raise
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {describe_os_error(exc)}",
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


def _execute_staged_script(
    script_path: Path,
    *,
    interpreter: InterpreterSpec,
    executable_path: str,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
) -> int:
    """Run one staged script through the configured output targets."""
    command = build_interpreter_command(
        interpreter,
        executable_path,
        script_path,
    )

    try:
        process_tree = create_process_tree(command, cwd=cwd)
    except OSError as exc:
        raise PatchHarborError(
            f"cannot start script interpreter: {describe_os_error(exc)}",
            ExitCode.INTERPRETER_ERROR,
        ) from exc

    targets = output or OutputTargets(visible_text_stream=sys.stdout)
    capture = ProcessOutputCapture(
        process_tree.output_stream,
        live_text_stream=targets.live_text_stream,
        raw_output_stream=targets.raw_output_stream,
        line_observer=targets.line_observer,
    )

    try:
        with process_tree:
            capture.start()
            result = process_tree.run(timeout_seconds=timeout_seconds)
            capture.finish()
            targets.write_visible_lines(capture.visible_lines)

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
            f"cannot control script process tree: {describe_os_error(exc)}",
            ExitCode.EXECUTION_ERROR,
        ) from exc
