"""Fail-closed release metadata and publication sequencing; never publish test releases."""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest
from scripts import release_artifacts as assets, release_runtime as release

COMMIT='a'*40


@pytest.fixture
def candidate(tmp_path,monkeypatch):
    version='2.7.3'
    root=tmp_path/'assets';root.mkdir()
    required=assets.names(version)
    for n in required[:3]:(root/n).write_bytes(('synthetic '+n).encode())
    raw=(root/required[0]).read_bytes()
    proof={'runtime':{'distribution_version':version,'size':len(raw),'sha256':sha256(raw).hexdigest(),
        'profile':'patchharbor-core-no-watcher-v1','requires_python':'>=3.10','content_id':'b'*64},
        'capabilities':{'contract_version':1,'snapshot_contract_version':1,'guarded_apply_contract_version':1,
                        'safe_reference_contract_version':1},
        'host':{'system':'Linux','machine':'x86_64','python':'3.14.4','implementation':'CPython'}}
    monkeypatch.setattr(assets,'_audit_release_artifacts',lambda *a:None)
    monkeypatch.setattr(assets,'_wheel_contract',lambda *a:SimpleNamespace(version=version))
    monkeypatch.setattr(assets,'canonical_pyz_from_wheel',lambda *a:(SimpleNamespace(version=version,content_id='b'*64,requires_python='>=3.10'),raw))
    manifest=assets.write_manifest(root,version,COMMIT,proof)
    work=tmp_path/'work';work.mkdir()
    (work/'prepared.json').write_text(json.dumps({'version':version,'commit':COMMIT,'acceptance_run_id':123,
        'manifest_sha256':sha256((root/'runtime-manifest.json').read_bytes()).hexdigest()}))
    return SimpleNamespace(root=root,version=version,manifest=manifest,work=work)


def test_future_version_has_exact_complete_asset_contract(candidate):
    c=candidate
    assert assets.verify_assets(c.root,c.version,COMMIT)==c.manifest
    lines=(c.root/'SHA256SUMS').read_text().splitlines()
    assert len(lines)==4 and not any(line.endswith('  SHA256SUMS') for line in lines)


@pytest.mark.parametrize('fault',['missing','unexpected','hash','commit','version','tag','size','capability','host','self_checksum'])
def test_incomplete_or_conflicting_assets_are_rejected(candidate,fault):
    c=candidate;p=c.root/'runtime-manifest.json';doc=json.loads(p.read_bytes())
    if fault=='missing':(c.root/assets.names(c.version)[0]).unlink()
    elif fault=='unexpected':(c.root/'private.log').write_bytes(b'do not release')
    elif fault=='hash':(c.root/assets.names(c.version)[0]).write_bytes(b'changed')
    elif fault in ('commit','version','tag'):doc[{'commit':'source_commit'}.get(fault,fault)]='wrong'
    elif fault=='size':doc['runtime']['size']=True
    elif fault=='capability':doc['integration_capabilities']['snapshot_contract_version']=True
    elif fault=='host':doc['capability_host']={}
    else:(c.root/'SHA256SUMS').write_text('0'*64+'  SHA256SUMS\n')
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError):assets.verify_assets(c.root,c.version,COMMIT)


@pytest.mark.parametrize('value',['1.8','v1.8.0','../1.8.0','1.8.0\n','1.8.0;run',None])
def test_release_version_cannot_select_paths_or_commands(value):
    with pytest.raises(ValueError):assets.names(value)


def test_exact_commit_ci_and_every_lane_required(monkeypatch):
    good={'head_sha':COMMIT,'head_branch':'dev','workflow_id':1,'event':'workflow_dispatch',
          'status':'completed','conclusion':'success','run_attempt':1}
    jobs=[{'name':n,'head_sha':COMMIT,'status':'completed','conclusion':'success'} for n in release.ci.JOBS]
    monkeypatch.setattr(release.ci,'pages',lambda *a:deepcopy(jobs))
    monkeypatch.setattr(release,'github',lambda route: {'id':1} if 'workflows/' in route else deepcopy(good))
    assert release.accepted_run(COMMIT,123)==good
    for key,value in [('head_sha','b'*40),('conclusion','failure'),('status','in_progress'),('event','push')]:
        old=good[key];good[key]=value
        with pytest.raises(ValueError):release.accepted_run(COMMIT,123)
        good[key]=old
    jobs.pop()
    with pytest.raises(ValueError):release.accepted_run(COMMIT,123)


@pytest.mark.parametrize('existing',[None,COMMIT,'b'*40])
def test_tag_check_is_readonly_and_never_overwrites_conflicting_ref(monkeypatch,existing):
    calls=[]
    def github(route,**kw):
        calls.append((route,kw))
        if kw.get('method')=='POST':return {'object':{'type':'commit','sha':kw['body']['sha']}}
        return None if existing is None else {'object':{'type':'commit','sha':existing}}
    monkeypatch.setattr(release,'github',github)
    if existing not in (None,COMMIT):
        with pytest.raises(ValueError):release.check_tag('2.7.3',COMMIT)
    else:release.check_tag('2.7.3',COMMIT)
    assert all(kw.get('method','GET')=='GET' for _,kw in calls)


@pytest.mark.parametrize('fault',['red_ci','missing_asset','changed_preparation'])
def test_publication_stops_before_tag_or_draft_when_gates_fail(candidate,monkeypatch,fault):
    c=candidate;calls=[]
    monkeypatch.setattr(release,'checkout',lambda *a:None)
    def accepted(*a):
        if fault=='red_ci':raise ValueError('CI failed')
        return {'html_url':'https://example.invalid/acceptance'}
    monkeypatch.setattr(release,'accepted_run',accepted)
    monkeypatch.setattr(release,'github',lambda *a,**k:calls.append((a,k)))
    if fault=='missing_asset':(c.root/assets.names(c.version)[0]).unlink()
    if fault=='changed_preparation':(c.work/'prepared.json').write_text('{}')
    with pytest.raises((ValueError,KeyError)):
        release.publish(c.version,COMMIT,123,c.root,c.work)
    assert not calls


@pytest.mark.parametrize('bad_download',[False,True])
def test_draft_upload_download_publish_and_redownload(candidate,monkeypatch,bad_download):
    c=candidate;calls=[];state={'tag':{'object':{'type':'commit','sha':COMMIT}},'release':None};downloads=[]
    monkeypatch.setattr(release,'checkout',lambda *a:None)
    monkeypatch.setattr(release,'accepted_run',lambda *a:{'html_url':'https://example.invalid/acceptance','run_attempt':1})
    monkeypatch.setattr(release.ci,'run',lambda *a,**kw:{'status':'success','artifacts':[
        {'build':{'version':c.version,'artifacts':[{'name':assets.names(c.version)[0],
        'sha256':c.manifest['runtime']['sha256']}]}}]})
    def github(route,**kw):
        calls.append((route,kw.get('method','GET')))
        if route.startswith('git/ref/'):return state['tag']
        if route=='git/refs':
            state['tag']={'object':{'type':'commit','sha':kw['body']['sha']}};return state['tag']
        if route.startswith('releases/tags/'):return deepcopy(state['release'])
        if route=='releases':
            state['release']={'id':4,**kw['body'],'assets':[]};return deepcopy(state['release'])
        if route=='releases/4':
            if kw.get('method')=='PATCH':state['release'].update(kw['body'])
            return deepcopy(state['release'])
        if route.startswith('releases/assets/'):
            asset=next(a for a in state['release']['assets'] if a['id']==int(route.rsplit('/',1)[1]))
            downloads.append((asset['name'],state['release']['draft']))
            return b'corrupt' if bad_download else (c.root/asset['name']).read_bytes()
        pytest.fail(route)
    def upload(command,**kw):
        assert command[:3]==['gh','release','upload'] and '--clobber' not in command
        assert state['release']['draft']
        from pathlib import Path
        p=Path(command[4]);state['release']['assets'].append({'id':len(state['release']['assets'])+1,
            'name':p.name,'size':p.stat().st_size,'state':'uploaded'})
    monkeypatch.setattr(release,'github',github);monkeypatch.setattr(release.subprocess,'run',upload)
    if bad_download:
        with pytest.raises(ValueError):release.publish(c.version,COMMIT,123,c.root,c.work)
        assert state['release']['draft']
    else:
        result=release.publish(c.version,COMMIT,123,c.root,c.work)
        assert not result['draft'] and len(downloads)==10
        assert {draft for _,draft in downloads}=={False,True}
        calls.clear()
        (c.work/'published.json').unlink()
        assert not release.publish(c.version,COMMIT,123,c.root,c.work)['draft']
        assert all(method=='GET' for _,method in calls)
        assert json.loads((c.work/'published.json').read_bytes())['download_verified']


@pytest.mark.parametrize('fault',['version','missing','hash'])
def test_ci_canonical_bytes_must_equal_prepared_candidate(fault):
    build={'version':'2.7.3','artifacts':[{'name':'patchharbor-2.7.3.pyz','sha256':'c'*64}]}
    review={'artifacts':[{'build':build}]}
    release.verify_ci_builds(review,'2.7.3','c'*64)
    if fault=='version':build['version']='2.7.4'
    elif fault=='missing':build['artifacts']=[]
    else:build['artifacts'][0]['sha256']='d'*64
    with pytest.raises(ValueError):release.verify_ci_builds(review,'2.7.3','c'*64)


def test_publication_requires_existing_tag_before_any_write(candidate,monkeypatch):
    c=candidate;calls=[]
    monkeypatch.setattr(release,'checkout',lambda *a:None)
    monkeypatch.setattr(release,'accepted_run',lambda *a:{'run_attempt':1})
    monkeypatch.setattr(release.ci,'run',lambda *a,**kw:{'status':'success','artifacts':[]})
    def github(route,**kw):
        calls.append(kw.get('method','GET'))
        return None
    monkeypatch.setattr(release,'github',github)
    with pytest.raises(ValueError):release.publish(c.version,COMMIT,123,c.root,c.work)
    assert calls and set(calls)=={'GET'}


def test_prepare_builds_and_checks_without_ci_or_tag(candidate,monkeypatch,tmp_path):
    c=candidate;calls=[];output=tmp_path/'prepared-assets'
    monkeypatch.setattr(release,'checkout',lambda *a:calls.append('checkout'))
    monkeypatch.setattr(release,'check_tag',lambda *a:None)
    monkeypatch.setattr(release,'accepted_run',lambda *a:pytest.fail('CI before candidate'))
    def build(out):
        import shutil
        for name in assets.names(c.version)[:3]:shutil.copy2(c.root/name,out/name)
        calls.append('build')
    proof={'runtime':{'sha256':c.manifest['runtime']['sha256']}}
    monkeypatch.setattr(release,'build_release',build)
    monkeypatch.setattr(release,'verify_distributions',lambda *a: {'pyz':proof})
    def manifest(out,*args):
        (out/'runtime-manifest.json').write_text(json.dumps(c.manifest))
        calls.append('manifest');return c.manifest
    monkeypatch.setattr(release,'write_manifest',manifest)
    monkeypatch.setattr(release.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout='{}'))
    release.prepare(c.version,COMMIT,output,c.work)
    assert calls==['checkout','build','manifest','checkout']
    assert json.loads((c.work/'prepared.json').read_bytes())['commit']==COMMIT
