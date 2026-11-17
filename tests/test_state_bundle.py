"""A State establishes context; a Result reports an Execute, including failures."""
from hashlib import sha256
import json

import pytest

from patchharbor import api
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.exchange import classify_exchange_artifact
from patchharbor.result_reader import read_result_reference
from tests.reference_support import reference_entries, write_reference


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
    facts, digest = read_result_reference(reference)
    assert facts.bundle_kind.label == label
    assert digest == sha256(original).hexdigest()
    snapshot = api.read_result_snapshot(reference, expected_sha256=digest)
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
