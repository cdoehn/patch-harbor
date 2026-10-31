"""Actual built distribution/PYZ: public-only snapshot -> transport -> pack/validate."""
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

from patchharbor import runtime_pyz as pyz
from tests.snapshot_support import produce_case

pytestmark = pytest.mark.packaging


@pytest.mark.parametrize('route',['wheel','pyz'])
def test_built_artifact_public_transport_without_git_shell_network_or_checkout(
        built_result_source,prepared_result_producer,tmp_path,monkeypatch,route):
    case=produce_case(tmp_path,monkeypatch)
    recipe=pyz.parse_recipe((built_result_source/pyz.RECIPE_PATH).read_bytes())
    raw=pyz.materialize(recipe,lambda name,size:(built_result_source/name).read_bytes())
    runtime=tmp_path/recipe.pyz_name;runtime.write_bytes(raw)
    outside=tmp_path/'python-only';outside.mkdir()
    reference=outside/'reference.zip';shutil.copyfile(case.result,reference)
    reference_sha=hashlib.sha256(reference.read_bytes()).hexdigest()
    with ZipFile(reference) as z:
        assert z.read('runtime/'+recipe.pyz_name)==raw
    expected={layer:{name:{'mode':mode,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
                       for name,(mode,data) in files.items()}
              for layer,files in case.expected.items()}
    (outside/'expected.json').write_text(json.dumps(expected))
    source=Path(__file__).resolve().parents[1]
    shutil.copyfile(source/'docs/examples/snapshot_transport.py',outside/'example.py')
    (outside/'approved.sh').write_text('#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    (outside/'output').mkdir()
    # The original repository can change after export; the example must only use
    # bytes in the independently expected Result, never its foreign live path.
    (case.repository/'tracked.txt').write_bytes(b'changed after export')
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONHOME','PYTHONPATH')}
    environment['PATH']=''
    selected=str(runtime if route=='pyz' else built_result_source)
    process=subprocess.run([sys.executable,'-I','-S','-B','-c',r'''
import hashlib,json,os,runpy,sys
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
root=Path.cwd();selected=sys.argv[1];checkout=Path(sys.argv[2]);expected_sha=sys.argv[3]
def audit(event,args):
    if event.startswith(('subprocess.','socket.','os.exec','os.spawn')) or event=='os.system':
        raise AssertionError('external work: '+event)
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=Path(os.fsdecode(args[0])).absolute()
        if path==checkout or checkout in path.parents:
            raise AssertionError('hidden source checkout dependency')
sys.addaudithook(audit)
sys.path.insert(0,selected)
from patchharbor import api
assert api.__file__.startswith(selected+os.sep),api.__file__
assert api.integration_capabilities().snapshot_contract_version==1
assert api.integration_capabilities().guarded_apply_contract_version==1
module=runpy.run_path(str(root/'example.py'))
snapshot,packed=module['prepare_transport'](root/'reference.zip',expected_result_sha256=expected_sha,
    trusted_entrypoint=root/'approved.sh',workspace=root/'workspace',output_directory=root/'output')
expected=json.loads((root/'expected.json').read_bytes())
for name,values in expected.items():
    observed={p:{'mode':f.mode,'sha256':f.sha256,'size':f.size} for p,f in getattr(snapshot,name).files.items()}
    assert observed==values,(name,observed,values)
validated=api.validate_patch(packed.path,reference_bundle=root/'reference.zip')
assert validated.binding_matches and validated.reference_sha256==snapshot.sha256==expected_sha
assert api.inspect_patch(packed.path)==validated.inspection
with ZipFile(packed.path) as archive:
    with ZipFile(BytesIO(archive.read('captured-project.zip'))) as project:
        assert set(project.namelist())==set(snapshot.effective.files)
        for name,file in snapshot.effective.files.items():
            assert project.read(name)==file.content
            assert project.getinfo(name).external_attr>>16==int(file.mode,8)
assert 'patchharbor_watcher' not in sys.modules
assert not any('site-packages' in p or 'dist-packages' in p for p in sys.path)
print(json.dumps({'origin':api.__file__,'package':str(packed.path),'sha256':packed.package_sha256,
                  'reference_sha256':snapshot.sha256,'capability_contract':1}))
''',selected,str(source),reference_sha],cwd=outside,env=environment,capture_output=True,text=True)
    assert process.returncode==0,process.stdout+process.stderr
    proof=json.loads(process.stdout)
    assert proof['origin'].startswith(selected+os.sep)
    assert proof['reference_sha256']==reference_sha
    assert proof['sha256']==hashlib.sha256(Path(proof['package']).read_bytes()).hexdigest()
    assert hashlib.sha256(reference.read_bytes()).hexdigest()==reference_sha
    (outside/'transport-proof.json').write_text(json.dumps({'route':route,'pyz_sha256':hashlib.sha256(raw).hexdigest(),
        'pyz_profile':pyz.PROFILE,'version':recipe.version,'python':sys.version,'evidence':proof},indent=2))


@pytest.mark.parametrize('route',['wheel','pyz'])
def test_guarded_host_apply_runs_from_actual_built_artifact(
        built_result_source,prepared_result_producer,tmp_path,monkeypatch,route):
    from patchharbor import api
    from tests.registration_support import create_repository,set_isolated_user_environment
    from tests.platform_support import native_script,native_value
    set_isolated_user_environment(monkeypatch,tmp_path/'user')
    repo=create_repository(tmp_path/'host');api.register(repo)
    exchange=tmp_path/'exchange';api.configure_exchange_directory(exchange,repository=repo)
    reference=api.bundle(repo).path
    recipe=pyz.parse_recipe((built_result_source/pyz.RECIPE_PATH).read_bytes())
    runtime=tmp_path/recipe.pyz_name
    raw=pyz.materialize(recipe,lambda name,size:(built_result_source/name).read_bytes());runtime.write_bytes(raw)
    contents=tmp_path/'contents';contents.mkdir()
    entrypoint=native_value('run.sh','run.ps1')
    body=native_script("printf 'artifact' > executed", "[IO.File]::WriteAllText('executed','artifact')")
    (contents/entrypoint).write_text(body);(contents/'payload').write_bytes(b'built host payload')
    outside=tmp_path/'outside';outside.mkdir()
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONHOME','PYTHONPATH')}
    selected=str(runtime if route=='pyz' else built_result_source)
    process=subprocess.run([sys.executable,'-I','-S','-B','-c',r'''
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from patchharbor import api
packed=api.pack_patch(sys.argv[2],reference_bundle=sys.argv[3],entrypoint=sys.argv[7],output_directory=sys.argv[6])
called=[]
def accept(facts):
    called.append(facts)
    assert facts.inspection.package_sha256==packed.package_sha256
    assert facts.context.repository_path.value==Path(sys.argv[4]).resolve()
    assert facts.contents['payload']==b'built host payload'
    assert hashlib.sha256(facts.contents[facts.inspection.entrypoint]).hexdigest()==sys.argv[5]
    assert not (Path(sys.argv[4])/'executed').exists()
    return True
report=api.apply_guarded(packed.path,expected_sha256=packed.package_sha256,expected_repository=sys.argv[4],admission=accept)
assert report.success and len(called)==1,report
snapshot=api.read_result_snapshot(report.result_bundle.path)
assert snapshot.primary_result.entrypoint_exit_code==0
assert snapshot.effective.files['payload'].content==b'built host payload'
assert snapshot.effective.files['executed'].content==b'artifact'
print(json.dumps({'result':str(report.result_bundle.path),'runtime_sha256':snapshot.runtime.artifact_sha256,'origin':api.__file__}))
''',selected,str(contents),str(reference),str(repo),hashlib.sha256((contents/entrypoint).read_bytes()).hexdigest(),str(exchange),entrypoint],
        cwd=outside,env=environment,capture_output=True,text=True,timeout=120)
    assert process.returncode==0,process.stdout+process.stderr
    evidence=json.loads(process.stdout)
    assert evidence['origin'].startswith(selected+os.sep)
    assert evidence['runtime_sha256']==hashlib.sha256(raw).hexdigest()
    assert (repo/'executed').read_bytes()==b'artifact'


def test_public_example_refuses_a_rebound_reference(tmp_path,monkeypatch):
    import runpy
    from patchharbor import api
    from tests.reference_support import reference_entries,write_reference
    module=runpy.run_path(str(Path(__file__).resolve().parents[1]/'docs/examples/snapshot_transport.py'))
    files,_=reference_entries();reference=tmp_path/'reference.zip';write_reference(reference,files)
    expected=hashlib.sha256(reference.read_bytes()).hexdigest()
    script=tmp_path/'run.sh';script.write_text('#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    output=tmp_path/'unwatched';output.mkdir()
    original=api.pack_patch;observed=[]
    def exchange_reference(*args,**kwargs):
        changed,_=reference_entries(dirty=True);changed['changes/unstaged.patch']=b''
        write_reference(reference,changed)
        result=original(*args,**kwargs);observed.append(result);return result
    monkeypatch.setattr(api,'pack_patch',exchange_reference)
    with pytest.raises(RuntimeError):
        module['prepare_transport'](reference,expected_result_sha256=expected,
            trusted_entrypoint=script,workspace=tmp_path/'fresh',output_directory=output)
    assert len(observed)==1 and observed[0].reference_sha256!=expected
    assert set(output.iterdir())=={observed[0].path}  # retained private diagnostic, not delivered
