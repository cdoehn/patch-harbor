"""Explicit force lifts resource caps, while the same bytes still need integrity."""
from hashlib import sha256
from io import BytesIO, StringIO
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor.bundle_limits import bundle_size_scope
from patchharbor.cli import main
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.zip_payloads import read_zip_payload_bytes, ZipPayloadError, ZipResourceLimitError
from tests import pack_support

request_files = pack_support.request_files


def archive(name='data.bin', data=b'x' * 128):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as output:
        output.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize('field,maximum', [
    ('max_input_artifact_bytes', 32), ('max_content_bytes', 32),
    ('max_zip_total_bytes', 32), ('max_zip_entries', 1),
])
def test_force_reads_complete_bytes_above_each_budget_and_restores_default(field, maximum):
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as output:
        output.writestr('one', b'a' * 128)
        output.writestr('two', b'b' * 128)
    raw = buffer.getvalue()
    policy = ResourcePolicy(warning_bytes=1, **{field: maximum})
    with pytest.raises(ZipResourceLimitError):
        read_zip_payload_bytes(raw, policy=policy)
    with bundle_size_scope(True):
        files = read_zip_payload_bytes(raw, policy=policy)
        assert {f.relative_path: f.content for f in files} == {'one': b'a' * 128, 'two': b'b' * 128}
    with pytest.raises(ZipResourceLimitError):
        read_zip_payload_bytes(raw, policy=policy)


@pytest.mark.parametrize('path', ['../outside', '/absolute', 'safe/../outside'])
def test_force_still_refuses_unsafe_archive_paths(path):
    with bundle_size_scope(True), pytest.raises(ZipPayloadError):
        read_zip_payload_bytes(archive(path))


def test_cli_inspect_force_reads_oversized_task_and_keeps_sha256(request_files, monkeypatch):
    from patchharbor import task_inspection
    result = pack_support.pack(request_files)
    raw = result.path.read_bytes()
    policy = ResourcePolicy(warning_bytes=1, max_input_artifact_bytes=32)
    monkeypatch.setitem(task_inspection.inspect_task.__kwdefaults__, 'resource_policy', policy)
    normal, forced = StringIO(), StringIO()
    assert main(['inspect', str(result.path), '--json'], stdout=normal, stderr=StringIO()) != 0
    assert main(['inspect', str(result.path), '--force', '--json'], stdout=forced, stderr=StringIO()) == 0
    assert sha256(raw).hexdigest() in forced.getvalue()
    assert result.path.read_bytes() == raw
    with pytest.raises(api.PatchHarborError):
        api.inspect_task(result.path)


def test_api_force_argument_is_strict_before_io(tmp_path):
    with pytest.raises(TypeError, match='force must be boolean'):
        api.inspect_task(tmp_path / 'absent.zip', force='yes')
