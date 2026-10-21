"""Run one Docker gate and transfer its private report to the host runner."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import subprocess
import sys


def export_report(path: Path, uid: int, gid: int) -> None:
    # The bind mount is prepared by the runner. Touch only this completed report,
    # never the checkout, build artifacts, directories or link targets.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("Docker evidence must be a regular file with one link")
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, uid, gid)
        after = os.fstat(descriptor)
        if (after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)) != (uid, gid, 0o600):
            raise ValueError("Docker evidence owner or permissions differ")
    finally:
        os.close(descriptor)


def run_gate(command: list[str], report: Path, uid: int, gid: int) -> int:
    # No shell, retries or altered test invocation. Stdout/stderr go to the
    # runner's existing log; failed gates must still export their diagnostics.
    status = subprocess.run(command, check=False).returncode
    try:
        export_report(report, uid, gid)
    except (OSError, ValueError) as error:
        print(f"Docker report export failed: {type(error).__name__}: {error}", file=sys.stderr)
        return status or 1
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--uid", required=True, type=int)
    parser.add_argument("--gid", required=True, type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.uid < 0 or args.gid < 0 or not command:
        parser.error("nonnegative owner IDs and a gate command are required")
    status = run_gate(command, args.report, args.uid, args.gid)
    return status if status >= 0 else 128 - status


if __name__ == "__main__":
    raise SystemExit(main())
