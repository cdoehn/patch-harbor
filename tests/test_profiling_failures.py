"""Actual local failures preserve history and never become successful measurements."""
import os
import signal
import sqlite3
import subprocess
import sys
import time

import pytest

from tests.platform_support import PROJECT_ROOT
from tests.profiling_support import profile_cli, profile_run
from tools.profiling.storage import database


def seeded(path):
    with database(path, writable=True) as connection:
        with connection:
            connection.execute("INSERT INTO runs VALUES('old','earlier','done','complete','{}')")


def test_unknown_schema_and_locked_database_keep_previous_history(tmp_path):
    path = tmp_path / 'history.sqlite3'
    seeded(path)
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA user_version=999')
    before = path.read_bytes()
    result, _ = profile_cli('report', '--database', path)
    assert result.returncode != 0 and path.read_bytes() == before
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA user_version=1')
        connection.execute('BEGIN IMMEDIATE')
        test = tmp_path / 'test_unused.py'
        sentinel = tmp_path / 'executed'
        test.write_text(f'from pathlib import Path\ndef test_probe(): Path({str(sentinel)!r}).touch()\n')
        result, _ = profile_run(path, test)
        assert result.returncode != 0 and not sentinel.exists()
        connection.rollback()
        assert connection.execute('SELECT id FROM runs').fetchall() == [('old',)]


def test_database_full_rolls_back_transaction_without_erasing_previous_runs(tmp_path):
    path = tmp_path / 'history.sqlite3'
    seeded(path)
    with database(path, writable=True) as connection:
        pages = connection.execute('PRAGMA page_count').fetchone()[0]
        connection.execute(f'PRAGMA max_page_count={pages}')
        with pytest.raises(sqlite3.DatabaseError):
            with connection:
                connection.execute('INSERT INTO runs VALUES(?,?,?,?,?)', ('large','now',None,'running','x' * 1024 * 1024))
        assert connection.execute('SELECT id FROM runs').fetchall() == [('old',)]


def test_timeout_is_partial_and_keeps_a_queryable_previous_run(tmp_path):
    path = tmp_path / 'history.sqlite3'
    seeded(path)
    test = tmp_path / 'test_wait.py'
    test.write_text('import time\ndef test_wait(): time.sleep(30)\n')
    result, document = profile_run(path, test, '--timeout', '.2')
    assert result.returncode != 0 and document['status'] == 'partial'
    with database(path) as connection:
        assert connection.execute("SELECT status FROM runs WHERE id='old'").fetchone() == ('complete',)
        assert connection.execute("SELECT status,test_exit_code FROM measurements").fetchone() == ('partial', None)


@pytest.mark.skipif(os.name != 'posix', reason='native SIGINT process semantics')
def test_interrupted_controller_preserves_partial_measurement(tmp_path):
    database_path = tmp_path / 'history.sqlite3'
    sentinel = tmp_path / 'running'
    test = tmp_path / 'test_wait.py'
    test.write_text(f'from pathlib import Path\nimport time\ndef test_wait():\n Path({str(sentinel)!r}).touch()\n time.sleep(30)\n')
    command = [sys.executable, '-B', str(PROJECT_ROOT / 'tools/profile_tests.py'), 'run',
               '--database', str(database_path), '--workers', '2', '--warmups', '0',
               '--repetitions', '1', '--', str(test)]
    process = subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 20
        while not sentinel.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        assert sentinel.exists()
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 130, stdout + stderr
        with database(database_path) as connection:
            assert connection.execute('SELECT status FROM runs').fetchone() == ('interrupted',)
            assert connection.execute('SELECT status FROM measurements').fetchone() == ('interrupted',)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)


def test_read_only_report_import_never_imports_pytest_or_launches_work():
    code = f"import sys; sys.path.insert(0,{str(PROJECT_ROOT)!r}); import tools.profiling.application; assert 'pytest' not in sys.modules"
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
