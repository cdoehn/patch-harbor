"""Reader-first Result 3: closed PYZ data, strict references and shared budgets."""
from dataclasses import FrozenInstanceError, replace
import hashlib
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from patchharbor import api, result_pyz, runtime_pyz as pyz
from patchharbor.exit_status import exit_code_for_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import (
    read_result_reference, capture_result_reference, parse_result_payloads,
    _parse_repository_payloads, result_member_path,
)
from patchharbor.zip_payloads import read_zip_payload_bytes
from tests.result_pyz_support import attach_pyz
from tests.result_runtime_support import descriptor, edit_metadata
from tests.test_reference_validation import bound_package, reference_entries, write_reference, edit_document
from tests.test_runtime_pyz import inputs, prepared


@pytest.fixture(scope='module')
def canonical():
    payloads = inputs()
    payloads['patchharbor/api.py'] = b'raise AssertionError("Result reader executed described API")\n'
    return prepared(payloads)[2]


def format3(raw, **options):
    files,binding = reference_entries(handoff=True,**options)
    return attach_pyz(files,raw), binding


@pytest.mark.parametrize('status',['embedded','unavailable'])
@pytest.mark.parametrize('kind,dirty', [('bundle',False),('success',False),('success',True),
                                       ('failure',True),('dry_run',False),('mismatch',False),
                                       ('timeout',True),('interrupted',True)])
def test_new_reference_keeps_actual_state_and_explicit_full_runtime_facts(canonical,tmp_path,status,kind,dirty):
    files,binding = format3(canonical if status=='embedded' else None,kind=kind,dirty=dirty)
    path=tmp_path/'result.zip';write_reference(path,files)
    facts,digest=read_result_reference(path)
    assert facts.format_version==3 and facts.runtime.status==status
    assert facts.context.dirty is dirty
    assert digest==hashlib.sha256(path.read_bytes()).hexdigest()
    assert capture_result_reference(path).facts==facts
    for key,value in binding.items(): assert str(getattr(facts.context,key))==value
    patch=tmp_path/'patch.zip';bound_package(patch,binding)
    checked=api.validate_patch(patch,reference_bundle=path)
    assert checked.binding_matches and checked.reference_sha256==digest
    assert checked.context.base_commit==facts.context.base_commit
    with pytest.raises(FrozenInstanceError):facts.runtime.status='forged'
    if status=='embedded':
        assert facts.runtime.artifact.type=='pyz'
        assert facts.runtime.artifact.sha256==hashlib.sha256(canonical).hexdigest()
        assert facts.runtime.profile==pyz.PROFILE
        assert facts.runtime.operations==('inspect_patch','validate_patch','pack_patch')
        assert facts.runtime.result_formats==(1,2,3)
        assert not hasattr(facts.runtime,'wheel')
    else: assert facts.runtime.artifact is None and facts.runtime.profile is None


@pytest.mark.parametrize('reason',sorted(result_pyz.UNAVAILABLE_REASONS))
@pytest.mark.parametrize('known',[False,True])
def test_unavailable_runtime_preserves_known_or_unknown_producer_data(tmp_path,reason,known):
    files,_=format3(None)
    edit_metadata(files,lambda d:d.update(reason=reason,version='1.2.1' if known else None,
                                         requires_python='>=3.12' if known else None))
    edit_document(files,'manifest.json',lambda d:d['runtime'].update(reason=reason))
    path=tmp_path/'result.zip';write_reference(path,files)
    runtime=read_result_reference(path)[0].runtime
    assert runtime.reason==reason and runtime.artifact is None
    assert runtime.operations==() and runtime.content_id is None
    assert runtime.version==('1.2.1' if known else None)


@pytest.mark.parametrize('fault',[
    'missing_metadata','missing_pyz','metadata_hash','pyz_hash','second_runtime','extra_root',
    'outer_unknown','metadata_unknown','metadata_version_bool','metadata_version_old',
    'result_version_bool','result_version_future','metadata_bool_size','artifact_bool_size',
    'artifact_float_size','wrong_type','wheel_field','wrong_distribution','wrong_version',
    'wrong_python','wrong_content','wrong_algorithm','wrong_profile','dependencies',
    'wrong_commit','bool_recipe_version','unknown_provenance','unknown_capability',
    'missing_pack','bool_patch_format','missing_format3','future_format','unknown_capability_field',
    'inconsistent_status','missing_handoff','foreign_path','empty_pyz','extra_tags',
])
def test_corrupt_format3_never_becomes_a_full_native_reference(canonical,tmp_path,fault):
    files,binding=format3(canonical);doc=json.loads(files['runtime/runtime.json']);name=doc['artifact']['path']
    if fault=='missing_metadata':files.pop('runtime/runtime.json')
    elif fault=='missing_pyz':files.pop(name)
    elif fault=='metadata_hash':files['runtime/runtime.json'] += b' '
    elif fault=='pyz_hash':files[name] += b'corrupt'
    elif fault=='second_runtime':files['runtime/extra.whl']=b'forbidden'
    elif fault=='extra_root':files['unknown']=b'forbidden'
    elif fault=='outer_unknown':edit_document(files,'manifest.json',lambda d:d['runtime'].update(unknown=1))
    elif fault=='metadata_bool_size':edit_document(files,'manifest.json',lambda d:d['runtime']['metadata'].update(size=True))
    elif fault=='artifact_bool_size':edit_document(files,'manifest.json',lambda d:d['runtime']['artifact'].update(size=True))
    elif fault=='artifact_float_size':edit_metadata(files,lambda d:d['artifact'].update(size=float(len(canonical))))
    elif fault=='wrong_type':edit_metadata(files,lambda d:d['artifact'].update(type='wheel'))
    elif fault=='wheel_field':edit_document(files,'manifest.json',lambda d:d['runtime'].update(wheel=None))
    elif fault=='wrong_commit':edit_metadata(files,lambda d:d['provenance'].update(source_commit='a'*40))
    elif fault=='bool_recipe_version':edit_metadata(files,lambda d:d['provenance'].update(recipe_format_version=True))
    elif fault=='unknown_provenance':edit_metadata(files,lambda d:d['provenance'].update(unknown=1))
    elif fault=='unknown_capability':edit_metadata(files,lambda d:d['capabilities'].update(operations=['execute']))
    elif fault=='missing_pack':edit_metadata(files,lambda d:d['capabilities'].update(operations=['inspect_patch','validate_patch']))
    elif fault=='bool_patch_format':edit_metadata(files,lambda d:d['capabilities'].update(patch_formats=[True]))
    elif fault=='missing_format3':edit_metadata(files,lambda d:d['capabilities'].update(result_formats=[1,2]))
    elif fault=='future_format':edit_metadata(files,lambda d:d['capabilities'].update(result_formats=[1,2,3,4]))
    elif fault=='unknown_capability_field':edit_metadata(files,lambda d:d['capabilities'].update(unknown=1))
    elif fault=='missing_handoff':files.pop('CHAT_INSTRUCTIONS.md');files.pop('environment.json')
    elif fault.startswith('result_version_'):
        edit_document(files,'manifest.json',lambda d:d.update(format_version=True if fault.endswith('bool') else 4))
    elif fault in ('foreign_path','empty_pyz'):
        item={**doc['artifact'],'path':'../outside.pyz'} if fault=='foreign_path' else dict(type='pyz',**descriptor(name,b''))
        if fault=='empty_pyz':files[name]=b''
        edit_metadata(files,lambda d:d.update(artifact=item))
        edit_document(files,'manifest.json',lambda d:d['runtime'].update(artifact=item))
    else:
        changes={'metadata_unknown':{'unknown':1},'metadata_version_bool':{'format_version':True},
                 'metadata_version_old':{'format_version':1},'wrong_distribution':{'distribution':'foreign'},
                 'wrong_version':{'version':'9.9'},'wrong_python':{'requires_python':'>=3.99'},
                 'wrong_content':{'content_id':'0'*64},'wrong_algorithm':{'content_id_algorithm':'legacy'},
                 'wrong_profile':{'profile':'with-watcher'},'dependencies':{'runtime_dependencies':['requests']},
                 'inconsistent_status':{'status':'unavailable'},'extra_tags':{'tags':['py3-none-any']}}
        edit_metadata(files,lambda d:d.update(changes[fault]))
    path=tmp_path/'result.zip';write_reference(path,files)
    patch=tmp_path/'patch.zip';bound_package(patch,binding)
    with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,reference_bundle=path)
    assert int(exit_code_for_error(caught.value))==4


@pytest.mark.parametrize('fault',['unknown_reason','no_warning','hash_claim','profile_claim','capability_claim','extra_pyz'])
def test_unavailable_is_not_a_permissive_repair_contract(tmp_path,fault):
    files,_=format3(None)
    if fault=='no_warning':edit_document(files,'logs/run.json',lambda d:d.update(warnings=[]))
    elif fault=='extra_pyz':files['runtime/extra.pyz']=b'extra'
    else:
        change={'unknown_reason':{'reason':'invented'},'hash_claim':{'content_id':'0'*64},
                'profile_claim':{'profile':pyz.PROFILE},'capability_claim':{'capabilities':{}}}[fault]
        edit_metadata(files,lambda d:d.update(change))
        if fault=='unknown_reason':edit_document(files,'manifest.json',lambda d:d['runtime'].update(reason='invented'))
    path=tmp_path/'result.zip';write_reference(path,files)
    with pytest.raises(api.PatchHarborError):read_result_reference(path)


def payloads(files):
    stream=BytesIO()
    with ZipFile(stream,'w') as archive:
        for name,raw in files.items():archive.writestr(name,raw)
    return read_zip_payload_bytes(stream.getvalue(),path_normalizer=result_member_path)


def test_shared_outer_inner_budget_is_exact_and_precedes_unbounded_expansion(canonical):
    files,_=format3(canonical);entries=payloads(files)
    with ZipFile(BytesIO(canonical)) as archive:inner=sum(info.file_size for info in archive.infolist())
    maximum=sum(len(raw) for raw in files.values())+inner
    policy=replace(DEFAULT_RESOURCE_POLICY,max_zip_total_bytes=maximum)
    assert parse_result_payloads(entries,resource_policy=policy).format_version==3
    with pytest.raises(ValueError):parse_result_payloads(entries,resource_policy=replace(policy,max_zip_total_bytes=maximum-1))


def test_private_diagnostic_fallback_retains_every_nonruntime_requirement(canonical):
    files,_=format3(canonical);files['runtime/runtime.json']=b'damaged optional runtime'
    assert _parse_repository_payloads(payloads(files)).format_version==3
    with pytest.raises(ValueError):parse_result_payloads(payloads(files))
    files['base/tracked.txt'] += b'changed snapshot'
    with pytest.raises(ValueError):_parse_repository_payloads(payloads(files))


def test_pack_uses_full_reader_and_never_the_private_diagnostic_fallback(canonical,tmp_path,monkeypatch):
    from patchharbor import result_reader
    files,_=format3(canonical);path=tmp_path/'result.zip';write_reference(path,files)
    contents=tmp_path/'contents';contents.mkdir();(contents/'run.sh').write_bytes(b'#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    output=tmp_path/'output';output.mkdir()
    monkeypatch.setattr(result_reader,'_parse_repository_payloads',lambda *a,**k:pytest.fail('pack used weak fallback'))
    packed=api.pack_patch(contents,reference_bundle=path,entrypoint='run.sh',output_directory=output)
    assert packed.validation.binding_matches
    files['runtime/runtime.json'] += b' ';write_reference(path,files)
    with pytest.raises(api.PatchHarborError):api.pack_patch(contents,reference_bundle=path,entrypoint='run.sh',output_directory=output)
    assert list(output.iterdir())==[packed.path]
