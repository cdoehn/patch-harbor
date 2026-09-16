#!/usr/bin/env python3
"""Run development tests in a fresh pytest process (serial reference)."""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _nonnegative(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a non-negative integer") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer")
    return result


def _parser(environment: Mapping[str, str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--serial", action="store_true", help="Run the serial reference suite.")
    parser.add_argument("--durations", type=_nonnegative,
                        default=environment.get("PATCHHARBOR_TEST_DURATIONS", "10"))
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER,
                        help="Pass pytest arguments after --; the default is the full tests directory.")
    return parser


def _pytest_arguments(parser: argparse.ArgumentParser, arguments: list[str]) -> list[str]:
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    # Execution-mode options must not silently defeat --serial. This is a
    # developer interface, not a security sandbox for arbitrary pytest plugins.
    forbidden = ("--numprocesses", "--dist", "--tx", "--looponfail")
    for argument in arguments:
        if (argument in ("-d", "-f") or argument.startswith("-n")
                or any(argument == name or argument.startswith(name + "=") for name in forbidden)):
            parser.error("select workers through the launcher's mode option, not pytest passthrough")
    return arguments or ["tests"]


def prepare_invocation(
    argv: Sequence[str] | None,
    *,
    environment: Mapping[str, str],
    python: str = sys.executable,
) -> tuple[list[str], dict[str, str]]:
    """Return a shell-free command and child-only environment; mutate neither."""
    parser = _parser(environment)
    args = parser.parse_args(argv)
    forwarded = _pytest_arguments(parser, args.pytest_args)
    command = [python, "-m", "pytest", "-p", "no:timeout", "-q",
               f"--durations={args.durations}", *forwarded]
    child_environment = dict(environment)
    child_environment["PYTEST_ADDOPTS"] = ""
    return command, child_environment


def main(argv: Sequence[str] | None = None) -> int:
    command, environment = prepare_invocation(argv, environment=os.environ)
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, env=environment, check=False)
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"Cannot start pytest: {exc}", file=sys.stderr)
        return 3
    # POSIX Popen uses negative return codes for signals; don't turn SIGKILL
    # into an apparently unrelated exit 247 via SystemExit(-9).
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
