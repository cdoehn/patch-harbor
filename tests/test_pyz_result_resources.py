"""Prepared Result-3 resources use the same pinned producer before the switch."""
from dataclasses import FrozenInstanceError
from functools import partial
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from patchharbor import api, application, result_bundle, result_resources as resources
from patchharbor import pyz_artifact, runtime_pyz as pyz
from patchharbor.result_reader import read_result_reference
from patchharbor.resource_policy import ResourcePolicy
from tests.test_pyz_resources import provider_for
from tests.test_reference_validation import reference_entries, write_reference, edit_document
from tests.test_result_runtime_writer import repository, package


@pytest.mark.parametrize('kind',['directory','zip'])
@pytest.mark.parametrize('embedded',[True,False])
def test_prepared_payload_matches_strict_native_reader(monkeypatch,tmp_path,kind,embedded):
    provider,_,_,_=provider_for(monkeypatch,tmp_path,kind=kind)
    artifact=provider.capture().artifact if embedded else None
    payload=resources.runtime_payload(artifact,reason=None if embedded else 'source_not_prepared')
    files,_=reference_entries(handoff=True)
    files.update(dict(payload.entries()))
    edit_document(files,'manifest.json',lambda d:d.update(format_version=3,runtime=payload.document()))
    edit_document(files,'logs/run.json',lambda d:d.update(warnings=list(payload.warnings)))
    reference=tmp_path/'result.zip';write_reference(reference,files)
    facts,_=read_result_reference(reference)
    assert facts.format_version==3 and facts.runtime.status==payload.status
    assert 'artifact' in payload.document() and 'wheel' not in payload.document()
    assert payload.result_format==3
    assert payload.unavailable('resource_limit').result_format==3
    assert len(payload.entries())==(2 if embedded else 1)
    with pytest.raises(FrozenInstanceError):payload.artifact_bytes=b'changed'


def damage(source,kind,name):
    if kind=='directory':(source.root/name).unlink()
    else:
        raw=bytearray(source.archive.read_bytes())
        with ZipFile(BytesIO(raw)) as archive:
            info=archive.getinfo(name)
            position=info.header_offset+30+len(info.filename.encode())+len(info.extra)
        raw[position]^=1
        source.archive.write_bytes(raw)


@pytest.mark.parametrize('kind',['directory','zip'])
@pytest.mark.parametrize('fault',['optional','template','recipe','new_producer'])
def test_optional_runtime_failure_keeps_only_proven_required_template(monkeypatch,tmp_path,kind,fault):
    provider,source,recipe,raw=provider_for(monkeypatch,tmp_path,kind=kind)
    expected=pyz_artifact.PyzProvider().capture().artifact.chat_template
    if fault=='new_producer':provider._producer_id='0'*64
    else:damage(source,kind,{'optional':pyz.DOC_PATH,'template':pyz.CHAT_PATH,'recipe':pyz.RECIPE_PATH}[fault])
    assert provider.capture().artifact is None
    if fault=='optional':assert provider.capture_required_template()==expected
    else:
        with pytest.raises((pyz.RuntimeDataError,OSError)):provider.capture_required_template()


@pytest.mark.parametrize('kind',['directory','zip'])
def test_required_template_is_from_the_same_captured_artifact_after_changes(monkeypatch,tmp_path,kind):
    provider,source,_,_=provider_for(monkeypatch,tmp_path,kind=kind)
    pinned=provider.capture().artifact
    damage(source,kind,pyz.CHAT_PATH)
    assert provider.capture_required_template()==pinned.chat_template
    assert provider.capture().artifact is pinned


@pytest.mark.parametrize('route',['bundle','apply','dry_run','failure','watcher'])
def test_private_format3_resources_run_through_actual_existing_writer_routes(repository,monkeypatch,tmp_path,route):
    provider,_,_,_=provider_for(monkeypatch,tmp_path)
    artifact=provider.capture().artifact
    root,exchange=repository
    patch=package(root,exchange,exit_code=23 if route=='failure' else 0)
    if route=='bundle':report=api.bundle(root).report
    elif route=='watcher':report=api.apply_next()
    else:report=api.apply(patch,dry_run=route=='dry_run')
    assert report.process_exit_code==(23 if route=='failure' else 0)
    facts,_=read_result_reference(report.result_bundle.path)
    assert facts.format_version==3 and facts.runtime.status=='embedded'
    assert facts.runtime.artifact.sha256==artifact.pyz_sha256
    with ZipFile(report.result_bundle.path) as archive:
        assert archive.read(facts.runtime.artifact.path)==artifact.pyz_bytes
        assert archive.read('CHAT_INSTRUCTIONS.md').endswith(artifact.chat_template)
        assert not any(name.startswith('runtime/') and name.endswith('.whl') for name in archive.namelist())


@pytest.mark.parametrize('kind',['directory','zip'])
def test_runtime_only_failure_keeps_snapshot_and_actual_failure_log(repository,monkeypatch,tmp_path,kind):
    _,source,_,_=provider_for(monkeypatch,tmp_path,kind=kind)
    damage(source,kind,pyz.DOC_PATH)
    root,exchange=repository
    from tests.platform_support import native_script
    patch=package(root,exchange,exit_code=23)
    with ZipFile(patch) as archive:files={name:archive.read(name) for name in archive.namelist()}
    entry=json.loads(files['patch.json'])['entrypoint']
    files[entry]=native_script("printf 'diagnostic-bytes'\nexit 23", "[Console]::Write('diagnostic-bytes')\nexit 23")
    write_reference(patch,files)
    report=api.apply(patch)
    assert report.process_exit_code==23
    facts,_=read_result_reference(report.result_bundle.path)
    assert facts.format_version==3 and facts.runtime.status=='unavailable'
    assert facts.warnings and facts.base_entries and facts.primary_result.entrypoint_exit_code==23
    with ZipFile(report.result_bundle.path) as archive:
        assert archive.read('logs/execution.log')==b'diagnostic-bytes'
        assert {n for n in archive.namelist() if n.startswith('runtime/')}=={'runtime/runtime.json'}


def test_format3_budget_fallback_cannot_reintroduce_legacy_wheel_contract(repository,monkeypatch,tmp_path):
    provider_for(monkeypatch,tmp_path)
    monkeypatch.setattr(result_bundle,'runtime_fits',partial(resources.runtime_fits,policy=ResourcePolicy(max_zip_total_bytes=1)))
    report=api.apply(package(*repository))
    assert report.process_exit_code==0
    facts,_=read_result_reference(report.result_bundle.path)
    assert facts.format_version==3 and facts.runtime.reason=='resource_limit'
    with ZipFile(report.result_bundle.path) as archive:
        doc=json.loads(archive.read('runtime/runtime.json'))
        assert doc['format_version']==2 and doc['artifact'] is None and 'wheel' not in doc


def test_prepared_runtime_and_template_are_frozen_before_mutation(repository,monkeypatch,tmp_path):
    provider,source,_,_=provider_for(monkeypatch,tmp_path)
    expected=provider.capture().artifact
    original=application.execute_prepared_script_with_log
    def mutate(*args,**kwargs):
        damage(source,'directory',pyz.CHAT_PATH)
        monkeypatch.setattr(pyz_artifact.PyzProvider,'capture',lambda *a:pytest.fail('late runtime capture'))
        return original(*args,**kwargs)
    monkeypatch.setattr(application,'execute_prepared_script_with_log',mutate)
    report=api.apply(package(*repository))
    assert report.process_exit_code==0
    facts,_=read_result_reference(report.result_bundle.path)
    assert facts.runtime.artifact.sha256==expected.pyz_sha256
    with ZipFile(report.result_bundle.path) as archive:
        assert archive.read('CHAT_INSTRUCTIONS.md').endswith(expected.chat_template)


def test_required_template_failure_still_preserves_actual_error_diagnostics(repository,monkeypatch,tmp_path):
    _,source,_,_=provider_for(monkeypatch,tmp_path)
    damage(source,'directory',pyz.CHAT_PATH)
    report=api.apply(package(*repository,exit_code=23))
    assert report.primary_result.entrypoint_exit_code==23
    assert report.result_bundle.status is api.ResultBundleStatus.FAILED
    assert report.result_bundle.emergency_diagnostics_path.is_dir()


def test_default_writer_retains_current_contract_until_switch(repository):
    report=api.bundle(repository[0]).report
    assert read_result_reference(report.result_bundle.path)[0].format_version==3


@pytest.mark.parametrize('fault',[RuntimeError('programming failure'),ValueError('programming failure'),KeyboardInterrupt(),SystemExit(9)])
def test_unexpected_provider_failures_and_cancellation_are_not_runtime_fallback(monkeypatch,fault):
    def fail(*args,**kwargs):raise fault
    monkeypatch.setattr(resources.PyzProvider,'capture',fail)
    with pytest.raises(type(fault)):resources.capture_result_resources()
