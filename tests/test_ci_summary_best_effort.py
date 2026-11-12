"""Diagnostic command failure handling never replaces acceptance evidence."""
import json

import pytest

from scripts.summarize_ci_tests import main
from tools.acceptance_catalog import LANES
from tools.test_results import validate


@pytest.mark.parametrize('best_effort', [False, True])
@pytest.mark.parametrize('failure', ['output', 'artifact'])
def test_summary_failure_policy_is_explicit_and_preserves_reports(tmp_path, capsys, best_effort, failure):
    source = tmp_path / 'patchharbor-core-tests.json'
    source.write_bytes(b'{invalid report')
    before = source.read_bytes()
    output = tmp_path if failure == 'output' else tmp_path / 'summary.md'
    artifact = LANES[0].artifact if failure == 'output' else 'unknown-acceptance-lane'
    arguments = ['--reports-dir', str(tmp_path), '--artifact', artifact, '--output', str(output)]
    if best_effort:
        arguments.append('--best-effort')
    assert main(arguments) == (0 if best_effort else 1)
    assert source.read_bytes() == before
    assert capsys.readouterr().err
    if failure == 'artifact':
        assert not output.exists()


@pytest.mark.parametrize('best_effort', [False, True])
def test_summary_cannot_turn_failed_evidence_into_success(tmp_path, best_effort):
    report = {
        'format_version': 2, 'run_id': 'failed-run', 'binding': {'source': 'same'},
        'expected_workers': 0, 'mode': 'run', 'started': [], 'finished': {},
        'collections': {'serial': ['test_a']}, 'proofs': {}, 'collection_reports': [],
        'errors': [], 'exitstatus': 1,
        'reports': [dict(nodeid='test_a', when=phase, outcome='failed' if phase == 'call' else 'passed',
                         reason='', xfail=False, subtest=None, worker='serial')
                    for phase in ('setup', 'call', 'teardown')],
    }
    source = tmp_path / 'patchharbor-core-tests.json'
    source.write_text(json.dumps(report), encoding='utf-8')
    before = source.read_bytes()
    output = tmp_path / 'summary.md'
    arguments = ['--reports-dir', str(tmp_path), '--artifact', LANES[0].artifact, '--output', str(output)]
    if best_effort:
        arguments.append('--best-effort')
    assert main(arguments) == 0
    assert output.stat().st_size > 0 and source.read_bytes() == before
    with pytest.raises(ValueError):
        validate(json.loads(source.read_text(encoding='utf-8')))


def test_best_effort_does_not_hide_command_argument_errors():
    with pytest.raises(SystemExit) as outcome:
        main(['--best-effort'])
    assert outcome.value.code == 2
