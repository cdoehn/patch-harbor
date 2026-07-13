"""PatchHarbor command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from patchharbor.errors import PatchHarborError
from patchharbor.execution import DEFAULT_TIMEOUT_SECONDS
from patchharbor.input import run_script_file


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
        help="run one script file",
        description="Run one Bash or PowerShell script file.",
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
        metavar="PATH",
        help="script file to run",
    )

    return parser


def _run_file_command(path: Path, timeout_seconds: float) -> int:
    try:
        return run_script_file(
            path,
            cwd=Path.cwd(),
            timeout_seconds=timeout_seconds,
        )
    except PatchHarborError as exc:
        print(f"patchharbor: {exc}", file=sys.stderr)
        return int(exc.exit_code)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PatchHarbor CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "fs" and args.fs_command == "run":
        return _run_file_command(args.path, args.timeout)

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
