"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import sys
from typing import BinaryIO

from patchharbor.progress import activity

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.interpreters import (
    InterpreterSpec,
    ResolvedInterpreter,
    build_interpreter_command,
    encode_script_file,
    resolve_script_interpreter,
)
from patchharbor.output import OutputTargets, ProcessOutputCapture
from patchharbor.platform import ProcessState, create_process_tree
from patchharbor.platform.errors import describe_os_error
from patchharbor.temporary_resources import (
    private_request_directory,
    write_private_bytes,
)


DEFAULT_TIMEOUT_SECONDS = 10_800.0


@contextmanager
def _temporary_script_file(script_content: bytes, *, suffix: str) -> Iterator[Path]:
    """Write one script inside the shared private request lifecycle."""
    with private_request_directory(prefix="patchharbor-script-") as directory:
        script_path = directory / f"script{suffix}"
        write_private_bytes(script_path, script_content)
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
            encode_script_file(script_text, resolved.spec),
            suffix=resolved.spec.script_suffix,
        ) as script_path:
            result = _run_staged_script(
                script_path,
                interpreter=resolved.spec,
                executable_path=resolved.executable_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                output=output,
            )
            return result.exit_code_or_raise()
    except PatchHarborError:
        raise
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {describe_os_error(exc)}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


@dataclass(frozen=True, slots=True)
class ScriptExecutionResult:
    """One fully cleaned-up script execution and its byte-exact output."""

    entrypoint_started: bool
    entrypoint_exit_code: int | None
    patchharbor_error: PatchHarborError | None
    output: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.entrypoint_started, bool):
            raise ValueError("entrypoint-started flag must be boolean")
        if self.entrypoint_exit_code is not None and (
            isinstance(self.entrypoint_exit_code, bool)
            or not isinstance(self.entrypoint_exit_code, int)
        ):
            raise ValueError("entrypoint exit code must be an integer")
        if (self.entrypoint_exit_code is None) == (self.patchharbor_error is None):
            raise ValueError(
                "script execution requires either an exit code or a PatchHarbor error"
            )
        if self.entrypoint_exit_code is not None and not self.entrypoint_started:
            raise ValueError("an exited entrypoint must have started")
        if self.patchharbor_error is not None:
            if not isinstance(self.patchharbor_error, PatchHarborError):
                raise ValueError("script execution error must be a PatchHarbor error")
            if self.patchharbor_error.exit_code in {
                ExitCode.TIMEOUT,
                ExitCode.INTERRUPTED,
            } and not self.entrypoint_started:
                raise ValueError("timeout and interruption require a started entrypoint")
        object.__setattr__(self, "output", bytes(self.output))

    @classmethod
    def exited(cls, exit_code: int, output: bytes) -> ScriptExecutionResult:
        return cls(
            entrypoint_started=True,
            entrypoint_exit_code=exit_code,
            patchharbor_error=None,
            output=output,
        )

    @classmethod
    def failed(
        cls,
        error: PatchHarborError,
        *,
        entrypoint_started: bool,
        output: bytes,
    ) -> ScriptExecutionResult:
        return cls(
            entrypoint_started=entrypoint_started,
            entrypoint_exit_code=None,
            patchharbor_error=error,
            output=output,
        )

    def with_output(self, output: bytes) -> ScriptExecutionResult:
        return replace(self, output=output)

    def with_cleanup_error(
        self,
        error: PatchHarborError,
    ) -> ScriptExecutionResult:
        """Keep interruption, timeout, exit, or an earlier tool failure first."""
        if self.patchharbor_error is not None:
            return self
        if self.entrypoint_exit_code not in (None, 0):
            return self
        return ScriptExecutionResult.failed(
            error,
            entrypoint_started=self.entrypoint_started,
            output=self.output,
        )

    def exit_code_or_raise(self) -> int:
        """Expose the legacy manual-runner contract from the shared outcome."""
        if self.patchharbor_error is not None:
            raise self.patchharbor_error
        if self.entrypoint_exit_code is None:
            raise RuntimeError("completed script execution has no exit code")
        return self.entrypoint_exit_code


def _read_execution_log(execution_log: BinaryIO) -> bytes:
    """Read one binary execution log after the process lifecycle has ended."""
    execution_log.flush()
    execution_log.seek(0)
    return bytes(execution_log.read())


def _execution_log_error(exc: OSError) -> PatchHarborError:
    return PatchHarborError(
        "cannot capture script output: "
        f"{describe_os_error(exc)}",
        ExitCode.EXECUTION_ERROR,
    )


def execute_prepared_script_with_log(
    script_path: Path,
    *,
    interpreter: ResolvedInterpreter,
    cwd: Path,
    timeout_seconds: float,
    execution_log_path: Path,
    output: OutputTargets | None = None,
) -> ScriptExecutionResult:
    """Run one private script through the shared process lifecycle and log it."""
    targets = output or OutputTargets(visible_text_stream=sys.stdout)
    try:
        execution_log = execution_log_path.open("w+b")
    except OSError as exc:
        return ScriptExecutionResult.failed(
            _execution_log_error(exc),
            output=b"",
            entrypoint_started=False,
        )

    result: ScriptExecutionResult | None = None
    try:
        result = _run_staged_script(
            script_path,
            interpreter=interpreter.spec,
            executable_path=interpreter.executable_path,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=replace(
                targets,
                raw_output_stream=execution_log,
            ),
        )

        try:
            result = result.with_output(_read_execution_log(execution_log))
        except OSError as exc:
            result = result.with_cleanup_error(_execution_log_error(exc))
    finally:
        try:
            execution_log.close()
        except OSError as exc:
            cleanup_error = _execution_log_error(exc)
            if result is None:
                result = ScriptExecutionResult.failed(
                    cleanup_error,
                    output=b"",
                    entrypoint_started=False,
                )
            else:
                result = result.with_cleanup_error(cleanup_error)

    if result is None:
        raise RuntimeError("script execution produced no result")
    return result


def _finish_capture_after_process_error(capture: ProcessOutputCapture) -> None:
    """Drain the now-closed process pipe without hiding the primary failure."""
    if not capture.started or capture.finished:
        return
    try:
        capture.finish()
    except OSError:
        pass


def _run_staged_script(
    script_path: Path,
    *,
    interpreter: InterpreterSpec,
    executable_path: str,
    cwd: Path,
    timeout_seconds: float,
    output: OutputTargets | None = None,
) -> ScriptExecutionResult:
    """Return one shared outcome for manual and repository-bound execution."""
    try:
        exit_code = _control_process(
            script_path,
            interpreter=interpreter,
            executable_path=executable_path,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            output=output,
        )
    except PatchHarborError as error:
        return ScriptExecutionResult.failed(
            error,
            entrypoint_started=(
                error.exit_code is not ExitCode.INTERPRETER_ERROR
            ),
            output=b"",
        )
    return ScriptExecutionResult.exited(exit_code, b"")


def _control_process(
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

    activity("EXEC", f"Start {executable_path} in {cwd}; timeout={timeout_seconds:g}s", "heading")
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
            activity("EXEC", "Interpreter started; drain complete merged stdout/stderr live", "success")
            capture.start()
            result = process_tree.run(timeout_seconds=timeout_seconds)
            capture.finish()
            targets.write_visible_lines(capture.visible_lines)

            if result.state is ProcessState.TIMED_OUT:
                activity("TIMEOUT", f"Script exceeded {timeout_seconds:g}s; process tree stopped", "error")
                raise PatchHarborError(
                    f"script timed out after {timeout_seconds:g} seconds",
                    ExitCode.TIMEOUT,
                )
            if result.state is ProcessState.INTERRUPTED:
                activity("INTERRUPT", "Script interrupted; process tree stopped", "warning")
                raise PatchHarborError(
                    "script aborted by user",
                    ExitCode.INTERRUPTED,
                )
            if result.state is not ProcessState.EXITED:
                raise OSError("script process tree returned no terminal result")
            if result.return_code is None:
                raise OSError("script process tree returned no exit code")
            activity("EXEC", f"Interpreter completed with exit {result.return_code}",
                     "success" if result.return_code == 0 else "error")
            return result.return_code
    except KeyboardInterrupt:
        _finish_capture_after_process_error(capture)
        raise PatchHarborError(
            "script aborted by user",
            ExitCode.INTERRUPTED,
        ) from None
    except PatchHarborError:
        _finish_capture_after_process_error(capture)
        raise
    except OSError as exc:
        _finish_capture_after_process_error(capture)
        raise PatchHarborError(
            f"cannot control script process tree: {describe_os_error(exc)}",
            ExitCode.EXECUTION_ERROR,
        ) from exc
