"""Real guarded Apply through the ordinary registered/locked lifecycle."""
from dataclasses import FrozenInstanceError
import hashlib
import inspect
import json
import typing
from zipfile import ZipFile

import pytest

from patchharbor import api
from tests.platform_support import native_script, native_value, project_environment
from tests.registration_support import create_repository, probe_repository_lock, set_isolated_user_environment

pytestmark = pytest.mark.e2e


@pytest.fixture
def host(tmp_path,monkeypatch):
    set_isolated_user_environment(monkeypatch,tmp_path/'user')
    repo=create_repository(tmp_path/'repo');api.register(repo)
    exchange=tmp_path/'exchange';api.configure_exchange_directory(exchange,repository=repo)
    return repo,exchange


def package(host,*,body=None,payloads=None,path=None):
    repo,exchange=host;context=api.context(repo)
    entrypoint=native_value('run.sh','run.ps1')
    body=body or native_script("printf 'approved' > execution-marker", "[IO.File]::WriteAllText('execution-marker','approved')")
    contents={'patch.json':json.dumps({'marker':'patch-harbor','format_version':1,'entrypoint':entrypoint,
        **{key:str(getattr(context,key)) for key in ('repo_id','base_commit','state_fingerprint','fingerprint_algorithm')}}).encode(),
        entrypoint:body.encode()}
    contents.update({'stage/item':b'approved payload'} if payloads is None else payloads)
    path=path or exchange/'candidate.zip'
    with ZipFile(path,'w') as z:
        for name,raw in contents.items():z.writestr(name,raw)
    return path,hashlib.sha256(path.read_bytes()).hexdigest(),contents


def guarded(host,path,digest,callback):
    return api.apply_guarded(path,expected_sha256=digest,expected_repository=host[0],admission=callback)


def no_execution(repo,report):
    assert not report.success and not report.execution_present
    assert not (repo/'stage/item').exists() and not (repo/'execution-marker').exists()


def test_complete_immutable_admission_under_actual_lock(host):
    repo,_=host;path,digest,contents=package(host);calls=[]
    def admit(facts):
        calls.append(facts)
        assert isinstance(facts,api.PatchAdmission)
        assert dict(facts.contents)==contents
        assert {e.path for e in facts.inspection.entries}==set(contents)
        assert facts.inspection.package_sha256==digest
        assert facts.inspection.manifest.repo_id==facts.context.repo_id
        assert facts.context.repository_path.value==repo.resolve()
        for entry in facts.inspection.entries:
            assert entry.sha256==hashlib.sha256(contents[entry.path]).hexdigest()
            assert entry.size==len(contents[entry.path])
        assert probe_repository_lock(str(facts.context.repo_id),project_environment())==12
        assert not (repo/'stage/item').exists() and not (repo/'execution-marker').exists()
        with pytest.raises(TypeError):facts.contents['stage/item']=b'forged'
        with pytest.raises(FrozenInstanceError):facts.context=None
        return True
    report=guarded(host,path,digest,admit)
    assert report.success and report.execution_present and len(calls)==1
    assert (repo/'stage/item').read_bytes()==b'approved payload'
    assert (repo/'execution-marker').read_text()=='approved'
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED
    snapshot=api.read_result_snapshot(report.result_bundle.path)
    assert snapshot.primary_result.success and snapshot.context.dirty
    assert snapshot.effective.files['stage/item'].content==b'approved payload'


@pytest.mark.parametrize('decision',[False,None,1,'yes',object()])
def test_only_explicit_boolean_true_accepts(host,decision):
    repo,_=host;path,digest,_=package(host);calls=[]
    def callback(facts):calls.append(facts);return decision
    report=guarded(host,path,digest,callback)
    no_execution(repo,report)
    assert len(calls)==1 and report.primary_tool_error.kind is api.ErrorKind.ADMISSION_REJECTED
    assert report.primary_tool_error.reason is api.FailureReason.SOURCE_ERROR
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED
    snapshot=api.read_result_snapshot(report.result_bundle.path)
    assert not snapshot.primary_result.success and not snapshot.primary_result.entrypoint_started


@pytest.mark.parametrize('error',[ValueError('missing evidence'),RuntimeError('failed policy'),SystemExit(0),KeyboardInterrupt()])
def test_callback_failure_is_closed_and_reported(host,error):
    repo,_=host;path,digest,_=package(host)
    def callback(_):raise error
    report=guarded(host,path,digest,callback);no_execution(repo,report)
    assert report.primary_result.failure_reason is api.FailureReason.SOURCE_ERROR
    assert report.primary_tool_error.kind is api.ErrorKind.ADMISSION_REJECTED
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED


def test_wrong_digest_rejects_before_callback_and_payload(host):
    repo,_=host;path,digest,_=package(host)
    report=guarded(host,path,'f'*64,lambda _:pytest.fail('admission of different bytes'))
    no_execution(repo,report)
    assert report.primary_result.failure_reason is api.FailureReason.SOURCE_ERROR


def test_wrong_explicit_repository_rejects_under_registered_binding(host,tmp_path):
    repo,_=host;path,digest,_=package(host)
    other=create_repository(tmp_path/'other');api.register(other)
    report=api.apply_guarded(path,expected_sha256=digest,expected_repository=other,
                             admission=lambda _:pytest.fail('wrong target admitted'))
    no_execution(repo,report)
    assert report.primary_result.failure_reason is api.FailureReason.STATE_MISMATCH
    assert not (other/'stage').exists()


def test_swap_after_external_inspection_cannot_change_expected_package(host):
    repo,_=host;path,digest,_=package(host)
    inspected=api.inspect_patch(path);assert inspected.package_sha256==digest
    package(host,path=path,payloads={'stage/item':b'swapped'})
    report=guarded(host,path,digest,lambda _:pytest.fail('replaced package admitted'))
    no_execution(repo,report)
    assert report.primary_result.failure_reason is api.FailureReason.SOURCE_ERROR


@pytest.mark.parametrize('in_exchange',[True,False])
def test_swap_during_admission_does_not_replace_owned_bytes(host,in_exchange):
    repo,_=host
    path,digest,contents=package(host,path=None if in_exchange else repo.parent/'outside.zip')
    def callback(facts):
        assert dict(facts.contents)==contents
        swapped=dict(contents)
        swapped[facts.inspection.entrypoint]=native_script('exit 37','exit 37').encode()
        swapped['stage/item']=b'swapped'
        with ZipFile(path,'w') as archive:
            for name,raw in swapped.items():archive.writestr(name,raw)
        return True
    report=guarded(host,path,digest,callback)
    if in_exchange:
        # Existing replay admission additionally revalidates the selected Exchange
        # artifact; its fail-closed refusal must not be bypassed for this API.
        no_execution(repo,report)
        assert report.primary_result.failure_reason is api.FailureReason.PATCH_PACKAGE_ERROR
    else:
        assert report.success and report.primary_result.entrypoint_exit_code==0
        assert (repo/'stage/item').read_bytes()==b'approved payload'
        assert (repo/'execution-marker').read_text()=='approved'
    assert hashlib.sha256(path.read_bytes()).hexdigest()!=digest


def test_target_change_during_admission_is_rechecked_before_writes(host):
    repo,_=host;path,digest,_=package(host)
    def callback(_):
        (repo/'tracked.txt').write_bytes(b'host changed target\n')
        return True
    report=guarded(host,path,digest,callback);no_execution(repo,report)
    assert report.primary_result.failure_reason is api.FailureReason.STATE_MISMATCH
    assert (repo/'tracked.txt').read_bytes()==b'host changed target\n'


@pytest.mark.parametrize('variant',['entrypoint','extra_payload','occupied'])
def test_host_policy_can_require_exact_script_inventory_and_fresh_staging(host,variant):
    repo,_=host
    approved=native_script("printf 'approved' > execution-marker", "[IO.File]::WriteAllText('execution-marker','approved')")
    if variant=='occupied':
        (repo/'stage').mkdir();(repo/'stage/item').write_bytes(b'existing')
    body=native_script('exit 27','exit 27') if variant=='entrypoint' else approved
    payloads={'stage/item':b'new','extra':b'not permitted'} if variant=='extra_payload' else None
    path,digest,_=package(host,body=body,payloads=payloads)
    calls=[]
    def policy(facts):
        calls.append(facts)
        allowed={'patch.json',facts.inspection.entrypoint,'stage/item'}
        return (set(facts.contents)==allowed and facts.contents[facts.inspection.entrypoint]==approved.encode()
                and not (facts.context.repository_path.value/'stage/item').exists())
    report=guarded(host,path,digest,policy)
    assert not report.success and not report.execution_present and len(calls)==1
    assert report.primary_tool_error.kind is api.ErrorKind.ADMISSION_REJECTED
    assert not (repo/'execution-marker').exists() and not (repo/'extra').exists()
    if variant=='occupied':assert (repo/'stage/item').read_bytes()==b'existing'
    else:assert not (repo/'stage/item').exists()


def test_second_attempt_obeys_actual_state_and_watcher_does_not_replay(host):
    repo,_=host;path,digest,_=package(host);calls=[]
    callback=lambda facts: calls.append(facts) or True
    first=guarded(host,path,digest,callback)
    second=guarded(host,path,digest,callback)
    assert first.success and not second.execution_present
    assert second.primary_result.failure_reason is api.FailureReason.STATE_MISMATCH
    assert len(calls)==1
    automatic=api.apply_next()
    assert automatic.automatic.status is api.AutomaticApplyStatus.NO_CANDIDATE
    assert (repo/'stage/item').read_bytes()==b'approved payload'


def test_actual_entrypoint_failure_is_preserved(host):
    repo,_=host;path,digest,_=package(host,body=native_script('exit 29','exit 29'))
    report=guarded(host,path,digest,lambda _:True)
    assert not report.success and report.execution_present
    assert report.primary_result.entrypoint_exit_code==29
    assert (repo/'stage/item').read_bytes()==b'approved payload'
    assert report.result_bundle.status is api.ResultBundleStatus.CREATED
    assert api.read_result_snapshot(report.result_bundle.path).primary_result.entrypoint_exit_code==29


def test_result_publication_failure_keeps_actual_executed_outcome(host,monkeypatch):
    from patchharbor import result_bundle_publication as publication
    repo,_=host;path,digest,_=package(host)
    def fail(*args,**kwargs):raise OSError('injected publication failure after execution')
    monkeypatch.setattr(publication,'_verify_result_bundle',fail)
    report=guarded(host,path,digest,lambda _:True)
    assert report.execution_present and report.primary_result.entrypoint_exit_code==0
    assert report.result_bundle.status is api.ResultBundleStatus.FAILED
    assert report.process_exit_code==11
    assert (repo/'stage/item').read_bytes()==b'approved payload'
    assert (repo/'execution-marker').read_text()=='approved'


def test_signatures_are_explicit_and_old_apply_contract_unchanged(host):
    repo,_=host;path,digest,_=package(host)
    assert list(inspect.signature(api.apply_guarded).parameters)==['patch','expected_sha256','expected_repository','admission','output_directory','timeout','output','observer']
    assert typing.get_type_hints(api.apply_guarded)['return'] is api.RunReport
    assert api.integration_capabilities().guarded_apply_contract_version==1
    with pytest.raises(ValueError):api.apply(path,repository=repo)
    for changes in ({'expected_sha256':'short'},{'admission':None},{'expected_repository':b'bytes'}):
        options={'expected_sha256':digest,'expected_repository':repo,'admission':lambda _:True};options.update(changes)
        with pytest.raises((TypeError,ValueError)):api.apply_guarded(path,**options)
    assert not (repo/'stage').exists()


def test_actual_execution_interrupt_retains_existing_result_contract(host,tmp_path):
    import subprocess
    import sys
    repo,_=host
    body=native_script("printf 'entrypoint-ready\\n'; sleep 60", "[Console]::Out.WriteLine('entrypoint-ready'); Start-Sleep -Seconds 60")
    path,digest,_=package(host,body=body)
    runner=tmp_path/'interrupt.py';report_file=tmp_path/'interrupt.json'
    runner.write_text(r'''
import _thread,json,sys
from pathlib import Path
from patchharbor import api
class Output:
    text=''
    signalled=False
    def write(self,value):
        self.text+=value
        if 'entrypoint-ready' in self.text and not self.signalled:
            self.signalled=True
            _thread.interrupt_main()
        return len(value)
    def flush(self):pass
report=api.apply_guarded(sys.argv[1],expected_sha256=sys.argv[2],expected_repository=sys.argv[3],
                         admission=lambda facts:True,timeout=30,output=api.OutputStreams(text=Output()))
Path(sys.argv[4]).write_text(json.dumps(report.apply_result()))
raise SystemExit(report.process_exit_code)
''')
    result=subprocess.run([sys.executable,str(runner),str(path),digest,str(repo),str(report_file)],
        cwd=tmp_path,env=project_environment(),capture_output=True,text=True,timeout=120)
    assert result.returncode==130,result.stdout+result.stderr
    report=json.loads(report_file.read_bytes())
    primary=report['primary_result']
    assert primary['kind']=='interrupted' and primary['entrypoint_started'] and primary['interrupted']
    assert primary['entrypoint_exit_code'] is None and primary['patchharbor_error_code']==130
    snapshot=api.read_result_snapshot(report['result_bundle']['path'])
    assert snapshot.primary_result.interrupted and snapshot.primary_result.entrypoint_started
    assert (repo/'stage/item').read_bytes()==b'approved payload'


def test_observer_acceptance_cannot_override_callback_denial(host):
    repo,_=host;path,digest,_=package(host)
    report=api.apply_guarded(path,expected_sha256=digest,expected_repository=repo,
        admission=lambda _:False,observer=lambda _:True)
    no_execution(repo,report)
    assert report.primary_tool_error.kind is api.ErrorKind.ADMISSION_REJECTED
