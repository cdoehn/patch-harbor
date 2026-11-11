"""Display optional live evidence without inferring locks or progress."""
from datetime import datetime, timezone
import time

from patchharbor.monitor_session import result_semantic
from patchharbor.monitor_projection import observe
from patchharbor.monitor_format import age, duration, symbol
from patchharbor.monitor_status import activity, activity_text, live, operation, repo_name


def watcher_summary(document):
    view = document.get('live_view', {})
    rows = [r for r in view.get('instances', []) if r['kind'] == 'watcher']
    active = sum(observe(r, document).current for r in rows)
    return f'{active} aktuell beobachtet' if active and not view.get('stale') else 'unbekannt / keine aktuelle Beobachtung'


def live_lines(document, session, *, height):
    view = document.get('live_view', {})
    rows, selected = session.live_instances(document), session.selected_live(document)
    lines = []
    if session.view == 'live':
        index = rows.index(selected) if selected else 0
        first = max(0, index - 2)
        for row in rows[first:first+3]:
            observation = observe(row, document)
            status = observation.status
            label = operation(row, session.full_identifiers) + ' · ' + activity_text(row)
            if row['kind'] != 'watcher':
                label = repo_name(row, document) + ' · ' + label
            if observation.stale:
                label = 'VERALTET · ' + label
            lines.append((('› ' if row is selected else '  ') + symbol(status, int(time.monotonic()*8)) + ' ' + label, status))
    if selected:
        data = selected['data']
        lines += [('Instanz: ' + selected['instance_id'], 'title'),
                  (f"{activity_text(selected)} · PID {selected['pid']} · Stand {age(selected['facts_updated_at'])}", '')]
        if session.view == 'live-logs':
            detail = document.get('live_log_view', {})
            row = next(iter(detail.get('instances', [])), {})
            lines.append(('Live-Ausschnitt: letzte 32 KiB · Original-Log unverändert', 'warning'))
            if detail.get('stale') or row.get('stale'):
                lines.append(('VERALTET: keine aktuelle Live-Quelle', 'warning'))
            lines += [(line, '') for line in row.get('log_tail', '').splitlines()]
        elif selected['kind'] == 'watcher':
            targets = data.get('targets', [])
            polling = data.get('watcher_mode') == 'poll'
            if polling:
                lines.append((f"Polling · Intervall {data['poll_interval_seconds']:g} s · {len(targets)} Exchange(s)", ''))
                due = data.get('next_poll_at')
                if due is not None:
                    lines.append(('Nächster Scan in ' + duration(max(0, due - datetime.now(timezone.utc).timestamp())), 'waiting'))
            else:
                lines.append((f"{len(targets)} Exchange(s) · {len(data.get('subscriptions', []))} tatsächliche Abonnements", ''))
            for target in targets:
                lock = target.get('blocked_on')
                lines.append((target['directory'] + ' · ' + (str(lock) if lock else 'kein gespeicherter Sperrhinweis'), ''))
                deadline = target.get('quiet_until')
                remaining = 'unbekannt' if deadline is None else duration(max(0, deadline - datetime.now(timezone.utc).timestamp()))
                if not polling:
                    lines.append((f"Ruhefrist: {remaining} · Änderung vorgemerkt: {target.get('dirty')}", ''))
            if data.get('last_error'):
                lines.insert(0, (data['last_error'], 'dirty'))
        else:
            lines += [(operation(selected, session.full_identifiers), 'title'),
                      ('Repository: ' + str(data.get('repository_path') or data.get('repo_id') or 'noch unbekannt'), ''),
                      ('Entrypoint: ' + str(data.get('entrypoint_name') or '—'), ''),
                      ('Run: ' + str(data.get('run_id')), ''),
                      ('Task: ' + str(data.get('task_sha256')), ''),
                      (f"Ursprung: {data.get('origin')} · {'DRY-RUN' if data.get('dry_run') else 'Execute'}", '')]
            timeout = data.get('effective_timeout_seconds')
            if selected['kind'] == 'execute':
                lines.append(('Wirksamer Entrypoint-Timeout: ' + (duration(timeout) if timeout is not None else 'noch nicht gestartet'), 'unknown'))
            if live(selected, document) and timeout is not None and data.get('process_state') is None:
                started = datetime.fromisoformat(data['entrypoint_started_at'].replace('Z', '+00:00'))
                remaining = max(0, timeout - (datetime.now(timezone.utc) - started).total_seconds())
                lines.append(('Bis Timeout höchstens ' + duration(remaining) + ' · keine Fertigstellungsprognose', 'unknown'))
            primary = data.get('primary_result') or {}
            if activity(selected)['code'] == 'no-candidate' or data.get('automatic_status') == 'locked':
                lines.append((activity(selected)['message'], 'waiting'))
            else:
                lines.append((f"{'Result-Bundle' if selected['kind'] == 'bundle' else 'Entrypoint'}: {primary.get('kind', selected['phase'])} · Exit {primary.get('entrypoint_exit_code', data.get('entrypoint_exit_code', '—'))} · Result: {data.get('result_status', 'noch nicht abgeschlossen')}",
                              result_semantic({**data, 'stale': selected.get('stale') or view.get('stale')})))
    else:
        lines.append(('Keine passende Beobachtung. Ältere Prozesse publizieren noch keinen Live-Status.', 'warning'))
    for error in view.get('errors', []):
        lines.insert(0, (error, 'warning'))
    if view.get('stale'):
        lines.insert(0, ('VERALTET: ' + str(view.get('error')), 'warning'))
    if view.get('incomplete'):
        lines.insert(0, ('UNVOLLSTÄNDIG: begrenzter Beobachtungsbestand.', 'warning'))
    return lines
