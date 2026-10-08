"""First productive Result uses its own embedded bootstrap, then real Apply."""
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

from patchharbor.result_reader import read_result_reference
from patchharbor import runtime_pyz as pyz
from scripts.build_release import _copy_release_inputs
from tests.embedded_pyz_support import bootstrap_program
from tests.platform_support import native_python_script, native_value
from tests.registration_support import create_repository
from tests.runtime_permissions import readonly_tree
from tests.test_runtime_packaging import _run, _venv


@pytest.fixture(scope='module')
def installed_producer(tmp_path_factory):
    root=tmp_path_factory.mktemp('pyz-writer-installation')
    source=root/'source';source.mkdir();outside=root/'outside';outside.mkdir()
    _copy_release_inputs(source)
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    environment.update(PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PIP_CONFIG_FILE=os.devnull)
    output=root/'dist'
    _run([sys.executable,'-m','build','--wheel','--no-isolation','--outdir',str(output)],source,environment)
    python=_venv(root/'venv',outside,environment)
    _run([sys.executable,'-m','pip','--python',str(python),'install','--no-index','--no-deps',
          '--no-cache-dir','--no-compile',str(next(output.glob('*.whl')))],outside,environment)
    shutil.rmtree(source);shutil.rmtree(output)
    return python


@pytest.mark.packaging
@pytest.mark.parametrize('payload_kind',['full','diff','mixed'])
def test_first_production_result_uses_own_instruction_then_regular_pyz_apply(installed_producer,tmp_path,payload_kind):
    repo=create_repository(tmp_path/'repository');exchange=tmp_path/'exchange'
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    produced=json.loads(_run([str(installed_producer),'-I','-B','-c',r'''
import json,sys
from pathlib import Path
from patchharbor import api
repo,exchange=map(Path,sys.argv[1:])
api.register(repo);api.configure_exchange_directory(exchange,repository=repo)
result=api.bundle(repo)
print(json.dumps({'path':str(result.path)}))
''',str(repo),str(exchange)],tmp_path,environment))
    reference=Path(produced['path']);original=reference.read_bytes()
    facts,digest=read_result_reference(reference)
    assert facts.format_version==3 and facts.runtime.status=='embedded' and not facts.warnings
    with ZipFile(reference) as archive:
        template=archive.read('CHAT_INSTRUCTIONS.md')
        raw=archive.read(facts.runtime.artifact.path)
        assert {n for n in archive.namelist() if n.startswith('runtime/')}=={
            'runtime/runtime.json',facts.runtime.artifact.path}
    with ZipFile(BytesIO(raw)) as archive:
        assert not any(n.startswith('patchharbor_watcher/') for n in archive.namelist())
    # E-10: executable bootstrap taken only from THIS Result's root handoff.
    helper=tmp_path/'reviewed-instruction.py';helper.write_text(bootstrap_program(template))
    outside=tmp_path/'outside';outside.mkdir()
    (outside/'patchharbor.py').write_text('raise AssertionError("foreign import")\n')
    contents=tmp_path/'contents';contents.mkdir();output=tmp_path/'patches';output.mkdir()
    entrypoint=native_value('run.sh','run.ps1')
    if payload_kind=='full':(contents/'tracked.txt').write_bytes(b'changed\n')
    else:
        (contents/'change.patch').write_bytes(b'diff --git a/tracked.txt b/tracked.txt\n--- a/tracked.txt\n+++ b/tracked.txt\n@@ -1 +1 @@\n-base\n+changed\n')
    if payload_kind!='diff':(contents/'payload.bin').write_bytes(b'\0payload\xff')
    code="from pathlib import Path\nimport subprocess\n"
    if payload_kind!='full':code+="subprocess.run(['git','apply','--','change.patch'],check=True)\n"
    code+="assert Path('tracked.txt').read_bytes()==b'changed\\n'\n"
    if payload_kind!='diff':code+="assert Path('payload.bin').read_bytes()==b'\\0payload\\xff'\n"
    code+="Path('entrypoint-proof').write_bytes(b'payloads-before-entrypoint')\n"
    (contents/entrypoint).write_text(native_python_script(code))
    proof=json.loads(_run([sys.executable,'-I','-S','-B','-c',r'''
import hashlib,importlib.util,json,os,socket,subprocess,sys
from pathlib import Path
helper,reference,workspace,contents,output=map(Path,sys.argv[1:6]);entrypoint=sys.argv[6]
spec=importlib.util.spec_from_file_location('reviewed_own_instruction',helper)
bootstrap=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bootstrap;spec.loader.exec_module(bootstrap)
assert not any(n=='patchharbor' or n.startswith('patchharbor.') for n in sys.modules)
def forbidden(*a,**k):raise AssertionError('Python-only consumer used process/network')
subprocess.run=subprocess.Popen=socket.socket=forbidden;os.environ['PATH']=''
assessment=bootstrap.assess(reference,trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
assert not assessment.full_reference_valid
prepared=bootstrap.prepare(assessment,workspace);api=bootstrap.import_api(prepared)
packed=api.pack_patch(contents,reference_bundle=reference,entrypoint=entrypoint,output_directory=output)
checked=api.validate_patch(packed.path,reference_bundle=reference)
assert checked.binding_matches and checked.scope=='reference'
assert checked.reference_sha256==assessment.reference_sha256
assert api.inspect_patch(packed.path).package_sha256==packed.package_sha256
assert 'patchharbor_watcher' not in sys.modules
print(json.dumps({'patch':str(packed.path),'pyz':str(prepared.path),'sha256':packed.package_sha256,
                  'reference_sha256':checked.reference_sha256,'api_origin':api.__file__}))
''',str(helper),str(reference),str(tmp_path/'private-runtime'),str(contents),str(output),entrypoint],outside,environment))
    assert proof['reference_sha256']==digest and reference.read_bytes()==original
    runtime=Path(proof['pyz']);assert runtime.read_bytes()==raw
    assert proof['api_origin'].startswith(str(runtime)+os.sep)
    assert hashlib.sha256(Path(proof['patch']).read_bytes()).hexdigest()==proof['sha256']
    prefix=[sys.executable,'-I','-S','-B',str(runtime)]
    def command(*arguments,cwd=repo):
        document=json.loads(_run([*prefix,*map(str,arguments),'--json'],cwd,environment))
        assert document['success'] is True,document
        return document['result']
    with readonly_tree(runtime.parent,owner=tmp_path,environment=environment):
        command('context');command('registry','list')
        _run([*prefix,'configure','show'],repo,environment)
        command('inspect',proof['patch'])
        assert command('validate',proof['patch'],'--reference-bundle',reference)['binding_matches']
        outcome=command('apply',proof['patch'])
        returned=Path(outcome['result_bundle']['path'])
        returned_facts,_=read_result_reference(returned)
        assert returned_facts.format_version==3 and returned_facts.runtime.artifact.sha256==facts.runtime.artifact.sha256
        assert (repo/'entrypoint-proof').read_bytes()==b'payloads-before-entrypoint'
        followup=tmp_path/'followup';followup.mkdir()
        fresh=command('bundle',repo,'--output-dir',followup)
        assert read_result_reference(Path(fresh['result_bundle_path']))[0].runtime.artifact.sha256==facts.runtime.artifact.sha256
        legacy=tmp_path/native_value('legacy.sh','legacy.ps1')
        legacy.write_text(native_python_script("from pathlib import Path; Path('fs-run-proof').write_bytes(b'legacy-core')"))
        _run([*prefix,'fs','run',str(legacy)],repo,environment)
        assert (repo/'fs-run-proof').read_bytes()==b'legacy-core'
        _run([*prefix,'unregister',str(repo)],repo,environment)
