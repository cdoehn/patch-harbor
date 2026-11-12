"""Prepare exact local release assets without GitHub, tags or publication."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0,str(ROOT))

from scripts.build_release import build_release
from scripts.release_source import source_checkout
from scripts.release_artifacts import names, require, verify_distributions, write_manifest




def prepare(version, commit, output, workspace):
    source_checkout(version,commit)
    output, workspace = output.absolute(), workspace.absolute()
    require(output != workspace and output not in workspace.parents and workspace not in output.parents,
            'asset and evidence directories must be separate')
    output.mkdir(parents=True,exist_ok=False)
    workspace.mkdir(parents=True,exist_ok=False)
    build_release(output)
    proofs = verify_distributions(output,version,workspace/'distribution')
    pyz_sha = proofs['pyz']['runtime']['sha256']
    for kind in ('clean','dirty'):
        done = subprocess.run([sys.executable,'-I','-S','-B',str(ROOT/'docs/examples/verify_release_runtime.py'),
            '--runtime',str(output/names(version)[0]),'--sha256',pyz_sha,
            '--fixture-root',str(workspace/kind),'--case',kind],check=True,capture_output=True,text=True,timeout=600)
        (workspace/(kind+'-proof.json')).write_text(done.stdout,encoding='utf-8')
    manifest = write_manifest(output,version,commit,proofs['pyz'])
    source_checkout(version,commit)
    receipt = {'version':version,'commit':commit,'runtime':manifest['runtime'],
               'manifest_sha256':sha256((output/'runtime-manifest.json').read_bytes()).hexdigest(),
               'distribution_proofs':proofs,'scope':'local candidate only',
               'native_ci_complete':False,'tag_created':False,'published':False}
    (workspace/'local-candidate.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',required=True)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--assets',required=True,type=Path)
    parser.add_argument('--workspace',required=True,type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.version,args.commit,args.assets,args.workspace),sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
