"""Real automatic Apply without native notifications; fresh scope and replay."""
from io import StringIO
import json
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from patchharbor import api
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from patchharbor_watcher.polling import run_polling_watcher
from tests.apply_support import write_package
from tests.platform_support import project_environment
from tests.registration_support import create_repository, set_isolated_user_environment
from tests.test_watcher_polling import Publication

pytestmark = pytest.mark.e2e


def test_poll_discovers_new_files_and_new_exchange_without_events_and_preserves_replay(tmp_path, monkeypatch):
    from patchharbor_watcher import platform, loop
    set_isolated_user_environment(monkeypatch, tmp_path/'user')
    def forbidden(*args, **kwargs):
        pytest.fail('polling tried to open a native event backend')
    monkeypatch.setattr(platform, 'open_event_source', forbidden)
    monkeypatch.setattr(loop, 'open_event_source', forbidden)
    repo = create_repository(tmp_path/'repo')
    context = api.register(repo)
    old, new = tmp_path/'old-exchange', tmp_path/'new-exchange'
    api.configure_exchange_directory(old, repository=repo)
    reports, scopes, waits = [], [], []
    ticks = [0.0]
    def delegate(*, exchanges):
        scopes.append(tuple(t.directory for t in exchanges))
        result = delegate_to_automatic_apply(exchanges=exchanges, environment=project_environment())
        reports.append(result)
        return result
    def wait(seconds):
        waits.append(seconds); ticks[0] += seconds
        if len(waits) == 1:
            # A remote writer can change the directory without a local event.
            write_package(old/'incoming.data', context, exit_code=23)
        elif len(waits) == 3:
            api.configure_exchange_directory(new, repository=repo)
            write_package(new/'next.data', context)
        return len(waits) >= 5
    run_polling_watcher(delegate=delegate, interval=.25,
        stop_requested=lambda: len(waits) >= 5, wait=wait, clock=lambda: ticks[0],
        log_stream=StringIO(), error_stream=StringIO(), publication_factory=Publication)
    assert [r.progress.status for r in reports] == ['no_candidate', 'attempted', 'no_candidate', 'attempted', 'no_candidate']
    assert [r.process_exit_code for r in reports if r.progress.status == 'attempted'] == [23, 0]
    assert scopes == [(old,)] * 3 + [(new,)] * 2
    assert waits == [.25] * 5
    assert api.context(repo) == context
    for r in reports:
        if r.progress.status == 'attempted':
            assert Path(r.apply_result['result']['result_bundle']['path']).is_file()


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX signal delivery; cross-platform stop event is tested separately')
@pytest.mark.parametrize('stop_signal', [signal.SIGINT, signal.SIGTERM])
def test_poll_cli_stops_with_expected_exit_code_even_for_huge_interval(tmp_path, monkeypatch, stop_signal):
    set_isolated_user_environment(monkeypatch, tmp_path/'user')
    process = subprocess.Popen([sys.executable, '-m', 'patchharbor.cli', 'watcher', 'poll', '--interval', '1e100'],
        cwd=tmp_path, env=project_environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        record = json.loads(process.stdout.readline())
        assert record['event'] == 'watcher_started' and record['watcher_mode'] == 'poll'
        process.send_signal(stop_signal)
        output, errors = process.communicate(timeout=10)
        assert process.returncode == (130 if stop_signal == signal.SIGINT else 0), errors
        assert [json.loads(row)['event'] for row in output.splitlines()] == ['watcher_stopped']
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()
