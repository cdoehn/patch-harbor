"""Bounded fair background summaries, independent from live/detail queries."""
from concurrent.futures import ThreadPoolExecutor
import time

from patchharbor.monitor_query import query_api


class OverviewRefresh:
    def __init__(self, timeout=10, interval=15):
        self.timeout, self.interval = timeout, interval
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='patchharbor-overview')
        self.entries, self.jobs = {}, set()

    def attach(self, document, *, force=False):
        rows = document.get('repositories', [])[:256]
        identities = {r['repo_id']: (r['path'], r.get('exchange'), r.get('archive')) for r in rows}
        self.entries = {key: entry for key, entry in self.entries.items()
                        if identities.get(key) == entry['identity']}
        for row in rows:
            if row.get('exchange') and row.get('registration') == 'ok':
                self.entries.setdefault(row['repo_id'], dict(identity=identities[row['repo_id']], value=None,
                                                            future=None, error=None, due=0))
        for entry in self.entries.values():
            future = entry['future']
            if future is not None and future.done():
                try:
                    entry.update(value=future.result(), error=None)
                except Exception as exc:
                    entry['error'] = str(exc)
                entry.update(future=None, due=time.monotonic() + self.interval)
            if force:
                entry['due'] = 0
        self.jobs = {future for future in self.jobs if not future.done()}
        for identity, entry in sorted(self.entries.items(), key=lambda item: item[1]['due']):
            if len(self.jobs) >= 2:
                break
            if entry['future'] is None and time.monotonic() >= entry['due']:
                entry['future'] = self.pool.submit(query_api, 'monitor_overview', {'repository': identity}, self.timeout)
                self.jobs.add(entry['future'])
        return {**document, 'repository_views': {key: {
            **(entry['value'] or {}), 'stale': bool(entry['error']) or bool((entry['value'] or {}).get('stale')),
            'error': entry['error'], 'refreshing': entry['future'] is not None}
            for key, entry in self.entries.items()}}

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def attach_overview_once(document, timeout):
    rows = [r for r in document.get('repositories', [])[:256] if r.get('exchange') and r.get('registration') == 'ok']
    def observe(row):
        try:
            return row['repo_id'], query_api('monitor_overview', {'repository': row['repo_id']}, timeout)
        except Exception as exc:
            return row['repo_id'], {'error': str(exc), 'stale': True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        return {**document, 'repository_views': dict(pool.map(observe, rows))}
