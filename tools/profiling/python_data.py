"""Validate locally produced phase collector records before one-controller import."""
import json
import math

from tools.profiling.common import encoded


def import_python(connection, measurement, directory, mode, *, max_bytes=64 * 1024 * 1024):
    records = []
    consumed = 0
    for path in sorted(directory.glob('collector-*.json')):
        consumed += path.stat().st_size
        if consumed > max_bytes:
            raise ValueError('collector data byte budget exceeded')
        if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('unsafe or oversized collector record')
        row = json.loads(path.read_text(encoding='utf-8'))
        if row.get('format_version') != 1 or row.get('measurement_id') != measurement or row.get('mode') != mode:
            raise ValueError('foreign collector record')
        if row.get('status') != 'complete':
            raise ValueError('partial collector: ' + str(row.get('reason')))
        for key in ('start_ns', 'end_ns', 'start_utc_ns', 'end_utc_ns', 'pid', 'thread_id'):
            if type(row.get(key)) is not int or row[key] < 0:
                raise ValueError('invalid collector identity or timestamp')
        if row['end_ns'] < row['start_ns']:
            raise ValueError('reversed collector interval')
        records.append(row)
    if not records or len(records) > 20_000:
        raise ValueError('collector records missing or excessive')
    expected = set(connection.execute("SELECT nodeid,phase,worker FROM phases WHERE measurement_id=? AND state='measured'", (measurement,)))
    observed = [(row['nodeid'], row['phase'], row['worker']) for row in records if row['nodeid'] is not None]
    if len(set(observed)) != len(observed) or set(observed) != expected:
        raise ValueError('Python collector coverage differs from observed phases')
    imported = 0
    for row in records:
        prefix = (measurement, row['nodeid'], row['phase'], row['worker'])
        connection.execute('INSERT INTO processes VALUES(?,?,?,?,?)', (*prefix, encoded({k:v for k,v in row.items() if k not in ('functions','memory')})))
        if mode == 'cprofile':
            functions = row.get('functions')
            if not isinstance(functions, list) or len(functions) > 10_000:
                raise ValueError('invalid function inventory')
            for function in functions:
                imported += 1 + len(function.get('callers', []))
                if imported > 250_000:
                    raise ValueError('normalized profile row budget exceeded')
                for field in ('self_s','cumulative_s'):
                    if type(function.get(field)) not in (int,float) or not math.isfinite(function[field]) or function[field] < 0:
                        raise ValueError('invalid function time')
                connection.execute('INSERT INTO python_functions VALUES(?,?,?,?,?)', (*prefix, encoded({k:v for k,v in function.items() if k!='callers'})))
                for caller in function['callers']:
                    connection.execute('INSERT INTO python_callers VALUES(?,?,?,?,?)', (*prefix, encoded(dict(callee={k:function[k] for k in ('file','line','function')},caller=caller))))
        elif mode == 'memory':
            memory = row.get('memory')
            if not isinstance(memory, dict) or any(type(memory.get(k)) is not int for k in ('before','current','peak','net_bytes')):
                raise ValueError('invalid memory observation')
            connection.execute('INSERT INTO memory_observations VALUES(?,?,?,?,?)', (*prefix, encoded(memory)))
    return {'records': len(records), 'coverage': 'pytest processes and threads explicitly instrumented; other processes unknown'}
