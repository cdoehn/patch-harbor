# PatchHarbor Monitor — Erweiterungsspezifikation

## Vertrag und Architektur

Diese Erweiterung wird ausdrücklich durch den Viewer-Auftrag aktiviert und
ändert keine vorhandenen Apply-/Replay-/Archivierungsregeln oder Versionen.
`patchharbor monitor` beobachtet vorhandene Daten; es registriert, reserviert,
repariert, archiviert und startet keine Applies oder Dienste. Alle gemeinsamen
Fachentscheidungen kommen aus dem Core. Terminalcode konsumiert die öffentliche
API; Beobachtung ist kein Ausführungsauftrag und keine Reservierung.

Detailentscheidungen VIEW-D1–D6 werden bereits mit dem angeforderten ersten
Plancommit festgelegt, damit sie überprüfbar sind:

1. Keine zusätzliche Laufzeitabhängigkeit: native Terminal-Eingabe auf POSIX
   und Windows hinter einer kleinen Plattformgrenze; JSON ohne TTY.
2. Neuer Einstieg `patchharbor monitor`; `--repo` (volle ID oder Pfad),
   `--exchange`, `--view`, `--interval`, `--query-timeout`, `--once`, `--json`,
   `--plain`, `--no-color`. JSON setzt `--once` voraus. Keine implizite TUI auf
   umgeleiteten Streams. Ansichten werden erst mit ihrer Implementierung angeboten.
3. UI-Einstellungen sind pro Prozess im Speicher. Keine gemeinsam beschriebene
   aktuelle Ansicht; mehrere Viewer nutzen nur lesend dieselben Quellinformationen.
4. Beobachtungen sind zeitgestempelte Momentaufnahmen. Alte Werte bleiben bei
   Fehler sichtbar, tragen aber `stale=true` und einen Fehler. Unbekannt ist
   niemals sauber, frei oder erfolgreich. Fehlende Werte sind null, nicht null Sekunden.
5. Historische Verknüpfungen brauchen vollständige IDs/Hashes und geprüfte native
   Daten. Derselbe Ausgangszustand beweist keine eindeutige Ursprungs-ZIP. Archiv
   und Verarbeitung sind unabhängig. Es gibt keine erfundene vollständige Historie.
6. Optionale Live-Publikation ist best effort, pro Instanz/Lauf getrennt und
   außerhalb beobachteter Exchanges. Fehler oder langsame Leser ändern kein
   fachliches Ergebnis. Ausgabegrenzen des Viewers kürzen nicht das echte Result-Log.

## Anzeige und Bedienung

Kopfzeile mit Watcher-Kurzstatus, Repository-Liste, Details der Auswahl, Tabs und
feste Tastaturhilfe. Tab wechselt Fokus, Pfeile/j/k und PgUp/PgDn bewegen die
Auswahl, Zahlen wechseln Ansicht, / sucht, r aktualisiert, ? zeigt Hilfe,
q beendet nur den eigenen Viewer. Auswahlidentität und Scrollposition bleiben
bei Aktualisierungen erhalten, soweit das Objekt noch im Filter liegt.

Repository clean ist grün, dirty rot (staged/unstaged/untracked separat zählen),
unbekannt grau. Ignorierte Dateien zählen nicht. Git-Zustand ist kein Apply-
Ergebnis. Result/Entrypoint-Erfolg mit Exit 0 ist grün, Fehler/nonzero/Timeout/
Abbruch rot, laufend/wartend gelb, unversucht/unbekannt grau. Texte und Exitcodes
tragen dieselbe Information ohne Farbe. Dry-run bleibt ausdrücklich erkennbar.

Ein erfolgreicher Entrypoint und fehlgeschlagene Result-Erzeugung sind zwei
getrennte Tatsachen mit rotem Gesamtausgang. Ein `attempted` beweist keinen noch
lebenden Prozess. Verbleibende Timeout-Zeit ist keine Fertigstellungsprognose.

## Ressourcen und Testgrenzen

Begrenzte Abfragen laufen außerhalb des Bildschirmthreads. Pro Quelle gibt es
höchstens eine laufende Abfrage; Fehler eines Ziels blockieren keine anderen.
Häufige UI-Neuzeichnung löst keinen vollständigen Paketscan aus. Paketinhalte und
Logs werden nur auf Bedarf geladen und begrenzt. Fremde Terminalsteuerzeichen
in Pfaden oder Logs werden vor Darstellung neutralisiert. Schmale Terminals,
Resize, Unicode, farblose Ausgabe und sauberes Wiederherstellen des Terminals
gehören zur praktischen Abnahme. Semantik, Filter, Nebenwirkungsfreiheit,
Bindungen und Parallelbetrieb erhalten Verhaltenstests.

Die vorhandene Linux-/Windows-Produktgrenze und Python >=3.10 bleiben erhalten.
Eine simulierte Plattformprüfung ist kein nativer Plattformnachweis.
