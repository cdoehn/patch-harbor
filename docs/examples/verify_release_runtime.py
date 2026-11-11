"""Executable consumer proof using public APIs after an externally expected hash.

Use only in a fresh process with a trusted Python interpreter, protected runtime
file and a new synthetic fixture root. No Result is needed to load the library.
The neighboring fixture helper creates only a new isolated demonstration repo.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import sys


def load_runtime(path, expected):
    path=Path(path).absolute()
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('a complete externally approved SHA-256 is required')
    if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError('runtime does not match the externally approved bytes')
    if any(n=='patchharbor' or n.startswith('patchharbor.') for n in sys.modules):
        raise RuntimeError('use a fresh process; PatchHarbor is already loaded')
    sys.path.insert(0,str(path))
    from patchharbor import api
    if not api.__file__.startswith(str(path)+os.sep):
        raise RuntimeError('unexpected library origin')
    caps=api.integration_capabilities()
    expected_contracts = {'contract_version': 2, 'snapshot_contract_version': 2,
                          'guarded_execute_contract_version': 2, 'safe_reference_contract_version': 1}
    for name, expected in expected_contracts.items():
        if type(getattr(caps,name,None)) is not int or getattr(caps,name)!=expected:
            raise RuntimeError('required integration contract unavailable: '+name)
    return api,caps


def inventory(root):
    return {p.relative_to(root).as_posix():{'mode':p.stat().st_mode,'sha256':sha256(p.read_bytes()).hexdigest()}
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--fixture-root',required=True,type=Path)
    parser.add_argument('--case',required=True,choices=('clean','dirty'))
    args=parser.parse_args()
    api,caps=load_runtime(args.runtime,args.sha256)
    here=Path(__file__).resolve().parent
    fixture=runpy.run_path(str(here/'create_safe_reference_fixture.py'))['create_fixture']
    root=args.fixture_root.absolute()
    repository,output,expected=fixture(root,dirty=args.case=='dirty')
    before=inventory(repository)
    # Consumers must perform their own closure/policy decision. This example
    # admits only its freshly created synthetic repo and private fixture state.
    context=api.context(repository,capture_mode='safe')
    plan=api.prepare_reference_export(repository,output_directory=output,expected_context=context)
    if (plan.context!=context or plan.context.repository_path.value!=repository
            or plan.output_directory!=output or plan.diagnostics_parent!=output
            or plan.maintenance_enabled or not plan.lock_paths
            or any(not p.is_relative_to(root) for p in plan.lock_paths)):
        raise PermissionError('plan exceeds this synthetic fixture operating boundary')
    bundle=api.bundle(repository,capture_mode='safe',export_plan=plan)
    external_result_sha=sha256(bundle.path.read_bytes()).hexdigest()
    snapshot=api.read_result_snapshot(bundle.path,expected_sha256=external_result_sha)
    assert snapshot.context.dirty==(args.case=='dirty')
    for layer,files in expected.items():
        assert {n:(f.mode,f.content) for n,f in getattr(snapshot,layer).files.items()}==files,layer
    assert inventory(repository)==before
    assert snapshot.runtime.status=='embedded' and snapshot.runtime.artifact_sha256==args.sha256
    assert snapshot.runtime.profile=='patchharbor-core-no-watcher-v1'
    print(json.dumps({'case':args.case,'runtime_sha256':args.sha256,'runtime_size':args.runtime.stat().st_size,
        'capabilities':asdict(caps),'result':str(bundle.path),'result_sha256':external_result_sha,
        'context':{n:str(getattr(snapshot.context,n)) for n in
                   ('repo_id','base_commit','state_fingerprint','fingerprint_algorithm')},
        'source_unchanged':True,'source_inventory':before,
        'layers':{n:{p:{'size':f.size,'mode':f.mode,'sha256':f.sha256} for p,f in getattr(snapshot,n).files.items()}
                  for n in ('base','index','worktree','untracked','effective')}},indent=2))


if __name__=='__main__':main()
