# PatchHarbor – Parallelisierung der Entwicklungstests

Stand: Benutzerauftrag vom 15.09.2026; ergänzt `spec/SPECIFICATION.md` und
`planning/1.2.0/specification.md`, ohne deren Produktvertrag zu ändern.
Implementierungsplan: `planning/test-parallel/commit-plan.md`.

## Ziel und Abgrenzung

PatchHarbor verwendet bereits pytest. Bestehende Tests bleiben erhalten;
unittest-Testfälle müssen nicht nur wegen pytest neu geschrieben werden.
pytest und pytest-xdist sind ausschließlich Development-Abhängigkeiten.
Runtime, CLI von PatchHarbor, Registry, lokale Konfiguration, Watcher,
Bundle-/Replay-/Timeout-Verträge bleiben unverändert. Insbesondere wird
kein Test-Scheduler im Produkt gebaut. xdist verteilt Tests auf Prozesse.

Nach Abschluss ist der Entwicklungslauf standardmäßig parallel (`auto`).
Eine feste Workerzahl sowie `--serial` / `-n 0` bleiben verfügbar. Bundle 1
bietet den Parallelbetrieb zunächst explizit an; erst Bundle 2 ändert den
Standard nach vollständiger Abnahme und parallelisiert die CI.

## W/R/C und echte Zwischenstände

W stellt echtes funktionierendes Verhalten her, keine Gerüste oder Attrappen.
R ergänzt Korrektheit, Fehler-/Grenzfälle und Parallelitätssicherheit.
C verändert kein fachliches Verhalten; neu entdecktes Verhalten gehört nach R
oder in einen neuen Schritt. Nicht benötigte C-Schritte werden nicht künstlich
erzeugt. Ein Bundle darf mehrere Schritte und mehr als neun Commits enthalten.
Jeder Commit entsteht nach Änderungen und eigenen erfolgreichen Tests, vor
Beginn des nächsten Schritts. Fehler stoppen; erfolgreiche Commits bleiben.
Kein destruktiver Rollback und keine nachträgliche Scheinzerlegung.

## Teststart

`tools/run_tests.py` ist ein Entwicklungseinstieg, kein PatchHarbor-Kommando.
Der bestehende `scripts/test.sh` bleibt als Bash-Setup/Einstieg erhalten.
pytest-Argumente werden nach `--` unverändert übergeben; Aufrufe erfolgen ohne
Shell-Auswertung mit dem ausgewählten Python-Interpreter im Repositoryroot.
Ein Aufruf importiert nicht mehrfach pytest in denselben Prozess. Geerbte
`PYTEST_ADDOPTS` werden nur im Kindprozess geleert, damit keine fremden Filter,
letzte-Fehler-Auswahl oder kurzen Timeouts eine Abnahme verfälschen.
Explizite Selektoren sind für gezielte Entwicklungstests erlaubt und niemals
als vollständige Suite auszugeben. Der serielle Referenzmodus darf nicht durch
weitergereichte Worker-Optionen unbemerkt parallel werden.

Keine künstlichen Einzeltest- oder Suitefristen als Ersatz für Fehleranalyse.
Der zentrale lokale Launcher deaktiviert pytest-timeout. Fachliche Tests der
Produkt-Timeouts und kontrollierte Synchronisations-/Prozessprüfungen bleiben.
Das äußere `patchharbor apply --timeout ...` ist ein anderer Mechanismus.
Es wird durch ein ZIP nicht stillschweigend verändert. Ohne uv.lock kein
`uv run --frozen`; Entwicklungsabhängigkeiten stammen aus `.[dev]` in .venv.

## Isolation und Hilfen

Schreibende Tests erhalten möglichst pro Test eigene temporäre Verzeichnisse.
Das betrifft Repository, Exchange, Archive, Registry, State, Locks, Datenbanken,
Builds, pipx-Installationen, Berichte und Prozess-Kommunikationsdateien.
Feste Ports/Sockets müssen vermieden oder eindeutig zugeteilt werden.
Ein gemeinsam benutzter Exchange innerhalb eines Tests ist zulässig, aber
keine gemeinsame echte Benutzer-Registry über mehrere Tests.

cwd, os.environ, sys.path, relevante sys.modules-Einträge, Zufallszustand,
Signalhandler, Caches, Singletons und Kindprozesse sind auf Leaks zu prüfen.
Verschiedene xdist-Worker sind unterschiedliche Prozesse, aber ein Worker
führt mehrere Tests nacheinander aus: Prozesszustand darf nicht zurückbleiben.
Keine pauschale Entfernung aller sys.modules-Einträge: Bibliotheksimporte und
pytest-Interna dürfen nicht beschädigt werden. Nicht verlässlich rücksetzbare
Import-/Signal-Szenarien gehören in kontrollierte Kindprozesse.

Auch dynamisch geladene Testhilfen können sys.path oder Modulregistrierungen
verändern. Diese Hilfen sind einzubeziehen. Prozesse werden bei Fehlern
aufgeräumt; keine verwaisten Lockhalter und keine pauschalen Benutzer-Löschungen.
Temporäre pytest-Caches und lokale .patchharbor-Metadaten gehören nicht in
parallel kopierte Packaging-Testquellen.

## Ergebnisnachweise (Bundle 2)

Nur der pytest-Controller darf einen gemeinsamen Abschlussnachweis erzeugen;
Worker schreiben isolierte Dateien oder liefern pytest-Reports zurück.
Unterschiedliche Testsammlungen, fehlende Tests/Workerergebnisse, abgestürzte
Worker, Setup-/Teardown-/Untertestfehler und unerwartete Skips dürfen keine
vollständig grüne Abnahme erzeugen. Diese Fehlerfälle werden gezielt injiziert.
Vorhandene pytest/xdist-Funktionen werden genutzt, nicht neu implementiert.
Eine neutrale Aggregation wird nur gebaut, soweit wirklich benötigt.

## Abnahme

Die vorhandene Testmenge darf nicht schrumpfen. Vollständige Läufe seriell,
-n 2, -n 4 und -n auto müssen fachlich dieselben Test-IDs, Eingaben und
Ergebnisse liefern. Reihenfolge, Workerzuordnung, Dauer, Zeitstempel und Lauf-ID
sind kein Vergleichskriterium. Mehrere Parallel-Läufe mit verschiedenen
PYTHONHASHSEED-Werten decken Reihenfolgeabhängigkeiten auf.

Normale CI verwendet am Ende xdist und behält mindestens einen blockierenden
seriellen Referenzlauf. Bestehende OS-/Python-/PowerShell-Abdeckungen bleiben.
Fehler/fehlende Resultate führen zu rotem CI-Status. Kein eigener Scheduler,
keine versteckten Retries. CI- und Docker-Umstellung erfolgt erst in Bundle 2.

Automatisiert geprüft werden Verhalten, Datenverträge, Zustandsübergänge,
Dateieffekte, Exitcodes, Fehlerfälle, Sicherheit, Wiederaufnahme, Idempotenz und
Parallelität. Keine exakten Konsolentexte, Farben, Spinner, Layouts oder
Dokumentation testen. Die Konsole darf weiterhin ausführlich und farbig sein.
