"""Failure contracts for untrusted complete references and stable byte ownership."""
from dataclasses import replace
import hashlib
from io import StringIO
import json
from pathlib import Path

import pytest

from patchharbor import api
from patchharbor.cli import main
from patchharbor.exit_status import exit_code_for_error
from patchharbor.patch_inspection import validate_patch
from patchharbor.platform.filesystem import FileChangedDuringRead
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
import patchharbor.result_reader as reader
from tests.test_reference_validation import reference_entries, write_reference, bound_package, edit_document


INVALID_FIELDS = [
    ('manifest.json', field, value) for field, values in {
        'format_version': [True, '1', None, 2], 'dirty': [0, None], 'dry_run': [0, True],
        'entrypoint_started': [0, True], 'execution_present': [0, True],
        'run_id': ['bad', 3], 'created_at': ['bad', None],
        'base_entries': [None, {}, [None]], 'untracked_entries': [None, {}],
        'result_bundle_status': ['failed'], 'primary_result': ['timeout'],
    }.items() for value in values
] + [
    ('logs/run.json', field, value) for field, values in {
        'duration_seconds': [True, -1, float('nan'), float('inf'), '1'],
        'ended_at': ['2025-01-01T00:00:00Z', 'invalid', '2026-10-03T12:00:00'],
        'repository_path': [None, '', 'relative/repo', 'C:relative', '/bad\x00path'],
        'repository_resolved': [False, 1], 'warnings': [{}, [1]],
        'process_exit_code': [False, 7], 'operation': ['other', None],
        'primary_result': [{}, None], 'result_bundle': [{}, None],
    }.items() for value in values
]


@pytest.mark.parametrize('name,field,value', INVALID_FIELDS)
def test_invalid_metadata_is_an_input_error(tmp_path, name, field, value):
    files, binding = reference_entries()
    edit_document(files, name, lambda d: d.update({field: value}))
    ref = tmp_path / 'result.zip'; write_reference(ref, files)
    patch = tmp_path / 'patch.zip'; bound_package(patch, binding)
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, reference_bundle=ref)
    assert int(exit_code_for_error(caught.value)) == 4


@pytest.mark.parametrize('name', ['manifest.json', 'context.json', 'logs/run.json'])
@pytest.mark.parametrize('fault', ['extra_key', 'missing_binding', 'duplicate', 'bom', 'trailing', 'invalid_utf8'])
def test_closed_json_documents(tmp_path, name, fault):
    files, _ = reference_entries()
    if fault == 'extra_key': edit_document(files, name, lambda d: d.update(future=None))
    elif fault == 'missing_binding': edit_document(files, name, lambda d: d.pop('repo_id'))
    elif fault == 'duplicate': files[name] = b'{"repo_id":"wrong",' + files[name][1:]
    elif fault == 'bom': files[name] = b'\xef\xbb\xbf' + files[name]
    elif fault == 'trailing': files[name] += b'{}'
    else: files[name] = b'\xff'
    ref = tmp_path / 'result.zip'; write_reference(ref, files)
    with pytest.raises(api.PatchHarborError) as caught:
        reader.read_result_reference(ref)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR


@pytest.mark.parametrize('fault', ['duplicate', 'wrong_object_format', 'unsafe_path', 'partial_inventory',
                                   'case_collision', 'invalid_mode', 'zip_mode', 'wrong_hash', 'bool_size',
                                   'inconsistent_clean', 'inconsistent_dirty'])
def test_inventories_are_complete_typed_and_bound_to_content(tmp_path, fault):
    files, _ = reference_entries(dirty=True)
    def mutate(d):
        entry=d['base_entries'][0]
        if fault == 'duplicate': d['base_entries'].append(dict(entry))
        elif fault == 'wrong_object_format': entry['object_id']='a'*64
        elif fault == 'unsafe_path': entry['path']='../outside'
        elif fault == 'partial_inventory': d['base_entries']=[]
        elif fault == 'invalid_mode': entry['git_mode']='120000'
        elif fault == 'zip_mode': entry['git_mode']='100755'
        elif fault == 'wrong_hash': d['untracked_entries'][0]['sha256']='0'*64
        elif fault == 'bool_size': d['untracked_entries'][0]['size']=False
    edit_document(files, 'manifest.json', mutate)
    if fault == 'case_collision': files['untracked/New.bin']=files['untracked/new.bin']
    if fault == 'inconsistent_clean':
        for name in ('manifest.json','context.json'):
            edit_document(files,name,lambda d:d.update(dirty=False))
    if fault == 'inconsistent_dirty':
        files.pop('untracked/new.bin'); files['changes/unstaged.patch']=b''
        edit_document(files,'manifest.json',lambda d:d.update(untracked_entries=[]))
    ref=tmp_path/'result.zip';write_reference(ref,files)
    with pytest.raises(api.PatchHarborError) as caught: reader.read_result_reference(ref)
    assert int(exit_code_for_error(caught.value)) == 4


@pytest.mark.parametrize('field', ['success','entrypoint_started','timed_out','interrupted','entrypoint_exit_code','patchharbor_error_code'])
def test_nested_execution_booleans_are_not_integer_aliases(tmp_path, field):
    files,_=reference_entries(kind='success')
    def mutate(d): d['primary_result'][field] = True if field.endswith('code') else int(d['primary_result'][field])
    edit_document(files,'logs/run.json',mutate)
    ref=tmp_path/'result.zip';write_reference(ref,files)
    with pytest.raises(api.PatchHarborError) as caught: reader.read_result_reference(ref)
    assert int(exit_code_for_error(caught.value)) == 4


@pytest.mark.parametrize('fault', ['missing_pair','wrong_binding','bool_version','nonfinite','wrong_path','bad_time'])
def test_optional_handoff_is_consistent_when_present(tmp_path, fault):
    files,_=reference_entries(handoff=True)
    if fault=='missing_pair': files.pop('CHAT_INSTRUCTIONS.md')
    else:
        changes={'wrong_binding':{'repository_context':{}},'bool_version':{'format_version':True},
                 'nonfinite':{'runtime':{'extra':1e999}},'wrong_path':{'repository_path':'/different'},
                 'bad_time':{'captured_at':'bad'}}
        edit_document(files,'environment.json',lambda d:d.update(changes[fault]))
    ref=tmp_path/'result.zip';write_reference(ref,files)
    with pytest.raises(api.PatchHarborError) as caught: reader.read_result_reference(ref)
    assert int(exit_code_for_error(caught.value)) == 4


@pytest.mark.parametrize('fault', ['missing', 'directory', 'nonzip', 'symlink_loop'])
def test_reference_input_errors_use_json_four(tmp_path, fault):
    _,binding=reference_entries(); patch=tmp_path/'patch.zip';bound_package(patch,binding)
    ref=tmp_path/'input'
    if fault=='directory':ref.mkdir()
    elif fault=='nonzip':ref.write_bytes(b'not zip')
    elif fault=='symlink_loop':
        try:ref.symlink_to(ref)
        except OSError:pytest.skip('symlinks unavailable')
    out=StringIO()
    assert main(['validate',str(patch),'--reference-bundle',str(ref),'--json'],stdout=out,stderr=StringIO())==4
    result=json.loads(out.getvalue());assert result['result'] is None and result['process_exit_code']==4


def test_reference_is_one_stable_capture_not_a_second_hash_read(tmp_path, monkeypatch):
    files,binding=reference_entries();ref=tmp_path/'result.zip';write_reference(ref,files)
    original_bytes=ref.read_bytes();patch=tmp_path/'patch.zip';bound_package(patch,binding)
    original=reader.read_stable_regular_file_with_sha256; calls=[]
    def replace_after_read(*args,**kwargs):
        captured=original(*args,**kwargs);calls.append(args[0]);ref.write_bytes(b'replaced');return captured
    monkeypatch.setattr(reader,'read_stable_regular_file_with_sha256',replace_after_read)
    result=api.validate_patch(patch,reference_bundle=ref)
    assert result.reference_sha256==hashlib.sha256(original_bytes).hexdigest() and calls==[ref]


def test_unstable_reference_cannot_pass(tmp_path,monkeypatch):
    files,binding=reference_entries();ref=tmp_path/'result.zip';write_reference(ref,files)
    patch=tmp_path/'patch.zip';bound_package(patch,binding)
    def unstable(*a,**k):raise FileChangedDuringRead('changed')
    monkeypatch.setattr(reader,'read_stable_regular_file_with_sha256',unstable)
    with pytest.raises(api.PatchHarborError) as caught:api.validate_patch(patch,reference_bundle=ref)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR


def test_reference_uses_existing_zip_budget(tmp_path):
    files,binding=reference_entries();files['logs/execution.log']=b'x'*8000
    # Budget rejection precedes inventory/metadata rejection.
    ref=tmp_path/'result.zip';write_reference(ref,files)
    patch=tmp_path/'patch.zip';bound_package(patch,binding)
    policy=replace(DEFAULT_RESOURCE_POLICY,warning_bytes=1024,max_input_artifact_bytes=4096)
    assert patch.stat().st_size<4096<ref.stat().st_size
    with pytest.raises(api.PatchHarborError) as caught:validate_patch(patch,reference_bundle=ref,resource_policy=policy)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR


def test_path_arguments_are_anchored_before_observer_changes_cwd(tmp_path,monkeypatch):
    original=tmp_path/'original';original.mkdir();other=tmp_path/'other';other.mkdir()
    files,binding=reference_entries();write_reference(original/'result.zip',files);bound_package(original/'patch.zip',binding)
    monkeypatch.chdir(original)
    def observer(event):monkeypatch.chdir(other)
    assert api.validate_patch('patch.zip',reference_bundle='result.zip',observer=observer).binding_matches


def test_unexpected_programmer_exception_is_not_disguised(tmp_path,monkeypatch):
    files,_=reference_entries();ref=tmp_path/'result.zip';write_reference(ref,files)
    def unexpected(*a,**k):raise RuntimeError('programming failure')
    monkeypatch.setattr(reader,'parse_result_payloads',unexpected)
    with pytest.raises(RuntimeError):reader.read_result_reference(ref)
