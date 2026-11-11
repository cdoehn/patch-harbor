"""Pure measurement readers; importing this module never loads pytest or Core."""
from __future__ import annotations

from collections import Counter
import math

PHASES = ('setup', 'call', 'teardown')
MAX_EVENTS = 250_000


def duration(value):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError('invalid timing duration')
    return float(value)


def _stamp(value, *, optional=False):
    if optional and value is None:
        return
    if type(value) is not int or value < 0:
        raise ValueError('invalid monotone timestamp')


def _worker_summary(value, worker, report):
    if (not isinstance(value, dict) or value.get('worker') != worker
            or value.get('run_id') != report.get('run_id') or value.get('binding') != report.get('binding')):
        raise ValueError('foreign worker timing')
    _stamp(value.get('observed_elapsed_ns'))
    _stamp(value.get('session_start_ns'), optional=True)
    fixtures = value.get('fixtures')
    if not isinstance(fixtures, list) or len(fixtures) > MAX_EVENTS:
        raise ValueError('invalid fixture inventory')
    seen = set()
    for fixture in fixtures:
        if (not isinstance(fixture, dict) or not isinstance(fixture.get('id'), str)
                or fixture['id'] in seen or fixture.get('worker') != worker
                or fixture.get('scope') not in ('session', 'package', 'module', 'class', 'function')
                or not isinstance(fixture.get('consumers'), list)
                or any(not isinstance(n, str) for n in fixture['consumers'])):
            raise ValueError('invalid fixture lifecycle')
        seen.add(fixture['id'])
        _stamp(fixture.get('setup_start_ns'))
        for key in ('setup_end_ns', 'finalized_ns'):
            _stamp(fixture.get(key), optional=True)
            if fixture.get(key) is not None and fixture[key] < fixture['setup_start_ns']:
                raise ValueError('reversed fixture lifecycle')
        if fixture.get('teardown_s') is not None:
            duration(fixture['teardown_s'])
        elif not fixture.get('teardown_reason'):
            raise ValueError('unknown fixture teardown lacks reason')


def read_telemetry(report):
    """Read timing independently of the strict successful-run validator."""
    data = report.get('telemetry')
    if (not isinstance(data, dict) or type(data.get('format_version')) is not int
            or data['format_version'] != 1):
        raise ValueError('missing or unsupported timing telemetry')
    if data.get('run_id') != report.get('run_id') or data.get('binding') != report.get('binding'):
        raise ValueError('timing belongs to another run or input')
    if data.get('status') not in ('complete', 'partial') or not isinstance(data.get('errors'), list):
        raise ValueError('invalid timing completeness')
    if not isinstance(data.get('phases'), list) or len(data['phases']) > MAX_EVENTS:
        raise ValueError('invalid timing event inventory')
    workers, missing = data.get('workers'), data.get('missing_workers')
    if not isinstance(workers, dict) or not isinstance(missing, list):
        raise ValueError('invalid timing worker inventory')
    if (set(workers) | set(missing) != set(report.get('started', []))
            or set(workers) & set(missing) or len(missing) != len(set(missing))):
        raise ValueError('timing worker inventory differs from observed workers')
    for worker, summary in workers.items():
        _worker_summary(summary, worker, report)
    if data.get('controller') is not None:
        _worker_summary(data['controller'], 'serial', report)
    elif data['status'] == 'complete':
        raise ValueError('complete timing lacks controller observation')
    if data['status'] == 'complete' and (missing or data['errors']):
        raise ValueError('complete timing contains missing data')
    seen = set()
    observed = Counter((r['worker'], r['nodeid'], r['when'], r['outcome'], r.get('subtest') is not None)
                       for r in report.get('reports', []))
    timings = Counter()
    for row in data['phases']:
        if (not isinstance(row, dict) or row.get('phase') not in PHASES
                or not isinstance(row.get('nodeid'), str) or not isinstance(row.get('worker'), str)
                or type(row.get('subtest')) is not bool
                or row.get('outcome') not in ('passed', 'failed', 'skipped')):
            raise ValueError('invalid timing phase')
        key = (row['worker'], row['nodeid'], row['phase'], row['outcome'], row['subtest'])
        timings[key] += 1
        if timings[key] > observed[key]:
            raise ValueError('timing has no matching observed phase')
        if row.get('duration_s') is not None:
            duration(row['duration_s'])
        elif not row.get('missing_reason'):
            raise ValueError('missing duration has no reason')
        if not row['subtest']:
            key = row['worker'], row['nodeid'], row['phase']
            if key in seen:
                raise ValueError('duplicate parent phase timing')
            seen.add(key)
        start, end = row.get('start_ns'), row.get('end_ns')
        if (start is None) != (end is None):
            raise ValueError('partial timing interval')
        if start is not None and (type(start) is not int or type(end) is not int or start < 0 or end < start):
            raise ValueError('invalid timing interval')
    if data['status'] == 'complete' and timings != observed:
        raise ValueError('complete timing omits observed phases')
    return data


def case_timings(report):
    """A missing phase is never silently replaced by a measured zero."""
    data = read_telemetry(report)
    grouped = {}
    for row in data['phases']:
        if not row['subtest']:
            grouped.setdefault((row['worker'], row['nodeid']), {})[row['phase']] = row
    collected = {nodeid for nodes in report.get('collections', {}).values() for nodeid in nodes}
    observed = {nodeid for _, nodeid in grouped}
    for nodeid in collected - observed:
        grouped[None, nodeid] = {}
    cases = []
    for (worker, nodeid), rows in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0] or '')):
        phases = {}
        for phase in PHASES:
            row = rows.get(phase)
            no_call = phase == 'call' and rows.get('setup', {}).get('outcome') in ('failed', 'skipped')
            state = ('measured' if row and row['duration_s'] is not None else
                     'not_run' if no_call or report.get('mode') == 'collection' else 'missing')
            phases[phase] = {'state': state, 'duration_s': row['duration_s'] if row else None,
                             'outcome': row['outcome'] if row else None}
        known = (all(value['state'] != 'missing' for value in phases.values())
                 and any(value['duration_s'] is not None for value in phases.values()))
        cases.append({'worker': worker, 'nodeid': nodeid, 'phases': phases,
                      'total_s': sum(value['duration_s'] or 0.0 for value in phases.values()) if known else None})
    return cases


def rank(report, *, phase='call', limit=10):
    """Default to test-body phases; exclude nested subtests from the ranking."""
    if phase not in PHASES or type(limit) is not int or limit < 1:
        raise ValueError('invalid phase ranking selection')
    data = read_telemetry(report)
    rows = [row for row in data['phases']
            if row['phase'] == phase and not row['subtest'] and row['duration_s'] is not None]
    return sorted(rows, key=lambda row: (-row['duration_s'], row['nodeid'], row['worker']))[:limit]
