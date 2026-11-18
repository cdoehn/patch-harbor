"""Small real bundles exercise raised limits without allocating huge fixtures."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import StringIO
import json
from threading import Barrier

import pytest

from patchharbor import api, pack_candidate, pack_sources, resource_policy
from patchharbor.bundle_limits import bundle_size_scope
from patchharbor.cli import main
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.zip_payloads import read_zip_payload_bytes, ZipResourceLimitError, ZipPayloadError
from tests import pack_support
from tests.reference_support import reference_entries, write_reference, edit_document
from tests.test_force_bundle_limits import archive
from tests.test_monitor import registered
from tools import pyz_bootstrap as bootstrap

request_files = pack_support.request_files


def test_manual_cli_state_pack_validate_execute_with_explicit_force(tmp_path, monkeypatch):
    (repository, _), = registered(tmp_path, monkeypatch)
    (repository / 'second.txt').write_text('another real snapshot file\n')
    monkeypatch.setattr(resource_policy, 'MAX_RESULT_FILES', 1)
    normal = StringIO()
    assert main(['bundle', str(repository), '--json'], stdout=normal, stderr=StringIO()) != 0
    output = StringIO()
    assert main(['bundle', str(repository), '--force', '--json'], stdout=output, stderr=StringIO()) == 0
    state = json.loads(output.getvalue())['result']['state_bundle_path']
    contents = tmp_path / 'contents'; contents.mkdir()
    (contents / 'run.sh').write_bytes(pack_support.SCRIPT)
    tasks = tmp_path / 'tasks'; tasks.mkdir()
    arguments = ['pack', str(contents), '--reference-bundle', state,
                 '--entrypoint', 'run.sh', '--output-dir', str(tasks), '--json']
    assert main(arguments, stdout=StringIO(), stderr=StringIO()) != 0
    assert not list(tasks.iterdir())
    assert main([*arguments, '--force'], stdout=StringIO(), stderr=StringIO()) == 0
    task, = tasks.iterdir()
    assert main(['validate', str(task), '--reference-bundle', state, '--force', '--json'],
                stdout=StringIO(), stderr=StringIO()) == 0
    report = api.execute(task, force=True)
    assert report.primary_result.success and report.result_bundle.path.is_file()
    snapshot = api.read_reference_snapshot(report.result_bundle.path, force=True)
    assert snapshot.bundle_kind is api.ReferenceBundleKind.RESULT
    with pytest.raises(api.PatchHarborError):
        api.validate_task(task, reference_bundle=state)


@pytest.mark.parametrize('limit', ['output_bytes', 'scan_nodes'])
def test_force_pack_lifts_writer_and_scan_limits_but_keeps_exact_output(request_files, monkeypatch, limit):
    if limit == 'scan_nodes':
        monkeypatch.setattr(pack_sources, 'MAX_SCAN_NODES', 1)
    else:
        original = pack_candidate._BoundedOutput.__init__
        def small_output(self, stream, maximum):
            original(self, stream, 16)
        monkeypatch.setattr(pack_candidate._BoundedOutput, '__init__', small_output)
    with pytest.raises(api.PatchHarborError):
        pack_support.pack(request_files)
    assert not list(request_files[2].iterdir())
    result = pack_support.pack(request_files, force=True)
    raw = result.path.read_bytes()
    assert result.package_sha256 == sha256(raw).hexdigest()
    assert api.validate_task(result.path, reference_bundle=request_files[1]).binding_matches
    with pytest.raises(api.PatchHarborError):
        pack_support.pack(request_files)


def test_forced_native_reference_still_checks_digest_and_kind(tmp_path):
    files, _ = reference_entries()
    path = tmp_path / 'reference.zip'; write_reference(path, files)
    with pytest.raises(api.ReferenceSnapshotError):
        api.read_reference_snapshot(path, expected_sha256='0' * 64, force=True)
    edit_document(files, 'manifest.json', lambda d: d.update(marker='patch-harbor-result-bundle'))
    write_reference(path, files)
    with pytest.raises(api.ReferenceSnapshotError):
        api.read_reference_snapshot(path, force=True)


def test_forced_bootstrap_assess_and_prepare_retain_trust_and_byte_identity(tmp_path, monkeypatch):
    files, _ = reference_entries()
    path = tmp_path / 'reference.zip'; write_reference(path, files)
    digest = sha256(path.read_bytes()).hexdigest()
    for name in ('MAX_INPUT', 'MAX_TOTAL', 'MAX_ENTRIES', 'MAX_PYZ', 'MAX_METADATA',
                 'MAX_RECIPE', 'MAX_INNER_TOTAL', 'MAX_INNER_ENTRIES'):
        monkeypatch.setattr(bootstrap, name, 1)
    with pytest.raises(ValueError):
        bootstrap.assess(path, trusted_source_sha256=digest)
    assessed = bootstrap.assess(path, trusted_source_sha256=digest, force=True)
    with pytest.raises(ValueError):
        bootstrap.prepare(assessed, tmp_path / 'normal')
    prepared = bootstrap.prepare(assessed, tmp_path / 'forced', force=True)
    assert prepared.path.read_bytes() == assessed.pyz_bytes
    assert not (tmp_path / 'normal').exists()
    with pytest.raises(ValueError, match='digest mismatch'):
        bootstrap.assess(path, trusted_source_sha256='0' * 64, force=True)
    with pytest.raises(ValueError):
        bootstrap.assess(path, trusted_source_sha256=digest)


def test_force_scope_is_independent_between_concurrent_requests():
    raw = archive()
    policy = ResourcePolicy(warning_bytes=1, max_content_bytes=1)
    barrier = Barrier(2)
    def read(force):
        with bundle_size_scope(force):
            barrier.wait(timeout=10)
            try:
                return read_zip_payload_bytes(raw, policy=policy)[0].content
            except ZipResourceLimitError:
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        forced = pool.submit(read, True)
        normal = pool.submit(read, False)
        assert forced.result() == b'x' * 128 and normal.result() is None


def test_failure_and_nested_public_call_do_not_leak_force(request_files, monkeypatch):
    from patchharbor import task_inspection
    task = pack_support.pack(request_files).path
    policy = ResourcePolicy(warning_bytes=1, max_input_artifact_bytes=1)
    monkeypatch.setitem(task_inspection.inspect_task.__kwdefaults__, 'resource_policy', policy)
    with pytest.raises(RuntimeError, match='interrupt witness'):
        with bundle_size_scope(True):
            with pytest.raises(api.PatchHarborError):
                api.inspect_task(task)  # A new public request defaults to bounded.
            assert api.inspect_task(task, force=True).package_sha256
            raise RuntimeError('interrupt witness')
    with pytest.raises(api.PatchHarborError):
        api.inspect_task(task)


def test_crc_is_checked_even_with_force():
    raw = archive(data=b'crc witness')
    corrupted = raw.replace(b'crc witness', b'CRC witness', 1)
    assert corrupted != raw
    with bundle_size_scope(True), pytest.raises(ZipPayloadError):
        read_zip_payload_bytes(corrupted)


def test_force_is_not_an_automatic_watcher_option():
    with pytest.raises(SystemExit) as error:
        main(['execute', '--automatic', '--force'], stdout=StringIO(), stderr=StringIO())
    assert error.value.code == 2


def test_forced_execute_keeps_repository_binding(tmp_path, monkeypatch):
    (repository, _), = registered(tmp_path, monkeypatch)
    state = api.bundle(repository)
    contents = tmp_path / 'contents'; contents.mkdir()
    (contents / 'run.sh').write_bytes(pack_support.SCRIPT)
    task = api.pack_task(contents, reference_bundle=state.path, entrypoint='run.sh',
                         output_directory=tmp_path)
    (repository / 'tracked.txt').write_text('state changed after reference\n')
    report = api.execute(task.path, force=True)
    assert not report.primary_result.success
    assert not report.primary_result.entrypoint_started
    assert report.process_exit_code == 9
    assert not (repository / 'run.sh').exists()
