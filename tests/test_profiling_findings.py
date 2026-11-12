"""Compare evidence under controlled input changes; never assert speed thresholds."""
import json
from types import SimpleNamespace

import pytest

from tools.profiling.findings import derive_findings
from tools.profiling.reporting import compare_runs, report_run
from tools.profiling.queries import rankings
from tools.profiling.storage import database


def seeded_history(path):
    metadata = {name: {} for name in ('host','selection_sources','options','dependencies','collector_sources')}
    metadata.update(selection=['test.py::test_a'],tool_version=1,binding={'source':'version-a'})
    with database(path, writable=True) as connection, connection:
        for identity, value in (('before', 2.), ('after', 1.)):
            connection.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (identity,'start','end','complete',json.dumps(metadata)))
            for mode, warmup, seconds in (('baseline',0,value),('baseline',1,200.),('cprofile',0,100.)):
                measurement = identity + mode + str(warmup)
                connection.execute('INSERT INTO measurements VALUES(?,?,?,?,?,?,?,?,?)',
                    (measurement,identity,mode,0,warmup,'complete',0,seconds,'{}'))
                for phase, duration in (('setup',seconds*3),('call',seconds),('teardown',seconds/2)):
                    connection.execute('INSERT INTO phases VALUES(?,?,?,?,?,?,?)',
                        (measurement,'test.py::test_a','gw0',phase,'measured','passed',duration))
                connection.execute('INSERT INTO processes VALUES(?,?,?,?,?)', (measurement,None,None,'gw0','{}'))


def comparison_args(path):
    return SimpleNamespace(database=path, before='before', after='after', phase='call')


@pytest.mark.parametrize('duplicate_identity', [False, True])
def test_report_preserves_payloads_and_uses_row_identity_read_only(tmp_path, duplicate_identity):
    path = tmp_path / 'measure.sqlite3'
    seeded_history(path)
    fixture = {'id': 'fixture-1', 'scope': 'session', 'setup_s': 0.5}
    finding = {'kind': 'slow-call', 'value': 2.0}
    if duplicate_identity:
        fixture.update(measurement_id='other-measurement', worker='other-worker')
        finding.update(nodeid='other-test', phase='setup', worker='other-worker')
    with database(path, writable=True) as connection, connection:
        connection.execute('INSERT INTO fixtures VALUES(?,?,?,?,?)',
            ('beforebaseline0', None, 'setup', 'gw0', json.dumps(fixture)))
        connection.execute('INSERT INTO findings VALUES(?,?,?,?,?)',
            ('beforebaseline0', 'test.py::test_a', 'call', 'gw0', json.dumps(finding)))
    before = path.read_bytes()
    result = report_run(SimpleNamespace(database=path, run='before', mode='baseline', phase='call', top=10))
    assert result['fixtures'] == [{'id': 'fixture-1', 'scope': 'session', 'setup_s': 0.5,
                                   'measurement_id': 'beforebaseline0', 'worker': 'gw0'}]
    assert result['findings'] == [{'kind': 'slow-call', 'value': 2.0,
                                   'nodeid': 'test.py::test_a', 'phase': 'call', 'worker': 'gw0'}]
    assert path.read_bytes() == before


def test_warmups_profiles_and_preparation_cannot_inflate_baseline_rankings(tmp_path):
    path = tmp_path / 'measure.sqlite3'
    seeded_history(path)
    with database(path) as connection:
        call = rankings(connection,'before','call')[0]
        setup = rankings(connection,'before','setup')[0]
        assert call['samples'] == 1 and call['median_s'] == 2.
        assert setup['median_s'] == 6.
    result = compare_runs(comparison_args(path))
    assert result['comparisons'][0]['difference_s'] == -1.
    assert result['comparisons'][0]['ratio'] == .5
    assert 'estimated_savings' not in result


@pytest.mark.parametrize('key', ['host','selection_sources','options','dependencies','collector_sources'])
def test_comparison_rejects_changed_measurement_conditions(tmp_path, key):
    path = tmp_path / 'measure.sqlite3'
    seeded_history(path)
    with database(path, writable=True) as connection, connection:
        data = json.loads(connection.execute("SELECT metadata FROM runs WHERE id='after'").fetchone()[0])
        data[key] = {'changed': True}
        connection.execute("UPDATE runs SET metadata=? WHERE id='after'", (json.dumps(data),))
    with pytest.raises(ValueError, match='incomparable'):
        compare_runs(comparison_args(path))


def test_findings_retain_measurement_and_phase_without_counting_subphases_twice(tmp_path):
    path = tmp_path / 'measure.sqlite3'
    seeded_history(path)
    with database(path, writable=True) as connection, connection:
        assert derive_findings(connection, 'beforebaseline0', 'baseline') == 3
        rows = connection.execute('SELECT phase,data FROM findings').fetchall()
        assert {phase for phase,_ in rows} == {'setup','call','teardown'}
        assert all(json.loads(raw)['measurement_id']=='beforebaseline0' for _,raw in rows)
        assert all(json.loads(raw)['rule_version']==1 for _,raw in rows)


def test_product_change_can_compare_but_worker_change_cannot(tmp_path):
    path = tmp_path / 'measure.sqlite3'
    seeded_history(path)
    with database(path, writable=True) as connection, connection:
        data = json.loads(connection.execute("SELECT metadata FROM runs WHERE id='after'").fetchone()[0])
        data['binding'] = {'source':'version-b'}
        connection.execute("UPDATE runs SET metadata=? WHERE id='after'", (json.dumps(data),))
    assert compare_runs(comparison_args(path))['comparisons']
    with database(path, writable=True) as connection, connection:
        connection.execute('INSERT INTO processes VALUES(?,?,?,?,?)', ('afterbaseline0',None,None,'gw1','{}'))
    with pytest.raises(ValueError, match='worker counts'):
        compare_runs(comparison_args(path))
