"""Small explicitly invoked local diagnostic processes for Apply acceptance."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from tests.platform_support import PROJECT_ROOT
from tools.profiling.storage import database as profile_database


# Instrumented Python startup can exceed 30 seconds on a busy Windows runner.
# These are process budgets, not assertions about profiling performance.
PROFILE_TEST_TIMEOUT = 120
PROFILE_CLI_TIMEOUT = 180


def profile_cli(*arguments):
    environment = os.environ.copy()
    environment['PYTHONPATH'] = os.pathsep.join((str(PROJECT_ROOT), str(PROJECT_ROOT / 'src')))
    result = subprocess.run([sys.executable, '-B', str(PROJECT_ROOT / 'tools/profile_tests.py'),
                             *map(str, arguments)], cwd=PROJECT_ROOT, env=environment,
                            text=True, capture_output=True, timeout=PROFILE_CLI_TIMEOUT)
    try:
        document = json.loads(result.stdout)
    except ValueError:
        raise AssertionError(result.stdout + result.stderr) from None
    return result, document


def profile_run(database, test, *options):
    result, document = profile_cli('run', '--database', Path(database), '--workers', '2',
                                  '--warmups', '0', '--repetitions', '1',
                                  '--timeout', str(PROFILE_TEST_TIMEOUT), *options, '--', test)
    if result.returncode and isinstance(document.get('run_id'), str):
        diagnostics = profile_diagnostics(database, document['run_id'])
        result.stderr += '\nProfiling diagnostics: ' + json.dumps(diagnostics, sort_keys=True) + '\n'
    return result, document


def profile_diagnostics(path, run_id):
    """Read failure reasons without changing the result, history or exit code."""
    try:
        with profile_database(path) as connection:
            run = connection.execute('SELECT status,metadata FROM runs WHERE id=?', (run_id,)).fetchone()
            if run is None:
                return {'run_id': run_id, 'unavailable': 'run not found'}
            rows = connection.execute(
                'SELECT mode,iteration,status,test_exit_code,elapsed_s,details FROM measurements '
                'WHERE run_id=? ORDER BY mode,iteration LIMIT 16', (run_id,)).fetchall()
            measurements = []
            for mode, iteration, status, exit_code, elapsed, encoded in rows:
                details = json.loads(encoded)
                measurements.append({'mode': mode, 'iteration': iteration, 'status': status,
                                     'test_exit_code': exit_code, 'elapsed_s': elapsed,
                                     **{key: details.get(key) for key in
                                        ('reason', 'report_error', 'process_exit_code', 'artifact_directory')}})
            return {'run_id': run_id, 'status': run[0], 'tool_error': json.loads(run[1]).get('tool_error'),
                    'measurements': measurements}
    except (OSError, ValueError, sqlite3.Error) as exc:
        return {'run_id': run_id, 'unavailable': str(exc)}
