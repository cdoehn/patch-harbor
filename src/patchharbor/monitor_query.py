"""Bounded child observations share the existing process-tree cleanup boundary."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import sys
import time

from patchharbor.output import ProcessOutputCapture
from patchharbor.platform import create_process_tree, ProcessState


class BoundedBuffer(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > 4 * 1024 * 1024:
            raise ValueError('monitor response exceeds four MiB')
        return super().write(data)


def query(repository, exchange, timeout, *, include_state=True):
    code = ('import json,sys; from patchharbor import api; '
            'args=json.loads(sys.argv[1]); '
            'print(json.dumps(api.monitor_snapshot(**args).document(),ensure_ascii=True))')
    command = [sys.executable, '-B', '-c', code,
               json.dumps({'repository': repository, 'exchange': exchange, 'include_state': include_state})]
    destination = BoundedBuffer()
    with create_process_tree(command, cwd=Path.cwd()) as process:
        capture = ProcessOutputCapture(process.output_stream, raw_output_stream=destination)
        capture.start()
        result = process.run(timeout_seconds=timeout)
        capture.finish()
    if result.state is not ProcessState.EXITED or result.return_code != 0:
        raise ValueError('observation failed or exceeded its query budget')
    return json.loads(destination.getvalue())


class MonitorRefresh:
    """One bounded child per source; never repeat an in-flight query."""
    def __init__(self, repository, exchange, *, interval=5, timeout=10, reader=query):
        self.repository, self.exchange = repository, exchange
        self.interval, self.timeout, self.reader = interval, timeout, reader
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='patchharbor-monitor')
        self.discovery = {'value': None, 'future': None, 'due': 0, 'error': None}
        self.sources = {}

    def _submit(self, entry, repo, *, include_state, force=False):
        if entry['future'] is None and (force or time.monotonic() >= entry['due']):
            entry['future'] = self.pool.submit(self.reader, repo, self.exchange, self.timeout, include_state=include_state)

    def _harvest(self, entry):
        future = entry['future']
        if future is None or not future.done():
            return False
        try:
            result = future.result()
            if result.get('errors'):
                raise ValueError('; '.join(result['errors']))
            if any(row.get('error') for row in result.get('repositories', [])) and entry is not self.discovery:
                raise ValueError('; '.join(row['error'] for row in result['repositories'] if row.get('error')))
            entry.update(value=result, error=None)
        except Exception as exc:
            entry['error'] = str(exc)
        entry.update(future=None, due=time.monotonic() + self.interval)
        return True

    def tick(self, force=False):
        discovered = self._harvest(self.discovery)
        if discovered and self.discovery['error'] is None:
            rows = self.discovery['value'].get('repositories', [])
            active = {r['repo_id']: r for r in rows}
            self.sources = {key: entry for key, entry in self.sources.items()
                            if key in active and entry['path'] == active[key]['path']}
            for key, row in active.items():
                self.sources.setdefault(key, {'value': None, 'future': None, 'due': 0, 'error': None, 'path': row['path']})
        self._submit(self.discovery, self.repository, include_state=False, force=force)
        for key, entry in self.sources.items():
            self._harvest(entry)
            self._submit(entry, key, include_state=True, force=force)

    @property
    def document(self):
        discovery = self.discovery['value'] or {'repositories': [], 'exchanges': [], 'errors': [], 'observed_at': 'lädt'}
        rows = []
        for row in discovery['repositories']:
            entry = self.sources.get(row['repo_id'], {})
            data = entry.get('value') or {}
            detail = next((r for r in data.get('repositories', []) if r['repo_id'] == row['repo_id'] and r['path'] == row['path']
                           and r.get('exchange') == row.get('exchange')), row)
            error = self.discovery['error'] or entry.get('error') or detail.get('error')
            rows.append({**detail, 'stale': bool(error), 'error': error,
                         'refreshing': entry.get('future') is not None})
        return {**discovery, 'repositories': rows, 'stale': bool(self.discovery['error']),
                'error': self.discovery['error'], 'refreshing': self.discovery['future'] is not None}

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def snapshot_once(repository, exchange, timeout):
    refresh = MonitorRefresh(repository, exchange, timeout=timeout)
    try:
        # Discovery and each selected repository are queried once. No repeat loop.
        try:
            discovery = query(repository, exchange, timeout, include_state=False)
            refresh.discovery['value'] = discovery
            refresh.discovery['error'] = '; '.join(discovery.get('errors', [])) or None
        except Exception as exc:
            refresh.discovery['error'] = str(exc)
            return refresh.document
        futures = {}
        for row in discovery['repositories']:
            entry = {'value': None, 'future': None, 'due': 0, 'error': None, 'path': row['path']}
            refresh.sources[row['repo_id']] = entry
            refresh._submit(entry, row['repo_id'], include_state=True, force=True)
            futures[row['repo_id']] = entry['future']
        for key, future in futures.items():
            try:
                future.result()
            except Exception:
                pass
            refresh._harvest(refresh.sources[key])
        return refresh.document
    finally:
        refresh.close()
