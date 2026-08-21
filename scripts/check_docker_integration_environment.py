#!/usr/bin/env python3
"""Fail unless the Docker integration environment matches the release gate."""

from __future__ import annotations

import argparse
from importlib.util import find_spec
from pathlib import Path
import shutil
import subprocess
import sys


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _command_version(command: str) -> None:
    executable = shutil.which(command)
    _require(executable is not None, f"required command is unavailable: {command}")
    completed = subprocess.run(
        [executable, "--version"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=10,
    )
    _require(completed.returncode == 0, f"required command is unusable: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-init", action="store_true")
    arguments = parser.parse_args(argv)

    _require(
        sys.version_info[:2] == (3, 12),
        f"Python 3.12 is required, found {sys.version_info.major}.{sys.version_info.minor}",
    )
    for command in ("bash", "git", "pipx"):
        _command_version(command)
    for module in ("build", "pytest", "pytest_timeout"):
        _require(find_spec(module) is not None, f"required Python module is unavailable: {module}")

    if arguments.require_init:
        init_name = Path("/proc/1/comm").read_text(encoding="utf-8").strip()
        _require(init_name in {"docker-init", "tini"}, f"container init is missing: {init_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
