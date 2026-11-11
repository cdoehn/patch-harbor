"""Small explicitly invoked local diagnostic processes for Apply acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys

from tests.platform_support import PROJECT_ROOT


def profile_cli(*arguments):
    environment = os.environ.copy()
    environment['PYTHONPATH'] = os.pathsep.join((str(PROJECT_ROOT), str(PROJECT_ROOT / 'src')))
    result = subprocess.run([sys.executable, '-B', str(PROJECT_ROOT / 'tools/profile_tests.py'),
                             *map(str, arguments)], cwd=PROJECT_ROOT, env=environment,
                            text=True, capture_output=True, timeout=90)
    try:
        document = json.loads(result.stdout)
    except ValueError:
        raise AssertionError(result.stdout + result.stderr) from None
    return result, document


def profile_run(database, test, *options):
    return profile_cli('run', '--database', Path(database), '--workers', '2',
                       '--warmups', '0', '--repetitions', '1', '--timeout', '30', *options, '--', test)
