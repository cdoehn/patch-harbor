"""Native read-only observations and independent viewer state, not rendering."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest

from patchharbor import api
from patchharbor.monitor_session import MonitorSession, git_semantic
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import create_repository, git, isolated_user_environment


def registered(tmp_path, monkeypatch, names=('one',)):
    for key, value in isolated_user_environment(tmp_path).items():
        monkeypatch.setenv(key, value)
    exchange = tmp_path / 'exchange'
    result = []
    for name in names:
        root = create_repository(tmp_path / name)
        context = api.register(root)
        api.configure_exchange_directory(exchange, repository=root)
        result.append((root, context))
    return result


def test_observation_counts_real_git_changes_without_mutating_sources(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    assert api.monitor_snapshot().repositories[0].git_status == 'clean'
    (root / 'new.txt').write_text('staged')
    git(root, 'add', 'new.txt')
    (root / 'tracked.txt').write_text('unstaged')
    (root / 'loose.txt').write_text('untracked')
    (root / '.git/info/exclude').write_text('.patchharbor/\nignored\n')
    (root / 'ignored').write_text('excluded')
    index = (root / '.git/index').read_bytes()
    paths = registration_user_paths()
    registry = paths.registry_path.read_bytes()
    before = {str(p): p.read_bytes() for p in (root/'.patchharbor').iterdir()}
    snapshot = api.monitor_snapshot()
    row, = snapshot.repositories
    assert (row.git_status, row.staged, row.unstaged, row.untracked) == ('dirty', 1, 1, 1)
    assert row.repo_id == str(context.repo_id)
    assert (root / '.git/index').read_bytes() == index
    assert paths.registry_path.read_bytes() == registry
    assert {str(p): p.read_bytes() for p in (root/'.patchharbor').iterdir()} == before
    assert not paths.exchange_state_path.exists()
    with pytest.raises(FrozenInstanceError):
        row.name = 'changed'


def test_shared_exchange_and_explicit_scope_keep_full_identities(tmp_path, monkeypatch):
    entries = registered(tmp_path, monkeypatch, ('one', 'two'))
    snapshot = api.monitor_snapshot()
    assert len(snapshot.repositories) == 2 and len(snapshot.exchanges) == 1
    assert set(snapshot.exchanges[0].repository_ids) == {str(c.repo_id) for _, c in entries}
    for root, context in entries:
        assert [r.repo_id for r in api.monitor_snapshot(repository=str(root)).repositories] == [str(context.repo_id)]
        assert [r.repo_id for r in api.monitor_snapshot(repository=str(context.repo_id)).repositories] == [str(context.repo_id)]
    assert api.monitor_snapshot(repository='unregistered').errors
    assert api.monitor_snapshot(exchange=tmp_path/'elsewhere').repositories == ()


def test_broken_target_does_not_hide_healthy_peer(tmp_path, monkeypatch):
    (a, _), (b, _) = registered(tmp_path, monkeypatch, ('one', 'two'))
    (a/'.patchharbor/config.json').write_text('{broken')
    by_name = {r.name: r for r in api.monitor_snapshot().repositories}
    assert by_name['one'].error and by_name['one'].git_status == 'unknown'
    assert by_name['two'].git_status == 'clean'
    (a/'.patchharbor/id').write_text('invalid')
    assert next(r for r in api.monitor_snapshot().repositories if r.path == str(a)).registration == 'conflict'


def test_empty_user_observation_does_not_create_directories(tmp_path, monkeypatch):
    for key, value in isolated_user_environment(tmp_path).items():
        monkeypatch.setenv(key, value)
    assert api.monitor_snapshot().repositories == ()
    assert list(tmp_path.iterdir()) == []


def test_missing_repository_and_exchange_are_explicit(tmp_path, monkeypatch):
    (root, _), = registered(tmp_path, monkeypatch)
    exchange = tmp_path/'exchange'
    exchange.rmdir()
    view = api.monitor_snapshot()
    assert view.exchanges[0].available is False
    root.rename(tmp_path/'moved')
    row, = api.monitor_snapshot().repositories
    assert row.registration == 'missing' and row.git_status == 'unknown'


def test_independent_concurrent_observers_and_viewer_filters(tmp_path, monkeypatch):
    entries = registered(tmp_path, monkeypatch, ('one', 'two'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        snapshots = list(pool.map(lambda pair: api.monitor_snapshot(repository=str(pair[0])).document(), entries))
    assert [s['repositories'][0]['name'] for s in snapshots] == ['one', 'two']
    document = api.monitor_snapshot().document()
    first, second = MonitorSession(match='one'), MonitorSession(view='exchanges', match='two')
    assert first.selected(document)['name'] == 'one'
    assert second.selected(document)['name'] == 'two'
    first.view, first.match = 'exchanges', ''
    first.move(document, 1)
    assert second.match == 'two' and first.selections is not second.selections
    assert git_semantic({'registration': 'ok', 'git_status': 'clean', 'stale': True}) == 'unknown'


def test_configured_git_filter_is_not_executed_by_monitor(tmp_path, monkeypatch):
    (root, _), = registered(tmp_path, monkeypatch)
    marker = tmp_path/'filter-ran'
    script = tmp_path/'filter.py'
    script.write_text('from pathlib import Path; Path(' + repr(str(marker)) + ').write_text("executed")')
    git(root, 'config', 'filter.trap.clean', f'"{sys.executable}" "{script}"')
    (root/'.gitattributes').write_text('tracked.txt filter=trap\n')
    (root/'tracked.txt').write_text('changed')
    row, = api.monitor_snapshot().repositories
    assert row.git_status == 'unknown' and row.error
    assert not marker.exists()


@pytest.mark.parametrize('selector', ['', '\x00', 1])
def test_monitor_rejects_invalid_selectors(selector):
    with pytest.raises(ValueError):
        api.monitor_snapshot(repository=selector)


def test_once_json_uses_bounded_observer_without_a_terminal(tmp_path, monkeypatch):
    import json
    from io import StringIO
    from patchharbor.cli import main
    (root, context), = registered(tmp_path, monkeypatch)
    stdout, stderr = StringIO(), StringIO()
    code = main(['monitor', '--repo', str(root), '--once', '--json'],
                stdin=StringIO(), stdout=stdout, stderr=stderr)
    assert code == 0, stderr.getvalue() + stdout.getvalue()
    document = json.loads(stdout.getvalue())
    assert document['kind'] == 'patchharbor-monitor'
    assert document['repositories'][0]['repo_id'] == str(context.repo_id)
    assert document['repositories'][0]['git_status'] == 'clean'
    assert main(['monitor'], stdin=StringIO(), stdout=StringIO(), stderr=StringIO()) == 2
