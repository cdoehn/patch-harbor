"""Record reproducible local measurements; no narrow timing promises."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import pytest

from patchharbor import runtime_pyz as pyz
from tests.test_pack_api import request_files


@pytest.mark.packaging
def test_real_pyz_start_and_pack_record_environment_size_and_memory(built_result_source, request_files, tmp_path):
    recipe=pyz.parse_recipe((built_result_source/pyz.RECIPE_PATH).read_bytes())
    raw=pyz.materialize(recipe,lambda name,size:(built_result_source/name).read_bytes())
    archive=tmp_path/recipe.pyz_name;archive.write_bytes(raw)
    contents,reference,output=request_files
    payload=bytes(range(256))*4096
    (contents/'representative.bin').write_bytes(payload)
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    rows=[]
    for sample in range(3):
        started=time.perf_counter()
        process=subprocess.run([sys.executable,'-I','-S','-B',str(archive),'--version'],
                               cwd=tmp_path,env=environment,capture_output=True,text=True)
        startup=time.perf_counter()-started
        assert process.returncode==0,process.stderr
        child=subprocess.run([sys.executable,'-I','-S','-B','-c',r'''
import json,sys,time,tracemalloc
sys.path.insert(0,sys.argv[1])
from patchharbor import api
tracemalloc.start();start=time.perf_counter()
p=api.pack_patch(sys.argv[2],reference_bundle=sys.argv[3],entrypoint='run.sh',output_directory=sys.argv[4])
elapsed=time.perf_counter()-start;peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
assert p.validation.binding_matches and p.validation.scope=='reference'
print(json.dumps({'pack_seconds':elapsed,'peak_python_bytes':peak,'package_bytes':p.package_size,
                  'package_sha256':p.package_sha256,'reference_sha256':p.reference_sha256,'origin':api.__file__}))
''',str(archive),str(contents),str(reference),str(output)],cwd=tmp_path,env=environment,capture_output=True,text=True)
        assert child.returncode==0,child.stdout+child.stderr
        row=json.loads(child.stdout)
        assert row['origin'].startswith(str(archive)+os.sep)
        assert row['peak_python_bytes']>0 and row['package_bytes']>0
        rows.append(dict(sample=sample,startup_seconds=startup,**row))
    measured={'method':'three fresh -I -S -B processes; perf_counter wall time and tracemalloc Python peak',
              'python':platform.python_version(),'platform':platform.platform(),'implementation':platform.python_implementation(),
              'worker':os.environ.get('PYTEST_XDIST_WORKER'), 'representative_bytes':len(payload),
              'total_content_bytes':sum(p.stat().st_size for p in contents.rglob('*') if p.is_file()),
              'pyz_sha256':hashlib.sha256(raw).hexdigest(),'pyz_bytes':len(raw),'samples':rows}
    (tmp_path/'pyz-pack-measurements.json').write_text(json.dumps(measured,indent=2)+'\n')
