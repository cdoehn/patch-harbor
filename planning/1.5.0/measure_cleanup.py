"""Read-only RF-12 audit of two exact Git trees; no checkout or code execution.

Counts are physical lines (including comments/blanks), bytes and static import
edges, not semantic complexity, pytest cases or a performance measurement.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
from importlib.util import resolve_name
import json
from pathlib import Path
import re
import subprocess


def git(repository: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(
        ['git', '--no-optional-locks', '-C', str(repository), *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout


def tree(repository: Path, commit: str) -> dict[str, bytes]:
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
        raise ValueError('use a complete commit ID')
    if git(repository, 'cat-file', '-t', commit).strip() != b'commit':
        raise ValueError('object is not a commit')
    entries = []
    for row in git(repository, 'ls-tree', '-rz', commit).split(b'\0'):
        if row:
            facts, path = row.split(b'\t', 1)
            mode, kind, oid = facts.split()
            if kind != b'blob' or mode not in (b'100644', b'100755'):
                raise ValueError('unexpected non-file in measured tree')
            entries.append((path.decode('utf-8'), oid))
    raw = git(repository, 'cat-file', '--batch', data=b''.join(oid + b'\n' for _, oid in entries))
    files = {}
    offset = 0
    for path, oid in entries:
        end = raw.index(b'\n', offset)
        actual, kind, size = raw[offset:end].split()
        if actual != oid or kind != b'blob':
            raise ValueError('unexpected batch object')
        offset = end + 1
        files[path] = raw[offset:offset + int(size)]
        offset += int(size)
        if raw[offset:offset + 1] != b'\n':
            raise ValueError('truncated blob')
        offset += 1
    if offset != len(raw):
        raise ValueError('unexpected trailing bytes')
    return files


def facts(raw: bytes) -> dict:
    return {'bytes': len(raw), 'lines': len(raw.splitlines()),
            'sha256': hashlib.sha256(raw).hexdigest()}


def group(files: dict[str, bytes], names: list[str]) -> dict:
    return {'files': len(names), 'bytes': sum(len(files[n]) for n in names),
            'lines': sum(len(files[n].splitlines()) for n in names)}


def imports(files: dict[str, bytes]) -> list[list[str]]:
    modules = {p[:-3].replace('/', '.'): raw for p, raw in files.items()
               if p.startswith('tests/') and p.endswith('.py') and '/fixtures/' not in p}
    tests = {m for m in modules if m.rsplit('.', 1)[-1].startswith('test_')}
    edges = set()
    for module in sorted(tests):
        for node in ast.walk(ast.parse(modules[module])):
            targets = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = (resolve_name('.' * node.level + (node.module or ''), module.rpartition('.')[0])
                        if node.level else node.module)
                targets = [base + '.' + a.name if base + '.' + a.name in modules else base
                           for a in node.names]
            edges.update((module, target) for target in targets if target in tests and target != module)
    return [list(edge) for edge in sorted(edges)]


def measure(files: dict[str, bytes]) -> dict:
    production = sorted(p for p in files if p.startswith('src/') and p.endswith('.py'))
    tests = sorted(p for p in files if p.startswith('tests/') and p.endswith('.py') and '/fixtures/' not in p)
    support = [p for p in tests if not Path(p).name.startswith('test_')]
    modules = {p: facts(files[p]) for p in production}
    bootstrap = files['scripts/pyz_bootstrap.py']
    chat = files['CHAT_INSTRUCTIONS.md']
    start = b'```python\n# PATCHHARBOR-PYZ-BOOTSTRAP\n'
    if chat.count(start) != 1:
        raise ValueError('ambiguous embedded bootstrap')
    embedded = chat.split(start, 1)[1].split(b'```', 1)[0]
    generated = 'scripts/render_chat_bootstrap.py' in files
    return {
        'tracked_files': len(files), 'production_python': group(files, production),
        'test_python_excluding_fixtures': group(files, tests),
        'test_support_python': group(files, support),
        'production_modules': modules,
        'application_family': group(files, [p for p in production if Path(p).stem == 'application' or Path(p).stem.startswith('application_')]),
        'cli_family': group(files, [p for p in production if p.startswith('src/patchharbor/cli')]),
        'test_to_test_static_import_edges': imports(files),
        'bootstrap': {'authored_program_copies': 1 if generated else 2,
                      'generated_program_copies': int(generated),
                      'script': facts(bootstrap), 'embedded': facts(embedded),
                      'program_bytes_equal': bootstrap == embedded,
                      'generator_present': generated},
        'acceptance_matrix_generator_present': 'scripts/render_acceptance_matrix.py' in files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    args = parser.parse_args()
    before, after = (tree(args.repository, commit) for commit in (args.before, args.after))
    result = {'format_version': 1, 'before_commit': args.before, 'after_commit': args.after,
              'method': 'Tracked regular Git blobs; physical splitlines including blanks/comments. Static AST imports only; unique directed test-module edges. No dynamic import/runtime/performance measurement.',
              'generated_scope': 'Embedded CHAT bootstrap and workflow matrices are counted separately from authored programs. Build-only PYZ identities/resources are not tracked Python sources. Frozen fixture binaries are excluded from Python source totals.',
              'before': measure(before), 'after': measure(after),
              'removed_production_files': {p: facts(before[p]) for p in sorted(before.keys() - after.keys()) if p.startswith('src/')},
              'added_production_files': {p: facts(after[p]) for p in sorted(after.keys() - before.keys()) if p.startswith('src/')},
              'removed_scripts': {p: facts(before[p]) for p in sorted(before.keys() - after.keys()) if p.startswith('scripts/')},
              'removed_test_files': sorted(p for p in before.keys() - after.keys() if p.startswith('tests/'))}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
