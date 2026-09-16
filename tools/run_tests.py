#!/usr/bin/env python3
"""Run development tests in a fresh pytest process (serial reference)."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--serial", action="store_true", help="Run the serial reference suite.")
    parser.add_argument("--durations", type=int, default=int(os.environ.get("PATCHHARBOR_TEST_DURATIONS", "10")))
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    forwarded = args.pytest_args
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    command = [sys.executable, "-m", "pytest", "-p", "no:timeout", "-q",
               f"--durations={args.durations}", *(forwarded or ["tests"])]
    environment = os.environ.copy()
    environment["PYTEST_ADDOPTS"] = ""
    return subprocess.run(command, cwd=PROJECT_ROOT, env=environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
