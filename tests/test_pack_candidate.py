"""Pack metadata, exact payloads, ZIP profile and shared reference validation."""
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import stat
from uuid import UUID
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from patchharbor import api
from patchharbor.bundle_handoff import BundleHandoff, MAX_HANDOFF_ENTRY_BYTES
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.pack_candidate import prepare_metadata, write_candidate
from patchharbor.pack_sources import capture_sources
from patchharbor.result_reader import capture_result_reference
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from tests.test_captured_reference import _reference
from tests.test_reference_validation import edit_document, write_reference


PACKAGE_ID=UUID('be14e6e2-5f1c-4693-8c94-30f2381499df')
STAMP=datetime(2026,10,7,17,28,39,tzinfo=timezone.utc)
SCRIPT=b'#!/usr/bin/env bash\r\n# PATCHHARBOR\r\nexit 0\r\n'
TEMPLATE='Canonical controlled fixture template\n'


def inputs(tmp_path):
    root=tmp_path/'contents';root.mkdir()
    (root/'run.sh').write_bytes(SCRIPT)
    (root/'binary').write_bytes(b'\x00\xff\r\n')
    return capture_sources(root,'run.sh',modes={'binary':0o755})


def build(tmp_path,reference,sources,*,filename=None,policy=DEFAULT_RESOURCE_POLICY,template=TEMPLATE):
    metadata=prepare_metadata(reference,PACKAGE_ID,STAMP,filename=filename)
    stream=BytesIO()
    warnings=write_candidate(stream,sources,reference,metadata,template,resource_policy=policy)
    return metadata,stream.getvalue(),warnings


@pytest.mark.parametrize('kind',['bundle','success','dry_run','failure','mismatch','timeout','interrupted'])
@pytest.mark.parametrize('dirty',[False,True])
@pytest.mark.parametrize('version,handoff',[(1,False),(1,True),(2,True)])
def test_candidate_preserves_exact_binding_and_is_natively_valid(tmp_path,kind,dirty,version,handoff):
    path,_,binding=_reference(tmp_path,kind=kind,dirty=dirty,handoff=handoff,version=version)
    reference=capture_result_reference(path)
    source=inputs(tmp_path)
    metadata,raw,warnings=build(tmp_path,reference,source)
    output=tmp_path/metadata.filename;output.write_bytes(raw)
    validated=api.validate_patch(output,reference_bundle=path)
    assert validated.binding_matches and validated.reference_sha256==reference.sha256
    with ZipFile(BytesIO(raw)) as archive:
        manifest=json.loads(archive.read('patch.json'))
        assert manifest=={'marker':'patch-harbor','format_version':1,**binding,'entrypoint':'run.sh'}
        assert archive.read('run.sh')==SCRIPT
        assert archive.read('binary')==b'\x00\xff\r\n'
        env=json.loads(archive.read('PATCHHARBOR_META/environment.json'))
        assert env['repository_context']==binding
        assert env['bundle_type']=='Patch' and env['bundle_filename']==metadata.filename
        assert env['bundle_suffix']=='.txt'
        assert env['run_id']==reference.facts.run_id
        if handoff:
            assert env['captured_at']=='2026-10-03T12:00:00Z'
            assert env['repository_path']=='/foreign/missing/repository'
            assert env['exchange_directory']=='/foreign/exchange'
            assert env['output_directory'] is None
            assert env['runtime']['system']=='ForeignOS'
        else:
            assert env['captured_at'] is None and env['runtime'] is None
            assert env['exchange_directory'] is None and env['output_directory'] is None
            assert warnings


def test_candidate_profile_is_ordered_reproducible_and_uses_explicit_modes(tmp_path):
    path,_,_=_reference(tmp_path)
    reference=capture_result_reference(path);source=inputs(tmp_path)
    first=build(tmp_path,reference,source);second=build(tmp_path,reference,source)
    assert first==second
    with ZipFile(BytesIO(first[1])) as archive:
        assert archive.namelist()==sorted(archive.namelist())
        assert archive.comment==b'' and len(archive.infolist())==5
        for info in archive.infolist():
            assert not info.is_dir() and info.compress_type==ZIP_DEFLATED
            assert info.date_time==(1980,1,1,0,0,0)
            assert info.create_system==3 and info.extra==b'' and info.comment==b''
            assert not info.flag_bits&1 and info.extract_version<45
            assert stat.S_ISREG(info.external_attr>>16)
            assert stat.S_IMODE(info.external_attr>>16)==(0o755 if info.filename=='binary' else 0o644)


@pytest.mark.parametrize('name,expected',[
    ('project','project'),('CON','_CON'),('nul.ext','_nul.ext'),
    ('...a b/ä...','a_b__'),('.'*7,'repository'),('a'*70,'a'*64),
    ('..'+'a'*63+'.extra','a'*63),
])
def test_automatic_name_uses_own_uuid_utc_and_portable_display_prefix(tmp_path,name,expected):
    path,files,_=_reference(tmp_path)
    edit_document(files,'environment.json',lambda d:d.update(repository_name=name))
    write_reference(path,files);reference=capture_result_reference(path)
    metadata=prepare_metadata(reference,PACKAGE_ID,STAMP)
    assert metadata.filename==expected+'_Patch_172839_1007_be14e6.zip.txt'
    assert metadata.package_id==PACKAGE_ID and metadata.created_at==STAMP
    assert json.loads(metadata.environment)['repository_name']==name
    assert bool(metadata.warnings)==(name!=expected)


@pytest.mark.parametrize('recorded,expected',[('/foreign/project','project'),
    ('C:\\Users\\somebody\\project','project'),('\\\\host\\share\\project','project'),('/', 'repository')])
def test_legacy_name_uses_recorded_path_syntax_without_local_resolution(tmp_path,monkeypatch,recorded,expected):
    path,files,_=_reference(tmp_path,handoff=False)
    edit_document(files,'logs/run.json',lambda d:d.update(repository_path=recorded))
    write_reference(path,files);reference=capture_result_reference(path)
    monkeypatch.setattr(Path,'resolve',lambda *a,**k:pytest.fail('foreign path resolution'))
    metadata=prepare_metadata(reference,PACKAGE_ID,STAMP)
    assert metadata.filename.startswith(expected+'_Patch_')


@pytest.mark.parametrize('suffix',['','.txt','.upload'])
def test_explicit_name_is_preserved_but_request_metadata_still_exists(tmp_path,suffix):
    path,_,_=_reference(tmp_path,suffix=suffix)
    metadata=prepare_metadata(capture_result_reference(path),PACKAGE_ID,STAMP,filename='chosen.zip'+suffix)
    assert metadata.filename=='chosen.zip'+suffix
    assert metadata.package_id==PACKAGE_ID and metadata.created_at==STAMP


@pytest.mark.parametrize('name',['wrong.zip','wrong.zip.txt.partial','wrong.txt','x/y.zip.txt','x\\y.zip.txt'])
def test_wrong_suffix_and_temporary_explicit_names_are_output_errors(tmp_path,name):
    path,_,_=_reference(tmp_path)
    with pytest.raises(PatchHarborError) as caught:
        prepare_metadata(capture_result_reference(path),PACKAGE_ID,STAMP,filename=name)
    assert caught.value.reason is FailureReason.PAYLOAD_PREPARATION_ERROR


def test_reference_rendered_instructions_are_not_the_new_template(tmp_path):
    path,_,_=_reference(tmp_path)
    reference=capture_result_reference(path)
    # Reference passive instructions were already validated; no later reading.
    reference=replace(reference,handoff=BundleHandoff(b'OLD_RENDERED_CONTEXT',reference.handoff.environment))
    _,raw,_=build(tmp_path,reference,inputs(tmp_path))
    with ZipFile(BytesIO(raw)) as archive:
        instruction=archive.read('PATCHHARBOR_META/CHAT_INSTRUCTIONS.md')
        assert b'OLD_RENDERED_CONTEXT' not in instruction
        assert instruction.count(TEMPLATE.encode())==1


@pytest.mark.parametrize('limit',['entry','entry_bytes','total','artifact','handoff'])
def test_generated_contents_and_compressed_output_share_budgets(tmp_path,limit):
    path,_,_=_reference(tmp_path);reference=capture_result_reference(path);source=inputs(tmp_path)
    policy=DEFAULT_RESOURCE_POLICY;template=TEMPLATE
    if limit=='entry':policy=replace(policy,max_zip_entries=4)
    elif limit=='entry_bytes':policy=replace(policy,warning_bytes=1,max_content_bytes=100)
    elif limit=='total':policy=replace(policy,max_zip_total_bytes=100)
    elif limit=='artifact':policy=replace(policy,warning_bytes=1,max_input_artifact_bytes=100)
    else:template='a'*MAX_HANDOFF_ENTRY_BYTES
    with pytest.raises(PatchHarborError) as caught:
        build(tmp_path,reference,source,policy=policy,template=template)
    assert caught.value.reason is FailureReason.SOURCE_ERROR
