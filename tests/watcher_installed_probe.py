"""Invoked by an isolated installed interpreter, without checkout imports."""
from io import StringIO
import json
from pathlib import Path
import sys
from threading import Timer
from time import monotonic
from zipfile import ZipFile

import patchharbor
from patchharbor import api
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from patchharbor_watcher.lifecycle import WatcherStopController
from patchharbor_watcher.loop import run_repository_watcher
from patchharbor_watcher.platform import open_event_source


def main():
    assert Path(patchharbor.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    repo, exchange = (Path(value).resolve() for value in sys.argv[1:])
    context = api.register(repo)
    api.configure_exchange_directory(exchange, repository=repo)
    entrypoint = 'run.ps1' if sys.platform == 'win32' else 'run.sh'
    body = '# PATCHHARBOR\nexit 0\n' if sys.platform == 'win32' else '#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n'
    with ZipFile(exchange / 'native-worker.bin', 'w') as z:
        z.writestr('patch.json', json.dumps({'marker': 'patch-harbor', 'format_version': 1,
            'repo_id': str(context.repo_id), 'base_commit': str(context.base_commit),
            'state_fingerprint': context.state_fingerprint, 'fingerprint_algorithm': context.fingerprint_algorithm,
            'entrypoint': entrypoint}))
        z.writestr(entrypoint, body)
    stop, results, opened = WatcherStopController(), [], []
    def source(directories):
        result = open_event_source(directories)
        opened.append(monotonic())
        return result
    def delegate(*, exchanges):
        started = monotonic()
        result = delegate_to_automatic_apply(exchanges=exchanges)
        results.append((started, result))
        stop.request_stop()
        return result
    timer = Timer(35, stop.request_stop)
    timer.start()
    try:
        run_repository_watcher(delegate=delegate, log_stream=StringIO(), error_stream=StringIO(),
            stop_requested=stop.stop_requested, bind_wake=stop.bind_wake, source_factory=source)
    finally:
        timer.cancel(); timer.join()
    assert len(results) == 1 and results[0][0] >= opened[0] + 5
    result = results[0][1]
    assert result.process_exit_code == 0 and result.progress.status == 'attempted'
    with ZipFile(result.apply_result['result']['result_bundle']['path']) as z:
        report = json.loads(z.read('logs/run.json'))
        assert report['execution_present'] and report['primary_result']['success'] and not report['dry_run']
        assert report['repo_id'] == str(context.repo_id)
    print(json.dumps({'native_wait': True, 'quiet_seconds': 5, 'actual_worker_apply': True,
                      'installation': str(Path(patchharbor.__file__).resolve())}))


if __name__ == '__main__':
    main()
