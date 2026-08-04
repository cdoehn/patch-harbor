"""PatchHarbor command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path
import sys
from typing import TextIO

from patchharbor import __version__
from patchharbor.application import run_script_path, run_standard_input
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    format_tool_message,
)
from patchharbor.execution import DEFAULT_TIMEOUT_SECONDS
from patchharbor.output import OutputTargets
from patchharbor.platform.errors import describe_os_error
from patchharbor.presentation import (
    TerminalDashboard,
    terminal_supports_dashboard,
)
from patchharbor.run_log import temporary_run_log


def _configure_utf8_standard_stream(stream: TextIO, *, errors: str) -> None:
    """Use deterministic UTF-8 for real process standard streams when possible."""
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors=errors)
    except (OSError, ValueError):
        # Embedded or already detached streams may not be reconfigurable.
        pass


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if seconds <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return seconds


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchharbor",
        description=(
            "Run generated Bash and PowerShell scripts or ZIP "
            "PatchBundles with controlled execution."
        ),
        epilog=(
            "Use 'patchharbor fs run --help' for input formats, "
            "execution rules, and run options."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the installed PatchHarbor version and exit",
    )
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="COMMAND",
    )

    fs_parser = commands.add_parser(
        "fs",
        help="run from the file system or standard input",
    )
    fs_commands = fs_parser.add_subparsers(
        dest="fs_command",
        required=True,
        metavar="COMMAND",
    )

    run_parser = fs_commands.add_parser(
        "run",
        help=(
            "run scripts from a file, ZIP PatchBundle, directory, "
            "or standard input"
        ),
        description=(
            "Run generated Bash or PowerShell scripts from a file, "
            "ZIP PatchBundle, directory, or standard input."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Script contract:\n"
            "  A script must contain a line exactly equal to "
            "'# PATCHHARBOR'.\n"
            "\n"
            "Input behavior:\n"
            "  PATH may name one script, a ZIP PatchBundle, or a "
            "directory.\n"
            "  Omit PATH to read one script or ZIP PatchBundle from "
            "standard input.\n"
            "  ZIP PatchBundles may contain ordered scripts and byte-exact "
            "payload files.\n"
            "\n"
            "Execution behavior:\n"
            "  Scripts run in the current working directory.\n"
            "  Oversized inputs and unsafe ZIP PatchBundles are rejected "
            "before any script starts."
        ),
    )
    run_parser.add_argument(
        "--timeout",
        type=_positive_seconds,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "stop the script after this many seconds "
            f"(default: {DEFAULT_TIMEOUT_SECONDS:g})"
        ),
    )
    run_parser.add_argument(
        "--plain",
        action="store_true",
        help="stream simple text output even when standard output is a terminal",
    )
    run_parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable colors in the terminal dashboard",
    )
    run_parser.add_argument(
        "--log",
        action="store_true",
        help=(
            "write complete merged script output and run metadata "
            "to a temporary log"
        ),
    )
    run_parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        metavar="PATH",
        help=(
            "script or ZIP PatchBundle file, or directory; "
            "omit to read standard input"
        ),
    )

    return parser


def _execute_request(
    path: Path | None,
    *,
    cwd: Path,
    timeout_seconds: float,
    stdin: TextIO,
    stdout: TextIO,
    output: OutputTargets,
    dashboard: TerminalDashboard | None,
) -> tuple[int, str | None]:
    try:
        if path is not None:
            return (
                run_script_path(
                    path,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                    selection_input=stdin,
                    selection_output=stdout,
                    output=output,
                    presentation=dashboard,
                ),
                None,
            )
        return (
            run_standard_input(
                stdin,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                output=output,
                presentation=dashboard,
            ),
            None,
        )
    except PatchHarborError as exc:
        return int(exc.exit_code), str(exc)


def _run_command(
    path: Path | None,
    timeout_seconds: float,
    *,
    force_plain: bool,
    no_color: bool,
    log_enabled: bool,
    parser: argparse.ArgumentParser,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if path is None and stdin.isatty():
        parser.error("PATH is required when standard input is a terminal")

    cwd = Path.cwd()
    plain_output = force_plain or not terminal_supports_dashboard(stdout)
    dashboard = (
        None
        if plain_output
        else TerminalDashboard(stdout, color_enabled=not no_color)
    )
    log_context = temporary_run_log() if log_enabled else nullcontext(None)
    log_path: Path | None = None
    exit_code = 0
    tool_error: str | None = None

    try:
        try:
            with log_context as run_log:
                if run_log is not None:
                    log_path = run_log.path
                    run_log.write_header(
                        source_name=(
                            "standard input" if path is None else str(path)
                        ),
                        cwd=cwd,
                        timeout_seconds=timeout_seconds,
                    )

                output = OutputTargets(
                    visible_text_stream=stdout,
                    live_text_stream=(stdout if plain_output else None),
                    raw_output_stream=(
                        None if run_log is None else run_log.raw_output_stream
                    ),
                    warning_text_stream=(stderr if plain_output else None),
                    warning_observer=(
                        None if run_log is None else run_log.write_warning
                    ),
                    line_observer=(
                        None if dashboard is None else dashboard.update_output
                    ),
                )
                try:
                    exit_code, tool_error = _execute_request(
                        path,
                        cwd=cwd,
                        timeout_seconds=timeout_seconds,
                        stdin=stdin,
                        stdout=stdout,
                        output=output,
                        dashboard=dashboard,
                    )
                except KeyboardInterrupt:
                    exit_code = int(ExitCode.INTERRUPTED)
                    tool_error = "request aborted by user"

                if run_log is not None:
                    run_log.write_result(
                        exit_code=exit_code,
                        tool_error=tool_error,
                    )
        except KeyboardInterrupt:
            exit_code = int(ExitCode.INTERRUPTED)
            tool_error = "request aborted by user"
        except OSError as exc:
            tool_error = (
                "cannot write PatchHarbor output: "
                f"{describe_os_error(exc)}"
            )
            exit_code = int(ExitCode.EXECUTION_ERROR)

        dashboard_active = dashboard is not None and dashboard.started
        if dashboard_active:
            try:
                dashboard.finish(
                    exit_code=exit_code,
                    tool_error=tool_error,
                    log_path=log_path,
                )
            except OSError as exc:
                print(
                    format_tool_message(
                        "cannot restore terminal: "
                        f"{describe_os_error(exc)}"
                    ),
                    file=stderr,
                )
                exit_code = int(ExitCode.EXECUTION_ERROR)
        else:
            if tool_error is not None:
                print(format_tool_message(tool_error), file=stderr)
            if log_path is not None:
                print(format_tool_message(f"log: {log_path}"), file=stderr)

        return exit_code
    finally:
        if dashboard is not None:
            dashboard.close()


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the PatchHarbor CLI."""
    actual_stdin = sys.stdin if stdin is None else stdin
    actual_stdout = sys.stdout if stdout is None else stdout
    actual_stderr = sys.stderr if stderr is None else stderr
    if stdin is None:
        _configure_utf8_standard_stream(actual_stdin, errors="strict")
    if stdout is None:
        _configure_utf8_standard_stream(actual_stdout, errors="replace")
    if stderr is None:
        _configure_utf8_standard_stream(actual_stderr, errors="replace")

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "fs" and args.fs_command == "run":
        return _run_command(
            args.path,
            args.timeout,
            force_plain=args.plain,
            no_color=args.no_color,
            log_enabled=args.log,
            parser=parser,
            stdin=actual_stdin,
            stdout=actual_stdout,
            stderr=actual_stderr,
        )

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
