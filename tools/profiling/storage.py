"""Local profiling storage; no implicit collection or network access."""
from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3

from tools.profiling.common import encoded, local_path
from tools.timing_model import case_timings, read_telemetry

APPLICATION_ID = 0x50485032
SCHEMA_VERSION = 1
MAX_ROWS = 250_000
KINDS = ('fixtures', 'fixture_uses', 'processes', 'python_functions', 'python_callers',
         'memory_observations', 'syscalls', 'findings')


def validate_database(connection):
    if connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
        raise ValueError('not a PatchHarbor profiling database')
    if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
        raise ValueError('unsupported profiling schema; existing history left untouched')
    if connection.execute('SELECT identity FROM schema_meta').fetchall() != [('patchharbor-local-profile',)]:
        raise ValueError('invalid profiling schema identity')
    if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
        raise ValueError('damaged profiling database')


@contextmanager
def database(path, *, writable=False):
    path = local_path(path)
    new = not path.exists()
    if new and not writable:
        raise ValueError('profiling database does not exist')
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    elif not path.is_file():
        raise ValueError('profiling database is not a regular file')
    connection = sqlite3.connect(path.as_uri() + ('?mode=rw' if writable else '?mode=ro'),
                                 uri=True, timeout=.5)
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        if new:
            connection.execute('PRAGMA journal_mode=DELETE')
            connection.execute('PRAGMA synchronous=FULL')
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                connection.execute(f'PRAGMA application_id={APPLICATION_ID}')
                connection.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
                connection.execute('CREATE TABLE schema_meta(identity TEXT NOT NULL)')
                connection.execute("INSERT INTO schema_meta VALUES('patchharbor-local-profile')")
                connection.execute('CREATE TABLE runs(id TEXT PRIMARY KEY, started TEXT NOT NULL, ended TEXT, status TEXT NOT NULL, metadata TEXT NOT NULL)')
                connection.execute('CREATE TABLE measurements(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), mode TEXT NOT NULL, iteration INTEGER NOT NULL, warmup INTEGER NOT NULL, status TEXT NOT NULL, test_exit_code INTEGER, elapsed_s REAL, details TEXT NOT NULL)')
                connection.execute('CREATE TABLE phases(measurement_id TEXT NOT NULL REFERENCES measurements(id), nodeid TEXT NOT NULL, worker TEXT, phase TEXT NOT NULL, state TEXT NOT NULL, outcome TEXT, duration_s REAL)')
                connection.execute('CREATE INDEX phase_lookup ON phases(measurement_id,nodeid,phase)')
                connection.execute('CREATE TABLE artifacts(measurement_id TEXT NOT NULL REFERENCES measurements(id), path TEXT NOT NULL, role TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL)')
                for name in KINDS:
                    connection.execute(f'CREATE TABLE {name}(measurement_id TEXT NOT NULL REFERENCES measurements(id), nodeid TEXT, phase TEXT, worker TEXT, data TEXT NOT NULL)')
                    connection.execute(f'CREATE INDEX {name}_lookup ON {name}(measurement_id,nodeid,phase)')
        validate_database(connection)
        if not writable:
            connection.execute('PRAGMA query_only=ON')
        yield connection
    finally:
        connection.close()


def store_report(connection, measurement, report, expected_binding):
    if report.get('binding') != expected_binding:
        raise ValueError('test report source binding changed')
    telemetry = read_telemetry(report)
    cases = case_timings(report)
    if len(cases) > MAX_ROWS:
        raise ValueError('too many observed tests')
    for case in cases:
        for phase, value in case['phases'].items():
            connection.execute('INSERT INTO phases VALUES(?,?,?,?,?,?,?)',
                (measurement, case['nodeid'], case['worker'], phase, value['state'], value['outcome'], value['duration_s']))
    summaries = list(telemetry['workers'].values())
    if telemetry['controller'] is not None:
        summaries.append(telemetry['controller'])
    for summary in summaries:
        connection.execute('INSERT INTO processes VALUES(?,?,?,?,?)',
            (measurement, None, None, summary['worker'], encoded(summary)))
        for fixture in summary['fixtures']:
            connection.execute('INSERT INTO fixtures VALUES(?,?,?,?,?)',
                (measurement, None, 'setup', summary['worker'], encoded(fixture)))
            for nodeid in fixture['consumers']:
                connection.execute('INSERT INTO fixture_uses VALUES(?,?,?,?,?)',
                    (measurement, nodeid, 'setup', summary['worker'], encoded({'fixture_id': fixture['id']})))
    return telemetry['status']
