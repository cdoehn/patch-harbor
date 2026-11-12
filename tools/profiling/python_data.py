"""Validate locally produced phase collector records before one-controller import."""
import json

from tools.profiling.common import encoded
from tools.profiling.coverage import collector_coverage
from tools.profiling.profiles import validate_function
from tools.profiling.budgets import default_limits, require_budget


def import_python(connection, measurement, directory, mode, *, max_bytes=None, limits=None):
    limits = default_limits() if limits is None else limits
    max_bytes = limits.artifact_bytes if max_bytes is None else max_bytes
    expected = set(connection.execute("SELECT nodeid,phase,worker FROM phases WHERE measurement_id=? AND state='measured'", (measurement,)))
    observed = set()
    consumed = imported = records = 0
    # The controller owns the transaction. Retain identities, not every parsed
    # function and caller from the full suite, and roll back on any incomplete input.
    for path in sorted(directory.glob('collector-*.json')):
        if path.is_symlink() or not path.is_file():
            raise ValueError('unsafe collector record')
        consumed += path.stat().st_size
        require_budget('collector data bytes', consumed, max_bytes, '--max-bytes')
        require_budget('collector record bytes', path.stat().st_size, limits.record_bytes)
        records += 1
        require_budget('collector records', records, limits.collector_records)
        row = json.loads(path.read_text(encoding='utf-8'))
        if row.get('format_version') != 2 or row.get('measurement_id') != measurement or row.get('mode') != mode:
            raise ValueError('foreign collector record')
        if row.get('coverage') != collector_coverage(mode) or row.get('thread_id_role') != 'boundary-observer':
            raise ValueError('missing or inconsistent collector coverage')
        if row.get('status') != 'complete':
            raise ValueError('partial collector: ' + str(row.get('reason')))
        for key in ('start_ns', 'end_ns', 'start_utc_ns', 'end_utc_ns', 'pid', 'thread_id'):
            if type(row.get(key)) is not int or row[key] < 0:
                raise ValueError('invalid collector identity or timestamp')
        if row['end_ns'] < row['start_ns']:
            raise ValueError('reversed collector interval')
        if row['nodeid'] is not None:
            identity = row['nodeid'], row['phase'], row['worker']
            if identity not in expected or identity in observed:
                raise ValueError('Python collector coverage differs from observed phases')
            observed.add(identity)
        prefix = (measurement, row['nodeid'], row['phase'], row['worker'])
        connection.execute('INSERT INTO processes VALUES(?,?,?,?,?)', (*prefix, encoded({k:v for k,v in row.items() if k not in ('functions','memory')})))
        if mode == 'cprofile':
            functions = row.get('functions')
            if not isinstance(functions, list):
                raise ValueError('invalid function inventory')
            require_budget('functions per record', len(functions), limits.functions)
            for function in functions:
                validate_function(function, max_callers=limits.callers)
                imported += 1 + len(function.get('callers', []))
                require_budget('normalized profile rows', imported, limits.profile_rows)
                connection.execute('INSERT INTO python_functions VALUES(?,?,?,?,?)', (*prefix, encoded(dict({k:v for k,v in function.items() if k!='callers'}, coverage=row['coverage']))))
                for caller in function['callers']:
                    connection.execute('INSERT INTO python_callers VALUES(?,?,?,?,?)', (*prefix, encoded(dict(callee={k:function[k] for k in ('file','line','function')},caller=caller,coverage=row['coverage']))))
        elif mode == 'memory':
            memory = row.get('memory')
            if not isinstance(memory, dict) or any(type(memory.get(k)) is not int for k in ('before','current','peak','net_bytes')):
                raise ValueError('invalid memory observation')
            connection.execute('INSERT INTO memory_observations VALUES(?,?,?,?,?)', (*prefix, encoded(memory)))
    if not records or observed != expected:
        raise ValueError('Python collector coverage differs from observed phases or records are missing')
    return {'records': records, 'normalized_rows': imported,
            'coverage': 'Observer intervals only; function rows retain backend thread scope, with no per-thread or exclusive-test ownership'}
