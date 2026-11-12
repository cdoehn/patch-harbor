"""Local persistence and phase data; no benchmark thresholds or remote actions."""
import json
import sqlite3

from tests.profiling_support import profile_cli, profile_run
from tools.profiling.storage import database


def test_two_local_runs_preserve_history_and_separate_phase_records(tmp_path):
    test = tmp_path / 'test_local.py'
    test.write_text('import pytest\n@pytest.fixture\ndef resource():\n yield [1,2,3]\ndef test_example(resource): assert sum(resource)==6\n')
    path = tmp_path / 'history.sqlite3'
    first, a = profile_run(path, test)
    assert first.returncode == 0, first.stdout + first.stderr
    second, b = profile_run(path, test)
    assert second.returncode == 0, second.stdout + second.stderr
    assert a['run_id'] != b['run_id']
    with database(path) as connection:
        assert connection.execute('SELECT count(*) FROM runs').fetchone() == (2,)
        assert connection.execute('SELECT count(*) FROM measurements').fetchone() == (2,)
        assert set(row[0] for row in connection.execute('SELECT DISTINCT phase FROM phases')) == {'setup','call','teardown'}
        assert connection.execute('SELECT count(*) FROM phases WHERE duration_s IS NULL').fetchone() == (0,)
        assert connection.execute('SELECT count(*) FROM artifacts').fetchone()[0] >= 4
        fixture_rows = connection.execute(
            'SELECT f.measurement_id,f.worker,f.data FROM fixtures f JOIN measurements m ON m.id=f.measurement_id WHERE m.run_id=? ORDER BY f.rowid',
            (a['run_id'],)).fetchall()
        assert fixture_rows
    before = path.read_bytes()
    shown, report = profile_cli('report', '--database', path, '--run', a['run_id'])
    assert shown.returncode == 0 and report['ranking'][0]['phase'] == 'call'
    assert len(report['fixtures']) == len(fixture_rows)
    for fixture, (measurement, worker, raw) in zip(report['fixtures'], fixture_rows):
        stored = json.loads(raw)
        assert fixture['measurement_id'] == measurement
        assert fixture['worker'] == worker == stored['worker']
        assert all(fixture[key] == value for key, value in stored.items())
    compared, comparison = profile_cli('compare', '--database', path, '--before', a['run_id'], '--after', b['run_id'])
    assert compared.returncode == 0 and len(comparison['comparisons']) == 1
    assert path.read_bytes() == before


def test_failed_test_is_retained_without_becoming_tool_success(tmp_path):
    test = tmp_path / 'test_failed.py'
    test.write_text('def test_failure(): assert False\n')
    path = tmp_path / 'history.sqlite3'
    result, response = profile_run(path, test)
    assert result.returncode == 1 and response['status'] == 'failed'
    with database(path) as connection:
        assert connection.execute('SELECT test_exit_code,status FROM measurements').fetchone() == (1,'complete')
        assert connection.execute("SELECT outcome FROM phases WHERE phase='call'").fetchone() == ('failed',)


def test_explicit_selection_and_read_only_missing_database(tmp_path):
    path = tmp_path / 'absent.sqlite3'
    result, response = profile_cli('run', '--database', path)
    assert result.returncode != 0 and response['status'] == 'error' and not path.exists()
    result, _ = profile_cli('report', '--database', path)
    assert result.returncode != 0 and not path.exists()


def test_foreign_database_is_not_replaced(tmp_path):
    path = tmp_path / 'foreign.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE important(value TEXT)')
        connection.execute("INSERT INTO important VALUES('preserve')")
    before = path.read_bytes()
    result, response = profile_cli('report', '--database', path)
    assert result.returncode != 0 and response['status'] == 'error'
    assert path.read_bytes() == before
    assert json.loads(result.stdout)['error']
