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

## Vorbereitete erste Lieferung 078

Enthalten: VIEW-00 und alle neun W/R/C-Positionen VIEW-01.W bis VIEW-03.C,
in der oben festgelegten Reihenfolge. Fachlich passen damit alle drei Gruppen
in die erste ZIP. Die Zwischenstände sind als echte aufeinander aufbauende
Git-Deltas vorbereitet, mit vollständigen Datei- und Modus-Inventaren.

Stand vor Übergabe: PREPARED, nicht APPLIED. Entwicklung und native Linux-
Abnahmen sind in `planning/viewer/delivery-078.md` dokumentiert. Jeder Commit,
einschließlich dieses ursprünglichen Plan-Zustands, erhält im Apply seine eigene
vollständige parallele Suite. Erst die Result-Ausgabe belegt ausgeführte Commits.
Es gibt keine künstlichen Klärungscommits: die notwendigen Detailentscheidungen
standen bereits in VIEW-00; die drei C-Schritte enthalten reale Strukturarbeit.

## Wiederaufnahme mit Bundle 079

Bundle 078 wurde am 9. November 2026 mit Exitcode 1 beendet. VIEW-00 ist
bestaetigt committed als `26b3bf4bf9b17c825b604cad1a180e3d6c64fe1d`; die
Vollsuite dieser Stufe bestand. VIEW-01.W blieb vor seinem Commit stehen,
weil die explizite Release-Dateiliste die neuen Viewer-Module noch nicht
enthielt. Der reale dirty Zwischenstand bleibt erhalten.

Bundle 079 ist an genau diesen geprueften Result-Snapshot gebunden. Es
vervollstaendigt VIEW-01.W und setzt alle weiteren W/R/C-Stufen in der
urspruenglichen Reihenfolge fort. Jede Stufe hat ihre eigene explizite
Paketdateiliste; das gemessene Wheel mit allen Viewer-Modulen erhaelt ein
begrenztes 432-KiB-Releasebudget. Kein Runtime-/Eingabelimit wird geaendert.
Details und noch ausstehender Apply-Nachweis: `delivery-079.md`.

## Folgeauftrag: Bedienbarkeit und betriebliche Übersicht

Am 10. November 2026 autorisiert der Nutzer die gemeinsam ausgearbeitete TUI:
fünf persistente Verlaufszeilen, aussagekräftiger Watcher-Zustand, echte
Aktivitätsgeschichte, bedingte Vorschau, dezente Symbole/Farben, lokale Zeiten,
kürzbare IDs und eine PatchHarbor-/Exchange-zentrierte Repositoryübersicht.
Vorhandene Bundle-Nummer, Kennung, Vorgangsart und Repository sind sichtbar.
Die ausdrückliche neue Gestaltung ersetzt die frühere Git-Priorität.

Bundle 082 liefert dies als einen zusammenhängenden OFF-PLAN-Commit VIEW-UX:
`feat(monitor): show persistent activity and operational repository status [VIEW-UX]`.
Kein weiterer nomineller W/R/C-Zwischenstand; ursprünglicher Planzähler unverändert.
Der verifizierte Ausgang ist `023e08a47eb30bd88a7440533e4f45ab8add54b8`.
Vor dem Commit vollständige parallele Apply-Suite, danach genau ein normaler
Push. Entwicklungsprüfungen und Übergabevertrag stehen in `delivery-082.md`.
