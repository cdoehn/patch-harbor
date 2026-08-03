"""PatchHarbor command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import TextIO

from patchharbor.application import run_script_path, run_standard_input
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import DEFAULT_TIMEOUT_SECONDS
from patchharbor.output import TemporaryRunLog, temporary_run_log


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
        description="Run generated scripts in a controlled workflow.",
    )
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="COMMAND",
    )

    fs_parser = commands.add_parser(
        "fs",
        help="read scripts from the file system",
    )
    fs_commands = fs_parser.add_subparsers(
        dest="fs_command",
        required=True,
        metavar="COMMAND",
    )

    run_parser = fs_commands.add_parser(
        "run",
        help="run a script file or choose one from a directory",
        description="Run one Bash or PowerShell script from a file, directory, or standard input.",
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
        help="disable PatchHarbor colors",
    )
    run_parser.add_argument(
        "--log",
        action="store_true",
        help="write complete script output and run metadata to a temporary log",
    )
    run_parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        metavar="PATH",
        help="script file or directory; omit to read standard input",
    )

    return parser


def _is_terminal(stream: TextIO) -> bool:
    try:
        return stream.isatty()
    except (AttributeError, OSError):
        return False


def _write_log_header(
    run_log: TemporaryRunLog,
    *,
    source_name: str,
    cwd: Path,
    timeout_seconds: float,
    plain_output: bool,
    color_enabled: bool,
) -> None:
    stream = run_log.stream
    stream.write("PatchHarbor run log\n")
    stream.write(
        f"started_utc: {datetime.now(timezone.utc).isoformat()}\n"
    )
    stream.write(f"source: {json.dumps(source_name, ensure_ascii=False)}\n")
    stream.write(
        f"working_directory: {json.dumps(str(cwd), ensure_ascii=False)}\n"
    )
    stream.write(f"timeout_seconds: {timeout_seconds:g}\n")
    stream.write(f"plain_output: {str(plain_output).lower()}\n")
    stream.write(f"color_enabled: {str(color_enabled).lower()}\n")
    stream.write("--- merged script output ---\n")
    stream.flush()


def _write_log_result(
    run_log: TemporaryRunLog,
    *,
    exit_code: int,
    tool_error: str | None,
) -> None:
    stream = run_log.stream
    stream.write("\n--- run result ---\n")
    stream.write(f"exit_code: {exit_code}\n")
    if tool_error is not None:
        stream.write(
            f"tool_error: {json.dumps(tool_error, ensure_ascii=False)}\n"
        )
    stream.write(
        f"finished_utc: {datetime.now(timezone.utc).isoformat()}\n"
    )
    stream.flush()


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
    plain_output = force_plain or not _is_terminal(stdout)
    color_enabled = not no_color and not plain_output
    log_context = temporary_run_log() if log_enabled else nullcontext(None)
    log_path: Path | None = None
    exit_code = 0
    tool_error: str | None = None

    try:
        with log_context as run_log:
            if run_log is not None:
                log_path = run_log.path
                _write_log_header(
                    run_log,
                    source_name="standard input" if path is None else str(path),
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                    plain_output=plain_output,
                    color_enabled=color_enabled,
                )

            try:
                if path is not None:
                    exit_code = run_script_path(
                        path,
                        cwd=cwd,
                        timeout_seconds=timeout_seconds,
                        selection_input=stdin,
                        selection_output=stdout,
                        output_stream=stdout,
                        plain_output_stream=(stdout if plain_output else None),
                        log_stream=(None if run_log is None else run_log.stream),
                    )
                else:
                    exit_code = run_standard_input(
                        stdin,
                        cwd=cwd,
                        timeout_seconds=timeout_seconds,
                        output_stream=stdout,
                        plain_output_stream=(stdout if plain_output else None),
                        log_stream=(None if run_log is None else run_log.stream),
                    )
            except PatchHarborError as exc:
                tool_error = str(exc)
                print(f"patchharbor: {exc}", file=stderr)
                exit_code = int(exc.exit_code)

            if run_log is not None:
                _write_log_result(
                    run_log,
                    exit_code=exit_code,
                    tool_error=tool_error,
                )
    except OSError as exc:
        print(f"patchharbor: cannot write run log: {exc}", file=stderr)
        return int(ExitCode.EXECUTION_ERROR)

    if log_path is not None:
        print(f"patchharbor: log: {log_path}", file=stderr)
    return exit_code


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the PatchHarbor CLI."""
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
            stdin=sys.stdin if stdin is None else stdin,
            stdout=sys.stdout if stdout is None else stdout,
            stderr=sys.stderr if stderr is None else stderr,
        )

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
