#!/usr/bin/env python3
"""Run sequential *whole-suite* references; pytest-xdist schedules the tests.

Evidence files are deliberately retained, including after a failure. An output
folder must not already exist, so an old green report cannot satisfy a new run.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

if __package__:
    from .test_results import EvidenceError, equivalent, validate
else:
    from test_results import EvidenceError, equivalent, validate

ROOT = Path(__file__).resolve().parents[1]


def verification_matrix() -> tuple[tuple[str, str], ...]:
    return (("0", "0"), ("2", "0"), ("4", "0"), ("auto", "0"),
            ("2", "1"), ("4", "42"), ("auto", "314159"))


def verify(outdir: Path, targets: list[str], *, python: str = sys.executable) -> int:
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=False)
    reference = None
    reference_path = None
    for index, (workers, seed) in enumerate(verification_matrix()):
        report = outdir / f"{index:02}-workers-{workers}-seed-{seed}.json"
        mode = ["--serial"] if workers == "0" else ["--workers", workers]
        command = [python, str(ROOT / "tools" / "run_tests.py"), *mode, "--report", str(report)]
        if reference_path is not None:
            command += ["--reference", str(reference_path)]
        command += ["--", *targets]
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        environment["PYTEST_ADDOPTS"] = ""
        print(f"Verification: workers={workers}; PYTHONHASHSEED={seed}", flush=True)
        result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
        if result.returncode:
            return result.returncode if result.returncode > 0 else 128 - result.returncode
        actual = json.loads(report.read_text(encoding="utf-8"))
        validate(actual)
        if reference is None:
            reference = actual
            reference_path = report
        else:
            equivalent(reference, actual)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    targets = args.pytest_args
    if targets[:1] == ["--"]: targets = targets[1:]
    try:
        return verify(args.outdir, targets or ["tests"])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Test-mode verification failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
