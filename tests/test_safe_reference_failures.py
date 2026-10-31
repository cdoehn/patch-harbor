"""Real boundaries, races and failures around the source-safe public contract."""
from dataclasses import replace
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import pytest
from patchharbor import api
from patchharbor import safe_export, safe_export_plan, result_bundle_publication
from tests.registration_support import create_repository,git
from tests.safe_reference_support import host,source_bytes
from tests.platform_support import project_environment

pytestmark=[pytest.mark.e2e,pytest.mark.skipif(not sys.platform.startswith('linux'),reason='safe reference host contract 1 requires Linux')]


def test_preflight_is_read_only_and_reports_complete_operating_boundaries(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch)
    before=source_bytes(tmp_path)
    (repo/'subdir').mkdir()
    context=api.context(repo/'subdir',capture_mode='safe')
    plan=api.prepare_reference_export(repo/'subdir',output_directory=output,expected_context=context)
    assert plan.context.repository_path.value==repo
    assert plan.output_directory==plan.diagnostics_parent==output
    assert plan.configured_exchange==exchange and plan.maintenance_enabled is False
    assert len(plan.binding_sha256)==64 and len(plan.lock_paths)==2
    assert all(repo not in p.parents for p in plan.lock_paths)
    assert source_bytes(tmp_path)==before
    for lock in plan.lock_paths:lock.unlink()
    absent=source_bytes(tmp_path)
    api.prepare_reference_export(repo,output_directory=output)
    api.context(repo,capture_mode='safe')
    assert source_bytes(tmp_path)==absent and all(not p.exists() for p in plan.lock_paths)


@pytest.mark.parametrize('explicit',[True,False])
def test_export_does_not_maintain_exchange_or_touch_foreign_files(tmp_path,monkeypatch,explicit):
    repo,exchange,output=host(tmp_path,monkeypatch)
    foreign=exchange/'foreign.zip';foreign.write_bytes(b'not ours')
    nested=exchange/'Archive';nested.mkdir();(nested/'receipt').write_bytes(b'keep')
    before=source_bytes(repo);foreign_before=source_bytes(exchange)
    import patchharbor.application_exchange as operations
    def forbidden(*args,**kwargs):pytest.fail('safe export started Exchange maintenance')
    monkeypatch.setattr(operations,'_maintain_bundle_exchange',forbidden)
    plan=api.prepare_reference_export(repo,output_directory=output if explicit else None)
    result=api.bundle(repo,capture_mode='safe',export_plan=plan)
    assert result.path.parent==(output if explicit else exchange)
    assert all(source_bytes(exchange)[name]==value for name,value in foreign_before.items())
    assert source_bytes(repo)==before


@pytest.mark.parametrize('fault',['registration','head','configuration'])
def test_invalid_source_has_no_repair_or_output_side_effect(tmp_path,monkeypatch,fault):
    repo,exchange,output=host(tmp_path,monkeypatch)
    if fault=='registration':api.unregister(repo)
    elif fault=='head':git(repo,'update-ref','-d','HEAD')
    else:(repo/'.patchharbor/config.json').write_bytes(b'{broken')
    before=source_bytes(tmp_path)
    with pytest.raises(api.SafeExportError):api.prepare_reference_export(repo,output_directory=output)
    assert source_bytes(tmp_path)==before


@pytest.mark.parametrize('kind',['repository','foreign_repository','file','symlink','parent_symlink','fifo','world_writable','missing'])
def test_unsafe_destination_is_refused_before_writing(tmp_path,monkeypatch,kind):
    repo,exchange,output=host(tmp_path,monkeypatch)
    if kind=='repository':target=repo/'dest';target.mkdir()
    elif kind=='foreign_repository':
        foreign=create_repository(tmp_path/'foreign');api.register(foreign);target=foreign/'dest';target.mkdir()
    elif kind=='file':target=tmp_path/'file';target.write_bytes(b'keep')
    elif kind=='symlink':target=tmp_path/'link';target.symlink_to(output,target_is_directory=True)
    elif kind=='parent_symlink':
        (output/'nested').mkdir();alias=tmp_path/'link';alias.symlink_to(output,target_is_directory=True);target=alias/'nested'
    elif kind=='fifo':target=tmp_path/'fifo';os.mkfifo(target)
    elif kind=='world_writable':target=output;target.chmod(0o777)
    else:target=tmp_path/'missing'
    before=source_bytes(tmp_path)
    with pytest.raises(api.SafeExportError) as caught:api.prepare_reference_export(repo,output_directory=target)
    assert caught.value.code is api.SafeExportErrorCode.UNSAFE_PATH
    assert source_bytes(tmp_path)==before


@pytest.mark.parametrize('change',['source','configuration','registry','output_identity','forged_plan'])
def test_stale_or_forged_plan_cannot_authorize_a_new_boundary(tmp_path,monkeypatch,change):
    repo,exchange,output=host(tmp_path,monkeypatch)
    plan=api.prepare_reference_export(repo,output_directory=output)
    if change=='source':(repo/'tracked.txt').write_bytes(b'new state\n')
    elif change=='configuration':api.configure_bundle_suffix('.txt',repository=repo)
    elif change=='registry':api.register(create_repository(tmp_path/'another'))
    elif change=='output_identity':output.rename(tmp_path/'old-output');output.mkdir()
    else:plan=replace(plan,maintenance_enabled=True)
    before=source_bytes(tmp_path)
    with pytest.raises(api.SafeExportError) as caught:api.bundle(repo,capture_mode='safe',export_plan=plan)
    assert caught.value.code is api.SafeExportErrorCode.STALE
    assert source_bytes(tmp_path)==before


def test_source_change_after_capture_does_not_publish_mixed_result(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch);plan=api.prepare_reference_export(repo,output_directory=output)
    original=safe_export.capture_safe_result;changed=[]
    def capture(*args):
        result=original(*args);(repo/'tracked.txt').write_bytes(b'concurrent external write\n');changed.append(source_bytes(repo));return result
    monkeypatch.setattr(safe_export,'capture_safe_result',capture)
    with pytest.raises(api.SafeExportError) as caught:api.bundle(repo,capture_mode='safe',export_plan=plan)
    assert caught.value.code is api.SafeExportErrorCode.STALE
    assert source_bytes(repo)==changed[0] and not list(output.glob('*.zip'))
    assert json.loads((caught.value.emergency_diagnostics_path/'failure.json').read_bytes())['code']=='stale'


def test_late_destination_collision_preserves_foreign_bytes(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch);plan=api.prepare_reference_export(repo,output_directory=output)
    before=source_bytes(repo);publish=safe_export.publish_result_bundle;foreign=[]
    def colliding(publication,**kwargs):
        callback=kwargs['before_atomic_publish']
        def collision():
            callback();path=output/publication.final_path.name;path.write_bytes(b'foreign occupant');foreign.append(path)
        return publish(publication,**{**kwargs,'before_atomic_publish':collision})
    monkeypatch.setattr(safe_export,'publish_result_bundle',colliding)
    with pytest.raises(api.SafeExportError):api.bundle(repo,capture_mode='safe',export_plan=plan)
    assert len(foreign)==1 and foreign[0].read_bytes()==b'foreign occupant'
    assert source_bytes(repo)==before


def test_directory_swap_during_publication_cannot_write_into_source(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch);plan=api.prepare_reference_export(repo,output_directory=output)
    before=source_bytes(repo);publish=safe_export.publish_result_bundle
    def swapped(publication,**kwargs):
        callback=kwargs['before_atomic_publish']
        def swap():
            callback();output.rename(tmp_path/'moved-output');output.symlink_to(repo,target_is_directory=True)
        return publish(publication,**{**kwargs,'before_atomic_publish':swap})
    monkeypatch.setattr(safe_export,'publish_result_bundle',swapped)
    with pytest.raises(api.SafeExportError) as caught:api.bundle(repo,capture_mode='safe',export_plan=plan)
    assert caught.value.code is api.SafeExportErrorCode.STALE
    assert source_bytes(repo)==before and not list((tmp_path/'moved-output').glob('*.zip'))


def test_real_permission_failure_does_not_mutate_source_or_publish(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch);output.chmod(0o500)
    plan=api.prepare_reference_export(repo,output_directory=output);before=source_bytes(repo)
    try:
        with pytest.raises(api.SafeExportError) as caught:api.bundle(repo,capture_mode='safe',export_plan=plan)
        assert caught.value.code is api.SafeExportErrorCode.IO
        assert source_bytes(repo)==before and not list(output.iterdir())
    finally:output.chmod(0o700)


def test_cleanup_failure_reports_the_actually_published_result(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch);plan=api.prepare_reference_export(repo,output_directory=output);before=source_bytes(repo)
    def failure(*args):raise OSError('injected cleanup failure')
    monkeypatch.setattr(safe_export,'_cleanup_diagnostics',failure)
    with pytest.raises(api.SafeExportError) as caught:api.bundle(repo,capture_mode='safe',export_plan=plan)
    assert caught.value.code is api.SafeExportErrorCode.CLEANUP
    assert caught.value.published_path.is_file()
    assert api.read_result_snapshot(caught.value.published_path).context.base_commit==plan.context.base_commit
    assert source_bytes(repo)==before
    assert json.loads((caught.value.emergency_diagnostics_path/'failure.json').read_bytes())['published_path']==str(caught.value.published_path)


@pytest.mark.parametrize('interrupt',[KeyboardInterrupt,SystemExit])
def test_interrupt_before_publication_keeps_source_and_error_evidence(tmp_path,monkeypatch,interrupt):
    repo,exchange,output=host(tmp_path,monkeypatch);plan=api.prepare_reference_export(repo,output_directory=output);before=source_bytes(repo)
    def abort(*args):raise interrupt()
    monkeypatch.setattr(safe_export,'capture_safe_result',abort)
    with pytest.raises(api.SafeExportError) as caught:api.bundle(repo,capture_mode='safe',export_plan=plan)
    assert caught.value.code is api.SafeExportErrorCode.INTERRUPTED
    assert source_bytes(repo)==before and not list(output.glob('*.zip'))
    assert (caught.value.emergency_diagnostics_path/'failure.json').is_file()


def test_killed_writer_never_exposes_partial_final_result(tmp_path,monkeypatch):
    repo,exchange,output=host(tmp_path,monkeypatch);before=source_bytes(repo)
    program='''
import sys
from pathlib import Path
from threading import Event
from patchharbor import api, result_bundle_publication as publication
original=publication.write_result_bundle
def paused(*args,**kwargs):
    original(*args,**kwargs)
    print('staged',flush=True)
    Event().wait(120)
publication.write_result_bundle=paused
repo,output=map(Path,sys.argv[1:])
plan=api.prepare_reference_export(repo,output_directory=output)
api.bundle(repo,capture_mode='safe',export_plan=plan)
'''
    child=subprocess.Popen([sys.executable,'-B','-c',program,str(repo),str(output)],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=project_environment())
    try:
        assert select.select([child.stdout],[],[],45)[0], 'writer did not signal staging'
        assert child.stdout.readline()==b'staged\n'
        child.kill();child.wait(timeout=15)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=15)
    assert child.returncode==-signal.SIGKILL
    assert not list(output.glob('*.zip')) and list(output.glob('.*.tmp'))
    assert source_bytes(repo)==before


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo'])
def test_unsafe_existing_lock_never_writes_through_it(tmp_path, monkeypatch, kind):
    repo, _, output = host(tmp_path, monkeypatch)
    plan = api.prepare_reference_export(repo, output_directory=output)
    target = plan.lock_paths[0]
    target.unlink()
    if kind == 'symlink':
        target.symlink_to(repo / 'protected.txt')
    elif kind == 'hardlink':
        os.link(repo / 'protected.txt', target)
    else:
        os.mkfifo(target)
    before = source_bytes(repo)
    with pytest.raises(api.SafeExportError):
        api.bundle(repo, capture_mode='safe', export_plan=plan)
    assert source_bytes(repo) == before and not list(output.iterdir())


def test_created_operating_files_are_private_and_existing_modes_unchanged(tmp_path, monkeypatch):
    import stat
    repo, _, output = host(tmp_path, monkeypatch)
    output.chmod(0o775)
    plan = api.prepare_reference_export(repo, output_directory=output)
    before = source_bytes(repo)
    old_mask = os.umask(0)
    try:
        result = api.bundle(repo, capture_mode='safe', export_plan=plan)
    finally:
        os.umask(old_mask)
    assert stat.S_IMODE(result.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.stat().st_mode) == 0o775
    assert source_bytes(repo) == before


def test_directory_swap_at_diagnostic_creation_never_redirects_writes(tmp_path, monkeypatch):
    repo, _, output = host(tmp_path, monkeypatch)
    plan = api.prepare_reference_export(repo, output_directory=output)
    before = source_bytes(repo)
    mkdir = os.mkdir
    def swapped(name, mode=0o777, *, dir_fd=None):
        result = mkdir(name, mode, dir_fd=dir_fd)
        if isinstance(name, str) and name.startswith('.patchharbor-safe-'):
            output.rename(tmp_path / 'moved-output')
            output.symlink_to(repo, target_is_directory=True)
        return result
    monkeypatch.setattr(os, 'mkdir', swapped)
    with pytest.raises(api.SafeExportError) as caught:
        api.bundle(repo, capture_mode='safe', export_plan=plan)
    assert caught.value.code is api.SafeExportErrorCode.STALE
    assert source_bytes(repo) == before
    assert not list((tmp_path / 'moved-output').glob('*.zip'))


def test_real_source_read_failure_has_semantic_io_error_without_repair(tmp_path, monkeypatch):
    repo, _, output = host(tmp_path, monkeypatch)
    target = repo / 'tracked.txt'
    before = source_bytes(repo)
    target.chmod(0)
    try:
        with pytest.raises(api.SafeExportError) as caught:
            api.prepare_reference_export(repo, output_directory=output)
        assert caught.value.code is api.SafeExportErrorCode.IO
        assert target.stat().st_mode & 0o777 == 0
        assert not list(output.iterdir())
    finally:
        target.chmod(before['tracked.txt'][0])
    assert source_bytes(repo) == before
