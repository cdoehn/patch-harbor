"""Create only a fresh synthetic fixture; never use this setup on a user project.

Run in a dedicated process: this fixture deliberately isolates HOME/XDG/Git for
registration and initial Git commits. Export itself uses safe_reference_export.
"""
import os
from pathlib import Path
import subprocess

from patchharbor import api


def create_fixture(root, *, dirty=False):
    root = Path(root).absolute()
    root.mkdir(parents=False, exist_ok=False)
    for key in tuple(os.environ):
        if key.startswith('GIT_'):
            del os.environ[key]
    for key, name in (('HOME', 'home'), ('XDG_CONFIG_HOME', 'config'),
                      ('XDG_STATE_HOME', 'state'), ('XDG_CACHE_HOME', 'cache')):
        directory = root / name
        directory.mkdir()
        os.environ[key] = str(directory)
    os.environ['GIT_CONFIG_NOSYSTEM'] = '1'
    os.environ['GIT_CONFIG_GLOBAL'] = os.devnull
    os.environ['GIT_TERMINAL_PROMPT'] = '0'
    repository, template, output = (root / name for name in ('synthetic-project', 'empty-template', 'output'))
    repository.mkdir()
    template.mkdir()
    output.mkdir()
    def git(*args):
        subprocess.run(['git', '--no-optional-locks', *args], cwd=repository,
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git('init', '--quiet', '--initial-branch=main', '--template=' + str(template))
    git('config', 'user.name', 'Synthetic PatchHarbor fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    git('config', 'core.autocrlf', 'false')
    original = {'README.txt': b'Synthetic reference; no user data.\n',
                'shared.txt': b'base\n', 'binary.dat': b'base\0\xff',
                'empty': b'', 'no-lf': b'no final newline', 'remove': b'delete\n',
                'rename-from': b'rename\n', '.gitignore': b'ignored-fixture\n'}
    for name, raw in original.items():
        (repository / name).write_bytes(raw)
    git('add', '--all')
    git('-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'Synthetic reference base')
    (repository / '.git' / 'info').mkdir(exist_ok=True)
    api.register(repository)
    api.configure_exchange_directory(root / 'unused-exchange', repository=repository)
    (repository / 'ignored-fixture').write_bytes(b'ignored synthetic witness\n')
    base = {name: ('100644', raw) for name, raw in original.items()}
    index = dict(base)
    untracked = {}
    if dirty:
        (repository / 'shared.txt').write_bytes(b'staged\n')
        (repository / 'binary.dat').write_bytes(b'staged\0\xfe')
        (repository / 'remove').unlink()
        (repository / 'rename-from').rename(repository / 'rename-to')
        (repository / 'new-empty').write_bytes(b'')
        (repository / 'executable').write_bytes(b'fixture bytes\n')
        (repository / 'executable').chmod(0o755)
        git('add', '--all')
        index.update({'shared.txt': ('100644', b'staged\n'),
                      'binary.dat': ('100644', b'staged\0\xfe'), 'new-empty': ('100644', b''),
                      'executable': ('100755', b'fixture bytes\n'), 'rename-to': index.pop('rename-from')})
        del index['remove']
        (repository / 'shared.txt').write_bytes(b'worktree\n')
        (repository / 'loose.dat').write_bytes(b'untracked\0\xff')
        untracked['loose.dat'] = ('100644', b'untracked\0\xff')
    worktree = dict(index)
    if dirty:
        worktree['shared.txt'] = ('100644', b'worktree\n')
    return repository, output, {'base': base, 'index': index, 'worktree': worktree,
                                'untracked': untracked, 'effective': {**worktree, **untracked}}
