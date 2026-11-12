"""Semantic diagnostic summaries do not replace the strict release validator."""
import pytest

from scripts.summarize_ci_tests import count_cases, summarize_document
from tools.test_results import validate


def document(rows, *, exitstatus=0, nodes=('test_a',)):
    return dict(format_version=2,run_id='run',binding={'source':'same'},expected_workers=0,
        mode='run',started=[],finished={},collections={'serial':list(nodes)},proofs={},
        collection_reports=[],reports=[dict(nodeid=n,when=p,outcome=o,reason='',xfail=False,subtest=None,worker='serial') for n,p,o in rows],
        errors=[],exitstatus=exitstatus)


def test_three_phases_count_as_one_passed_test_and_keep_missing_duration_unknown():
    doc = document([('test_a',p,'passed') for p in ('setup','call','teardown')])
    row = summarize_document(doc,{'commit':'full-sha','binding':doc['binding']},'full-sha')
    assert row['counts']['passed'] == 1 and sum(row['counts'].values()) == 1
    assert row['commit_binding_verified'] and row['status'] == 'passed'
    assert row['controller_observed_s'] is None and row['job_walltime_s'] is None
    assert row['timing_status'] == 'unavailable'


@pytest.mark.parametrize('phase', ['setup','call','teardown'])
def test_failed_phase_keeps_case_failed_without_relaxing_validator(phase):
    doc = document([('test_a',p,'failed' if p==phase else 'passed') for p in ('setup','call','teardown')],exitstatus=1)
    row = summarize_document(doc,{},'sha')
    assert row['status'] == 'failed' and row['counts']['failed'] == 1
    with pytest.raises(ValueError):
        validate(doc)


def test_collected_but_not_executed_is_not_a_pytest_skip():
    counts = count_cases(document([],nodes=('test_a','test_b')))
    assert counts['not_run'] == 2 and counts['skipped'] == 0
