"""Versioned observations; no estimated savings or automatic code changes."""
import json
from pathlib import Path

from tools.profiling.common import encoded
from tools.test_policy import PROJECT_ROOT

RULE_VERSION = 1


def source_kind(filename):
    path = Path(filename)
    for name, kind in (('src', 'product'), ('tests', 'test'), ('tools', 'test-tool')):
        try:
            path.relative_to(PROJECT_ROOT / name)
            return kind
        except ValueError:
            pass
    return 'framework-or-external'


def derive_findings(connection, measurement, mode):
    observations = []
    def add(rule, nodeid, phase, worker, evidence, limitation):
        observations.append((measurement, nodeid, phase, worker, encoded({
            'rule': rule, 'rule_version': RULE_VERSION, 'mode': mode,
            'measurement_id': measurement, 'evidence': evidence,
            'interpretation': 'candidate for investigation', 'limitation': limitation})))
    if mode == 'baseline':
        for phase in ('setup', 'call', 'teardown'):
            for nodeid, worker, duration in connection.execute(
                    'SELECT nodeid,worker,duration_s FROM phases WHERE measurement_id=? AND phase=? AND state=? AND duration_s IS NOT NULL ORDER BY duration_s DESC,nodeid LIMIT 20',
                    (measurement, phase, 'measured')):
                add('phase-duration', nodeid, phase, worker, {'duration_s': duration},
                    'Single unprofiled observation; setup, call and teardown must be compared separately.')
    elif mode == 'cprofile':
        rows = ((n,p,w,json.loads(d)) for n,p,w,d in connection.execute(
            'SELECT nodeid,phase,worker,data FROM python_functions WHERE measurement_id=?', (measurement,)))
        import heapq
        for nodeid, phase, worker, data in heapq.nlargest(20, rows, key=lambda r:r[3]['self_s']):
            add('python-function-time', nodeid, phase, worker, dict(data, source_kind=source_kind(data['file'])),
                'Instrumented cProfile interval with recorded backend thread scope; no thread-separated call paths or exclusive test cost. Cumulative values overlap and cannot be added as savings.')
    elif mode == 'memory':
        for nodeid, phase, worker, raw in connection.execute(
                'SELECT nodeid,phase,worker,data FROM memory_observations WHERE measurement_id=? LIMIT 2000', (measurement,)):
            data = json.loads(raw)
            add('python-memory', nodeid, phase, worker, data,
                'Python allocation peak and net delta only; neither native RSS nor proof of a leak.')
    elif mode == 'strace':
        rows = ((n,p,w,json.loads(d)) for n,p,w,d in connection.execute(
            'SELECT nodeid,phase,worker,data FROM syscalls WHERE measurement_id=?', (measurement,)))
        import heapq
        for nodeid, phase, worker, data in heapq.nlargest(20, rows, key=lambda r:r[3]['elapsed_ns']):
            add('syscall-wait', nodeid, phase, worker, data,
                'Elapsed syscall time includes blocking and tracing overhead; parallel processes overlap.')
    connection.executemany('INSERT INTO findings VALUES(?,?,?,?,?)', observations)
    return len(observations)
