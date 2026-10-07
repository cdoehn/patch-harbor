"""Run the executable handoff resource, including its strict native reference path."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from patchharbor import runtime_pyz as pyz
from tests.embedded_pyz_support import bootstrap_program
from tests.result_pyz_support import attach_pyz
from tests.test_pack_api import request_files
from tests.test_reference_validation import reference_entries, write_reference


@pytest.mark.packaging
@pytest.mark.parametrize('corrupt_snapshot',[False,True])
def test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result(
    built_result_source, request_files, tmp_path, corrupt_snapshot,
):
    recipe=pyz.parse_recipe((built_result_source/pyz.RECIPE_PATH).read_bytes())
    raw=pyz.materialize(recipe,lambda name,size:(built_result_source/name).read_bytes())
    files,_=reference_entries(handoff=True)
    files=attach_pyz(files,raw)
    files['CHAT_INSTRUCTIONS.md']=(built_result_source/pyz.CHAT_PATH).read_bytes()
    if corrupt_snapshot:files['base/tracked.txt']+=b'changed after snapshot'
    reference=tmp_path/'actual-reference.zip';write_reference(reference,files)
    # The executable program comes only from the handoff carried by this Result.
    helper=tmp_path/'reviewed-from-result.py'
    helper.write_text(bootstrap_program(files['CHAT_INSTRUCTIONS.md']))
    outside=tmp_path/'outside';outside.mkdir()
    (outside/'patchharbor.py').write_text('raise AssertionError("foreign CWD")\n')
    contents,_,output=request_files
    code = """
import hashlib, importlib.util, json, os, socket, subprocess, sys
from pathlib import Path
helper, reference, workspace, contents, output = map(Path,sys.argv[1:6])
corrupt = sys.argv[6] == 'True'
spec=importlib.util.spec_from_file_location('reviewed_embedded_bootstrap',helper)
bootstrap=importlib.util.module_from_spec(spec);sys.modules[spec.name]=bootstrap;spec.loader.exec_module(bootstrap)
assert not any(n=='patchharbor' or n.startswith('patchharbor.') for n in sys.modules)
def forbidden(*a,**k):raise AssertionError('external operation during Python-only handoff')
subprocess.run=subprocess.Popen=socket.socket=forbidden
os.environ['PATH']=''
assessment=bootstrap.assess(reference,trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
assert not assessment.full_reference_valid and assessment.scope=='runtime_descriptor_precheck'
prepared=bootstrap.prepare(assessment,workspace)
api=bootstrap.import_api(prepared)
if corrupt:
    try:api.pack_patch(contents,reference_bundle=reference,entrypoint='run.sh',output_directory=output)
    except api.PatchHarborError as exc:assert exc.reason is api.FailureReason.SOURCE_ERROR
    else:raise AssertionError('descriptor precheck bypassed native snapshot validation')
    assert not list(output.iterdir())
    print(json.dumps({'native_reference_rejected':True}))
else:
    packed=api.pack_patch(contents,reference_bundle=reference,entrypoint='run.sh',output_directory=output)
    inspected=api.inspect_patch(packed.path)
    checked=api.validate_patch(packed.path,reference_bundle=reference)
    assert checked.binding_matches and checked.scope=='reference'
    assert checked.reference_sha256==assessment.reference_sha256
    assert inspected.package_sha256==packed.package_sha256
    assert 'patchharbor_watcher' not in sys.modules
    print(json.dumps({'package_sha256':packed.package_sha256,'reference_sha256':checked.reference_sha256,
                      'runtime_sha256':assessment.artifact_sha256,'api_origin':api.__file__}))
"""
    run=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(helper),str(reference),
                        str(tmp_path/'private'),str(contents),str(output),str(corrupt_snapshot)],
                       cwd=outside,capture_output=True,text=True,timeout=90)
    assert run.returncode==0,run.stdout+run.stderr
    data=json.loads(run.stdout)
    if corrupt_snapshot:assert data['native_reference_rejected'] is True
    else:
        assert data['reference_sha256']==hashlib.sha256(reference.read_bytes()).hexdigest()
        assert data['runtime_sha256']==hashlib.sha256(raw).hexdigest()
        assert str(tmp_path/'private'/recipe.pyz_name) in data['api_origin']
