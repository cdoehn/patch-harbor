# Native Watcher-Ereignisadapter – WE-2

Die Adapter sind durch WE-2 angewendet. WE-3 bindet sie im Development an
die CLI mit fünf Sekunden Ruhefrist, Worker-Steuerung und
Konfigurationsaktualisierung an. Die Module
sind interne Watcher-Bausteine und keine zusätzliche öffentliche Apply-API.
`events.py` enthält den plattformneutralen Vertrag. Die Factory und nativen
Systemaufrufe liegen getrennt unter `patchharbor_watcher.platform`; Core
importiert keine Watcher-Module. Die Factory lädt die native Bibliothek erst
beim Öffnen einer Quelle.

`patchharbor_watcher.open_event_source(tuple_of_absolute_paths)` öffnet
eine feste Generation flacher Verzeichnisbeobachtungen. Der Aufrufer bezieht
Exchange-/Kontrollpfade zuvor aus Core. Nur vorhandene, physisch kanonische
Verzeichnisse sind zulässig. Bei Änderungen der Zielmenge wird eine neue Quelle
geöffnet; eine alte Beobachtung erteilt niemals eine Apply-Freigabe.

- `read(timeout=None)` wartet blockierend auf relevante Ereignisse. Ein endlicher
  Timeout dient später der offenen Ruhefrist, nicht einem periodischen Scan.
- `wake()` unterbricht das Warten. Ein Controller darf `close()` aus einem anderen
  Thread aufrufen; der Reader kehrt zurück und Ressourcen werden freigegeben.
  Signalhandler sollen nur aufwecken; Schließen erfolgt außerhalb des Readers.
- `()` bedeutet Timeout, Aufwecken oder geschlossene Quelle. Backend-Fehler
  werden als `EventBackendError` mit Kategorie und gegebenenfalls nativem Code
  gemeldet. Der Aufrufer darf diese nicht als gesunden Leerlauf behandeln.
- `DirectoryEvent` unterscheidet `CHANGED`, `ROOT_INVALIDATED` und `OVERFLOW`.
  Ein globaler Überlauf hat `directory=None`; er betrifft alle offenen Wurzeln.
  Namen sind Hinweise auf direkte Einträge und keine validierten Bundle-Pfade.

Die Adapter lesen weder Bundle-Inhalte noch Registry-/Konfigurationsdateien.
Sie listen keine Verzeichnisinhalte auf. Zusätzlich zu den Wurzeln beobachten
sie deren Eltern und Vorfahren flach, gefiltert auf die jeweiligen Pfadkomponenten.
Dadurch werden auch Umbenennung oder Austausch eines Vorfahren erkennbar.
Unbeteiligte Nachbareinträge gelangen nicht zum Aufrufer. Einrichten und relevante
Elternereignisse dürfen Verzeichnismetadaten prüfen; es gibt keinen Leerlauftimer.

Pro Rückgabe werden höchstens 512 unterschiedliche Hinweise behalten; darüber
folgt ein globaler Überlaufhinweis. Doppelte Hinweise werden zusammengefasst.
Nach Verlust oder Austausch muss der Aufrufer durch Core revalidieren, neu
beobachten und die volle Ruhefrist einhalten. Hier findet noch kein Rescan statt.

## Linux

`inotify` verwendet einen nicht blockierenden Descriptor und einen blockierenden
Selector; eine private Pipe weckt ihn auf. Die Maske enthält direkte Create-/Write-/
Delete-/Rename-/Attributänderungen und den Verlust der Wurzel. Öffnen, Lesen und
Schließen ohne Schreibzugriff sind keine Auslöser. Es werden keine rekursiven
Watches angelegt. Queue-Überlauf und verlorene Watches werden ausdrücklich
weitergegeben. Die Descriptoren bleiben bis zum Ende des Readers gültig.
Grundlage: [Linux-inotify-Vertrag](https://man7.org/linux/man-pages/man7/inotify.7.html).

## Windows

`ReadDirectoryChangesW` verwendet `bWatchSubtree=False`, DWORD-ausgerichtete
Puffer und einen gemeinsamen I/O-Completion-Port. Der Filter enthält keine
Zugriffszeitmeldungen. Metadatenmeldungen zu bestehenden direkten Unterordnern
lösen keinen Exchange-Scan aus; deren Anlegen, Entfernen oder Umbenennen bleibt
relevant. Fertige Puffer werden vor erneuter Anmeldung kopiert.
Grundlage: [ReadDirectoryChangesW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-readdirectorychangesw)
und [Completion-Port-Empfang](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getqueuedcompletionstatus).

Beim Schließen werden ausstehende Operationen abgebrochen und ihr Abschluss
abgewartet, bevor Puffer, OVERLAPPED-Strukturen und Handles freigegeben werden.
Eine bereits abgeschlossene Operation kann dem Abbruch zuvorgekommen sein.
Grundlage: [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex).

## Nachweise und Grenzen

`tests/test_watcher_events.py` prüft binäre Ereignisformate, Routing, Begrenzung,
Fehler, Win32-Aufrufparameter und Ressourcenlebenszyklus mit kontrollierten
Completion-Ereignissen. `tests/test_watcher_events_native.py` führt auf der
jeweiligen unterstützten Plattform echte Dateioperationen, flache Beobachtung,
atomaren Austausch, Root-/Vorfahrenwechsel sowie Stop im Leerlauf aus. Zusätzliche
Linux-Fälle prüfen Descriptorfreigabe, Initialisierungs- und Empfangsfehler.

Die lokalen Nachweise stammen von Linux. Native Windows-Nachweise stehen bis zur
vorgesehenen CI aus; Simulationen gelten nicht als Windows-Abnahme. Alle nativen
Tests bleiben für die vollständigen seriellen und parallelen CI-Suiten aktiviert.

Keine neuen Laufzeitabhängigkeiten, kein automatischer Polling-Fallback und
keine neue Termux-Service-Zusage. Netzwerk-/virtuelle Dateisysteme und Änderungen
ohne unterstützte OS-Ereignisse erhalten keine pauschale Erkennungsgarantie.
Core muss weiterhin Inhalt, Pfade, Fingerprint und Replay unabhängig prüfen;
manueller Apply und der dokumentierte Wheel-/Runtime-Fallback bleiben verfügbar.

Weitere Betriebs- und Abnahmedetails: [Ereignis-Watcher](watcher-events.md).
