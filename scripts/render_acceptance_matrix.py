"""Render only CI matrix blocks from the catalogue; never invoke CI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.acceptance_catalog import LANES

WORKFLOW = ROOT / '.github/workflows/acceptance-tests.yml'


def render(text: str) -> str:
    for group in dict.fromkeys(lane.group for lane in LANES):
        start = f'      # BEGIN acceptance-catalog: {group}\n'
        end = f'      # END acceptance-catalog: {group}\n'
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError('Missing or duplicate generated matrix boundary: ' + group)
        lines = ['      matrix:', '        include:']
        for lane in LANES:
            if lane.group == group:
                for index, (key, value) in enumerate(lane.matrix().items()):
                    lines.append(('          - ' if index == 0 else '            ')
                                 + key + ': ' + json.dumps(value))
        text, count = re.subn(re.escape(start) + r'.*?' + re.escape(end),
                             lambda _: start + '\n'.join(lines) + '\n' + end, text, flags=re.S)
        if count != 1:
            raise ValueError('Invalid generated matrix boundary: ' + group)
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    before = WORKFLOW.read_text(encoding='utf-8')
    after = render(before)
    if args.check:
        if after != before:
            print('Acceptance matrix differs from tools/acceptance-catalog.json', file=sys.stderr)
            return 1
    elif after != before:
        WORKFLOW.write_text(after, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
