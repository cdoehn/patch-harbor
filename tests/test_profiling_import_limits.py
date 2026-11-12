"""Large local collector records import incrementally and fail atomically."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from tools.profiling.budgets import default_limits
from tools.profiling.coverage import collector_coverage
from tools.profiling.python_data import import_python
from tools.profiling.storage import database


def function():
    return dict(file='test_probe.py', line=1, function='probe', primitive_calls=1,
                calls=1, self_s=.1, cumulative_s=.1, callers=[])


def record(nodeid):
    return dict(format_version=2, measurement_id='measurement', mode='cprofile',
                nodeid=nodeid, phase='call', worker='gw0', status='complete',
                coverage=collector_coverage('cprofile'), thread_id_role='boundary-observer',
                start_ns=1, end_ns=2, start_utc_ns=1, end_utc_ns=2, pid=1, thread_id=1,
                functions=[function()])


def seed(connection, nodeids):
    with connection:
        connection.execute("INSERT INTO runs VALUES('run','now',NULL,'running','{}')")
        connection.execute("INSERT INTO measurements VALUES('measurement','run','cprofile',0,0,'running',NULL,NULL,'{}')")
        connection.executemany("INSERT INTO phases VALUES('measurement',?,'gw0','call','measured','passed',.1)",
                               ((nodeid,) for nodeid in nodeids))


def test_record_above_old_bytes_and_function_limits_is_imported(tmp_path):
    row = record('test_a')
    row['functions'] = [dict(function(), function=f'probe_{i}') for i in range(10_001)]
    row['local_context'] = 'x' * (4 * 1024**2)
    (tmp_path / 'collector-a.json').write_text(json.dumps(row))
    with database(tmp_path / 'measure.sqlite3', writable=True) as connection:
        seed(connection, ['test_a'])
        with connection:
            result = import_python(connection, 'measurement', tmp_path, 'cprofile')
        assert result['records'] == 1 and result['normalized_rows'] == 10_001
        assert connection.execute('SELECT count(*) FROM python_functions').fetchone() == (10_001,)


def test_import_writes_each_record_before_reading_the_next(tmp_path, monkeypatch):
    for name in ('a', 'b'):
        (tmp_path / f'collector-{name}.json').write_text(json.dumps(record('test_' + name)))
    with database(tmp_path / 'measure.sqlite3', writable=True) as connection:
        seed(connection, ['test_a', 'test_b'])
        read_text = Path.read_text

        def read(path, *args, **kwargs):
            if path.name == 'collector-b.json':
                assert connection.execute('SELECT count(*) FROM python_functions').fetchone() == (1,)
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'read_text', read)
        with connection:
            assert import_python(connection, 'measurement', tmp_path, 'cprofile')['records'] == 2


@pytest.mark.parametrize('failure', ['rows', 'duplicate', 'missing', 'foreign'])
def test_late_import_failure_rolls_back_all_new_profile_rows(tmp_path, failure):
    (tmp_path / 'collector-a.json').write_text(json.dumps(record('test_a')))
    second = record('test_a' if failure == 'duplicate' else 'test_b')
    if failure == 'foreign':
        second['measurement_id'] = 'elsewhere'
    if failure != 'missing':
        (tmp_path / 'collector-b.json').write_text(json.dumps(second))
    budget = replace(default_limits(), profile_rows=1) if failure == 'rows' else default_limits()
    with database(tmp_path / 'measure.sqlite3', writable=True) as connection:
        seed(connection, ['test_a', 'test_b'])
        with pytest.raises(ValueError):
            with connection:
                import_python(connection, 'measurement', tmp_path, 'cprofile', limits=budget)
        assert connection.execute('SELECT count(*) FROM python_functions').fetchone() == (0,)
        assert connection.execute('SELECT count(*) FROM processes').fetchone() == (0,)
        assert connection.execute('SELECT count(*) FROM phases').fetchone() == (2,)
