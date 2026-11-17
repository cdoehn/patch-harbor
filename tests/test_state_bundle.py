"""A State establishes context; a Result reports an Execute, including failures."""
from hashlib import sha256
import json

import pytest

from patchharbor import api
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.exchange import classify_exchange_artifact
from patchharbor.reference_reader import read_reference
from tests.reference_support import reference_entries, write_reference, edit_document
from tests.result_runtime_support import edit_metadata
from tools import pyz_bootstrap as bootstrap


@pytest.mark.parametrize('operation,label,artifact_kind', [
    ('bundle', 'State', 'state_bundle'),
    ('success', 'Result', 'result_bundle'),
    ('failure', 'Result', 'result_bundle'),
    ('dry_run', 'Result', 'result_bundle'),
    ('mismatch', 'Result', 'result_bundle'),
])
def test_both_reference_kinds_pack_and_validate_without_an_execution(
    tmp_path, operation, label, artifact_kind,
):
    files, _ = reference_entries(kind=operation)
    reference = tmp_path / 'arbitrary-name.data'
    write_reference(reference, files)
    original = reference.read_bytes()
    assert json.loads(files['environment.json'])['bundle_type'] == label
    classified = classify_exchange_artifact(reference)
    assert classified.kind.value == artifact_kind and classified.package is None
    facts, digest = read_reference(reference)
    assert facts.bundle_kind.label == label
    assert digest == sha256(original).hexdigest()
    snapshot = api.read_reference_snapshot(reference, expected_sha256=digest)
    assert snapshot.bundle_kind.label == label
    assert snapshot.effective.files['tracked.txt'].content == b'base\x00\xff\n'
    content = tmp_path / 'content'
    content.mkdir()
    (content / 'run.sh').write_text('#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    (tmp_path / 'tasks').mkdir()
    packed = api.pack_task(content, reference_bundle=reference, entrypoint='run.sh',
                           output_directory=tmp_path / 'tasks')
    assert packed.validation.binding_matches
    assert api.validate_task(packed.path, reference_bundle=reference).reference_sha256 == digest
    assert reference.read_bytes() == original
    if operation == 'bundle':
        evidence = parse_archive_evidence(original, reference)
        assert evidence.kind == 'state_bundle' and evidence.receipt is None
        assert facts.expected is None and facts.task_sha256 is None
        assert not facts.primary_result.entrypoint_started


@pytest.mark.parametrize('operation', ['bundle', 'success', 'failure', 'dry_run'])
@pytest.mark.parametrize('fault', ['marker', 'handoff'])
def test_conflicting_kinds_are_rejected_before_pack_output(tmp_path, operation, fault):
    files, _ = reference_entries(kind=operation)
    wrong_label = 'Result' if operation == 'bundle' else 'State'
    if fault == 'marker':
        edit_document(files, 'manifest.json', lambda d: d.update(
            marker='patch-harbor-' + wrong_label.lower() + '-bundle'))
    else:
        edit_document(files, 'environment.json', lambda d: d.update(bundle_type=wrong_label))
    reference = tmp_path / 'reference.zip'
    write_reference(reference, files)
    original = reference.read_bytes()
    contents = tmp_path / 'contents'; contents.mkdir()
    output = tmp_path / 'output'; output.mkdir()
    (contents / 'run.sh').write_bytes(b'#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    with pytest.raises(api.PatchHarborError):
        read_reference(reference)
    with pytest.raises(api.PatchHarborError):
        api.pack_task(contents, reference_bundle=reference, entrypoint='run.sh', output_directory=output)
    if fault == 'marker':
        with pytest.raises(ValueError, match='kind and operation disagree'):
            bootstrap.assess(reference)
    assert reference.read_bytes() == original and not list(output.iterdir())


@pytest.mark.parametrize('capability', [None, [], [True], [5.0], ['5'], [5, 5], [6]])
def test_state_capabilities_are_checked_by_native_and_standalone_readers(tmp_path, capability):
    files, _ = reference_entries()
    edit_metadata(files, lambda d: d['capabilities'].update(state_formats=capability))
    reference = tmp_path / 'state.zip'; write_reference(reference, files)
    original = reference.read_bytes()
    with pytest.raises(api.PatchHarborError):
        read_reference(reference)
    with pytest.raises(ValueError):
        bootstrap.assess(reference)
    assert reference.read_bytes() == original


@pytest.mark.parametrize('kind', ['bundle', 'success'])
def test_filename_cannot_relabel_reference_or_create_execute_receipt(tmp_path, kind):
    files, _ = reference_entries(kind=kind)
    other = 'Result' if kind == 'bundle' else 'State'
    reference = tmp_path / ('repo_' + other + '_Bundle.zip')
    write_reference(reference, files)
    facts, _ = read_reference(reference)
    expected = 'state_bundle' if kind == 'bundle' else 'result_bundle'
    assert classify_exchange_artifact(reference).kind.value == expected
    assert facts.bundle_kind.artifact_kind == expected
    assert facts.task_sha256 is None and facts.completed_commit is None
