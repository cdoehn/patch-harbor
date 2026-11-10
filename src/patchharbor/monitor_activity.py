"""Bounded factual activity records; never infer work inside an entrypoint."""
from __future__ import annotations

import re

HISTORY_LIMIT = 32
STATUSES = frozenset({'running', 'success', 'failure', 'waiting', 'unknown'})
WATCH_LABELS = {
    'starting': 'Watcher startet', 'registry': 'Registrierung wird gelesen',
    'configuration': 'Konfigurationen werden gelesen', 'targets': 'Exchanges werden ermittelt',
    'subscribing': 'Verzeichnisüberwachung wird eingerichtet',
    'watching': 'Wartet auf Änderungen', 'no-targets': 'Keine überwachbaren Exchanges',
    'refreshing': 'Überwachungsziele werden aktualisiert',
    'changed': 'Änderung im Exchange erkannt', 'quiet': 'Wartet auf Ruhe im Exchange',
    'ready': 'Exchange-Prüfung bereit', 'overflow': 'Ereignisüberlauf; erneute Prüfung',
    'replaced': 'Verzeichnis geändert; Überwachung erneuern',
    'worker-start': 'Apply-Prozess wird gestartet', 'applying': 'Apply aktiv',
    'completion': 'Apply-Rückmeldung wird ausgewertet',
    'no-candidate': 'Kein ausführbarer Patch gefunden', 'pending': 'Weitere Prüfung vorgemerkt',
    'waiting-change': 'Wartet nach Fehler auf eine neue Änderung',
    'registry-lock': 'Wartet auf Registrierungssperre',
    'repository-lock': 'Wartet auf Repository-Sperre',
    'exchange_state-lock': 'Wartet auf Exchange-Statussperre',
    'lock-probe': 'Sperre wird erneut geprüft', 'lock-free': 'Sperre freigegeben',
    'lock-held': 'Sperre weiterhin belegt', 'probe-failed': 'Sperrprüfung fehlgeschlagen',
    'configuration-error': 'Konfiguration oder Exchange nicht verfügbar',
    'worker-error': 'Apply-Prozess oder Rückmeldung fehlgeschlagen',
    'watcher-error': 'Watcher fehlgeschlagen', 'stopping': 'Beenden angefordert',
    'draining': 'Wartet vor dem Beenden auf den Apply', 'stopped': 'Watcher beendet',
}
PHASES = {
    'DISCOVER': ('discovery', 'Exchange-Konfiguration wird gelesen'),
    'SCAN': ('scan', 'Exchange wird durchsucht'),
    'IDENTIFY': ('package-check', 'Bundle-Inhalt wird geprüft'),
    'MANIFEST': ('package-check', 'Patch-Manifest wird geprüft'),
    'HANDOFF': ('package-check', 'Bundle-Begleitdaten werden geprüft'),
    'SHA256': ('digest', 'Bundle-Prüfsumme geprüft'),
    'PATCH': ('package-check', 'Patch-Bundle geprüft'),
    'SELECT': ('selection', 'Passender Patch wird ausgewählt'),
    'MATCH': ('selection', 'Passender Patch gefunden'),
    'SKIP': ('skipped', 'Bundle übersprungen'),
    'REPO': ('repository', 'Zielrepository wird ermittelt'),
    'LOCK': ('repository-lock', 'Repository-Sperre wird geprüft'),
    'STATE': ('state', 'Repository- und Exchange-Zustand wird erfasst'),
    'BINDING': ('binding', 'Repository-Bindung wird geprüft'),
    'RECHECK': ('recheck', 'Zustand wird vor Übernahme erneut geprüft'),
    'PREPARE': ('prepare', 'Entrypoint wird vorbereitet'),
    'SCRIPT': ('interpreter', 'Entrypoint und Interpreter werden geprüft'),
    'PAYLOAD': ('payload', 'Patch-Dateien werden übernommen'),
    'EXEC': ('entrypoint', 'Entrypoint läuft'),
    'TIMEOUT': ('entrypoint', 'Entrypoint wegen Zeitüberschreitung beendet'),
    'INTERRUPT': ('entrypoint', 'Entrypoint unterbrochen'),
    'BUNDLE': ('result-capture', 'Result-Bundle wird vorbereitet'),
    'SNAPSHOT': ('result-capture', 'Repository-Zustand für Result wird erfasst'),
    'RESULT-ZIP': ('result-write', 'Result-Bundle wird geschrieben'),
    'VERIFY': ('result-verify', 'Result-Bundle wird geprüft'),
    'PUBLISH': ('result-publish', 'Result-Bundle wird veröffentlicht'),
    'RECOVERY': ('recovery', 'Nachweise früherer Versuche werden geprüft'),
    'ARCHIVE': ('archive', 'Überholte Bundles werden geprüft und archiviert'),
    'DRY-RUN': ('dry-run', 'Validierung abgeschlossen · Dry-run'),
}


def declared_bundle_number(content):
    """Read only an unambiguous literal handoff number, never an outcome."""
    values = set(re.findall(rb'PATCHHARBOR-BUNDLE-NR:[ \t]*([0-9]{3})(?![0-9])', content[:128*1024]))
    return next(iter(values)).decode('ascii') if len(values) == 1 else None


def record_activity(document, code, status, message, stamp):
    previous = document.get('activity')
    message = str(message)[:512]
    if previous and (previous['code'], previous['status'], previous['message']) == (code, status, message):
        return
    sequence = previous['sequence'] + 1 if previous else 1
    since = previous['since'] if previous and previous['code'] == code else stamp
    if previous and previous['code'] != code:
        # A transition alone does not prove that the preceding operation succeeded.
        document['history'] = (document.get('history', []) + [dict(previous)])[-HISTORY_LIMIT:]
    document['activity'] = dict(sequence=sequence, at=stamp, since=since,
                                code=code, status=status, message=message)


def activity_event(event):
    """Consume Core's structured events, never arbitrary process output."""
    if event.phase not in PHASES or event.level == 'detail':
        return None
    code, label = PHASES[event.phase]
    status = {'success': 'success', 'error': 'failure', 'warning': 'unknown'}.get(event.level, 'running')
    if event.phase == 'EXEC':
        if event.message.startswith('Interpreter completed with exit '):
            label = 'Entrypoint beendet · Exit ' + event.message.rsplit(' ', 1)[-1]
        elif event.message.startswith('Start '):
            label, status = 'Entrypoint wird gestartet', 'running'
        else:
            status = 'running'
    elif event.phase in ('TIMEOUT', 'INTERRUPT'):
        status = 'failure'
    elif event.phase == 'RESULT-ZIP':
        # Success of one ZIP member is not success of the entire Result.
        status = 'running'
    elif event.phase == 'SELECT' and event.message.startswith('No eligible patch'):
        code, label, status = 'no-candidate', 'Kein ausführbarer Patch gefunden', 'waiting'
    elif event.phase == 'SKIP':
        status = 'unknown'
    elif event.phase == 'PUBLISH' and event.level == 'success':
        label = 'Result-Bundle veröffentlicht'
    elif event.phase == 'PAYLOAD' and event.level == 'success':
        label = 'Patch-Dateien übernommen'
    elif event.phase == 'BINDING' and event.level == 'success':
        label = 'Repository-Bindung stimmt überein'
    elif event.phase == 'BINDING' and event.level == 'error':
        label = 'Repository-Bindung stimmt nicht überein'
    elif status == 'success':
        label = label.replace('wird ', '').replace('werden ', '')
    return code, status, label
