"""Designated uv installation proof for the normal wheel and its current Core-PYZ.

The historic CI proof identity stays stable; no Result wheel is installed.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tests.reference_support import bound_package, reference_entries, write_reference

pytestmark = pytest.mark.packaging


@pytest.mark.proof('installation.uv')
def test_uv_installed_runtime_works_outside_checkout(built_result_source, tmp_path):
    uv = shutil.which('uv')
    if uv is None:
        pytest.skip('uv route runs on the designated Ubuntu 26.04 CI lane')
    workspace = tmp_path / 'outside'; workspace.mkdir()
    environment = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    environment.update(UV_CACHE_DIR=str(tmp_path/'uv-cache'), UV_PYTHON_DOWNLOADS='never')
    wheel, = (built_result_source.parent / 'dist').glob('*.whl')
    target = workspace/'venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    for command in (
        [uv,'venv','--offline','--no-python-downloads','--python',sys.executable,str(target.parent.parent)],
        [uv,'pip','install','--offline','--no-index','--no-deps','--python',str(target),str(wheel)],
    ):
        result = subprocess.run(command,cwd=workspace,env=environment,capture_output=True,text=True,timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    files, binding = reference_entries()
    reference = workspace/'reference.zip'; write_reference(reference,files)
    patch = workspace/'patch.zip'; bound_package(patch,binding)
    contents=workspace/'contents'; contents.mkdir()
    (contents/'run.sh').write_bytes(b'#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    (workspace/'patchharbor.py').write_text('raise AssertionError("foreign CWD")\n')
    runtime = workspace/'core.pyz'
    program = '''
import hashlib,json,os,socket,subprocess,sys
from pathlib import Path
selected,reference,patch,contents=map(Path,sys.argv[1:])
if selected.is_file():sys.path.insert(0,str(selected))
from patchharbor import api
from patchharbor.pyz_artifact import PyzProvider
if selected.is_file():assert api.__file__.startswith(str(selected)+os.sep)
else:assert Path(api.__file__).resolve().is_relative_to(Path(sys.prefix))
def forbidden(*a,**k):raise AssertionError('installed runtime attempted external work')
socket.socket=subprocess.Popen=subprocess.run=forbidden
os.environ['PATH']=''
checked=api.validate_patch(patch,reference_bundle=reference)
assert checked.binding_matches and checked.reference_sha256==hashlib.sha256(reference.read_bytes()).hexdigest()
output=Path('pyz-output' if selected.is_file() else 'installed-output');output.mkdir()
packed=api.pack_patch(contents,reference_bundle=reference,entrypoint='run.sh',output_directory=output)
assert api.validate_patch(packed.path,reference_bundle=reference).binding_matches
artifact=PyzProvider().capture().artifact
assert artifact is not None and artifact.recipe.requires_python=='>=3.10'
if selected.is_file():assert selected.read_bytes()==artifact.pyz_bytes
else:selected.write_bytes(artifact.pyz_bytes)
assert 'patchharbor_watcher' not in sys.modules
print(json.dumps({'reference_sha256':checked.reference_sha256,'pyz_sha256':artifact.pyz_sha256}))
'''
    proofs=[]
    for python, flags in ((str(target), ['-I','-B']), (sys.executable,['-I','-S','-B'])):
        completed=subprocess.run([python,*flags,'-c',program,str(runtime),str(reference),str(patch),str(contents)],
                                 cwd=workspace,env=environment,capture_output=True,text=True,timeout=90)
        assert completed.returncode==0,completed.stdout+completed.stderr
        proofs.append(json.loads(completed.stdout))
    assert proofs[0]==proofs[1]
    assert proofs[0]['reference_sha256']==hashlib.sha256(reference.read_bytes()).hexdigest()
    assert proofs[0]['pyz_sha256']==hashlib.sha256(runtime.read_bytes()).hexdigest()
