# Entwicklungstests mit pytest-xdist

Plan: `planning/test-parallel/commit-plan.md` (15 echte W/R/C-Zwischenstände).
Historischer Vertrag: `planning/test-parallel/specification.md`.
Bisherige Nutzerregel vom 3. Oktober 2026: Development ausschließlich parallel;
Apply-Zwischenstände parallel, nur am Bundle-Ende seriell und parallel.
**Auf dem Pixel wird diese Regel durch die nachstehende Entscheidung vom
7. Oktober 2026 ersetzt, bis der Nutzer ausdrücklich zum Laptop wechselt.**

## Aktive Pixel-Phase: nur automatisch gestartete parallele CI

Gilt für PatchHarbor ab Bundle **027 / PP-01-FIX1** und für alle folgenden
Pixel-Bundles, bis Christian ausdrücklich seinen Wechsel auf den Laptop
bestätigt. Keine automatische Rückkehr zu lokalen Tests beim nächsten
Planpunkt, Bundle oder Datum. Die ursprünglich nur für PP-00 erklärte
Ausnahme ist historisch; diese spätere Nutzerregel ist nicht einmalig.

**Auf dem Pixel keine Produkttests und keine Testinstallation.** Das umfasst
lokale Voll-, Teil- und Smoke-Suites, pytest/Collection, serielle oder parallele
Läufe, Modusverifier und Development-Setup über venv/pip/uv/test.sh. Vorhandene
Testberichte, ignorierte Entwicklungsumgebungen und unterbrochene Änderungen
bleiben erhalten. Sie werden weder gelöscht noch als grüne Nachweise verwendet.
Commit- und Push-Hooks werden nur in diesen Aufrufen mit
`git -c core.hooksPath=/dev/null ...` deaktiviert; keine dauerhafte Einstellung.

Der Ablauf eines eincommittigen Bundles lautet:

```text
Core-/Bindungs-/Datei-/Git-Scopeprüfungen (keine Produkttests)
→ ein fachlicher Commit → normaler Push
→ einmaliger automatischer Dispatch des vorhandenen CI-Workflows
→ alle sechs Jobs und die zum Commit gehörenden Nachweise prüfen
→ unveränderten sauberen Zielzustand bestätigen → Gesamterfolg
```

Die Tests laufen ausschließlich in der GitHub-CI, parallel mit dem vorhandenen
xdist-`auto`-Vertrag. Keine zusätzliche serielle Suite, kein Modusvergleich und
keine neue Triggerinfrastruktur. `scripts/run_handoff_ci.py` wartet auf den
korrelierten Workflow inklusive Windows/Docker; Ergebnis-/Berichtsprüfung auf
dem Pixel ist kein lokaler Testlauf. Der native Bericht muss tatsächlich Worker
belegen. Plattform-Skips bleiben Skips, keine erfundenen Zielplattformnachweise.

**Jedes änderungsführende Pixel-Bundle benötigt seinen zugeordneten Lauf.** Die
Fünferregel ist während dieser Phase ausgesetzt: nicht bis 029 warten, keinen
zweiten Lauf an einem alten Zähltermin starten. Bei mehreren Zwischenzuständen
muss die externe CI jedes zu prüfenden Zustands vor dessen Fortsetzung grün sein;
vorzugsweise getrennte Bundles statt ungetesteter nomineller Commitketten.
Bundle 027 führt genau einen Commit/Push und einen Dispatch aus.

Fehlender Zugang, fehlende/rote/unvollständige CI oder Abbruch führt nicht zu
lokalen Ersatztests oder einem Erfolgsmarker. Kein automatischer Retry, Rerun,
Force-Push oder Rollback. Ein bereits erzeugter Commit bleibt bestehen. Ein
Laptop-Wechsel wird nicht aus Betriebssystem oder Pfad geraten; die dann wieder
maßgebliche Testpolicy wird nach dem ausdrücklichen Wechsel neu eingeordnet.

Paket-/Bindungsprüfung und leichte Syntax-/Hash-/Git-Prüfungen bleiben erlaubt;
sie werden nie als bestandene Produkt- oder Plattformtests ausgegeben.
Details und aktuelle Bindung: [aktiver Plan, Abschnitt 1.8](../planning/pyz-pack/commit-plan.md#18-pp-01-fix1--bundle-027-pixel-phase-nur-parallele-ci).

### Historie der vorherigen Ausnahmen

PP-00 / Bundles 024/025 hatten eine einmalige CI-only-Ausnahme. Das Result von
025 bestätigt Commit `7a28bbc2189cdb2a78590e62a45e4d96b0ff893d` und sechs
erfolgreiche Jobs in CI-Run `37635401106`. Bundle 026 kehrte zu lokalen Gates
zurück; sein serieller Lauf wurde auf dem Pixel unterbrochen, bevor Commit,
Push oder CI erreicht wurden. Das hat die obige spätere Dauerregel ausgelöst.
Alte Aussagen „PP-00 allein“ und „nächste CI 029“ beschreiben nur diese Historie.

**Die folgenden lokalen Beispiele dokumentieren die Basispolicy außerhalb
der aktiven Pixel-Phase. Auf dem Pixel sind sie derzeit nicht auszuführen.**

## Teststart

In der Entwicklungs-venv die deklarierten Abhängigkeiten installieren:

```sh
python -m pip install -e '.[dev]'
python tools/run_tests.py
python tools/run_tests.py --workers 4
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
Datei. Eine persistente JSON-Datei ist optional. Development benötigt nur den
parallelen Bericht; das Vergleichspaar gehört ans Apply-Bundle-Ende:

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
neue serielle Referenz, auch wenn nur Dokumentation geändert wurde. Development
führt keine seriellen Referenzläufe aus und vergleicht seinen neuen parallelen
Bericht nicht mit einem veralteten seriellen Stand.

## Vollständige Modusabnahme

```sh
python tools/verify_test_modes.py --outdir /tmp/ph-mode-check-001
```

Dieser Modusvergleich ist kein Development- oder reguläres Apply-Gate.
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
Der GitHub-Acceptance-Workflow startet ausschließlich per
`workflow_dispatch`: keine Push-/Pull-Request-Auslöser, kein Schedule/Nightly und
kein zusätzlicher serieller Volltestlauf. Die vorhandenen Linux-, Windows-,
PowerShell- und Docker-Gates bleiben blockierend und verwenden die parallele
Runner-Policy. Keine optionalen Tests, kein continue-on-error und keine stillen
Retries.

**Außerhalb der aktiven Pixel-Phase gilt die nachfolgende Basispolicy. Während
der Pixel-Phase tritt an ihre Stelle die CI-Pflicht pro Änderung aus dem
Anfang dieses Dokuments; die lokalen Gate-Befehle unten bleiben deaktiviert.**

Seit der Nutzeranweisung vom 4. Oktober 2026 läuft reguläre GitHub-CI nur nach
jeweils fünf weiteren Bundles: Basis ist der manuelle Lauf zu Bundle 009,
nächste Stände 014, 019 usw., nach tatsächlichem Apply/Push. Zwischenbundles
brauchen keinen eigenen Lauf; fehlende CI auf ihrem Commit allein blockiert
keinen Folgepatch. Bekannte CI-Fehler weiter auswerten; zusätzliche Läufe nur
auf ausdrücklichen Auftrag. Native Freigaben gelten für die tatsächlich
geprüften Stände. Die lokalen parallelen bzw. finalen seriellen/parallelen
Gates bleiben unverändert.

Bei fälligen Bundles startet der ausdrücklich beauftragte Apply-Entrypoint nach
erfolgreichem Push den vorhandenen Workflow per `workflow_dispatch` und wartet
auf alle vorgeschriebenen Jobs einschließlich Windows. Er gibt Run-ID, URL,
vollständigen geprüften Commit, Job-Ergebnisse sowie relevante Testnachweise
oder Fehlerdiagnosen über das Ausführungslog im Result zurück. GitHub-Zugang
mit passenden Rechten muss vorhanden sein. Fehlende/rote CI bleibt sichtbar;
kein vorzeitiger Gesamterfolg, kein automatischer Retry. Diese Regel gehört
zu PatchHarbor, nicht zur allgemeinen S-Schleife.

Die native Packaging-Lane speichert seit `1.c.R-FIX1` ihren Controller-Bericht
unter `${{ runner.temp }}/patchharbor-packaging-tests.json` und lädt ihn auch bei
Fehlern als `patchharbor-packaging-<runner>` hoch (14 Tage Aufbewahrung).
Fehlende Dateien sind Fehler. Der JSON-Bericht enthält Sammlung, Phasen,
Workerabschlüsse, Plattform/Interpreter und Quellbindung; ein Upload allein
ist kein bestandenes Gate. Die erforderlichen Runtime-/Windows-Rechtefälle
und Zuordnung zum tatsächlichen Run-HEAD stehen in `docs/runtime-artifact.md`.
Die DACL-Tests ändern ausschließlich Rechte ihrer privaten temporären Fixtures;
Linux-Ausführung und Windows-Skips ersetzen keinen nativen Windows-Beleg.

Im Development läuft jeder Zwischenstand ausschließlich parallel. Im lokalen
Apply-Entrypoint läuft vor jedem Zwischencommit die vollständige parallele Suite.
Nur der letzte Zustand am Bundle-Ende durchläuft diese beiden vollständigen
Gates auf unveränderten Quellen, vor dem letzten Commit:

```sh
.venv/bin/python tools/run_tests.py --suite all --serial
.venv/bin/python tools/run_tests.py --suite all
```

Der abschließende parallele Lauf verwendet `auto` und erfüllt zugleich das
Commit-Gate des letzten Zustands; ein zusätzlicher identischer Vorlauf ist nicht
erforderlich. Erst nach beiden grünen Endgates entstehen letzter Commit und
genau ein normaler Push auf den bestätigten Zielbranch, ohne Tag oder Force-Push.
Ein Pushfehler erhält die erfolgreichen lokalen Commits. Diagnosebundles mit
null Commits haben auftragsbezogene Prüfungen und keinen Push. Diese Nutzerregel
ersetzt serielle Tests vor jedem Zwischencommit. Der Modusverifier bleibt ein
explizites Diagnosewerkzeug; CI startet nur durch den beauftragten Dispatch.

Funktionale Tests prüfen auch ausführbare CI-/Docker-Verträge, nicht den Wortlaut
der Dokumentation oder die Konsolendarstellung. Ein erzeugtes Patchpaket, ein
lokales Testergebnis oder dieser Text ist keine externe CI-Freigabe. Jeder
W/R/C-Commit entsteht nur nach seinem eigenen Testgate; spätere Schritte bleiben
bis dahin unappliziert. Bei Fehler bleiben erfolgreiche Commits bestehen.
