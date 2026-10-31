"""Public export behavior, immutable producer capture and exclusive output."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from io import StringIO
import json
import os
import socket
import subprocess

import pytest
from patchharbor import api, cli, pyz_artifact
from patchharbor.platform.pack_output import OwnedPackFile
from tests.runtime_pyz_support import provider_for


@pytest.mark.parametrize('kind', ['directory', 'zip'])
def test_export_uses_canonical_capture_without_external_work(monkeypatch, tmp_path, kind):
    _, _, recipe, raw = provider_for(monkeypatch, tmp_path, kind=kind)
    def forbidden(*a, **k): pytest.fail('external work during export')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setenv('PATH', '')
    outputs = [tmp_path/'first', tmp_path/'second']
    for p in outputs: p.mkdir()
    result = api.export_runtime(outputs[0])
    assert result.path.name == recipe.pyz_name and result.path.read_bytes() == raw
    assert result.sha256 == sha256(raw).hexdigest() and result.size == len(raw)
    assert result.distribution_version == recipe.version and result.source_commit is None
    assert result.content_id == recipe.content_id and result.requires_python == recipe.requires_python
    with pytest.raises(FrozenInstanceError): result.size = 0
    out = StringIO()
    assert cli.main(['runtime','export','--output-dir',str(outputs[1]),'--json'], stdout=out) == 0
    doc = json.loads(out.getvalue())
    assert doc['output_version'] == 1 and doc['command'] == 'runtime.export' and doc['success']
    assert doc['result']['sha256'] == result.sha256 and doc['result']['size'] == result.size
    assert (outputs[1]/recipe.pyz_name).read_bytes() == raw
    assert all(len(list(p.iterdir())) == 1 for p in outputs)


def test_unprepared_export_api_cli_agree_without_output(monkeypatch, tmp_path):
    monkeypatch.setattr(pyz_artifact, '_pyz_resource_id', None)
    with pytest.raises(api.RuntimeExportError) as caught: api.export_runtime(tmp_path)
    assert caught.value.code == api.RuntimeExportErrorCode.UNAVAILABLE
    assert caught.value.unavailable_reason == 'source_not_prepared'
    out = StringIO()
    assert cli.main(['runtime','export','--output-dir',str(tmp_path),'--json'], stdout=out) == 4
    doc = json.loads(out.getvalue())
    assert not doc['success'] and doc['result'] is None
    assert doc['error']['unavailable_reason'] == caught.value.unavailable_reason
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('target_kind', ['file', 'directory', 'link', 'dangling'])
def test_existing_output_is_never_replaced(monkeypatch, tmp_path, target_kind):
    _, _, recipe, _ = provider_for(monkeypatch, tmp_path)
    output = tmp_path/'output'; output.mkdir(); target = output/recipe.pyz_name
    foreign = tmp_path/'foreign'; foreign.write_bytes(b'preserve')
    if target_kind == 'file': target.write_bytes(b'preserve')
    elif target_kind == 'directory': target.mkdir()
    else:
        try: target.symlink_to(foreign if target_kind == 'link' else tmp_path/'missing')
        except OSError: pytest.skip('symlink unavailable')
    with pytest.raises(api.RuntimeExportError) as caught: api.export_runtime(output)
    assert caught.value.code == api.RuntimeExportErrorCode.COLLISION
    assert foreign.read_bytes() == b'preserve' and len(list(output.iterdir())) == 1
    if target_kind == 'file': assert target.read_bytes() == b'preserve'


@pytest.mark.parametrize('fault', ['missing', 'corrupt', 'version', 'identity', 'resource', 'limit'])
def test_defective_producer_fails_before_output(monkeypatch, tmp_path, fault):
    from patchharbor import runtime_pyz as pyz
    _, source, _, _ = provider_for(monkeypatch, tmp_path)
    p = source.root/pyz.RECIPE_PATH
    if fault == 'missing': p.unlink()
    elif fault == 'corrupt': p.write_bytes(b'{}')
    elif fault == 'version': monkeypatch.setattr(pyz_artifact, '__version__', '99.0.0')
    elif fault == 'identity': monkeypatch.setattr(pyz_artifact, '_pyz_resource_id', '0'*64)
    elif fault == 'resource': (source.root/'patchharbor/api.py').write_bytes(b'changed')
    else: p.write_bytes(b' '* (pyz.MAX_RECIPE_BYTES+1))
    out = tmp_path/'out'; out.mkdir()
    with pytest.raises(api.RuntimeExportError) as caught: api.export_runtime(out)
    assert caught.value.code == api.RuntimeExportErrorCode.UNAVAILABLE
    assert not list(out.iterdir())


def test_missing_and_linked_output_are_not_created_or_followed(monkeypatch, tmp_path):
    provider_for(monkeypatch, tmp_path)
    with pytest.raises(api.RuntimeExportError): api.export_runtime(tmp_path/'missing')
    assert not (tmp_path/'missing').exists()
    foreign=tmp_path/'foreign';foreign.mkdir();link=tmp_path/'link'
    try:link.symlink_to(foreign,target_is_directory=True)
    except OSError:pytest.skip('symlink unavailable')
    with pytest.raises(api.RuntimeExportError): api.export_runtime(link)
    assert not list(foreign.iterdir())


@pytest.mark.parametrize('fault', [OSError('I/O'), KeyboardInterrupt(), SystemExit(9)])
def test_failure_before_publication_has_no_final_file(monkeypatch, tmp_path, fault):
    _, _, recipe, _ = provider_for(monkeypatch, tmp_path)
    out=tmp_path/'out';out.mkdir()
    def fail(*a): raise fault
    monkeypatch.setattr(OwnedPackFile, 'sync', fail)
    with pytest.raises(api.RuntimeExportError) as caught: api.export_runtime(out)
    assert caught.value.code.value == ('io' if isinstance(fault,OSError) else 'interrupted')
    assert caught.value.published_path is None and not list(out.iterdir())


def test_late_collision_preserves_foreign_bytes(monkeypatch, tmp_path):
    _, _, recipe, _ = provider_for(monkeypatch, tmp_path)
    out=tmp_path/'out';out.mkdir();original=OwnedPackFile.publish
    def race(self, name):
        (out/name).write_bytes(b'foreign')
        original(self, name)
    monkeypatch.setattr(OwnedPackFile,'publish',race)
    with pytest.raises(api.RuntimeExportError) as caught:api.export_runtime(out)
    assert caught.value.code==api.RuntimeExportErrorCode.COLLISION
    assert (out/recipe.pyz_name).read_bytes()==b'foreign' and len(list(out.iterdir()))==1


def test_capture_remains_consistent_when_resources_change_before_write(monkeypatch,tmp_path):
    from patchharbor.platform.pack_output import OutputDirectory
    _,source,recipe,raw=provider_for(monkeypatch,tmp_path)
    out=tmp_path/'out';out.mkdir();original=OutputDirectory.reserve
    def change(self):
        (source.root/'patchharbor/api.py').write_bytes(b'replaced producer')
        return original(self)
    monkeypatch.setattr(OutputDirectory,'reserve',change)
    result=api.export_runtime(out)
    assert result.path.read_bytes()==raw and result.sha256==sha256(raw).hexdigest()
    other=tmp_path/'other';other.mkdir()
    with pytest.raises(api.RuntimeExportError):api.export_runtime(other)


@pytest.mark.parametrize('value', ['', b'bytes', None, 7])
def test_invalid_api_arguments_are_rejected_before_capture(monkeypatch,value):
    monkeypatch.setattr(pyz_artifact.PyzProvider,'capture',lambda _:pytest.fail('capture'))
    with pytest.raises((TypeError,ValueError)):api.export_runtime(value)
