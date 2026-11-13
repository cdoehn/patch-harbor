"""Installed failure outcomes and offline handoff rejection, with no host cutover."""
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor.result_reader import read_result_reference
from tests.embedded_pyz_support import bootstrap_program
from tests.platform_support import native_python_script, native_value
from tests.reference_support import write_reference
from tests.registration_support import create_repository, git
from tests.result_runtime_support import edit_metadata
from tests.runtime_installation_support import _run
from tests.runtime_permissions import readonly_tree
from tests.runtime_v2_support import offline_environment

pytest_plugins = ['tests.runtime_v2_support']

pytestmark = pytest.mark.packaging

FRESH_RESULT = r'''
import json, socket, sys
from pathlib import Path
from patchharbor import api
def no_network(*args, **kwargs): raise AssertionError('unexpected network')
socket.socket = no_network
repo, exchange = map(Path, sys.argv[1:3])
api.register(repo); api.configure_exchange_directory(exchange, repository=repo)
result = api.bundle(repo)
assert result.report.success
print(json.dumps(dict(path=str(result.path))))
'''


def _fixture(tmp_path):
    repo = create_repository(tmp_path / 'repo')
    outside = tmp_path / 'outside'
    outside.mkdir()
    cache = tmp_path / 'cache-disabled'
    cache.write_bytes(b'cache disabled')
    return repo, outside, offline_environment(tmp_path / 'user', cache)


@pytest.mark.parametrize('fault', ['entrypoint', 'timeout', 'publication', 'runtime_budget'])
def test_installed_failure_keeps_primary_outcome_and_actual_state(version2_runtime, tmp_path, fault):
    repo, outside, environment = _fixture(tmp_path)
    head = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    contents = tmp_path / 'contents'
    contents.mkdir()
    (contents / 'actual.txt').write_bytes(b'retained payload')
    entrypoint = native_value('run.sh', 'run.ps1')
    code = "import sys,time\nfrom pathlib import Path\nprint('actual script output', flush=True)\n"
    code += "time.sleep(5)\n" if fault == 'timeout' else "Path('executed').write_bytes(b'yes')\n"
    code += 'sys.exit(23)\n' if fault == 'entrypoint' else 'sys.exit(0)\n'
    (contents / entrypoint).write_text(native_python_script(code), encoding='utf-8')
    probe = FRESH_RESULT[:FRESH_RESULT.index('print(json.dumps')]+r'''
from patchharbor import result_bundle, result_bundle_publication as publication
from patchharbor.errors import result_bundle_error
from patchharbor.result_reader import read_result_reference
contents, entrypoint, fault = Path(sys.argv[3]), sys.argv[4], sys.argv[5]
task = api.pack_task(contents, reference_bundle=result.path, entrypoint=entrypoint,
                     output_directory=exchange)
if fault == 'publication':
    def denied(*args, **kwargs): raise result_bundle_error('injected publication denial')
    publication._verify_result_bundle = denied
if fault == 'runtime_budget':
    result_bundle.runtime_fits = lambda *args, **kwargs: False
report = api.execute(task.path, timeout=.2 if fault == 'timeout' else 30)
assert (repo / 'actual.txt').read_bytes() == b'retained payload'
assert not report.success if fault != 'runtime_budget' else report.success
assert report.primary_result.timed_out is (fault == 'timeout')
if fault != 'timeout':
    assert report.primary_result.entrypoint_exit_code == (23 if fault == 'entrypoint' else 0)
if fault == 'publication':
    assert report.result_bundle.status is api.ResultBundleStatus.FAILED
    rescue = report.result_bundle.emergency_diagnostics_path
    saved = json.loads((rescue / 'run.json').read_bytes())
    assert saved['primary_result']['entrypoint_exit_code'] == 0
    assert (rescue / 'execution.log').read_bytes()
    print(json.dumps(dict(publication='failed', primary_success=report.primary_result.success)))
else:
    facts, _ = read_result_reference(report.result_bundle.path)
    assert facts.format_version == 5 and facts.context.dirty and facts.completed_commit is None
    assert facts.primary_result.timed_out is (fault == 'timeout')
    assert facts.runtime.status == ('unavailable' if fault == 'runtime_budget' else 'embedded')
    if fault == 'runtime_budget': assert facts.runtime.reason == 'resource_limit'
    followup = api.pack_task(contents, reference_bundle=report.result_bundle.path,
        entrypoint=entrypoint, output_directory=exchange)
    assert api.validate_task(followup.path, repository=repo).binding_matches
    print(json.dumps(dict(publication='created', result=str(report.result_bundle.path))))
'''
    proof = json.loads(_run(version2_runtime.library(probe, repo, tmp_path / 'exchange',
                                                    contents, entrypoint, fault), outside, environment))
    assert proof['publication'] == ('failed' if fault == 'publication' else 'created')
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == head
    assert (repo / 'actual.txt').read_bytes() == b'retained payload'


@pytest.mark.parametrize('fault', ['operations', 'task_formats', 'result_formats', 'boolean', 'extra'])
def test_own_bootstrap_and_native_reader_reject_unknown_capabilities(version2_runtime, tmp_path, fault):
    repo, outside, environment = _fixture(tmp_path)
    original = json.loads(_run(version2_runtime.library(FRESH_RESULT, repo, tmp_path / 'exchange'),
                               outside, environment))
    with ZipFile(original['path']) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    helper = tmp_path / 'own-reviewed-bootstrap.py'
    helper.write_text(bootstrap_program(files['tools/pyz_bootstrap.py']), encoding='utf-8')
    def damage(document):
        capabilities = document['capabilities']
        if fault == 'operations': capabilities['operations'].append('unknown_operation')
        elif fault == 'boolean': capabilities['task_formats'] = [True]
        elif fault == 'extra': capabilities['legacy'] = True
        else: capabilities[fault] = [1 if fault == 'task_formats' else 3]
    edit_metadata(files, damage)
    reference = tmp_path / 'invalid-capabilities.zip'
    write_reference(reference, files)
    with pytest.raises(api.PatchHarborError):
        read_result_reference(reference)
    probe = r'''
import hashlib, importlib.util, json, socket, subprocess, sys
from pathlib import Path
helper, reference = map(Path, sys.argv[1:3])
spec = importlib.util.spec_from_file_location('own_bootstrap', helper)
bootstrap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap; spec.loader.exec_module(bootstrap)
def forbidden(*args, **kwargs): raise AssertionError('precheck attempted external work')
socket.socket = subprocess.run = subprocess.Popen = forbidden
try:
    bootstrap.assess(reference, trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
except ValueError:
    assert not any(n == 'patchharbor' or n.startswith('patchharbor.') for n in sys.modules)
    print(json.dumps(dict(rejected=True)))
else:
    raise AssertionError('unknown capabilities accepted')
'''
    before = sha256(reference.read_bytes()).hexdigest()
    result = json.loads(_run([sys.executable, '-I', '-S', '-B', '-c', probe, str(helper), str(reference)],
                             outside, environment))
    assert result['rejected'] and sha256(reference.read_bytes()).hexdigest() == before


def test_installed_runtime_operates_readonly_with_no_writable_cache(version2_runtime, tmp_path):
    repo, outside, environment = _fixture(tmp_path)
    if version2_runtime.pyz is None:
        location = Path(_run(version2_runtime.library(
            "import sysconfig; print(sysconfig.get_path('purelib'))"), outside, environment).strip())
        owner = version2_runtime.python.parent.parent
    else:
        location = version2_runtime.pyz.parent
        owner = location.parent
    with readonly_tree(location, owner=owner, environment=environment):
        proof = json.loads(_run(version2_runtime.library(FRESH_RESULT, repo, tmp_path / 'exchange'),
                                outside, environment))
        facts, _ = read_result_reference(Path(proof['path']))
        assert facts.format_version == 5 and facts.runtime.status == 'embedded'
