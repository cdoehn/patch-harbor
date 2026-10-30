# Entwicklungstests mit pytest-xdist

Historischer Einführungsplan: `planning/test-parallel/commit-plan.md` (15 echte W/R/C-Zwischenstände).
Historischer Vertrag: `planning/test-parallel/specification.md`.
**Aktuelle Nutzerentscheidung vom 29. Oktober 2026:** Development führt nur
ausgewählte, änderungsbezogene Tests parallel aus. Die vollständige parallele
Suite läuft im Apply vor jedem Commit, auch am Bundle-Ende. Keine seriellen Gates. Nur Christian selbst startet den weiterhin manuellen CI-Workflow.
Codex und Entrypoints starten keine CI; der frühere Fünfertakt entfällt.
Eine ausdrücklich aktivierte Schleife arbeitet den bestehenden Plan ohne feste Korrekturgrenze ab; ein einzelner Folgeauftrag startet keine Schleife.
Der vorhandene Watcher übernimmt ausschließlich fertig veröffentlichte Pakete.
Details und aktuelle Resultbindung: aktiver
`planning/1.5.0/commit-plan.md`.

## Historische Pixel-Phase: durch den Laptop-Wechsel beendet

Der folgende Abschnitt beschreibt die frühere Ausnahme und ist aktuell nicht aktiv.

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
keine neue Triggerinfrastruktur. Die damalige Fassung von
`scripts/run_handoff_ci.py` wartete auf den korrelierten Workflow inklusive
Windows/Docker; Ergebnis-/Berichtsprüfung auf
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

**Die folgenden Beispiele beschreiben die vorhandenen Werkzeuge. Für den aktiven
Auftrag gilt die obige Laptop-Policy: gezielte parallele Auswahl im Development,
vollständige parallele Commit-Gates im Apply.
Ein beschriebener Modusvergleich ist kein Auftrag, serielle Tests zu starten.**

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
Datei. Eine persistente JSON-Datei ist optional. Development dokumentiert seine
gezielte parallele Auswahl; ein vollständiger Bericht über diese Auswahl ist
kein Vollsuite-Nachweis. Apply benötigt den vollständigen parallelen Suite-Bericht
vor jedem Commit, auch am Bundle-Ende. Eine serielle Referenz ist nicht erforderlich:

```sh
python tools/run_tests.py --suite all --workers 4 --report /tmp/ph-parallel.json
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
Ein vollständiger Bericht darf deklarierte Skips enthalten. Bei einem separat
beauftragten Modusvergleich müssen auch die Skip-Gründe übereinstimmen.
Ein reiner Collection-Lauf ist niemals ein erfolgreicher Laufzeitnachweis.

Die Vergleichsbindung umfasst Quellbytes sowie Python-, Betriebssystem-, pytest-
und xdist-Version und die ausgewählte Windows-Engine. Quellen dürfen während
eines Laufs nicht wechseln. Lauf-ID, Zeit, Reihenfolge und Worker-Zuteilung
werden dagegen nicht fachlich verglichen. Ein Quellenwechsel erfordert einen
neuen parallelen Bericht zum vorgeschriebenen Umfang: gezielte Development-Auswahl
oder vollständiges Apply-Gate, auch bei Dokumentänderungen.
Alte Berichte eines anderen Standes sind kein Gate für neue Quellen. Nur der
separat beauftragte Modusverifier benötigt zusätzlich seine passende serielle
Referenz; er gehört nicht zum Development-/Apply-Ablauf.

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

Der Workflow wird ausschließlich von Christian selbst gestartet. Codex und
Apply-Entrypoints führen keinen Dispatch aus. Der bisherige automatische
Fünfertakt gilt nicht mehr. Fehlende CI allein blockiert keinen Folgepatch;
native Plattformabnahmen und Releasefreigabe bleiben bis zum passenden Nachweis
offen. Bekannte CI-Fehler werden weiterhin anhand tatsächlicher Ergebnisse
ausgewertet. Ein paralleler Linux-Lauf ersetzt keinen nativen Windows-Beleg.

Die manuelle CP-04-Matrix enthält zwölf Jobs: vollständige Gruppen auf Linux und
Windows mit CPython 3.10, 3.11 und 3.12, zusätzlich Linux mit 3.14, drei
PowerShell-7-Lanes (3.10/3.11/3.12) und die beiden bisherigen Docker-Lanes.
Jeder Job zeichnet die exakte Interpreterversion, aufgelöste Build-/Testwerkzeuge,
Quellbindung und SHA-256 der tatsächlich gebauten Wheel-, sdist- und PYZ-Dateien
auf. Native Hauptlanes laden alle vier Controller-Berichte hoch;
PowerShell 7 seinen erweiterten Windows-Bericht; Docker zusätzlich seine Logs.
Artefaktnamen enthalten Interpreter und Plattform, zum Beispiel
`patchharbor-packaging-windows-2025-py3.10`. Aufbewahrung: 14 Tage.

Nach Christians manuellem Start kann ein vorhandener Lauf einmal lesend geprüft
werden (Platzhalter durch Run-ID und vollständigen Commit ersetzen):

```sh
python scripts/run_handoff_ci.py --run-id RUN_ID --commit FULL_COMMIT_SHA
```

Der Helfer startet und wiederholt keinen Workflow und wartet nicht auf laufende
Jobs. Er bindet den vorhandenen Run und seinen Attempt an `dev` und den genannten
Commit, prüft alle zwölf Jobs sowie deren Build- und parallele Testnachweise und
speichert `build/manual-ci-review/RUN_ID-1/evidence.json`. Ein laufender Run wird
als `pending` mit Exitcode 2 erfasst. Eine spätere Auswertung benötigt ein neues
`--workspace`-Verzeichnis; ein vorhandener Nachweis wird nicht überschrieben.
Für einen von Christian gestarteten weiteren Attempt dient `--attempt NUMMER`.
Eine zusätzliche Handoff-ID ist für diese Auswertung nicht erforderlich.

Pflichtfälle für eigene Result-Anleitung, Core-PYZ, drei Installationsgenerationen,
CLI/API/Watcher und native Windows-Sicherheitsadapter müssen bestanden sein.
Skips und Collection-Skips werden separat erhalten. Historische eingefrorene
Laufzeiten mit eigener Mindestversion 3.12 werden auf älteren Interpretern nicht
als ausführbar behauptet; die Datenlesbarkeit alter Results und die neue
3.10-Produktion bleiben eigene Pflichtprüfungen. Native DACL-Fälle ändern nur
private temporäre Fixtures. CI ersetzt keine zusätzliche geforderte CIFS-Praxis
oder die abschließende Releaseentscheidung.

Im Development läuft nur die begründete parallele Testauswahl. Im Apply läuft
vor jedem Commitstand die vollständige parallele Suite, auch am Bundle-Ende;
kein serieller Vorlauf und kein
Vergleich mit einer seriellen Referenz:

```sh
.venv/bin/python tools/run_tests.py --suite all
```

Der Launcher verwendet standardmäßig xdist `auto`; eine ausdrücklich gewählte
positive Workerzahl bleibt zulässig. Der erfolgreiche Controller-Bericht muss
vollständige Sammlung, Workerabschlüsse, Phasen und unveränderte Quellen belegen.
Erst danach Commit und schließlich genau ein normaler Push. Erfolgreiche
Teilcommits und erhaltene Payloads bleiben bei Fehlern Grundlage der Korrektur.
Der Modusverifier bleibt ein explizites Diagnosewerkzeug außerhalb dieser Schleife.

Funktionale Tests prüfen auch ausführbare CI-/Docker-Verträge, nicht den Wortlaut
der Dokumentation oder die Konsolendarstellung. Ein erzeugtes Patchpaket, ein
lokales Testergebnis oder dieser Text ist keine externe CI-Freigabe. Jeder
W/R/C-Commit entsteht nur nach seinem eigenen Testgate; spätere Schritte bleiben
bis dahin unappliziert. Bei Fehler bleiben erfolgreiche Commits bestehen.

## Stabile Abnahmenachweise und CI-Katalog (RF-11)

`tools/acceptance-catalog.json` enthält die zwölf unveränderten CI-Lanes,
Windows-Testauswahl, Build-Artefaktrollen und die erforderlichen Nachweisvarianten.
Nach einer bewussten Katalogänderung pflegt
`python scripts/render_acceptance_matrix.py` nur die markierten Matrixblöcke in
`.github/workflows/acceptance-tests.yml`. `--check` prüft diese ohne Schreiben;
die manuellen Jobs führen diese Prüfung ebenfalls aus. Beide Modi starten keine CI.

Ein fachlicher Test trägt zum Beispiel
`@pytest.mark.proof("handoff.commit-sequence", parameter="count")`.
Die Varianten stammen aus dem tatsächlichen Parameterwert (`0`, `1`, `3`),
nicht aus Funktionsnamen oder frei wählbaren pytest-IDs. Unparametrisierte
Nachweise verwenden die Variante `default`. Genau eine Kennung pro Testfall
ist erlaubt; unbekannte IDs, Varianten oder Parameter werden abgewiesen.

Neue interne Testberichte verwenden `format_version: 2`. `proofs` ordnet
gesammelten Node-IDs jeweils `id` und `variant` zu. Jeder Worker bestätigt die
gleiche Zuordnung, auch wenn er keinen Test ausgeführt hat. Die neutrale
Prüfung erhält alle bisherigen Phasen-, Collection-, Input- und Worker-Gates
und verwirft doppelte Varianten oder widersprüchliche Zuordnungen. Der
CI-Auswerter verlangt jede im Katalog für die Lane vorgeschriebene Variante
genau einmal mit bestandenem Ergebnis über alle Suite-Berichte hinweg.
Ein Skip oder ein einzelner beliebig markierter Fall ersetzt keine übrigen Varianten.

Neue Buildberichte verwenden Format 2, nennen `wheel`, `sdist`, `pyz` als Rollen
und verlangen Testberichtformat 2. Neue CI-Reviewbelege verwenden Format 3 und
speichern die geprüften Pflichtvarianten samt Bericht und Test-ID. Historische
Build-/Testberichte im Format 1 bleiben prüfbar: Nur dort dient eine eingefrorene
Namenszuordnung als Übersetzung. Eine Mischung alter Testberichte mit neuen
Buildberichten wird abgewiesen. Öffentliche PatchHarbor-Result-/Patch-Formate
bleiben davon unberührt. Die bestehenden Lauf-/Commit-/Interpreterbindungen,
ZIP-Budgets und ausschließlich lesenden GitHub-Aufrufe bleiben verbindlich.
