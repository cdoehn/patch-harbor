"""Normalized Python profile values, independent of pytest and persistence."""
import math


def validate_function(row):
    if not isinstance(row, dict) or not isinstance(row.get('file'), str) or not isinstance(row.get('function'), str):
        raise ValueError('invalid profile source identity')
    for field in ('line', 'primitive_calls', 'calls'):
        if type(row.get(field)) is not int or row[field] < 0:
            raise ValueError('invalid profile count or source line')
    if row['primitive_calls'] > row['calls']:
        raise ValueError('primitive calls exceed total calls')
    for field in ('self_s','cumulative_s'):
        if type(row.get(field)) not in (int,float) or not math.isfinite(row[field]) or row[field] < 0:
            raise ValueError('invalid function time')
    callers = row.get('callers')
    if not isinstance(callers, list) or len(callers) > 10_000:
        raise ValueError('invalid caller inventory')
    for caller in callers:
        if not isinstance(caller, dict) or not isinstance(caller.get('file'), str) or not isinstance(caller.get('function'), str) or type(caller.get('line')) is not int:
            raise ValueError('invalid caller source')
        metrics = caller.get('metrics')
        if not isinstance(metrics, (list,tuple)) or len(metrics) != 4:
            raise ValueError('unsupported pstats caller tuple')
        if any(type(value) not in (int,float) or not math.isfinite(value) or value < 0 for value in metrics):
            raise ValueError('invalid pstats caller values')
    return row


def function_rows(stats, limit=10_000):
    functions = []
    for (file,line,name), (primitive,calls,own,cumulative,callers) in stats.items():
        row = dict(file=file,line=line,function=name,primitive_calls=primitive,calls=calls,
                   self_s=own,cumulative_s=cumulative,
                   callers=[dict(file=k[0],line=k[1],function=k[2],metrics=v) for k,v in callers.items()])
        functions.append(validate_function(row))
    return sorted(functions,key=lambda r:(-r['self_s'],r['file'],r['line']))[:limit], len(functions)>limit


def memory_record(before, current, peak, differences):
    if any(type(value) is not int or value < 0 for value in (before,current,peak)) or peak < current:
        raise ValueError('invalid Python memory counters')
    return dict(method='tracemalloc',unit='bytes',before=before,current=current,peak=peak,
        net_bytes=current-before,
        scope='Python allocations since explicit plugin start; peak includes earlier live objects; native memory and RSS unknown',
        differences=[dict(size_diff=d.size_diff,count_diff=d.count_diff,
            traceback=[dict(file=f.filename,line=f.lineno) for f in d.traceback]) for d in differences[:200]],
        differences_truncated=len(differences)>200)
