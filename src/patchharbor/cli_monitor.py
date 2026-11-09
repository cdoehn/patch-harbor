"""Read-only CLI orchestration for independent monitor sessions."""
from __future__ import annotations

import json
import os

from patchharbor.monitor_display import render, safe_text
from patchharbor.monitor_query import MonitorRefresh, query
from patchharbor.monitor_session import MonitorSession, VIEWS
from patchharbor.platform.monitor_terminal import terminal_mode, read_key, size


def monitor_command(args, *, stdin, stdout, stderr):
    if args.json_output and not args.once:
        print('--json requires --once', file=stderr)
        return 2
    state = MonitorSession(view=args.view, match=args.match)
    if args.once:
        try:
            document = query(args.repo, args.exchange, args.query_timeout)
        except (OSError, ValueError, RuntimeError) as exc:
            document = {'format_version': 1, 'kind': 'patchharbor-monitor', 'repositories': [],
                        'exchanges': [], 'errors': [str(exc)], 'stale': True}
        print(json.dumps(document, ensure_ascii=True) if args.json_output else render(document, state), file=stdout)
        return 2 if document.get('stale') or document.get('errors') or any(r.get('error') for r in document['repositories']) else 0
    if not stdin.isatty() or not stdout.isatty():
        print('monitor requires a terminal; use --once or --once --json', file=stderr)
        return 2
    refresh = MonitorRefresh(args.repo, args.exchange, interval=args.interval, timeout=args.query_timeout)
    color = not args.no_color and not args.plain and 'NO_COLOR' not in os.environ
    search = None
    help_open = False
    try:
        with terminal_mode(stdin, stdout):
            while True:
                refresh.tick()
                width, height = size()
                display = render(refresh.document, state, width=width, height=height, color=color)
                if width < 60 or height < 15:
                    display = 'Terminal mindestens 60×15; q beendet.'
                if help_open:
                    display = ('PATCHHARBOR MONITOR\n\nTab: Fokus wechseln\nPfeile / j k: Auswahl\n'
                               '1 Übersicht / 2 Exchanges\n/ Suche, Enter übernehmen, Esc zurück\n'
                               's Sortierung umkehren\nr Quellen aktualisieren\nq nur diesen Viewer schließen\n'
                               '? Hilfe schließen\n\nBeobachtungen sind keine Reservierungen.')
                if search is not None:
                    display += '\n/ ' + safe_text(search) + '  [Enter / Esc]'
                stdout.write('\x1b[H\x1b[2J' + display.replace('\n', '\r\n'))
                stdout.flush()
                key = read_key(stdin)
                if search is not None:
                    if key in ('\r', '\n'):
                        state.match, search = search, None
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
                    state.move(refresh.document, {'up': -1, 'k': -1, 'down': 1, 'j': 1, 'pageup': -8, 'pagedown': 8}[key])
                elif key in ('1', '2'):
                    state.view = VIEWS[int(key) - 1]
                elif key == '/':
                    search = state.match
                elif key == 's':
                    state.descending = not state.descending
                elif key == 'r':
                    refresh.tick(force=True)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        print(safe_text(exc), file=stderr)
        return 2
    finally:
        refresh.close()
