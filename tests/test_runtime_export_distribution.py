"""Actual fresh installations and executable exports; no Git or user state at export."""
from pathlib import Path
import subprocess
import sys

import pytest
from patchharbor import __version__
from scripts.release_artifacts import verify_distributions
from tests.platform_support import PROJECT_ROOT

pytestmark=pytest.mark.packaging


def build_release(artifacts):
    # Build tools may alter interpreter search paths; keep the actual build isolated.
    subprocess.run([sys.executable, str(PROJECT_ROOT/'scripts/build_release.py'),
                    '--outdir',str(artifacts)],check=True,capture_output=True,text=True,timeout=120)


@pytest.mark.proof('runtime.public-export')
def test_wheel_sdist_pyz_public_export_byte_equality(tmp_path):
    artifacts=tmp_path/'artifacts'
    build_release(artifacts)
    proofs=verify_distributions(artifacts,__version__,tmp_path/'installation')
    assert len({p['runtime']['sha256'] for p in proofs.values()})==1
    assert {p['runtime']['distribution_version'] for p in proofs.values()}=={__version__}


@pytest.mark.proof('runtime.direct-consumer', parameter='case')
@pytest.mark.parametrize('case',['clean','dirty'])
@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='safe-reference host contract requires Linux')
def test_release_pyz_direct_consumer_without_result_bootstrap(tmp_path,case):
    from hashlib import sha256
    artifacts=tmp_path/'artifacts'
    build_release(artifacts)
    runtime=artifacts/f'patchharbor-{__version__}.pyz'
    digest=sha256(runtime.read_bytes()).hexdigest()
    process=subprocess.run([sys.executable,'-I','-S','-B',str(PROJECT_ROOT/'docs/examples/verify_release_runtime.py'),
        '--runtime',str(runtime),'--sha256',digest,'--fixture-root',str(tmp_path/'fixture'),'--case',case],
        capture_output=True,text=True,timeout=120)
    assert process.returncode==0,process.stdout+process.stderr
    import json
    proof=json.loads(process.stdout)
    assert proof['source_unchanged'] and proof['runtime_sha256']==digest
    assert proof['capabilities']['safe_reference_contract_version']==1
    assert proof['capabilities']['snapshot_contract_version']==1


def test_public_consumer_rejects_hash_before_import(tmp_path):
    runtime=tmp_path/'fake.pyz';runtime.write_bytes(b'not approved')
    done=subprocess.run([sys.executable,'-I','-S','-B',str(PROJECT_ROOT/'docs/examples/verify_release_runtime.py'),
        '--runtime',str(runtime),'--sha256','0'*64,'--fixture-root',str(tmp_path/'fixture'),'--case','clean'],
        capture_output=True,text=True)
    assert done.returncode!=0 and not (tmp_path/'fixture').exists()
