"""Explicit stdlib bootstrap, finite extraction and in-process origin checks."""
from dataclasses import replace
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
from zipfile import ZipFile, ZipInfo

import pytest

from scripts import pyz_bootstrap as bootstrap
from patchharbor import api, runtime_pyz as pyz
from tests.result_pyz_support import attach_pyz
from tests.result_runtime_support import edit_metadata
from tests.test_pack_api import request_files
from tests.test_runtime_pyz import inputs, prepared
from tests.test_reference_validation import reference_entries, write_reference, edit_document


@pytest.fixture
def reference(tmp_path):
    payloads = inputs()
    payloads['patchharbor/api.py'] = b'raise AssertionError("described code must not run during assessment")\n'
    recipe, _, raw = prepared(payloads)
    files, _ = reference_entries(handoff=True)
    files = attach_pyz(files, raw)
    path = tmp_path/'result.zip';write_reference(path,files)
    return path, files, raw


def trusted(path):
    return bootstrap.assess(path,trusted_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success(reference, tmp_path, monkeypatch):
    path, files, raw = reference
    before = {p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs): pytest.fail('precheck imported or executed bundled code')
    monkeypatch.setattr(bootstrap.importlib,'import_module',forbidden)
    monkeypatch.setattr(subprocess,'Popen',forbidden);monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(socket,'socket',forbidden)
    result = bootstrap.assess(path)
    assert result.scope == 'runtime_descriptor_precheck' and result.full_reference_valid is False
    assert result.pyz_bytes == raw and not result.source_trusted
    with pytest.raises(bootstrap.BootstrapUnavailable): bootstrap.prepare(result,tmp_path/'not-created')
    assert {p:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_one_controlled_extraction_needs_no_installer_or_process(reference,tmp_path,monkeypatch):
    path, _, raw = reference
    assessed = trusted(path)
    def forbidden(*args,**kwargs):pytest.fail('bootstrap attempted install or execution')
    monkeypatch.setattr(subprocess,'run',forbidden);monkeypatch.setattr(subprocess,'Popen',forbidden)
    monkeypatch.setattr(socket,'socket',forbidden)
    result = bootstrap.prepare(assessed,tmp_path/'private')
    assert list(result.path.parent.iterdir()) == [result.path]
    assert result.path.read_bytes() == raw
    assert result.assessment.reference_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):bootstrap.prepare(assessed,result.path.parent)


@pytest.mark.parametrize('fault',['outer_marker','boolean_format','metadata_hash','artifact_hash',
                                  'metadata_size','artifact_type','artifact_path','second_artifact',
                                  'descriptor_disagrees','requirement','profile','unsafe_path','symlink','duplicate'])
def test_corrupt_or_ambiguous_bootstrap_data_is_rejected_without_code(reference,tmp_path,monkeypatch,fault):
    path,files,_ = reference
    metadata = json.loads(files['runtime/runtime.json']);artifact_path=metadata['artifact']['path']
    if fault=='outer_marker':edit_document(files,'manifest.json',lambda d:d.update(marker='wrong'))
    elif fault=='boolean_format':edit_document(files,'manifest.json',lambda d:d.update(format_version=True))
    elif fault=='metadata_hash':files['runtime/runtime.json'] += b' '
    elif fault=='artifact_hash':files[artifact_path] += b'changed'
    elif fault=='metadata_size':edit_document(files,'manifest.json',lambda d:d['runtime']['metadata'].update(size=0))
    elif fault=='artifact_type':edit_document(files,'manifest.json',lambda d:d['runtime']['artifact'].update(type='wheel'))
    elif fault=='artifact_path':edit_metadata(files,lambda d:d['artifact'].update(path='runtime/../evil.pyz'))
    elif fault=='second_artifact':files['runtime/second.pyz']=files[artifact_path]
    elif fault=='descriptor_disagrees':edit_metadata(files,lambda d:d['artifact'].update(sha256='0'*64))
    elif fault=='requirement':edit_metadata(files,lambda d:d.update(requires_python='>=3.8'))
    elif fault=='profile':edit_metadata(files,lambda d:d.update(profile='includes-watcher'))
    elif fault=='unsafe_path':files['../outside']=b'escape'
    write_reference(path,files)
    if fault in ('symlink','duplicate'):
        with ZipFile(path,'a') as archive:
            info=ZipInfo('unsafe-link' if fault=='symlink' else 'context.json')
            info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16 if fault=='symlink' else 0o100644<<16
            archive.writestr(info,b'linked-or-duplicate')
    with pytest.raises((ValueError,KeyError)):trusted(path)
    assert not (tmp_path/'outside').exists()


def test_source_hash_mismatch_never_prepares_or_imports(reference):
    with pytest.raises(ValueError):bootstrap.assess(reference[0],trusted_source_sha256='0'*64)


@pytest.mark.parametrize('fault',['size','count'])
def test_budgets_precede_zipfile_inventory_allocation(reference,monkeypatch,fault):
    path,_,_=reference
    if fault=='size':monkeypatch.setattr(bootstrap,'MAX_INPUT',len(path.read_bytes())-1)
    else:monkeypatch.setattr(bootstrap,'MAX_ENTRIES',1)
    monkeypatch.setattr(bootstrap,'ZipFile',lambda *a,**k:pytest.fail('oversized archive reached ZipFile'))
    with pytest.raises(ValueError):trusted(path)


@pytest.mark.parametrize('version',[1,2])
def test_legacy_result_selects_explicit_previous_path(reference,version):
    path,files,_=reference
    edit_document(files,'manifest.json',lambda d:d.update(format_version=version));write_reference(path,files)
    with pytest.raises(bootstrap.BootstrapUnavailable):trusted(path)


def test_unavailable_runtime_does_not_erase_or_repair_the_original_result(reference):
    path,files,_=reference
    files=attach_pyz(files,None);write_reference(path,files);before=path.read_bytes()
    with pytest.raises(bootstrap.BootstrapUnavailable):trusted(path)
    assert path.read_bytes()==before


def test_old_python_refuses_execution_without_a_preparation_directory(reference,tmp_path,monkeypatch):
    assessed=trusted(reference[0]);monkeypatch.setattr(bootstrap.sys,'version_info',(3,11))
    with pytest.raises(bootstrap.BootstrapUnavailable):bootstrap.prepare(assessed,tmp_path/'unused')
    assert not (tmp_path/'unused').exists()


def test_foreign_already_imported_core_is_kept_and_conflict_is_reported(reference,tmp_path):
    assessed=trusted(reference[0]);runtime=bootstrap.prepare(assessed,tmp_path/'private')
    modules={name:module for name,module in sys.modules.items() if name=='patchharbor' or name.startswith('patchharbor.')}
    paths=list(sys.path)
    with pytest.raises(bootstrap.BootstrapUnavailable):bootstrap.import_api(runtime)
    assert sys.path==paths
    assert all(sys.modules[name] is module for name,module in modules.items())


def test_changed_prepared_file_is_rejected_before_import(reference,tmp_path,monkeypatch):
    runtime=bootstrap.prepare(trusted(reference[0]),tmp_path/'private')
    runtime.path.write_bytes(runtime.path.read_bytes()+b'changed')
    monkeypatch.setattr(bootstrap.importlib,'import_module',lambda *a,**k:pytest.fail('changed PYZ imported'))
    with pytest.raises(ValueError):bootstrap.import_api(runtime)


@pytest.mark.packaging
def test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses(
    built_result_source,request_files,tmp_path,
):
    recipe=pyz.parse_recipe((built_result_source/pyz.RECIPE_PATH).read_bytes())
    raw=pyz.materialize(recipe,lambda name,size:(built_result_source/name).read_bytes())
    files,_=reference_entries(handoff=True)
    reference=tmp_path/'future-result.zip';write_reference(reference,attach_pyz(files,raw))
    outside=tmp_path/'outside';outside.mkdir()
    (outside/'patchharbor.py').write_text('raise AssertionError("foreign CWD import")\n')
    helper=Path(bootstrap.__file__).resolve()
    script='''
import hashlib, importlib.util, json, os, socket, subprocess, sys
from pathlib import Path
helper, reference, workspace, contents, original, output = map(Path, sys.argv[1:])
spec=importlib.util.spec_from_file_location('reviewed_bootstrap',helper)
bootstrap=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bootstrap;spec.loader.exec_module(bootstrap)
assert not any(name=='patchharbor' or name.startswith('patchharbor.') for name in sys.modules)
def forbidden(*a,**k):raise AssertionError('bootstrap/runtime started an external operation')
subprocess.run=subprocess.Popen=socket.socket=forbidden
os.environ['PATH']=''
assessment=bootstrap.assess(reference,trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
assert assessment.scope=='runtime_descriptor_precheck' and not assessment.full_reference_valid
runtime=bootstrap.prepare(assessment,workspace)
api=bootstrap.import_api(runtime)
assert bootstrap.import_api(runtime) is api
packed=api.pack_patch(contents,reference_bundle=original,entrypoint='run.sh',output_directory=output)
assert api.inspect_patch(packed.path).package_sha256==packed.package_sha256
assert api.validate_patch(packed.path,reference_bundle=original).binding_matches
assert str(runtime.path) in sys.path
assert 'patchharbor_watcher' not in sys.modules
print(json.dumps({'package_sha256':packed.package_sha256,'path':str(packed.path),
                  'pyz_sha256':assessment.artifact_sha256,'origin':api.__file__}))
'''
    result=subprocess.run([sys.executable,'-I','-S','-B','-c',script,str(helper),str(reference),
                           str(tmp_path/'runtime'),*(str(p) for p in request_files)],
                          cwd=outside,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads(result.stdout)
    assert report['pyz_sha256']==hashlib.sha256(raw).hexdigest()
    assert api.validate_patch(report['path'],reference_bundle=request_files[1]).binding_matches


@pytest.mark.packaging
@pytest.mark.parametrize('isolated',[False,True])
def test_direct_pyz_cli_pack_inspect_validate_outside_checkout(built_result_source,request_files,tmp_path,isolated):
    recipe=pyz.parse_recipe((built_result_source/pyz.RECIPE_PATH).read_bytes())
    raw=pyz.materialize(recipe,lambda name,size:(built_result_source/name).read_bytes())
    runtime=tmp_path/recipe.pyz_name;runtime.write_bytes(raw)
    outside=tmp_path/'outside';outside.mkdir()
    (outside/'patchharbor.py').write_bytes(b'raise AssertionError("foreign CWD")\n')
    environment={key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')}
    environment['PATH']='';environment['PYTHONPATH']=str(outside)
    prefix=[sys.executable, *(['-I','-S','-B'] if isolated else []), str(runtime)]
    contents,reference,output=request_files
    def run(*arguments):
        result=subprocess.run([*prefix,*map(str,arguments),'--json'],cwd=outside,env=environment,
                              capture_output=True,text=True,timeout=90)
        assert result.returncode==0,result.stdout+result.stderr
        document=json.loads(result.stdout);assert document['success'] is True;return document['result']
    packed=run('pack',contents,'--reference-bundle',reference,'--entrypoint','run.sh','--output-dir',output)
    inspected=run('inspect',packed['path'])
    validated=run('validate',packed['path'],'--reference-bundle',reference)
    assert inspected['package_sha256']==packed['package_sha256']
    assert validated['binding_matches'] and validated['scope']=='reference'
    assert validated['reference_sha256']==hashlib.sha256(reference.read_bytes()).hexdigest()
