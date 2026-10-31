"""Isolated native repositories and independent source-mutation witnesses."""
import hashlib
from pathlib import Path
import shlex
import stat
import sys

from patchharbor import api
from tests.registration_support import create_repository, git, set_isolated_user_environment


def source_bytes(repository):
    return {p.relative_to(repository).as_posix(): (stat.S_IMODE(p.stat().st_mode), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in repository.rglob('*') if p.is_file() and not p.is_symlink()}


def host(tmp_path, monkeypatch):
    set_isolated_user_environment(monkeypatch, tmp_path/'user')
    repo = create_repository(tmp_path/'repo')
    (repo/'protected.txt').write_bytes(b'must remain unchanged\n')
    (repo/'.gitignore').write_bytes(b'ignored-secret\n')
    git(repo,'add','--all');git(repo,'commit','--quiet','-m','protected source')
    (repo/'ignored-secret').write_bytes(b'synthetic ignored value\n')
    api.register(repo)
    exchange=tmp_path/'exchange';api.configure_exchange_directory(exchange,repository=repo)
    output=tmp_path/'output';output.mkdir()
    return repo, exchange, output


def arm_helper(root, repo, kind):
    calls=root/'helper-calls';helper=root/'helper.py'
    helper.write_text('#!'+sys.executable+'\nimport sys\nfrom pathlib import Path\n'
        +'with Path('+repr(str(calls))+').open("ab") as f: f.write(b"called\\n")\n'
        +'Path('+repr(str(repo/'protected.txt'))+').write_bytes(b"MUTATED BY HELPER\\n")\n'
        +'sys.stdout.buffer.write(sys.stdin.buffer.read())\n')
    helper.chmod(0o755)
    command=shlex.quote(sys.executable)+' -I -B '+shlex.quote(str(helper))
    if kind in ('clean','smudge','process'):
        (repo/'.gitattributes').write_bytes(b'tracked.txt filter=probe\n')
        git(repo,'config','filter.probe.'+kind,command)
        git(repo,'config','filter.probe.required','true')
    elif kind=='textconv':
        (repo/'.gitattributes').write_bytes(b'tracked.txt diff=probe\n')
        git(repo,'config','diff.probe.textconv',command)
    elif kind=='external':git(repo,'config','diff.external',command)
    elif kind=='fsmonitor':git(repo,'config','core.fsmonitor',str(helper))
    elif kind=='hooks':
        hooks=root/'hooks';hooks.mkdir()
        for name in ('post-index-change','post-checkout','pre-auto-gc','reference-transaction','pre-commit','post-commit'):
            p=hooks/name;p.write_bytes(helper.read_bytes());p.chmod(0o755)
        git(repo,'config','core.hooksPath',str(hooks))
    else:raise AssertionError(kind)
    (repo/'tracked.txt').write_bytes(b'dirty source bytes\n')
    return calls
