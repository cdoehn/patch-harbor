"""Real phase-specific Python diagnostics, with no speed or RSS assertions."""
import json

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
