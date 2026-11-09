"""Human rendering; semantic observations remain color-free."""
from __future__ import annotations

import unicodedata

from patchharbor.monitor_artifact_display import artifact_lines
from patchharbor.monitor_session import git_semantic

LABELS = {'clean': 'SAUBER', 'dirty': 'DIRTY', 'unknown': 'UNBEKANNT'}
COLORS = {'clean': 32, 'dirty': 31, 'unknown': 90, 'title': 36, 'warning': 33}


def safe_text(value):
    return ''.join(c if not unicodedata.category(c).startswith('C') else '?' for c in str(value))


def crop(value, width):
    result, used = '', 0
    for char in safe_text(value):
        size = 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
        if used + size > width:
            break
        result += char
        used += size
    return result


def lines(document, session, *, width=100, height=35):
    result = [('PATCHHARBOR / MONITOR', 'title'),
              (f"Stand: {document.get('observed_at', 'lädt')} · Watcher: unbekannt", 'title'), ('', '')]
    repos = session.repositories(document)
    selected = session.selected(document)
    visible = max(1, min(8, height // 3))
    index = repos.index(selected) if selected else 0
    first = max(0, index - visible + 1)
    for row in repos[first:first + visible]:
        semantic = 'unknown' if document.get('stale') else git_semantic(row)
        count = ' / '.join(str(row.get(k)) if row.get(k) is not None else '—' for k in ('staged', 'unstaged', 'untracked'))
        marker = '> ' if row is selected else '  '
        result.append((f"{marker}{row['name']:<23.23} {LABELS[semantic]:<10} {count:<12} {row.get('exchange') or 'kein Exchange'}", semantic))
    if not repos:
        result.append(('Keine registrierten Ziele im Filter.', 'warning'))
    result += [('', ''), (f"1 Übersicht · 2 Exchanges · 3 Bundles · 4 Verlauf · 5 Logs   Ansicht: {session.view} · Fokus: {session.focus}", 'title'),
               (f"Suche: {session.match or '—'} · Sortierung {'↓' if session.descending else '↑'} · staged / unstaged / untracked", 'title')]
    if session.view == 'exchanges':
        for row in document.get('exchanges', [])[session.offsets.get('exchanges', 0):]:
            result.append((f"{row['path']} · {len(row['repository_ids'])} Repository(s) · {'erreichbar' if row['available'] else 'FEHLT'}", 'title' if row['available'] else 'warning'))
    elif session.view in ('bundles', 'history', 'logs'):
        result += artifact_lines(document, session, height=height)
    elif selected:
        result += [(selected['path'], ''), ('Repository-ID: ' + selected['repo_id'], ''),
                   ('Commit: ' + (selected.get('commit') or '—'), ''),
                   ('Fingerprint: ' + (selected.get('fingerprint') or '—'), ''),
                   ('Registrierung: ' + selected['registration'], '')]
        if selected.get('error'):
            result.append((selected['error'], 'warning'))
    for error in document.get('errors', []):
        result.append((error, 'warning'))
    if document.get('stale'):
        result.append(('VERALTET: ' + document.get('error', 'Quelle nicht aktuell'), 'warning'))
    result = result[:max(1, height - 3)]
    result += [('', ''), ('Tab Fokus · ↑↓ j/k · 1–5 Ansicht · / Suche · s Sortierung · r Aktualisieren · ? Hilfe · q', 'title'),
               ('Momentaufnahme · keine Reservierung · unbekannt ist nicht sauber', 'warning')]
    return [(crop(text, max(1, width - 1)), style) for text, style in result]


def render(document, session, *, width=120, height=40, color=False):
    return '\n'.join((f'\x1b[{COLORS[style]}m{text}\x1b[0m' if color and style in COLORS else text)
                     for text, style in lines(document, session, width=width, height=height))
