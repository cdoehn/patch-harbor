"""Real phase-specific Python diagnostics, with no speed or RSS assertions."""
import json
import sys

import pytest

from tests.profiling_support import profile_run
from tools.profiling.storage import database


@pytest.mark.parametrize('mode', ['cprofile','memory'])
def test_explicit_python_collector_covers_all_test_phases(tmp_path, mode):
    test = tmp_path / 'test_cpu_memory.py'
    test.write_text('import pytest\n@pytest.fixture\ndef resource():\n value=bytearray(32000)\n yield value\n value.clear()\ndef compute(): return sum(i*i for i in range(2000))\ndef test_compute(resource): assert compute()>0 and len(resource)==32000\n')
    path = tmp_path / 'history.sqlite3'
    result, response = profile_run(path, test, '--modes', mode)
    assert result.returncode == 0, result.stdout + result.stderr
    assert response['status'] == 'complete'
    with database(path) as connection:
        table = 'python_functions' if mode == 'cprofile' else 'memory_observations'
        rows = connection.execute(f'SELECT nodeid,phase,data FROM {table} WHERE nodeid IS NOT NULL').fetchall()
        assert {phase for _,phase,_ in rows} == {'setup','call','teardown'}
        if mode == 'cprofile':
            assert any(phase=='call' and json.loads(data)['function']=='compute' for _,phase,data in rows)
            assert connection.execute("SELECT count(*) FROM artifacts WHERE role LIKE 'python-%.prof'").fetchone()[0] > 0
        else:
            assert all(json.loads(data)['unit']=='bytes' for _,_,data in rows)
            assert any(phase=='setup' and json.loads(data)['peak'] > 0 for _,phase,data in rows)
        assert connection.execute('SELECT count(*) FROM python_functions' if mode=='memory' else 'SELECT count(*) FROM memory_observations').fetchone() == (0,)


def test_python_thread_and_child_coverage_is_explicit(tmp_path):
    test = tmp_path / 'test_process.py'
    test.write_text('import subprocess,sys,threading\ndef background_only(): return sum(range(2000))\ndef owner_only(): return sum(range(1000))\ndef test_process():\n assert owner_only()>0\n thread=threading.Thread(target=background_only)\n thread.start()\n thread.join()\n subprocess.run([sys.executable,"-c","def child_only(): return 3\\nassert child_only()==3"],check=True)\n')
    path = tmp_path / 'history.sqlite3'
    result, _ = profile_run(path, test, '--modes', 'cprofile')
    assert result.returncode == 0, result.stdout + result.stderr
    with database(path) as connection:
        functions = [json.loads(r[0])['function'] for r in connection.execute('SELECT data FROM python_functions')]
        assert 'owner_only' in functions and 'child_only' not in functions
        if sys.implementation.name == 'cpython' and (3, 10) <= sys.version_info[:2] <= (3, 14):
            assert ('background_only' in functions) is (sys.version_info >= (3, 12))
        rows = [json.loads(r[0]) for r in connection.execute("SELECT data FROM processes WHERE phase='call'")]
        assert rows and all(r['coverage']['children']=='unobserved' for r in rows)
        assert all(r['coverage']['python_thread_attribution']=='not-separated' and r['coverage']['test_exclusive'] is False for r in rows)
        assert all(r['thread_id_role']=='boundary-observer' and r['coverage']['phase_attribution']=='observer-interval' for r in rows)
        if sys.implementation.name == 'cpython' and (3, 10) <= sys.version_info[:2] <= (3, 14):
            assert all(r['coverage']['python_threads']==('interpreter' if sys.version_info >= (3, 12) else 'current') for r in rows)
        observed = [json.loads(r[0]) for r in connection.execute("SELECT data FROM python_functions WHERE phase='call'")]
        assert observed and all(r['coverage']['test_exclusive'] is False for r in observed)
        assert all(r['serialization_preparation_ns'] >= 0 and r['end_process_cpu_ns'] >= r['start_process_cpu_ns'] for r in rows)


def test_foreign_tracemalloc_session_is_not_stopped_or_claimed(tmp_path, monkeypatch):
    monkeypatch.setenv('PYTHONTRACEMALLOC', '1')
    test = tmp_path / 'test_existing_memory.py'
    test.write_text('import tracemalloc\ndef test_probe(): assert tracemalloc.is_tracing()\n')
    path = tmp_path / 'history.sqlite3'
    result, document = profile_run(path, test, '--modes', 'memory', '--timeout', '60')
    assert result.returncode != 0 and document['status'] == 'partial'
    with database(path) as connection:
        assert connection.execute('SELECT test_exit_code FROM measurements').fetchone() == (0,)
        assert connection.execute('SELECT count(*) FROM memory_observations').fetchone() == (0,)
