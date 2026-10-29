"""Closed capability profiles retain native validation and data-only assessment."""
import hashlib
import socket
import subprocess

import pytest

from patchharbor import api
from patchharbor.result_reader import capture_result_reference
from scripts import pyz_bootstrap as bootstrap
from tests.pack_support import request_files
from tests.reference_support import bound_package, write_reference
from tests.result_pyz_support import canonical, format3
from tests.result_runtime_support import edit_metadata


@pytest.fixture(autouse=True)
def no_runtime_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('static capability validation executed external code')

    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(bootstrap, 'prepare', forbidden)
    monkeypatch.setattr(bootstrap, 'import_api', forbidden)


@pytest.mark.parametrize('result_formats', [[1,2,3],[3]], ids=['original_caps','current_caps'])
def test_closed_capabilities_keep_reference_bytes_binding_and_static_pack(
    canonical, request_files, tmp_path, result_formats,
):
    files, binding = format3(canonical)
    edit_metadata(files, lambda doc: doc['capabilities'].update(result_formats=result_formats))
    reference = tmp_path / 'result.zip'
    write_reference(reference, files)
    original = reference.read_bytes()
    digest = hashlib.sha256(original).hexdigest()

    captured = capture_result_reference(reference)
    runtime = captured.facts.runtime
    assert captured.sha256 == digest
    assert runtime.result_formats == tuple(result_formats)
    assert runtime.patch_formats == (1,)
    assert runtime.operations == ('inspect_patch', 'validate_patch', 'pack_patch')
    assert runtime.artifact.sha256 == hashlib.sha256(canonical).hexdigest()
    for key, expected in binding.items():
        assert str(getattr(captured.facts.context, key)) == expected

    assessment = bootstrap.assess(reference, trusted_source_sha256=digest)
    assert assessment.scope == 'runtime_descriptor_precheck'
    assert not assessment.full_reference_valid
    assert assessment.source_trusted and assessment.reference_sha256 == digest
    assert assessment.pyz_bytes == canonical

    contents, _, output = request_files
    packed = api.pack_patch(contents, reference_bundle=reference, entrypoint='run.sh',
                            output_directory=output)
    checked = api.validate_patch(packed.path, reference_bundle=reference)
    assert checked.binding_matches and checked.reference_sha256 == digest
    assert checked.scope == 'reference'
    for key, expected in binding.items():
        assert str(getattr(checked.context, key)) == expected
    assert list(output.iterdir()) == [packed.path]
    assert reference.read_bytes() == original


def assert_invalid_reference(files, binding, request_files, tmp_path):
    reference = tmp_path / 'invalid-result.zip'
    write_reference(reference, files)
    original = reference.read_bytes()
    patch = tmp_path / 'patch.zip'
    bound_package(patch, binding)
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, reference_bundle=reference)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR
    contents, _, output = request_files
    with pytest.raises(api.PatchHarborError) as caught:
        api.pack_patch(contents, reference_bundle=reference, entrypoint='run.sh',
                       output_directory=output)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR
    with pytest.raises(ValueError):
        bootstrap.assess(reference, trusted_source_sha256=hashlib.sha256(original).hexdigest())
    assert not list(output.iterdir())
    assert reference.read_bytes() == original


@pytest.mark.parametrize('result_formats', [
    [], [1], [2], [1,2], [1,3], [2,3], [3,3], [3,2,1], [1,2,3,4],
    [True,2,3], [3.0], ['3'], 3, None, {'3': True},
], ids=[
    'empty', 'only1', 'only2', 'missing3', 'subset13', 'subset23', 'duplicate', 'order',
    'future', 'bool', 'float', 'string_entry', 'scalar', 'null', 'mapping',
])
def test_other_result_capabilities_are_rejected_without_output(
    canonical, request_files, tmp_path, result_formats,
):
    files, binding = format3(canonical)
    edit_metadata(files, lambda doc: doc['capabilities'].update(result_formats=result_formats))
    assert_invalid_reference(files, binding, request_files, tmp_path)


@pytest.mark.parametrize('result_formats', [[1,2,3],[3]], ids=['original_caps','current_caps'])
@pytest.mark.parametrize('patch_formats', [[], [True], [1.0], [1,1], [1,2], '1', None],
                         ids=['empty','bool','float','duplicate','future','scalar','null'])
def test_result_capability_choice_does_not_relax_patch_format_validation(
    canonical, request_files, tmp_path, result_formats, patch_formats,
):
    files, binding = format3(canonical)
    edit_metadata(files, lambda doc: doc['capabilities'].update(
        result_formats=result_formats, patch_formats=patch_formats))
    assert_invalid_reference(files, binding, request_files, tmp_path)


@pytest.mark.parametrize('result_formats', [[1,2,3],[3]], ids=['original_caps','current_caps'])
def test_unavailable_runtime_cannot_claim_either_capability_profile(
    request_files, tmp_path, result_formats,
):
    files, binding = format3(None)
    edit_metadata(files, lambda doc: doc.update(capabilities={
        'operations': ['inspect_patch','validate_patch','pack_patch'],
        'patch_formats': [1], 'result_formats': result_formats,
    }))
    assert_invalid_reference(files, binding, request_files, tmp_path)
