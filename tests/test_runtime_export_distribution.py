"""Actual fresh installations and executable exports; no Git or user state at export."""
from pathlib import Path
from hashlib import sha256
import json
import os
import shutil
import subprocess
import sys

import pytest
from patchharbor import __version__
from scripts.release_artifacts import PROBE, verify_distributions
from tests.platform_support import PROJECT_ROOT

pytestmark=pytest.mark.packaging


def build_release(artifacts, *, root=PROJECT_ROOT):
    # Build tools may alter interpreter search paths; keep the actual build isolated.
    subprocess.run([sys.executable, str(root/'scripts/build_release.py'),
                    '--outdir',str(artifacts)],cwd=root,check=True,capture_output=True,text=True,timeout=120)


@pytest.mark.proof('runtime.public-export')
def test_wheel_sdist_pyz_public_export_byte_equality(tmp_path):
    artifacts=tmp_path/'artifacts'
    build_release(artifacts)
    proofs=verify_distributions(artifacts,__version__,tmp_path/'installation')
    assert len({p['runtime']['sha256'] for p in proofs.values()})==1
    assert {p['runtime']['distribution_version'] for p in proofs.values()}=={__version__}


@pytest.mark.proof('runtime.direct-consumer', parameter='case')
@pytest.mark.parametrize('case',['clean','dirty'])
@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='safe-reference host contract requires Linux')
def test_release_pyz_direct_consumer_without_result_bootstrap(tmp_path,case):
    from hashlib import sha256
    artifacts=tmp_path/'artifacts'
    build_release(artifacts)
    runtime=artifacts/f'patchharbor-{__version__}.pyz'
    digest=sha256(runtime.read_bytes()).hexdigest()
    process=subprocess.run([sys.executable,'-I','-S','-B',str(PROJECT_ROOT/'docs/examples/verify_release_runtime.py'),
        '--runtime',str(runtime),'--sha256',digest,'--fixture-root',str(tmp_path/'fixture'),'--case',case],
        capture_output=True,text=True,timeout=120)
    assert process.returncode==0,process.stdout+process.stderr
    import json
    proof=json.loads(process.stdout)
    assert proof['source_unchanged'] and proof['runtime_sha256']==digest
    assert proof['capabilities']['safe_reference_contract_version']==1
    assert proof['capabilities']['snapshot_contract_version']==1


def test_public_consumer_rejects_hash_before_import(tmp_path):
    runtime=tmp_path/'fake.pyz';runtime.write_bytes(b'not approved')
    done=subprocess.run([sys.executable,'-I','-S','-B',str(PROJECT_ROOT/'docs/examples/verify_release_runtime.py'),
        '--runtime',str(runtime),'--sha256','0'*64,'--fixture-root',str(tmp_path/'fixture'),'--case','clean'],
        capture_output=True,text=True)
    assert done.returncode!=0 and not (tmp_path/'fixture').exists()


@pytest.mark.parametrize('operation',['none','socket','subprocess'])
def test_probe_separates_host_metadata_and_keeps_export_guard(tmp_path,operation):
    artifacts=tmp_path/'artifacts';build_release(artifacts)
    runtime=artifacts/f'patchharbor-{__version__}.pyz'
    digest=sha256(runtime.read_bytes()).hexdigest();output=tmp_path/'export';output.mkdir()
    bootstrap=r'''
from hashlib import sha256
import json, platform, socket, subprocess, sys
from pathlib import Path
operation=sys.argv.pop(1)
runtime,expected=sys.argv[1:3]
assert sha256(Path(runtime).read_bytes()).hexdigest()==expected
sys.path.insert(0,runtime)
from patchharbor import api
metadata=[False];attempted=[False];events=[]
original_system=platform.system
def local_host_metadata():
    platform.system=original_system
    socket.gethostname()  # Windows platform.uname performs this local lookup.
    metadata[0]=True
    return original_system()
platform.system=local_host_metadata
def record(event,args):
    if event in ('socket.__new__','subprocess.Popen'):events.append(event)
sys.addaudithook(record)
if operation!='none':
    def external_export(*args,**kwargs):
        attempted[0]=True
        if operation=='socket':
            with socket.socket():pass
        else:
            subprocess.run([sys.executable,'-I','-S','-c','raise SystemExit(97)'],check=False)
        raise RuntimeError('export guard allowed the injected external operation')
    api.export_runtime=external_export
blocked=False
try:exec(compile(sys.stdin.read(),'distribution-probe','exec'))
except AssertionError:
    if operation=='none':raise
    blocked=True
print(json.dumps({'metadata_prepared':metadata[0],'operation_attempted':attempted[0],
                  'events':events,'blocked':blocked}))
'''
    done=subprocess.run([sys.executable,'-I','-S','-B','-c',bootstrap,operation,
        str(runtime),digest,str(output),__version__,'pyz'],input=PROBE,
        env={**os.environ,'PATH':''},cwd=tmp_path,capture_output=True,text=True,timeout=120)
    assert done.returncode==0,done.stdout+done.stderr
    documents=[json.loads(line) for line in done.stdout.splitlines()]
    audit=documents[-1]
    if operation=='none':
        assert audit['metadata_prepared'] and not audit['blocked'] and not audit['operation_attempted']
        assert documents[0]['runtime']['sha256']==digest
        assert (output/'api'/runtime.name).read_bytes()==runtime.read_bytes()
        assert (output/'cli'/runtime.name).read_bytes()==runtime.read_bytes()
    else:
        assert audit['blocked'] and audit['operation_attempted']
        assert ('socket.__new__' if operation=='socket' else 'subprocess.Popen') in audit['events']
        assert not list(output.rglob('*.pyz'))


def test_windows_checkout_preserves_canonical_release_runtime(tmp_path):
    from tests.registration_support import create_repository,git
    repo=create_repository(tmp_path/'repository',with_commit=False)
    git(repo,'config','core.autocrlf','false')
    for name in ('.gitattributes','pyproject.toml','README.md','LICENSE','CHAT_INSTRUCTIONS.md',
                 'MANIFEST.in','build_backend.py'):
        (repo/name).write_bytes((PROJECT_ROOT/name).read_bytes())
    for name in ('src','docs','scripts','tools'):
        shutil.copytree(PROJECT_ROOT/name,repo/name,ignore=shutil.ignore_patterns(
            '__pycache__','*.pyc','*.pyo','*.egg-info','_runtime','_runtime_identity.py','_pyz_identity.py'))
    (repo/'control.txt').write_bytes(b'ordinary checkout text\n')
    git(repo,'add','--all')
    checkout=tmp_path/'windows-checkout';checkout.mkdir()
    git(repo,'-c','core.autocrlf=true','checkout-index','--all','--prefix='+checkout.as_posix()+'/')
    assert (checkout/'control.txt').read_bytes()==b'ordinary checkout text\r\n'
    original=tmp_path/'original-artifacts';converted=tmp_path/'checkout-artifacts'
    build_release(original);build_release(converted,root=checkout)
    name=f'patchharbor-{__version__}.pyz'
    assert (converted/name).read_bytes()==(original/name).read_bytes()
