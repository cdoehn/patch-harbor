"""Read-only CLI orchestration for independent monitor sessions."""
from __future__ import annotations

import json
import os

from patchharbor.monitor_details import MonitorDetails, attach_once
from patchharbor.monitor_display import render, safe_text
from patchharbor.monitor_refresh import MonitorRefresh, snapshot_once
from patchharbor.monitor_session import MonitorSession, VIEWS
from patchharbor.platform.monitor_terminal import terminal_mode, read_key, size


def monitor_command(args, *, stdin, stdout, stderr):
    if args.json_output and not args.once:
        print('--json requires --once', file=stderr)
        return 2
    state = MonitorSession(view=args.view, match=args.match, artifact_match=args.artifact_match, include_archive=args.archive)
    if args.once:
        try:
            document = attach_once(snapshot_once(args.repo, args.exchange, args.query_timeout), state, args.query_timeout)
        except (OSError, ValueError, RuntimeError) as exc:
            document = {'format_version': 1, 'kind': 'patchharbor-monitor', 'repositories': [],
                        'exchanges': [], 'errors': [str(exc)], 'stale': True}
        print(json.dumps(document, ensure_ascii=True) if args.json_output else render(document, state), file=stdout)
        return 2 if document.get('stale') or document.get('errors') or document.get('bundle_view', {}).get('errors') or any(r.get('error') for r in document['repositories']) else 0
    if not stdin.isatty() or not stdout.isatty():
        print('monitor requires a terminal; use --once or --once --json', file=stderr)
        return 2
    refresh = MonitorRefresh(args.repo, args.exchange, interval=args.interval, timeout=args.query_timeout)
    color = not args.no_color and not args.plain and 'NO_COLOR' not in os.environ
    details = MonitorDetails(timeout=args.query_timeout, interval=max(10, args.interval))
    search = None
    help_open = False
    try:
        with terminal_mode(stdin, stdout):
            while True:
                refresh.tick()
                width, height = size()
                document = details.attach(refresh.document, state)
                display = render(document, state, width=width, height=height, color=color)
                if width < 60 or height < 15:
                    display = 'Terminal mindestens 60×15; q beendet.'
                if help_open:
                    display = ('PATCHHARBOR MONITOR\n\nTab: Fokus wechseln\nPfeile / j k: Auswahl\n'
                               '1 Übersicht / 2 Exchanges / 3 Bundles / 4 Verlauf / 5 Logs\n'
                               '6 Live-Status / 7 Live-Log\n'
                               'a Archiv ein/aus · / Suche im Fokus · Enter / Esc\n'
                               's Sortierung umkehren\nr Quellen aktualisieren\nq nur diesen Viewer schließen\n'
                               '? Hilfe schließen\n\nBeobachtungen sind keine Reservierungen.')
                if search is not None:
                    display += '\n/ ' + safe_text(search) + '  [Enter / Esc]'
                stdout.write('\x1b[H\x1b[2J' + display)
                stdout.flush()
                key = read_key(stdin)
                if search is not None:
                    if key in ('\r', '\n'):
                        setattr(state, 'artifact_match' if state.focus == 'details' and state.view in ('bundles', 'history', 'logs') else 'match', search)
                        search = None
                    elif key == '\x1b':
                        search = None
                    elif key in ('\x7f', '\b'):
                        search = search[:-1]
                    elif isinstance(key, str) and len(key) == 1 and key.isprintable() and len(search) < 256:
                        search += key
                    continue
                if key in ('q', '\x03'):
                    return 0
                if key == '?':
                    help_open = not help_open
                elif key == '\t':
                    state.focus = 'details' if state.focus == 'repositories' else 'repositories'
                elif key in ('up', 'k', 'down', 'j', 'pageup', 'pagedown'):
                    state.move(document, {'up': -1, 'k': -1, 'down': 1, 'j': 1, 'pageup': -8, 'pagedown': 8}[key])
                elif key in ('1', '2', '3', '4', '5', '6', '7'):
                    state.view = VIEWS[int(key) - 1]
                elif key == '/':
                    search = state.artifact_match if state.focus == 'details' and state.view in ('bundles', 'history', 'logs') else state.match
                elif key == 'a':
                    state.include_archive = not state.include_archive
                elif key == 's':
                    state.descending = not state.descending
                elif key == 'r':
                    refresh.tick(force=True)
                    details.attach(refresh.document, state, force=True)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        print(safe_text(exc), file=stderr)
        return 2
    finally:
        refresh.close()
        details.close()
