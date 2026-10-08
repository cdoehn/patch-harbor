"""Executable pack examples: real installed CLI, PYZ CLI/API and regular Apply."""
import hashlib
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor.result_reader import read_result_reference
from tests.platform_support import native_python_script, native_script, native_value
from tests.registration_support import create_repository, git
from tests.test_pyz_result_e2e import installed_producer
from tests.test_runtime_packaging import _run

pytestmark = pytest.mark.packaging


@pytest.mark.parametrize('route', ['installed_cli', 'pyz_cli', 'pyz_api'])
@pytest.mark.parametrize('kind', ['full', 'diff', 'mixed', 'diagnostic', 'broken'])
def test_documented_pack_workflows_preserve_execution_boundary(installed_producer, tmp_path, route, kind):
    repo = create_repository(tmp_path/'repository')
    before = git(repo, 'rev-parse', 'HEAD').stdout
    environment = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    reference = Path(json.loads(_run([str(installed_producer), '-I', '-B', '-c', '''
import json,sys
from patchharbor import api
api.register(sys.argv[1]);api.configure_exchange_directory(sys.argv[2],repository=sys.argv[1])
print(json.dumps(str(api.bundle(sys.argv[1]).path)))
''', str(repo), str(tmp_path/'exchange')], tmp_path, environment)))
    facts, reference_sha = read_result_reference(reference)
    assert facts.format_version == 3 and facts.runtime.status == 'embedded'
    runtime = tmp_path/'selected.pyz'
    with ZipFile(reference) as archive: runtime.write_bytes(archive.read(facts.runtime.artifact.path))
    assert hashlib.sha256(runtime.read_bytes()).hexdigest() == facts.runtime.artifact.sha256
    contents = tmp_path/'contents'; contents.mkdir()
    output = tmp_path/'output'; output.mkdir()
    entry = native_value('run.sh','run.ps1')
    if kind == 'full': (contents/'tracked.txt').write_bytes(b'changed\n')
    if kind in ('diff','mixed'):
        (contents/'change.patch').write_bytes(b'diff --git a/tracked.txt b/tracked.txt\n--- a/tracked.txt\n+++ b/tracked.txt\n@@ -1 +1 @@\n-base\n+changed\n')
    if kind == 'mixed': (contents/'payload.bin').write_bytes(b'\0extra\xff')
    code = 'from pathlib import Path\nimport subprocess\n'
    if kind in ('diff','mixed'): code += "subprocess.run(['git','apply','--','change.patch'],check=True)\n"
    expected = b'changed\n' if kind in ('full','diff','mixed') else b'base\n'
    code += f"assert Path('tracked.txt').read_bytes()=={expected!r}\n"
    if kind == 'mixed': code += "assert Path('payload.bin').read_bytes()==b'\\0extra\\xff'\n"
    code += "print('diagnostic-evidence')\n"
    script = native_script('if deliberately broken (', 'if (') if kind == 'broken' else native_python_script(code)
    (contents/entry).write_text(script)
    if route == 'pyz_api':
        packed = json.loads(_run([sys.executable, '-I','-S','-B','-c', '''
import json,sys
sys.path.insert(0,sys.argv[1])
from patchharbor import api
p=api.pack_patch(sys.argv[2],reference_bundle=sys.argv[3],entrypoint=sys.argv[4],output_directory=sys.argv[5])
v=api.validate_patch(p.path,reference_bundle=sys.argv[3])
assert v.binding_matches and v.scope=='reference'
print(json.dumps({'path':str(p.path),'package_sha256':p.package_sha256,'reference_sha256':v.reference_sha256}))
''',str(runtime),str(contents),str(reference),entry,str(output)],tmp_path,environment))
    else:
        prefix = ([str(installed_producer),'-I','-B','-m','patchharbor.cli'] if route == 'installed_cli'
                  else [sys.executable,'-I','-S','-B',str(runtime)])
        packed = json.loads(_run([*prefix,'pack',str(contents),'--reference-bundle',str(reference),
                                 '--entrypoint',entry,'--output-dir',str(output),'--json'],tmp_path,environment))['result']
    patch = Path(packed['path'])
    assert packed['reference_sha256'] == reference_sha
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == packed['package_sha256']
    assert api.validate_patch(patch,reference_bundle=reference).binding_matches
    with ZipFile(patch) as archive: assert archive.read(entry) == (contents/entry).read_bytes()
    # Static success is true even for broken shell syntax; no entrypoint ran.
    assert (repo/'tracked.txt').read_bytes() == b'base\n'
    assert not (repo/'payload.bin').exists() and not git(repo,'status','--porcelain').stdout
    applied = json.loads(_run([sys.executable,'-I','-S','-B','-c', '''
import json,sys
sys.path.insert(0,sys.argv[1])
from patchharbor import api
r=api.apply(sys.argv[2])
print(json.dumps({'success':r.success,'exit_code':r.process_exit_code,
                  'result':str(r.result_bundle.path),'started':r.primary_result.entrypoint_started}))
''',str(runtime),str(patch)],repo,environment))
    returned, _ = read_result_reference(Path(applied['result']))
    assert applied['started'] and not returned.dry_run
    assert applied['success'] is (kind != 'broken')
    assert (applied['exit_code'] == 0) is (kind != 'broken')
    assert git(repo,'rev-parse','HEAD').stdout == before  # no implicit commits
    if kind == 'broken':
        assert returned.primary_result.entrypoint_exit_code != 0
        assert not git(repo,'status','--porcelain').stdout
    else:
        assert (repo/'tracked.txt').read_bytes() == expected
        with ZipFile(applied['result']) as archive:
            assert b'diagnostic-evidence' in archive.read('logs/execution.log')
        if kind == 'diagnostic': assert not git(repo,'status','--porcelain').stdout
