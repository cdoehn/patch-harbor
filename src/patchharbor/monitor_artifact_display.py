"""Artifact/history/log presentation from already observed facts."""
from patchharbor.monitor_session import result_semantic


def artifact_lines(document, session, *, height):
    view = document.get('bundle_view', {})
    rows = session.artifacts(document)
    selected = session.selected_artifact(document)
    lines = [(f"Pakete: {len(rows)} · Archiv: {'an' if session.include_archive else 'aus'} (a) · Suche: {session.artifact_match or '—'}", 'title')]
    if view.get('incomplete'):
        lines.append(('UNVOLLSTÄNDIG: beschädigte, ältere oder begrenzte Quellen; Auswahl nicht bewiesen.', 'warning'))
    if session.view != 'logs':
        index = rows.index(selected) if selected else 0
        visible = max(1, min(5, height // 6))
        for row in rows[max(0, index-visible+1):max(0, index-visible+1)+visible]:
            primary = row.get('primary_result', {})
            status = primary.get('kind') or row.get('replay_status') or row['kind']
            exit_code = primary.get('entrypoint_exit_code')
            lines.append((f"{'>' if row is selected else ' '} {row['name']} · {status} · Exit {exit_code if exit_code is not None else '—'} · {'ARCHIV' if row['archived'] else 'Exchange'}", 'unknown' if view.get('stale') else result_semantic(row)))
    if session.view == 'history':
        lines.insert(1, ('Verlauf aus vorhandenen Nachweisen · nicht vollständig', 'warning'))
    if selected:
        if selected.get('ambiguous_run'):
            lines.insert(1, ('MEHRDEUTIG: mehrere unterschiedliche Results derselben Run-ID', 'warning'))
        if selected.get('attempt_result_missing'):
            lines.insert(1, ('Result des letzten gespeicherten Versuchs fehlt im beobachteten Bestand.', 'warning'))
        if session.view == 'logs':
            log = document.get('log_view', {})
            lines.append((selected['name'] + ' · Run ' + str(selected.get('run_id')), 'title'))
            if log.get('truncated'):
                lines.append(('Log gekürzt: letzte 64 KiB; Original unverändert.', 'warning'))
            if log.get('error'):
                lines.append(('VERALTET: ' + log['error'], 'warning'))
            lines += [(line, '') for line in log.get('text', '').splitlines()]
        else:
            lines.append(('SHA-256: ' + str(selected.get('sha256')), ''))
            expected = selected.get('expected') or selected.get('context') or {}
            lines.append(('Repo: ' + str(selected.get('repo_id')), ''))
            lines.append(('Erwarteter Ausgang: ' + str(expected.get('base_commit')) + ' / ' + str(expected.get('state_fingerprint')), ''))
            if selected['kind'] == 'task_package':
                lines.append((selected['eligibility'], 'warning'))
                for digest in selected.get('source_candidates', []):
                    lines.append(('Passender Ausgangs-Result-Hash: ' + digest, ''))
                for digest in selected.get('result_links', []):
                    lines.append(('Zugehöriger Result-Hash: ' + digest, ''))
                lines.append((f"Passende Ausgangszustände: {len(selected.get('source_candidates', []))} (kein eindeutiger Ursprung) · Result-Nachweise: {len(selected.get('result_links', []))}", ''))
                if selected.get('attempt_run_id'):
                    lines.append(('Letzter Versuch: ' + selected['attempt_run_id'] + ' · kein Live-Nachweis', ''))
            else:
                context = selected.get('context', {})
                if context:
                    lines.append(('Result-Zustand: ' + context['base_commit'] + ' / ' + context['state_fingerprint'], ''))
                lines.append((f"Run: {selected.get('run_id')} · {'DRY-RUN / Validierung' if selected.get('dry_run') else selected.get('operation', '—')} · Result: {selected.get('result_status', 'unbekannt')}", result_semantic({**selected, 'stale': view.get('stale')})))
                if selected.get('task_sha256'):
                    lines.append(('Patch: ' + selected['task_sha256'], ''))
            if selected.get('error'):
                lines.append((selected['error'], 'dirty'))
    else:
        lines.append(('Keine Pakete im Filter / Quelle lädt.', 'warning'))
    for error in view.get('errors', []):
        lines.append((error, 'warning'))
    if view.get('stale'):
        lines.insert(1, ('VERALTET: ' + str(view.get('error')), 'warning'))
    return lines
