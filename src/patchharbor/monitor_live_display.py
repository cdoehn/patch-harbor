"""Display optional live evidence without inferring locks or progress."""
from datetime import datetime, timezone

from patchharbor.monitor_session import result_semantic


def watcher_summary(document):
    view = document.get('live_view', {})
    rows = [r for r in view.get('instances', []) if r['kind'] == 'watcher']
    active = sum(r.get('live', False) for r in rows)
    return f'{active} aktuell beobachtet' if active and not view.get('stale') else 'unbekannt / keine aktuelle Beobachtung'


def live_lines(document, session, *, height):
    view = document.get('live_view', {})
    rows, selected = session.live_instances(document), session.selected_live(document)
    lines = []
    if session.view == 'live':
        index = rows.index(selected) if selected else 0
        first = max(0, index - 2)
        for row in rows[first:first+3]:
            status = 'VERALTET / unbekannt' if view.get('stale') else 'AKTIV' if row.get('live') else 'VERALTET / unbekannt' if row.get('stale') else 'beendet'
            lines.append((f"{'>' if row is selected else ' '} {row['kind']} {row['instance_id']} · {row['phase']} · {status}",
                          'warning' if row.get('live') and not view.get('stale') else 'unknown'))
    if selected:
        data = selected['data']
        lines += [('Instanz: ' + selected['instance_id'], 'title'),
                  (f"Phase: {selected['phase']} · PID {selected['pid']} · Stand {selected['facts_updated_at']}", '')]
        if session.view == 'live-logs':
            detail = document.get('live_log_view', {})
            row = next(iter(detail.get('instances', [])), {})
            lines.append(('Live-Ausschnitt: letzte 32 KiB · Original-Log unverändert', 'warning'))
            if detail.get('stale') or row.get('stale'):
                lines.append(('VERALTET: keine aktuelle Live-Quelle', 'warning'))
            lines += [(line, '') for line in row.get('log_tail', '').splitlines()[session.offsets.get('live-logs', 0):]]
        elif selected['kind'] == 'watcher':
            targets = data.get('targets', [])
            lines.append((f"{len(targets)} Exchange(s) · {len(data.get('subscriptions', []))} tatsächliche Abonnements", ''))
            for target in targets:
                lock = target.get('blocked_on')
                lines.append((target['directory'] + ' · ' + (str(lock) if lock else 'kein gespeicherter Sperrhinweis'), ''))
                deadline = target.get('quiet_until')
                remaining = 'unbekannt' if deadline is None else f'{max(0, deadline - datetime.now(timezone.utc).timestamp()):.1f}s'
                lines.append((f"Ruhefrist: {remaining} · Änderung vorgemerkt: {target.get('dirty')}", ''))
            if data.get('last_error'):
                lines.insert(0, (data['last_error'], 'dirty'))
        else:
            lines += [('Run: ' + str(data.get('run_id')), ''),
                      ('Patch: ' + str(data.get('patch_sha256')), ''),
                      (f"Ursprung: {data.get('origin')} · {'DRY-RUN' if data.get('dry_run') else 'Apply'}", '')]
            timeout = data.get('effective_timeout_seconds')
            lines.append(('Wirksamer Entrypoint-Timeout: ' + (f'{timeout:g}s' if timeout is not None else 'noch nicht gestartet'), ''))
            if selected.get('live') and not view.get('stale') and timeout is not None and data.get('process_state') is None:
                started = datetime.fromisoformat(data['entrypoint_started_at'].replace('Z', '+00:00'))
                remaining = max(0, timeout - (datetime.now(timezone.utc) - started).total_seconds())
                lines.append((f"Bis Timeout höchstens {remaining:.1f}s · keine Fertigstellungsprognose", 'warning'))
            primary = data.get('primary_result') or {}
            lines.append((f"Entrypoint: {primary.get('kind', selected['phase'])} · Exit {primary.get('entrypoint_exit_code', data.get('entrypoint_exit_code', '—'))} · Result: {data.get('result_status', 'noch nicht abgeschlossen')}",
                          result_semantic({**data, 'stale': selected.get('stale') or view.get('stale')})))
    else:
        lines.append(('Keine passende Beobachtung. Ältere Prozesse publizieren noch keinen Live-Status.', 'warning'))
    for error in view.get('errors', []):
        lines.insert(0, (error, 'warning'))
    if view.get('stale'):
        lines.insert(0, ('VERALTET: ' + str(view.get('error')), 'warning'))
    return lines
