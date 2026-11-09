"""Bounded child observations share the existing process-tree cleanup boundary."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys

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
