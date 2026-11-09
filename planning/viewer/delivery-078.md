# Viewer — vorbereitete Lieferung 078

Diese Lieferung enthält zehn geordnete Commit-Stufen: zuerst VIEW-00 mit Plan
und Spezifikation, anschließend VIEW-01.W/R/C, VIEW-02.W/R/C und VIEW-03.W/R/C.
Alle drei ursprünglich geplanten fachlichen Gruppen passen in eine ZIP.
Status dieser Datei ist PREPARED; sie ist kein Nachweis erfolgreicher Applies.

## Enthaltene Funktion

- `patchharbor monitor`: Repositorys, Exchanges, Bundles, Verlauf, Result-Logs,
  Watcher-/Apply-Instanzen und Live-Logs; außerdem lesende JSON-Einmalausgabe.
- Unabhängige Viewer-Prozesse mit eigener Ansicht, Auswahl, Suche, Sortierung,
  Fokus und Scrollposition. Keine gemeinsamen UI-Einstellungen.
- Git clean grün, staged/unstaged/untracked dirty rot, unbekannt/veraltet explizit.
  Erfolg/Exit 0 grün; Fehler/nonzero/Timeout/Abbruch rot. Entrypoint-Ausgang und
  Result-Publikation bleiben getrennt; Dry-run bleibt Validierung.
- Native Bindungs-/Inhaltsprüfungen, Replay-Bezug, optionales Archiv, vollständige
  Hash-Verknüpfungen und sichtbare fehlende/mehrdeutige Nachweise.
- Optionale, begrenzte Statuspublikation außerhalb der Exchanges mit echter
  Prozessgeburtsidentität, Heartbeat, Phasen, effektivem Timeout und Log-Tail.
  Quellenfehler verändern keine Ausführung. Viewer greifen nur lesend zu.

## Development-Prüfungen

Ausgeführte Auswahlen liefen parallel mit vier Workern unter nativem Linux und
Python 3.14.4. Die breite abschließende Integrationsauswahl bestand 213 Tests;
die anschließende Viewer-/API-/CLI-/Architektur-Auswahl bestand 121 Tests.
Ein in der Abbruchprüfung gefundener Import-Lebenszyklusfehler wurde auch in
VIEW-03.W und VIEW-03.R zurückgenommen; diese Zwischenstände wurden separat
mit 77 bzw. 85 Tests einschließlich realer Prozessbaum-Abbrüche erneut geprüft.
Die übrigen W/R/C-Zwischenstände wurden ebenfalls gezielt parallel geprüft.

Geprüft wurden reale Git-Zustände, Nebenwirkungsfreiheit der Leser, native
Pakete/Results, geänderte Dateien während Abfragen, beschädigte Daten,
Replay-Zuordnung, Archivbezug, exakte Log-Identität, begrenzte Abfragen und
Caches, fehlende Heartbeats, Prozess-ID-Wiederverwendung, parallele Läufe,
langsame/fehlerhafte Statusablage, Exit 0 bei fehlgeschlagener Result-Erzeugung
sowie die vorhandenen Apply-/Watcher-/Output-Verträge.

Praktische Linux-Abnahme: drei gleichzeitige native Terminal-Sitzungen am
registrierten PatchHarbor-Repository mit Übersicht, Bundles und Result-Logs.
Ansichtswechsel, unabhängiger Filter, Scrollen und getrenntes Schließen
funktionierten; grüne saubere Repositorys/Erfolge und rote Fehler wurden am
vorhandenen Exchange geprüft. Terminalzustand wurde bei allen Sitzungen
wiederhergestellt. Eine native Windows-Terminalabnahme wurde nicht ausgeführt.

## Apply und verbleibende Betriebsprüfung

Der Entrypoint prüft Zielpfad, Branch, Push-Ziel, Elterncommit, exakte Dateien,
Modi und Git-Scope vor/nach jedem Schritt. Er führt vor JEDEM Commit
`tools/run_tests.py --suite all --workers 12` aus und prüft den strukturierten
Testnachweis. Kein Erfolg ohne Gate, sauberen Abschluss und normalen Push.
Beim Fehler bleiben vorherige Commits und tatsächlicher Arbeitsstand erhalten.

Weder dieser Entwicklungsstand noch die ZIP-Verpackung installieren neue
Runtimes oder starten Dienste/CI. Bereits laufende alte Prozesse liefern noch
keinen Live-Status. Die lokalen Apply-Vollsuite-Ergebnisse und die native
Windows-Bedienung bleiben durch ihre jeweiligen Ausführungen nachzuweisen.
Ältere, vom vorhandenen Core nicht unterstützte Results erscheinen als
unbekannt/ungültig; aus ihnen wird kein Erfolg und keine vollständige Historie
abgeleitet.
