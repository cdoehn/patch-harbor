# PatchHarbor Monitor — Implementierungsplan

## Auftrag und Lieferfolge

Nutzerauftrag: lesender TUI-Viewer im Stil des SpecRoad-Test-Monitors, mit
Repositorys, Exchanges, Bundle-Beziehungen, Apply-Verlauf und Watcher-Status.
Mehrere Viewer müssen gleichzeitig mit unabhängigen Ansichten laufen.
Repository sauber = grün; staged/unstaged/untracked Änderungen = rot.
Erfolg/Exit 0 = grün; Fehler, Timeout und Abbruch = rot. Git-Zustand,
Entrypoint-Ergebnis und Result-Erzeugung bleiben getrennt.

Der erste Commit der ersten Lieferung ist VIEW-00 (dieser Plan samt
Erweiterungsspezifikation). Danach folgen echte W/R/C-Zustände, jeweils geprüft
und committed vor der nächsten Änderung. Die drei ursprünglich geschätzten
Bundles sind fachliche Gruppen; der Nutzer autorisiert ausdrücklich möglichst
viele vollständige Schritte in einer einzigen ZIP. Paketgrenzen sind keine
Funktionsgrenzen. Erforderliche Detailklärungen werden dokumentiert; zusätzliche
Klärungscommits nur bei tatsächlichem fachlichem Bedarf.

Maßgeblich: `planning/viewer/specification.md` ergänzt `spec/SPECIFICATION.md`.
Vorbereitungsbasis: Result SHA-256
`e792c340f4317be01cf92f14fb12807ac9146257be15f10574a638f8e9242534`,
Commit `2121d3abd2ca4b6c523d9e0698d997a86581d5bc`, sauber.
Bundle-Nummer der ersten Lieferung: 078. Die Nummer ist keine Zustandsbindung.

## Geordnete Commits

| Position | ID | Commit-Message | Fachlicher Umfang |
|---|---|---|---|
| 0 | VIEW-00 | docs(monitor): record viewer plan and acceptance contract [VIEW-00] | Plan als erster Commit, gemeinsame Abnahmen und Detailentscheidungen |
| 1 | VIEW-01.W | feat(monitor): observe repositories and exchanges in independent viewers [VIEW-01.W] | Lesende Core-Schnittstelle, TUI, Auswahl, Git-Zustand, Exchange-Zuordnung, JSON |
| 2 | VIEW-01.R | fix(monitor): bound observations and preserve stale source evidence [VIEW-01.R] | Unabhängige Abfragen, Grenzen, Quellfehler, Rennen, mehrere Viewer |
| 3 | VIEW-01.C | refactor(monitor): separate observation scheduling and terminal state [VIEW-01.C] | Reale Strukturverbesserung ohne neue Fachfunktion |
| 4 | VIEW-02.W | feat(monitor): relate patches results and apply attempts [VIEW-02.W] | Paketbindung, Ausschlussgründe, Result-/Apply-Ausgänge, Historie und Logs |
| 5 | VIEW-02.R | fix(monitor): validate artifact provenance and ambiguous histories [VIEW-02.R] | Beschädigte/veränderte Dateien, Mehrdeutigkeit, fehlende/archivierte Nachweise |
| 6 | VIEW-02.C | refactor(monitor): share artifact facts and bound detail caching [VIEW-02.C] | Gemeinsame Leser und begrenzte Metadaten-/Detail-Caches |
| 7 | VIEW-03.W | feat(monitor): publish live watcher and apply observations [VIEW-03.W] | Versionierte Beobachtungsdaten, Phasen, Timeout, Sperren und Live-Ausgabe |
| 8 | VIEW-03.R | fix(monitor): isolate concurrent runs and stale live publishers [VIEW-03.R] | Prozessneustart, Absturz, mehrere Applies/Viewer, Fehlerisolation |
| 9 | VIEW-03.C | refactor(monitor): consolidate live contracts and delivery documentation [VIEW-03.C] | Verträge, Ressourcen, Plattformgrenzen und vollständige Bedienung |

Alle Positionen sind zunächst OFFEN. Vorbereitete Dateistände und lokale Tests
sind kein Apply-Nachweis. Die Lieferdokumentation nennt enthaltene Positionen,
tatsächlich geprüfte Development-Stände und verbleibenden Umfang. Erst das
zurückgegebene Result belegt Commits und Fortschritt.

## Gruppe 1: Repositories und Exchanges

W liefert eine durchgängige lesende Übersicht über alle registrierten Ziele,
Repository-Pfad/ID, Registrierung, konfigurierten Exchange, Git-Commit,
Fingerprint und Anzahlen staged/unstaged/untracked. Mehrere Repositorys können
sich einen Exchange teilen. Jede Instanz hält Fokus, Ansicht, Auswahl, Suche,
Sortierung und Scrollposition unabhängig. Einmalausgabe und JSON sind verfügbar.
R isoliert defekte Quellen, begrenzt Abfragen, hält die Oberfläche reaktionsfähig
und kennzeichnet alte Werte statt einen veralteten Erfolg fortzuschreiben.
C trennt Quellen, Aktualisierung und Darstellung und reduziert Doppelarbeit.

Abnahmen VIEW-A1–A7: reale registrierte saubere/dirty Repositorys; alle drei
Änderungsarten; ignorierte Dateien bleiben ignoriert; fehlende/konfliktäre IDs
und defekte Konfiguration; gemeinsame und fehlende Exchanges; unabhängige
Viewer/Filter; unveränderte Registry, Replay-Daten, Git-Index und Nutzdateien.

## Gruppe 2: Bundles, Results und Verlauf

W zeigt Patch/Result/sonstige Dateien, Identität, Bindung, Verarbeitung und
Ablage getrennt. Der Verlauf verbindet belegte Ausgangszustände, Patches,
Apply-Versuche, Results und Folgezustände. Logs abgeschlossener Läufe sind
lesbar. Native Core-Regeln liefern Bindung und Auswahlgründe; keine FIFO-Fiktion.
R behandelt Races, defekte Pakete, doppelte/mehrdeutige Referenzen, wiederholte
Versuche sowie fehlende und archivierte Nachweise. C vereinheitlicht Leser und
begrenzt Metadaten-/Detail-Caches; teure Details werden nur bei Bedarf geladen.

Abnahmen VIEW-B1–B8: vollständige IDs statt Dateinamen; kein Vermischen von
Repositorys; erwarteter Commit/Fingerprint; Replay-Zustände; Exit 0 mit roter
Result-Publikation; Dry-run ausdrücklich als Validierung; belegte Wiederholungen
getrennt; fehlende Historie und nicht eindeutiges Ausgangs-Result sichtbar.

## Gruppe 3: Watcher und laufende Applies

W publiziert optionale Beobachtungen unabhängig von geöffneten Viewern:
Watcher-Instanz, tatsächlich beobachtete Exchanges, Ruhe-/Sperrfristen,
Apply-Lauf-ID, Repository/Patch, Phase, Beginn, effektiver Timeout und Live-Log.
Die Ablage liegt im Benutzerzustandsverzeichnis außerhalb der Exchanges.
R verhindert Verwechslungen bei Neustart/PID-Wiederverwendung, isoliert mehrere
manuelle Applies und behandelt abgestürzte oder alte Quellen. C konsolidiert
Verträge, begrenzte Aufbewahrung und Dokumentation.

Abnahmen VIEW-C1–C8: aktuelle Watcher-/Apply-Phasen; effektiver Entrypoint-Timeout
statt konfiguriertem Wunschwert; kein Live-Beweis aus `attempted`; manueller und
automatischer Ursprung; mehrere Läufe ohne Überschreiben; langsame/abgestürzte
Viewer blockieren keine Ausführung; Statusfehler ändern kein Apply-Ergebnis;
drei parallele Viewer zeigen unabhängig Übersicht, Bundle und Logs.

## Tests, Übergabe und Nachweise

Aktuelle Laptop-Policy: gezielte parallele Development-Prüfungen; vor JEDEM
Apply-Commit vollständige parallele Suite über `tools/run_tests.py --suite all`.
Auch VIEW-00 erhält sein Apply-Gate. Kein serielles Gate, kein automatischer
CI-Start, kein Tag oder Installationswechsel. UI-Farben/Layout werden praktisch
geprüft; automatisierte Tests prüfen Datenverträge und tatsächliches Verhalten.
Native Linux-/Windows-Nachweise werden getrennt ausgewiesen.

Die ZIP enthält zunächst nur den Plan-Zustand als reguläre Payload. Der
Entrypoint stellt weitere Zustände mit geprüften Git-Deltas einzeln her,
prüft Vorher-/Nachherbytes und den Git-Scope, führt das jeweilige Gate aus und
committet erst danach. Bei Fehler stoppt die Folge; erfolgreiche Vorgänger und
der tatsächliche Arbeitsstand bleiben erhalten. Erst nach allen enthaltenen
Commits, sauberem Ziel und normalem Push erscheint der Bundle-Erfolgsmarker.
Keine rekursiven Apply-/Bundle-Aufrufe und keine Dienststeuerung.
