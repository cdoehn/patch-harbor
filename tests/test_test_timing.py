"""Timing provenance and real pytest outcomes; these are not timing benchmarks."""
from copy import deepcopy
import json
import os
from time import perf_counter_ns

import pytest

from tests.runner_support import example, invoke, make_suite
from tools.test_results import EvidenceError, equivalent, report_digest, validate
from tools.timing_model import case_timings, rank, read_telemetry


def measured_example():
    report = example()
    summary = dict(run_id=report['run_id'], binding=report['binding'], worker='serial',
                   observed_elapsed_ns=9_000_000_000, session_start_ns=0, fixtures=[])
    phases = [dict(nodeid=r['nodeid'], worker=r['worker'], phase=r['when'], outcome=r['outcome'],
                   subtest=False, duration_s=value, missing_reason=None, start_ns=0, end_ns=1)
              for r, value in zip(report['reports'], (4.8, .12, .3))]
    report['telemetry'] = dict(format_version=1, run_id=report['run_id'], binding=report['binding'],
                               status='complete', errors=[], phases=phases,
                               workers={}, missing_workers=[], controller=summary)
    return report


def test_default_ranking_means_call_and_never_total_or_fixture_time():
    report = measured_example()
    assert rank(report)[0]['duration_s'] == .12
    assert rank(report, phase='setup')[0]['duration_s'] == 4.8
    assert rank(report, phase='teardown')[0]['duration_s'] == .3
    assert case_timings(report)[0]['total_s'] == pytest.approx(5.22)
    for phase in ('total', 'fixture', 'cpu'):
        with pytest.raises(ValueError): rank(report, phase=phase)


@pytest.mark.parametrize('fault', ['run', 'binding', 'nan', 'negative', 'boolean', 'duplicate', 'unobserved', 'worker'])
def test_damaged_telemetry_is_not_used_and_cannot_rewrite_acceptance(fault):
    report = measured_example()
    original = deepcopy(report)
    digest = report_digest(report['reports'])
    data = report['telemetry']
    if fault == 'run': data['run_id'] = 'other'
    elif fault == 'binding': data['binding'] = {'source_sha256': 'other'}
    elif fault == 'duplicate': data['phases'].append(deepcopy(data['phases'][0]))
    elif fault == 'unobserved': data['phases'][0]['nodeid'] = 'not-collected'
    elif fault == 'worker': data['workers']['foreign'] = deepcopy(data['controller'])
    else: data['phases'][0]['duration_s'] = {'nan': float('nan'), 'negative': -1, 'boolean': True}[fault]
    with pytest.raises(ValueError): read_telemetry(report)
    assert report_digest(report['reports']) == digest
    equivalent(original, report)
    assert validate(report)


@pytest.mark.parametrize('outcome', ['failed', 'skipped'])
def test_no_call_after_setup_failure_or_skip_is_not_a_zero_measurement(outcome):
    report = measured_example()
    report['reports'] = [r for r in report['reports'] if r['when'] != 'call']
    report['reports'][0]['outcome'] = outcome
    data = report['telemetry']
    data['phases'] = [r for r in data['phases'] if r['phase'] != 'call']
    data['phases'][0]['outcome'] = outcome
    call = case_timings(report)[0]['phases']['call']
    assert call == dict(state='not_run', duration_s=None, outcome=None)
    assert rank(report) == []
    assert case_timings(report)[0]['total_s'] == pytest.approx(5.1)


def test_unobserved_phase_and_collection_only_are_distinct():
    report = measured_example()
    report['reports'].pop()
    report['telemetry']['phases'].pop()
    report['telemetry']['status'] = 'partial'
    case = case_timings(report)[0]
    assert case['total_s'] is None and case['phases']['teardown']['state'] == 'missing'
    report['mode'] = 'collection'
    report['reports'] = []
    report['telemetry']['phases'] = []
    assert all(v['state'] == 'not_run' for v in case_timings(report)[0]['phases'].values())


@pytest.mark.parametrize('workers', ['0', '2'])
def test_real_phase_boundaries_and_shared_fixture_are_separate(tmp_path, workers):
    suite = make_suite(tmp_path, '''
        import json
        import os
        from pathlib import Path
        import time
        import pytest

        def measured_sleep(seconds):
            start = time.perf_counter_ns()
            time.sleep(seconds)
            return (time.perf_counter_ns() - start) / 1e9

        @pytest.fixture(scope='module')
        def shared():
            observed = {'setup': measured_sleep(.02)}
            yield observed
            observed['teardown'] = measured_sleep(.03)
            path = Path(__file__).with_name(f'observed-{os.getpid()}.json')
            path.write_text(json.dumps(observed), encoding='utf-8')

        def test_first(shared): shared['call'] = measured_sleep(.04)
        def test_second(shared): pass
    ''')
    path = tmp_path / 'report.json'
    result = invoke(suite, path, workers=workers)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(path.read_text())
    data = read_telemetry(report)
    assert data['status'] == 'complete' and validate(report)
    cases = case_timings(report)
    assert len(cases) == 2
    first = next(c for c in cases if c['nodeid'].endswith('test_first'))
    # Sleep is only a workload. Its requested duration is not the clock oracle
    # (notably on Windows/Python 3.10); each pytest phase must enclose the
    # independently measured work that actually ran inside it.
    observed = [json.loads(p.read_text(encoding='utf-8')) for p in suite.glob('observed-*.json')]
    first_observations = [item for item in observed if 'call' in item]
    assert len(first_observations) == 1
    first_observed = first_observations[0]
    assert all(value > 0 for item in observed for value in item.values())
    assert first['phases']['setup']['duration_s'] >= first_observed['setup']
    assert first['phases']['call']['duration_s'] >= first_observed['call']
    summaries = list(data['workers'].values()) if workers != '0' else [data['controller']]
    fixtures = [f for summary in summaries for f in summary['fixtures'] if f['name'] == 'shared']
    assert len(fixtures) == 1 if workers == '0' else 1 <= len(fixtures) <= 2
    assert len(observed) == len(fixtures)
    assert sum(len(f['consumers']) for f in fixtures) == 2
    assert all(f['scope'] == 'module' and f['finalized_ns'] >= f['setup_end_ns']
               and f['teardown_s'] is None and f['teardown_reason'] for f in fixtures)
    assert sum(c['phases']['teardown']['duration_s'] for c in cases) >= sum(item['teardown'] for item in observed)
    assert all(c['total_s'] == pytest.approx(sum(v['duration_s'] for v in c['phases'].values())) for c in cases)
    assert data['controller']['observed_elapsed_ns'] > 0


def test_parametrized_scoped_fixtures_have_distinct_lifetimes_and_consumers(tmp_path):
    suite = make_suite(tmp_path, '''
        import pytest
        @pytest.fixture(scope='session')
        def shared(): return object()
        @pytest.fixture(scope='module', params=[1, 2])
        def value(request, shared): return request.param
        @pytest.fixture(scope='class')
        def group(): return object()
        class TestCases:
            def test_a(self, shared, value, group): assert value > 0
            def test_b(self, shared, value, group): assert value > 0
    ''')
    path = tmp_path / 'report.json'
    result = invoke(suite, path)
    assert result.returncode == 0, result.stdout + result.stderr
    data = read_telemetry(json.loads(path.read_text()))
    fixtures = data['controller']['fixtures']
    shared = [f for f in fixtures if f['name'] == 'shared']
    values = [f for f in fixtures if f['name'] == 'value']
    groups = [f for f in fixtures if f['name'] == 'group']
    assert len(shared) == 1 and len(shared[0]['consumers']) == 4
    assert len(values) == 2 and {f['parameter_index'] for f in values} == {0, 1}
    assert len({f['id'] for f in values}) == 2
    assert all(len(f['consumers']) == 2 for f in values)
    assert groups and all(f['scope'] == 'class' and f['finalized_ns'] is not None for f in groups)


@pytest.mark.parametrize('scenario', ['setup', 'teardown', 'skip', 'subtest'])
def test_real_failed_or_skipped_phases_retain_outcomes(tmp_path, scenario):
    body = "def test_probe(resource): pass\n"
    config = "import pytest\n@pytest.fixture\ndef resource():\n"
    if scenario == 'setup': config += " raise RuntimeError('setup')\n"
    elif scenario == 'teardown': config += " yield\n raise RuntimeError('teardown')\n"
    elif scenario == 'skip': config += " pytest.skip('skip setup')\n"
    else:
        body = "import unittest\nclass TestSub(unittest.TestCase):\n def test_sub(self):\n  with self.subTest(value=1): self.assertEqual(1,2)\n"
        config = ''
    suite = make_suite(tmp_path, body, config)
    path = tmp_path / 'report.json'
    result = invoke(suite, path, workers='2')
    assert (result.returncode == 0) == (scenario == 'skip')
    report = json.loads(path.read_text())
    data = read_telemetry(report)
    assert data['status'] == 'complete'
    case = case_timings(report)[0]
    if scenario in ('setup', 'skip'):
        assert case['phases']['call']['state'] == 'not_run' and not rank(report)
    if scenario == 'subtest':
        assert any(p['subtest'] for p in data['phases']) and len(rank(report)) == 1
    if scenario != 'skip':
        with pytest.raises(EvidenceError): validate(report)


@pytest.mark.parametrize('fault', ['crash', 'missing_timing', 'observer', 'publication'])
def test_partial_observation_never_changes_the_test_exit_status(tmp_path, fault):
    body = "def test_probe(): pass\n"
    config = ''
    if fault == 'crash': body = "import os\ndef test_probe(): os._exit(7)\n"
    elif fault == 'missing_timing':
        config = """
            import pytest
            @pytest.hookimpl(hookwrapper=True, trylast=True)
            def pytest_sessionfinish(session, exitstatus):
                yield
                if hasattr(session.config, 'workerinput'):
                    session.config.workeroutput.pop('ph_telemetry', None)
        """
    else:
        config = """
            from tools.timing_capture import TimingCapture
            def broken(*args, **kwargs): raise OSError('observer unavailable')
            TimingCapture.now = broken
        """
        if fault == 'publication':
            config = config.replace('TimingCapture.now = broken', 'TimingCapture.finish = broken')
    suite = make_suite(tmp_path, body, config)
    path = tmp_path / 'report.json'
    result = invoke(suite, path, workers='0' if fault in ('observer', 'publication') else '2')
    assert (result.returncode == 0) == (fault != 'crash'), result.stdout + result.stderr
    report = json.loads(path.read_text())
    data = read_telemetry(report)
    assert data['status'] == 'partial' and data['errors']
    if fault in ('crash', 'missing_timing'): assert data['missing_workers']
    if fault != 'crash': assert validate(report)


@pytest.mark.parametrize('workers', ['0', '2'])
@pytest.mark.parametrize('failing', [False, True])
def test_repeated_subtests_preserve_one_complete_parent_interval(tmp_path, workers, failing):
    suite = make_suite(tmp_path, """
        import unittest
        class TestSub(unittest.TestCase):
            def test_many(self):
                for value in range(3):
                    with self.subTest(value=value):
                        self.assertEqual(value, EXPECTED_VALUE)
    """.replace('EXPECTED_VALUE', '0' if failing else 'value'))
    path = tmp_path / 'report.json'
    result = invoke(suite, path, workers=workers)
    assert (result.returncode != 0) is failing, result.stdout + result.stderr
    report = json.loads(path.read_text())
    data = read_telemetry(report)
    assert data['status'] == 'complete' and data['errors'] == []
    children = [row for row in data['phases'] if row['subtest']]
    parents = [row for row in data['phases'] if not row['subtest']]
    assert len(children) == 3
    assert sum(row['outcome'] == 'failed' for row in children) == (2 if failing else 0)
    assert len(parents) == 3 and {row['phase'] for row in parents} == {'setup', 'call', 'teardown'}
    assert all(type(row['start_ns']) is int and type(row['end_ns']) is int
               and row['end_ns'] >= row['start_ns'] for row in parents)
    assert all(row['start_ns'] is None and row['end_ns'] is None for row in children)
    assert rank(report) == [next(row for row in parents if row['phase'] == 'call')]
    assert case_timings(report)[0]['total_s'] == pytest.approx(sum(row['duration_s'] for row in parents))
    if failing:
        with pytest.raises(EvidenceError): validate(report)
    else:
        assert validate(report)


@pytest.mark.parametrize('own_launcher', [False, True])
def test_startup_timing_is_bound_to_the_direct_launcher(tmp_path, monkeypatch, own_launcher):
    stamp = '2026-01-01T00:00:00+00:00'
    monkeypatch.setenv('PH_TEST_PROCESS_PARENT_PID', str(os.getpid()) if own_launcher else '-1')
    monkeypatch.setenv('PH_TEST_PROCESS_START_NS', str(perf_counter_ns()))
    monkeypatch.setenv('PH_TEST_PROCESS_START_UTC', stamp)
    suite = make_suite(tmp_path, 'def test_probe(): pass')
    path = tmp_path / 'report.json'
    result = invoke(suite, path)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(path.read_text())
    data = read_telemetry(report)
    assert validate(report) and data['status'] == 'complete'
    controller = data['controller']
    if own_launcher:
        assert controller['launch_to_registration_s'] >= 0
        assert controller['process_start_utc'] == stamp
    else:
        assert controller['launch_to_registration_s'] is None
        assert controller['process_start_utc'] is None
