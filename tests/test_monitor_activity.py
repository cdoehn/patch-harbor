"""Operational UI contracts, genuine publisher history and bounded overview work."""
from concurrent.futures import Future
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

import pytest

from patchharbor import api
from patchharbor.monitor_activity import declared_bundle_number, HISTORY_LIMIT
from patchharbor.monitor_display import render
from patchharbor.monitor_format import duration, human_text, short_id, SPINNER, cell_width
from patchharbor.monitor_live_schema import parse_live
from patchharbor.monitor_session import MonitorSession, VIEWS
from patchharbor.monitor_status import activity, active_runs, exchange_status, last_result, repository_status
from patchharbor.monitor_timeline import timeline, forecast
from tests.test_monitor import registered
from tests.test_monitor_live import wait_for, instance
from tests.test_monitor_artifacts import patch
from tests.exchange_support import _write_custom_package

NOW = datetime(2026, 11, 10, 12, 30, tzinfo=timezone.utc)
REPO, OTHER, RUN = (str(uuid4()) for _ in range(3))
DIGEST = 'a12345' + 'b' * 58


def stamp(seconds=0):
    return (NOW + timedelta(seconds=seconds)).isoformat()


def event(code, status, message, sequence, seconds):
    return dict(code=code, status=status, message=message, sequence=sequence,
                at=stamp(seconds), since=stamp(seconds))


def document():
    execute = dict(kind='execute', instance_id=RUN, pid=123, phase='entrypoint',
                 started_at=stamp(-140), updated_at=stamp(), facts_updated_at=stamp(-134),
                 completed=False, live=True, stale=False,
                 data=dict(repo_id=REPO, repository_path='/repos/patchharbor', run_id=RUN,
                           task_sha256=DIGEST, bundle_number='082', entrypoint_name='run.sh',
                           origin='automatic', dry_run=False, effective_timeout_seconds=3600,
                           entrypoint_started_at=stamp(-134)),
                 history=[event('binding', 'success', 'Repository-Bindung stimmt überein', 1, -136),
                          event('payload', 'success', 'Task-Dateien übernommen', 2, -135)],
                 activity=event('entrypoint', 'running', 'Entrypoint läuft', 3, -134))
    repos = [dict(repo_id=identity, name=name, path='/repos/'+name, registration='ok',
                  git_status='dirty', staged=1, unstaged=2, untracked=3, exchange='/exchange',
                  fingerprint='c'*16, commit='d'*40, observed_at=stamp())
             for identity, name in ((REPO, 'patchharbor'), (OTHER, 'other'))]
    return dict(observed_at=stamp(), repositories=repos,
                exchanges=[dict(path='/exchange', available=True, repository_ids=[REPO, OTHER])],
                errors=[], live_view=dict(instances=[execute], observed_at=stamp(), errors=[]),
                repository_views={})


@pytest.mark.parametrize('view', VIEWS)
def test_global_five_line_timeline_survives_view_filter_and_scroll(view):
    doc = document()
    session = MonitorSession(view=view, match='other', focus='content', offsets={view: 999})
    screen = render(doc, session, now=NOW, frame=0, width=140, height=35)
    header = screen.splitlines()[2:7]
    assert len(header) == 5
    assert '✓' in header[0] and '✓' in header[1]
    assert SPINNER[0] in header[2] and '→' not in header[2]
    assert all(value in header[2] for value in ('patchharbor', '#082', 'a12345...', 'run.sh', '2m 14s'))
    assert 'Result-Bundle' in header[3] and 'Commit' not in '\n'.join(header)
    assert header[3].startswith('--:--:--') and header[4].startswith('--:--:--')
    assert session.repository_id == OTHER


@pytest.mark.parametrize('dimensions', [(60, 15), (80, 24), (120, 40)])
def test_resizing_keeps_current_middle_line_and_bounds_output(dimensions):
    width, height = dimensions
    screen = render(document(), MonitorSession(), now=NOW, frame=0, width=width, height=height)
    assert SPINNER[0] in screen.splitlines()[4]
    assert len(screen.splitlines()) <= height
    assert all(sum(cell_width(c) for c in line) < width for line in screen.splitlines())


def test_colors_follow_outcome_and_future_and_git_is_secondary():
    doc = document()
    doc['live_view']['instances'][0]['history'][0]['status'] = 'failure'
    screen = render(doc, MonitorSession(), now=NOW, frame=0, color=True, width=140)
    assert '\x1b[31m×' in screen and '\x1b[32m✓' in screen
    assert '\x1b[1;36m' + SPINNER[0] in screen
    assert '\x1b[35m' in screen
    assert 'Staged / unstaged' not in screen and 'Git:' not in screen
    assert 'Git: dirty' in render(doc, MonitorSession(show_git=True), now=NOW, height=60)
    assert repository_status(doc['repositories'][0], doc, NOW)[1] == 'running'
    assert repository_status(doc['repositories'][1], doc, NOW)[1] == 'unknown'


@pytest.mark.parametrize('change', ['stale', 'heartbeat', 'future-clock', 'source-error'])
def test_unconfirmed_activity_never_spins_or_forecasts_success(change):
    doc = document()
    row = doc['live_view']['instances'][0]
    if change == 'stale': row['stale'] = True
    if change == 'heartbeat': row['updated_at'] = stamp(-60)
    if change == 'future-clock': row['updated_at'] = stamp(60)
    if change == 'source-error': doc['live_view']['stale'] = True
    assert not active_runs(doc, now=NOW)
    assert all(style == 'unknown' for _, style in forecast(row, doc, NOW))
    screen = render(doc, MonitorSession(), now=NOW, frame=0)
    assert not any(char in screen for char in SPINNER)
    assert 'VERALTET' in screen


def test_successful_entrypoint_with_failed_result_stays_failed():
    doc = document()
    row = doc['live_view']['instances'][0]
    row.update(completed=True, live=False, facts_updated_at=stamp())
    row['data'].update(primary_result={'success': True, 'entrypoint_exit_code': 0}, result_status='failed')
    row['activity'] = event('completed', 'failure', 'Execute fehlgeschlagen', 4, 0)
    text, status = last_result(doc['repositories'][0], doc, NOW)
    assert status == 'failure' and 'Result fehlgeschlagen' in text
    assert all(style == 'unknown' for _, style in forecast(row, doc, NOW))


def test_parallel_applies_have_stable_focus_and_separate_repository_states():
    doc = document()
    other = deepcopy(doc['live_view']['instances'][0])
    other.update(instance_id=str(uuid4()), started_at=stamp(-20))
    other['data'].update(repo_id=OTHER, repository_path='/repos/other', bundle_number='083')
    doc['live_view']['instances'].insert(0, other)
    assert [r['data']['bundle_number'] for r in active_runs(doc, now=NOW)] == ['082', '083']
    assert repository_status(doc['repositories'][1], doc, NOW)[2]['instance_id'] == other['instance_id']
    assert '#082' in render(doc, MonitorSession(), now=NOW).splitlines()[4]


def test_identifiers_toggle_without_changing_sources_or_raw_logs():
    doc = document()
    before = deepcopy(doc)
    short = render(doc, MonitorSession(view='live', repository_id=REPO), now=NOW, height=80)
    full = render(doc, MonitorSession(view='live', repository_id=REPO, full_identifiers=True), now=NOW, width=140, height=80)
    assert DIGEST not in short and 'a12345...' in short
    assert DIGEST in full and RUN in full
    assert doc == before
    assert human_text('2026-11-10T12:30:00+00:00') != '2026-11-10T12:30:00+00:00'
    assert human_text('\x1b[2J' + DIGEST).startswith('?[2J')


def test_unknown_or_incomplete_inventory_does_not_claim_no_candidate():
    doc = document(); repo = doc['repositories'][1]
    for view in ({}, {'incomplete': True}, {'observed_at': stamp(-90)},
                 {'observed_at': stamp(), 'repository_error': 'cannot inspect state'}):
        doc['repository_views'][OTHER] = view
        assert 'kein Task passend' not in exchange_status(repo, doc, NOW)[0]
    doc['repository_views'][OTHER] = dict(observed_at=stamp(), eligible_count=0, candidate=None)
    assert exchange_status(repo, doc, NOW)[0] == 'kein Task passend'


def test_global_live_jump_keeps_operation_visible_outside_repository_filter():
    doc = document()
    doc['repositories'] = [doc['repositories'][1]]
    session = MonitorSession(view='live', repository_id=OTHER, live_focus_id=RUN)
    assert session.selected(doc)['repo_id'] == OTHER
    assert session.selected_live(doc)['instance_id'] == RUN
    session.focus = 'repositories'
    session.move(doc, 1)
    assert session.live_focus_id is None


def test_bundle_number_requires_one_literal_declaration():
    assert declared_bundle_number(b"printf 'PATCHHARBOR-BUNDLE-NR: 082 | APPLIED SUCCESSFULLY'") == '082'
    assert declared_bundle_number(b'# PATCHHARBOR-BUNDLE-NR: 082\n# PATCHHARBOR-BUNDLE-NR: 082') == '082'
    assert declared_bundle_number(b'# PATCHHARBOR-BUNDLE-NR: 082\n# PATCHHARBOR-BUNDLE-NR: 083') is None
    assert declared_bundle_number(b'file_082.zip\nPATCHHARBOR-BUNDLE-NR: %03d') is None
    assert declared_bundle_number(b'PATCHHARBOR-BUNDLE-NR: 0820') is None


def test_published_history_survives_late_monitor_start_and_is_bounded(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    publication = api.watcher_observation()
    for index in range(60):
        publication.update(activity_code='step-' + str(index), activity_status='success', activity_message='Schritt ' + str(index))
    publication.update(phase='watching')
    row = wait_for(lambda: r if (r := instance(publication.instance_id)) and len(r.get('history', [])) == HISTORY_LIMIT else None)
    publication.close()
    assert row['format_version'] == 3 and row['history'][-1]['message'] == 'Schritt 59'
    assert row['history'][-1]['status'] == 'success'
    assert row['activity']['status'] == 'waiting'


def test_version_one_is_readable_and_malformed_history_is_rejected(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    publication = api.watcher_observation()
    row = wait_for(lambda: instance(publication.instance_id))
    publication.close()
    for key in ('live', 'stale', 'stale_reason', 'age_seconds'):
        row.pop(key, None)
    name = 'watcher-' + row['instance_id'] + '.json'
    legacy = {k: v for k, v in row.items() if k not in ('activity', 'history')}
    legacy['format_version'] = 1
    with pytest.raises(ValueError, match='schema'):
        parse_live(json.dumps(legacy).encode(), name)
    row['history'] = [row['activity']] * (HISTORY_LIMIT+1)
    with pytest.raises(ValueError, match='history'):
        parse_live(json.dumps(row).encode(), name)
    row['history'] = []
    row['activity']['status'] = []
    with pytest.raises(ValueError, match='status'):
        parse_live(json.dumps(row).encode(), name)


def test_native_execute_reports_bundle_number_entrypoint_repo_and_exit(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    path = tmp_path/'exchange'/'patch.zip'
    _write_custom_package(path, {k: str(getattr(context, k)) for k in ('repo_id', 'base_commit', 'state_fingerprint')},
        posix_entrypoint='# PATCHHARBOR-BUNDLE-NR: 082\nexit 0',
        powershell_entrypoint='# PATCHHARBOR-BUNDLE-NR: 082\nexit 0')
    report = api.execute(path)
    assert report.success
    row = wait_for(lambda: next((r for r in api.monitor_live()['instances']
        if r['data'].get('run_id') == str(report.run_id) and r['completed']), None))
    assert row['data']['bundle_number'] == '082'
    assert row['data']['entrypoint_name'] in ('run.sh', 'run.ps1')
    assert row['data']['repo_id'] == str(context.repo_id)
    assert row['kind'] == 'execute'
    assert row['data']['task_sha256'] == sha256(path.read_bytes()).hexdigest()
    assert row['data']['run_id'] == str(report.run_id)
    assert any(e['code'] == 'entrypoint' and e['status'] == 'success' for e in row['history'])


def test_manual_result_bundle_is_a_separate_observed_operation(tmp_path, monkeypatch):
    (root, context), = registered(tmp_path, monkeypatch)
    result = api.bundle(root)
    row = wait_for(lambda: next((r for r in api.monitor_live()['instances'] if r['kind'] == 'bundle' and r['completed']), None))
    assert row['data']['run_id'] == str(result.report.run_id)
    assert row['data']['repo_id'] == str(context.repo_id)
    assert row['activity']['status'] == 'success'
    assert not row['data'].get('entrypoint_started_at')
    assert not row['data'].get('task_sha256') and not row['data'].get('bundle_number')


def test_empty_automatic_scan_is_waiting_not_a_failed_apply(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    report = api.execute_next()
    assert report.automatic.status.value == 'no_candidate'
    row = wait_for(lambda: next((r for r in api.monitor_live()['instances'] if r['kind'] == 'execute' and r['completed']), None))
    assert row['data']['automatic_status'] == 'no_candidate'
    assert activity(row)['status'] == 'waiting'
    assert activity(row)['code'] == 'no-candidate'
    legacy = {k: v for k, v in row.items() if k not in ('activity', 'history')}
    legacy['data'].pop('automatic_status')
    assert activity(legacy)['status'] == 'waiting'
    legacy['data']['message'] = 'A different validation failure'
    assert activity(legacy)['status'] == 'failure'


def test_overview_summaries_observe_unselected_repositories_with_full_binding(tmp_path, monkeypatch):
    (a, ac), (b, bc) = registered(tmp_path, monkeypatch, ('one', 'two'))
    ap, bp = patch(a, ac, 'a.zip'), patch(b, bc, 'b.zip')
    first, second = api.monitor_overview(str(a)), api.monitor_overview(str(b))
    assert first['task_count'] == second['task_count'] == 1
    assert 'patch_count' not in first and 'patch_count' not in second
    assert first['candidate']['path'] == str(ap) and second['candidate']['path'] == str(bp)
    assert first['candidate']['repo_id'] == str(ac.repo_id)
    (b/'tracked.txt').write_text('changed')
    assert api.monitor_overview(str(b))['candidate'] is None


def test_configuration_failure_is_distinct_from_git_state(tmp_path, monkeypatch):
    (root, _), = registered(tmp_path, monkeypatch)
    (root/'.patchharbor/config.json').write_text('{broken')
    doc = api.monitor_snapshot().document()
    repo, = doc['repositories']
    assert repo['configuration_status'] == 'invalid'
    assert repository_status(repo, doc)[1] == 'failure'
    doc['stale'] = True
    assert repository_status(repo, doc)[1] == 'unknown'


def test_background_summary_budget_fairness_and_reconfiguration(monkeypatch):
    from patchharbor import monitor_overview
    class Pool:
        def __init__(self, **kwargs): self.calls = []
        def submit(self, *args):
            future = Future(); self.calls.append((args, future)); return future
        def shutdown(self, **kwargs): pass
    monkeypatch.setattr(monitor_overview, 'ThreadPoolExecutor', Pool)
    refresh = monitor_overview.OverviewRefresh()
    doc = document()
    doc['repositories'].append({**doc['repositories'][0], 'repo_id': 'third', 'path': '/third'})
    first = refresh.attach(doc)
    assert len(refresh.pool.calls) == 2 and len(first['repository_views']) == 3
    refresh.attach(doc, force=True)
    assert len(refresh.pool.calls) == 2
    refresh.pool.calls[1][1].set_result({'observed_at': stamp(), 'candidate': None})
    view = refresh.attach(doc)
    assert len(refresh.pool.calls) == 3
    assert refresh.pool.calls[-1][0][2]['repository'] == 'third'
    assert view['repository_views'][OTHER]['observed_at'] == stamp()
    doc['repositories'][1]['exchange'] = '/reconfigured'
    view = refresh.attach(doc)
    assert 'observed_at' not in view['repository_views'][OTHER]
    refresh.close()
