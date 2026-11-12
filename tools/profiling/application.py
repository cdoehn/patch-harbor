"""Local profiling application; no implicit collection or network access."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

from tools.profiling.capture import run
from tools.profiling.common import count, encoded, positive
from tools.profiling.reporting import compare_runs, report_run
from tools.test_policy import PROJECT_ROOT


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
    capture_parser.add_argument('--timeout', type=positive, default=3600.)
    capture_parser.add_argument('--max-bytes', type=int, default=64 * 1024 * 1024)
    capture_parser.add_argument('selection', nargs=argparse.REMAINDER)
    for name in ('report', 'compare'):
        read = commands.add_parser(name, allow_abbrev=False)
        read.add_argument('--database', type=Path, default=PROJECT_ROOT / 'build/test-profile/measurements.sqlite3')
        read.add_argument('--phase', choices=('setup', 'call', 'teardown'), default='call')
        read.add_argument('--format', choices=('json',), default='json')
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
            if args.max_bytes < 1024 or args.max_bytes > 4 * 1024**3:
                raise ValueError('artifact budget must be between 1 KiB and 4 GiB')
            result, code = run(args)
        else:
            result, code = (report_run(args) if args.command == 'report' else compare_runs(args)), 0
        print(encoded(result))
        return code
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(encoded({'status': 'error', 'error': str(exc)}))
        return 2
