"""Presentation facts from explicit live identity, native candidates and Results."""
from __future__ import annotations

from datetime import datetime, timezone

from patchharbor.monitor_activity import PHASES, WATCH_LABELS
from patchharbor.monitor_format import age, duration, elapsed, short_id, timestamp


def live(row, document, now=None):
    stamp = timestamp(row.get('updated_at'))
    age_seconds = ((now or datetime.now(timezone.utc)) - stamp).total_seconds() if stamp else None
    return bool(row.get('live') and not row.get('stale') and not document.get('live_view', {}).get('stale')
                and age_seconds is not None and 0 <= age_seconds <= 15)


def instances(document):
    return document.get('live_view', {}).get('instances', [])


def active_runs(document, repo_id=None, now=None):
    return sorted((r for r in instances(document) if r['kind'] in ('apply', 'bundle') and live(r, document, now)
                   and (repo_id is None or r.get('data', {}).get('repo_id') == repo_id)),
                  key=lambda r: (r['started_at'], r['instance_id']))


def activity(row):
    if row.get('activity'):
        return row['activity']
    data, phase = row.get('data', {}), row.get('phase', 'starting')
    status, message, code = 'unknown', 'Aktivität unbekannt', phase
    if row.get('completed'):
        primary = data.get('primary_result') or {}
        if (data.get('origin') == 'automatic' and not primary.get('entrypoint_started')
                and primary.get('kind') == 'validation_error' and data.get('result_status') == 'not_attempted'
                and data.get('message') == 'No eligible patch remains after content, scope, state and replay checks'):
            code, status, message = 'no-candidate', 'waiting', 'Kein ausführbarer Patch gefunden'
        elif primary or data.get('result_status') == 'failed':
            status = 'success' if primary.get('success') and data.get('result_status') != 'failed' else 'failure'
            message = 'Apply erfolgreich abgeschlossen' if status == 'success' else 'Apply fehlgeschlagen'
        elif row['kind'] == 'watcher' and phase == 'stopped':
            status, message = ('failure' if data.get('last_error') else 'success'), 'Watcher beendet'
    elif row['kind'] == 'watcher':
        targets = data.get('targets', [])
        lock = data.get('control_lock') or next((t.get('blocked_on') for t in targets if t.get('blocked_on')), None)
        code = phase if phase == 'applying' else lock['kind'] + '-lock' if lock else 'quiet' if any(t.get('dirty') for t in targets) else phase
        status, message = ('running' if code in ('starting', 'applying') else 'waiting'), WATCH_LABELS.get(code, 'Watcher-Zustand unbekannt')
    elif data.get('effective_timeout_seconds') is not None and data.get('process_state') is None:
        code, status, message = 'entrypoint', 'running', 'Entrypoint läuft'
    elif phase in PHASES:
        code, message = PHASES[phase]
        status = 'failure' if phase in ('TIMEOUT', 'INTERRUPT') else 'running'
    elif phase == 'starting':
        code, status, message = 'starting', 'running', 'PatchHarbor startet'
    return dict(code=code, status=status, message=message, sequence=0,
                at=row.get('facts_updated_at'), since=data.get('entrypoint_started_at') or row.get('facts_updated_at'))


def basename(path):
    return str(path or '').replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]


def repo_name(row, document):
    data = row.get('data', {})
    repo = next((r for r in document.get('repositories', []) if r['repo_id'] == data.get('repo_id')), None)
    return repo['name'] if repo else basename(data.get('repository_path')) or 'Repo noch offen'


def package_label(data, full=False):
    number = data.get('bundle_number')
    digest = data.get('task_sha256') or data.get('sha256')
    if number:
        return 'Patch #' + number + (' · ' + short_id(digest, full) if digest else '')
    if digest:
        return 'Patch ' + short_id(digest, full)
    return 'Patch ' + basename(data['patch_path']) if data.get('patch_path') else 'Patch-Suche'


def operation(row, full=False):
    item, data = activity(row), row.get('data', {})
    if row['kind'] == 'watcher':
        return 'Watcher'
    if item['code'] == 'no-candidate':
        return 'Exchange-Prüfung'
    if row['kind'] == 'bundle':
        return 'Result-Bundle · Lauf ' + short_id(data.get('run_id'), full)
    label = package_label(data, full)
    return 'Result zu ' + label if item['code'].startswith('result-') else label


def activity_text(row, now=None):
    item, data = activity(row), row.get('data', {})
    if item['code'] == 'entrypoint' and item['status'] == 'running':
        return (data.get('entrypoint_name') or 'Entrypoint') + ' läuft · seit ' + duration(elapsed(data.get('entrypoint_started_at') or item['since'], now))
    return item['message']


def watcher_targets(document, repo_id=None, exchange=None, now=None):
    return [(row, target) for row in instances(document) if row['kind'] == 'watcher' and live(row, document, now)
            for target in row.get('data', {}).get('targets', [])
            if (repo_id is None or repo_id in target.get('repository_ids', []))
            and (exchange is None or target['directory'] == exchange)]


def summary_current(summary, now=None):
    stamp = timestamp(summary.get('observed_at'))
    seconds = ((now or datetime.now(timezone.utc)) - stamp).total_seconds() if stamp else None
    return bool(seconds is not None and 0 <= seconds <= 45 and not summary.get('stale') and not summary.get('error')
                and not summary.get('errors') and not summary.get('incomplete') and not summary.get('repository_error'))


def repository_status(repo, document, now=None):
    runs = active_runs(document, repo['repo_id'], now)
    if runs:
        return activity_text(runs[0], now) + (f' · +{len(runs)-1} aktiv' if len(runs) > 1 else ''), 'running', runs[0]
    if document.get('stale'):
        return 'Repository-Beobachtung veraltet', 'unknown', None
    if repo.get('registration') != 'ok':
        return 'Registrierung fehlt/konfliktär', 'failure', None
    if repo.get('configuration_status') == 'invalid':
        return 'Konfiguration ungültig', 'failure', None
    if document.get('stale') or repo.get('stale') or repo.get('error'):
        return 'Repository-Beobachtung unklar', 'unknown', None
    if not repo.get('exchange'):
        return 'Exchange nicht eingerichtet', 'waiting', None
    target = next(iter(watcher_targets(document, repo['repo_id'], repo.get('exchange'), now)), None)
    if target:
        watcher, facts = target
        lock = facts.get('blocked_on') or watcher.get('data', {}).get('control_lock')
        if lock:
            return WATCH_LABELS.get(lock['kind'] + '-lock', 'Wartet auf Sperre'), 'waiting', None
        if facts.get('dirty'):
            return 'Prüfung vorgemerkt', 'waiting', None
        return 'Wartet auf Änderungen', 'waiting', None
    stale = next((r for r in instances(document) if r['kind'] in ('apply', 'bundle') and
                  r.get('data', {}).get('repo_id') == repo['repo_id'] and not r.get('completed')), None)
    return ('Aktivität nicht mehr bestätigt' if stale else 'Keine aktive Ausführung beobachtet'), 'unknown', None


def exchange_status(repo, document, now=None):
    path = repo.get('exchange')
    if not path:
        return 'nicht eingerichtet', 'waiting'
    exchange = next((r for r in document.get('exchanges', []) if r['path'] == path), {})
    if not document.get('stale') and exchange.get('available') is False:
        return 'nicht erreichbar', 'failure'
    summary = document.get('repository_views', {}).get(repo['repo_id'], {})
    targets = watcher_targets(document, repo['repo_id'], path, now)
    if targets:
        facts = targets[0][1]
        remaining = max(0, facts.get('quiet_until', 0) - (now or datetime.now(timezone.utc)).timestamp()) if facts.get('quiet_until') else 0
        if facts.get('dirty') and remaining:
            return 'Ruhefrist ' + duration(remaining), 'waiting'
        if facts.get('dirty'):
            return 'Prüfung vorgemerkt', 'waiting'
    if summary_current(summary, now):
        if summary.get('candidate'):
            number = summary['candidate'].get('bundle_number')
            return ('Patch #' + number if number else 'Task') + ' passend', 'title'
        return 'kein Patch passend', 'waiting'
    if summary.get('incomplete') or summary.get('errors'):
        return 'Bestand unklar', 'unknown'
    if summary.get('stale') or summary.get('error') or summary.get('observed_at'):
        return 'Bestand veraltet', 'unknown'
    return ('überwacht · lädt' if targets else 'Überwachung unklar'), 'unknown'


def last_result(repo, document, now=None):
    candidates = []
    for row in instances(document):
        data = row.get('data', {})
        if row['kind'] == 'apply' and row.get('completed') and data.get('repo_id') == repo['repo_id'] and not data.get('dry_run'):
            if data.get('automatic_status') in ('no_candidate', 'locked') or activity(row)['code'] == 'no-candidate':
                continue
            candidates.append((row.get('facts_updated_at', ''), data, False))
    summary = document.get('repository_views', {}).get(repo['repo_id'], {})
    result = summary.get('latest_result')
    if result:
        candidates.append((result.get('ended_at', ''), result, bool(result.get('ambiguous_run') or summary.get('stale') or summary.get('error'))))
    if not candidates:
        return '—', 'unknown'
    stamp, data, uncertain = max(candidates, key=lambda item: timestamp(item[0]) or datetime.min.replace(tzinfo=timezone.utc))
    primary = data.get('primary_result') or {}
    status = 'unknown' if uncertain or not primary else 'success' if primary.get('success') and data.get('result_status') != 'failed' else 'failure'
    detail = 'Result fehlgeschlagen' if data.get('result_status') == 'failed' else ('Exit ' + str(primary['entrypoint_exit_code'])) if status == 'failure' and primary.get('entrypoint_exit_code') is not None else ''
    return (detail + ' · ' if detail else '') + age(stamp, now), status
