"""Local profiling reporting; no implicit collection or network access."""
from __future__ import annotations

import json

from tools.profiling.storage import database
from tools.profiling.queries import load_run, rankings






def report_run(args):
    with database(args.database) as connection:
        result = load_run(connection, args.run)
        result['ranking'] = rankings(connection, result['run_id'], args.phase)[:args.top]
        result['ranking_mode'] = 'baseline'
        # Indexed row identities take precedence over duplicated payload fields.
        result['findings'] = [{**json.loads(d), 'nodeid': n, 'phase': p, 'worker': w} for n,p,w,d in connection.execute(
            'SELECT f.nodeid,f.phase,f.worker,f.data FROM findings f JOIN measurements m ON m.id=f.measurement_id WHERE m.run_id=? AND m.warmup=0 AND m.status=? AND m.mode=? AND (f.phase=? OR f.phase IS NULL) ORDER BY f.rowid LIMIT ?',
            (result['run_id'], 'complete', args.mode, args.phase, args.top))]
        result['fixtures'] = [{**json.loads(d), 'measurement_id': m, 'worker': w} for m,w,d in connection.execute(
            'SELECT f.measurement_id,f.worker,f.data FROM fixtures f JOIN measurements m ON m.id=f.measurement_id WHERE m.run_id=? AND m.mode=? AND m.warmup=0 ORDER BY f.rowid LIMIT 1000',
            (result['run_id'], args.mode))]
        result['finding_count'] = connection.execute(
            'SELECT count(*) FROM findings f JOIN measurements m ON m.id=f.measurement_id WHERE m.run_id=?', (result['run_id'],)).fetchone()[0]
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
        for key in ('host', 'selection', 'selection_sources', 'options', 'tool_version', 'dependencies', 'collector_sources'):
            if before['metadata'][key] != after['metadata'][key]:
                raise ValueError('incomparable run ' + key)
        worker_counts = []
        for info in (before, after):
            worker_counts.append(sorted(row[0] for row in connection.execute(
                'SELECT count(DISTINCT p.worker) FROM processes p JOIN measurements m ON m.id=p.measurement_id WHERE m.run_id=? AND m.mode=? AND m.warmup=0 AND m.status=? GROUP BY m.id',
                (info['run_id'], 'baseline', 'complete'))))
        if not worker_counts[0] or worker_counts[0] != worker_counts[1]:
            raise ValueError('incomparable observed worker counts')
        a, b = ({row['nodeid']: row for row in rankings(connection, r['run_id'], args.phase)} for r in (before, after))
        if not a or set(a) != set(b):
            raise ValueError('comparison needs the same measured baseline cases')
        rows = [{'nodeid': nodeid, 'phase': args.phase, 'before': a[nodeid], 'after': b[nodeid],
                 'difference_s': b[nodeid]['median_s'] - a[nodeid]['median_s'],
                 'ratio': b[nodeid]['median_s'] / a[nodeid]['median_s'] if a[nodeid]['median_s'] else None} for nodeid in sorted(a)]
        return {'before': before, 'after': after, 'comparisons': rows,
                'limitation': 'Observed baseline difference; no causal speedup or savings claim. No percentile estimate for small samples.',
                'comparison_scope': 'Same host, selection and selected sources, collectors, dependencies, options and observed worker counts; product revision may differ.'}
