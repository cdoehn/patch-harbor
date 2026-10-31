"""CLI observation, machine envelopes and completion rendering."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, TextIO

import patchharbor.api as api
from patchharbor.api import PatchHarborError, ResultBundleStatus, RunReport
from patchharbor.errors import format_tool_message
from patchharbor.exit_status import exit_code_for_error
from patchharbor.identifier_presentation import shorten_identifier
from patchharbor.json_document import serialize_json_document
from patchharbor.presentation import (
    PresentedCompletion,
    PresentedStatus,
    StreamingConsole,
)
from patchharbor.run_report import physical_absolute_path_text, sanitize_structured_text


def _write_json_document(document: dict[str, object], stream: TextIO) -> None:
    stream.write(serialize_json_document(document))


def _json_envelope(
    command: str,
    *,
    result: dict[str, object] | None,
    error: PatchHarborError | None,
    process_exit_code: int,
    output_version: int = 1,
) -> dict[str, object]:
    structured_error: dict[str, object] | None = None
    if error is not None:
        report = error.run_report if isinstance(error.run_report, RunReport) else None
        emergency_path = (
            error.emergency_diagnostics_path
            if report is None
            else report.result_bundle.emergency_diagnostics_path
        )
        structured_error = {
            "kind": error.error_kind.value,
            "message": sanitize_structured_text(str(error)),
            "patchharbor_error_code": int(exit_code_for_error(error)),
            "emergency_diagnostics_path": physical_absolute_path_text(
                emergency_path
            ),
        }
    return {
        "output_version": output_version,
        "command": command,
        "success": process_exit_code == 0,
        "result": result,
        "error": structured_error,
        "process_exit_code": process_exit_code,
    }


def _write_emergency_diagnostics_notice(
    path: Path | None,
    *,
    failed: bool,
    stderr: TextIO,
) -> None:
    """Expose one best-effort diagnostics outcome without duplicating wording."""
    if path is not None:
        print(
            format_tool_message(f"emergency diagnostics: {path}"),
            file=stderr,
        )
    elif failed:
        print(
            format_tool_message("emergency diagnostics could not be saved"),
            file=stderr,
        )


def _write_apply_completion(
    report: RunReport,
    *,
    json_output: bool,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Render one completed Apply run solely from its immutable report."""
    if json_output:
        _write_json_document(report.apply_json_envelope(), stdout)
    else:
        tool_error = report.completion_tool_error
        if tool_error is not None:
            print(format_tool_message(tool_error.message), file=stderr)
            if report.result_bundle.path is not None:
                print(
                    format_tool_message(
                        f"result bundle: {report.result_bundle.path}"
                    ),
                    file=stderr,
                )
        else:
            print(
                f"run_id: {shorten_identifier(report.run_id_text)}",
                file=stdout,
            )
            print(f"repository_path: {report.resolved_repository}", file=stdout)
            print(f"result_bundle_path: {report.result_bundle.path}", file=stdout)
    _write_emergency_diagnostics_notice(
        report.result_bundle.emergency_diagnostics_path,
        failed=report.result_bundle.status is ResultBundleStatus.FAILED,
        stderr=stderr,
    )
    return report.process_exit_code


def _presented_completion(
    *,
    exit_code: int,
    tool_error: str | None,
    log_path: Path | None = None,
    result_path: Path | None = None,
) -> PresentedCompletion:
    """Choose one completion state before crossing into presentation."""
    if tool_error is not None:
        status = PresentedStatus.ERROR
    elif exit_code == 0:
        status = PresentedStatus.SUCCESS
    else:
        status = PresentedStatus.FAILED
    return PresentedCompletion(
        status=status,
        exit_code=exit_code,
        detail=tool_error,
        log_path=log_path,
        result_path=result_path,
    )


@contextmanager
def _console_scope(
    stdout: TextIO, *, enabled: bool, color_enabled: bool,
    stderr: TextIO | None = None,
    plain: bool = False,
    verbose: bool = False,
) -> Iterator[StreamingConsole | None]:
    """Start observation before discovery and release it on every exit path."""
    try:
        terminal = stdout.isatty() and not plain
    except (AttributeError, OSError):
        terminal = False
    console = (
        StreamingConsole(
            stdout if terminal or stderr is None else stderr,
            color_enabled=color_enabled and terminal, plain=plain,
            child_output=None if terminal else stdout, verbose=verbose,
        ) if enabled else None
    )
    try:
        if console is not None:
            console.activity("PATCHHARBOR", "Starting request", "heading")
        yield console
    finally:
        if console is not None:
            console.close()


def _progress_observer(console: StreamingConsole | None) -> api.ProgressObserver | None:
    """Pass this invocation's presentation explicitly through the API boundary."""
    return None if console is None else console.observe


def _output_streams_for_presentation(
    *, visible_stdout: TextIO, visible_stderr: TextIO,
    console: StreamingConsole | None, suppress_visible_output: bool = False,
    raw_output_stream: BinaryIO | None = None,
    warning_observer: Callable[[str], None] | None = None,
) -> api.OutputStreams:
    """Keep machine JSON and raw bytes separate from human streaming output."""
    if suppress_visible_output:
        return api.OutputStreams(raw=raw_output_stream, on_warning=warning_observer)
    return api.OutputStreams(
        text=visible_stdout if console is None else console.child_stream,
        raw=raw_output_stream,
        warnings=visible_stderr if console is None else console.warning_stream,
        on_warning=warning_observer,
    )


def _write_command_error(
    command: str, error: PatchHarborError, *, json_output: bool,
    stdout: TextIO, stderr: TextIO, output_version: int = 1,
) -> int:
    """Render a known query/bundle failure with its existing JSON version."""
    code = int(exit_code_for_error(error))
    if json_output:
        _write_json_document(_json_envelope(
            command, result=None, error=error, process_exit_code=code,
            output_version=output_version,
        ), stdout)
    else:
        print(format_tool_message(str(error)), file=stderr)
    return code
