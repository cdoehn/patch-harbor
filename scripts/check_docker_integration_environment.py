#!/usr/bin/env python3
"""Fail unless the Docker integration environment matches the release gate."""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, distribution
from importlib.util import find_spec
import locale
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_DETERMINISTIC_ENVIRONMENT = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TZ": "UTC",
    "PYTHONHASHSEED": "0",
    "PYTHONUTF8": "1",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
}


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


def declared_dev_distribution_names(
    pyproject_path: Path = PROJECT_ROOT / "pyproject.toml",
) -> tuple[str, ...]:
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    requirements = project["project"]["optional-dependencies"]["dev"]
    names: list[str] = []
    for requirement in requirements:
        _require(isinstance(requirement, str), "development requirement is not text")
        match = _REQUIREMENT_NAME.match(requirement)
        _require(match is not None, f"invalid development requirement: {requirement!r}")
        names.append(match.group(0))
    return tuple(names)


def _require_declared_dev_distributions(pyproject_path: Path) -> None:
    for name in declared_dev_distribution_names(pyproject_path):
        try:
            installed = distribution(name)
        except PackageNotFoundError:
            raise SystemExit(f"required development distribution is unavailable: {name}") from None
        _require(bool(installed.version), f"development distribution has no version: {name}")


def _require_deterministic_environment() -> None:
    for name, expected in _DETERMINISTIC_ENVIRONMENT.items():
        _require(
            os.environ.get(name) == expected,
            f"deterministic environment variable differs: {name}",
        )
    encoding = locale.getpreferredencoding(False).replace("-", "").lower()
    _require(encoding == "utf8", f"UTF-8 locale is required, found {encoding}")
    _require(Path.home().is_absolute(), "HOME must resolve to an absolute path")
    _require(Path.home().is_dir(), "HOME directory is unavailable")


def _require_empty_global_git_configuration() -> None:
    completed = subprocess.run(
        ["git", "config", "--global", "--list", "--null"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=10,
    )
    _require(completed.returncode == 0, "global Git configuration cannot be inspected")
    _require(completed.stdout == b"", "global Git configuration must be isolated")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-init", action="store_true")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=PROJECT_ROOT / "pyproject.toml",
    )
    arguments = parser.parse_args(argv)

    _require(
        sys.version_info[:2] == (3, 12),
        f"Python 3.12 is required, found {sys.version_info.major}.{sys.version_info.minor}",
    )
    for command in ("bash", "git", "pipx"):
        _command_version(command)
    for module in ("build", "pytest", "pytest_timeout"):
        _require(find_spec(module) is not None, f"required Python module is unavailable: {module}")
    _require_declared_dev_distributions(arguments.pyproject)
    _require_deterministic_environment()
    _require_empty_global_git_configuration()

    if arguments.require_init:
        init_name = Path("/proc/1/comm").read_text(encoding="utf-8").strip()
        _require(init_name in {"docker-init", "tini"}, f"container init is missing: {init_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
