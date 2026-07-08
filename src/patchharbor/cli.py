from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Sequence

try:
    from patchharbor import __version__
except ImportError:
    __version__ = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchharbor",
        description="Repository-agnostic development script and patch workflow tools.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"patchharbor {__version__}",
        help="print the PatchHarbor version and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser(
        "doctor",
        help="print a minimal local environment check",
    )
    doctor.add_argument(
        "--repo",
        default=".",
        help="repository path to check; defaults to the current working directory",
    )

    return parser


def _git_root(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _run_doctor(repo: str) -> int:
    repo_path = Path(repo).expanduser()
    print("PatchHarbor doctor")

    if not repo_path.exists():
        print("status: error")
        print(f"repository path: {repo_path}")
        print("git repository: no")
        return 1

    root = _git_root(repo_path)
    if root is None:
        print("status: error")
        print(f"repository path: {repo_path.resolve()}")
        print("git repository: no")
        return 1

    print("status: ok")
    print("git repository: yes")
    print(f"repository root: {root}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _run_doctor(args.repo)

    parser.print_help()
    return 0
