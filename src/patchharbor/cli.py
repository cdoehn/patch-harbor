"""Minimal PatchHarbor command-line interface."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Sequence

from . import __version__


def _is_git_repository(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def run_doctor(args: argparse.Namespace) -> int:
    repo = Path(args.repo).expanduser().resolve()
    print(f"PatchHarbor doctor: {repo}")
    if not repo.exists():
        print("status: error")
        print("problem: repository path does not exist")
        return 1
    if not _is_git_repository(repo):
        print("status: error")
        print("problem: repository path is not a Git repository")
        return 1
    print("status: ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchharbor",
        description="Repository-agnostic development scripts and patch workflow tools.",
    )
    parser.add_argument("--version", action="version", version=f"patchharbor {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="run a minimal environment check")
    doctor.add_argument("--repo", default=".", help="repository path to check, default: current directory")
    doctor.set_defaults(func=run_doctor)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args))
