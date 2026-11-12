"""Local profiling application; no implicit collection or network access."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

from tools.profiling.capture import run
from tools.profiling.common import count, encoded, positive, positive_integer
from tools.profiling.budgets import requested_limits
from tools.profiling.reporting import compare_runs, report_run
from tools.test_policy import PROJECT_ROOT
from tools.report_rendering import render_profile


def parser():
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = result.add_subparsers(dest='command', required=True)
    capture_parser = commands.add_parser('run', allow_abbrev=False)
    capture_parser.add_argument('--database', type=Path, default=PROJECT_ROOT / 'build/test-profile/measurements.sqlite3')
    capture_parser.add_argument('--modes', default='baseline')
    capture_parser.add_argument('--workers', default='auto')
    capture_parser.add_argument('--repetitions', type=count, default=5)
    capture_parser.add_argument('--profile-repetitions', type=count, default=1)
    capture_parser.add_argument('--warmups', type=int, default=1, choices=range(0, 101))
    capture_parser.add_argument('--budget-scale', type=positive_integer, default=1,
                                help='multiply all default budgets (default: 1, already includes 10x headroom)')
    capture_parser.add_argument('--timeout', type=positive,
                                help='seconds per measurement (default: 432000, scaled by --budget-scale)')
    capture_parser.add_argument('--max-bytes', type=positive_integer,
                                help='artifact bytes per measurement (default: 343597383680 = 320 GiB, scaled)')
    capture_parser.add_argument('--max-files', type=positive_integer,
                                help='artifact files per measurement (default: 1500000, scaled)')
    capture_parser.add_argument('selection', nargs=argparse.REMAINDER)
    for name in ('report', 'compare'):
        read = commands.add_parser(name, allow_abbrev=False)
        read.add_argument('--database', type=Path, default=PROJECT_ROOT / 'build/test-profile/measurements.sqlite3')
        read.add_argument('--phase', choices=('setup', 'call', 'teardown'), default='call')
        read.add_argument('--format', choices=('json','text','markdown'), default='json')
        if name == 'report':
            read.add_argument('--run', default='latest')
            read.add_argument('--mode', choices=('baseline','cprofile','memory','strace'), default='baseline')
            read.add_argument('--top', type=count, default=10)
        else:
            read.add_argument('--before', required=True)
            read.add_argument('--after', required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'run':
            args.limits = requested_limits(args)
            args.timeout = args.limits.timeout_s
            args.max_bytes = args.limits.artifact_bytes
            args.max_files = args.limits.artifact_files
            result, code = run(args)
        else:
            result, code = (report_run(args) if args.command == 'report' else compare_runs(args)), 0
        print(encoded(result) if args.command == 'run' else render_profile(result, args.format))
        return code
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(encoded({'status': 'error', 'error': str(exc)}))
        return 2
