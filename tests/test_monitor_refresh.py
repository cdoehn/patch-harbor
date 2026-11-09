"""Refresh isolation, bounded native queries and stale-data contracts."""
from concurrent.futures import Future
import json
import sys
import time

import pytest

from patchharbor import api
from patchharbor import monitor_query
from patchharbor.monitor_query import MonitorRefresh, query
from patchharbor.monitor_session import MonitorSession, git_semantic
from patchharbor.user_paths import registration_user_paths
from tests.test_monitor import registered


def complete(entry, value=None, error=None):
    future = Future()
    if error is None:
        future.set_result(value)
    else:
        future.set_exception(error)
    entry['future'] = future


def test_stale_previous_success_is_retained_but_not_presented_as_clean():
    refresh = MonitorRefresh(None, None)
    row = {'repo_id': 'a', 'path': '/a', 'name': 'a', 'registration': 'ok', 'git_status': 'clean', 'exchange': '/x'}
    document = {'repositories': [row], 'exchanges': [], 'errors': [], 'observed_at': 'old'}
    try:
        refresh.discovery['value'] = document
        refresh.sources['a'] = {'value': document, 'future': None, 'due': 0, 'error': None, 'path': '/a'}
        complete(refresh.sources['a'], error=ValueError('query timed out'))
        refresh._harvest(refresh.sources['a'])
        observed = refresh.document['repositories'][0]
        assert observed['git_status'] == 'clean' and observed['stale']
        assert git_semantic(observed) == 'unknown'
        assert refresh.document['observed_at'] == 'old'
        complete(refresh.sources['a'], value={**document, 'observed_at': 'new'})
        refresh._harvest(refresh.sources['a'])
        assert not refresh.document['repositories'][0]['stale']
    finally:
        refresh.close()


def test_one_blocked_source_does_not_block_other_completed_source():
    refresh = MonitorRefresh(None, None)
    rows = [{'repo_id': n, 'name': n, 'path': '/' + n, 'exchange': '/x', 'registration': 'ok', 'git_status': 'unknown'} for n in ('a', 'b')]
    refresh.discovery['value'] = {'repositories': rows, 'exchanges': [], 'errors': [], 'observed_at': 'initial'}
    try:
        refresh.sources = {r['repo_id']: {'value': None, 'future': Future(), 'due': 0, 'error': None, 'path': r['path']} for r in rows}
        complete(refresh.sources['b'], {'repositories': [{**rows[1], 'git_status': 'dirty'}], 'errors': []})
        refresh._harvest(refresh.sources['b'])
        result = refresh.document['repositories']
        assert result[0]['refreshing'] and result[0]['git_status'] == 'unknown'
        assert result[1]['git_status'] == 'dirty' and not result[1]['refreshing']
    finally:
        refresh.close()


def test_in_flight_queries_are_not_duplicated_by_manual_refresh():
    refresh = MonitorRefresh(None, None)
    try:
        refresh.discovery['future'] = Future()
        refresh.sources['a'] = {'value': None, 'future': Future(), 'due': 0, 'error': None, 'path': '/a'}
        original = refresh.sources['a']['future']
        refresh.tick(force=True)
        assert refresh.sources['a']['future'] is original
    finally:
        refresh.close()


def test_child_observation_timeout_stops_the_query(monkeypatch):
    original = monitor_query.create_process_tree
    def slow(command, *, cwd):
        return original([sys.executable, '-c', 'import time; time.sleep(30)'], cwd=cwd)
    monkeypatch.setattr(monitor_query, 'create_process_tree', slow)
    started = time.monotonic()
    with pytest.raises(ValueError, match='budget'):
        query(None, None, .1)
    assert time.monotonic() - started < 10


def test_response_byte_limit_is_enforced():
    output = monitor_query.BoundedBuffer()
    with pytest.raises(ValueError):
        output.write(b'x' * (4 * 1024 * 1024 + 1))
    assert output.getvalue() == b''


def test_discovery_can_skip_expensive_git_capture(tmp_path, monkeypatch):
    import patchharbor.application_monitor as monitor
    registered(tmp_path, monkeypatch)
    monkeypatch.setattr(monitor, 'inspect_source', lambda *_: pytest.fail('state capture in discovery'))
    row, = api.monitor_snapshot(include_state=False).repositories
    assert row.registration == 'ok' and row.exchange and row.git_status == 'unknown'


def test_oversized_registry_is_reported_without_partial_clean_rows(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    path = registration_user_paths().registry_path
    path.write_bytes(b' ' * (4 * 1024 * 1024 + 1))
    result = api.monitor_snapshot()
    assert result.errors and not result.repositories


def test_repository_replacement_does_not_reuse_old_details():
    refresh = MonitorRefresh(None, None)
    try:
        refresh.discovery['value'] = {'repositories': [{'repo_id': 'a', 'path': '/new', 'name': 'new', 'registration': 'ok', 'git_status': 'unknown'}], 'errors': []}
        refresh.sources['a'] = {'value': {'repositories': [{'repo_id': 'a', 'path': '/old', 'git_status': 'clean'}]}, 'error': None, 'future': None}
        assert refresh.document['repositories'][0]['git_status'] == 'unknown'
    finally:
        refresh.close()


def test_detail_scrolling_does_not_change_repository_selection():
    session = MonitorSession(view='exchanges', focus='details', repository_id='selected')
    session.move({}, 3)
    assert session.repository_id == 'selected'
    assert session.offsets['exchanges'] == 3
    assert MonitorSession().offsets == {}
