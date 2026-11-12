"""Build a candidate before tagging; publish its original bytes only after exact CI."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import run_handoff_ci as ci
from scripts.build_release import build_release
from scripts.release_source import source_checkout
from scripts.release_artifacts import names, require, verify_assets, verify_distributions, write_manifest


def github(route, *, method='GET', body=None, binary=False, missing=False):
    command=['gh','api','--hostname','github.com','--method',method,
             '-H','X-GitHub-Api-Version: 2026-03-10',f'repos/{ci.REPOSITORY}/{route}']
    if binary: command += ['-H','Accept: application/octet-stream']
    if body is not None: command += ['--input','-']
    result=subprocess.run(command,input=None if body is None else json.dumps(body).encode(),
                          capture_output=True,timeout=180)
    if missing and result.returncode and b'(HTTP 404)' in result.stderr:
        return None
    require(result.returncode==0,'GitHub operation failed: '+result.stderr.decode(errors='replace'))
    return result.stdout if binary else (json.loads(result.stdout) if result.stdout.strip() else None)


def checkout(version, commit):
    source_checkout(version,commit,root=ROOT)
    observed=github('commits/'+commit)
    require(observed['sha']==commit,'release commit is not on GitHub')


def accepted_run(commit, run_id):
    workflow=github('actions/workflows/'+ci.WORKFLOW)
    observed=github(f'actions/runs/{run_id}')
    require(observed['head_sha']==commit and observed['head_branch']==ci.BRANCH
            and observed['event']=='workflow_dispatch' and observed['workflow_id']==workflow['id']
            and observed['status']=='completed' and observed['conclusion']=='success',
            'required exact-commit acceptance is not green')
    jobs=ci.pages(f'actions/runs/{run_id}/attempts/{observed["run_attempt"]}/jobs','jobs')
    ci.validate_jobs(jobs,commit)
    return observed


def check_tag(version, commit):
    tag='v'+version
    ref=github('git/ref/tags/'+tag,missing=True)
    if ref is not None:
        obj=ref['object']
        # Existing annotated tags are accepted only after exact peeling.
        for _ in range(4):
            if obj['type']!='tag':break
            obj=github('git/tags/'+obj['sha'])['object']
        require(obj['type']=='commit' and obj['sha']==commit,'existing release tag conflicts')
    return ref


def prepare(version, commit, output, workspace):
    checkout(version,commit)
    check_tag(version,commit)
    output.mkdir(parents=True,exist_ok=False)
    build_release(output)
    proofs=verify_distributions(output,version,workspace/'distribution')
    pyz_sha=proofs['pyz']['runtime']['sha256']
    # Public-only safe-reference consumer, using the exact candidate and external hash.
    for kind in ('clean','dirty'):
        done=subprocess.run([sys.executable,'-I','-S','-B',str(ROOT/'docs/examples/verify_release_runtime.py'),
            '--runtime',str(output/names(version)[0]),'--sha256',pyz_sha,
            '--fixture-root',str(workspace/kind),'--case',kind],check=True,capture_output=True,text=True)
        (workspace/(kind+'-proof.json')).write_text(done.stdout)
    manifest=write_manifest(output,version,commit,proofs['pyz'])
    checkout(version,commit)
    (workspace/'prepared.json').write_text(json.dumps({'version':version,'commit':commit,
        'manifest_sha256':sha256((output/'runtime-manifest.json').read_bytes()).hexdigest(),
        'runtime':manifest['runtime'],'distribution_proofs':proofs},indent=2)+'\n')


def compare_downloads(release, directory, version, *, complete):
    required=set(names(version));assets=release['assets']
    require(len({a['name'] for a in assets})==len(assets),'duplicate release assets')
    require({a['name'] for a in assets} <= required,'unexpected release assets')
    if complete:require({a['name'] for a in assets}==required,'release asset set is incomplete')
    for asset in assets:
        require(asset['state']=='uploaded','asset upload is incomplete')
        raw=github('releases/assets/'+str(asset['id']),binary=True)
        require(raw==(directory/asset['name']).read_bytes(),'downloaded asset differs from approved bytes: '+asset['name'])
        require(asset['size']==len(raw),'asset size mismatch')
    return {a['name'] for a in assets}


def publish(version, commit, run_id, directory, workspace):
    checkout(version,commit)
    observed=accepted_run(commit,run_id)
    manifest=verify_assets(directory,version,commit)
    prepared=json.loads((workspace/'prepared.json').read_bytes())
    require(prepared['version']==version and prepared['commit']==commit
            and prepared['manifest_sha256']==sha256((directory/'runtime-manifest.json').read_bytes()).hexdigest(),
            'prepared artifact binding differs')
    review=ci.run(commit,run_id,attempt=observed['run_attempt'],workspace=workspace/'ci'/uuid4().hex)
    require(review['status']=='success','complete CI evidence required')
    verify_ci_builds(review,version,manifest['runtime']['sha256'])
    marker='PatchHarbor verified runtime release: '+commit+' / '+prepared['manifest_sha256']
    release=github('releases/tags/v'+version,missing=True)
    check_tag(version,commit)
    if release is not None:
        require(release['tag_name']=='v'+version and not release['prerelease'],'release metadata conflict')
        if release['draft']:
            require(release['body'].startswith(marker+'\n') and release['target_commitish']==commit,
                    'existing draft is not this prepared release')
        else:
            require(check_tag(version,commit) is not None,'published release lacks exact tag')
        present=compare_downloads(release,directory,version,complete=not release['draft'])
        if not release['draft']:
            save_publication(workspace,release,manifest,observed)
            return release
    else:
        present=set()
    require(check_tag(version,commit) is not None, 'existing exact-commit release tag is required')
    if release is None:
        release=github('releases',method='POST',body={'tag_name':'v'+version,'target_commitish':commit,
            'name':'PatchHarbor '+version,'draft':True,'prerelease':False,
            'body':marker+'\n\nCore-PYZ, wheel and built sdist with exact source and byte provenance.\n\n'
                   'Acceptance: '+observed['html_url']+'\n\nPYZ SHA-256: '+manifest['runtime']['sha256']+
                   '\n\nUse an independently trusted expected hash before importing the PYZ. '
                   'CPython >=3.10; safe-reference contract 1 is Linux x86-64 / CPython 3.10–3.14.\n'})
    for name in names(version):
        if name not in present:
            # gh uses the release upload endpoint; no clobber or replacement.
            subprocess.run(['gh','release','upload','v'+version,str(directory/name),
                            '--repo',ci.REPOSITORY],check=True,timeout=180)
    release=github('releases/'+str(release['id']))
    compare_downloads(release,directory,version,complete=True)
    accepted_run(commit,run_id)
    require(check_tag(version,commit) is not None,'release tag disappeared before publication')
    require(release['draft'] and release['body'].startswith(marker+'\n'),'draft changed before publication')
    release=github('releases/'+str(release['id']),method='PATCH',body={'draft':False})
    require(not release['draft'],'release remained a draft')
    # Re-download every published asset; uploading is not a download proof.
    compare_downloads(github('releases/'+str(release['id'])),directory,version,complete=True)
    require(check_tag(version,commit) is not None,'published release lacks exact tag')
    save_publication(workspace,release,manifest,observed)
    return release


def verify_ci_builds(review,version,pyz_sha):
    for lane in review['artifacts']:
        require(lane['build']['version']==version,'CI version differs')
        built=[a for a in lane['build']['artifacts'] if a['name']==names(version)[0]]
        require(len(built)==1 and built[0]['sha256']==pyz_sha,'CI canonical PYZ differs from release')


def save_publication(workspace,release,manifest,observed):
    (workspace/'published.json').write_text(json.dumps({'release':release,'manifest':manifest,
        'acceptance_url':observed['html_url'],'download_verified':True},indent=2)+'\n')


def verify_preparation(commit, run_id):
    require(os.environ.get('DISPATCH_COMMIT',commit)==commit,'release dispatch commit mismatch')
    workflow=github('actions/workflows/'+ci.WORKFLOW)
    observed=github(f'actions/runs/{run_id}')
    require(observed['head_sha']==commit and observed['head_branch']==ci.BRANCH
            and observed['event']=='workflow_dispatch' and observed['workflow_id']==workflow['id']
            and observed['status']=='completed' and observed['conclusion']=='success',
            'preparation run does not match the approved commit')
    jobs=ci.pages(f'actions/runs/{run_id}/attempts/{observed["run_attempt"]}/jobs','jobs')
    prepared=[j for j in jobs if j['name']=='Prepare verified runtime release']
    require(len(prepared)==1 and prepared[0]['conclusion']=='success' and prepared[0]['head_sha']==commit,
            'preparation job is not successful')
    artifacts=ci.pages(f'actions/runs/{run_id}/artifacts','artifacts')
    matches=[a for a in artifacts if a['name']=='patchharbor-prepared-release' and not a['expired']]
    require(len(matches)==1,'prepared artifact missing or ambiguous')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('prepare','publish','verify-preparation'))
    parser.add_argument('--version',required=True)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--acceptance-run-id',type=int)
    parser.add_argument('--assets',required=True,type=Path)
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--prepared-run-id',type=int)
    a=parser.parse_args()
    if a.operation=='verify-preparation':
        require(type(a.prepared_run_id) is int and a.prepared_run_id>0,'preparation Run-ID required')
        checkout(a.version,a.commit)
        verify_preparation(a.commit,a.prepared_run_id)
        return
    a.workspace.mkdir(parents=True,exist_ok=True)
    if a.operation=='prepare':
        prepare(a.version,a.commit,a.assets.absolute(),a.workspace.absolute())
    else:
        require(type(a.acceptance_run_id) is int and a.acceptance_run_id>0,'acceptance Run-ID required')
        publish(a.version,a.commit,a.acceptance_run_id,a.assets.absolute(),a.workspace.absolute())


if __name__=='__main__':main()
