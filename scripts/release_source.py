"""Shared read-only source binding for local candidates and remote releases."""
import ast
from pathlib import Path
import subprocess

from scripts.release_artifacts import names, require

ROOT = Path(__file__).resolve().parents[1]


def source_checkout(version, commit, *, root=ROOT):
    names(version)
    require(len(commit)==40 and all(c in '0123456789abcdef' for c in commit),'full commit required')
    def git(*arguments):
        return subprocess.check_output(['git','--no-optional-locks',*arguments],cwd=root,text=True).strip()
    require(git('rev-parse','HEAD')==commit,'checkout differs from expected candidate commit')
    require(not git('status','--porcelain=v1','--untracked-files=all'),'candidate checkout is dirty')
    source = ast.parse((root/'src/patchharbor/__init__.py').read_text())
    versions = [ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='__version__' for t in n.targets)]
    require(versions==[version],'source version differs from candidate')
