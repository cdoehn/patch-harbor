"""Native roundtrips with independent Git-created layers and a Git-execute oracle."""
from pathlib import Path
import hashlib
import sys
from zipfile import ZipFile
import pytest
from patchharbor import api
from tests.registration_support import create_repository,git
from tests.safe_reference_support import source_bytes
from tests.snapshot_support import produce_case,index_files,working_files

pytestmark=[pytest.mark.e2e,pytest.mark.skipif(not sys.platform.startswith('linux'),reason='safe reference host contract 1 requires Linux')]


@pytest.mark.parametrize('kind',['clean','staged','unstaged','mixed','untracked'])
@pytest.mark.parametrize('object_format',['sha1','sha256'])
def test_layers_binding_and_git_delta_oracle(tmp_path,monkeypatch,kind,object_format):
    case=produce_case(tmp_path,monkeypatch,kind=kind,object_format=object_format)
    normal=api.context(case.repository)
    before=source_bytes(case.repository)
    output=tmp_path/'safe-output';output.mkdir()
    plan=api.prepare_reference_export(case.repository,output_directory=output,expected_context=normal)
    result=api.bundle(case.repository,capture_mode='safe',export_plan=plan)
    digest=hashlib.sha256(result.path.read_bytes()).hexdigest()
    snapshot=api.read_result_snapshot(result.path,expected_sha256=digest)
    assert result.context==normal
    for layer,expected in case.expected.items():
        actual=getattr(snapshot,layer).files
        assert {n:(f.mode,f.content) for n,f in actual.items()}==expected,layer
    assert source_bytes(case.repository)==before
    oracle=create_repository(tmp_path/'oracle',with_commit=False,object_format=object_format)
    for name,(mode,content) in case.expected['base'].items():
        p=oracle/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content);p.chmod(0o755 if mode=='100755' else 0o644)
    git(oracle,'add','--all');git(oracle,'commit','--quiet','-m','independent base')
    with ZipFile(result.path) as archive:
        for layer,arguments in (('staged',['--index']),('unstaged',[])):
            raw=archive.read('changes/'+layer+'.patch')
            if raw:
                patch=tmp_path/(layer+'.patch');patch.write_bytes(raw)
                git(oracle,'apply','--binary',*arguments,str(patch))
            if layer=='staged':assert index_files(oracle)==case.expected['index']
        assert working_files(oracle,index_files(oracle))==case.expected['worktree']


@pytest.mark.parametrize('filemode',[True,False])
def test_executable_modes_follow_existing_core_filemode_contract(tmp_path,monkeypatch,filemode):
    from tests.safe_reference_support import host
    repo,exchange,output=host(tmp_path,monkeypatch)
    target=repo/'tracked.txt';target.chmod(0o755)
    git(repo,'add','tracked.txt');git(repo,'commit','--quiet','-m','executable base')
    git(repo,'config','core.fileMode','true' if filemode else 'false')
    target.chmod(0o644);target.write_bytes(b'changed content\n')
    normal=api.context(repo);before=source_bytes(repo)
    plan=api.prepare_reference_export(repo,output_directory=output,expected_context=normal)
    result=api.bundle(repo,capture_mode='safe',export_plan=plan)
    snapshot=api.read_result_snapshot(result.path)
    assert snapshot.base.files['tracked.txt'].mode==snapshot.index.files['tracked.txt'].mode=='100755'
    assert snapshot.worktree.files['tracked.txt'].mode==('100644' if filemode else '100755')
    assert source_bytes(repo)==before
