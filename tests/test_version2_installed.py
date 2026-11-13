"""Two real Task/Execute/Result rounds outside the development checkout."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from patchharbor.result_reader import read_result_reference
from tests.platform_support import native_python_script, native_value
from tests.registration_support import create_repository, git
from tests.runtime_installation_support import _run
from tests.runtime_v2_support import offline_environment

pytest_plugins = ['tests.runtime_v2_support']

pytestmark = pytest.mark.packaging

ROUNDTRIP = r'''
from hashlib import sha256
import json, socket, subprocess, sys
from io import BytesIO
from zipfile import ZipFile
import patchharbor
from pathlib import Path
from patchharbor import api
from patchharbor.result_reader import read_result_reference
def no_network(*args, **kwargs):
    raise AssertionError('installed handoff attempted networking')
socket.socket = no_network
repo, exchange, contents = map(Path, sys.argv[1:4])
entrypoint = sys.argv[4]
api.register(repo)
api.configure_exchange_directory(exchange, repository=repo)
if sys.argv[5] == 'True':
    (repo / 'tracked.txt').write_bytes(b'staged\n')
    subprocess.run(['git', '-C', str(repo), 'add', 'tracked.txt'], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (repo / 'tracked.txt').write_bytes(b'working\n')
    (repo / 'untracked.bin').write_bytes(b'\x00untracked\xff')
reference = api.bundle(repo)
initial, _ = read_result_reference(reference.path)
assert initial.format_version == 5 and initial.operation == 'bundle'
assert initial.runtime.status == 'embedded' and initial.runtime.task_formats == (3,)
assert initial.runtime.result_formats == (5,)
assert patchharbor.__version__ == '2.0.0'
with ZipFile(reference.path) as outer:
    runtime_bytes = outer.read(initial.runtime.artifact.path)
assert sha256(runtime_bytes).hexdigest() == initial.runtime.artifact.sha256
with ZipFile(BytesIO(runtime_bytes)) as core:
    assert not any(name.startswith(('tools/', 'tests/', 'patchharbor_watcher/', 'pytest/', 'xdist/')) for name in core.namelist())
    assert not any(name.endswith(('.sqlite3', '.prof', '.log')) for name in core.namelist())
first = api.pack_task(contents, reference_bundle=reference.path, entrypoint=entrypoint,
                      output_directory=exchange)
checked = api.validate_task(first.path, reference_bundle=reference.path)
assert checked.binding_matches and checked.reference_sha256 == sha256(reference.path.read_bytes()).hexdigest()
assert api.inspect_task(first.path).manifest.format_version == 3
report = api.execute(first.path, timeout=30)
assert report.success and report.primary_result.entrypoint_exit_code == 0
returned, _ = read_result_reference(report.result_bundle.path)
assert returned.format_version == 5 and returned.operation == 'execute'
assert returned.task_sha256 == sha256(first.path.read_bytes()).hexdigest()
assert returned.completed_commit is None and returned.context.base_commit == initial.context.base_commit
assert returned.runtime.artifact.sha256 == initial.runtime.artifact.sha256
second = api.pack_task(contents, reference_bundle=report.result_bundle.path,
                       entrypoint=entrypoint, output_directory=exchange)
assert api.validate_task(second.path, repository=repo).binding_matches
assert 'patchharbor_watcher' not in sys.modules
assert all(not hasattr(api, name) for name in ('apply', 'pack_patch', 'inspect_patch', 'validate_patch'))
print(json.dumps(dict(reference=str(reference.path), first_result=str(report.result_bundle.path),
    initial_dirty=initial.context.dirty, next_task=str(second.path), next_sha256=second.package_sha256,
    runtime_sha256=returned.runtime.artifact.sha256, api_origin=api.__file__)))
'''


@pytest.mark.parametrize('dirty', [False, True])
def test_installed_api_then_cli_complete_two_bound_rounds(version2_runtime, tmp_path, dirty):
    repository = create_repository(tmp_path / 'repository')
    before = git(repository, 'rev-parse', 'HEAD').stdout.strip()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'patchharbor.py').write_text('raise AssertionError("foreign CWD import")\n')
    cache = tmp_path / 'blocked-cache'
    cache.write_bytes(b'not a cache directory')
    environment = offline_environment(tmp_path / 'user', cache)
    contents = tmp_path / 'contents'
    contents.mkdir()
    (contents / 'requested.txt').write_bytes(b'payload precedes entrypoint')
    entrypoint = native_value('run.sh', 'run.ps1')
    (contents / entrypoint).write_text(native_python_script(
        "from pathlib import Path\n"
        "assert Path('requested.txt').read_bytes()==b'payload precedes entrypoint'\n"
        "with Path('rounds.txt').open('ab') as stream: stream.write(b'round\\n')\n"), encoding='utf-8')
    proof = json.loads(_run(version2_runtime.library(ROUNDTRIP, repository, tmp_path / 'exchange',
                                                   contents, entrypoint, dirty), outside, environment))
    assert proof['initial_dirty'] is dirty
    assert Path(proof['api_origin']).is_absolute()
    assert (repository / 'rounds.txt').read_bytes() == b'round\n'
    task = Path(proof['next_task'])
    assert sha256(task.read_bytes()).hexdigest() == proof['next_sha256']
    result = json.loads(_run(version2_runtime.cli('execute', task, '--json'), outside, environment))
    assert result['success'] and result['command'] == 'execute' and result['output_version'] == 2
    final, _ = read_result_reference(Path(result['result']['result_bundle']['path']))
    assert final.task_sha256 == proof['next_sha256'] and final.completed_commit is None
    assert final.runtime.artifact.sha256 == proof['runtime_sha256']
    assert (repository / 'rounds.txt').read_bytes() == b'round\nround\n'
    assert git(repository, 'rev-parse', 'HEAD').stdout.strip() == before
    assert cache.read_bytes() == b'not a cache directory'
    if dirty:
        assert git(repository, 'show', ':tracked.txt').stdout == 'staged\n'
        assert (repository / 'tracked.txt').read_bytes() == b'working\n'
        assert (repository / 'untracked.bin').read_bytes() == b'\x00untracked\xff'
