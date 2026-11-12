"""Semantic diagnostic summaries do not replace the strict release validator."""
import pytest

from scripts.summarize_ci_tests import count_cases, summarize_document, summarize, read_json, main
from tools.acceptance_catalog import LANES
from tools.test_results import validate


def document(rows, *, exitstatus=0, nodes=('test_a',)):
    return dict(format_version=2,run_id='run',binding={'source':'same'},expected_workers=0,
        mode='run',started=[],finished={},collections={'serial':list(nodes)},proofs={},
        collection_reports=[],reports=[dict(nodeid=n,when=p,outcome=o,reason='',xfail=False,subtest=None,worker='serial') for n,p,o in rows],
        errors=[],exitstatus=exitstatus)


def test_three_phases_count_as_one_passed_test_and_keep_missing_duration_unknown():
    doc = document([('test_a',p,'passed') for p in ('setup','call','teardown')])
    row = summarize_document(doc,{'commit':'a'*40,'binding':doc['binding']},'a'*40)
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


@pytest.mark.parametrize('outcome,state', [('skipped','xfail'),('passed','xpass')])
def test_expected_failure_does_not_become_successful_acceptance(outcome, state):
    doc = document([('test_a','setup','passed'),('test_a','call',outcome),('test_a','teardown','passed')])
    doc['reports'][1]['xfail'] = True
    assert count_cases(doc)[state] == 1
    with pytest.raises(ValueError):
        validate(doc)


def test_subtest_failure_counts_parent_once_and_collection_failures_are_separate():
    doc = document([('test_a',p,'passed') for p in ('setup','call','teardown')],exitstatus=1)
    doc['reports'].append(dict(doc['reports'][1],outcome='failed',subtest='case-1'))
    doc['collection_reports'] = [{'nodeid':'module.py','outcome':'failed'}]
    row = summarize_document(doc,None,'a'*40)
    assert row['counts']['failed'] == 1 and sum(row['counts'].values()) == 1
    assert row['collection_outcomes'] == {'failed':1}


def test_foreign_or_short_commit_cannot_get_a_bound_success():
    doc = document([('test_a',p,'passed') for p in ('setup','call','teardown')])
    for commit, build in [('short',{'commit':'short','binding':doc['binding']}),
                           ('a'*40,{'commit':'b'*40,'binding':doc['binding']})]:
        row = summarize_document(doc,build,commit)
        assert not row['commit_binding_verified'] and row['status']=='unbound'


def test_missing_and_invalid_reports_keep_unknown_counts_for_every_lane(tmp_path):
    for lane in LANES:
        result = summarize(tmp_path,lane.artifact,{'GITHUB_SHA':'a'*40})
        assert [r['suite'] for r in result['suites']] == list(lane.suites)
        assert all(r['status']=='missing' and r['counts'] is None for r in result['suites'])
    broken = tmp_path / 'patchharbor-core-tests.json'
    broken.write_text('{broken')
    result = summarize(tmp_path,LANES[0].artifact,{})
    assert result['suites'][0]['status']=='invalid' and broken.read_text()=='{broken'


@pytest.mark.parametrize('content', ['{"key":1,"key":2}', '{"key":NaN}', '[1,2]'])
def test_invalid_json_evidence_cannot_be_silently_normalized(tmp_path, content):
    path = tmp_path / 'report.json'
    path.write_text(content)
    with pytest.raises(ValueError):
        read_json(path)
    assert path.read_text()==content


def test_summary_output_failure_is_reported_without_mutating_reports(tmp_path):
    source = tmp_path / 'patchharbor-core-tests.json'
    source.write_text('{invalid')
    assert main(['--reports-dir',str(tmp_path),'--artifact',LANES[0].artifact,'--output',str(tmp_path)]) == 1
    assert source.read_text() == '{invalid'
