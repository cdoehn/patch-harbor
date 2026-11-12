"""Append diagnostic Actions summaries without changing acceptance decisions."""
import argparse
import os
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ci_summary import summarize
from tools.report_rendering import render_ci


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports-dir',type=Path,required=True)
    parser.add_argument('--artifact',default=os.environ.get('PH_SUMMARY_ARTIFACT'))
    parser.add_argument('--output',type=Path,default=os.environ.get('GITHUB_STEP_SUMMARY'))
    parser.add_argument('--best-effort',action='store_true',
                        help='Report diagnostic failures without changing existing test results')
    args = parser.parse_args(argv)
    if args.output is None:
        parser.error('an explicit output or GITHUB_STEP_SUMMARY is required')
    try:
        document = summarize(args.reports_dir,args.artifact,os.environ)
        with args.output.open('a',encoding='utf-8') as stream:
            stream.write(render_ci(document))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('Additional test summary failed: ' + str(exc),file=sys.stderr)
        return 0 if args.best_effort else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
