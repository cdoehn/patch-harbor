"""Local profiling reporting; no implicit collection or network access."""
from __future__ import annotations

import json
import statistics

from tools.profiling.storage import database


def load_run(connection, identity):
    row = connection.execute('SELECT id,started,ended,status,metadata FROM runs ORDER BY rowid DESC LIMIT 1').fetchone() if identity == 'latest' else connection.execute('SELECT id,started,ended,status,metadata FROM runs WHERE id=?', (identity,)).fetchone()
    if row is None:
        raise ValueError('unknown profiling run')
    return dict(zip(('run_id', 'started', 'ended', 'status', 'metadata'), (*row[:4], json.loads(row[4]))))


def rankings(connection, identity, phase):
    groups = {}
    for nodeid, seconds in connection.execute('SELECT p.nodeid,p.duration_s FROM phases p JOIN measurements m ON m.id=p.measurement_id WHERE m.run_id=? AND m.mode=? AND m.warmup=0 AND m.status=? AND p.phase=? AND p.state=? AND p.duration_s IS NOT NULL',
                                              (identity, 'baseline', 'complete', phase, 'measured')):
        groups.setdefault(nodeid, []).append(seconds)
    return sorted(({'nodeid': key, 'phase': phase, 'samples': len(values), 'median_s': statistics.median(values),
                    'min_s': min(values), 'max_s': max(values)} for key, values in groups.items()),
                  key=lambda row: (-row['median_s'], row['nodeid']))


def report_run(args):
    with database(args.database) as connection:
        result = load_run(connection, args.run)
        result['ranking'] = rankings(connection, result['run_id'], args.phase)[:args.top]
        result['ranking_mode'] = 'baseline'
        result['findings'] = [dict(nodeid=n, phase=p, worker=w, **json.loads(d)) for n,p,w,d in connection.execute(
            'SELECT f.nodeid,f.phase,f.worker,f.data FROM findings f JOIN measurements m ON m.id=f.measurement_id WHERE m.run_id=? AND m.warmup=0 AND m.status=? AND m.mode=? AND (f.phase=? OR f.phase IS NULL) ORDER BY f.rowid LIMIT ?',
            (result['run_id'], 'complete', args.mode, args.phase, args.top))]
        result['coverage'] = {'startup': 'recorded where observable', 'subprocess_python_profiles': 'unobserved',
                              'native_memory': 'unobserved', 'fixture_teardown': 'unobserved; test teardown is measured'}
        result['artifacts'] = [dict(zip(('measurement_id','path','role','sha256','size','status'), row)) for row in connection.execute(
            'SELECT a.* FROM artifacts a JOIN measurements m ON m.id=a.measurement_id WHERE m.run_id=? ORDER BY a.rowid LIMIT 10000', (result['run_id'],))]

        result['measurements'] = [dict(zip(('id', 'mode', 'warmup', 'status', 'test_exit_code', 'elapsed_s', 'details'), (*row[:6], json.loads(row[6]))))
            for row in connection.execute('SELECT id,mode,warmup,status,test_exit_code,elapsed_s,details FROM measurements WHERE run_id=? ORDER BY rowid', (result['run_id'],))]
    return result


def compare_runs(args):
    with database(args.database) as connection:
        before, after = (load_run(connection, identity) for identity in (args.before, args.after))
        for run_info in (before, after):
            if run_info['status'] != 'complete':
                raise ValueError('comparison requires complete successful runs')
        for key in ('host', 'selection', 'options'):
            if before['metadata'][key] != after['metadata'][key]:
                raise ValueError('incomparable run ' + key)
        a, b = ({row['nodeid']: row for row in rankings(connection, r['run_id'], args.phase)} for r in (before, after))
        if not a or set(a) != set(b):
            raise ValueError('comparison needs the same measured baseline cases')
        rows = [{'nodeid': nodeid, 'phase': args.phase, 'before': a[nodeid], 'after': b[nodeid],
                 'difference_s': b[nodeid]['median_s'] - a[nodeid]['median_s']} for nodeid in sorted(a)]
        return {'before': before, 'after': after, 'comparisons': rows,
                'limitation': 'Observed baseline difference; no causal speedup or savings claim.'}
