"""Real wheel/PYZ source-safe exports and public-only, offline snapshot reading."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from patchharbor import runtime_pyz as pyz
from tests.safe_reference_support import arm_helper, source_bytes
from tests.snapshot_support import produce_case

pytestmark = [pytest.mark.packaging,
              pytest.mark.skipif(not sys.platform.startswith('linux'), reason='safe host contract requires Linux')]


@pytest.mark.proof('reference.safe-distribution', parameter='case_id')
@pytest.mark.parametrize('case_id', [route + '-' + kind for route in ('wheel', 'pyz') for kind in ('clean', 'mixed', 'filter')])
def test_built_artifact_safe_export_and_offline_native_read(
        built_result_source, tmp_path, monkeypatch, case_id):
    route, kind = case_id.split('-', 1)
    case = produce_case(tmp_path, monkeypatch, kind='mixed' if kind == 'mixed' else 'clean')
    calls = arm_helper(tmp_path, case.repository, 'clean') if kind == 'filter' else None
    before = source_bytes(case.repository)
    recipe = pyz.parse_recipe((built_result_source / pyz.RECIPE_PATH).read_bytes())
    raw = pyz.materialize(recipe, lambda name, size: (built_result_source / name).read_bytes())
    artifact = tmp_path / recipe.pyz_name
    artifact.write_bytes(raw)
    selected = artifact if route == 'pyz' else built_result_source
    outside = tmp_path / 'outside'
    outside.mkdir()
    output = outside / 'output'
    output.mkdir()
    source = Path(__file__).resolve().parents[1]
    shutil.copyfile(source / 'docs/examples/safe_reference_export.py', outside / 'example.py')
    expected = {layer: {name: {'mode': mode, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
                       for name, (mode, data) in files.items()} for layer, files in case.expected.items()}
    (outside / 'expected.json').write_text(json.dumps(expected))
    environment = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    process = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', r'''
import hashlib, json, os, runpy, sys
from pathlib import Path
from zipfile import ZipFile
selected, source, repo, kind, runtime_sha = sys.argv[1:]
root = Path.cwd()
offline = False
def audit(event, args):
    if event.startswith('socket.') or (offline and (event.startswith(('subprocess.', 'os.exec', 'os.spawn')) or event == 'os.system')):
        raise AssertionError('unapproved external operation: ' + event)
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0])).absolute()
        if path == Path(source) or Path(source) in path.parents:
            raise AssertionError('hidden development checkout dependency')
sys.addaudithook(audit)
sys.path.insert(0, selected)
from patchharbor import api
assert api.__file__.startswith(selected + os.sep), api.__file__
caps = api.integration_capabilities()
assert caps.safe_reference_contract_version == 1
assert caps.contract_version == caps.snapshot_contract_version == 2
assert caps.guarded_apply_contract_version == 1
example = runpy.run_path(str(root / 'example.py'))
authorized = []
def authorize(plan):
    authorized.append(plan)
    assert plan.context.repository_path.value == Path(repo)
    assert plan.output_directory == plan.diagnostics_parent == root / 'output'
    assert plan.maintenance_enabled is False
    return True
if kind == 'filter':
    try:
        example['export_reference'](repo, output_directory=root / 'output', authorize=authorize)
    except api.SafeExportError as exc:
        assert exc.code is api.SafeExportErrorCode.UNSUPPORTED_CONVERSION
    else:
        raise AssertionError('active filter was accepted')
    assert authorized == [] and list((root / 'output').iterdir()) == []
else:
    plan, bundle, snapshot = example['export_reference'](repo, output_directory=root / 'output', authorize=authorize)
    assert authorized == [plan]
    expected_sha = hashlib.sha256(bundle.path.read_bytes()).hexdigest()
    offline = True
    os.environ['PATH'] = ''
    snapshot = api.read_result_snapshot(bundle.path, expected_sha256=expected_sha)
    expected = json.loads((root / 'expected.json').read_bytes())
    for layer, files in expected.items():
        assert {name: {'mode': file.mode, 'sha256': file.sha256, 'size': file.size}
                for name, file in getattr(snapshot, layer).files.items()} == files, layer
    assert snapshot.format_version == 4 and snapshot.runtime.status == 'embedded'
    assert snapshot.runtime.artifact_sha256 == runtime_sha
    assert snapshot.runtime.requires_python == '>=3.10'
    with ZipFile(bundle.path) as archive:
        assert hashlib.sha256(archive.read('runtime/patchharbor-' + snapshot.runtime.version + '.pyz')).hexdigest() == runtime_sha
    assert hashlib.sha256(bundle.path.read_bytes()).hexdigest() == snapshot.sha256
assert 'patchharbor_watcher' not in sys.modules
assert not any('site-packages' in p or 'dist-packages' in p for p in sys.path)
print(json.dumps({'origin': api.__file__, 'kind': kind, 'contract': 1, 'runtime_sha256': runtime_sha}))
''', str(selected), str(source), str(case.repository), kind, hashlib.sha256(raw).hexdigest()],
        cwd=outside, env=environment, capture_output=True, text=True, timeout=120)
    assert process.returncode == 0, process.stdout + process.stderr
    proof = json.loads(process.stdout)
    assert proof['origin'].startswith(str(selected) + os.sep)
    assert proof['runtime_sha256'] == hashlib.sha256(raw).hexdigest()
    assert source_bytes(case.repository) == before
    assert calls is None or not calls.exists()


@pytest.mark.parametrize('capability', ['missing_function', 'missing_field', None, 0, 2, True, '1'])
def test_public_example_refuses_old_or_unknown_contract_before_any_export(monkeypatch, capability):
    from patchharbor import api
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'docs/examples/safe_reference_export.py'))
    if capability == 'missing_function':
        monkeypatch.delattr(api, 'integration_capabilities')
    else:
        value = SimpleNamespace() if capability == 'missing_field' else SimpleNamespace(safe_reference_contract_version=capability)
        monkeypatch.setattr(api, 'integration_capabilities', lambda: value)
    def forbidden(*args, **kwargs):
        pytest.fail('unsupported runtime entered a source or producing operation')
    for name in ('context', 'prepare_reference_export', 'bundle'):
        monkeypatch.setattr(api, name, forbidden)
    with pytest.raises(RuntimeError):
        module['export_reference']('/unused', output_directory='/unused', authorize=lambda plan: True)
