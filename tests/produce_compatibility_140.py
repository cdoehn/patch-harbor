"""One-time Linux fixture capture with pinned 1.4.0 code; never run by pytest.

Creates only private sample repositories. Does not build, rewrite or normalize
the producer or its output archives. Output must be a new directory. See the
fixture README for provenance and the distinction from ordinary regression tests.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile


PRODUCER_SHA256 = '4e0d26997bffe9476e79d98211cef2d93be7899063a0eb3480bea2ffa3d8f594'
BINDING_FIELDS = ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repo, *args):
    # Only the newly created private sample repo may be mutated by this helper.
    assert repo.name in {'sample', 'unprepared-sample'} and repo.parent.name.startswith('patchharbor-140-')
    return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.PIPE).decode().strip()


def seed(root, name):
    repo = root / name
    repo.mkdir()
    git(repo, 'init', '--quiet', '--initial-branch=fixture')
    git(repo, 'config', 'user.name', 'PatchHarbor Compatibility Fixture')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    git(repo, 'config', 'core.autocrlf', 'false')
    git(repo, 'config', 'core.fileMode', 'true')
    (repo / 'tracked.txt').write_bytes(b'base\n')
    (repo / 'delete-me.txt').write_bytes(b'deletion fixture\n')
    (repo / 'Grüße.txt').write_text('public fixture\n', encoding='utf-8')
    (repo / 'tool.sh').write_bytes(b'#!/bin/sh\nprintf fixture\n')
    (repo / 'tool.sh').chmod(0o755)
    git(repo, 'add', '--', 'tracked.txt', 'delete-me.txt', 'Grüße.txt', 'tool.sh')
    git(repo, 'commit', '--quiet', '-m', 'public fixture base')
    return repo


def record_result(path, destination, *, before, after, commits, operation, patch=None):
    raw = path.read_bytes()
    destination.write_bytes(raw)
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        run = json.loads(archive.read('logs/run.json'))
        runtime = json.loads(archive.read('runtime/runtime.json'))
        entries = {name: {'bytes': len(data), 'sha256': digest(data)}
                   for name in archive.namelist() for data in [archive.read(name)]}
    return {
        'bytes': len(raw), 'sha256': digest(raw), 'original_filename': path.name,
        'format_version': manifest['format_version'],
        'binding': {key: manifest[key] for key in BINDING_FIELDS},
        'operation': operation, 'primary_kind': run['primary_result']['kind'],
        'entrypoint_exit_code': run['primary_result']['entrypoint_exit_code'],
        'process_exit_code': run['process_exit_code'], 'dry_run': run['dry_run'],
        'dirty': manifest['dirty'], 'runtime_status': runtime['status'],
        'runtime_reason': runtime['reason'], 'runtime_version': runtime['version'],
        'expected_base_commit': manifest.get('expected_base_commit'),
        'completed_commit': manifest.get('completed_commit'),
        'patch_sha256': manifest.get('patch_sha256'), 'patch_fixture': patch,
        'before_commit': before, 'after_commit': after, 'actual_new_commits': commits,
        'archive_eligible': not (manifest['dirty'] or run['dry_run'] or run['warnings'])
                            and run['primary_result']['kind'] == 'success',
        'entries': entries,
    }


def produce(args):
    if os.name != 'posix':
        raise SystemExit('This one-time historical producer recipe requires Linux/Git/Bash.')
    producer = args.producer.resolve()
    assert digest(producer.read_bytes()) == PRODUCER_SHA256
    source = args.source.resolve()
    source_manifest = json.loads(args.source_manifest.read_bytes())
    for name, expected in source_manifest['files'].items():
        assert digest((source / name).read_bytes()) == expected
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    # The isolated process imports only the trusted historical artifact.
    sys.path.insert(0, str(producer))
    import patchharbor
    from patchharbor import api
    assert patchharbor.__version__ == '1.4.0'
    assert patchharbor.__file__.startswith(str(producer) + os.sep)
    cases, patches = {}, {}
    with tempfile.TemporaryDirectory(prefix='patchharbor-140-') as temporary:
        root = Path(temporary)
        for name in tuple(os.environ):
            if name.startswith('GIT_'):
                del os.environ[name]
        # Keep the caller's HOME unchanged; all PatchHarbor writes use private XDG roots.
        os.environ.update(XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'),
                          XDG_CACHE_HOME=str(root / 'cache'), GIT_CONFIG_GLOBAL=os.devnull,
                          GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0',
                          GIT_AUTHOR_DATE='2026-10-14T12:00:00+00:00',
                          GIT_COMMITTER_DATE='2026-10-14T12:00:00+00:00')
        repo = seed(root, 'sample')
        api.register(repo)
        api.configure_exchange_directory(root / 'exchange', repository=repo)
        (root / 'clean').mkdir()
        current = api.bundle(repo, output_directory=root / 'clean').path
        head = git(repo, 'rev-parse', 'HEAD')
        cases['clean'] = record_result(current, output / 'result-clean.zip', before=head,
                                       after=head, commits=[], operation='bundle')

        def apply_case(name, payload, body, *, commits, exit_code=0, dry_run=False):
            nonlocal current
            contents = root / ('contents-' + name)
            contents.mkdir()
            for path, data in payload.items():
                (contents / path).write_bytes(data)
            (contents / 'run.sh').write_text('#!/usr/bin/env bash\n# PATCHHARBOR\nset -eu\n' + body + '\n')
            modes = {'run.sh': 0o755}
            if 'payload.sh' in payload:
                modes['payload.sh'] = 0o755
            (root / ('patches-' + name)).mkdir()
            (root / ('result-' + name)).mkdir()
            packed = api.pack_patch(contents, reference_bundle=current, entrypoint='run.sh',
                                    output_directory=root / ('patches-' + name), modes=modes)
            patch_name = 'patch-' + name + '.zip'
            raw = packed.path.read_bytes()
            (output / patch_name).write_bytes(raw)
            patches[name] = {'bytes': len(raw), 'sha256': digest(raw), 'reference': current.name,
                             'reference_fixture': 'result-' + ('multi' if name in {'dry-run', 'partial-failure'} else
                                 {'diagnostic': 'clean', 'single': 'diagnostic', 'multi': 'single'}[name]) + '.zip',
                             'original_filename': packed.path.name}
            before = git(repo, 'rev-parse', 'HEAD')
            report = api.apply(packed.path, dry_run=dry_run, output_directory=root / ('result-' + name),
                               output=api.OutputStreams(text=StringIO(), warnings=StringIO()))
            assert report.process_exit_code == exit_code
            after = git(repo, 'rev-parse', 'HEAD')
            history = git(repo, 'rev-list', '--reverse', before + '..' + after).splitlines()
            assert len(history) == commits
            path = report.result_bundle.path
            cases[name] = record_result(path, output / ('result-' + name + '.zip'), before=before,
                                         after=after, commits=history, operation='apply', patch=patch_name)
            if not dry_run:
                current = path

        apply_case('diagnostic', {}, "printf 'public diagnostic, zero commits\\n'", commits=0)
        apply_case('single', {'tracked.txt': b'one\n', 'payload.sh': b'#!/bin/sh\nexit 0\n'},
                   'git add -- tracked.txt payload.sh\ngit commit --quiet -m "fixture single"', commits=1)
        apply_case('multi', {'tracked.txt': b'two-a\n'},
                   'git add -- tracked.txt\ngit commit --quiet -m "fixture multi first"\n'
                   'printf "two-b\\n" > tracked.txt\ngit add -- tracked.txt\n'
                   'git commit --quiet -m "fixture multi second"', commits=2)
        apply_case('dry-run', {'must-not-exist.txt': b'not applied\n'},
                   'printf forbidden > dry-run-executed.txt', commits=0, dry_run=True)
        assert not (repo / 'must-not-exist.txt').exists() and not (repo / 'dry-run-executed.txt').exists()
        apply_case('partial-failure', {'tracked.txt': b'partial commit\n'},
                   'git add -- tracked.txt\ngit commit --quiet -m "fixture partial progress"\n'
                   'printf "uncommitted after failure\\n" > tracked.txt\n'
                   'printf "public untracked\\n" > failed-untracked.txt\nexit 7', commits=1, exit_code=7)
        # The final manual snapshot independently captures staged, unstaged, deletion and untracked data.
        (repo / 'tracked.txt').write_bytes(b'staged\n')
        git(repo, 'add', '--', 'tracked.txt')
        (repo / 'tracked.txt').write_bytes(b'unstaged\n')
        (repo / 'delete-me.txt').unlink()
        (repo / 'untracked.bin').write_bytes(b'\x00public\xff\n')
        head = git(repo, 'rev-parse', 'HEAD')
        (root / 'dirty').mkdir()
        dirty = api.bundle(repo, output_directory=root / 'dirty').path
        cases['dirty'] = record_result(dirty, output / 'result-dirty.zip', before=head,
                                       after=head, commits=[], operation='bundle')
        # Unprepared *original release source*, not a patched provider or forged descriptor.
        bare_repo = seed(root, 'unprepared-sample')
        program = '''
import json,sys
from pathlib import Path
source,repo,exchange=map(Path,sys.argv[1:])
sys.path.insert(0,str(source/'src'))
import patchharbor
from patchharbor import api
assert patchharbor.__version__=='1.4.0'
assert Path(patchharbor.__file__).resolve().is_relative_to(source/'src')
api.register(repo);api.configure_exchange_directory(exchange,repository=repo)
print(json.dumps({'path':str(api.bundle(repo).path)}))
'''
        command = [sys.executable, '-I', '-S', '-B', '-c', program,
                   str(source), str(bare_repo), str(root / 'unavailable')]
        captured = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
        path = Path(json.loads(captured.stdout)['path'])
        head = git(bare_repo, 'rev-parse', 'HEAD')
        cases['unavailable'] = record_result(path, output / 'result-unavailable.zip', before=head,
                                             after=head, commits=[], operation='bundle')
        assert cases['unavailable']['runtime_status'] == 'unavailable'
        assert cases['unavailable']['runtime_reason'] == 'source_not_prepared'
        assert all(c['runtime_status'] == 'embedded' for n,c in cases.items() if n != 'unavailable')
        # No host or user repository files are ever added to these sample repositories.
        snapshots = {n for c in cases.values() for n in c['entries'] if n.startswith(('base/', 'untracked/'))}
        assert not any('.patchharbor/' in n or '.git/' in n for n in snapshots)
    with ZipFile(producer) as archive:
        recipe = json.loads(archive.read('patchharbor/_runtime/pyz-recipe.json'))
    provenance = {
        'fixture_format': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Unmodified artifacts captured from genuine 1.4.0 bundle/pack/apply operations on public sample data.',
        'producer': {'version': '1.4.0', 'bytes': producer.stat().st_size, 'sha256': PRODUCER_SHA256,
                     'content_id': recipe['content_id'], 'declared_source_commit': recipe['source_commit'],
                     'requires_python': recipe['requires_python'],
                     'trusted_result': args.reference_name, 'trusted_result_sha256': args.reference_sha256},
        'unprepared_source': source_manifest,
        'generation': {'script_sha256': digest(Path(__file__).read_bytes()),
                       'python': sys.version, 'platform': sys.platform, 'git': subprocess.check_output(['git','--version'],text=True).strip(),
                       'network_used': False, 'archives_rewritten': False,
                       'note': 'Git commits exist only in temporary sample repos. No push; directories deleted after capture.'},
        'results': cases, 'patches': patches,
    }
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'results': len(cases), 'patches': len(patches), 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('producer', 'source', 'source-manifest', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--reference-name', required=True)
    parser.add_argument('--reference-sha256', required=True)
    produce(parser.parse_args())
