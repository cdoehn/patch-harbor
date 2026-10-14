"""Real release bytes and no-replace receipts for the manual acceptance jobs."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import capture_ci_build
from scripts import run_handoff_ci

pytestmark = pytest.mark.packaging


@pytest.fixture(scope='module')
def captured(tmp_path_factory):
    report = tmp_path_factory.mktemp('ci-build-evidence') / 'patchharbor-build.json'
    evidence = capture_ci_build.capture(report, commit='a' * 40)
    return report, evidence


def test_build_receipt_binds_real_distribution_bytes_and_interpreter(captured):
    report, evidence = captured
    assert json.loads(report.read_bytes()) == evidence
    directory = report.with_name(report.stem + '-artifacts')
    assert {p.name for p in directory.iterdir()} == {row['name'] for row in evidence['artifacts']}
    for row in evidence['artifacts']:
        raw = (directory / row['name']).read_bytes()
        assert len(raw) == row['size'] and sha256(raw).hexdigest() == row['sha256']
    binding = evidence['binding']
    expected = (binding['platform'], '.'.join(binding['python'].split('.')[:2]), binding['windows_engine'])
    assert run_handoff_ci._build_evidence(report.read_bytes(), expected, 'a' * 40, True) == evidence


def test_build_receipt_never_replaces_an_existing_attempt(captured, monkeypatch):
    report, _ = captured
    original = report.read_bytes()
    monkeypatch.setattr(capture_ci_build, 'build_release', lambda *a: pytest.fail('existing attempt rebuilt'))
    with pytest.raises(FileExistsError): capture_ci_build.capture(report, commit='a' * 40)
    assert report.read_bytes() == original
