# Entwicklungstests mit pytest-xdist

Plan: `planning/test-parallel/commit-plan.md` (15 echte W/R/C-Zwischenstände).
Vertrag: `planning/test-parallel/specification.md`.

## Teststart

In der Entwicklungs-venv die deklarierten Abhängigkeiten installieren:

```sh
python -m pip install -e '.[dev]'
python tools/run_tests.py
python tools/run_tests.py --workers 4
python tools/run_tests.py --serial
python tools/run_tests.py --workers 2 -- tests/test_configuration.py
```

Ohne Modusargument verwendet der Launcher **auto**, unverändert an xdist
weitergegeben. `--serial` verwendet `-n 0`; feste positive Workerzahlen bleiben
wählbar. `scripts/test.sh` richtet die lokale `.venv` ein und delegiert an
denselben Launcher. Unter Windows wird der Python-Einstieg benutzt. Keine
Runtime-Abhängigkeit, kein eigener Scheduler, keine produktive Neuinstallation.

Nur nach `--` übergebene Selektoren erzeugen eine gezielte Teilabnahme, niemals
unbemerkt eine Vollabnahme. Alternativ gibt es die zentralen CI-Suites `core`,
`e2e`, `platform`, `packaging`, `windows` und `all` über `--suite`. Eine benannte
Teilsuite kann nicht zugleich durch weitere Selektoren umdefiniert werden.
Geerbte `PYTEST_ADDOPTS` werden nur im Kindprozess geleert. Workerzahl,
Schedulerwechsel, Neustarts und Nachweisoptionen lassen sich nicht heimlich
über den normalen Argument-Passthrough umschalten.

Direktes `python -m pytest -n 0` beziehungsweise `-n 2/4/auto` bleibt möglich,
aktiviert aber nicht automatisch die zusätzlichen Nachweisprüfungen des
Launchers. Rohes pytest übernimmt zudem geerbte `PYTEST_ADDOPTS`.

## Laufzeit und Isolation

Der Launcher deaktiviert pytest-timeout und führt keine Test-/Suitefrist ein.
Produkt-Timeouttests, kontrollierte Prozessprüfungen, Docker-Build-/Preflight-
Grenzen und äußere CI-Joblimits bleiben eigenständige Mechanismen. Für lange
Patchfolgen wird das äußere Limit ausdrücklich mit
`patchharbor apply --timeout 28800 ...` erhöht; das ZIP erhöht es nicht selbst.
Auf einem knappen Gerät kann `--workers 2` oder `--workers 4` sinnvoller als
`auto` sein. Es gibt keine garantierte Laufzeit oder lineare Beschleunigung.

Pro Test gelten eigene Home-/Config-/State-/Temp-/Git-Umgebungen. Nach dem
Fixture-Teardown prüft die Prozesswache cwd, Umgebungsvariablen, sys.path,
globalen Zufallszustand und SIGINT/SIGTERM-Handler. Leaks werden als Fehler
gemeldet und der Zustand wird für nachfolgende Tests zurückgesetzt.
PYTEST_CURRENT_TEST ist eine von pytest verwaltete Ausnahme. Dynamische
Hilfsimporte und gezielt veränderte sys.modules-Einträge werden explizit
zurückgesetzt; normale Lazy-Imports werden nicht pauschal entladen. Neue
Caches/Singletons brauchen ihre eigene Isolation. Packaging arbeitet auf
privaten Kopien, ohne lokale .patchharbor-Daten oder flüchtige pytest-Caches.
Prozess-/Locktests bleiben erhalten; es wird kein echter systemd-Dienst gestartet.

## Controller-Nachweise

Jeder Launcher-Lauf aktiviert die Vollständigkeitsprüfung, auch ohne gespeicherte
Datei. Eine persistente JSON-Datei ist optional:

```sh
python tools/run_tests.py --serial --report /tmp/ph-serial.json
python tools/run_tests.py --workers 4 --report /tmp/ph-parallel.json --reference /tmp/ph-serial.json
```

Berichte gehören außerhalb der getesteten Quellen. Jeder gleichzeitige Aufruf
braucht einen eigenen Ausgabepfad; unterschiedliche Controller koordinieren
keine gemeinsam benannte Datei. Innerhalb eines Laufs schreibt ausschließlich
der Controller atomar. Worker liefern Phasenberichte und einen Abschlussbeleg
mit Laufbindung, Sammlung, Berichtanzahl und Bericht-Multimengenhash zurück.
Auch ein Worker ohne zugeteilten Test muss seinen Abschluss liefern.

`tools/test_evidence.py` ist der pytest/xdist-Adapter, `tools/test_results.py`
das neutrale Ergebnis-Modell und `tools/result_io.py` die atomare Speicherung.
Keines davon verteilt Tests. Originale pytest-Fehlercodes bleiben rot; eine
zusätzlich unvollständige Nachweislage macht einen sonst grünen Lauf ebenfalls
rot. Worker-Neustarts sind deaktiviert. Fehlende oder doppelte Phasen, fehlende
Worker-Abschlüsse, verlorene Reports, abweichende Sammlungen, Setup-/Teardown-
und Untertestfehler werden durch absichtliche Fehlerfälle überprüft.

Die Sammlung enthält ausführbare Test-IDs separat von bereits bei der Sammlung
übersprungenen Modulen. Skips werden nicht als bestandene Tests ausgegeben.
Ein vollständiger Bericht darf deklarierte Skips enthalten; ein neuer Skip oder
ein veränderter Skip-Grund kann nicht mit der seriellen Referenz übereinstimmen.
Ein reiner Collection-Lauf ist niemals ein erfolgreicher Laufzeitnachweis.

Die Vergleichsbindung umfasst Quellbytes sowie Python-, Betriebssystem-, pytest-
und xdist-Version und die ausgewählte Windows-Engine. Quellen dürfen während
eines Laufs nicht wechseln. Lauf-ID, Zeit, Reihenfolge und Worker-Zuteilung
werden dagegen nicht fachlich verglichen. Ein Quellenwechsel erfordert eine
neue serielle Referenz, auch wenn nur Dokumentation geändert wurde.

## Vollständige Modusabnahme

```sh
python tools/verify_test_modes.py --outdir /tmp/ph-mode-check-001
```

Das Ziel darf noch nicht existieren. Nacheinander laufen vollständige Suites:
seriell, zwei, vier und auto Worker mit Hash-Seed 0; danach zwei Worker mit Seed 1,
vier mit Seed 42 und auto mit Seed 314159. Alle Berichte werden mit derselben
seriellen Referenz verglichen: IDs, Phasenvollständigkeit, Ergebnisse, Subtests,
Collection-Skips und gebundene Eingaben. Report-Ankunftsreihenfolge und Laufzeiten
sind keine Abnahmebedingung. Schon ein fehlender oder abweichender Nachweis
stoppt den Ablauf. Vorhandene Berichte bleiben zur Diagnose erhalten.

Mit nach `--` explizit gewählten Tests ist ein kurzer Werkzeugtest möglich,
aber keine Vollabnahme der PatchHarbor-Suite. Der Verifier startet komplette
pytest-Läufe nacheinander und baut keinen zusätzlichen Test-Scheduler.

## CI und Git-Freigabe

Native OS-/Python-/PowerShell-Lanes und Docker verwenden dieselben benannten
Suites über den Launcher und damit xdist. Die bisherige Abdeckung bleibt erhalten.
Eine zusätzliche blockierende Ubuntu-24.04/Python-3.12-Lane führt die vollständige
Suite seriell aus und lädt ihren JSON-Bericht auch im Fehlerfall als Artefakt
hoch. Keine optionalen Tests, kein continue-on-error und keine stillen Retries.

Funktionale Tests prüfen auch ausführbare CI-/Docker-Verträge, nicht den Wortlaut
der Dokumentation oder die Konsolendarstellung. Ein erzeugtes Patchpaket, ein
lokales Testergebnis oder dieser Text ist keine externe CI-Freigabe. Jeder
W/R/C-Commit entsteht nur nach seinem eigenen Testgate; spätere Schritte bleiben
bis dahin unappliziert. Bei Fehler bleiben erfolgreiche Commits bestehen.
