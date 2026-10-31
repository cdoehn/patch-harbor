"""Real producer fixtures with independent Git/index and filesystem byte oracles."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import random
import subprocess
from zipfile import ZipFile

from patchharbor import api
from tests.registration_support import create_repository, git, set_isolated_user_environment


def git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=repo)


def index_files(repo: Path) -> dict[str, tuple[str, bytes]]:
    files = {}
    for row in git_bytes(repo, 'ls-files', '--stage', '-z').split(b'\0'):
        if not row:
            continue
        attributes, name = row.split(b'\t', 1)
        mode, oid, stage = attributes.split()
        assert stage == b'0'
        files[name.decode()] = (mode.decode(), git_bytes(repo, 'cat-file', 'blob', oid.decode()))
    return files


def working_files(repo: Path, index) -> dict[str, tuple[str, bytes]]:
    return {name: ('100755' if os.name != 'nt' and (repo/name).stat().st_mode & 0o111
                  else mode if os.name == 'nt' else '100644', (repo/name).read_bytes())
            for name, (mode, _) in index.items() if (repo/name).is_file()}


@dataclass(frozen=True)
class SnapshotCase:
    result: Path
    repository: Path
    expected: dict


def produce_case(tmp_path, monkeypatch, *, kind='mixed', object_format='sha1', quoted=True):
    set_isolated_user_environment(monkeypatch, tmp_path/'user')
    repo = create_repository(tmp_path/'repo', object_format=object_format)
    original = {
        'tracked.txt': b''.join(f'line {i}\n'.encode() for i in range(100)),
        'large.bin': random.Random(53).randbytes(32768),
        'small.bin': b'old\0\xff', 'no-lf': b'first\nlast',
        'empty-delete': b'', 'remove': b'gone\n', 'rename from': b'move\n',
        'replace': b'old tracked\n', '雪 space/a b/file': b'unicode\n',
        'raw-text': b'raw \xff\xfe\n',
    }
    for name, data in original.items():
        p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    git(repo, 'add', '--all');git(repo, 'commit', '--quiet', '-m', 'snapshot fixture')
    base=index_files(repo)
    api.register(repo)
    api.configure_exchange_directory(tmp_path/'exchange', repository=repo)
    git(repo,'config','core.quotePath','true' if quoted else 'false')
    # Product capture must stay canonical despite ordinary local preferences.
    git(repo,'config','diff.mnemonicPrefix','true')
    git(repo,'config','diff.noPrefix','true')
    git(repo,'config','diff.relative','true')
    def change(phase):
        text=original['tracked.txt'].replace(b'line 3\n', b'first change\n').replace(b'line 80\n', phase+b' change\n')
        (repo/'tracked.txt').write_bytes(text)
        raw=bytearray(original['large.bin']);raw[100:132]=bytes([phase[0]])*32
        (repo/'large.bin').write_bytes(raw)
        (repo/'small.bin').write_bytes(b'\0'+phase+b'\xff')
        (repo/'no-lf').write_bytes(b'first\n'+phase)
        (repo/'raw-text').write_bytes(b'new \xfe\xff\r\n'+phase)
        (repo/'雪 space/a b/file').write_bytes(phase+b'\n')
    if kind in ('staged','mixed'):
        change(b'staged')
        for name in ('empty-delete','remove','replace'):(repo/name).unlink()
        (repo/'empty-add').write_bytes(b'')
        (repo/'new file').write_bytes(b'new\n')
        (repo/'rename from').rename(repo/'renamed to')
        git(repo,'add','--all')
    index=index_files(repo)
    if kind in ('unstaged','mixed'):
        change(b'worktree')
    untracked={}
    if kind in ('untracked','mixed'):
        untracked={'loose/sub':('100644',b'loose\0\xff'), 'replace':('100644',b'replacement\n')} if kind=='mixed' else {'loose/sub':('100644',b'loose\0\xff')}
        for name,(_,data) in untracked.items():
            p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    worktree=working_files(repo,index)
    bundled=api.bundle(repo)
    return SnapshotCase(bundled.path,repo,{'base':base,'index':index,'worktree':worktree,
        'untracked':untracked,'effective':{**worktree,**untracked}})


def result_files(path):
    with ZipFile(path) as z:
        return {i.filename:z.read(i) for i in z.infolist()}, tuple(i.filename for i in z.infolist() if (i.external_attr>>16)&0o111)


def update_json(files,name,operation):
    document=json.loads(files[name]);operation(document);files[name]=json.dumps(document).encode()
