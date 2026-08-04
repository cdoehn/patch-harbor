# PatchHarbor 1.1.0 – Cleanup- und Rückbau-Commit-Plan

**Dateiname:** `planning/1.1.0/commit-plan.md`  
**Zielversion:** `1.1.0`  
**Planphase:** Rückbau und Bereinigung vor der Implementierung neuer 1.1.0-Funktionen  
**Stand:** 2026-08-04  
**Ausgangsbasis:** vorhandene Implementierung 1.0.0 mit der verbindlichen `spec/SPECIFICATION.md` und `spec/SPECIFICATION_CHANGELOG.md` für 1.1.0

---

## 1. Zweck dieses Plans

Dieser Commit-Plan entfernt zuerst alle tatsächlich vorhandenen Implementierungsreste und Zukunftsvorbereitungen, die nach der Spezifikation 1.1.0 nicht mehr zu PatchHarbor gehören.

Er implementiert bewusst noch nicht:

- Repository-Registry und UUID,
- Kontext und Fingerprint,
- `patch.json`,
- den sicheren `apply`-Pfad,
- Repository-Locks,
- Dry-Run,
- Result Bundle,
- PatchHarbor Watcher.

Nach Abschluss dieses Plans besitzt das Repository eine kleine, grüne und widerspruchsfreie 1.0.0-Codebasis, auf der die neuen 1.1.0-Funktionen ohne Altlasten aufgebaut werden können.

---

## 2. Verbindliche Arbeits- und Commit-Regeln

Für jeden Commit dieses Plans gilt:

1. Der Commit hat genau eine erkennbare Absicht.
2. Produktionscode, zugehörige Tests und notwendige Dokument- beziehungsweise Audit-Anpassungen werden gemeinsam abgeschlossen.
3. Alle Testläufe besitzen harte Timeouts.
4. Schlägt ein vorgesehener Test fehl, wird kein Commit erstellt.
5. Nach jedem Commit ist der Arbeitsbaum auf unbeabsichtigte Dateien und temporäre Artefakte zu prüfen.
6. Historische Dokumente werden nicht rückwirkend umgeschrieben.
7. Neue 1.1.0-Produktfunktionen werden in dieser Cleanup-Phase nicht vorgezogen.
8. Die Versionsnummer des installierbaren Produkts wird während des reinen Rückbaus nicht vorzeitig auf 1.1.0 erhöht.

Empfohlener vollständiger lokaler Testlauf nach jedem Commit:

```bash
PATCHHARBOR_TEST_TIMEOUT_SECONDS=120 \
PATCHHARBOR_TEST_SUITE_TIMEOUT_SECONDS=900 \
PATCHHARBOR_TEST_DURATIONS=10 \
./scripts/test.sh
```

Bei einem roten Testlauf:

```text
kein Commit
→ Fehler beheben
→ denselben Testlauf erneut vollständig ausführen
→ erst bei grünem Ergebnis committen
```

---

## 3. Befund des aktuellen Snapshots

### 3.1 Aktuell wirklich implementiert und zu entfernen

Der alte zweite Dateiübertragungsweg ist vollständig implementiert:

- Parser erkennt spezielle Skriptkommentarblöcke für Dateien.
- `PayloadFile` und `ParsedScript.payload_files` bilden diese Dateien ab.
- `application.py` bereitet die Textdateien vor und schreibt sie vor der Skriptausführung.
- `payload_files.py` besitzt einen eigenen Textdatei-Pfad neben dem ZIP-Nutzdateipfad.
- Die Terminaldarstellung kennt zusätzliche `inline_files`.
- Unit-, E2E-, Plattform- und Akzeptanztests sichern dieses Verhalten ab.
- Ein E2E-Test behandelt textuell codierte Binärdaten ausdrücklich als unveränderten Text.

Dieser vollständige Pfad wird entfernt.

### 3.2 Nicht implementiert, aber noch als zukünftiger Scope erwähnt

Im Runtime-Code existieren derzeit keine Module oder Abhängigkeiten für:

- Netzwerk- oder Chattransport,
- Clipboard,
- SSH,
- Save-Modus,
- öffentliches Plugin-System,
- Zielprojekt-Testmanagement,
- Git-Commitmanagement.

Es existieren aber noch veraltete Vorbereitungen und Zukunftslisten in Tests:

- CLI-Help-Test mit einer Liste „deferred features“,
- Packaging-Test mit derselben Zukunftsliste,
- `DEFERRED_FEATURE_MODULES` im Release-Audit,
- ein Release-Audit, der noch die alte 1.0.0-Spezifikation und den früheren nachgelagerten Transport-Meilenstein erwartet.

Diese Zukunftsvorbereitungen werden entfernt. Es wird kein nicht vorhandener Runtime-Code vorgetäuscht oder gelöscht.

### 3.3 Kein automatischer Decoder vorhanden

Im aktuellen Runtime-Code existiert kein automatischer Decoder für textuell codierte Binärdaten.

Daher gilt:

- Es wird kein Decoder aus dem Produktionscode entfernt.
- Der alte Inline-Test mit codiertem Text wird zusammen mit dem Inline-Dateipfad entfernt.
- Der Plattformtest für echte binäre ZIP-Nutzdateien wird so umgeschrieben, dass er die Bytes direkt prüft und keine Textcodierung als Testhilfsmittel verwendet.

### 3.4 Weitere Inkonsistenzen zur aktuellen Spezifikation

Der aktuelle Snapshot enthält außerdem:

- einen Release-Audit-Test, der weiterhin `1.0.0` in der aktuellen Spezifikation erwartet,
- einen leeren `planning/1.1.0/commit-plan.md`,
- Ubuntu 26.04 im Acceptance-Workflow noch als nicht blockierende Preview-Lane,
- einen statischen Workflow-Test, der genau diese veraltete Preview-Regel erzwingt.

Diese Punkte werden im ersten Commit korrigiert.

### 3.5 Aktueller bekannter Teststand

Ein lokaler Lauf der Kern-, Architektur- und E2E-Tests ohne Packaging-, Acceptance- und Plattformmarker ergab:

```text
321 passed
1 failed
17 deselected
```

Der einzige Fehler stammt aus `tests/test_release_audit.py`, weil der Test noch die alte 1.0.0-Dokumentstruktur erwartet.

---

## 4. Was laut Spezifikation ebenfalls nicht zu PatchHarbor gehört

Die Spezifikation schließt weitere Funktionen aus. Im aktuellen Snapshot existiert dafür jedoch kein rückzubauender Produktcode.

| Ausgeschlossene Funktion | Befund im Snapshot | Cleanup-Aktion |
|---|---|---|
| Netzwerk- oder Chatquelle im Core | nicht implementiert | veraltete Zukunfts- und Auditverweise entfernen |
| Clipboard-Quelle | nicht implementiert | veraltete Zukunftslisten entfernen |
| SSH-Quelle | nicht implementiert | veraltete Zukunftslisten entfernen |
| öffentliches Plugin-System | nicht implementiert | nichts aus Runtime entfernen |
| Save-Modus mit chmod | nicht implementiert | veraltete Zukunftslisten entfernen |
| Zielprojekt-Testmanagement | nicht implementiert | nichts aus PatchHarbors eigener Testsuite entfernen |
| Git-Commit-, Branch-, Tag- oder Release-Management | nicht implementiert | keine Git-Zustandsgrundlagen für 1.1.0 entfernen |
| interaktive Kindskripte | bereits durch geschlossenes Kind-STDIN verhindert | bestehende Schutztests behalten |
| rekursive Ordnersuche | aktueller Scan ist bereits nicht rekursiv | bestehende Implementierung und Tests behalten |
| rekursive Auflösung enthaltener Archive | wird nicht implementiert | ZIP-Dateien als normale Nutzdateien weiterhin zulassen |
| globale Pakettransaktion und Rollback | nicht implementiert | atomisches Schreiben einzelner Dateien behalten |
| dauerhafte Logverwaltung und Rotation im Core | nicht implementiert | vorhandenes temporäres Run-Log behalten |
| automatisches Einsammeln von Diagnoseartefakten | nicht implementiert | nichts entfernen |
| Upload- und Downloadlogik im Core | nicht implementiert | nichts entfernen |
| Submodule im sicheren 1.1.0-Pfad | sicherer Pfad noch nicht implementiert | erst im späteren Fingerprint-/Apply-Plan ablehnen |

Wichtig:

> PatchHarbors eigene Tests, Git-Befehle für den späteren Repository-Zustand und die vorhandene CI-/Release-Infrastruktur sind nicht mit „Zielprojekt-Testmanagement“ oder „Git-Commitmanagement“ zu verwechseln.

---

## 5. Was ausdrücklich erhalten bleibt

Der Rückbau darf folgende gültige 1.0.0-Funktionen nicht beschädigen:

- `patchharbor fs run [PFAD]`,
- direkte Skriptdatei,
- gepipetes STDIN,
- einmaliger nicht rekursiver Ordnerscan,
- Auswahl genau eines Ordnerkandidaten,
- ZIP-PatchBundles,
- mehrere geordnete Skripte in einem ZIP,
- echte bytegenaue ZIP-Nutzdateien einschließlich Binärdateien,
- sichere relative ZIP-Pfade,
- Vorvalidierung aller ZIP-Ziele,
- atomischer Austausch einzelner Nutzdateien,
- META,
- MESSAGE,
- Pflichtmarker `# PATCHHARBOR`,
- Bash und PowerShell,
- geschlossenes Kind-STDIN,
- Timeout und vollständiger Prozessbaum,
- Strg+C-Vertrag,
- Plain-Ausgabe,
- feste Terminaldarstellung,
- der sichtbare Bereich `FILES` für echte ZIP-Nutzdateien,
- temporäres vollständiges Run-Log,
- Ressourcenlimits,
- ZIP-Bomben-Schutz,
- `InputArtifact` und die kleine gemeinsame Datei-/STDIN-Grenze,
- exakte Runtime-Modulinventur,
- pipx- und Wheel-Verträge.

Ebenfalls unverändert bleiben:

- `planning/1.0.0/commit-plan.md` als historisches Dokument,
- historische Einträge in `spec/SPECIFICATION_CHANGELOG.md`.

Historische Dokumente dürfen weiterhin frühere Funktionsnamen nennen. Sie sind kein aktiver Produktvertrag.

---

# Cleanup-Meilenstein – Altpfade vollständig entfernen

## Ziel

Nach diesem Meilenstein existiert im aktiven Runtime-, Test-, Packaging- und CI-Pfad nur noch der weiterhin gültige ZIP-basierte Nutzdateiweg. Nicht implementierte Transportideen werden nicht mehr als „späteres PatchHarbor-Feature“ vorbereitet.

## Definition of Done

- Die aktuelle Dokumentstruktur wird korrekt auditiert.
- Ubuntu 26.04 ist ein blockierendes Release-Gate.
- Der alte Skriptkommentar-Dateipfad existiert nicht mehr.
- Parser, Datenmodelle und Anwendung kennen nur noch META und MESSAGE als optionale Skriptinformationen.
- `payload_files.py` enthält ausschließlich den sicheren ZIP-Nutzdateipfad.
- Die Präsentation besitzt keine `inline_files`-Schnittstelle mehr.
- Der Bereich `FILES` zeigt weiterhin echte ZIP-Nutzdateien.
- Es gibt keinen alten codierten Inline-Transporttest mehr.
- Der binäre ZIP-Payloadtest prüft Bytes direkt.
- Veraltete Zukunftslisten für Transport-, Save-, Test- und Git-Module sind entfernt.
- Alle Unit-, Architektur-, E2E-, Acceptance-, Plattform- und Packaging-Tests sind grün.
- Ubuntu 24.04, Ubuntu 26.04 und der echte Windows-Runner sind grün.
- Noch keine neue 1.1.0-Funktion ist implementiert.

---

## Commit 1 – Dokument-, Audit- und CI-Basis auf 1.1.0 ausrichten

**Commit-Message:**

```text
docs: establish PatchHarbor 1.1.0 cleanup baseline
```

### Ziel

Die neue Spezifikation, der Changelog und dieser Commit-Plan bilden den verbindlichen aktiven Dokumentstand. Release-Audit und CI prüfen nicht länger den abgeschlossenen 1.0.0-Plan als aktuelle Produktspezifikation.

### Änderungen

#### Dokumente

- `spec/SPECIFICATION.md` als aktuelle 1.1.0-Spezifikation führen,
- `spec/SPECIFICATION_CHANGELOG.md` als aktuellen Spezifikations-Changelog führen,
- diesen Plan unter `planning/1.1.0/commit-plan.md` einchecken,
- `planning/1.0.0/commit-plan.md` unverändert als Historie behalten.

#### Release-Audit

`tests/test_release_audit.py` so ändern, dass der Test:

- die aktuelle Produktversion `1.1.0` in `spec/SPECIFICATION.md` erwartet,
- `spec/SPECIFICATION_CHANGELOG.md` erwartet,
- den nicht leeren Plan `planning/1.1.0/commit-plan.md` erwartet,
- den historischen 1.0.0-Plan nur noch auf Vorhandensein prüft,
- keine alten `60 / 60`-, Step-5- oder nachgelagerten Transportaussagen mehr aus der aktuellen Spezifikation verlangt,
- die exakte Runtime-Modulinventur weiterhin prüft,
- die leere Runtime-Abhängigkeitsliste weiterhin prüft.

#### CI

`.github/workflows/acceptance-tests.yml` ändern:

- Ubuntu 24.04 bleibt Release-Gate,
- Windows 2025 bleibt Release-Gate,
- Ubuntu 26.04 wird ebenfalls Release-Gate,
- `continue-on-error` für Ubuntu 26.04 entfällt,
- die Preview-Eigenschaft entfällt, sofern sie danach keinen Zweck mehr besitzt.

`tests/test_github_actions.py` entsprechend ändern:

- drei blockierende Lanes erwarten,
- keine Preview-Lane erwarten,
- kein `continue-on-error` erwarten.

### Nicht enthalten

- keine Produktionscodeänderung,
- keine Entfernung des alten Dateipfads,
- keine neue 1.1.0-CLI.

### Zieltests

```bash
timeout --foreground 180s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    tests/test_release_audit.py \
    tests/test_github_actions.py
```

Danach vollständiger lokaler Testlauf über `./scripts/test.sh`.

### Commit-Gate

- gezielte Tests grün,
- vollständiger lokaler Testlauf grün,
- kein Produktionscode verändert,
- historischer 1.0.0-Plan unverändert.

---

## Commit 2 – Veraltete Zukunfts- und Transportvorbereitungen entfernen

**Commit-Message:**

```text
test: remove obsolete deferred transport scaffolding
```

### Ziel

Nicht implementierte und nicht mehr PatchHarbor zugeordnete Transportideen werden nicht länger als „deferred PatchHarbor features“ in Tests und Audits vorbereitet.

### Änderungen

#### CLI-Test

In `tests/test_cli.py`:

- die Schleife über veraltete „deferred features“ entfernen,
- stattdessen nur die positiv definierte öffentliche CLI-Oberfläche prüfen,
- keinen zukünftigen Transport- oder Save-Scope in PatchHarbor festschreiben.

#### Packaging-Test

In `tests/test_packaging_e2e.py`:

- dieselbe Zukunftsliste entfernen,
- weiterhin die tatsächliche installierte CLI, Help-Ausgabe, Version und den echten Run prüfen.

#### Release-Audit

In `tests/test_release_audit.py`:

- `DEFERRED_FEATURE_MODULES` entfernen,
- die exakte Runtime-Modulinventur als ausreichenden Vertrag behalten,
- keine Modulnamen für nicht mehr vorgesehene PatchHarbor-Funktionen als Zukunftsplanung führen.

#### Binärer Plattformtest

In `tests/test_platform_e2e.py`:

- den binären ZIP-Nutzdateitest behalten,
- die Datei weiterhin vor der ersten Skriptausführung bytegenau prüfen,
- die Prüfung ohne textuelle Binärcodierung durchführen,
- unter PowerShell die tatsächliche Bytefolge oder einen direkt berechneten Byte-/Hexvergleich verwenden,
- unter Bash die tatsächliche Bytefolge oder eine direkte Hex-/Byteprüfung verwenden,
- keine Änderung an der produktiven ZIP-Nutzdateibehandlung.

### Tatsächlicher Rückbauumfang

Es wird kein Runtime-Netzwerkcode entfernt, weil keiner vorhanden ist.

Es wird kein automatischer Decoder entfernt, weil keiner vorhanden ist.

Dieser Commit entfernt ausschließlich:

- veraltete Zukunftslisten,
- alte Release-Audit-Annahmen,
- ein nicht mehr passendes Testhilfsmittel.

### Zieltests

```bash
timeout --foreground 600s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    tests/test_cli.py \
    tests/test_release_audit.py \
    tests/test_platform_e2e.py \
    tests/test_packaging_e2e.py
```

Danach vollständiger lokaler Testlauf über `./scripts/test.sh`.

### Commit-Gate

In den aktiven Bereichen dürfen keine veralteten Zukunftsvorbereitungen mehr vorkommen:

```bash
! rg -n -i \
  'websocket|clipboard|(^|[^a-z])ssh([^a-z]|$)|save mode|b64decode|base64' \
  src tests README.md pyproject.toml .github
```

Historische Dokumente und der Spezifikations-Changelog sind von diesem Suchgate bewusst ausgenommen.

---

## Commit 3 – Alten Skriptkommentar-Dateipfad funktional entfernen

**Commit-Message:**

```text
refactor: remove script-comment file transfer behavior
```

### Ziel

Ein Skript kann keine Nutzdateien mehr über spezielle Kommentarblöcke erzeugen. Echte Dateien werden ausschließlich durch ZIP-Nutzdateieinträge transportiert.

### Produktionscode

#### `src/patchharbor/parser.py`

Entfernen:

- `PayloadFile`,
- `ParsedScript.payload_files`,
- die gemeinsame MESSAGE/FILE-Blocksyntax,
- alle FILE-spezifischen Parserzweige,
- alle FILE-spezifischen Warnings und Fehlertexte.

Behalten:

- exakte Pflichtmarkerprüfung,
- META,
- MESSAGE,
- fail-soft Verhalten für beschädigte optionale MESSAGE-Inhalte.

Parserstruktur danach:

```text
Pflichtmarker
+ META
+ MESSAGE
+ Warnings
```

Andere Skriptkommentare besitzen keine besondere Dateisemantik.

#### `src/patchharbor/application.py`

Entfernen:

- Auslesen von `parsed_script.payload_files`,
- Vorbereitung der Textdateien,
- Schreiben dieser Textdateien vor Execution,
- FILE-spezifische Warnings,
- Übergabe dargestellter Inline-Dateien.

Behalten:

- Schreiben echter ZIP-Nutzdateien vor den ZIP-Skripten,
- Messages,
- Bundle-Warnings,
- Skriptreihenfolge,
- Stop beim ersten Skriptfehler,
- CWD, Timeout und Output.

Für den zunächst noch vorhandenen Präsentationsvertrag wird bis Commit 4 ausschließlich eine leere Dateizusatzmenge übergeben. Dadurch bleibt Commit 3 eigenständig grün, bevor die tote Schnittstelle im nächsten Commit entfernt wird.

### Verhaltenstests

#### `tests/test_parser.py`

Entfernen:

- alle Parserfälle für den alten Dateiblock,
- Import und Erwartungen für `PayloadFile`,
- beschädigte, doppelte oder unsichere alte Datei-Blöcke.

Behalten und gegebenenfalls schärfen:

- Pflichtmarker,
- META,
- mehrere MESSAGE-Blöcke,
- beschädigte MESSAGE-Blöcke,
- Warning-Deduplizierung.

#### `tests/test_cli_e2e.py`

Entfernen:

- Datei aus Kommentarblock vor Ausführung erstellen,
- bestehende Datei aus Kommentarblock überschreiben,
- mehrere Kommentar-Dateien,
- codierter Text im Kommentar-Dateipfad,
- beschädigter Datei-Block,
- unsicherer Inline-Dateiname,
- nicht reguläres Inline-Ziel.

ZIP-E2E-Tests bleiben vollständig erhalten.

#### `tests/test_platform_e2e.py`

Entfernen:

- plattformspezifischer Inline-Dateitest.

Behalten:

- plattformspezifischer binärer ZIP-Nutzdateitest,
- CWD,
- temporäre Skriptdatei,
- Timeout,
- Log,
- PowerShell 7.

#### `tests/test_acceptance_e2e.py`

Den ersten Akzeptanzfall umstellen:

- direkter Skriptlauf,
- MESSAGE,
- Plain-Ausgabe,
- vollständiges Log,
- kein Inline-Dateitransport.

Der vorhandene ZIP-Akzeptanzfall bleibt für Binärdatei und Skriptreihenfolge zuständig.

#### `tests/test_presentation.py`

Den Anwendungstest so umstellen, dass:

- Messages weiter an die Präsentation gehen,
- keine Inline-Dateien mehr erwartet werden,
- echte Bundle-Dateien weiterhin über `begin_request` dargestellt werden.

### Noch bewusst nicht in diesem Commit

Die nun unbenutzten Hilfsfunktionen in `payload_files.py` und der noch leere Parameter `inline_files` in der Präsentationsschnittstelle werden erst in Commit 4 entfernt. Das trennt die sichtbare Verhaltensänderung vom anschließenden strukturellen Cleanup.

### Zieltests

```bash
timeout --foreground 600s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    tests/test_parser.py \
    tests/test_cli_e2e.py \
    tests/test_platform_e2e.py \
    tests/test_acceptance_e2e.py \
    tests/test_presentation.py
```

Danach vollständiger lokaler Testlauf über `./scripts/test.sh`.

### Commit-Gate

- Direkte Skripte erzeugen keine Nutzdateien aus Kommentaren.
- ZIP-Nutzdateien funktionieren weiterhin.
- MESSAGE und META funktionieren weiterhin.
- Alle betroffenen Tests sind grün.

---

## Commit 4 – Toten Inline-Code entfernen und ZIP-Payload-Grenze vereinfachen

**Commit-Message:**

```text
refactor: reduce payload handling to ZIP bundle files
```

### Ziel

Nach der funktionalen Entfernung werden alle toten Hilfsfunktionen, Parameter, Abhängigkeiten und Tests des alten Pfads gelöscht. `payload_files.py` bleibt als kleine sichere Implementierung für echte ZIP-Nutzdateien bestehen.

### Produktionscode

#### `src/patchharbor/payload_files.py`

Entfernen:

- `_file_error`,
- `is_safe_payload_name`,
- `payload_size_warning`,
- `prepare_payload_files`,
- `write_payload_files`,
- alle FILE-spezifischen Docstrings, Labels und Fehlertexte,
- die danach unbenutzte `ResourcePolicy`-Abhängigkeit.

Behalten:

- Validierung sicherer ZIP-Pfade,
- Prüfung aller Ziele vor der ersten Ersetzung,
- sichere Elternverzeichnisse,
- Ablehnung nicht regulärer Ziele,
- atomischer Austausch,
- `write_bundle_payloads`,
- ZIP-spezifische Fehlertexte.

#### `src/patchharbor/application.py`

Entfernen:

- den danach unbenutzten `resource_policy`-Parameter aus `_execute_bundle_script`,
- nicht mehr benötigte Imports und Zwischenwerte.

Behalten:

- `resource_policy` auf der Artefakt-/ZIP-Auflösungsgrenze,
- `write_bundle_payloads`.

#### `src/patchharbor/presentation.py`

Entfernen:

- `inline_files` aus dem Präsentationsvertrag,
- Speicherung oder Zusammenführung von Inline-Dateien,
- FILE-spezifische Artbezeichnungen für den alten Pfad.

Behalten:

- `PresentedFile`,
- `bundle_files`,
- den sichtbaren TUI-Bereich `FILES`,
- Größenanzeige echter ZIP-Nutzdateien.

### Tests

#### `tests/test_files.py`

Entfernen:

- Tests ausschließlich für den alten Textdateipfad,
- dessen Namensfilter,
- dessen Größenwarnungen,
- dessen atomische Schreibhelfer,
- dessen FIFO-/Symlinkfälle,
- dessen Anwendungstest.

Behalten:

- bytegenaues Schreiben von ZIP-Nutzdateien,
- atomisches Ersetzen,
- Vorvalidierung sämtlicher Ziele,
- doppelte oder kollidierende Ziele,
- Symlink-Eltern und Symlink-Ziele,
- FIFO- und Sonderdateischutz für ZIP-Nutzdateien,
- Cleanup nach fehlgeschlagenem atomarem Austausch.

#### `tests/test_presentation.py` und `tests/test_cli.py`

- `inline_files` aus Test-Doubles und Aufrufen entfernen,
- `FILES`-Bereich weiterhin mit Bundle-Dateien testen.

#### `tests/test_architecture.py`

- die nicht mehr bestehende Ressourcenrichtlinien-Abhängigkeit von `payload_files.py` entfernen,
- die weiterhin gültige Plattform-Filesystem-Grenze prüfen,
- gerichtete und azyklische Abhängigkeiten weiter erzwingen.

### Zieltests

```bash
timeout --foreground 300s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    tests/test_files.py \
    tests/test_presentation.py \
    tests/test_cli.py \
    tests/test_architecture.py
```

Danach vollständiger lokaler Testlauf über `./scripts/test.sh`.

### Statisches Commit-Gate

In Runtime und Tests dürfen folgende alten Symbole nicht mehr vorkommen:

```bash
! rg -n \
  'PATCHHARBOR FILE|PayloadFile|payload_files[[:space:]]*:|prepare_payload_files|write_payload_files|inline_files' \
  src tests README.md pyproject.toml
```

Erlaubt und erforderlich bleiben:

```text
BundlePayload
write_bundle_payloads
PresentedFile
bundle_files
FILES
```

---

# Abschluss-Gate des Cleanup-Meilensteins

Für das Abschluss-Gate wird kein künstlicher leerer Commit erzeugt. Der letzte Codecommit darf erst erstellt werden, wenn alle folgenden Prüfungen erfolgreich sind.

## 1. Vollständige lokale Testsuite

```bash
PATCHHARBOR_TEST_TIMEOUT_SECONDS=120 \
PATCHHARBOR_TEST_SUITE_TIMEOUT_SECONDS=900 \
PATCHHARBOR_TEST_DURATIONS=10 \
./scripts/test.sh
```

## 2. Explizite Testgruppen

```bash
timeout --foreground 300s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    -m "not e2e and not acceptance and not platform and not packaging" \
    tests

timeout --foreground 600s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    -m "e2e or acceptance" \
    tests

timeout --foreground 600s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    -m "platform" \
    tests

timeout --foreground 900s \
  .venv/bin/python -m pytest -q \
    --timeout=120 \
    --durations=10 \
    -m "packaging" \
    tests
```

## 3. Docker-Release-Gates

```bash
./scripts/run_docker_integration_tests.sh 24.04
./scripts/run_docker_integration_tests.sh 26.04
```

Die Skripte besitzen eigene Build-, Run- und Test-Timeouts.

## 4. Echter Windows-Runner

Auf dem echten Windows-Release-Gate müssen grün sein:

- Core und Architektur,
- E2E und Acceptance,
- Plattformtests,
- Packaging,
- Windows PowerShell,
- PowerShell 7, sofern als verbindliche Lane aktiviert.

Ein lokaler Linux- oder Docker-Lauf ersetzt diesen Gate nicht.

## 5. Repository-Audit

```bash
git status --short
git diff --check
python -m compileall -q src tests
```

Aktive Runtime-, Test-, README-, Packaging- und Workflow-Dateien dürfen keine entfernten Zukunftsvorbereitungen mehr enthalten:

```bash
! rg -n -i \
  'websocket|clipboard|(^|[^a-z])ssh([^a-z]|$)|save mode|b64decode|base64' \
  src tests README.md pyproject.toml .github
```

Der alte Skriptkommentar-Dateipfad darf nicht mehr vorkommen:

```bash
! rg -n \
  'PATCHHARBOR FILE|PayloadFile|prepare_payload_files|write_payload_files|inline_files' \
  src tests README.md pyproject.toml
```

Bewusst ausgenommen sind:

- `planning/1.0.0/commit-plan.md`,
- `spec/SPECIFICATION_CHANGELOG.md`,
- dieser Cleanup-Plan.

Diese Dokumente beschreiben historische oder ausdrücklich entfernte Funktionen und dürfen die Begriffe zur Nachvollziehbarkeit nennen.

## 6. Abschlusszustand

Nach erfolgreichem Cleanup gilt:

```text
PatchHarbor 1.0.0 Runner-Basis
+ echte ZIP-Nutzdateien
+ META und MESSAGE
+ Plattform-, Prozess-, TUI-, Logging- und Release-Verträge
- alter Inline-Dateipfad
- veraltete Transport-Zukunftsvorbereitungen
= saubere Ausgangsbasis für die Implementierung von 1.1.0
```

---

## 6. Nach diesem Plan

Erst nach vollständig grünem Cleanup beginnt ein separater Implementierungsplan für:

1. Repository-Registry mit UUID und atomarer Persistenz,
2. kanonischen Kontext,
3. Fingerprint `patchharbor-state-v1`,
4. geschlossenes `patch.json`,
5. sicheren `apply`-Pfad,
6. Repository-Lock,
7. zweite Zustandsprüfung vor dem ersten Schreibzugriff,
8. Dry-Run,
9. strukturierten Run-Bericht und Fehlerpriorität,
10. vollständiges Result Bundle,
11. separaten PatchHarbor Watcher,
12. Integrationsgrenzen zu Repo Assist und PromptBridge.

Diese neuen Funktionen werden nicht mit dem Rückbau vermischt.
