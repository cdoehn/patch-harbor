"""Five fixed activity rows: two observations, current state, two forecasts."""
from patchharbor.monitor_format import age, fit, human_text, local_time, symbol
from patchharbor.monitor_status import activity, activity_text, active_runs, instances, live, operation, repo_name


def focus_instance(document, now=None):
    runs = active_runs(document, now=now)
    if runs:
        return runs[0]
    watchers = [r for r in instances(document) if r['kind'] == 'watcher' and live(r, document, now)]
    if watchers:
        return sorted(watchers, key=lambda r: (r.get('started_at', ''), r['instance_id']))[0]
    return max(instances(document), key=lambda r: r.get('facts_updated_at', ''), default=None)


def watcher_line(document, now=None):
    rows = [r for r in instances(document) if r['kind'] == 'watcher' and live(r, document, now)]
    if not rows:
        return 'Watcher: keine aktuelle Beobachtung', 'unknown'
    texts = []
    for row in rows[:2]:
        text = activity(row)['message']
        if row.get('data', {}).get('last_error'):
            text += ' · letzter Fehler vorhanden'
        if any(t.get('dirty') for t in row.get('data', {}).get('targets', [])) and row.get('phase') == 'applying':
            text += ' · weitere Prüfung vorgemerkt'
        texts.append(text)
    count = len(active_runs(document, now=now))
    text = 'Watcher: ' + ' / '.join(texts)
    if len(rows) > 2:
        text += f' · +{len(rows)-2} weitere'
    text += (' · 1 Vorgang aktiv' if count == 1 else f' · {count} Vorgänge aktiv') if count else ''
    text += ' · Stand ' + age(min(r['updated_at'] for r in rows), now)
    return text, 'failure' if any(r.get('data', {}).get('last_error') for r in rows) else 'running' if count else 'unknown'


def forecast(row, document, now=None):
    unknown = ('Weiterer Ablauf noch offen', 'unknown')
    if not row or not live(row, document, now):
        return [unknown, unknown]
    item, data = activity(row), row.get('data', {})
    code = item['code']
    if item['status'] == 'failure' and code != 'entrypoint':
        return [unknown, unknown]
    if row['kind'] == 'watcher':
        if code.endswith('-lock') or code in ('lock-held', 'lock-probe'):
            labels = ('Erneut prüfen, ob Sperre frei ist', 'Bei freier Sperre: Exchange prüfen')
        elif code in ('quiet', 'ready', 'pending', 'changed', 'refreshing', 'subscribing'):
            return [('Voraussichtlich: Exchange prüfen', 'future'), unknown]
        elif code in ('watching', 'no-candidate', 'waiting-change'):
            labels = ('Auf nächste Änderung warten', 'Nach Änderung: Ruhefrist abwarten')
        elif code == 'draining':
            return [('Nach Apply-Abschluss: Watcher beenden', 'future'), unknown]
        else:
            return [unknown, unknown]
    elif data.get('dry_run'):
        return [('Voraussichtlich: Validierung abschließen', 'future'), unknown]
    elif code in ('entrypoint', 'result-capture'):
        labels = ('Result-Bundle erzeugen', 'Result-Bundle prüfen')
    elif code == 'result-write':
        labels = ('Result-Bundle prüfen', 'Result-Bundle veröffentlichen')
    elif code == 'result-verify':
        labels = ('Result-Bundle veröffentlichen', 'Vorgang abschließen')
    elif code == 'result-publish':
        return [('Voraussichtlich: Vorgang abschließen', 'future'), unknown]
    elif code in ('prepare', 'interpreter', 'payload'):
        labels = ('Bei erfolgreicher Vorbereitung: Entrypoint starten', 'Nach Entrypoint: Result erzeugen')
    elif row['kind'] == 'bundle':
        labels = ('Repository-Zustand erfassen', 'Result-Bundle schreiben')
    elif code in ('binding', 'recheck', 'repository', 'repository-lock'):
        labels = ('Bei passender Bindung: Dateien übernehmen', 'Danach: Entrypoint starten')
    else:
        return [unknown, unknown]
    return [('Voraussichtlich: ' + label, 'future') for label in labels]


def timeline(document, session, *, now=None, frame=0, width=120):
    row = focus_instance(document, now)
    full = session.full_identifiers
    if row is None:
        return [[('--:--:--  ·  ' + text, 'unknown')] for text in
                ('Noch kein Verlauf beobachtet', 'Noch kein Verlauf beobachtet',
                 'Aktueller Vorgang unbekannt', 'Weiterer Ablauf noch offen', 'Weiterer Ablauf noch offen')]
    current = activity(row)
    history = [(r, event) for r in instances(document) for event in r.get('history', [])
               if (r['instance_id'] == row['instance_id'] or row['kind'] == 'watcher')
               and event['at'] <= current['at']]
    if row['kind'] == 'watcher':
        history += [(r, activity(r)) for r in instances(document) if r.get('completed')
                    and activity(r)['at'] <= current['at']]
    history.sort(key=lambda pair: (pair[1]['at'], pair[1]['sequence']))
    rows = []
    for old, event in history[-2:]:
        status = event['status'] if event['status'] != 'running' else 'unknown'
        label = event['message']
        if old['kind'] != 'watcher' and (old.get('data', {}).get('repo_id') or old.get('data', {}).get('repository_path')):
            label = repo_name(old, document) + ' · ' + label
        rows.append([(fit(local_time(event['at'], now), 12), 'unknown'),
                     (symbol(status) + '  ' + human_text(label, full=full, now=now), status)])
    while len(rows) < 2:
        rows.insert(0, [('--:--:--    ·  Kein früherer Schritt beobachtet', 'unknown')])
    status = current['status']
    text = activity_text(row, now)
    if row['kind'] != 'watcher':
        label = operation(row, full)
        if width < 85:
            data = row.get('data', {})
            if row['kind'] == 'apply' and data.get('bundle_number'):
                label = ('Result zu #' if current['code'].startswith('result-') else 'Patch #') + data['bundle_number']
            if current['code'] == 'entrypoint' and current['status'] == 'running':
                text = (data.get('entrypoint_name') or 'Entrypoint') + ' läuft'
        text = repo_name(row, document) + ' · ' + label + ' · ' + text
    if not live(row, document, now) and not row.get('completed'):
        status, text = 'unknown', 'VERALTET · ' + text
    elif row.get('completed') and status == 'running':
        status = 'unknown'
    rows.append([(fit(local_time(current['at'], now), 12), 'unknown'),
                 (symbol(status, frame) + '  ' + human_text(text, full=full, now=now), status)])
    rows += [[(fit('--:--:--', 12), 'unknown'), ('   ' + text, style)] for text, style in forecast(row, document, now)]
    return rows
