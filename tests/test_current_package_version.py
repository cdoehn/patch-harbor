"""Exact product-version rejection at public processing and bootstrap boundaries."""
import json
from io import StringIO

import pytest

from patchharbor import __version__, api
from patchharbor.cli import main
from patchharbor.monitor_artifact_facts import ArtifactCache
from patchharbor.result_reader import capture_result_reference
from tests.reference_support import reference_entries, write_reference, bound_package
from tests.result_runtime_support import edit_metadata
from tests.task_inspection_support import MANIFEST, write_package
from tools import pyz_bootstrap


@pytest.mark.parametrize('version', [None, True, 2, '', '1.9.1', '2.0.1', '99.0.0'])
def test_foreign_task_version_never_reaches_repository_resolution(tmp_path, monkeypatch, version):
    from patchharbor import application_execute
    task = tmp_path / 'task.zip'
    manifest = dict(MANIFEST, patchharbor_version=version)
    if version is None:
        manifest.pop('patchharbor_version')
    write_package(task, changes={'task.json': json.dumps(manifest).encode()})
    original = task.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail('unsupported version reached repository execution')
    monkeypatch.setattr(application_execute, 'execute_task_bundle', forbidden)
    for operation in (api.inspect_task, api.validate_task):
        with pytest.raises(api.PatchHarborError, match='package version'):
            operation(task)
    output = StringIO()
    assert main(['execute', str(task), '--json'], stdout=output, stderr=StringIO()) != 0
    result = json.loads(output.getvalue())['result']
    assert not result['repository_resolved'] and not result['primary_result']['entrypoint_started']
    metadata, _ = ArtifactCache()._parse(task, type('Captured', (), {
        'content': original, 'sha256': 'a' * 64, 'size': len(original)})())
    assert metadata['kind'] == 'other' and 'package version' in metadata['error']
    assert task.read_bytes() == original and not (tmp_path / 'SHOULD_NOT_EXIST').exists()


@pytest.mark.parametrize('version', [None, True, '', '1.9.1', '2.0.1', '99.0.0'])
def test_foreign_result_never_becomes_reference_or_bootstrap(tmp_path, version):
    files, binding = reference_entries()
    manifest = json.loads(files['manifest.json'])
    manifest['patchharbor_version'] = version
    if version is None:
        manifest.pop('patchharbor_version')
    files['manifest.json'] = json.dumps(manifest).encode()
    reference = tmp_path / 'result.zip'
    write_reference(reference, files)
    original = reference.read_bytes()
    task = tmp_path / 'task.zip'
    bound_package(task, binding)
    with pytest.raises(api.PatchHarborError, match='package version'):
        capture_result_reference(reference)
    with pytest.raises(api.PatchHarborError):
        api.validate_task(task, reference_bundle=reference)
    with pytest.raises(ValueError, match='package version'):
        pyz_bootstrap.assess(reference)
    contents = tmp_path / 'contents'
    contents.mkdir()
    (contents / 'run.sh').write_bytes(b'# PATCHHARBOR\nexit 0\n')
    output = tmp_path / 'never-published.zip'
    with pytest.raises(api.PatchHarborError):
        api.pack_task(contents, reference_bundle=reference, entrypoint='run.sh', output=output)
    assert not output.exists() and reference.read_bytes() == original


@pytest.mark.parametrize('embedded', [False, True])
@pytest.mark.parametrize('version', [None, '1.9.1', '2.0.1'])
def test_runtime_version_must_match_current_result_even_when_unavailable(tmp_path, embedded, version):
    from tests.result_pyz_support import attach_pyz
    files, _ = reference_entries()
    if not embedded:
        files = attach_pyz(files, None)
    edit_metadata(files, lambda doc: doc.update(version=version))
    path = tmp_path / 'result.zip'
    write_reference(path, files)
    with pytest.raises(api.PatchHarborError):
        capture_result_reference(path)
    with pytest.raises(ValueError):
        pyz_bootstrap.assess(path)


def test_current_reference_and_packed_task_report_exact_product_version(tmp_path):
    files, _ = reference_entries()
    path = tmp_path / 'result.zip'
    write_reference(path, files)
    facts = capture_result_reference(path).facts
    assert facts.patchharbor_version == facts.runtime.version == __version__
    contents = tmp_path / 'contents'
    contents.mkdir()
    (contents / 'run.sh').write_bytes(b'# PATCHHARBOR\nexit 0\n')
    packed = api.pack_task(contents, reference_bundle=path, entrypoint='run.sh', output=tmp_path / 'task.zip')
    assert api.inspect_task(packed.path).manifest.patchharbor_version == __version__
