"""Stable proof identities survive xdist and fail closed on missing variants."""
from copy import deepcopy
import json

import pytest

from tests.runner_support import example, invoke, make_suite
from tools.test_results import EvidenceError, equivalent, validate


def version2():
    document = example()
    document.update(format_version=2, proofs={
        'test_a.py::test_a': {'id': 'handoff.commit-sequence', 'variant': '0'}})
    return document


def test_neutral_validator_reads_historical_reports_but_keeps_proof_versions_distinct():
    old, current = example(), version2()
    assert validate(old) == validate(current)
    equivalent(old, deepcopy(old)); equivalent(current, deepcopy(current))
    with pytest.raises(EvidenceError): equivalent(old, current)
    changed = deepcopy(current); changed['proofs']['test_a.py::test_a']['variant'] = '1'
    with pytest.raises(EvidenceError): equivalent(current, changed)


@pytest.mark.parametrize('fault', ['missing', 'not_mapping', 'outside_collection', 'missing_id',
    'missing_variant', 'empty_variant', 'wrong_type', 'extra_field', 'downgrade', 'future_format'])
def test_versioned_proof_assignments_reject_malformed_evidence(fault):
    document = version2(); proof = document['proofs']['test_a.py::test_a']
    if fault == 'missing': document.pop('proofs')
    elif fault == 'not_mapping': document['proofs'] = []
    elif fault == 'outside_collection': document['proofs'] = {'foreign': proof}
    elif fault == 'missing_id': proof.pop('id')
    elif fault == 'missing_variant': proof.pop('variant')
    elif fault == 'empty_variant': proof['variant'] = ''
    elif fault == 'wrong_type': proof['variant'] = 0
    elif fault == 'extra_field': proof['passed'] = True
    elif fault == 'downgrade': document['format_version'] = 1
    else: document['format_version'] = 3
    with pytest.raises(EvidenceError): validate(document)


@pytest.mark.parametrize('workers', ['2', '4'])
def test_real_parallel_proof_transport_uses_parameter_values_not_display_names(tmp_path, workers):
    suite = make_suite(tmp_path, """
        import pytest
        @pytest.mark.proof('handoff.commit-sequence', parameter='count')
        @pytest.mark.parametrize('count', [0, 1, 3], ids=['diagnosis', 'renamed', 'many'])
        def test_renamed_function(count): assert count >= 0
    """)
    path = tmp_path / 'report.json'
    completed = invoke(suite, path, workers=workers)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(path.read_bytes()); validate(report)
    assert report['format_version'] == 2 and report['expected_workers'] == int(workers)
    assert len(report['proofs']) == 3
    assert {(p['id'], p['variant']) for p in report['proofs'].values()} == {
        ('handoff.commit-sequence', '0'), ('handoff.commit-sequence', '1'), ('handoff.commit-sequence', '3')}
    assert all(end['proofs'] == report['proofs'] for end in report['finished'].values())


@pytest.mark.parametrize('fault', ['unknown_id', 'unknown_variant', 'missing_parameter',
    'ambiguous_marker', 'duplicate_marker', 'duplicate_variant', 'worker_disagreement', 'lost_worker_proofs'])
def test_real_parallel_proof_errors_fail_the_run(tmp_path, fault):
    marker = "@pytest.mark.proof('handoff.commit-sequence', parameter='count')"
    parameters = [0, 1, 3]
    if fault == 'unknown_id': marker = "@pytest.mark.proof('unregistered', parameter='count')"
    if fault == 'unknown_variant': parameters = [0, 1, 9]
    if fault == 'missing_parameter': marker = "@pytest.mark.proof('handoff.commit-sequence', parameter='absent')"
    if fault == 'ambiguous_marker': marker = "@pytest.mark.proof('handoff.commit-sequence', parameter='count', variant='0')"
    if fault == 'duplicate_marker': marker += '\n' + marker
    if fault == 'duplicate_variant': parameters = [0, 0, 1]
    config = ''
    if fault in ('worker_disagreement', 'lost_worker_proofs'):
        mutate = "summary['proofs'] = {}" if fault == 'worker_disagreement' else "summary.pop('proofs')"
        config = f"""
            import pytest
            @pytest.hookimpl(wrapper=True)
            def pytest_sessionfinish(session, exitstatus):
                yield
                if getattr(session.config, 'workerinput', {{}}).get('workerid') == 'gw1':
                    summary = session.config.workeroutput['ph_evidence']
                    {mutate}
        """
    body = 'import pytest\n' + marker + f"\n@pytest.mark.parametrize('count', {parameters!r})\ndef test_probe(count): pass\n"
    suite = make_suite(tmp_path, body, config); path = tmp_path / 'report.json'
    completed = invoke(suite, path, workers='2')
    assert completed.returncode != 0, completed.stdout + completed.stderr
    if path.is_file():
        with pytest.raises(EvidenceError): validate(json.loads(path.read_bytes()))
