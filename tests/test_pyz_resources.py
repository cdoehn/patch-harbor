"""Producer-bound ZIP/directory resources, immutable requests and real imports."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Barrier
from zipfile import ZipFile

import pytest

from patchharbor import pyz_artifact as provider_module, runtime_pyz as pyz
from patchharbor.pyz_artifact import PyzProvider
from patchharbor.runtime_sources import DirectoryResources, ZipResources
from tests.test_pack_api import request_files
from tests.test_runtime_pyz import inputs, prepared


def provider_for(monkeypatch, tmp_path, *, kind='directory', payloads=None):
    recipe, payloads, archive = prepared(payloads)
    if kind == 'directory':
        root = tmp_path/'installation'; root.mkdir()
        for name, raw in {**payloads, pyz.RECIPE_PATH: recipe.data}.items():
            if name == '__main__.py': continue
            target = root/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        source = DirectoryResources(root)
    else:
        path = tmp_path/'own.pyz'; path.write_bytes(archive); source = ZipResources(path)
    monkeypatch.setattr(provider_module, 'own_resources', lambda: source)
    monkeypatch.setattr(provider_module, '_pyz_resource_id', pyz.producer_id(recipe))
    return PyzProvider(), source, recipe, archive


@pytest.mark.parametrize('kind', ['directory', 'zip'])
def test_resource_forms_materialize_identical_canonical_bytes_and_documents(monkeypatch, tmp_path, kind):
    provider, source, recipe, archive = provider_for(monkeypatch, tmp_path, kind=kind)
    result = provider.capture()
    assert result.status == 'embedded' and result.reason is None
    artifact = result.artifact
    assert artifact.recipe == recipe and artifact.pyz_bytes == archive
    assert artifact.pyz_sha256 == hashlib.sha256(archive).hexdigest()
    expected = inputs()
    assert artifact.chat_template == expected[pyz.CHAT_PATH]
    assert artifact.api_documentation == expected[pyz.DOC_PATH]
    assert artifact.license == expected[pyz.LICENSE_PATH]
    assert provider.capture() is result
    with pytest.raises(FrozenInstanceError): artifact.pyz_sha256 = 'forged'


@pytest.mark.parametrize('kind', ['directory', 'zip'])
def test_pinned_request_survives_update_but_old_producer_rejects_same_version_replacement(
    monkeypatch, tmp_path, kind,
):
    provider, source, old, archive = provider_for(monkeypatch, tmp_path, kind=kind)
    pinned = provider.capture(); pending = PyzProvider()
    changed = inputs(); changed[pyz.DOC_PATH] += b'updated producer data\n'
    recipe, payloads, new_archive = prepared(changed)
    if kind == 'zip': source.archive.write_bytes(new_archive)
    else:
        for name, raw in {**payloads, pyz.RECIPE_PATH: recipe.data}.items():
            if name != '__main__.py': (source.root/name).write_bytes(raw)
    assert provider.capture() is pinned and pinned.artifact.pyz_bytes == archive
    assert pending.capture().reason == 'source_changed'
    assert pending.capture().artifact is None
    monkeypatch.setattr(provider_module, '_pyz_resource_id', pyz.producer_id(recipe))
    assert PyzProvider().capture().artifact.pyz_bytes == new_archive
    assert recipe.version == old.version and recipe.content_id != old.content_id


@pytest.mark.parametrize('kind', ['directory', 'zip'])
def test_request_capture_is_once_even_with_concurrent_callers(monkeypatch, tmp_path, kind):
    provider, _, _, _ = provider_for(monkeypatch, tmp_path, kind=kind)
    original, calls = provider._capture, []
    def counted(): calls.append(1); return original()
    monkeypatch.setattr(provider, '_capture', counted)
    barrier = Barrier(4)
    def run(_): barrier.wait(timeout=30); return provider.capture()
    with ThreadPoolExecutor(4) as pool: results = list(pool.map(run, range(4)))
    assert len(calls) == 1 and all(result is results[0] for result in results)
    assert results[0].status == 'embedded'


@pytest.mark.parametrize('fault,reason', [
    ('missing', 'resources_missing'), ('recipe', 'resources_invalid'),
    ('code', 'resources_invalid'), ('identity', 'resources_invalid'),
    ('limit', 'resource_limit'), ('link', 'resources_invalid'),
])
def test_invalid_own_directory_resources_never_trigger_foreign_fallback(monkeypatch, tmp_path, fault, reason):
    provider, source, _, _ = provider_for(monkeypatch, tmp_path)
    recipe = source.root/pyz.RECIPE_PATH
    if fault == 'missing': recipe.unlink()
    elif fault == 'recipe': recipe.write_bytes(b'{}')
    elif fault == 'limit': recipe.write_bytes(b' ' * (pyz.MAX_RECIPE_BYTES+1))
    else:
        target = source.root/(pyz.IDENTITY_PATH if fault == 'identity' else 'patchharbor/api.py')
        if fault == 'link':
            backup = tmp_path/'foreign.py'; backup.write_bytes(target.read_bytes()); target.unlink()
            try: target.symlink_to(backup)
            except OSError: pytest.skip('symlink creation unavailable')
        else: target.write_bytes(b'changed resource\n')
    result = provider.capture()
    assert result.reason == reason and result.artifact is None


@pytest.mark.parametrize('fault,reason', [
    ('missing', 'resources_missing'), ('corrupt', 'resources_invalid'),
    ('suffix', 'resources_invalid'), ('limit', 'resource_limit'),
])
def test_invalid_executing_archive_has_no_directory_fallback(monkeypatch, tmp_path, fault, reason):
    provider, source, _, archive = provider_for(monkeypatch, tmp_path, kind='zip')
    if fault == 'missing': source.archive.unlink()
    elif fault == 'corrupt': source.archive.write_bytes(b'not a ZIP')
    elif fault == 'suffix': source.archive.write_bytes(archive+b'trailing')
    else: source.archive.write_bytes(b'x' * (pyz.MAX_PYZ_BYTES+1))
    assert provider.capture().reason == reason and provider.capture().artifact is None


def test_unprepared_source_does_not_scan_build_cache_or_other_installation(monkeypatch):
    monkeypatch.setattr(provider_module, '_pyz_resource_id', None)
    monkeypatch.setattr(provider_module, 'own_resources', lambda: pytest.fail('unprepared provider read resources'))
    assert PyzProvider().capture().reason == 'source_not_prepared'


@pytest.mark.parametrize('fault', [RuntimeError('bug'), ValueError('bug'), KeyboardInterrupt(), SystemExit(9)])
def test_programming_errors_and_cancellation_propagate_and_release_lock(monkeypatch, tmp_path, fault):
    provider, source, _, _ = provider_for(monkeypatch, tmp_path)
    def broken(): raise fault
    monkeypatch.setattr(provider_module, 'own_resources', broken)
    with pytest.raises(type(fault)): provider.capture()
    monkeypatch.setattr(provider_module, 'own_resources', lambda: source)
    assert provider.capture().status == 'embedded'


@pytest.mark.parametrize('kind', ['directory', 'zip'])
def test_capture_performs_no_writes_external_processes_or_network(monkeypatch, tmp_path, kind):
    import socket
    provider, _, _, _ = provider_for(monkeypatch, tmp_path, kind=kind)
    original = os.open
    def readonly(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return original(path, flags, *args, **kwargs)
    def forbidden(*args, **kwargs): pytest.fail('provider attempted external work')
    monkeypatch.setattr(os, 'open', readonly)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    assert provider.capture().status == 'embedded'


@pytest.mark.packaging
@pytest.mark.parametrize('kind', ['directory', 'pyz'])
def test_real_built_producer_uses_only_own_resources_for_pack_from_readonly_runtime(
    tmp_path, built_result_source, request_files, kind,
):
    from tests.runtime_permissions import readonly_tree
    installed = tmp_path/'installed'; shutil.copytree(built_result_source, installed)
    recipe = pyz.parse_recipe((installed/pyz.RECIPE_PATH).read_bytes())
    archive = pyz.materialize(recipe, lambda name, size: (installed/name).read_bytes())
    path = installed/recipe.pyz_name; path.write_bytes(archive)
    runtime = installed if kind == 'directory' else path
    outside = tmp_path/'outside'; outside.mkdir()
    (outside/'patchharbor.py').write_text('raise AssertionError("CWD import")\n')
    (outside/'CHAT_INSTRUCTIONS.md').write_bytes(b'foreign template\n')
    script = '''
import hashlib, json, os, socket, subprocess, sys
from pathlib import Path
from zipfile import ZipFile
root = Path(sys.argv[1]); sys.path.insert(0, str(root))
import patchharbor
from patchharbor import api
from patchharbor.chat_instructions import load_chat_template
from patchharbor.pyz_artifact import PyzProvider
from patchharbor.patch_pack import capture_pack_template
assert str(patchharbor.__file__).startswith(str(root) + os.sep)
assert patchharbor._pyz_resource_id is not None
def forbidden(*a, **k): raise AssertionError('runtime attempted external work')
socket.socket = subprocess.run = subprocess.Popen = forbidden
os.environ['PATH'] = ''
provider = PyzProvider(); pinned = provider.capture()
assert pinned.status == 'embedded', pinned
artifact = pinned.artifact
assert artifact.pyz_sha256 == sys.argv[5]
assert artifact.chat_template.decode() == capture_pack_template()
normalized_template = artifact.chat_template.decode().replace('\\r\\n', '\\n').replace('\\r', '\\n')
assert normalized_template == load_chat_template()
assert artifact.api_documentation and artifact.license
result = api.pack_patch(sys.argv[2], reference_bundle=sys.argv[3], entrypoint='run.sh',
                        output_directory=sys.argv[4])
assert result.validation.binding_matches
assert api.inspect_patch(result.path).package_sha256 == result.package_sha256
assert api.validate_patch(result.path, reference_bundle=sys.argv[3]).binding_matches
assert provider.capture() is pinned
assert 'patchharbor_watcher' not in sys.modules
with ZipFile(result.path) as package:
    assert package.read('PATCHHARBOR_META/CHAT_INSTRUCTIONS.md').endswith(normalized_template.encode('utf-8'))
print(json.dumps({'path': str(result.path), 'sha256': result.package_sha256}))
'''
    env = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    with readonly_tree(installed, owner=tmp_path, environment=env):
        child = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', script, str(runtime),
                                *(str(path) for path in request_files), hashlib.sha256(archive).hexdigest()],
                               cwd=outside, env=env, text=True, capture_output=True, timeout=90)
    assert child.returncode == 0, child.stdout+child.stderr
    evidence = json.loads(child.stdout)
    assert hashlib.sha256(Path(evidence['path']).read_bytes()).hexdigest() == evidence['sha256']


def test_template_rejects_linked_resource_directory(tmp_path, monkeypatch):
    from patchharbor import chat_instructions
    from patchharbor.errors import PatchHarborError
    foreign = tmp_path/'foreign'; foreign.mkdir()
    (foreign/'CHAT_INSTRUCTIONS.md').write_bytes(b'foreign template')
    linked = tmp_path/'linked'
    try: linked.symlink_to(foreign, target_is_directory=True)
    except OSError: pytest.skip('symlink creation unavailable')
    monkeypatch.setattr(chat_instructions, '_template_path', lambda: linked/'CHAT_INSTRUCTIONS.md')
    with pytest.raises(PatchHarborError): chat_instructions.load_chat_template()


@pytest.mark.parametrize('kind', ['directory', 'zip'])
def test_missing_loaded_pyz_identity_cannot_select_the_legacy_pack_provider(monkeypatch, tmp_path, kind):
    from patchharbor import patch_pack
    from patchharbor.errors import FailureReason, PatchHarborError
    provider_for(monkeypatch, tmp_path, kind=kind)
    monkeypatch.setattr(provider_module, '_pyz_resource_id', None)
    def forbidden(): pytest.fail('defective own PYZ silently selected legacy runtime')
    monkeypatch.setattr(patch_pack, 'RuntimeProvider', forbidden)
    with pytest.raises(PatchHarborError) as caught: patch_pack.capture_pack_template()
    assert caught.value.reason is FailureReason.PAYLOAD_PREPARATION_ERROR
