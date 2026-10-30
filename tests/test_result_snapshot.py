"""Public snapshot semantics against real producer bytes and independent oracles."""
from dataclasses import FrozenInstanceError
import hashlib
import inspect
import os
import typing
from pathlib import Path

import pytest

from patchharbor import api
from tests.registration_support import git
from tests.reference_support import reference_entries, write_reference
from tests.snapshot_support import produce_case, result_files

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize('kind', ['clean','staged','unstaged','untracked','mixed'])
@pytest.mark.parametrize('object_format', ['sha1','sha256'])
@pytest.mark.parametrize('quoted', [False, True])
def test_layers_match_independent_original_states(tmp_path,monkeypatch,kind,object_format,quoted):
    case=produce_case(tmp_path,monkeypatch,kind=kind,object_format=object_format,quoted=quoted)
    raw=case.result.read_bytes()
    snapshot=api.read_result_snapshot(case.result,expected_sha256=hashlib.sha256(raw).hexdigest())
    assert snapshot.format_version==3 and snapshot.context.dirty==(kind!='clean')
    assert snapshot.sha256==hashlib.sha256(raw).hexdigest()
    assert snapshot.context==api.ReferenceContext(**{name:getattr(api.context(case.repository),name)
        for name in ('repo_id','base_commit','dirty','state_fingerprint','fingerprint_algorithm')},repository_path=str(case.repository.resolve()))
    assert snapshot.operation=='bundle' and not snapshot.dry_run and snapshot.primary_result.success
    for name,expected in case.expected.items():
        actual=getattr(snapshot,name)
        assert actual.name==name
        assert {p:(f.mode,f.content) for p,f in actual.files.items()}==expected
        assert list(actual.files)==sorted(actual.files,key=lambda p:p.encode())
        for path,f in actual.files.items():
            assert f.path==path and f.kind=='regular' and f.size==len(expected[path][1])
            assert f.sha256==hashlib.sha256(expected[path][1]).hexdigest()
            assert str(f.object_id)==hashlib.new(object_format,b'blob '+str(f.size).encode()+b'\0'+f.content).hexdigest()
    if kind=='mixed':
        files,_=result_files(case.result)
        assert b'\ndelta ' in files['changes/staged.patch']
        assert b'\nliteral ' in files['changes/staged.patch']
        assert snapshot.base.files['replace'].content==b'old tracked\n'
        assert 'replace' not in snapshot.index.files
        assert snapshot.effective.files['replace'].content==b'replacement\n'
    assert case.result.read_bytes()==raw
    case.result.write_bytes(b'replaced after capture')
    (case.repository/'tracked.txt').write_bytes(b'late repository change')
    assert snapshot.effective.files['tracked.txt'].content==case.expected['effective']['tracked.txt'][1]
    with pytest.raises(TypeError):snapshot.effective.files['forged']=snapshot.base.files['tracked.txt']
    with pytest.raises(FrozenInstanceError):snapshot.base.files['tracked.txt'].content=b'forged'
    with pytest.raises(FrozenInstanceError):snapshot.sha256='0'*64


@pytest.mark.skipif(os.name=='nt', reason='native POSIX executable-bit transition')
def test_mode_changes_preserve_bytes_and_effective_modes(tmp_path,monkeypatch):
    case=produce_case(tmp_path,monkeypatch,kind='clean')
    path=case.repository/'tracked.txt';path.chmod(0o755)
    git(case.repository,'add','tracked.txt')
    path.chmod(0o644)
    result=api.bundle(case.repository)
    s=api.read_result_snapshot(result.path)
    assert [getattr(s,n).files['tracked.txt'].mode for n in ('base','index','worktree','effective')]==['100644','100755','100644','100644']
    assert all(getattr(s,n).files['tracked.txt'].content==path.read_bytes() for n in ('base','index','worktree'))


@pytest.mark.parametrize('kind',['bundle','success','failure','dry_run','timeout','interrupted','mismatch'])
@pytest.mark.parametrize('dirty',[False,True])
def test_valid_execution_facts_are_never_promoted_to_success(tmp_path,kind,dirty):
    files,_=reference_entries(kind=kind,dirty=dirty)
    if dirty:files['changes/unstaged.patch']=b''  # actual untracked state, no fictional delta
    path=tmp_path/'reference.zip';write_reference(path,files)
    s=api.read_result_snapshot(path)
    assert s.context.dirty is dirty and s.dry_run==(kind=='dry_run')
    assert s.primary_result.success==(kind in ('bundle','success','dry_run'))
    assert s.primary_result.entrypoint_started==(kind in ('success','failure','timeout','interrupted'))
    assert ('new.bin' in s.effective.files) is dirty
    # The described synthetic runtime raises if imported; validation reads data only.
    assert s.runtime.status=='embedded' and len(s.runtime.artifact_sha256)==64


def test_public_signature_types_capabilities_and_argument_failures(tmp_path):
    signature=inspect.signature(api.read_result_snapshot)
    assert list(signature.parameters)==['result','expected_sha256','observer']
    assert typing.get_type_hints(api.read_result_snapshot)['return'] is api.ResultSnapshot
    assert {'ResultSnapshot','SnapshotLayer','SnapshotFile','SnapshotRuntime','ResultSnapshotError','SnapshotErrorCode'}<=set(api.__all__)
    capability=api.integration_capabilities()
    assert capability.contract_version==capability.snapshot_contract_version==1
    for digest in ('short','A'*64,'x'*64):
        with pytest.raises(ValueError):api.read_result_snapshot(tmp_path/'absent',expected_sha256=digest)
    for digest in (True,b'0'*64,5):
        with pytest.raises(TypeError):api.read_result_snapshot(tmp_path/'absent',expected_sha256=digest)
    with pytest.raises(TypeError):api.read_result_snapshot(tmp_path/'absent',observer='observer')
    with pytest.raises(api.ResultSnapshotError) as caught:api.read_result_snapshot(tmp_path/'absent')
    assert caught.value.code is api.SnapshotErrorCode.INVALID_RESULT


@pytest.mark.parametrize('direction',['file_to_directory','directory_to_file'])
def test_real_file_directory_transition_preserves_layers(tmp_path,monkeypatch,direction):
    case=produce_case(tmp_path,monkeypatch,kind='clean')
    repo=case.repository
    if direction=='file_to_directory':
        (repo/'tracked.txt').unlink();(repo/'tracked.txt').mkdir();(repo/'tracked.txt'/'child').write_bytes(b'child\n')
    else:
        (repo/'雪 space/a b/file').unlink();(repo/'雪 space/a b').rmdir();(repo/'雪 space').rmdir();(repo/'雪 space').write_bytes(b'file\n')
    git(repo,'add','--all')
    s=api.read_result_snapshot(api.bundle(repo).path)
    if direction=='file_to_directory':
        assert 'tracked.txt' in s.base.files and 'tracked.txt' not in s.index.files
        assert s.effective.files['tracked.txt/child'].content==b'child\n'
    else:
        assert '雪 space/a b/file' in s.base.files and '雪 space/a b/file' not in s.index.files
        assert s.effective.files['雪 space'].content==b'file\n'


@pytest.mark.parametrize('before,after',[(b'',b'first'),(b'first',b''),(b'a',b'a\n'),(b'a\n',b'a'),
    (b'a\nb',b'new\na\nb'),(b'a\nb',b'a\nb\nnew'),(b'\n',b'\n\n'),(b'a\r\n',b'a\n')])
def test_text_edge_shapes_match_real_git(tmp_path,monkeypatch,before,after):
    case=produce_case(tmp_path,monkeypatch,kind='clean')
    p=case.repository/'tracked.txt';p.write_bytes(before)
    git(case.repository,'add','tracked.txt');git(case.repository,'commit','--quiet','-m','text edge base')
    p.write_bytes(after)
    snapshot=api.read_result_snapshot(api.bundle(case.repository).path)
    assert snapshot.base.files['tracked.txt'].content==before
    assert snapshot.index.files['tracked.txt'].content==before
    assert snapshot.worktree.files['tracked.txt'].content==after


@pytest.mark.parametrize('case',['clean','diagnostic','single','multi','dry-run','partial-failure','dirty','unavailable'])
def test_frozen_140_snapshots_preserve_status_and_actual_file_layers(case,monkeypatch):
    import socket
    import subprocess
    from tests.compatibility_140_support import artifact
    path,expected=artifact('result',case)
    def forbidden(*args,**kwargs):pytest.fail('snapshot started a subprocess or network operation')
    monkeypatch.setattr(subprocess,'Popen',forbidden);monkeypatch.setattr(socket,'socket',forbidden)
    s=api.read_result_snapshot(path,expected_sha256=expected['sha256'])
    assert s.context.dirty is expected['dirty']
    assert s.primary_result.kind.value==expected['primary_kind']
    assert s.dry_run is expected['dry_run']
    if case=='dirty':
        assert s.base.files['tracked.txt'].content==b'partial commit\n'
        assert s.index.files['tracked.txt'].content==b'staged\n'
        assert s.worktree.files['tracked.txt'].content==b'unstaged\n'
        assert 'delete-me.txt' not in s.effective.files
        assert s.effective.files['untracked.bin'].content==b'\x00public\xff\n'
    elif case=='partial-failure':
        assert s.worktree.files['tracked.txt'].content==b'uncommitted after failure\n'
        assert s.primary_result.entrypoint_exit_code==7
    else:
        assert s.base.files==s.index.files==s.worktree.files==s.effective.files
