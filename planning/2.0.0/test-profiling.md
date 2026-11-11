# PatchHarbor 2.0.0 – lokale Testmessung und Profiling

**Status:** verbindlicher Detailentwurf zum [WRC-Plan](commit-plan.md), noch nicht
vollständig implementiert. Die normale Phasenbeobachtung `200-05.W/R/C` ist in
Bundle 094 vorbereitet; Ausführung und Bestätigung durch Apply stehen aus.
Profiling-Startbefehl, Collector und Datenbank folgen weiterhin in `200-06`
bis `200-09`. **Schritte:** `200-05` bis `200-09`; normale CI-Zeitdarstellung
zusätzlich `200-10`. **Stand:** 11. November 2026.

## 1. Lokale Bedienung und Abgrenzung

Das Werkzeug wird im Development-Repository mit einem eigenen Befehl gestartet.
Es läuft nicht automatisch beim normalen Testlauf, bei Apply, beim Watcher,
bei einer Installation oder in GitHub Actions. Es startet keine Remote-Tests,
keine SSH-Verbindung und keinen Upload. Messdaten bleiben vollständig lokal.
Die Beispiele beschreiben die geplante Oberfläche; diese Befehle existieren
im Stand 1.9.1 noch nicht.

```sh
# Ausgewählte Tests, getrennte Baseline-, Python-, Speicher- und strace-Läufe.
python tools/profile_tests.py run \
  --modes baseline,cprofile,memory,strace \
  --database build/test-profile/measurements.sqlite3 \
  --repetitions 5 --warmups 1 \
  -- tests/test_result_bundle_e2e.py

# Ohne Linux-strace: Python-Laufzeit und Python-Speicher bleiben nutzbar.
python tools/profile_tests.py run \
  --modes baseline,cprofile,memory \
  --database build/test-profile/measurements.sqlite3 \
  -- tests/test_parser.py

# Nur lesen; startet weder Tests noch Collector.
python tools/profile_tests.py report \
  --database build/test-profile/measurements.sqlite3 \
  --run latest --phase call --top 10

python tools/profile_tests.py report \
  --database build/test-profile/measurements.sqlite3 \
  --run latest --phase setup --top 10 --format markdown

python tools/profile_tests.py compare \
  --database build/test-profile/measurements.sqlite3 \
  --before RUN_ID_A --after RUN_ID_B --phase call
```

`run` verlangt eine explizite Testauswahl; keine heimliche Vollsuite. Die
Default-Datenbank ist `build/test-profile/measurements.sqlite3`, der Datenordner
liegt daneben unter `runs/<run-id>/`. Beide bleiben git-ignoriert und außerhalb
von Produktbundles, Runtime-Ressourcen und GitHub-Artefaktglobs. Ein expliziter
alternativer Pfad wird angezeigt und genau benutzt. Das Werkzeug bietet keinen
Remote-Speicheradapter und keinen Hintergrundmodus.

Für Diagnosezuordnung wird die gewählte Auswahl standardmäßig mit einem
xdist-Worker gemessen. Das ist ein ausdrücklich gestarteter Diagnosemodus,
kein neues serielles Commit-Gate. Der bestehende Testlauncher, seine Isolation,
Suiteauswahl und xdist bleiben maßgeblich; kein eigener Scheduler. Parallelität
kann ausdrücklich gewählt und dokumentiert werden, unsichere Zuordnungen bleiben
unbekannt. Die normale vollständige Apply-Suite bleibt parallel und unprofiliert.

Baseline-Läufe erhalten standardmäßig einen Warm-up und fünf Wiederholungen;
Parameter sind einstellbar. Teure Collector-Läufe erhalten standardmäßig eine
separate Wiederholung, mit `--profile-repetitions` einstellbar. Warm-ups werden
gespeichert, aber nicht als Messwiederholungen verrechnet. Tests/Fixtures werden
zwischen unabhängigen Wiederholungen regulär neu ausgeführt. Keine versteckte
Fixture-Cachestrategie, die das ursprüngliche Testverhalten verändert.

Exit-Status und Datenqualität sind getrennt: Testfehler behalten ihren Teststatus;
Tool-/DB-/angeforderte Collectorfehler ergeben einen Fehlerstatus; Ctrl-C bleibt
Abbruch. Details stehen in `test_exit_code`, `tool_status` und dem Collectorstatus.
Fehlendes ausdrücklich angefordertes strace wird `unavailable` mit Grund, nicht
ein erfolgreicher leerer Trace. Andere bereits verfügbare Messungen bleiben erhalten.

## 2. Messvertrag: Vorbereitung, Testkörper und Aufräumen

| Bereich | Erfasst | Auswertung |
| --- | --- | --- |
| Start/Imports/Collection | Prozessstart bis Testsession, Import-/Collectionintervalle und Workerstart, soweit separat messbar | Eigener Session-/Workerbereich; nicht als Testkörperzeit ausgeben. |
| `setup` | Pytest-Vorbereitung einschließlich Fixtureaufbau vor dem Testkörper | Eigene Dauer und eigenes Ranking „Testvorbereitung“. |
| `call` | Ausführung des Testkörpers innerhalb der Pytest-call-Phase | Primäres Ranking „reine Testausführung“. |
| `teardown` | Finalizer, Cleanup und Rückbau nach dem Testkörper | Eigene Dauer und eigenes Ranking „Aufräumen“. |
| Gemeinsame Fixtures | Echte Fixtureinstanz mit Scope, Parameterfall, Worker, Auf-/Abbau und Verbrauchern | Einmalige Kosten; nicht jedem Verbraucher in voller Höhe zuschlagen. |
| Session-Ende/Framework | Sessionhooks, Reportpublikation und außerhalb von Testphasen anfallende Arbeit | Eigener Bereich, bei fehlender Instrumentierung als nicht getrennt messbar markieren. |
| Collectoraufwand | Zusätzliche Prozesszeit, Serialisierung, Traces/Profiles und eigene Datenvolumen | Gesonderter Diagnostikaufwand; nicht still von Messwerten abziehen. |

`call` enthält die durch den Testkörper selbst ausgelöste Arbeit, einschließlich
selbst aufgebauter Daten oder dort gestarteter Prozesse. Solche fachliche
Vorbereitung kann der Profiler nicht automatisch aus beliebigem Testcode
herausrechnen. Sie bleibt `call`, bis der Test bewusst anders strukturiert wird.
Die gemessene Pytest-call-Phase kann kleine Hook-/Capturekosten enthalten; sie
wird nicht als hardwaregenaue exklusive Funktionszeit ausgegeben. Zusätzlich
vorhandene engere Testkörper-Spans tragen ihren eigenen Messumfang.

Bei Scope-Fixtures wird zunächst die tatsächliche Vorbereitung des auslösenden
Tests gemessen und der Fixture-Span zusätzlich seinem Scope zugeordnet. Der
Fixtureanteil ist eine Teilmenge der Phase, keine zusätzlich zu summierende
Dauer. Verschachtelte Fixtures und inklusive/exklusive Spans kennzeichnen;
bei nur teilweise messbaren Finalizern keine vollständige Fixturezeit behaupten.
Keine gleichmäßige, stillschweigende Verteilung auf alle Tests.

Je Test und Wiederholung wird `setup + call + teardown` als **Testgesamtzeit**
angezeigt. Das ist nicht die Job-Walltime und nicht automatisch die Summe
verschachtelter Fixture-/Funktionsspans. Bei übersprungenem oder gescheitertem
Setup ist `call = nicht ausgeführt`, nicht `0 s`. Abgebrochene Phasen sind partiell.

Zeitdauern werden mit monotoner Uhr bzw. den tatsächlichen Pytest-Phasendauern
gespeichert. UTC-Zeit dient der Einordnung. CPU-Zeit hat einen expliziten
Messumfang (Prozess/Thread/Kindprozesse) und darf nicht aus Walltime erraten werden.
Überlappende Workerintervalle werden nicht zur Suite-Walltime addiert. Nicht
aufgelöste Differenzen heißen Framework-/unzugeordneter Anteil, nicht CPU-Verlust.

Beispiel der geplanten Übersicht, mit rein illustrativen Messwerten:

| Test | Vorbereitung | Testkörper | Aufräumen | Testgesamtzeit | Hinweis |
| --- | ---: | ---: | ---: | ---: | --- |
| `test_export` | 4,80 s | 0,12 s | 0,30 s | 5,22 s | Vorbereitung untersuchen; Testkörper schnell. |
| `test_hash` | 0,02 s | 2,90 s | 0,01 s | 2,93 s | Produkt-/Testcode im call-Profil untersuchen. |
| `test_cleanup` | 0,03 s | 0,08 s | 3,10 s | 3,21 s | Cleanup separat untersuchen. |
| `test_setup_error` | 0,40 s | nicht ausgeführt | 0,05 s | 0,45 s | Kein langsamer oder erfolgreicher Testkörper. |

## 3. Normale Testreports und lokale Profiling-Daten sind verschieden

In 1.9.1 speichert `tools/test_evidence.py` schon `nodeid`, `when`, `outcome`,
Worker und Nachweisbindung, aber keine Zeitdauern. `--durations=10` erzeugt nur
Konsolenausgabe. Diese wird nicht nachträglich als strukturierte Messquelle geparst.

Geplant ist eine additive `telemetry` im vorhandenen JSON, mit eigenem
`format_version: 1`, Run-ID, Binding, Worker-/Phasenbezug, Dauerwerten und
Vollständigkeit. Die vorhandenen Beweisfelder, Reportdigests, Erfolgsvalidatoren
und Vergleichssignaturen bleiben in ihrer Bedeutung unverändert. Zeitdaten
haben ihre eigene Validierung; fehlerhafte Telemetrie ergibt keine falsche
Abnahme. Worker-Daten müssen demselben tatsächlichen Lauf entstammen.

Das erhält die vorhandenen CI-JSON-Dateien und ihre strengen Artefaktinventare.
Die normale Zeitmessung ist kein cProfile-/tracemalloc-/strace-Profiling. Nur
diese normalen CI-Testergebnisse dürfen die Actions Job Summaries speisen.
Die lokale Profiling-Datenbank wird niemals implizit importiert oder hochgeladen.

Der Summary-Reader kann rote Reports anzeigen, ohne `test_results.validate()`
für erfolgreiche Abnahme permissiver zu machen. Er unterscheidet Testfehler,
Collectionfehler, fehlende Ergebnisse und echte Pytest-Skips. Ein Test mit drei
Phasen zählt höchstens einmal; ein fehlgeschlagenes Teardown bleibt ein Fehler,
auch wenn `call` bestanden war.

## 4. Datenbank und Provenienz

SQLite aus der Standardbibliothek ist das lokale Auswertungsformat. Ein
Controller schreibt Transaktionen; Worker und Collector schreiben keine
konkurrierenden SQLite-Transaktionen. Rohartefakte werden begrenzt lokal
gespeichert und mit vollständigem Hash referenziert. Kein Löschen alter Runs
als normale Nebenwirkung und kein Überschreiben durch `latest`.

| Tabelle / Bereich | Wesentliche Felder |
| --- | --- |
| `schema_meta` | Schema-Version, Werkzeugversion, dokumentierte Migrationen. |
| `runs` | UUID, Parent-/Vergleichsgruppe, Commit, dirty-Flag, tatsächlicher Source-Digest, Testauswahl, Args, UTC-Start/Ende, monotone Walltime, Host/OS/Architektur, Python/Pytest/xdist, Workerzahl, Ergebnis/Vollständigkeit. |
| `measurements` | Run, Modus, Wiederholung, Warm-up, Collectorversion/-parameter, Zeitbasis, Testexit, Toolstatus, Abdeckungsgrad, Fehlgrund. |
| `test_cases` / `phases` | Vollständige parametrische Node-ID, Worker, Prozess-/Threadbezug, setup/call/teardown, Ergebnis, Dauer, CPU-Messumfang, fehlend/partiell/vollständig. |
| `fixtures` / `fixture_uses` | Fixtureinstanz, Scope, Parameteridentität, Worker, Aufbau/Finalisierung, Verbraucher; verschachtelte Spans und inklusive Zeit. |
| `processes` | Messlauf, PID plus Lebensdauer/Startidentität, Parent, Thread-ID, exec-Wechsel und Zuordnungssicherheit. |
| `python_functions` / `python_callers` | Phase, Quelldatei, Zeile, Funktion, primitive/gesamte Aufrufe, Eigen-/kumulative Profilzeit, Caller-Kanten. |
| `memory_observations` | Phase, Methode, Python aktuell/Peak/Differenz, optional Prozess-RSS, Einheit, Zeitbezug, Traceback, Abdeckung. |
| `syscalls` / `syscall_groups` | Prozess/Thread, Aufruf/Fehler, Dauer, Kategorie, Phasenanteil oder unzugeordnet; Bezug zum lokalen Rohtrace. |
| `artifacts` | Relativer lokaler Pfad, Rolle, SHA-256, Größe, vollständig/abgeschnitten/fehlt. |
| `findings` | Versionierte Regel, Phase/Test/Quellort, zugrunde liegende Messungen, Stärke und Einschränkung des Hinweises; keine erfundene Einsparung. |

Indizes orientieren sich an Run, Messmodus, Node-ID/Phase und Quellort.
Unbekannte Größen werden `NULL` mit Grund, nicht `0`. Schemaänderungen erfolgen
transaktional mit prüfbarem Backup; unbekannte neuere Schemas werden nicht
überschrieben. Fremde Datenbanken werden nicht als leere Profiling-DB übernommen.
Abgebrochene Runs bleiben als solche abfragbar. Die Datenbank liegt standardmäßig
auf lokalem Speicher; kein impliziter SQLite-WAL-Betrieb auf einem Exchange/CIFS.

Keine globalen Umgebungs-/Geheimnisdumps. Gespeichert wird nur benötigte,
ausgewählte Laufkonfiguration. Pfade/Traceargumente können lokale Inhalte
enthalten; Rohdaten bleiben entsprechend lokal und werden nicht automatisch
in Produkt-Result-Bundles aufgenommen. Löschung/Export wäre ein eigener,
ausdrücklicher lokaler Befehl und ist für den ersten Umfang nicht notwendig.

Für große Traces bleiben Rohdaten begrenzt im lokalen Run-Verzeichnis; SQLite
enthält indizierbare Phasen-/Syscallaggregate und Belegstellen. Ein Byte-für-Byte-
Import beliebig großer Traces ist kein Ziel. Fehlende oder wegen eines Limits
nicht erfasste Daten bleiben im Status sichtbar.

## 5. Getrennte Collector-Läufe

### 5.1 Baseline

Ein normaler Lauf mit leichter Phasenbeobachtung liefert die Referenz für
Ranglisten und spätere Vorher-/Nachher-Vergleiche. Wiederholungen, Median,
Spannweite und Stichprobengröße ausweisen. Keine aussagekräftigen Perzentile
aus wenigen Messungen vortäuschen. Hostzustand und Cacheeffekte sind Störgrößen;
Messung nicht mit einem gleichzeitig laufenden Vollgate vermischen.

### 5.2 Python-Funktionsprofil

`cProfile`/`pstats` erfassen Funktionen, Aufrufzahlen und Eigen-/kumulative Zeit.
Der gewählte Timer wird mitgespeichert. Profilzeit ist keine ungeprüfte CPU-Zeit
und kein Benchmark; Baselinezeiten sind die Vergleichsbasis. Collector, Test-
Framework und Produktcode werden anhand der Quellpfade getrennt dargestellt.
Roh-`.prof`-Dateien bleiben lokal, normalisierte Daten kommen in SQLite.
Die Standardbibliothek dokumentiert ausdrücklich den Messaufwand und die
Abgrenzung zum Benchmarking. [Python-Profiler](https://docs.python.org/3.10/library/profile.html)

Thread-/Kindprozessprofile benötigen tatsächlich gestartete Instrumentierung.
Der Python-Testprozess liefert nicht automatisch das Pythonprofil eines
Shell-/Git-/PYZ-Kindprozesses. Unterstützte eigene Python-Helfer können über
eine explizite Startgrenze instrumentiert werden; ansonsten bleibt ihre
Python-Abdeckung unbekannt. Keine dauerhafte `sitecustomize`-Installation,
kein globales `PYTHONPATH` und keine Behauptung vollständiger Prozessabdeckung.

### 5.3 Python-Speicher und optionaler Prozessspeicher

Ein eigener `tracemalloc`-Durchlauf speichert aktuellen und Spitzenwert der
verfolgten Python-Allokationen sowie Snapshotdifferenzen und Quell-Tracebacks.
Die Messung beginnt früh genug; Import-/Sessionarbeit wird separat eingeordnet.
Phasenstartwerte und `reset_peak`-Semantik verhindern, dass ein früherer Peak
dem nächsten Test als neuer Peak zugeschrieben wird. Ein Peak umfasst weiterhin
bereits lebende Objekte; Differenz und absolute Größe klar beschriften.
[tracemalloc-Vertrag](https://docs.python.org/3.10/library/tracemalloc.html)

Snapshotdifferenz misst netto noch vorhandene Allokationen; sie beweist weder
alle kurzlebigen Allokationen noch automatisch ein Leak. Wiederholte Zunahme
ist ein Untersuchungshinweis. Speicher von nativen Bibliotheken und externen
Prozessen ist nicht vollständig durch tracemalloc abgedeckt.

Optionaler RSS-Collector ist getrennt gekennzeichnet: unter Linux etwa lokale
Prozessdaten, unter Windows nur ein nachgewiesener nativer Adapter. Fehlende
Unterstützung bleibt unbekannt. Prozess-Höchststände über die Lebensdauer sind
keine per-Test-Peaks. Abgetastete RSS-Maxima können kurze Spitzen verpassen;
RSS mehrerer Prozesse wird wegen geteilten Speichers nicht als eindeutiger
physischer Gesamtverbrauch ausgegeben. Keine Pflichtabhängigkeit wie `psutil`.

### 5.4 Linux-strace

Ein eigener lokaler Lauf nutzt sinngemäß `strace -ff -ttt -T -o TRACE …` mit
argumentlistenbasiertem Start und geprüften Optionen der installierten Version.
`-ff` trennt Prozesse, `-ttt` ermöglicht Zeitkorrelation und `-T` liefert
beobachtete Systemaufrufdauer. strace ist ein externer optionaler Linux-Collector,
keine neue Python-Produktabhängigkeit. Keine automatische Installation oder
Rechteerhöhung. [Offiziell verlinktes strace-Handbuch](https://man7.org/linux/man-pages/man1/strace.1.html)

Zeitkorrelation verbindet die monotone Phasenzeit mit der Trace-Zeitbasis;
Uhrsprünge/Unsicherheit werden erkannt. Aufrufe über Phasengrenzen erhalten
nachgewiesene Überlappungen oder bleiben unzugeordnet. Nachlaufende Kinder
werden nicht dem zufällig gerade laufenden nächsten Test zugeschlagen. Keine
eindeutige Testzuordnung allein aus globaler Uhrzeit bei mehreren Workern.

Datei-I/O, Metadatenzugriffe, Prozessstart und Warten werden separat gruppiert.
Zeit in `wait`/`poll`/`futex` ist kein Beleg für CPU-Verbrauch. Addierte Zeiten
parallel laufender Prozesse sind nicht die beobachtete Gesamtdauer. Wiederholte
Syscalls zeigen Untersuchungsbedarf, nicht automatisch einen Fehler.

Keine vollständigen Datei-/Netzwerkpuffer oder Umgebungen absichtlich dumpen.
Argument- und Tracegröße begrenzen; Parser verarbeitet Daten strömend und
speichert begrenzte Aggregate. Explizite Zeit-/Speicher-/Dateibudgets schützen
den Messlauf. Bei Erreichen wird der Collector kontrolliert beendet und der
Lauf partiell markiert; bestehende Test-Gates werden dafür nicht verändert.

## 6. Aussagen über Optimierungspotenzial

Getrennte Standardansichten:

1. Testkörper: langsamste `call`-Phasen aus der Baseline.
2. Vorbereitung: teuerste Setups und tatsächlich aufgebaute gemeinsame Fixtures.
3. Aufräumen: lange Finalisierung, Prozesse und Dateien im Teardown.
4. Python-Hotspots: häufige Aufrufe, hohe Eigen-/kumulative Zeit mit Datei/Zeile.
5. Speicher: hohe Python-Peaks, Nettozunahme, optionale RSS-Beobachtung.
6. Betriebssystem: häufige Metadaten-/I/O-/Prozessaufrufe und lange Warteanteile.

Jeder Hinweis enthält **Test, Phase, Quellort soweit belegt, Messgrundlage,
Wiederholungen und Einschränkungen**. Produktcode und Testinfrastruktur werden
unterschieden. Ein teures Fixture ist nicht pauschal ein langsamer Produktalgorithmus.
Kumulative Funktionszeiten werden nicht mehrfach zu einer Einsparung addiert.
Es werden keine Tests abgeschaltet, Wartebedingungen gelockert, Sicherheits-
prüfungen entfernt oder Codeänderungen automatisch vorgenommen.

Vergleichbar sind bewusst ausgewählte Runs mit gleichem Messmodus, kompatibler
Umgebung, Auswahl und Parametrisierung. Bei Vorher/Nachher darf der Quellcommit
natürlich unterschiedlich sein; beide tatsächlichen Quellstände müssen gebunden
und die Testfälle fachlich zugeordnet sein. Umbenannte Node-IDs oder Quellzeilen
sind nicht automatisch identisch; eine explizite Zuordnung ist zu dokumentieren.
Teständerungen und Python-/Hardwarewechsel dürfen nicht unbemerkt als
Produktbeschleunigung erscheinen. Instrumentierte und Baselinezeiten werden
nicht als gleichartige Stichproben vermischt.

## 7. Implementierungsgrenzen

Startpunkt: `tools/run_tests.py`, `tools/test_runner.py`, `tools/test_evidence.py`,
`tools/test_results.py`, `tools/result_io.py`. Neues Werkzeug:
`tools/profile_tests.py`; unterstützende Module nach Bedarf unter
`tools/profiling/`, nicht im Produktkern. Keine abstrakte Collector-Plattform
auf Vorrat und kein eigener Testprozess-Scheduler.

Sinnvolle Verantwortungen sind lokaler Start, Pytest-Messadapter, Datenmodell,
SQLite-Persistenz, Python-Collector, strace-Parser/Korrelation und Bericht.
Bestehende Quellbindungs-/Exitstatus-/Reportprimitive werden verwendet, soweit
ihr Vertrag passt. JSON-Ausgaben sind maschinenlesbar; keine ANSI-Sequenzen
oder Fortschrittstexte auf deren stdout. Freie Testnamen/Quellpfade werden für
Markdown/Textdarstellung begrenzt und entschärft.

Zusätzliche Python-Abhängigkeiten sind zunächst nicht vorgesehen: `sqlite3`,
`cProfile`, `pstats`, `tracemalloc`, `time`, `subprocess` und `json` reichen für
den Kernumfang. Pytest/xdist sind bereits Entwicklungsabhängigkeiten.
Profiling-Befehle sind ausdrücklich lokale Entwicklerwerkzeuge und werden
nicht Bestandteil der Core-PYZ oder eines automatisch gestarteten Watchers.

## 8. Konkrete Abnahmefälle

| ID | Verhalten, das tatsächlich nachgewiesen werden muss |
| --- | --- |
| P-01 | Künstlich teures Setup, kurzer Testkörper und teures Cleanup erscheinen in drei richtigen Spalten/Ranglisten; keine doppelte Gesamtsumme. |
| P-02 | Zwei Tests teilen ein Session-/Module-Fixture; Aufbau wird einmal mit Scope und Verbrauchern erfasst, nicht beiden vollständig zugeschlagen. |
| P-03 | Setupfehler/Skip: call ist nicht ausgeführt; Teardownfehler bleibt Fehler; Collectionfehler und fehlende Worker sind sichtbar. |
| P-04 | Zwei überlappende Worker: Walltime, aufsummierte Testarbeit und geteilte/verschachtelte Spans bleiben verschieden. |
| P-05 | CPU-Helfer im Testkörper, Allokation im Setup und Cleanup-Allokation werden der korrekten Phase und Quelle zugeordnet. |
| P-06 | Ein nicht instrumentierter Python-/Git-Kindprozess erscheint ohne erfundenes Pythonprofil; Hintergrundthreads werden nicht still als vollständig profiliert ausgegeben. |
| P-07 | Lokaler Linux-Trace mit Datei-I/O und Kindprozess liefert PID/Lebensdauer, Syscallgruppe und nachvollziehbare Phasenzuordnung. |
| P-08 | Unfinished/resumed, Signal, exec, Nachläufer und beschädigter/abgeschnittener Trace bleiben nachvollziehbar; unklare Zeitbasis ergibt unbekannte Zuordnung. |
| P-09 | Fehlendes strace, fehlende Berechtigung oder nicht unterstützte Plattform: Collectorstatus eindeutig; andere lokale Daten bleiben erhalten. |
| P-10 | Ctrl-C, voller Datenträger und DB-Sperre erhalten vorherige Runs; unvollständige Messungen werden nicht grün. Zwei Controller beschädigen die DB nicht. |
| P-11 | Kein Netzwerk-/SSH-/Uploadpfad des Werkzeugs; keine Wirkung durch bloßes Importieren; `report`/`compare` starten keine Tests. |
| P-12 | Alter/neuer Quellstand mit gleicher Testaufgabe ist vergleichbar; unterschiedliche Instrumentierung, ungleiche Auswahl oder unklare Umbenennung nicht still vergleichbar. |
| P-13 | Strenge bisherige Testnachweisprüfungen bleiben wirksam; kaputte Telemetrie erzeugt keine falschen Testsiege oder Releasefreigaben. |
| P-14 | Kleine lokale reale Messung von mindestens einem Vorbereitung-, CPU-, Speicher- und I/O-Fall erzeugt DB, lokale Rohdateien und überprüfbare Hinweise. |

Die Tests verwenden kurze reale Prozesse und kontrollierte Arbeit/Barrieren,
ergänzt um deterministische Parser-/DB-Fixtures. Keine absoluten CPU-/Speicher-
Schwellen für unbekannte CI-Runner, keine langen Sleeps und keine neue
Benchmark-Pflicht in allen Releasejobs. Hardwareabhängige Aussagen benötigen
lokale Messbelege; reine Parser-Tests ersetzen keine echte Collector-Abnahme.
