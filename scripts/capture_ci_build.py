"""Build audited release artifacts and record exact interpreter/dependency bytes."""
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_release import build_release
from tools.test_evidence import input_binding


def capture(report: Path, *, commit: str | None = None) -> dict:
    if commit is None:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        commit_source = 'checkout'
    else:
        commit_source = 'docker-build-context'
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('full build commit required')
    report = report.absolute()
    if report.exists():
        raise FileExistsError(report)
    before = input_binding(ROOT)
    artifacts = report.with_name(report.stem + '-artifacts')
    artifacts.mkdir(parents=True, exist_ok=False)
    wheel, sdist = build_release(artifacts)
    pyz = next(artifacts.glob('*.pyz'))
    from zipfile import ZipFile
    with ZipFile(wheel) as archive:
        recipe = json.loads(archive.read('patchharbor/_runtime/pyz-recipe.json'))
    if input_binding(ROOT) != before or recipe['requires_python'] != '>=3.10':
        raise ValueError('build inputs or Python variant changed')
    document = {
        'format_version': 1, 'commit': commit, 'commit_source': commit_source,
        'binding': before, 'version': recipe['version'], 'requires_python': recipe['requires_python'],
        'pyz_content_id': recipe['content_id'],
        'dependencies': {name: metadata.version(name) for name in
                         ('pip', 'setuptools', 'build', 'wheel', 'pipx', 'pytest', 'pytest-xdist', 'pytest-timeout')},
        'artifacts': [{'name': path.name, 'size': path.stat().st_size, 'sha256': sha256(path.read_bytes()).hexdigest()}
                      for path in (wheel, sdist, pyz)],
    }
    if sys.version_info < (3, 11):
        document['dependencies']['tomli'] = metadata.version('tomli')
    temporary = report.with_suffix('.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(document, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, report)
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--commit', help='Host checkout commit for a Docker build context without .git')
    args = parser.parse_args()
    print(json.dumps(capture(args.report, commit=args.commit)))


if __name__ == '__main__':
    main()
