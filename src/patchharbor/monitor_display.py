"""Persistent activity header and operational repository overview."""
from __future__ import annotations

from datetime import datetime, timezone
import time

from patchharbor.monitor_artifact_display import artifact_lines
from patchharbor.monitor_format import (crop, safe_text, fit, human_text, render_spans,
                                       short_id, symbol, wrap, age)
from patchharbor.monitor_live_display import live_lines
from patchharbor.monitor_session import git_semantic
from patchharbor.monitor_status import (active_runs, exchange_status, last_result, operation,
                                       package_label, repository_status, watcher_targets)
from patchharbor.monitor_timeline import timeline, watcher_line

VIEW_NAMES = dict(zip(('overview', 'exchanges', 'bundles', 'history', 'logs', 'live', 'live-logs'),
                      ('Übersicht', 'Exchanges', 'Bundles', 'Verlauf', 'Logs', 'Live', 'Live-Log')))
FOCUS_NAMES = {'repositories': 'Repositorys', 'details': 'Liste/Details', 'content': 'Detailtext'}


def repository_rows(document, session, *, width, height, now, frame):
    repos, selected = session.repositories(document), session.selected(document)
    visible = max(1, min(6, (height - 16) // 3))
    index = repos.index(selected) if selected else 0
    first = max(0, index - visible + 1)
    name_width = min(20, max(12, width // 5))
    exchange_width = min(30, max(18, width // 4))
    last_width = 21 if width >= 105 else 0
    state_width = max(12, width - name_width - exchange_width - last_width - 8)
    rows = [[('  ' + fit('Repository', name_width) + '  ' + fit('PatchHarbor aktuell', state_width) +
              '  ' + fit('Exchange', exchange_width) + ('  Letzter Execute*' if last_width else ''), 'title')]]
    for repo in repos[first:first+visible]:
        text, status, run = repository_status(repo, document, now)
        if run:
            data = run['data']
            label = operation(run)
            if data.get('bundle_number'):
                label = ('Result zu #' if label.startswith('Result') else 'Task #') + data['bundle_number']
                if data.get('task_sha256'):
                    label += ' ' + short_id(data['task_sha256'])
            if data.get('entrypoint_name') and run.get('activity', {}).get('code', run.get('phase')) == 'entrypoint':
                text = label + ' · ' + data['entrypoint_name']
            else:
                text = label + ' · ' + text
        exchange, exchange_style = exchange_status(repo, document, now)
        last, last_style = last_result(repo, document, now)
        marker = '› ' if repo is selected else '  '
        row = [(marker + fit(repo['name'], name_width) + '  ', 'selected' if repo is selected else ''),
               (fit(symbol(status, frame) + ' ' + text, state_width) + '  ', status),
               (fit(exchange, exchange_width), exchange_style)]
        if last_width:
            row.append(('  ' + fit(symbol(last_style) + ' ' + last, last_width), last_style))
        rows.append(row)
    if not repos:
        rows.append([('Keine registrierten Ziele im Filter.', 'unknown')])
    elif height >= 20:
        runs = active_runs(document, selected['repo_id'], now)
        candidate = document.get('repository_views', {}).get(selected['repo_id'], {}).get('candidate')
        context = operation(runs[0], session.full_identifiers) if runs else package_label(candidate, session.full_identifiers) if candidate else ''
        rows.append([('  ' + (context + ' · ' if context else '') + (selected.get('exchange') or 'kein Exchange'), 'unknown')])
    return rows


def overview_details(selected, document, session, now):
    if not selected:
        return []
    lines = [(selected['path'], 'title')]
    text, status, run = repository_status(selected, document, now)
    lines.append((text, status))
    if run:
        lines += [(operation(run, session.full_identifiers), 'running'),
                  ('Entrypoint: ' + (run['data'].get('entrypoint_name') or 'noch nicht bestimmt'), ''),
                  ('Lauf: ' + str(run['data'].get('run_id') or run['instance_id']), 'unknown')]
    latest, style = last_result(selected, document, now)
    lines.append(('Letzter beobachteter Execute: ' + latest, style))
    summary = document.get('repository_views', {}).get(selected['repo_id'], {})
    candidate = summary.get('candidate')
    if candidate:
        lines.append(('Beobachteter Kandidat: ' + package_label(candidate, session.full_identifiers), 'title'))
    if summary.get('observed_at'):
        lines.append(('Exchange-Bestand: ' + age(summary['observed_at'], now), 'unknown'))
    lines += [('Repository-ID: ' + selected['repo_id'], 'unknown'),
              ('Registrierung: ' + selected.get('registration', 'unbekannt'), 'unknown')]
    if session.show_git:
        lines += [('Git: ' + selected.get('git_status', 'unknown'), git_semantic(selected)),
                  ('Staged / unstaged / untracked: ' + ' / '.join(str(selected.get(k, '—')) for k in ('staged', 'unstaged', 'untracked')), 'unknown'),
                  ('Commit: ' + str(selected.get('commit') or '—'), 'unknown'),
                  ('Fingerprint: ' + str(selected.get('fingerprint') or '—'), 'unknown')]
    for error in (selected.get('error'), summary.get('error'), *(summary.get('errors') or [])):
        if error:
            lines.append((error, 'warning'))
    return lines


def exchange_details(document, session, now, frame):
    repos = session.repositories(document)
    groups = {}
    for repo in repos:
        groups.setdefault(repo.get('exchange'), []).append(repo)
    lines = []
    for path, owners in sorted(groups.items(), key=lambda item: item[0] or ''):
        targets = watcher_targets(document, exchange=path, now=now) if path else []
        availability = next((e for e in document.get('exchanges', []) if e['path'] == path), {})
        missing = availability.get('available') is False and not document.get('stale')
        status = 'nicht erreichbar' if missing else 'überwacht' if targets else 'Überwachung nicht bestätigt'
        lines.append(((path or 'Kein Exchange eingerichtet') + ' · ' + status, 'failure' if missing else 'title'))
        for repo in owners:
            text, style, run = repository_status(repo, document, now)
            if run:
                text = operation(run, session.full_identifiers) + ' · ' + text
            exchange, _ = exchange_status(repo, document, now)
            lines.append(('  ' + symbol(style, frame) + ' ' + repo['name'] + ' · ' + text + ' · ' + exchange, style))
    return lines


def lines(document, session, *, width=100, height=35, now=None, frame=0, help_open=False):
    now = now or datetime.now(timezone.utc)
    watcher, watcher_style = watcher_line(document, now)
    result = [[('PATCHHARBOR / MONITOR', 'title'), (' · ' + now.astimezone().strftime('%Z') + ' · ' + ('volle IDs' if session.full_identifiers else 'kurze IDs'), 'unknown')],
              [(watcher, watcher_style)], *timeline(document, session, now=now, frame=frame, width=width)]
    result += repository_rows(document, session, width=width-1, height=height, now=now, frame=frame)
    tabs = ('1 Übersicht  2 Exchanges  3 Bundles  4 Verlauf  5 Logs  6 Live  7 Live-Log'
            if width >= 80 else '1–7 Ansichten · ? Tastaturhilfe')
    result += [[(tabs, 'title')],
               [(f'Ansicht: {VIEW_NAMES[session.view]} · Fokus: {FOCUS_NAMES[session.focus]} · Suche: {session.match or "—"}', 'unknown')]]
    selected = session.selected(document)
    if help_open:
        body = [('Tab: Repository / Liste / Detailtext · Pfeile, j/k, PgUp/PgDn: bewegen', ''),
                ('1–7: Ansicht · l: zum aktiven Vorgang · v: kurze/volle IDs', ''),
                ('g: Git-Details · a: Archiv · /: Suche · s: Sortierung', ''),
                ('r: aktualisieren · ?: Hilfe schließen · q: nur diesen Viewer schließen', ''),
                ('✓ Erfolg · × Fehler · Spinner aktiv · Lila Vorschau · Grau unbekannt/wartend', ''),
                ('* Letzter Execute aus beobachteten Nachweisen; Historie kann unvollständig sein.', 'unknown')]
    elif session.view == 'exchanges':
        body = exchange_details(document, session, now, frame)
    elif session.view in ('live', 'live-logs'):
        body = live_lines(document, session, height=height)
    elif session.view in ('bundles', 'history', 'logs'):
        body = artifact_lines(document, session, height=height)
    else:
        body = overview_details(selected, document, session, now)
    body += [(error, 'warning') for error in document.get('errors', [])]
    if document.get('stale'):
        body.insert(0, ('VERALTET: ' + str(document.get('error') or 'Quelle nicht aktuell'), 'warning'))
    formatted = []
    for text, style in body:
        formatted += [[(part, style)] for part in wrap(human_text(text, full=session.full_identifiers, now=now), width-1)] or [[('', style)]]
    if not help_open and (session.focus == 'content' or session.focus == 'details' and session.view in ('overview', 'exchanges', 'logs', 'live-logs')):
        offset = min(session.offsets.get(session.view, 0), max(0, len(formatted)-1))
        formatted = formatted[offset:]
    available = max(0, height - len(result) - 2)
    result += formatted[:available]
    keys = ('Tab Fokus · ↑↓ j/k · v IDs · g Git · l aktiv · r neu · ? Hilfe · q' if width >= 80
            else 'Tab Fokus · 1–7 Ansicht · v IDs · ? Hilfe · q Ende')
    result += [[(keys, 'title')], [('* Letzter Execute aus beobachteten Nachweisen', 'unknown')]]
    return result[:height]


def render(document, session, *, width=120, height=40, color=False, now=None, frame=None, help_open=False):
    frame = int(time.monotonic() * 8) if frame is None else frame
    return '\n'.join(render_spans(row, max(1, width-1), color) for row in
                     lines(document, session, width=width, height=height, now=now, frame=frame, help_open=help_open))
