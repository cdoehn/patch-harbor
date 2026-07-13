"""Command-line interface for the first PatchHarbor vertical slice."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from patchharbor.input import run_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patchharbor")
    commands = parser.add_subparsers(dest="command", required=True)

    fs_parser = commands.add_parser("fs")
    fs_commands = fs_parser.add_subparsers(dest="fs_command", required=True)

    run_parser = fs_commands.add_parser("run")
    run_parser.add_argument("path", type=Path)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PatchHarbor CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "fs" and args.fs_command == "run":
        result = run_file(args.path)
        if result.error is not None:
            print(f"patchharbor: {result.error.message}", file=sys.stderr)
            return 2
        if result.execution is None:
            raise RuntimeError("file run finished without a result")
        return result.execution.exit_code

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
