# Ereignisgesteuerter Exchange-Watcher

Der Development-Stand von WE-3/WE-4 verwendet native Dateisystemereignisse.
WE-0 bis WE-4 und die Korrekturen aus Bundle 020/021 sind durch tatsächliche
Results bestätigt. Die Windows-E2E-Prüfungen bestehen. Bundle 022 korrigiert
die Prüfung einer Windows-Umbenennungssperre; sein Apply und die abschließende
native Windows-Abnahme stehen noch aus.
Produktversion und Tags ändern sich dadurch nicht.

## Betrieb

`patchharbor-watcher` beobachtet die durch Core gelieferten Exchanges aller
registrierten Repositories. Das Arbeitsverzeichnis begrenzt die Auswahl nicht.
Linux verwendet inotify, Windows ReadDirectoryChangesW; zusätzliche
Laufzeitabhängigkeiten sind nicht erforderlich.

Jede Wurzel erhält eine monotone Ruhefrist von fünf Sekunden. Direkte
Dateiänderungen setzen sie zurück. Bei Start werden zuerst Beobachtungen
geöffnet und danach bestehende Dateien zur ersten Prüfung vorgemerkt. Ohne
Änderung oder offene Arbeit wartet der Prozess blockierend; es gibt weder einen
sekündlichen Exchange-Scan noch regelmäßige Workerstarts. Lesen und Schreiben
innerhalb bestehender Unterordner, etwa `reports/`, lösen keine Prüfung aus.

Die Ruhefrist bezieht sich auf eingegangene Dateisystemereignisse. Unter
Windows können Dateicaches Schreibmeldungen verzögern. Die Frist ersetzt keine
Fertigmeldung eines Downloads: vollständige Bundles außerhalb des Exchange-Roots
bereitstellen und atomar hineinverschieben. Paketintegrität und stabilen
Dateizustand prüft Core bei jeder Verarbeitung erneut.

Die bisherige Option `--poll-interval` wird abgewiesen. Unveränderte systemd-
Units benötigen keine neuen Parameter. Nach Installation des neuen Stands den
Watcher neu starten, sobald ein laufender Apply beendet ist. Die Bundle-
Auslieferung selbst ersetzt keine global installierte Engine.

## Ablauf und Zuständigkeit

Der Hauptthread verarbeitet Ereignisse. Ein einzelner Hilfsthread wartet auf
den bestehenden isolierten Apply-Prozess; weitere Worker starten erst danach.
Die Änderungen einer neuen Generation bleiben erhalten, wenn ein älterer
Auftrag abschließt. Ein belegter Verbrauch einer Patch-Identität erlaubt einen
Nachlauf für weitere Kandidaten, unter derselben Ruhebedingung. Ein leeres
Result der Discovery beendet diesen Bedarf. Tatsächlich fehlgeschlagene
Identitäten werden von Core weiterhin nicht automatisch erneut versucht.

Der private Worker erhält nur einen versionierten, begrenzten JSON-Scope mit
vollständigen physischen Wurzeln und Repository-IDs. Er erhält keinen expliziten
Kandidatenpfad. Core revalidiert Konfiguration, Identität, Inhalte, Fingerprint,
Locks und Replay. `watcher_progress` ergänzt ausschließlich die private
Worker-Antwort; öffentliche CLI- und persistierte Result-Verträge bleiben gleich.

Bei bekannten Sperren erfolgen nur Bereitschaftsprüfungen nach 5, 10, 20, 40,
80, 160 und anschließend jeweils 300 Sekunden. Dabei werden keine Bundles
untersucht. Nach Freigabe muss auch die Ruhefrist erfüllt sein. Diese Prüfung
reserviert keine Sperre; Apply erwirbt seine Locks selbst erneut.

## Änderungen und Fehler

Registry- und Konfigurationsdateien werden über eng gefilterte Elternpfade
beobachtet. Änderungen erneuern die Core-Ziele und eröffnen eine volle Ruhefrist.
Beschädigte Konfiguration sperrt Apply bis zu einem Reparaturereignis; sie wird
nicht verändert. Für fehlende Exchanges liefert Core lediglich unverbindliche
Beobachtungspfade in `WatchControlPaths.exchange_paths`. Deren Wiederkehr löst
erneute Zielprüfung und Beobachtung aus. Ein solcher Pfad ist keine Scanfreigabe.

Root-Austausch und Ereignisverlust erneuern Beobachtung und Ruhefrist. Ein
Backend-Ausfall wird als Fehler sichtbar; es gibt keinen stillen Polling-Fallback.
Ein Stoppsignal weckt auch ereignisloses Warten. Weitere Worker werden verhindert;
ein bereits laufender Apply behält seine bisherige Prozess-/Signalbehandlung.

Unter Windows kann die laufende Beobachtung das Umbenennen eines übergeordneten
Exchange-Ordners verhindern. Für ein geplantes Verschieben zuerst einen
laufenden Apply beenden lassen und den Watcher geordnet stoppen. Nach dem
Verschieben die Exchange-Konfiguration prüfen und den Watcher erneut starten.
Eine vom Betriebssystem verweigerte Umbenennung verändert die beobachtete
Wurzel nicht; ihre Ereigniserkennung bleibt aktiv.

Git-Änderungen außerhalb des Exchanges lösen keine Prüfung aus. Für ein dadurch
passend gewordenes Bundle sind ein neues Exchange-Ereignis, Watcher-Neustart
oder bewusster manueller Apply möglich. Manuelle Verarbeitung und der vorhandene
Wheel-/Offline-Runtime-Fallback bleiben erhalten. Netzwerk-/virtuelle
Dateisysteme erhalten keine weitergehende Garantie als ihre nativen Ereignisse.

## Nachweise

| Vertrag | Prüfung |
| --- | --- |
| Fünf Sekunden, Timergrenze, unabhängige Wurzeln, Generationen, Nachlauf, Sperr-Backoff und Konfigurationswechsel | `tests/test_watcher_scheduling.py` |
| Strikte Scope-/Fortschrittsdaten, leere Scopes, Beobachtung fehlender Wurzeln | `tests/test_watcher_protocol.py` |
| Native Ereignisse, Decoder, Ressourcen, Root-/Vorfahrenersatz, Stop und Überlauf | `tests/test_watcher_events.py`, `tests/test_watcher_events_native.py` |
| Echte Ruhefristen, Änderungen während Worker, ruhiger Nachlauf, echte erfolgreiche/fehlgeschlagene Applies und unabhängiger Download | `tests/test_watcher_event_loop_e2e.py` |
| Isolierter installierter Wheel, echte native Warteoperation und tatsächlicher scoped Worker-Apply | Packaging-Gate mit `tests/watcher_installed_probe.py` |
| Bindung, Replay, Locks, fremde Exchanges und Mutation-Gates | vorhandene vollständige Core-/E2E-/Plattform-Suiten |
| Offline-Runtime und bisheriger Fallback | vorhandene Runtime-/Bootstrap-Suiten |

Linux-Nachweise stammen aus den lokalen parallelen Läufen. Simulationen sind
kein Windows-Nachweis. Der tatsächliche Apply von Bundle 022 und der manuelle
[CI-Lauf 37459998721](https://github.com/cdoehn/patch-harbor/actions/runs/37459998721)
bestätigen Commit `44cc77a42b492fc1f31267db5139253ef7545b9f` einschließlich aller
sechs Jobs und Windows-Packaging. Der [Plan](../planning/watcher-events/commit-plan.md)
dokumentiert Result-Bindung, vorherige Fehler und vollständigen Abschluss.
Diese Abnahme gilt für diesen Endstand; spätere Änderungen brauchen eigene
Nachweise. Für die aktive PYZ/PACK-Entwicklung startet ausschließlich Christian
die manuelle CI; die historische Bundle-Taktung ist aufgehoben.
