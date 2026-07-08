from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Sequence

try:
    from patchharbor import __version__
except ImportError:
    __version__ = "0.1.0"

from patchharbor.patch_lint import PatchLintError
from patchharbor.patch_lint_api import lint_patch_file, render_patch_lint_result


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

    lint_script = subparsers.add_parser(
        "lint-script",
        help="lint a patch script file",
    )
    lint_script.add_argument(
        "path",
        help="patch script file to lint",
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


def _run_lint_script(path: str) -> int:
    print("PatchHarbor lint-script")
    print(f"script: {Path(path).expanduser()}")

    try:
        result = lint_patch_file(path)
    except PatchLintError as exc:
        print("status: error")
        print(f"problem: {exc}")
        return 2

    for line in render_patch_lint_result(result):
        print(line)

    return 1 if result.has_findings else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _run_doctor(args.repo)

    if args.command == "lint-script":
        return _run_lint_script(args.path)

    parser.print_help()
    return 0
