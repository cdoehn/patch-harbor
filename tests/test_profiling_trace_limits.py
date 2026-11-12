"""Full-suite process inventories and explicit bounded strace import failures."""
from dataclasses import replace

import pytest

from tests.test_profiling_import_limits import seed
from tools.profiling.budgets import default_limits
from tools.profiling.storage import database
from tools.profiling.tracing import import_trace


def test_trace_accepts_more_than_old_process_file_limit(tmp_path):
    for pid in range(1, 4101):
        (tmp_path / f'trace.{pid}').write_text('1.000000 +++ exited with 0 +++\n')
    with database(tmp_path / 'measure.sqlite3', writable=True) as connection:
        seed(connection, [])
        with connection:
            result = import_trace(connection, 'measurement', tmp_path, max_bytes=1024**2)
        assert result['process_files'] == result['events'] == 4100
        assert connection.execute('SELECT count(*) FROM processes').fetchone() == (4100,)


@pytest.mark.parametrize('limited,diagnostic', [('trace_events','strace events'),
                                               ('trace_rows','normalized strace rows'),
                                               ('artifact_files','strace process files')])
def test_trace_limits_keep_specific_diagnostics_and_rollback(tmp_path, limited, diagnostic):
    for pid in (42, 43):
        (tmp_path / f'trace.{pid}').write_text('1.000000 +++ exited with 0 +++\n')
    with database(tmp_path / 'measure.sqlite3', writable=True) as connection:
        seed(connection, [])
        with pytest.raises(ValueError, match=diagnostic) as error:
            with connection:
                import_trace(connection, 'measurement', tmp_path, max_bytes=1024,
                             limits=replace(default_limits(), **{limited: 1}))
        assert 'observed=2, limit=1' in str(error.value)
        assert connection.execute('SELECT count(*) FROM processes').fetchone() == (0,)
        assert connection.execute('SELECT count(*) FROM syscalls').fetchone() == (0,)
