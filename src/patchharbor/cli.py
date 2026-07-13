"""Command-line interface for the first PatchHarbor vertical slice."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path
import subprocess


def _run_file(script_path: Path) -> int:
    """Read one UTF-8 script and run it with the platform default shell."""
    script_path.read_text(encoding="utf-8")

    if os.name == "nt":
        command = [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script_path),
        ]
    else:
        command = ["bash", str(script_path)]

    completed = subprocess.run(command, check=False)
    return completed.returncode


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
        return _run_file(args.path)

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
