"""On-demand, per-viewer artifact and log refresh; no shared UI state."""
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import time

from patchharbor.monitor_query import query_api


class MonitorDetails:
    def __init__(self, *, timeout=10, interval=10):
        self.timeout, self.interval = timeout, interval
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='patchharbor-details')
        self.logs = OrderedDict()
        self.sources = {name: {'key': None, 'value': None, 'future': None, 'error': None, 'due': 0}
                        for name in ('artifacts', 'log')}

    def _tick(self, name, key, method, args, force):
        source = self.sources[name]
        future = source['future']
        if future is not None and future.done():
            try:
                source.update(value=future.result(), error=None)
                if name == 'log':
                    self.logs[source['key']] = (time.monotonic(), source['value'])
                    self.logs.move_to_end(source['key'])
                    while len(self.logs) > 8:
                        self.logs.popitem(last=False)
            except Exception as exc:
                source['error'] = str(exc)
            source.update(future=None, due=time.monotonic() + self.interval)
        if key != source['key'] and source['future'] is None:
            cached = self.logs.get(key) if name == 'log' else None
            if cached and time.monotonic() - cached[0] < 60:
                self.logs.move_to_end(key)
                source.update(key=key, value=cached[1], error=None, due=cached[0] + 60)
            else:
                source.update(key=key, value=None, error=None, due=0)
        if key == source['key'] and source['future'] is None and (force or time.monotonic() >= source['due']):
            source['future'] = self.pool.submit(query_api, method, args, self.timeout)
        if key != source['key']:
            return {'artifacts': [], 'text': '', 'refreshing': True}
        return {**(source['value'] or {}), 'stale': bool(source['error']) or (source['value'] or {}).get('stale', False),
                'error': source['error'], 'refreshing': source['future'] is not None}

    def attach(self, document, session, *, force=False):
        selected = session.selected(document)
        if not selected or session.view not in ('bundles', 'history', 'logs'):
            return document
        key = (selected['repo_id'], session.include_archive)
        artifacts = self._tick('artifacts', key, 'monitor_artifacts',
                              {'repository': key[0], 'include_archive': key[1]}, force)
        document = {**document, 'bundle_view': artifacts}
        artifact = session.selected_artifact(document)
        if session.view == 'logs' and artifact and artifact['kind'] == 'result_bundle' and not artifact.get('error'):
            log = self._tick('log', (artifact['path'], artifact['sha256']), 'monitor_log',
                             {'path': artifact['path'], 'expected_sha256': artifact['sha256']}, force)
            document['log_view'] = log
        return document

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def attach_once(document, session, timeout):
    selected = session.selected(document)
    if selected and session.view in ('bundles', 'history', 'logs'):
        document['bundle_view'] = query_api('monitor_artifacts',
            {'repository': selected['repo_id'], 'include_archive': session.include_archive}, timeout)
        row = session.selected_artifact(document)
        if session.view == 'logs' and row and row['kind'] == 'result_bundle' and not row.get('error'):
            document['log_view'] = query_api('monitor_log', {'path': row['path'], 'expected_sha256': row['sha256']}, timeout)
    return document
