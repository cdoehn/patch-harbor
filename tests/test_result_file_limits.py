"""Real snapshot capacity, shared ZIP64 input, and deterministic limit failures."""
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
import struct
import sys
import types
from zipfile import ZipFile

import pytest

from patchharbor import result_bundle_publication as publication
from patchharbor import result_verification as verification
from patchharbor import resource_policy as policy
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.bundle_handoff import BundleHandoff
from patchharbor.errors import PatchHarborError
from patchharbor.models import GitObjectFormat, GitObjectId
from patchharbor.pyz_artifact import PyzArtifact
from patchharbor.result_bundle import _context_document, _manifest_document
from patchharbor.result_bundle_snapshot import build_result_bundle_snapshot
from patchharbor.result_bundle_writer import write_result_bundle
from patchharbor.result_reader import read_result_reference, parse_result_payloads, result_member_path
from patchharbor.result_resources import runtime_payload, runtime_fits
from patchharbor.run_report import PrimaryResult, RunOperation
from patchharbor.zip_payloads import read_zip_payload_bytes
from scripts import pyz_bootstrap as bootstrap
from tests.embedded_pyz_support import bootstrap_program
from tests.run_report_support import successful_bundle_run_report
from tests.test_reference_validation import reference_entries, edit_document
from tests.test_result_bundle_publication import _publish
from tests.test_runtime_pyz import prepared


def publication_inputs(tmp_path, count):
    path = tmp_path / 'result.zip'
    report = replace(successful_bundle_run_report(tmp_path / 'repository', path),
                     operation=RunOperation.APPLY,
                     primary_result=PrimaryResult.entrypoint_success_result())
    blob = GitObjectId('e69de29bb2d1d6434b8b29ae775ad8c2e48c5391', GitObjectFormat.SHA1)
    snapshot = build_result_bundle_snapshot(
        base_entries=((f'f{n:06d}'.encode(), b'100644', blob, b'') for n in range(count)),
        untracked_entries=(), staged_patch=b'', unstaged_patch=b'')
    recipe, payloads, raw = prepared()
    from patchharbor import runtime_pyz as pyz
    runtime = runtime_payload(PyzArtifact(recipe, raw, sha256(raw).hexdigest(),
        payloads[pyz.CHAT_PATH], payloads[pyz.DOC_PATH], payloads[pyz.LICENSE_PATH]))
    context = _context_document(report)
    environment = dict(marker='patch-harbor-environment', format_version=1, bundle_type='Result',
        repository_context={k: context[k] for k in
            ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')},
        run_id=report.run_id_text, bundle_suffix='')
    manifest = _manifest_document(report=report, snapshot=snapshot, runtime=runtime)
    for key in ('base_commit', 'state_fingerprint', 'fingerprint_algorithm'):
        manifest['actual_' + key] = manifest['expected_' + key] = context[key]
    return path, dict(manifest=manifest,
        context_document=context, handoff=BundleHandoff(b'contract\n', json.dumps(environment).encode()),
        run_report=report, snapshot=snapshot, runtime=runtime, execution_log=b'success\n')


@pytest.mark.parametrize('count', [1500, 250_000])
def test_real_publication_and_reference_accept_snapshot_capacity(tmp_path, monkeypatch, count):
    path, arguments = publication_inputs(tmp_path, count)
    assert runtime_fits(arguments['runtime'], **{k: v for k, v in arguments.items() if k != 'runtime'})
    destination = publication.prepare_result_bundle_publication(path, run_id=arguments['run_report'].timing.run_id)
    publication.publish_result_bundle(destination, **arguments)
    assert not destination.temporary_path.exists()
    facts, digest = read_result_reference(path)
    assert facts.primary_result.success
    raw = path.read_bytes()
    assert digest == sha256(raw).hexdigest()
    with ZipFile(BytesIO(raw)) as archive:
        assert len(archive.infolist()) == count + 10
        assert len([n for n in archive.namelist() if n.startswith('base/')]) == count
    assert (b'PK\x06\x06' in raw) == (count > 65535)
    assert parse_archive_evidence(raw, path).kind == 'result_bundle'
    assert bootstrap.assess(path).pyz_bytes == arguments['runtime'].artifact_bytes
    # Exercise the actual executable handoff resource too, not just its source helper.
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / 'CHAT_INSTRUCTIONS.md').read_bytes()
    module = types.ModuleType('capacity_bootstrap')
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(bootstrap_program(template), '<handoff>', 'exec'), module.__dict__)
    assert module.assess(path).pyz_bytes == arguments['runtime'].artifact_bytes
    if count == 250_000:
        with ZipFile(path, 'a') as archive: archive.writestr('extra', b'')
        with pytest.raises(PatchHarborError) as caught:
            read_result_reference(path)
        failure = caught.value.__cause__
        assert failure.resource == 'zip_entries'
        assert failure.actual == 250_011 and failure.limit == 250_010


def test_over_capacity_is_rejected_before_writer_opens_destination(tmp_path):
    policy.check_result_file_count(249_999, 1)
    with pytest.raises(policy.ResultSnapshotLimitError) as caught:
        policy.check_result_file_count(250_000, 1)
    assert (caught.value.actual, caught.value.limit) == (250_001, 250_000)
    # No filesystem tree or blob capture is needed to reject an oversized inventory.
    oversized = (None,) * 250_001
    with pytest.raises(PatchHarborError) as caught:
        build_result_bundle_snapshot(base_entries=oversized, untracked_entries=(),
                                     staged_patch=b'', unstaged_patch=b'')
    assert isinstance(caught.value.__cause__, policy.ResultSnapshotLimitError)
    _, arguments = publication_inputs(tmp_path, 0)
    arguments['snapshot'] = replace(arguments['snapshot'], base_entries=oversized)
    output = BytesIO()
    with pytest.raises(PatchHarborError) as caught:
        write_result_bundle(output, **arguments)
    assert isinstance(caught.value.__cause__, policy.ResultSnapshotLimitError)
    assert output.getvalue() == b''


def test_reader_rejects_snapshot_over_capacity_before_inventory_expansion():
    files, _ = reference_entries()
    edit_document(files, 'manifest.json', lambda doc:
                  doc.update(base_entries=doc['base_entries'] * 250_001))
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        for name, raw in files.items(): archive.writestr(name, raw)
    payloads = read_zip_payload_bytes(output.getvalue(), path_normalizer=result_member_path)
    with pytest.raises(policy.ResultSnapshotLimitError) as caught:
        parse_result_payloads(payloads)
    assert caught.value.resource == 'result_snapshot_files'
    assert caught.value.actual == 250_001 and caught.value.limit == 250_000


def test_publication_preserves_typed_limit_and_never_waits(tmp_path, monkeypatch):
    from uuid import UUID
    path = tmp_path / 'result.zip'
    destination = publication.prepare_result_bundle_publication(path, run_id=UUID(int=123))
    original = publication.read_result_reference
    def read(*args, **kwargs):
        return original(*args, **kwargs, resource_policy=replace(policy.DEFAULT_RESOURCE_POLICY, max_zip_entries=7))
    monkeypatch.setattr(publication, 'read_result_reference', read)
    monkeypatch.setattr(verification, 'sleep', lambda delay: pytest.fail('resource failure retried'))
    with pytest.raises(verification.ResultVerificationError) as caught:
        _publish(destination)
    details = caught.value.diagnostics
    assert details['verification_error_type'] == 'ZipResourceLimitError'
    assert details['resource_limit'] == dict(resource='zip_entries', actual=8, limit=7)
    assert details['verification_attempts'] == 1 and details['waited_seconds'] == 0
    assert not path.exists() and not destination.temporary_path.exists()


def zip64_fixture():
    output = BytesIO()
    with ZipFile(output, 'w') as archive: archive.writestr('file', b'')
    raw = output.getvalue(); end = len(raw) - 22
    _, _, _, _, count, size, offset, _ = struct.unpack_from('<4s4H2IH', raw, end)
    record = struct.pack('<4sQ2H2L4Q', b'PK\x06\x06', 44, 45, 45, 0, 0, count, count, size, offset)
    locator = struct.pack('<4sLQL', b'PK\x06\x07', 0, end, 1)
    classic = struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, 65535, 65535, size, offset, 0)
    return bytearray(raw[:end] + record + locator + classic), end


def test_zip64_directory_is_accepted_without_allocating_zip_members():
    raw, _ = zip64_fixture()
    bootstrap._directory_budget(raw)


@pytest.mark.parametrize('fault', ['limit', 'locator', 'disk', 'size', 'count', 'offset', 'classic', 'extension'])
def test_malformed_zip64_is_rejected_before_zipfile_allocation(tmp_path, monkeypatch, fault):
    raw, end = zip64_fixture()
    if fault == 'limit':
        struct.pack_into('<2Q', raw, end + 24, 250_011, 250_011)
    elif fault == 'locator': struct.pack_into('<Q', raw, end + 64, len(raw))
    elif fault == 'disk': struct.pack_into('<L', raw, end + 16, 1)
    elif fault == 'size': struct.pack_into('<Q', raw, end + 4, 45)
    elif fault == 'count': struct.pack_into('<Q', raw, end + 24, 2)
    elif fault == 'offset': struct.pack_into('<Q', raw, end + 48, 1)
    elif fault == 'classic': struct.pack_into('<H', raw, end + 86, 2)
    elif fault == 'extension':
        struct.pack_into('<Q', raw, end + 4, 45)
        raw[end + 56:end + 56] = b'x'
    path = tmp_path / 'invalid.zip'; path.write_bytes(raw)
    monkeypatch.setattr(bootstrap, 'ZipFile', lambda *a, **k: pytest.fail('unbounded metadata allocated'))
    with pytest.raises(ValueError): bootstrap.assess(path)
