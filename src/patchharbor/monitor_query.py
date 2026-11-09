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


def query(repository, exchange, timeout):
    code = ('import json,sys; from patchharbor import api; '
            'args=json.loads(sys.argv[1]); '
            'print(json.dumps(api.monitor_snapshot(**args).document(),ensure_ascii=True))')
    command = [sys.executable, '-B', '-c', code,
               json.dumps({'repository': repository, 'exchange': exchange})]
    destination = BytesIO()
    with create_process_tree(command, cwd=Path.cwd()) as process:
        capture = ProcessOutputCapture(process.output_stream, raw_output_stream=destination)
        capture.start()
        result = process.run(timeout_seconds=timeout)
        capture.finish()
    if result.state is not ProcessState.EXITED or result.return_code != 0:
        raise ValueError('observation failed or exceeded its query budget')
    return json.loads(destination.getvalue())


class MonitorRefresh:
    def __init__(self, repository, exchange, *, interval=5, timeout=10):
        self.repository, self.exchange = repository, exchange
        self.interval, self.timeout = interval, timeout
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='patchharbor-monitor')
        self.future = None
        self.due = 0
        self.document = {'repositories': [], 'exchanges': [], 'errors': [], 'observed_at': 'lädt'}

    def tick(self, force=False):
        if self.future is not None and self.future.done():
            try:
                self.document = self.future.result()
            except Exception as exc:
                self.document = {**self.document, 'stale': True, 'error': str(exc)}
            self.future = None
            self.due = time.monotonic() + self.interval
        if self.future is None and (force or time.monotonic() >= self.due):
            self.future = self.pool.submit(query, self.repository, self.exchange, self.timeout)

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
