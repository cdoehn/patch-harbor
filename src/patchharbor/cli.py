"""PatchHarbor command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import TextIO

from patchharbor.errors import PatchHarborError
from patchharbor.execution import DEFAULT_TIMEOUT_SECONDS
from patchharbor.application import run_script_path, run_standard_input


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
        "path",
        type=Path,
        nargs="?",
        metavar="PATH",
        help="script file or directory; omit to read standard input",
    )

    return parser


def _run_command(
    path: Path | None,
    timeout_seconds: float,
    *,
    parser: argparse.ArgumentParser,
    stdin: TextIO,
) -> int:
    if path is None and stdin.isatty():
        parser.error("PATH is required when standard input is a terminal")

    try:
        if path is not None:
            return run_script_path(
                path,
                cwd=Path.cwd(),
                timeout_seconds=timeout_seconds,
                selection_input=stdin,
                selection_output=sys.stdout,
            )

        return run_standard_input(
            stdin,
            cwd=Path.cwd(),
            timeout_seconds=timeout_seconds,
        )
    except PatchHarborError as exc:
        print(f"patchharbor: {exc}", file=sys.stderr)
        return int(exc.exit_code)


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
) -> int:
    """Run the PatchHarbor CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "fs" and args.fs_command == "run":
        return _run_command(
            args.path,
            args.timeout,
            parser=parser,
            stdin=sys.stdin if stdin is None else stdin,
        )

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
