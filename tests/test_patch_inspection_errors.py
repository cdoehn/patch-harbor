"""Adversarial static inspection, stable captures and request-local observations."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import stat
import struct
from threading import Barrier
from zipfile import ZIP_DEFLATED, ZIP_LZMA, ZIP_STORED, ZipFile, ZipInfo

import pytest

from patchharbor import api
from patchharbor.cli import main
from patchharbor.patch_inspection import inspect_patch
import patchharbor.patch_package as packages
from patchharbor.platform.filesystem import FileChangedDuringRead
from patchharbor.progress import activity, observe_activity
from patchharbor.resource_policy import ResourcePolicy
from tests.test_patch_inspection import MANIFEST, SCRIPT, write_package


def json_cli_failure(path, command, code):
    stdout, stderr = StringIO(), StringIO()
    assert main([command, str(path), '--json'], stdout=stdout, stderr=stderr) == code
    result = json.loads(stdout.getvalue())
    assert result['output_version'] == 2 and result['command'] == command
    assert result['success'] is False and result['result'] is None
    assert result['process_exit_code'] == result['error']['patchharbor_error_code'] == code
    assert stderr.getvalue() == ''


def broken_archive(case):
    entries = [('patch.json', json.dumps(MANIFEST).encode()), ('run.sh', SCRIPT)]
    compression = ZIP_STORED
    if case == 'duplicate':
        entries.append(('run.sh', SCRIPT))
    elif case == 'file_directory_collision':
        entries += [('folder', b'file'), ('folder/child', b'child')]
    elif case == 'directory_data':
        entries.append(('folder/', b'not-empty'))
    elif case in ('symlink', 'fifo', 'device', 'unsafe_mode'):
        entries.append(('special', b'x'))
    elif case == 'reserved_path':
        entries.append(('.GiT/config', b'bad'))
    elif case == 'invalid_member':
        entries.append(('CON.txt', b'bad'))
    elif case == 'deflate':
        compression = ZIP_DEFLATED
    elif case == 'lzma':
        pytest.importorskip('lzma')
        compression = ZIP_LZMA
    out = BytesIO()
    with ZipFile(out, 'w', compression=compression) as archive:
        for name, data in entries:
            info = ZipInfo(name)
            info.create_system = 3
            info.compress_type = compression
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            if name.endswith('/'):
                info.external_attr = (stat.S_IFDIR | 0o755) << 16
            if name == 'special':
                mode = {'symlink': stat.S_IFLNK | 0o644, 'fifo': stat.S_IFIFO | 0o644,
                        'device': stat.S_IFCHR | 0o644, 'unsafe_mode': stat.S_IFREG | 0o4666}[case]
                info.external_attr = mode << 16
            if case == 'duplicate' and name == 'run.sh' and name in archive.namelist():
                with pytest.warns(UserWarning):
                    archive.writestr(info, data)
            else:
                archive.writestr(info, data)
    raw = bytearray(out.getvalue())
    if case in ('crc', 'encrypted', 'compression', 'deflate', 'lzma'):
        with ZipFile(BytesIO(raw)) as archive:
            member = archive.getinfo('run.sh')
        local = member.header_offset
        name_length, extra_length = struct.unpack_from('<HH', raw, local + 26)
        start = local + 30 + name_length + extra_length
        central = raw.index(b'PK\x01\x02')
        while True:
            length, extra, comment = struct.unpack_from('<HHH', raw, central + 28)
            if raw[central + 46:central + 46 + length] == b'run.sh':
                break
            central += 46 + length + extra + comment
        if case == 'crc':
            raw[start] ^= 1
        elif case == 'encrypted':
            for offset in (local + 6, central + 8):
                struct.pack_into('<H', raw, offset, struct.unpack_from('<H', raw, offset)[0] | 1)
        elif case == 'compression':
            struct.pack_into('<H', raw, local + 8, 99)
            struct.pack_into('<H', raw, central + 10, 99)
        elif case == 'deflate':
            # A final DEFLATE block with reserved BTYPE=3, not merely a bad CRC.
            raw[start] = 7
        else:
            # Invalid LZMA properties after its four-byte ZIP method header.
            raw[start + 4] = 255
    return bytes(raw)


@pytest.mark.parametrize('case', ['duplicate', 'file_directory_collision', 'directory_data',
                                'symlink', 'fifo', 'device', 'unsafe_mode', 'reserved_path',
                                'invalid_member', 'crc', 'encrypted', 'compression', 'deflate', 'lzma'])
@pytest.mark.parametrize('command', ['inspect', 'validate'])
def test_archive_failures_are_input_errors_without_partial_results(tmp_path, case, command):
    path = tmp_path / 'bad.zip'
    path.write_bytes(broken_archive(case))
    with pytest.raises(api.PatchHarborError) as caught:
        getattr(api, command + '_patch')(path)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR
    json_cli_failure(path, command, 4)


@pytest.mark.parametrize('content', [
    b'\xef\xbb\xbf' + json.dumps(MANIFEST).encode(),
    json.dumps(MANIFEST).encode()[:-1] + b',"marker":"patch-harbor"}',
    json.dumps({**MANIFEST, 'format_version': True}).encode(),
    json.dumps({**MANIFEST, 'format_version': 1.0}).encode(),
    json.dumps({**MANIFEST, 'base_commit': '123456'}).encode(),
    json.dumps({**MANIFEST, 'repo_id': True}).encode(),
    json.dumps({**MANIFEST, 'fingerprint_algorithm': 'unknown'}).encode(),
    json.dumps({**MANIFEST, 'entrypoint': 'absent.sh'}).encode(),
    json.dumps({**MANIFEST, 'unused': 1}).encode(),
    b'{"format_version":NaN}', b'[]', b'\xff',
    b'{"nested":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}',
], ids=['bom', 'duplicate-key', 'boolean-version', 'float-version', 'short-commit',
        'boolean-id', 'unknown-algorithm', 'missing-entrypoint', 'extra-field',
        'nan', 'array', 'encoding', 'deep-json'])
@pytest.mark.parametrize('command', ['inspect', 'validate'])
def test_invalid_manifest_is_domain_error_not_crash(tmp_path, content, command):
    path = tmp_path / 'bad.zip'
    write_package(path, changes={'patch.json': content})
    json_cli_failure(path, command, 10)


@pytest.mark.parametrize('content', [b'\xef\xbb\xbf{}', b'{"marker":NaN}', b'[]',
                                  b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'],
                         ids=['bom', 'nan', 'array', 'deep-json'])
def test_bad_handoff_is_rejected_as_package_error(tmp_path, content):
    path = tmp_path / 'bad.zip'
    write_package(path, handoff=True, changes={'PATCHHARBOR_META/environment.json': content})
    json_cli_failure(path, 'inspect', 10)


def test_json_backend_recursion_limit_is_a_manifest_error(tmp_path, monkeypatch):
    # Python versions differ in how deeply nested JSON is decoded internally.
    import patchharbor.patch_manifest as manifests
    path = tmp_path / 'patch.zip'
    write_package(path)
    def recursion_limited(*args, **kwargs):
        raise RecursionError('decoder limit')
    monkeypatch.setattr(manifests.json, 'loads', recursion_limited)
    with pytest.raises(api.PatchHarborError) as caught:
        api.inspect_patch(path)
    assert caught.value.reason is api.FailureReason.PATCH_PACKAGE_ERROR


def test_unexpected_programming_failure_is_not_disguised_as_package_rejection(tmp_path, monkeypatch):
    path = tmp_path / 'patch.zip'
    write_package(path)
    def broken(*args, **kwargs):
        raise AssertionError('internal bug')
    monkeypatch.setattr(packages, 'read_stable_regular_file_with_sha256', broken)
    with pytest.raises(AssertionError):
        api.inspect_patch(path)


@pytest.mark.parametrize('operation', [api.inspect_patch, api.validate_patch])
def test_inspection_uses_one_capture_even_if_name_is_replaced_after_read(tmp_path, monkeypatch, operation):
    path = tmp_path / 'patch.zip'
    original_entries = write_package(path)
    original = path.read_bytes()
    read = packages.read_stable_regular_file_with_sha256
    calls = []
    def replace_after_capture(*args, **kwargs):
        calls.append(args[0])
        captured = read(*args, **kwargs)
        write_package(path, changes={'docs/data.bin': b'changed-and-longer-than-original'})
        return captured
    monkeypatch.setattr(packages, 'read_stable_regular_file_with_sha256', replace_after_capture)
    result = operation(path)
    info = result.inspection if isinstance(result, api.PatchValidationResult) else result
    assert calls == [path]
    assert info.package_sha256 == hashlib.sha256(original).hexdigest()
    assert info.package_size == len(original) != path.stat().st_size
    payload = next(entry for entry in info.entries if entry.path == 'docs/data.bin')
    assert payload.sha256 == hashlib.sha256(original_entries[payload.path]).hexdigest()
    monkeypatch.setattr(packages, 'read_stable_regular_file_with_sha256', read)
    assert api.inspect_patch(path).package_sha256 != info.package_sha256


@pytest.mark.parametrize('error', [FileChangedDuringRead('changed'), PermissionError('denied'),
                                  UnicodeEncodeError('utf-8', '\ud800', 0, 1, 'surrogate')])
def test_unstable_or_unreadable_capture_maps_to_input_error(tmp_path, monkeypatch, error):
    path = tmp_path / 'patch.zip'
    write_package(path)
    def unreadable(*args, **kwargs):
        raise error
    monkeypatch.setattr(packages, 'read_stable_regular_file_with_sha256', unreadable)
    json_cli_failure(path, 'inspect', 4)


def test_missing_directory_and_non_zip_are_not_discovery_inputs(tmp_path):
    json_cli_failure(tmp_path / 'missing.zip', 'validate', 4)
    json_cli_failure(tmp_path, 'validate', 4)
    path = tmp_path / 'plain.txt'
    path.write_text('# PATCHHARBOR\n')
    json_cli_failure(path, 'validate', 10)


def test_resource_boundaries_include_directories_and_all_payload_bytes(tmp_path):
    path = tmp_path / 'patch.zip'
    entries = write_package(path)
    sizes = [len(data) for data in entries.values()]
    boundary = ResourcePolicy(warning_bytes=max(sizes), max_input_artifact_bytes=path.stat().st_size,
                              max_content_bytes=max(sizes), max_zip_total_bytes=sum(sizes),
                              max_zip_entries=len(entries) + 1)
    assert inspect_patch(path, resource_policy=boundary).package_size == path.stat().st_size
    for policy in (replace(boundary, warning_bytes=1, max_content_bytes=max(sizes) - 1),
                   replace(boundary, max_zip_total_bytes=sum(sizes) - 1),
                   replace(boundary, max_zip_entries=len(entries))):
        with pytest.raises(api.PatchHarborError) as caught:
            inspect_patch(path, resource_policy=policy)
        assert caught.value.reason is api.FailureReason.SOURCE_ERROR


def test_relative_path_is_bound_before_caller_observer_changes_directory(tmp_path, monkeypatch):
    first, second = tmp_path / 'first', tmp_path / 'second'
    first.mkdir(); second.mkdir()
    write_package(first / 'patch.zip')
    write_package(second / 'patch.zip', changes={'docs/data.bin': b'different'})
    expected = api.inspect_patch(first / 'patch.zip')
    monkeypatch.chdir(first)
    def observer(event):
        monkeypatch.chdir(second)
    assert api.inspect_patch('patch.zip', observer=observer) == expected


def test_argument_errors_precede_filesystem_resolution(monkeypatch):
    def no_resolution(path):
        pytest.fail('filesystem path resolution happened before argument validation')
    monkeypatch.setattr(Path, 'absolute', no_resolution)
    for operation in (api.inspect_patch, api.validate_patch):
        with pytest.raises(TypeError):
            operation('patch.zip', observer=42)


@pytest.mark.parametrize('command', ['inspect', 'validate'])
@pytest.mark.parametrize('value', ['', 'nul\x00path'], ids=['empty', 'nul'])
def test_bad_cli_paths_fail_at_argument_boundary(command, value):
    with pytest.raises(SystemExit) as caught:
        main([command, value, '--json'], stdout=StringIO(), stderr=StringIO())
    assert caught.value.code == 2


def test_unavailable_calling_directory_is_an_input_error(monkeypatch):
    def unavailable(*args):
        raise FileNotFoundError('calling directory removed')
    with monkeypatch.context() as scope:
        scope.setattr(Path, 'cwd', unavailable)
        for command in ('inspect', 'validate'):
            json_cli_failure('patch.zip', command, 4)


def test_pathlike_is_evaluated_once(tmp_path):
    path = tmp_path / 'patch.zip'
    write_package(path)
    class Once:
        count = 0
        def __fspath__(self):
            self.count += 1
            assert self.count == 1
            return str(path)
    value = Once()
    api.inspect_patch(value)
    assert value.count == 1


def test_parallel_observers_and_nested_calls_are_request_local(tmp_path):
    paths = [tmp_path / 'first.zip', tmp_path / 'second.zip']
    for path in paths:
        write_package(path)
    barrier = Barrier(2)
    def inspect(path):
        events = []
        nested_delivery = []
        synchronized = False
        def observer(event):
            nonlocal synchronized
            events.append(event)
            if not synchronized:
                synchronized = True
                barrier.wait(timeout=15)
                # No observer means silent even inside the caller's active request.
                count = len(events)
                api.validate_patch(path)
                nested_delivery.append(len(events) - count)
        info = api.inspect_patch(path, observer=observer)
        return info, events, nested_delivery
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(inspect, paths))
    for (info, events, nested_delivery), own, other in zip(results, paths, reversed(paths), strict=True):
        assert info.package_sha256 == hashlib.sha256(own.read_bytes()).hexdigest()
        assert events and all(str(other) not in event.message for event in events)
        assert nested_delivery == [0]
    outer = []
    with observe_activity(outer.append):
        api.inspect_patch(paths[0])
        assert outer == []
        with pytest.raises(api.PatchHarborError):
            api.inspect_patch(tmp_path / 'missing')
        activity('OUTER', 'restored')
    assert len(outer) == 1 and outer[0].phase == 'OUTER'


def test_observer_error_does_not_turn_validity_into_failure_but_interrupt_propagates(tmp_path):
    path = tmp_path / 'patch.zip'
    write_package(path)
    def broken(event):
        raise RuntimeError('caller callback')
    assert api.inspect_patch(path, observer=broken) == api.inspect_patch(path)
    def interrupted(event):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        api.inspect_patch(path, observer=interrupted)


def test_supported_shebang_does_not_require_installed_interpreter(tmp_path, monkeypatch):
    path = tmp_path / 'patch.zip'
    write_package(path, changes={'run.sh': b'#!powershell.exe\n# PATCHHARBOR\n'})
    import patchharbor.interpreters as interpreters
    def forbidden(*args):
        pytest.fail('inspection attempted interpreter lookup')
    monkeypatch.setattr(interpreters, 'find_executable', forbidden)
    assert api.validate_patch(path).scope is api.PatchValidationScope.PACKAGE
