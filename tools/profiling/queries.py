"""Read-only baseline query model, independent of CLI presentation."""
import json
import statistics


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
