#!/usr/bin/env python3
"""Development-only pytest invocation policy; no test scheduling or aggregation."""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import sys

if __package__:
    from .test_policy import PROJECT_ROOT, DEFAULT_WORKERS, EVIDENCE_PLUGIN, process_exit_code
else:
    from test_policy import PROJECT_ROOT, DEFAULT_WORKERS, EVIDENCE_PLUGIN, process_exit_code


def _nonnegative(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a non-negative integer") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("expected a non-negative integer")
    return result


def _workers(value: str) -> str:
    if value == "auto":
        return value
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("workers must be auto or a positive integer") from exc
    if count < 1:
        raise argparse.ArgumentTypeError("use --serial for the zero-worker reference")
    return str(count)


def _parser(environment: Mapping[str, str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--serial", action="store_true", help="Run the serial reference suite.")
    mode.add_argument("--workers", type=_workers,
                      help="Run with N xdist workers; the default is auto.")
    parser.add_argument("--report", type=Path, help="Write a controller-owned JSON result.")
    parser.add_argument("--reference", type=Path, help="Compare with a serial JSON result.")
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
    forbidden = ("--numprocesses", "--dist", "--tx", "--looponfail", "--max-worker-restart",
                 "--ph-report", "--ph-reference", "--ph-check")
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
    if args.reference and not args.report:
        parser.error("--reference requires --report")
    evidence = ["-p", EVIDENCE_PLUGIN, "--ph-check"]
    if args.report:
        evidence.extend(["--ph-report", str(args.report.resolve())])
        if args.reference:
            evidence.extend(["--ph-reference", str(args.reference.resolve())])
    command = [python, "-m", "pytest", "-p", "no:timeout", "-q",
               f"--durations={args.durations}",
               "-n", "0" if args.serial else args.workers or DEFAULT_WORKERS, "--max-worker-restart=0", *evidence, *forwarded]
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
    return process_exit_code(result.returncode)
