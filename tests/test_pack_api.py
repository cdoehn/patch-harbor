"""Public pack contract, actual ZIP verification and faulted publication boundaries."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import hashlib
import inspect
import os
from pathlib import Path
import subprocess
from threading import Barrier
import typing
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor import patch_pack as core
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.platform.filesystem import FileChangedDuringRead
from patchharbor.platform.pack_output import OwnedPackFile, OutputDirectory
from tests.test_captured_reference import _reference
from tests.test_pack_sources import SCRIPT


@pytest.fixture
def request_files(tmp_path):
    reference, _, _ = _reference(tmp_path)
    contents = tmp_path / 'contents'; contents.mkdir()
    (contents / 'run.sh').write_bytes(SCRIPT)
    (contents / 'binary').write_bytes(b'\0\xff\r\n')
    output = tmp_path / 'out'; output.mkdir()
    return contents, reference, output


def pack(files, **kwargs):
    contents, reference, output = files
    options = dict(reference_bundle=reference, entrypoint='run.sh', output_directory=output)
    options.update(kwargs)
    if 'output' in kwargs:
        options.pop('output_directory')
    return api.pack_patch(contents, **options)


def fail(reason, call):
    with pytest.raises(PatchHarborError) as caught:
        call()
    assert caught.value.reason is reason
    return caught.value


def test_pack_api_has_exact_typed_signature():
    signature = inspect.signature(api.pack_patch)
    assert list(signature.parameters) == ['content_directory', 'reference_bundle', 'entrypoint',
                                          'output', 'output_directory', 'modes', 'observer']
    assert signature.parameters['content_directory'].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in list(signature.parameters.values())[1:])
    assert set(typing.get_type_hints(api.pack_patch)) == set(signature.parameters) | {'return'}
    assert {'pack_patch', 'PatchPackResult'} <= set(api.__all__)


def test_public_pack_is_silent_preserves_inputs_and_returns_actual_validated_bytes(request_files, capfd):
    contents, reference, output = request_files
    originals = {p: p.read_bytes() for p in (reference, *(contents.iterdir()))}
    result = pack(request_files, modes={'binary': 0o755})
    assert isinstance(result, api.PatchPackResult)
    assert result.path.is_absolute() and result.path.parent == output
    assert set(output.iterdir()) == {result.path}
    assert result.package_id.version == 4 and result.created_at.utcoffset().total_seconds() == 0
    assert result.package_sha256 == hashlib.sha256(result.path.read_bytes()).hexdigest()
    assert result.package_size == result.path.stat().st_size
    assert result.reference_sha256 == hashlib.sha256(reference.read_bytes()).hexdigest()
    assert result.validation.scope is api.PatchValidationScope.REFERENCE
    assert result.validation.binding_matches is True and result.validation.inspection.manifest is not None
    assert result.validation.not_checked
    assert result.validation.inspection == api.inspect_patch(result.path)
    assert result.validation.reference_sha256 == api.validate_patch(result.path, reference_bundle=reference).reference_sha256
    assert type(result.warnings) is tuple
    with pytest.raises(FrozenInstanceError): result.path = output / 'other.zip'
    assert all(p.read_bytes() == raw for p, raw in originals.items())
    with ZipFile(result.path) as archive:
        assert archive.read('run.sh') == SCRIPT
        assert archive.read('binary') == b'\0\xff\r\n'
        assert (archive.getinfo('binary').external_attr >> 16) & 0o777 == 0o755
    assert capfd.readouterr() == ('', '')


def test_explicit_name_and_automatic_name_have_independent_request_identities(request_files):
    _, _, output = request_files
    first = pack(request_files, output=output / 'manual.zip.txt')
    second = pack(request_files)
    assert first.path.name == 'manual.zip.txt'
    assert second.path.name.endswith(str(second.package_id)[:6] + '.zip.txt')
    assert first.package_id != second.package_id
    assert first.created_at <= second.created_at


@pytest.mark.parametrize('option,value,error', [
    ('content_directory', b'bytes', TypeError), ('reference_bundle', b'bytes', TypeError),
    ('output', b'bytes', TypeError), ('output_directory', b'bytes', TypeError),
    ('content_directory', '', ValueError), ('reference_bundle', '', ValueError),
    ('output', '', ValueError), ('output_directory', '', ValueError),
    ('entrypoint', b'run.sh', TypeError), ('entrypoint', '', ValueError),
    ('modes', [], TypeError), ('modes', {'run.sh': True}, TypeError),
    ('modes', {1: 0o644}, TypeError), ('modes', {'run.sh': '0644'}, TypeError),
    ('observer', object(), TypeError),
])
def test_formal_argument_errors_precede_any_capture(request_files, monkeypatch, option, value, error):
    contents, reference, output = request_files
    options = dict(content_directory=contents, reference_bundle=reference, entrypoint='run.sh', output_directory=output)
    options[option] = value
    if option == 'output': options.pop('output_directory')
    monkeypatch.setattr(core, 'capture_result_reference', lambda *a, **k: pytest.fail('capture on invalid arguments'))
    with pytest.raises(error): api.pack_patch(**options)
    assert not list(output.iterdir())


@pytest.mark.parametrize('both', [False, True])
def test_exactly_one_explicit_output_choice(request_files, both):
    contents, reference, output = request_files
    kwargs = {'output': output/'manual.zip.txt', 'output_directory': output} if both else {}
    with pytest.raises(ValueError):
        api.pack_patch(contents, reference_bundle=reference, entrypoint='run.sh', **kwargs)


def test_mutable_mode_mapping_is_copied_before_observer_runs(request_files):
    modes = {'binary': 0o755}
    events = []
    def observer(event):
        events.append(event); modes['binary'] = 0o777
    result = pack(request_files, modes=modes, observer=observer)
    assert events and modes['binary'] == 0o777
    with ZipFile(result.path) as archive:
        assert (archive.getinfo('binary').external_attr >> 16) & 0o777 == 0o755


@pytest.mark.parametrize('contents,mode,entrypoint,reason', [
    ({'run.sh': b'#!/bin/bash\nexit 0\n'}, {}, 'run.sh', FailureReason.NO_VALID_SCRIPT),
    ({'run.sh': b'#!/usr/bin/python3\n# PATCHHARBOR\n'}, {}, 'run.sh', FailureReason.INTERPRETER_ERROR),
    ({}, {}, 'missing.sh', FailureReason.PATCH_PACKAGE_ERROR),
    ({'patch.json': b'{}'}, {}, 'run.sh', FailureReason.PATCH_PACKAGE_ERROR),
    ({}, {'missing': 0o644}, 'run.sh', FailureReason.PATCH_PACKAGE_ERROR),
    ({}, {'binary': 0o777}, 'run.sh', FailureReason.SOURCE_ERROR),
    ({}, {}, '../run.sh', FailureReason.SOURCE_ERROR),
])
def test_shared_input_errors_keep_categories_before_any_output(request_files, contents, mode, entrypoint, reason):
    root, _, output = request_files
    for name, raw in contents.items(): (root / name).write_bytes(raw)
    fail(reason, lambda: pack(request_files, modes=mode, entrypoint=entrypoint))
    assert not list(output.iterdir())


def test_invalid_reference_is_not_repaired_or_retried(request_files):
    _, reference, output = request_files
    reference.write_bytes(b'not a result')
    fail(FailureReason.SOURCE_ERROR, lambda: pack(request_files))
    assert reference.read_bytes() == b'not a result' and not list(output.iterdir())


def test_pack_does_not_run_tools_or_change_process_state(request_files, monkeypatch):
    cwd, environment = Path.cwd(), dict(os.environ)
    def forbidden(*a, **k): pytest.fail('pack spawned an external tool')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = pack(request_files)
    assert result.validation.binding_matches
    assert Path.cwd() == cwd and dict(os.environ) == environment


@pytest.mark.parametrize('reason', [FailureReason.SOURCE_ERROR, FailureReason.PATCH_PACKAGE_ERROR, FailureReason.STATE_MISMATCH])
def test_mandatory_written_archive_validation_cannot_be_skipped_or_reclassified(request_files, monkeypatch, reason):
    calls = []
    def rejected(path, reference, **kwargs):
        calls.append(path)
        assert path.is_file() and path.name.endswith('.partial')
        assert 'expected_identity' in kwargs
        with ZipFile(path) as archive: assert archive.read('run.sh') == SCRIPT
        assert not any(p.name.endswith('.zip.txt') for p in request_files[2].iterdir())
        raise PatchHarborError('controlled validator rejection', reason)
    monkeypatch.setattr(core, 'validate_patch_against_reference', rejected)
    fail(reason, lambda: pack(request_files))
    assert len(calls) == 1 and not list(request_files[2].iterdir())


@pytest.mark.parametrize('method', ['sync', 'publish'])
def test_required_sync_and_unsupported_publication_are_output_failures(request_files, monkeypatch, method):
    def broken(*a, **k): raise OSError('unsupported target primitive')
    monkeypatch.setattr(OwnedPackFile, method, broken)
    fail(FailureReason.PAYLOAD_PREPARATION_ERROR, lambda: pack(request_files))
    assert not list(request_files[2].iterdir())


@pytest.mark.parametrize('stage', ['capture', 'write', 'validate', 'publish'])
def test_interrupt_before_publication_has_130_and_no_partial_final(request_files, monkeypatch, stage):
    def interrupted(*a, **k): raise KeyboardInterrupt()
    target, name = {'capture': (core, 'capture_sources'), 'write': (core, 'write_prepared_candidate'),
                    'validate': (core, 'validate_patch_against_reference'), 'publish': (OwnedPackFile, 'publish')}[stage]
    monkeypatch.setattr(target, name, interrupted)
    fail(FailureReason.INTERRUPTED, lambda: pack(request_files))
    assert not list(request_files[2].iterdir())


@pytest.mark.parametrize('kind', ['add_source', 'change_source', 'change_reference'])
def test_known_input_change_after_validation_fails_without_retry(request_files, monkeypatch, kind):
    original = core.validate_patch_against_reference
    def mutate(*a, **k):
        validated = original(*a, **k)
        contents, reference, _ = request_files
        if kind == 'add_source': (contents / 'new').write_bytes(b'new')
        else:
            path = reference if kind == 'change_reference' else contents / 'binary'
            metadata = path.stat(); raw = path.read_bytes()
            path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        return validated
    monkeypatch.setattr(core, 'validate_patch_against_reference', mutate)
    fail(FailureReason.SOURCE_ERROR, lambda: pack(request_files))
    assert not list(request_files[2].iterdir())


@pytest.mark.skipif(os.name == 'nt', reason='Windows publication handle prevents deliberate file writes/swaps')
@pytest.mark.parametrize('kind', ['bytes', 'replace', 'symlink', 'hardlink'])
def test_output_mutation_after_validation_never_publishes_or_deletes_foreign_file(request_files, monkeypatch, kind):
    original = core.validate_patch_against_reference
    alien = request_files[2].parent / 'alien'; alien.write_bytes(b'foreign data')
    def mutate(path, *a, **k):
        validated = original(path, *a, **k)
        if kind == 'bytes':
            metadata = path.stat(); raw = path.read_bytes()
            path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        elif kind == 'hardlink': os.link(path, request_files[2] / 'foreign-link')
        else:
            path.unlink()
            if kind == 'replace': path.write_bytes(b'foreign data')
            else: path.symlink_to(alien)
        return validated
    monkeypatch.setattr(core, 'validate_patch_against_reference', mutate)
    error = fail(FailureReason.SOURCE_ERROR, lambda: pack(request_files))
    assert alien.read_bytes() == b'foreign data'
    assert not any(p.name.endswith('.zip.txt') for p in request_files[2].iterdir())
    remaining = list(request_files[2].iterdir())
    if kind in ('replace', 'symlink'):
        assert len(remaining) == 1 and remaining[0].read_bytes() == b'foreign data'
        assert getattr(error, '__notes__', ())


def test_destination_created_at_last_instant_is_never_overwritten(request_files, monkeypatch):
    output = request_files[2] / 'manual.zip.txt'
    original = OwnedPackFile.publish
    def collision(self, name):
        output.write_bytes(b'other producer')
        return original(self, name)
    monkeypatch.setattr(OwnedPackFile, 'publish', collision)
    fail(FailureReason.PAYLOAD_PREPARATION_ERROR, lambda: pack(request_files, output=output))
    assert output.read_bytes() == b'other producer'
    assert list(request_files[2].iterdir()) == [output]


def test_two_concurrent_requests_publish_exactly_one_complete_package(request_files, monkeypatch):
    barrier = Barrier(2)
    original = OwnedPackFile.publish
    def synchronized(self, name):
        barrier.wait(timeout=20)
        return original(self, name)
    monkeypatch.setattr(OwnedPackFile, 'publish', synchronized)
    destination = request_files[2] / 'shared.zip.txt'
    def attempt():
        try: return pack(request_files, output=destination)
        except PatchHarborError as error: return error
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    winners = [r for r in results if isinstance(r, api.PatchPackResult)]
    losers = [r for r in results if isinstance(r, PatchHarborError)]
    assert len(winners) == len(losers) == 1
    assert losers[0].reason is FailureReason.PAYLOAD_PREPARATION_ERROR
    assert winners[0].package_sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert set(request_files[2].iterdir()) == {destination}


@pytest.mark.skipif(os.name == 'nt', reason='Windows renames the owned file without a temporary second name')
@pytest.mark.parametrize('failure', [OSError, KeyboardInterrupt])
def test_postpublication_cleanup_retains_complete_success_without_observer(request_files, monkeypatch, failure):
    original = os.unlink
    def broken(path, *a, **k):
        if str(path).startswith('.patchharbor-pack-'): raise failure('controlled cleanup failure')
        return original(path, *a, **k)
    monkeypatch.setattr(os, 'unlink', broken)
    result = pack(request_files)
    assert result.path.is_file() and result.package_sha256 == hashlib.sha256(result.path.read_bytes()).hexdigest()
    assert result.validation.binding_matches and result.reference_sha256
    partial = next(p for p in request_files[2].iterdir() if p.name.endswith('.partial'))
    assert any(str(partial) in warning for warning in result.warnings)


def test_watcher_can_take_final_file_before_api_returns_success(request_files, monkeypatch):
    original = OwnedPackFile.cleanup
    destination = request_files[2] / 'manual.zip.txt'
    taken = request_files[2].parent / 'taken.zip'
    def watcher(self):
        # On Windows the publication guard is deliberately released by cleanup.
        warnings = original(self)
        if self.published: destination.rename(taken)
        return warnings
    monkeypatch.setattr(OwnedPackFile, 'cleanup', watcher)
    result = pack(request_files, output=destination)
    assert not destination.exists() and result.path == destination
    assert result.package_sha256 == hashlib.sha256(taken.read_bytes()).hexdigest()


def test_missing_own_template_fails_without_borrowing_reference_instructions(request_files, monkeypatch):
    class Missing:
        def capture(self):
            from types import SimpleNamespace
            return SimpleNamespace(artifact=None, reason='integrity_failure')
    monkeypatch.setattr(core, 'RuntimeProvider', Missing)
    monkeypatch.setattr(core, 'PyzProvider', Missing)
    fail(FailureReason.PAYLOAD_PREPARATION_ERROR, lambda: pack(request_files))
    assert not list(request_files[2].iterdir())


def test_unexpected_programming_error_after_publication_is_not_claimed_as_success(request_files, monkeypatch):
    original = OwnedPackFile.cleanup
    def programming_error(self):
        warnings = original(self)
        if self.published: raise RuntimeError('controlled programming fault')
        return warnings
    monkeypatch.setattr(OwnedPackFile, 'cleanup', programming_error)
    with pytest.raises(RuntimeError): pack(request_files)
    assert len(list(request_files[2].iterdir())) == 1


def test_pack_validates_static_contract_without_executing_broken_shell(request_files):
    (request_files[0] / 'run.sh').write_bytes(b'#!/usr/bin/env bash\n# PATCHHARBOR\nif deliberately broken (\n')
    result = pack(request_files)
    assert result.validation.binding_matches and result.validation.not_checked


def test_reservation_stream_failure_cleans_owned_file_and_handle(request_files, monkeypatch):
    original = os.fdopen
    def rejected(fd, mode='r', *a, **k):
        if mode == 'w+b': raise OSError('controlled stream initialization failure')
        return original(fd, mode, *a, **k)
    monkeypatch.setattr(os, 'fdopen', rejected)
    fail(FailureReason.PAYLOAD_PREPARATION_ERROR, lambda: pack(request_files))
    assert not list(request_files[2].iterdir())


@pytest.mark.skipif(os.name == 'nt', reason='native Windows guard prevents deliberate final file substitution')
def test_identity_loss_at_publication_keeps_source_error_and_foreign_file(request_files, monkeypatch):
    original = OwnedPackFile.publish
    def swapped(self, name):
        self.path.unlink(); self.path.write_bytes(b'foreign')
        return original(self, name)
    monkeypatch.setattr(OwnedPackFile, 'publish', swapped)
    fail(FailureReason.SOURCE_ERROR, lambda: pack(request_files))
    paths = list(request_files[2].iterdir())
    assert len(paths) == 1 and paths[0].name.endswith('.partial')
    assert paths[0].read_bytes() == b'foreign'


@pytest.mark.parametrize('field', ['bytes', 'mode'])
def test_valid_but_semantically_substituted_written_package_is_not_released(request_files, monkeypatch, field):
    original = core.write_prepared_candidate
    def changed(stream, candidate):
        entries = tuple((name, b'substituted' if name == 'binary' and field == 'bytes' else data,
                         0o755 if name == 'binary' and field == 'mode' else mode)
                        for name, data, mode in candidate.entries)
        return original(stream, replace(candidate, entries=entries))
    monkeypatch.setattr(core, 'write_prepared_candidate', changed)
    fail(FailureReason.SOURCE_ERROR, lambda: pack(request_files))
    assert not list(request_files[2].iterdir())
