# PatchHarbor – Spezifikation

**Dateiname:** `SPECIFICATION.md`<br>
**Produktversion:** `1.1.0`<br>
**Spezifikationsstand:** 2026-08-04<br>
**Status:** Verbindliches, implementierungsreifes Zielbild für PatchHarbor 1.1.0<br>
**Projektname:** `PatchHarbor`<br>
**Kommando:** `patchharbor`<br>
**Skriptmarker:** `# PATCHHARBOR`<br>
**Patch-Paketmarker:** `patch-harbor`

Der Umsetzungs- und Commit-Plan ist von dieser Produktspezifikation getrennt und liegt unter `planning/1.1.0/commit-plan-cleanup.md`. Änderungen am Produktziel werden in `spec/SPECIFICATION_CHANGELOG.md` dokumentiert.

---

## 1. Zweck, Gültigkeit und Verhältnis zu 1.0.0

Dieses Dokument beschreibt das vollständige verbindliche Produktziel von PatchHarbor 1.1.0.

Es übernimmt die weiterhin gültigen Produktverträge aus 1.0.0 vollständig und ergänzt sie um:

- die Registrierung konkreter lokaler Git-Repository-Instanzen,
- eine eindeutige Repository-ID,
- einen reproduzierbaren Repository-Kontext,
- einen kanonischen Zustands-Fingerprint,
- ein selbstbeschreibendes sicheres ZIP-Patch-Paket,
- strikte Repository- und Zustandsprüfung,
- einen Dry-Run,
- eine exklusive Repository-Sperre,
- ein vollständiges Result Bundle mit Repository-Snapshot und Ausführungsprotokoll,
- einen separaten PatchHarbor Watcher,
- klar getrennte Verantwortlichkeiten gegenüber Repo Assist und PromptBridge.

Diese Datei ersetzt die frühere kombinierte Spezifikation mit Commit-Plan als Produktspezifikation. Der historische 1.0.0-Commit-Plan bleibt unter `planning/1.0.0/commit-plan.md` erhalten, ist aber kein normativer Teil dieses Dokuments.

Bei einem Widerspruch zwischen diesem Dokument und einer älteren Produktspezifikation gilt dieses Dokument.

---

## 2. Produktzweck und Sicherheitsgrenze

PatchHarbor ist ein kontrollierter, plattformübergreifender Runner für von einem Chatbot erzeugte Skripte und ZIP-Patch-Pakete.

PatchHarbor unterstützt zwei öffentliche Ausführungswege:

1. den fortgeführten expliziten manuellen Runner `patchharbor fs run`,
2. den neuen sicheren Mehr-Repository-Pfad `patchharbor apply`.

Der sichere Mehr-Repository-Pfad ordnet ein Patch-Paket genau einer registrierten lokalen Repository-Instanz in genau einem erwarteten Zustand zu:

```text
Patch-Paket
    +
Repository-ID
    +
Base-Commit
    +
Zustands-Fingerprint
    =
genau eine lokale Repository-Instanz in genau einem erwarteten Zustand
```

PatchHarbor führt einen validierten Entrypoint aus, erfasst das Ergebnis und erzeugt einen vollständigen Snapshot des aktuellen Repository-Zustands ohne Git-Historie.

PatchHarbor ist kein Testmanager, kein Commit-Manager, kein Build-System, kein Chat-Transport und kein allgemeiner Workflow-Orchestrator.

### 2.1 PatchHarbor Core macht

- direkte Skripte und ZIP-Container kontrolliert verarbeiten,
- konkrete lokale Git-Repository-Instanzen registrieren,
- pro lokaler Instanz eine UUID v4 verwalten,
- Repository-Kontext und Zustands-Fingerprint bestimmen,
- sichere Patch-Pakete anhand einer verpflichtenden `patch.json` validieren,
- ein Patch-Paket eindeutig einem registrierten Ziel-Repository zuordnen,
- Base-Commit und Zustands-Fingerprint strikt prüfen,
- einen Dry-Run ohne Repository-Änderung durchführen,
- einen Entrypoint mit geprüfter Interpreterzuordnung ausführen,
- sichere reguläre ZIP-Nutzdateien bytegenau bereitstellen,
- Timeout, Abbruch und vollständigen Prozessbaum kontrollieren,
- stdout und stderr vollständig erfassen,
- Exit-Code, Laufzeit, Warnings und Tool-Fehler dokumentieren,
- ein vollständiges PatchHarbor Result Bundle erzeugen,
- einen maschinenlesbaren Ergebnisvertrag für Watcher und Repo Assist anbieten.

### 2.2 PatchHarbor Core macht ausdrücklich nicht

- keinen Ordner dauerhaft überwachen,
- keinen systemd-Dienst enthalten,
- keinen eigenen Managed- oder Standalone-Modus besitzen,
- keine Netzwerk- oder Chatverbindung betreiben,
- keine Dateien selbst zu einem Chat hochladen oder von ihm abrufen,
- keine Tests des Zielprojekts als fachlichen Workflow verwalten oder bewerten,
- keine Git-Commits, Branches, Tags oder Releases erzeugen,
- keine Builds oder Linter als eigene Produktfunktion verwalten,
- keine Patches inhaltlich bewerten,
- keine interaktiven Kindskripte unterstützen,
- keine öffentliche Plugin-Schnittstelle anbieten,
- keine Clipboard- oder SSH-Quelle anbieten,
- keine Dateien aus kommentierten Skriptabschnitten erzeugen,
- keine textuelle Binärkodierung automatisch erkennen oder dekodieren,
- keine rekursive Ordnersuche durchführen,
- keine enthaltenen Archive rekursiv als weitere Patch-Pakete öffnen,
- keine vollständige Pakettransaktion oder automatische globale Rückabwicklung versprechen,
- keine dauerhafte zentrale Loghistorie oder Logrotation verwalten,
- keine beliebigen Diagnose-, Test- oder Build-Artefakte automatisch einsammeln.

### 2.3 Keine Sandbox

PatchHarbor ist keine Sandbox. Ein ausgeführter Entrypoint besitzt grundsätzlich die Rechte des PatchHarbor-Benutzers. Repository-ID, Base-Commit und Fingerprint sichern Zuordnung und Zustand, authentifizieren aber nicht den Absender des Pakets. Nur vertrauenswürdige Patch-Pakete dürfen ausgeführt werden.

Die Pfadprüfung von ZIP-Nutzdateien schützt vor unbeabsichtigtem oder manipuliertem Entpacken außerhalb der erlaubten Ziele. Sie kann nicht verhindern, dass ein vertrauenswürdig gestartetes Skript mit den Rechten des Benutzers selbst beliebige erreichbare Dateien oder Programme verwendet.

---

## 3. Komponenten und Verantwortungsgrenzen

### 3.1 PatchHarbor Core

PatchHarbor Core ist ein normales CLI-Werkzeug und eine wiederverwendbare Runner-Engine. Jeder Aufruf verarbeitet genau einen klar abgegrenzten Auftrag und endet anschließend.

PatchHarbor Core besitzt keinen Hintergrundloop und keine Netzwerkverbindung.

### 3.2 PatchHarbor Watcher

Der PatchHarbor Watcher ist eine separate dünne Komponente im PatchHarbor-Projekt.

Er kann unter Linux als systemd-Service betrieben werden und:

- einen konfigurierten Download- oder Eingangsordner überwachen,
- vollständig abgeschlossene Downloads erkennen,
- offensichtliche temporäre Browserdateien ignorieren,
- eine gefundene Datei an `patchharbor apply` übergeben,
- Rückgabecode und strukturiertes Ergebnis protokollieren,
- die ungeplante erneute Verarbeitung derselben unveränderten Datei verhindern.

Der Watcher implementiert keine eigene Repository-, Git-, Manifest-, Fingerprint-, Lock-, Ausführungs- oder Result-Bundle-Logik. Er darf Prüfungen des Core weder nachbauen noch umgehen.

Der Watcher scannt den Eingangsordner nicht rekursiv.

Der physisch kanonisierte Eingangsordner muss außerhalb aller registrierten Repository-Instanzen liegen. Er darf weder mit einer Repository-Wurzel identisch sein noch innerhalb einer registrierten Repository-Instanz liegen. Eingangsordner und Result-Ordner dürfen sich außerdem in keiner Richtung überlappen. Eine Watcher-Konfiguration oder spätere Repository-Registrierung, die diese Grenzen verletzen würde, wird abgelehnt.

### 3.3 Repo Assist

Repo Assist ist ein optionaler übergeordneter Workflow-Orchestrator.

Repo Assist kann:

- PatchHarbor Core aufrufen,
- PatchHarbor Result Bundles anfordern,
- Aufgaben und Workflow-Zustände verwalten,
- Tests mit Timeouts ausführen,
- Testresultate bewerten,
- nur bei erfolgreichem Workflow Commits erzeugen,
- Retry, Abort und Journal verwalten,
- eigene Repo-Assist-Journal-Bundles erzeugen.

Repo Assist erzeugt den technischen PatchHarbor-Repository-Snapshot nicht selbst. Benötigt Repo Assist den vollständigen Repository-Zustand, ruft es PatchHarbor auf.

PatchHarbor ruft Repo Assist nicht auf. Ein Patch darf Repo Assist nicht als versteckten inneren Workflow starten.

### 3.4 PromptBridge

PromptBridge besitzt die Chat- und Transportverantwortung.

Dazu können gehören:

- Chat-Interaktion,
- Netzwerktransport,
- Upload und Download,
- Übertragung von Nachrichten, Variablen und Dateien,
- spätere Automatisierung des Austauschs zwischen Chat und lokaler Umgebung.

PromptBridge ist kein internes PatchHarbor-Modul.

### 3.5 Keine konkurrierenden Orchestratoren

Für dieselben registrierten Repository-Instanzen gilt:

- Entweder verarbeitet der PatchHarbor Watcher neue Downloads autonom über PatchHarbor Core,
- oder Repo Assist ist der aktive Orchestrator.

Wenn Repo Assist aktiv ist, darf für dieselben Repository-Instanzen kein autonomer PatchHarbor Watcher aktiv sein.

Unabhängig von dieser Betriebsregel erzwingt PatchHarbor Core pro Repository eine technische exklusive Sperre. Dadurch können zwei PatchHarbor-Aufträge dieselbe lokale Instanz nicht gleichzeitig bearbeiten.

---

## 4. Installation, Plattformen und lokale Verzeichnisse

### 4.1 Installation

PatchHarbor wird für den Benutzer über pipx installiert:

```bash
pipx install patchharbor
```

Wheel und Source-Distribution werden aus derselben Version und denselben Release-Metadaten gebaut.

Der Konsolenbefehl lautet:

```bash
patchharbor
```

`patchharbor --version` zeigt die installierte Release-Version.

### 4.2 Python und Zielplattformen

PatchHarbor 1.1.0 verwendet die vorhandene 1.0.0-Basis und benötigt Python 3.12 oder neuer.

Verbindliche Zielplattformen:

- Linux,
- Windows 11.

Verbindliche CI-Plattformen:

- Ubuntu 24.04,
- Ubuntu 26.04,
- ein echter GitHub-gehosteter Windows-Runner mit Windows PowerShell,
- zusätzlich PowerShell 7, soweit auf dem Runner vorhanden.

Ubuntu 24.04, Ubuntu 26.04 und der echte Windows-Runner sind normale blockierende Release-Gates. Eine Release-Freigabe ist nur zulässig, wenn alle verbindlichen Lanes grün sind. PowerShell 7 ist zusätzlich blockierend, sobald die entsprechende Lane im Release-Workflow aktiviert ist.

### 4.3 Benutzerspezifische Verzeichnisse

Unter Linux gelten standardmäßig:

```text
Konfiguration: ${XDG_CONFIG_HOME:-$HOME/.config}/patchharbor/
Zustand:       ${XDG_STATE_HOME:-$HOME/.local/state}/patchharbor/
Resultate:     ${XDG_STATE_HOME:-$HOME/.local/state}/patchharbor/results/
Locks:         ${XDG_STATE_HOME:-$HOME/.local/state}/patchharbor/locks/
```

Unter Windows gelten standardmäßig:

```text
Konfiguration: %APPDATA%\PatchHarbor\
Zustand:       %LOCALAPPDATA%\PatchHarbor\
Resultate:     %LOCALAPPDATA%\PatchHarbor\results\
Locks:         %LOCALAPPDATA%\PatchHarbor\locks\
```

Alle konfigurierten Pfade werden vor ihrer Verwendung physisch kanonisiert. Symbolische Verknüpfungen und Junctions werden bei der Grenzprüfung auf ihr tatsächliches Ziel aufgelöst.

Für jeden Result-Ordner gelten verbindlich:

- Er darf nicht identisch mit einem registrierten Repository-Wurzelpfad sein.
- Er darf nicht innerhalb irgendeiner registrierten Repository-Instanz liegen.
- Er darf keinen konfigurierten Watcher-Eingangsordner enthalten.
- Er darf nicht identisch mit einem Watcher-Eingangsordner sein und nicht innerhalb eines solchen Eingangsordners liegen.
- Er muss vor der ersten Repository-Änderung sicher angelegt und auf Schreibbarkeit geprüft werden.
- Die temporäre ZIP-Datei eines Result Bundles wird direkt in diesem endgültigen Result-Ordner erzeugt, damit die spätere Veröffentlichung über einen dateisystemgleichen atomaren Austausch möglich ist.

Für jeden Watcher-Eingangsordner gelten verbindlich:

- Er darf nicht identisch mit einem registrierten Repository-Wurzelpfad sein.
- Er darf nicht innerhalb irgendeiner registrierten Repository-Instanz liegen.
- Er darf keinen konfigurierten Result-Ordner enthalten.
- Er darf nicht identisch mit einem Result-Ordner sein und nicht innerhalb eines Result-Ordners liegen.

Liegt ein expliziter `--output-dir` oder ein konfigurierter Watcher-Eingangsordner nach physischer Auflösung in einem verbotenen Bereich, wird die Konfiguration beziehungsweise der Auftrag abgelehnt. Wird später ein Repository registriert, dessen Wurzel einen bereits konfigurierten Watcher-Eingangsordner oder Result-Ordner enthalten würde, wird auch diese Registrierung abgelehnt.

Der Watcher darf Result Bundles niemals erneut als Eingabepakete behandeln.

### 4.4 Dokumentation

- Die Installationsanleitung steht kurz im README.
- Die vollständige Bedienungsdokumentation steht in den argparse-Help-Screens.
- Die Produktspezifikation beschreibt verbindliches Verhalten, nicht die tägliche Kurzanleitung.
- Nicht implementierte Funktionen werden nicht im Help-Screen angeboten.

---

## 5. Öffentliche CLI

### 5.1 Sicherer Mehr-Repository-Pfad

```bash
patchharbor register [REPOSITORY]
patchharbor register --new-id [REPOSITORY]
patchharbor registry list
patchharbor unregister [REPOSITORY_OR_REPO_ID]
patchharbor context [REPOSITORY]
patchharbor bundle [REPOSITORY]
patchharbor apply PATCH_ZIP
patchharbor apply --dry-run PATCH_ZIP
```

Die Optionen sind pro Befehl verbindlich begrenzt:

| Befehl | Unterstützte zusätzliche Optionen |
|---|---|
| `patchharbor register` | `--new-id` |
| `patchharbor registry list` | `--json` |
| `patchharbor unregister` | keine fachliche Zusatzoption |
| `patchharbor context` | `--json` |
| `patchharbor bundle` | `--json`, `--output-dir VERZEICHNIS` |
| `patchharbor apply` | `--dry-run`, `--timeout SEKUNDEN`, `--plain`, `--no-color`, `--json`, `--output-dir VERZEICHNIS` |

Für `patchharbor apply` beträgt der Standard-Timeout 300 Sekunden.

`--json` und eine interaktive Terminaldarstellung schließen sich aus. Im JSON-Modus werden weder TUI-Sequenzen noch Farbcodes auf stdout ausgegeben. Nicht für einen Befehl aufgeführte Optionen werden von argparse abgelehnt.

Alle Befehle unterstützen die üblichen argparse-Hilfen wie `--help`.

### 5.2 Gemeinsamer JSON-Ausgabevertrag

Die Befehle `registry list --json`, `context --json`, `bundle --json` und `apply --json` verwenden einen gemeinsamen versionierten Abschlussvertrag.

Nach erfolgreicher CLI-Argumentanalyse gilt:

- stdout enthält genau ein UTF-8-JSON-Objekt und einen abschließenden LF-Zeilenumbruch,
- stdout enthält weder TUI-Sequenzen noch Farbcodes noch rohen Kindprozessoutput,
- menschliche Zusatz- oder Notfallmeldungen erscheinen ausschließlich auf stderr,
- alle UUIDs werden in kanonischer kleingeschriebener Schreibweise ausgegeben,
- alle Objekt-IDs und Fingerprints werden kleingeschrieben ausgegeben,
- Zeitstempel sind UTC-Zeitstempel nach RFC 3339 mit `Z`,
- Pfade sind physisch kanonisierte absolute Pfadstrings,
- nicht endliche Zahlenwerte kommen nicht vor,
- JSON-Ausgabeformat 1 enthält nur die nachfolgend festgelegten Felder; Erweiterungen erfordern eine höhere `output_version`.

Jedes Abschlussobjekt besitzt exakt diese Top-Level-Felder:

| Feld | Typ | Bedeutung |
|---|---|---|
| `output_version` | Integer | Exakt `1`. |
| `command` | String | `registry.list`, `context`, `bundle` oder `apply`. |
| `success` | Boolean | `true` genau dann, wenn der Prozess-Exit-Code `0` ist. |
| `result` | Objekt oder `null` | Befehlsspezifisches Ergebnis, soweit vorhanden. |
| `error` | Objekt oder `null` | Strukturierter PatchHarbor-Tool-Fehler, soweit vorhanden. |
| `process_exit_code` | Integer | Tatsächlich zurückgegebener Prozess-Exit-Code. |

Ein nicht-null `error`-Objekt besitzt exakt:

| Feld | Typ | Bedeutung |
|---|---|---|
| `kind` | String | Stabile Fehlerkategorie aus dem jeweiligen Befehl. |
| `message` | String | Menschenlesbare, nicht geheime Kurzbeschreibung. |
| `patchharbor_error_code` | Integer | Zugehöriger PatchHarbor-Tool-Exit-Code. |
| `emergency_diagnostics_path` | String oder `null` | Physisch kanonischer Notfallpfad, falls vorhanden. |

Ein normal beendeter Entrypoint mit einem von null verschiedenen Exit-Code ist kein PatchHarbor-Tool-Fehler. In diesem Fall ist `success` gleich `false`, `error` bleibt `null`, und das Resultat beschreibt den Entrypoint-Exit eindeutig.

#### `patchharbor registry list --json`

Das `result`-Objekt besitzt exakt ein Feld `repositories`. Die Einträge sind nach den ASCII-Bytes der `repo_id` sortiert und besitzen exakt `repo_id`, `repository_path` und `status`. Zulässige Statuswerte sind `ok`, `missing` und `conflict`.

```json
{
  "output_version": 1,
  "command": "registry.list",
  "success": true,
  "result": {
    "repositories": [
      {
        "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
        "repository_path": "/home/user/src/patchharbor",
        "status": "ok"
      }
    ]
  },
  "error": null,
  "process_exit_code": 0
}
```

#### `patchharbor context --json`

Das erfolgreiche `result`-Objekt besitzt exakt:

- `repo_id`,
- `repository_path`,
- `base_commit`,
- `dirty`,
- `state_fingerprint`,
- `fingerprint_algorithm`.

```json
{
  "output_version": 1,
  "command": "context",
  "success": true,
  "result": {
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "repository_path": "/home/user/src/patchharbor",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "dirty": true,
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": "patchharbor-state-v1"
  },
  "error": null,
  "process_exit_code": 0
}
```

#### `patchharbor bundle --json`

Das erfolgreiche `result`-Objekt besitzt exakt:

- `run_id`,
- `repo_id`,
- `repository_path`,
- `base_commit`,
- `state_fingerprint`,
- `fingerprint_algorithm`,
- `result_bundle_status`,
- `result_bundle_path`,
- `emergency_diagnostics_path`.

`result_bundle_status` ist bei einem erfolgreichen manuellen Bundle exakt `created`; `emergency_diagnostics_path` ist dann `null`.

```json
{
  "output_version": 1,
  "command": "bundle",
  "success": true,
  "result": {
    "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "repository_path": "/home/user/src/patchharbor",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": "patchharbor-state-v1",
    "result_bundle_status": "created",
    "result_bundle_path": "/home/user/.local/state/patchharbor/results/patchharbor_result_20260804_093000_b592be12.zip",
    "emergency_diagnostics_path": null
  },
  "error": null,
  "process_exit_code": 0
}
```

#### `patchharbor apply --json`

Das erfolgreiche oder fachlich fehlgeschlagene `result`-Objekt besitzt exakt:

- `run_id`,
- `repository_resolved`,
- `repo_id`,
- `repository_path`,
- `primary_result`,
- `result_bundle`.

`repo_id` und `repository_path` sind `null`, solange kein Repository sicher aufgelöst wurde.

`primary_result` besitzt exakt:

- `kind`,
- `entrypoint_started`,
- `entrypoint_exit_code`,
- `timed_out`,
- `interrupted`,
- `patchharbor_error_code`.

`result_bundle` besitzt exakt:

- `attempted`,
- `status`,
- `path`,
- `emergency_diagnostics_path`.

Zulässige Bundle-Statuswerte sind `created`, `failed` und `not_attempted`. `not_attempted` ist nur zulässig, wenn `repository_resolved` gleich `false` ist.

```json
{
  "output_version": 1,
  "command": "apply",
  "success": false,
  "result": {
    "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
    "repository_resolved": true,
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "repository_path": "/home/user/src/patchharbor",
    "primary_result": {
      "kind": "entrypoint_exit",
      "entrypoint_started": true,
      "entrypoint_exit_code": 7,
      "timed_out": false,
      "interrupted": false,
      "patchharbor_error_code": null
    },
    "result_bundle": {
      "attempted": true,
      "status": "created",
      "path": "/home/user/.local/state/patchharbor/results/patchharbor_result_20260804_093000_b592be12.zip",
      "emergency_diagnostics_path": null
    }
  },
  "error": null,
  "process_exit_code": 7
}
```

### 5.3 Fortgeführter manueller Runner

Der vorhandene öffentliche Hauptaufruf bleibt:

```bash
patchharbor fs run [PFAD]
```

Unterstützte Optionen:

- `--timeout SEKUNDEN` mit Standardwert 300,
- `--log` für eine vollständige temporäre Logdatei,
- `--plain` für einfache fortlaufende Textausgabe,
- `--no-color`,
- die üblichen argparse-Hilfen.

`patchharbor fs run` ist ein expliziter lokaler Runner. Er besitzt keine automatische Repository-Zuordnung und prüft weder Repository-ID noch Base-Commit oder Fingerprint.

## 6. Gemeinsamer Runner-Lebenszyklus

Ein Runner-Auftrag verarbeitet genau ein Eingabeartefakt oder ein sicheres Patch-Paket und endet anschließend.

Der allgemeine Lebenszyklus lautet:

```text
Start
→ Eingabe übernehmen
→ vollständige Struktur und Ressourcen prüfen
→ ausführbare Einträge vorbereiten und Pflichtmarker prüfen
→ angeforderte Interpreter bestimmen und ihre Verfügbarkeit prüfen
→ Nutzdateien vollständig vorbereiten und sicher schreiben
→ Kindprozess nicht interaktiv ausführen
→ Output und Ergebnis erfassen
→ gegebenenfalls Result Bundle erzeugen
→ temporäre Ressourcen über einen gemeinsamen Cleanup-Pfad entfernen
→ Auftrag beenden
```

Beim sicheren Apply werden sämtliche rein lesenden Prüfungen einschließlich Entrypoint-, Marker-, Interpreter- und Result-Zielprüfung vor der ersten Änderung einer Repository-Datei abgeschlossen.

Kein Skript startet, bevor das zugehörige Eingabepaket vollständig validiert wurde und alle vorab bereitzustellenden Nutzdateien erfolgreich geschrieben wurden.

### 6.1 Arbeitsverzeichnis

Beim manuellen Runner läuft jedes Skript im ursprünglichen aktuellen Arbeitsverzeichnis des Aufrufs.

Beim sicheren Apply läuft der Entrypoint im Wurzelverzeichnis des anhand der Repository-ID aufgelösten Ziel-Repositorys.

Der Speicherort der Eingabedatei, des ZIP-Pakets oder der temporären Entrypoint-Datei ändert das Arbeitsverzeichnis nicht.

Relative Pfade im Skript beziehen sich immer auf dieses Arbeitsverzeichnis.

### 6.2 Temporäre Eingabe- und Skriptdateien

Direkte Skriptinhalte, aus STDIN erzeugte Eingabeartefakte und ausführbare ZIP-Einträge werden bei Bedarf in einem privaten System-Temp-Verzeichnis bereitgestellt.

Eine temporäre Datei:

- wird nicht als Nutzdatei in das Zielverzeichnis kopiert,
- erhält nur die für ihren Zweck notwendigen Benutzerrechte,
- wird nach Erfolg, Fehler, Timeout oder Strg+C über genau einen gemeinsamen Cleanup-Pfad entfernt,
- darf vom Skript nicht als dauerhaft im Projekt vorhandene Datei vorausgesetzt werden.

Nur wenn die in Abschnitt 18 definierte Notfallrettung benötigt wird, dürfen `execution.log` und `run.json` nach einem Bundle-Fehler im ausdrücklich gemeldeten Notfallverzeichnis verbleiben.

## 7. Manueller Runner: Quellen und Eingabeartefakte

### 7.1 Quellengrenze

Eine Quelle ist ausschließlich dafür verantwortlich, Daten zu empfangen und als neutrales `InputArtifact` bereitzustellen.

Ein `InputArtifact` enthält nur:

- einen sicher lesbaren lokalen Pfad,
- einen Anzeigenamen für Status und Fehler.

Die Quelle interpretiert den Inhalt nicht. Sie kennt weder Skriptmarker noch ZIP-Regeln, Nutzdateien, Interpreter oder Execution.

### 7.2 Einzelne Datei

Eine einzelne reguläre Datei wird als Eingabeartefakt übernommen.

Dateiname und Dateiendung sind für die Skript- und ZIP-Erkennung unerheblich.

Symbolische Links werden als direkte Eingabe nicht stillschweigend dereferenziert. Kann eine Datei nicht sicher als reguläre Datei geöffnet werden, endet der Auftrag mit einem Tool-Fehler.

### 7.3 Einmaliger Ordnerscan

Ein an `patchharbor fs run` übergebener Ordner wird genau einmal gescannt. Er wird nicht überwacht.

Regeln:

- nicht rekursiv,
- nur reguläre Dateien,
- symbolische Links werden ignoriert,
- ein Kandidat ist eine Datei, deren Auflösung mindestens ein gültiges PatchHarbor-Skript liefert,
- Sortierung nach Änderungszeit, neueste zuerst,
- bei gleicher Änderungszeit Dateiname als stabiler zweiter Sortierschlüssel,
- Auswahl mit einer ab eins gezählten Zahl aus ASCII-Ziffern,
- bei genau einem Kandidaten automatische Auswahl,
- bei mehreren Kandidaten muss der Benutzer genau einen Eintrag wählen,
- leere Eingabe bricht ohne automatische Auswahl ab,
- ungültige Eingabe wird erneut abgefragt, solange die Eingabe interaktiv möglich ist.

### 7.4 STDIN und Pipe

Ist kein Pfad angegeben und STDIN eine Pipe, wird der vollständige Byte-Strom einmalig und unter Einhaltung des Eingabebudgets in ein sicheres temporäres Eingabeartefakt geschrieben.

STDIN kann übertragen:

- ein direktes UTF-8-Skript,
- ein binäres ZIP-PatchBundle.

Es gibt keinen Streaming-Befehlsdialog und kein interaktives Protokoll.

Ist kein Pfad angegeben und STDIN ein normales Terminal, endet PatchHarbor mit einem klaren Usage-Fehler wegen fehlender Eingabe.

Das aus STDIN erzeugte temporäre Eingabeartefakt unterliegt demselben zentralen Cleanup-Vertrag wie temporäre Skriptdateien und wird bei Erfolg, Fehler, Timeout und Strg+C entfernt.

Die Standardeingabe des ausgeführten Kindprozesses ist geschlossen.

## 8. Skripterkennung, Metadaten und Messages

### 8.1 Pflichtmarker

Ein Skript ist nur gültig, wenn es mindestens eine vollständige Zeile enthält, die exakt lautet:

```text
# PATCHHARBOR
```

Regeln:

- Die Zeile beginnt am ersten Zeichen der Zeile.
- Es gibt keine führenden Leerzeichen.
- Groß- und Kleinschreibung sind fest.
- Die Zeile enthält keinen Zusatz und keine Version.
- Eine META- oder MESSAGE-Zeile ersetzt den Pflichtmarker nicht.
- Zeilenenden von Linux und Windows werden beim Prüfen normalisiert.

Fehlt der Pflichtmarker, wird das Skript nicht ausgeführt.

### 8.2 Optionale Metadaten

Kleine Informationen können als optionale META-Zeilen übertragen werden:

```text
# PATCHHARBOR META name=wert
```

Metadaten sind rein informativ. Sie verändern weder Timeout noch Interpreter, Umgebungsvariablen, Repository-Zuordnung, Fingerprint oder anderes Ausführungsverhalten.

Fehlerhafte META-Zeilen führen höchstens zu einer Warning und werden ansonsten ignoriert.

### 8.3 Optionale Messages

Es dürfen mehrere benannte Message-Blöcke enthalten sein.

Ein Message-Name besteht aus Großbuchstaben, Kleinbuchstaben, Zahlen und Punkten und enthält keine Leerzeichen.

Anfang und Ende eines Blocks enthalten denselben Namen. Der Text dazwischen besteht aus kommentierten UTF-8-Zeilen. Beim Lesen wird das definierte Kommentarpräfix entfernt.

Messages sind ausschließlich Informationen für Menschen oder äußere Orchestratoren. Sie steuern PatchHarbor nicht.

Ein unvollständiger, falsch benannter oder beschädigter Message-Block wird vollständig verworfen. PatchHarbor zeigt eine Warning und führt ein ansonsten gültiges Skript trotzdem aus.

---

## 9. Manueller Runner: PatchBundle-Auflösung

### 9.1 Begriff

Jedes Eingabeartefakt des manuellen Runners wird genau einmal zu einem `PatchBundle` aufgelöst.

Ein PatchBundle enthält:

- mindestens ein PatchHarbor-Skript in definierter Reihenfolge,
- null oder mehr geordnete reguläre Nutzdateien mit relativem Zielpfad und bytegenauem Inhalt.

Ein einzelnes direktes Skript ist fachlich ein PatchBundle mit genau einem Skript und ohne Nutzdateien.

### 9.2 Auflösungsreihenfolge

- Ein vollständig als UTF-8 lesbares direktes Skript mit exaktem Pflichtmarker ergibt ein PatchBundle mit genau einem Skript.
- Ist das Artefakt kein gültiges direktes Skript, wird es als ZIP-basiertes PatchBundle geprüft.
- Ist es weder ein gültiges direktes Skript noch ein gültiges ZIP-Bundle mit mindestens einem PatchHarbor-Skript, endet der Auftrag mit einem klaren Tool-Fehler.
- Quelle, Dateiname und Dateiendung bestimmen weder Skripttyp noch Bundletyp.

### 9.3 ZIP-PatchBundle

ZIP ist die Codierung für mehrere geordnete Skripte und zusätzliche Text- oder Binärdateien. Es ist kein eigener Ausführungsmodus.

Regeln:

- Das Archiv wird vor der ersten Dateischreibung vollständig auf Struktur, Eintragstypen, Zielpfade, Duplikate, Lesbarkeit und Ressourcenbudgets geprüft.
- Verzeichniseinträge beschreiben nur die sichere relative Zielstruktur.
- Symbolische Links, Hardlinks und andere besondere oder mehrdeutige Einträge machen das gesamte Bundle ungültig.
- Jeder reguläre Dateieintrag wird in Archiv-Reihenfolge klassifiziert.
- Ist ein Eintrag vollständig als UTF-8 lesbar und enthält er den exakten Pflichtmarker, ist er ein ausführbares PatchHarbor-Skript.
- Jeder andere sichere reguläre Eintrag ist eine Nutzdatei und wird bytegenau übertragen. Das gilt auch für markerlose Shell- oder PowerShell-Dateien.
- Binärdateien werden niemals als Text verändert und niemals automatisch ausgeführt.
- Ein enthaltenes Archiv ohne PatchHarbor-Marker wird nicht rekursiv geöffnet, sondern wie jede andere Binärdatei als Nutzdatei behandelt.
- Skripteinträge werden in der im Archiv gespeicherten Reihenfolge ausgeführt.
- Alle Nutzdateien werden vollständig vorbereitet und vor dem ersten Skript bereitgestellt.
- Jedes Skript erhält sein eigenes Timeout.
- Beim ersten nicht erfolgreichen Skript wird abgebrochen.
- Der Exit-Code des zuletzt ausgeführten Skripts wird zurückgegeben.
- Enthält das Archiv kein gültiges PatchHarbor-Skript, endet PatchHarbor mit einem Tool-Fehler.
- Das Archiv wird möglichst streamend verarbeitet und nicht pauschal vollständig in das Arbeitsverzeichnis entpackt.

---

## 10. Sichere ZIP-Nutzdateien

Die Regeln dieses Abschnitts gelten sowohl für den manuellen ZIP-PatchBundle-Pfad als auch für sichere `patchharbor apply`-Pakete.

### 10.1 Erlaubte relative Pfade

Für jeden Nutzdateipfad gelten:

- ausschließlich relative Pfade mit dem ZIP-Trennzeichen `/`,
- keine absoluten Pfade,
- keine Laufwerks- oder UNC-Angaben,
- keine Backslashes,
- kein leeres Segment,
- kein `.`- oder `..`-Segment,
- jedes Segment besteht ausschließlich aus ASCII-Buchstaben, Ziffern, Punkt, Unterstrich und Bindestrich,
- jedes Segment ist höchstens 128 Zeichen lang,
- der vollständige relative Pfad ist höchstens 512 Zeichen lang,
- kein Segment endet mit Punkt oder Leerzeichen,
- kein Segment ist ein reservierter Windows-Gerätename wie `CON`, `PRN`, `AUX`, `NUL`, `COM1` bis `COM9` oder `LPT1` bis `LPT9`, auch nicht mit Dateiendung,
- symbolische Links, Hardlinks, Geräte, FIFOs, Sockets und andere besondere Archivtypen sind unzulässig,
- vorhandene symbolische Links oder andere nicht reguläre Ziel- oder Elternpfade werden nicht überschrieben,
- doppelte normalisierte Zielpfade werden abgelehnt,
- Groß-/Kleinschreibungs-Kollisionen werden plattformübergreifend als mehrdeutig abgelehnt.

### 10.2 Verbotene interne Pfade

Kein Paket darf einen Pfad enthalten, bei dem irgendein normalisiertes Segment ohne Beachtung der Groß-/Kleinschreibung exakt einem der folgenden Namen entspricht:

```text
.git
.patchharbor
```

Das Verbot gilt für:

- reguläre Nutzdateien,
- Verzeichniseinträge,
- den Entrypoint-Pfad,
- alle Elternsegmente eines Eintrags.

Dadurch kann ein ZIP-Paket weder Git-Metadaten noch die lokale PatchHarbor-Identität direkt als Paketinhalt überschreiben.

Diese Regel ist eine Entpack- und Bereitstellungsgrenze, keine Sandbox für das anschließend gestartete Skript.

### 10.3 Vollständige Vorabvalidierung

Das gesamte Paket wird einschließlich aller Eintragstypen, Zielpfade, Duplikate, Kollisionen und Ressourcenbudgets validiert, bevor eine Zieldatei geschrieben wird.

Beim sicheren Apply werden zusätzlich vor der ersten Repository-Änderung:

- der Entrypoint privat temporär bereitgestellt,
- sein Pflichtmarker geprüft,
- der angeforderte Interpreter eindeutig bestimmt,
- die Verfügbarkeit des Interpreters geprüft,
- der Result-Ordner validiert und ein temporärer Ausgabepfad im endgültigen Result-Ordner reserviert.

Ein unsicherer, beschädigter oder mehrdeutiger Eintrag oder ein fehlender Interpreter macht das gesamte Paket ungültig. Kein Skript wird gestartet und keine endgültige Nutzdatei wird geschrieben.

### 10.4 Schreiben und Atomizität

- Nutzdateien werden bytegenau vorbereitet.
- Vorhandene reguläre Dateien werden ohne Nachfrage überschrieben.
- Jede Zieldatei wird zuerst vollständig in eine sichere temporäre Datei im selben Zielverzeichnis geschrieben und danach atomar ersetzt.
- Benötigte sichere Unterverzeichnisse werden angelegt.
- PatchHarbor legt keine dauerhaften Backups an.
- Jeder einzelne Dateiaustausch ist atomar.
- Das Gesamtpaket besitzt in 1.1.0 keine vollständige Transaktion und keine automatische globale Rückabwicklung.
- Scheitert die vollständige Vorbereitung oder ein tatsächlicher Schreibvorgang, startet kein Skript.

### 10.5 Ressourcenbudget

Ein Auftrag verwendet genau eine kleine unveränderliche `ResourcePolicy`.

Verbindliche Anfangswerte:

- Warning ab 10 MiB für einen einzelnen Skript- oder Nutzdateiinhalt,
- höchstens 256 MiB pro Eingabeartefakt oder ZIP-Eintrag,
- höchstens 512 MiB unkomprimierte Gesamtdaten eines Eingabe-ZIP-Archivs einschließlich Skripten, Manifest und Nutzdateien,
- höchstens 1.000 ZIP-Einträge einschließlich Verzeichnis-, Skript-, Manifest- und Nutzdateieinträgen.

Eine Pipe setzt das harte Eingabebudget bereits während des Empfangs durch.

Die ZIP-Auflösung prüft deklarierte Größen und Eintragszahlen vorab und die tatsächlich gelesenen Bytes erneut während des Lesens. Die Vorabprüfung stoppt offensichtlich zu große Archive früh; die laufende Prüfung schützt vor falschen oder manipulierten Größenangaben.

Eine Überschreitung eines harten Budgets führt vor der Ausführung zu einem Tool-Fehler. Die Warning-Schwelle allein verhindert die Verarbeitung nicht.

---

## 11. Interpreter und Ausführung

### 11.1 Unterstützte Interpreter

PatchHarbor 1.1.0 unterstützt bewusst Bash und PowerShell.

- Linux ohne Shebang: Bash.
- Windows ohne Shebang: Windows PowerShell.
- Ein bekannter unterstützter Shebang in der ersten Skriptzeile hat Vorrang.
- Bash: `#!/bin/bash`, `#!/usr/bin/bash`, `#!/usr/bin/env bash`.
- Windows PowerShell: `#!powershell`, `#!powershell.exe`, `#!/usr/bin/env powershell`, `#!/usr/bin/env powershell.exe`.
- PowerShell 7: `#!pwsh`, `#!pwsh.exe`, `#!/usr/bin/pwsh`, `#!/usr/bin/env pwsh`, `#!/usr/bin/env pwsh.exe`.
- Unbekannte, erweiterte oder beliebige Shebang-Kommandos werden nicht ausgeführt.
- Ein angeforderter Interpreter wird vor Prozessstart über den Systempfad gesucht.
- Fehlt er, endet PatchHarbor mit einem klaren Tool-Fehler.
- Die Dateiendung entscheidet nicht über den Interpreter.
- Eine temporäre Skriptdatei erhält lediglich eine technisch passende Endung.
- Weitere Interpreter dürfen später nur über eine kleine geprüfte Zuordnung ergänzt werden, nicht über freie Kommandoausführung.

### 11.2 PowerShell auf Windows

- PowerShell wird ohne Benutzerprofil und nicht interaktiv gestartet.
- Die festen Prozessargumente enthalten weder `-ExecutionPolicy` noch `Bypass`.
- PatchHarbor umgeht oder verändert keine lokale oder zentrale Execution Policy.
- Verhindert die Richtlinie die Ausführung, bleibt die native PowerShell-Fehlermeldung sichtbar und der PowerShell-Exit-Code wird unverändert zurückgegeben.

### 11.3 Nicht interaktive Ausführung

Die Standardeingabe des Kindprozesses ist geschlossen.

Nicht unterstützt sind insbesondere:

- Eingabeaufforderungen,
- Ja/Nein-Rückfragen,
- Warten auf Enter,
- interaktive Programmsitzungen,
- während der Ausführung erforderliche Benutzereingaben.

### 11.4 Timeout und Prozessende

- Standard-Timeout: 300 Sekunden pro Skript beziehungsweise Entrypoint.
- Der Wert ist über `--timeout` änderbar.
- Bei normalem Ende wird der Skript-Exit-Code übernommen.
- Bei Timeout versucht PatchHarbor zunächst eine geordnete Beendigung.
- Nach einer Frist von zwei Sekunden wird der vollständige Prozessbaum hart beendet.
- Unter Linux wird eine eigene Prozesssitzung beziehungsweise Prozessgruppe verwendet.
- Unter Windows wird eine echte Prozessbaum-Lösung verwendet, vorzugsweise ein Windows Job Object.
- Strg+C beendet Skript und Kindprozesse und liefert Exit-Code 130.
- Timeout liefert Exit-Code 124.

### 11.5 Reihenfolge im manuellen PatchBundle

1. Eingabeartefakt vollständig auflösen.
2. Gesamtes Bundle validieren.
3. Alle Skripteinträge vollständig parsen und Pflichtmarker prüfen.
4. Beschädigte optionale META- oder MESSAGE-Inhalte als Warning verwerfen.
5. Für alle auszuführenden Skripte den Interpreter bestimmen und seine Verfügbarkeit prüfen.
6. Alle Nutzdateien vollständig vorbereiten und sicher schreiben.
7. Skripte in der Archiv-Reihenfolge im ursprünglichen Arbeitsverzeichnis starten.
8. Output erfassen und Status darstellen.
9. Bei Erfolg mit dem nächsten Skript fortfahren oder beim ersten Fehler abbrechen.
10. Exit-Code des zuletzt ausgeführten Skripts zurückgeben.

Damit führt auch im manuellen ZIP-Pfad ein vorhersehbar fehlender Interpreter nicht erst nach dem Schreiben von Nutzdateien zum Abbruch.

## 12. Output, Terminaldarstellung und manuelles Logging

### 12.1 Output-Erfassung

- stdout und stderr werden zu einem gemeinsamen zeitlich beobachteten Strom zusammengeführt.
- PatchHarbor liest fortlaufend, damit der Kindprozess nicht an vollen Pipes blockiert.
- Intern werden die letzten zehn vollständigen oder begonnenen Ausgabezeilen im Rolling Buffer gehalten.
- Im Execution-Bereich werden die letzten fünf Zeilen angezeigt.
- Sehr lange Zeilen werden auf die verfügbare Breite gekürzt.
- Eine letzte Zeile ohne Zeilenumbruch wird angezeigt.
- Für die TUI werden ANSI- und andere Terminal-Steuersequenzen entfernt oder entschärft.
- Der vollständige Run-Log ist nicht auf den Rolling Buffer begrenzt.

### 12.2 Feste Terminaloberfläche

Im interaktiven Terminal verwendet PatchHarbor eine feste neu gezeichnete Oberfläche.

Regeln:

- maximale Breite 80 Zeichen,
- bei schmalerem Terminal tatsächliche Breite verwenden,
- bei zu schmalem Layout automatisch in den einfachen Textmodus wechseln,
- kein horizontaler Umbruch innerhalb fester Bereiche; Text rechts kürzen,
- feste Höhen für Informationsbereiche,
- vertikalen Überlauf durch Anzahl weiterer Elemente anzeigen,
- Redraw ungefähr alle 0,2 Sekunden während der Ausführung,
- sofortiger finaler Redraw nach Prozessende,
- sehr schnelle Skripte zeigen direkt den finalen Zustand,
- keine künstliche Pause nach Ende,
- keine zeitgesteuerten Informationen verschwinden lassen.

Vorgesehene Bereiche:

- Source,
- Repository beziehungsweise Kontext, sofern vorhanden,
- Messages,
- Files,
- Execution,
- Result.

Dateibereiche zeigen Pfad, Größe und Status, niemals Dateiinhalt.

### 12.3 Nicht interaktive Ausgabe

Ist stdout kein echtes Terminal, verwendet PatchHarbor automatisch fortlaufenden Text ohne Cursorsteuerung und Farben.

Das gilt insbesondere für:

- umgeleitete Ausgabe,
- CI-Systeme,
- Logsammler,
- Tests ohne Pseudo-Terminal.

`--plain` erzwingt diesen Modus auch im Terminal.

### 12.4 `--log` des manuellen Runners

Mit `patchharbor fs run --log` wird der vollständige zusammengeführte Output zusätzlich in eine sichere eindeutig benannte Datei im System-Temp-Verzeichnis geschrieben.

Das Log enthält:

- Startzeit,
- Quelle,
- Arbeitsverzeichnis,
- gewählten Interpreter,
- PatchHarbor-Warnings,
- vollständigen rohen Skriptoutput,
- Endzeit,
- Exit-Code oder Tool-Fehler.

Ohne `--log` erzeugt der manuelle Runner keine vollständige separate Ausgabedatei.

Der sichere Apply-Pfad verwendet unabhängig davon den vollständigen Run-Log für sein Result Bundle.

---

## 13. Registrierung lokaler Repository-Instanzen

### 13.1 Identitätsmodell

Ein entferntes Git-Repository kann mehrfach geklont, kopiert oder als zusätzlicher Worktree vorhanden sein. Jede lokale Instanz kann einen anderen Commit, Index und Working Tree besitzen.

Die PatchHarbor-ID gehört deshalb zu genau einer lokalen Repository-Instanz und nicht zum abstrakten Remote-Repository.

### 13.2 Globaler Registry-Lock und Persistenz

Alle lesenden und schreibenden Registry-Operationen verwenden einen eigenen globalen Registry-Lock. Dieser Lock ist von den Repository-Locks getrennt.

Verbindliche Lock-Reihenfolge:

1. globaler Registry-Lock,
2. danach gegebenenfalls der betroffene Repository-Lock.

Kein Codepfad darf diese Reihenfolge umkehren.

Die zentrale Registry wird:

- vollständig in eine temporäre Datei im selben Konfigurationsverzeichnis geschrieben,
- vor Veröffentlichung geschlossen und syntaktisch geprüft,
- anschließend über einen atomaren Austausch ersetzt,
- niemals durch stückweises direktes Überschreiben aktualisiert.

Eine Operation meldet erst Erfolg, wenn lokale ID-Datei und zentrale Registry konsistent sind. Scheitert eine Teiloperation, versucht PatchHarbor den vorherigen Zustand wiederherzustellen und meldet bei verbleibender Inkonsistenz einen ausdrücklichen Registry-Fehler. Es wird kein scheinbarer Erfolg ausgegeben.

### 13.3 Registrierung

```bash
patchharbor register
patchharbor register /pfad/zum/repository
```

PatchHarbor führt unter dem globalen Registry-Lock mindestens aus:

1. kanonischen Repository-Wurzelpfad bestimmen,
2. prüfen, dass `HEAD` auf einen Commit auflösbar ist,
3. prüfen, dass weder der Base-Baum von `HEAD` noch der Index einen Pfad mit dem reservierten Segment `.patchharbor` in beliebiger Groß-/Kleinschreibung enthält,
4. prüfen, dass die neue Repository-Wurzel keinen konfigurierten Watcher-Eingangsordner oder Result-Ordner enthält und mit keinem solchen Pfad identisch ist,
5. prüfen, dass ein vorhandener Pfad `.patchharbor` ein echtes reguläres Verzeichnis und weder Symlink noch Junction noch Datei ist,
6. das lokale interne Verzeichnis andernfalls sicher anlegen,
7. eine vorhandene lokale ID validieren oder eine UUID v4 erzeugen,
8. den vollständigen lokalen Pfad `.patchharbor/` über den von `git rev-parse --git-path info/exclude` gelieferten Exclude-Pfad aus der normalen Git-Statusanzeige ausnehmen,
9. veraltete zentrale Zuordnungen desselben kanonischen Pfads entfernen,
10. lokale ID-Datei und zentrale Registry konsistent und atomar aktualisieren,
11. einen fertigen Kontextblock zum Kopieren in den Chat ausgeben.

PatchHarbor verändert nicht ungefragt die gemeinsam versionierte `.gitignore`.

### 13.4 Repository-ID

Die Repository-ID ist eine UUID v4.

Beispiel:

```text
a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d
```

Eigenschaften:

- 36 Zeichen einschließlich Bindestrichen,
- automatisch erzeugt,
- praktisch eindeutig,
- unabhängig von Name, Remote-URL, Branch und Pfad,
- stabil für genau diese lokale Instanz,
- nicht zu kürzen,
- nicht fachlich zu interpretieren.

Jeder lokale Klon oder Worktree erhält eine eigene UUID.

### 13.5 Reserviertes lokales Verzeichnis

Das vollständige Verzeichnis:

```text
.patchharbor/
```

ist für lokale PatchHarbor-Daten reserviert.

Für Version 1.1.0 enthält es mindestens:

```text
.patchharbor/id
```

Der Inhalt von `id` besteht ausschließlich aus der UUID und einem abschließenden Zeilenumbruch.

Verbindliche Regeln:

- Kein Pfad unter `.patchharbor/` darf von Git getrackt sein.
- `.patchharbor` selbst darf kein Symlink, keine Junction und kein anderer besonderer Dateityp sein.
- Die ID-Datei muss eine reguläre Datei sein und wird atomar ersetzt.
- Das gesamte Verzeichnis wird lokal ausgeschlossen und nicht in Result Bundles aufgenommen.
- Die Repository-ID selbst steht in den maschinenlesbaren Kontextdateien.

### 13.6 Idempotente Registrierung und Pfadänderungen

Ist derselbe kanonische Pfad bereits mit derselben gültigen ID registriert, ist `patchharbor register` idempotent und gibt den bestehenden Kontext zurück.

Ist eine ID einem anderen weiterhin vorhandenen Pfad zugeordnet, wird nicht geraten. Die Registrierung wird als Konflikt abgelehnt.

Ist die ID-Datei mit dem Repository an einen neuen Pfad verschoben worden und der bisher registrierte Pfad existiert nicht mehr, darf `patchharbor register` die Zuordnung auf den neuen kanonischen Pfad aktualisieren.

Fehlt die lokale ID-Datei, erzeugt eine normale Registrierung eine neue UUID. Vor der neuen Zuordnung werden alle alten Registry-Einträge entfernt, deren kanonischer Pfad exakt dieser lokalen Instanz entspricht. Dadurch bleiben niemals zwei IDs für denselben kanonischen Pfad als erfolgreicher Zustand bestehen.

### 13.7 Minimale Registry-Verwaltung

```bash
patchharbor registry list
```

liest unter dem globalen Registry-Lock einen konsistenten Snapshot und zeigt mindestens:

- `repo_id`,
- kanonischen Pfad,
- Status `ok`, `missing` oder `conflict`.

```bash
patchharbor unregister REPOSITORY_OR_REPO_ID
```

entfernt unter dem globalen Registry-Lock die zentrale Zuordnung. Soweit ein vorhandenes Repository betroffen ist, wird zusätzlich dessen Repository-Lock beachtet. Die lokale `.patchharbor/id` bleibt bestehen, damit ein verschobenes oder später erneut registriertes Repository seine Identität behalten kann.

```bash
patchharbor register --new-id [REPOSITORY]
```

- erzeugt bewusst eine neue UUID,
- ersetzt die lokale ID-Datei atomar,
- entfernt alte Zuordnungen genau dieses kanonischen Pfads,
- verändert nicht die gültige Zuordnung eines anderen Pfads mit einer kopierten alten ID,
- registriert die neue ID,
- ist der vorgesehene Minimalweg zur Auflösung einer kopierten ID.

Registry-Mutationen, die eine aktuell gesperrte Repository-Instanz verändern würden, warten kontrolliert oder schlagen mit einer eindeutigen Busy-Meldung fehl; sie umgehen den Repository-Lock nicht.

## 14. Repository-Kontext und Zustandsmodell

### 14.1 Kontextbefehl

```bash
patchharbor context
patchharbor context /pfad/zum/repository
```

Der Kontextbefehl verwendet den Repository-Lock für die Dauer seiner Zustandsaufnahme.

Beispiel:

```text
PATCH_HARBOR_CONTEXT

repo_id: a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d
base_commit: f4e9c2a7b8c9d01234567890abcdef1234567890
dirty: true
state_fingerprint: a1b2c3d4e5f67890
fingerprint_algorithm: patchharbor-state-v1

INSTRUCTIONS:
- Verwende diese Werte unverändert in patch.json.
- Erzeuge bei geändertem Repository-Zustand einen neuen Kontext.
```

Der Chat darf Repository-ID, Base-Commit oder Fingerprint nicht erraten.

### 14.2 Base-Commit

`base_commit` ist die vollständige Ausgabe von:

```bash
git rev-parse HEAD
```

Der Wert wird nicht künstlich auf 40 Zeichen begrenzt und unterstützt damit unterschiedliche Git-Objektformate.

Der Base-Commit beschreibt den committed Basiszustand und wird getrennt vom Fingerprint geprüft.

### 14.3 Dirty State

Der Dirty State beschreibt alle nicht in `HEAD` enthaltenen unterstützten Git-Zustände:

- staged Änderungen im Index,
- unstaged Änderungen zwischen Index und Working Tree,
- nicht ignorierte untracked reguläre Dateien.

Dazu gehören Hinzufügungen, Änderungen, Löschungen und unterstützte Dateimodusänderungen. Umbenennungen werden kanonisch als Löschung plus Hinzufügung dargestellt.

Ignorierte Dateien werden nicht aufgenommen.

### 14.4 Algorithmuskennung

Der verbindliche Algorithmus heißt:

```text
patchharbor-state-v1
```

Jeder Kontext und jedes Manifest nennt diese Kennung. Ein unbekannter Algorithmus wird abgelehnt.

Der endgültige Fingerprint ist:

```text
SHA-256 über den kanonischen Eingabestrom
→ erste 16 kleingeschriebene Hex-Zeichen
```

### 14.5 Unterstützte Repository-Grenzen

Der sichere 1.1.0-Pfad unterstützt ausschließlich Repository-Zustände, die auf Linux und Windows eindeutig, sicher und vollständig darstellbar sind.

Die Pfadprüfung umfasst die Vereinigungsmenge aus:

- allen Pfaden des Base-Baums von `HEAD`,
- allen Pfaden des Index,
- allen von Git als unstaged betroffen gemeldeten getrackten Pfaden,
- allen nicht ignorierten untracked Pfaden.

Damit wird ein im Base-Baum noch vorhandener, aber im Index bereits zur Löschung vorgesehener verbotener Pfad ebenfalls abgelehnt.

Alle von Git gelieferten Repository-Pfade müssen gültiges UTF-8 sein. PatchHarbor decodiert streng, führt keine Unicode-Normalisierung aus und verwendet für Hashing und Manifest wieder exakt die ursprünglichen UTF-8-Bytes. Ein nicht streng als UTF-8 darstellbarer Pfad führt zu einem klaren Fehler wegen nicht unterstützten Repository-Zustands.

Jeder Repository-Pfad ist ein relativer POSIX-Pfad mit `/` als Segmenttrenner. Für jedes Segment gelten verbindlich:

- nicht leer,
- weder `.` noch `..`,
- kein NUL-Byte,
- keine ASCII-Steuerzeichen `U+0001` bis `U+001F` und kein `U+007F`,
- keines der Zeichen `<`, `>`, `:`, `"`, `\`, `|`, `?` oder `*`,
- kein abschließender Punkt und kein abschließendes ASCII-Leerzeichen,
- weder `.git` noch `.patchharbor` nach Unicode-`casefold()`,
- kein reservierter Windows-Gerätename nach Unicode-`casefold()`.

Als reservierte Windows-Gerätenamen gelten der Segmentteil vor dem ersten Punkt mit den Werten:

```text
con
prn
aux
nul
com1 bis com9
lpt1 bis lpt9
conin$
conout$
clock$
```

Für die Kollisionsprüfung bildet PatchHarbor aus jedem vollständig decodierten Pfad einen Vergleichsschlüssel mit Unicode-`casefold()`, ohne die gespeicherten Pfadbytes zu verändern. Zwei verschiedene Repository-Pfade mit demselben Vergleichsschlüssel werden als Groß-/Kleinschreibungs-Kollision abgelehnt.

Die gleichen Portabilitätsregeln gelten für Pfade, die in `base/`, `untracked/`, Rekonstruktions-Patches oder JSON-Manifeste aufgenommen werden. Ein nicht sicher als regulärer UTF-8-ZIP-Pfad darstellbarer Repository-Pfad wird vor Kontextausgabe, Apply oder Bundle-Erzeugung abgelehnt.

Vor Kontext, Apply und Bundle werden außerdem folgende Zustände abgelehnt:

- nicht aufgelöste Merge-Stages,
- Indexeinträge mit `assume-unchanged`,
- Indexeinträge mit `skip-worktree`,
- Intent-to-add-Einträge,
- aktiviertes Sparse-Checkout,
- Sparse-Index,
- Gitlink-Einträge beziehungsweise Submodule,
- getrackte symbolische Links in `HEAD` oder Index,
- ein symbolischer Link oder anderer besonderer Dateityp an einem getrackten Working-Tree-Pfad,
- andere getrackte Modi als `100644` und `100755`,
- nicht reguläre untracked Einträge.

Der manuelle Befehl `patchharbor fs run` ist von diesen Repository-Grenzen nicht betroffen.

### 14.6 Kanonische Git-Umgebung und Abfragen

Alle Git-Befehle laufen:

- im kanonischen Repository-Wurzelverzeichnis,
- mit `LC_ALL=C` und `LANG=C`,
- mit `GIT_OPTIONAL_LOCKS=0`,
- mit deaktiviertem externem Diff-Programm,
- ohne Textkonvertierung,
- ohne Rename-Erkennung,
- ohne Farbausgabe,
- mit NUL-getrennter Pfadausgabe, wo Git sie anbietet.

Verbindliche Abfragen umfassen mindestens:

```text
git rev-parse HEAD
git ls-tree -r -z --full-tree <base_commit>
git ls-files --stage -z
git ls-files --unmerged -z
git ls-files -v -z
git diff-files --raw -z --no-renames --no-ext-diff --
git ls-files --others --exclude-standard -z --
git config --bool --get core.fileMode
git config --bool --get core.sparseCheckout
git config --bool --get index.sparse
```

Fehlende boolesche Konfigurationswerte gelten als `false`, soweit Git keinen repositoryspezifischen Standardwert liefert.

Sonderzustände werden wie folgt erkannt:

- Eine nicht leere Ausgabe von `git ls-files --unmerged -z` wird abgelehnt.
- Bei `git ls-files -v -z` kennzeichnet ein führendes `S` einen Skip-Worktree-Eintrag; ein kleingeschriebener führender Statusbuchstabe kennzeichnet Assume-Unchanged. Beide werden abgelehnt.
- Ein `A`-Datensatz in `git diff-files --raw -z` wird als Intent-to-add-Sonderzustand abgelehnt.
- `core.sparseCheckout=true` oder `index.sparse=true` wird abgelehnt.
- Baum- oder Indexmodi `120000` und `160000` sowie alle nicht ausdrücklich unterstützten Modi werden abgelehnt.

PatchHarbor liest die Ausgaben als Bytes und normalisiert keine Zeilenenden oder Pfadbytes.

### 14.7 Kanonischer staged Zustand

PatchHarbor bildet aus `git ls-tree -r -z --full-tree <base_commit>` den Base-Baum und aus `git ls-files --stage -z` den Index ab.

Für jeden Pfad, dessen `(mode, object-id)` zwischen Base-Commit und Index abweicht, wird genau ein staged Datensatz erzeugt.

Ein Datensatz enthält in dieser Reihenfolge:

1. Pfadbytes,
2. Base-Modus oder leeres Feld,
3. vollständige Base-Objekt-ID oder leeres Feld,
4. Indexmodus oder leeres Feld,
5. vollständige Indexobjekt-ID oder leeres Feld.

Die Datensätze werden byteweise nach Pfad sortiert.

Damit sind Hinzufügungen, Änderungen, Löschungen und Modusänderungen eindeutig beschrieben, ohne von einer konfigurierbaren Patch-Darstellung abhängig zu sein.

### 14.8 Kanonischer unstaged Zustand

`git diff-files --raw -z --no-renames --no-ext-diff --` bestimmt die getrackten Pfade, die Git gegenüber dem Index als unstaged verändert betrachtet.

Ein Intent-to-add-Datensatz wird vor der Fingerprint-Bildung abgelehnt.

Für jeden übrigen betroffenen Pfad wird genau ein Datensatz erzeugt. Er enthält:

1. Pfadbytes,
2. Git-Statusbyte,
3. Indexmodus,
4. vollständige Indexobjekt-ID,
5. Working-Tree-Art `missing` oder `regular`,
6. kanonischen Working-Tree-Modus,
7. vollständigen aktuellen Inhalt als rohe Bytes; bei `missing` ein leeres Feld.

Die Datensätze werden byteweise nach Pfad sortiert.

Der Working-Tree-Modus lautet:

- `100755`, wenn `core.fileMode=true` gilt und mindestens ein Ausführungsbit der regulären Datei gesetzt ist,
- sonst `100644` für reguläre Dateien,
- leer für fehlende Einträge.

PatchHarbor verwendet `lstat` und folgt keinem symbolischen Link. Trifft es an einem getrackten Pfad auf einen Symlink, ein Verzeichnis oder einen anderen besonderen Dateityp, wird der sichere Auftrag abgelehnt.

### 14.9 Kanonischer untracked Zustand

Die Ausgabe von `git ls-files --others --exclude-standard -z --` liefert die nicht ignorierten untracked Pfade.

Die Pfade werden byteweise sortiert.

Für jeden Pfad werden einbezogen:

1. Pfadbytes,
2. kanonischer Modus,
3. Dateigröße,
4. vollständiger Dateiinhalt als rohe Bytes.

Der kanonische Modus lautet:

- `100755`, wenn `core.fileMode=true` gilt und mindestens ein Ausführungsbit gesetzt ist,
- sonst `100644`.

Nur reguläre Dateien sind zulässig. Symlinks, Junctions, Geräte, FIFOs, Sockets, Verzeichnisse oder andere besondere Einträge führen zu einem klaren Kontextfehler und werden niemals dereferenziert.

### 14.10 Kanonische Payloadcodierung und Byte-Rahmung

Der Hash-Eingabestrom beginnt exakt mit diesen Bytes:

```text
PATCHHARBOR_STATE_FINGERPRINT\0
1\0
```

Feldnamen sind exakt die in diesem Abschnitt genannten ASCII-Bytes ohne Groß-/Kleinschreibungsvariation.

Jedes Feld wird codiert als:

```text
ASCII-Feldname
+ NUL-Byte
+ 8-Byte-Länge des Payloads, unsigned big-endian
+ Payloadbytes
```

Für alle Payloads gelten verbindlich:

| Fachlicher Wert | Exakte Payloadcodierung |
|---|---|
| Repository-Pfad | Die ursprünglichen streng validierten UTF-8-Pfadbytes, ohne Normalisierung und ohne abschließendes NUL. |
| Git-Modus | ASCII `100644` oder ASCII `100755`; ein fachlich fehlender Modus ist ein Payload der Länge null. |
| Git-Objekt-ID | Vollständiger kleingeschriebener ASCII-Hex-String des Repository-Objektformats; 40 Zeichen bei SHA-1 und 64 Zeichen bei SHA-256. Keine Abkürzung und keine rohen Objekt-ID-Bytes. |
| Unstaged-Status | Genau ein großgeschriebenes ASCII-Byte. Im unterstützten 1.1.0-Zustand sind ausschließlich `M` und `D` zulässig. |
| Working-Tree-Art | Exakt ASCII `regular` oder ASCII `missing`. |
| Dateiinhalt | Unveränderte rohe Bytes, einschließlich vorhandener NUL-Bytes und Zeilenenden. |
| Zähler und Dateigröße | Genau acht Bytes, unsigned big-endian. |
| Fachlich leerer Wert | Payloadlänge null; das Feld selbst bleibt vorhanden. |

Es werden keine impliziten Zeilenumbrüche, Terminatoren, Textcodierungen oder Trennzeichen ergänzt.

Die Payload jedes Zählerfelds ist eine 8-Byte-Zahl, unsigned big-endian.

Abschnittsreihenfolge und exakte Feldnamen:

1. `staged-count`,
2. je staged Datensatz: `staged-path`, `staged-head-mode`, `staged-head-object`, `staged-index-mode`, `staged-index-object`,
3. `unstaged-count`,
4. je unstaged Datensatz: `unstaged-path`, `unstaged-status`, `unstaged-index-mode`, `unstaged-index-object`, `unstaged-worktree-kind`, `unstaged-worktree-mode`, `unstaged-worktree-content`,
5. `untracked-count`,
6. je untracked Datensatz: `untracked-path`, `untracked-mode`, `untracked-size`, `untracked-content`.

Die Payload von `untracked-size` ist eine 8-Byte-Zahl, unsigned big-endian. Leere fachliche Werte werden als Feld mit Payloadlänge null codiert; das Feld selbst wird nicht ausgelassen.

Jeder Datensatz besteht damit ausschließlich aus einzeln längencodierten Feldern. Es gibt keine Trennzeichenverkettung ohne Längenfeld.

Der Base-Commit wird nicht in diesen Eingabestrom aufgenommen.

### 14.11 Clean-Zustand

Auch ein sauberes Repository besitzt einen deterministischen Fingerprint. Alle drei Zähler sind null; das zusätzliche Feld `dirty: false` dient nur der Lesbarkeit.

### 14.12 Referenz-Testvektoren

Die Implementierung muss mindestens die folgenden reinen Encoder-Testvektoren erfüllen. Die Zeichenfolgen in den Vektoren werden nach den Codierungsregeln aus Abschnitt 14.10 in Payloadbytes überführt.

#### Leerer Zustand

Für einen leeren Zustand mit null staged, null unstaged und null untracked Datensätzen:

```text
vollständiger SHA-256:
7c9d2a24e397e0e58d8caf4c14abf8f76879b256ef7f843655981fb751c7b309

16-stelliger Fingerprint:
7c9d2a24e397e0e5
```

#### Genau eine untracked Datei

```text
Pfad:    note.txt
Modus:   100644
Inhalt:  hello\n
```

Alle staged- und unstaged-Zähler sind null; `untracked-count` ist eins.

```text
vollständiger SHA-256:
05fe268b93ee2ea113d23b0dfc1becd7bfe881f8992e91b7e2ea8bdea2745310

16-stelliger Fingerprint:
05fe268b93ee2ea1
```

#### Genau eine staged Hinzufügung

```text
staged-path:          app.txt
staged-head-mode:     <leer>
staged-head-object:   <leer>
staged-index-mode:    100644
staged-index-object:  0123456789abcdef0123456789abcdef01234567
```

`staged-count` ist eins; alle unstaged- und untracked-Zähler sind null.

```text
vollständiger SHA-256:
b56f3f6610db992f53139dc53d1decdccb9fd510260dafa1a29473c47a257008

16-stelliger Fingerprint:
b56f3f6610db992f
```

#### Genau eine unstaged Änderung

```text
unstaged-path:              app.txt
unstaged-status:            M
unstaged-index-mode:        100644
unstaged-index-object:      0123456789abcdef0123456789abcdef01234567
unstaged-worktree-kind:     regular
unstaged-worktree-mode:     100644
unstaged-worktree-content:  hello\n
```

Alle staged- und untracked-Zähler sind null; `unstaged-count` ist eins.

```text
vollständiger SHA-256:
fa106451ef080706f5f24269d0dc2192bd50ef6f5ac69215485771137a8d3010

16-stelliger Fingerprint:
fa106451ef080706
```

Die vier Testvektoren prüfen Feldcodierung, Abschnittsreihenfolge und Byte-Rahmung. Repository-basierte Tests prüfen zusätzlich die kanonische Erzeugung aller staged-, unstaged- und untracked Datensätze auf Linux und Windows.

### 14.13 Kontextänderung

Ändert sich nach der Kontexterzeugung einer der folgenden Zustände, ist ein alter Patch nicht mehr gültig:

- `HEAD`,
- Index,
- getrackter Working Tree,
- Pfad, Modus oder Inhalt einer nicht ignorierten untracked Datei.

PatchHarbor lehnt den Patch ab. Der Benutzer erzeugt einen neuen Kontext oder ein neues Result Bundle.

## 15. Sicheres Patch-Paket

### 15.1 Container

Ein über `patchharbor apply` verarbeiteter Patch ist immer ein ZIP-Paket.

Der äußere Dateiname und die Dateiendung sind keine Sicherheits- oder Zuordnungsinformation. PatchHarbor prüft die tatsächlichen ZIP-Bytes.

### 15.2 Verpflichtende Wurzeldatei

Im Wurzelverzeichnis des ZIP-Pakets liegt genau eine Datei mit dem Namen:

```text
patch.json
```

Weitere sichere Dateien und Unterverzeichnisse sind zulässig.

Beispiel:

```text
patch.zip
├── patch.json
├── run.sh
└── files/
    └── configuration.bin
```

### 15.3 `patch.json`

`patch.json` ist UTF-8 ohne Byte-Order-Mark und enthält genau ein JSON-Objekt. Doppelte Schlüssel, Kommentare, nachgestellte Daten und nicht endliche Zahlenwerte sind ungültig.

Für Paketformat 1 sind ausschließlich die folgenden sieben Schlüssel zulässig; unbekannte oder zusätzliche Schlüssel werden abgelehnt:

```json
{
  "marker": "patch-harbor",
  "format_version": 1,
  "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
  "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
  "state_fingerprint": "a1b2c3d4e5f67890",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "entrypoint": "run.sh"
}
```

Der Vertrag lautet exakt:

| Feld | Typ und Validierung |
|---|---|
| `marker` | JSON-String, exakt `patch-harbor`. |
| `format_version` | JSON-Integer, exakt `1`; ein Boolean oder Gleitkommawert ist ungültig. |
| `repo_id` | JSON-String in kanonischer kleingeschriebener UUID-v4-Schreibweise nach dem Muster `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`, wobei `y` eines von `8`, `9`, `a`, `b` ist. |
| `base_commit` | JSON-String mit der vollständigen kleingeschriebenen Hex-Objekt-ID; exakt 40 Zeichen für ein SHA-1-Repository oder 64 Zeichen für ein SHA-256-Repository. Abgekürzte Objekt-IDs sind verboten. |
| `state_fingerprint` | JSON-String aus exakt 16 kleingeschriebenen Hex-Zeichen. |
| `fingerprint_algorithm` | JSON-String, exakt `patchharbor-state-v1`. |
| `entrypoint` | Nicht leerer JSON-String, der nach Abschnitt 10 einen sicheren relativen ZIP-Pfad bezeichnet, nicht `patch.json` ist und exakt einen vorhandenen regulären ZIP-Eintrag referenziert. |

Die exakte Objekt-ID-Länge wird nach Auflösung von `repo_id` gegen das Objektformat des Ziel-Repositorys geprüft. Der angegebene Commit muss zusätzlich exakt dem aktuellen `HEAD` entsprechen.

Eine Verletzung dieses Schemas, eine nicht unterstützte Formatversion oder eine unbekannte Semantik führt vor der Repository-Änderung zur Ablehnung. Erweiterungen des Paketvertrags erfordern eine neue `format_version`.

### 15.4 Entrypoint-Lebenszyklus

Der Entrypoint:

- ist genau ein regulärer ZIP-Eintrag,
- liegt nicht unter einem verbotenen Pfad,
- wird nicht als Nutzdatei in das Repository geschrieben,
- wird in ein privates temporäres Auftragsverzeichnis extrahiert,
- wird dort vollständig gelesen und anhand des exakten Skriptmarkers validiert,
- wird mit der bestehenden Interpreter-Whitelist gestartet,
- läuft mit dem Ziel-Repository als aktuellem Arbeitsverzeichnis,
- erhält geschlossene Standardeingabe,
- wird nach dem Auftrag entfernt.

Der temporäre Speicherort ist kein Teil der öffentlichen Patch-Schnittstelle.

### 15.5 Weitere Paketdateien

Jeder andere sichere reguläre ZIP-Eintrag außer `patch.json` und dem Entrypoint ist eine Nutzdatei.

Nutzdateien können Text, Binärdaten, Unterverzeichnisse oder nicht automatisch ausgeführte Hilfsskripte enthalten. Sie werden bytegenau in den entsprechenden relativen Repository-Pfad geschrieben.

Nur der in `patch.json` benannte Entrypoint wird automatisch gestartet. Ein Marker in einer anderen Paketdatei macht diese Datei nicht zu einem weiteren Entrypoint.

### 15.6 Keine rekursive Paketauflösung

Ein enthaltenes ZIP oder anderes Archiv wird nicht als weiteres Patch-Paket geöffnet. Ist es ein sicherer regulärer Nutzdateieintrag, wird es ausschließlich bytegenau als Datei behandelt.

---

## 16. Exklusive Repository-Sperre und Apply-Ablauf

### 16.1 Sperrmodell

Für jede `repo_id` existiert genau eine betriebssystemübergreifende exklusive Sperre im benutzerspezifischen Lock-Verzeichnis.

Die Sperre:

- wird von `context`, `apply`, `apply --dry-run` und `bundle` verwendet,
- gilt pro `repo_id`, nicht pro Download-Dateiname,
- wird vor der ersten Zustandsaufnahme erworben,
- bleibt bei `apply`, Dry-Run und Bundle bis zum Abschluss oder Fehlschlag der Result-Bundle-Erzeugung gehalten,
- wird bei `context` unmittelbar nach der konsistenten Zustandsaufnahme freigegeben,
- wird über einen sicheren Cleanup-Pfad freigegeben,
- darf durch Prozessabsturz nicht dauerhaft unauflösbar werden.

Kann die Sperre nicht erworben werden, startet kein weiterer Auftrag für dieses Repository. PatchHarbor liefert den Tool-Fehler „Repository beschäftigt“.

Die Sperre koordiniert PatchHarbor-Aufträge. Fremde Editoren oder andere Git-Prozesse werden dadurch nicht blockiert.

Bei einer Auflösung über die zentrale Registry gilt die Lock-Reihenfolge aus Abschnitt 13: zuerst globaler Registry-Lock, danach Repository-Lock. Nach erfolgreicher Revalidierung wird der Registry-Lock freigegeben, während der Repository-Lock bis zum Auftragsende gehalten bleibt.

### 16.2 Sicher aufgelöstes Repository

Ein Repository gilt erst dann als sicher aufgelöst, wenn:

1. `patch.json` soweit gültig gelesen wurde, dass `repo_id` verfügbar ist,
2. unter dem globalen Registry-Lock genau eine Zuordnung gefunden wurde,
3. der kanonische Pfad existiert,
4. der Pfad weiterhin ein gültiges Git-Repository ist,
5. `.patchharbor` ein reguläres lokales Verzeichnis ist,
6. `.patchharbor/id` exakt dieselbe ID enthält,
7. kein Pfad unter `.patchharbor/` getrackt ist,
8. die exklusive Repository-Sperre in der verbindlichen Lock-Reihenfolge erworben wurde,
9. Registry-Zuordnung, Pfad und lokale ID unter beiden Locks erneut übereinstimmen.

Ab diesem Zeitpunkt versucht PatchHarbor am Ende des Auftrags stets, ein Result Bundle zu erzeugen.

Kann das Repository vorher nicht sicher aufgelöst werden, entsteht kein Repository-Snapshot.

### 16.3 Validierungs- und Ausführungsreihenfolge

`patchharbor apply PATCH_ZIP` führt mindestens aus:

1. Eingabedatei stabil und vollständig lesbar öffnen.
2. Tatsächliches ZIP-Format prüfen.
3. Archivstruktur, Eintragstypen, Pfade und Ressourcenlimits vollständig prüfen.
4. `patch.json` im ZIP-Wurzelverzeichnis finden.
5. Striktes JSON-Schema, Paketmarker, Fingerprint-Algorithmus und Formatversion prüfen.
6. `repo_id` unter dem globalen Registry-Lock eindeutig auflösen.
7. Kanonischen Result-Ordner bestimmen, gegen alle registrierten Repository-Pfade und den Watcher-Eingangsordner prüfen und dort einen temporären Ausgabepfad reservieren.
8. Zielpfad, Git-Repository, reserviertes lokales Verzeichnis und ID-Datei prüfen.
9. Exklusive Repository-Sperre erwerben, Zuordnung unter beiden Locks erneut validieren und danach den Registry-Lock freigeben.
10. Unterstützte Repository- und Pfadgrenzen aus Abschnitt 14 prüfen.
11. Aktuellen vollständigen Base-Commit bestimmen und mit dem Manifest vergleichen.
12. Aktuellen Fingerprint bestimmen und mit dem Manifest vergleichen.
13. Entrypoint und alle Nutzdateipfade vollständig prüfen.
14. Entrypoint in einem privaten Temp-Verzeichnis bereitstellen und den Pflichtmarker prüfen.
15. Interpreter bestimmen und seine Verfügbarkeit prüfen.
16. Alle Nutzdateiinhalte vollständig in Speicher oder ein privates auftragsbezogenes Temp-Verzeichnis außerhalb des Repositorys lesen und deren Größen und Hashes gegen die bereits validierten ZIP-Einträge prüfen. Noch wird keine temporäre Datei in einem Repository-Zielverzeichnis erzeugt.
17. Unmittelbar vor der ersten Repository-Schreiboperation Base-Commit und Fingerprint erneut bestimmen. Beide Werte müssen sowohl den Manifestwerten als auch den in den Schritten 11 und 12 ermittelten Werten exakt entsprechen.
18. Nur bei unverändertem Zustand die Zielpfade und Elternverzeichnisse erneut gegen Austausch, Symlinks, Junctions und besondere Dateitypen prüfen und sichere temporäre Zieldateien in den jeweiligen Repository-Zielverzeichnissen erzeugen.
19. Nutzdateien jeweils atomar in ihre endgültigen Repository-Pfade austauschen.
20. Entrypoint im Repository-Wurzelverzeichnis ausführen.
21. stdout, stderr, Exit-Code, Laufzeit und Warnings erfassen.
22. Aktuellen Repository-Zustand konsistent aufnehmen.
23. Result Bundle in der reservierten temporären Datei im endgültigen Result-Ordner erstellen, prüfen und atomar veröffentlichen.
24. Repository-Sperre und temporäre Ressourcen freigeben.

Scheitert eine rein lesende Vorprüfung einschließlich der zweiten Zustandsprüfung, Result-Ziel-, Marker- oder Interpreterprüfung, wird keine temporäre oder endgültige Datei in einem Repository-Zielverzeichnis erzeugt.

Die zweite Zustandsprüfung schützt das Zeitfenster zwischen der ersten Kontextprüfung und der ersten Schreiboperation gegen Änderungen durch fremde Editoren oder Git-Prozesse. Der Repository-Lock bleibt zusätzlich für die gesamte PatchHarbor-Ausführung bestehen.

### 16.4 Harte Ablehnung

PatchHarbor nimmt keine Fuzzy-Zuordnung vor.

Keine Ersatzschlüssel sind:

- Repository-Name,
- Remote-URL,
- Branchname,
- Download-Dateiname,
- zuletzt verwendete Repository-Instanz.

Harte Ablehnungsgründe sind insbesondere:

- unbekannte oder mehrdeutige Repository-ID,
- ungültige lokale ID-Datei,
- getrackte oder besondere `.patchharbor`-Struktur,
- Base-Commit-Mismatch,
- Fingerprint- oder Algorithmus-Mismatch,
- nicht unterstützter Git-Sonderzustand,
- nicht als UTF-8 darstellbarer Repository-Pfad,
- ungültiges Manifest,
- unsicherer Paketpfad,
- verbotener interner Pfad,
- fehlender Entrypoint,
- fehlender Interpreter,
- ungültiger oder im Repository liegender Result-Ordner,
- überschrittenes Ressourcenbudget,
- bereits gesperrtes Repository.

### 16.5 Konsistenter Snapshot trotz äußerer Änderungen

Vor der Snapshot-Aufnahme wird der aktuelle Kontext bestimmt. Während der Aufnahme werden genau die Daten gelesen, die in das Result Bundle geschrieben werden.

Nach der Aufnahme bestimmt PatchHarbor Base-Commit und Fingerprint erneut.

Nur wenn Vorzustand, aufgenommene Daten und Nachzustand konsistent sind, wird das temporäre Result Bundle veröffentlicht.

Ändert ein fremder Prozess das Repository während der Aufnahme, wird die temporäre Bundle-Datei entfernt und die Bundle-Erzeugung schlägt klar fehl.

Da die temporäre Bundle-Datei außerhalb aller registrierten Repositories liegt, verändert die Snapshot-Erzeugung den aufzunehmenden Repository-Zustand nicht.

## 17. Dry-Run

```bash
patchharbor apply --dry-run PATCH_ZIP
```

### 17.1 Der Dry-Run führt aus

- vollständige ZIP- und Ressourcenvalidierung,
- `patch.json`-Validierung,
- Repository-Auflösung,
- lokale ID-Prüfung,
- exklusive Sperre,
- Base-Commit-Vergleich,
- Fingerprint-Berechnung und Vergleich,
- Entrypoint- und Nutzdateipfadprüfung,
- Interpreter-Verfügbarkeitsprüfung, soweit ohne Prozessstart möglich,
- Erzeugung eines Result Bundles des unveränderten Repository-Zustands.

### 17.2 Der Dry-Run führt nicht aus

- keine Nutzdatei wird geschrieben,
- kein Entrypoint wird gestartet,
- kein Kindprozess wird erzeugt,
- keine Repository-Datei wird verändert,
- kein Test wird gestartet,
- kein Commit wird erzeugt.

Das Result Bundle kennzeichnet:

```json
{
  "dry_run": true,
  "entrypoint_started": false,
  "execution_present": false
}
```

---

## 18. Auftragsergebnis und Result-Bundle-Fehler

PatchHarbor behandelt zwei getrennte Ergebnisse:

1. das primäre Auftragsergebnis,
2. das Ergebnis der Result-Bundle-Erzeugung.

### 18.1 Grundregel

Ein Fehler bei der Result-Bundle-Erzeugung überschreibt einen bereits vorhandenen primären Fehler nicht. Er überschreibt nur einen ansonsten erfolgreichen Auftrag.

| Primärer Auftrag | Result Bundle | Prozess-Exit-Code |
|---|---|---:|
| erfolgreich | erfolgreich | `0` |
| erfolgreich | fehlgeschlagen | `11` |
| fehlgeschlagen | erfolgreich | primärer Fehlercode |
| fehlgeschlagen | ebenfalls fehlgeschlagen | primärer Fehlercode |

Beispiele:

- Entrypoint Exit `0`, Bundle fehlgeschlagen: PatchHarbor Exit `11`.
- Entrypoint Exit `7`, Bundle erfolgreich: PatchHarbor Exit `7`.
- Entrypoint Exit `7`, Bundle ebenfalls fehlgeschlagen: PatchHarbor Exit `7`, Bundle-Fehler zusätzlich dokumentiert.
- Timeout plus Bundle-Fehler: PatchHarbor Exit `124`.
- Strg+C plus Bundle-Fehler: PatchHarbor Exit `130`.

### 18.2 Priorität des primären Ergebnisses

1. Benutzerabbruch: `130`.
2. Timeout: `124`.
3. normal beendeter Entrypoint: dessen exakter Exit-Code.
4. Tool-Fehler vor Entrypoint-Start: zugehöriger Tool-Exit-Code.
5. interner PatchHarbor-Fehler während der Prozesssteuerung: zugehöriger Tool-Exit-Code.

### 18.3 Strukturierter Run-Bericht

Jeder Auftrag besitzt eine UUID-v4-`run_id`.

Soweit ein Result Bundle erzeugt werden kann, liegt der Bericht unter:

```text
logs/run.json
```

Beispiel:

```json
{
  "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
  "operation": "apply",
  "dry_run": false,
  "repository_resolved": true,
  "primary_result": {
    "kind": "entrypoint_exit",
    "success": false,
    "patchharbor_error_code": null,
    "entrypoint_started": true,
    "entrypoint_exit_code": 7,
    "timed_out": false,
    "interrupted": false
  },
  "result_bundle": {
    "attempted": true,
    "status": "created",
    "error": null
  },
  "process_exit_code": 7
}
```

Mögliche `primary_result.kind`-Werte:

```text
success
dry_run_success
validation_error
repository_error
state_mismatch
repository_busy
entrypoint_exit
timeout
interrupted
execution_error
```

Mögliche `result_bundle.status`-Werte:

```text
created
failed
not_attempted
```

`not_attempted` ist nur zulässig, wenn kein Repository sicher aufgelöst werden konnte.

### 18.4 Maschinenlesbare Apply-Ausgabe

```bash
patchharbor apply --json PATCH_ZIP
```

Die Ausgabe folgt exakt dem gemeinsamen Vertrag aus Abschnitt 5.2.

Insbesondere:

- enthält stdout genau ein Abschlussobjekt,
- enthält `result.primary_result` die primäre Ergebnisart und den Entrypoint-Zustand,
- enthält `result.result_bundle` Versuch, Status, Pfad und gegebenenfalls Notfalldiagnose,
- bleibt `error` bei einem normalen von null verschiedenen Entrypoint-Exit `null`,
- enthält `error` bei einem PatchHarbor-Tool-Fehler den zugehörigen Tool-Code,
- entspricht `process_exit_code` exakt dem tatsächlich zurückgegebenen Exit-Code.

`logs/run.json` ist der ausführliche persistierte Bericht. Das stdout-Abschlussobjekt ist die kompakte maschinenlesbare Aufrufantwort und darf nicht aus TUI-Text rekonstruiert werden.

### 18.5 Atomare Bundle-Veröffentlichung und Notfallrettung

Für jeden Auftrag entsteht ein privates temporäres Run-Verzeichnis:

```text
<system-temp>/patchharbor-<run_id>/
├── execution.log
└── run.json
```

Die temporäre ZIP-Datei des Result Bundles wird ausdrücklich nicht im System-Temp-Verzeichnis erzeugt. Sie wird unter einem nicht endgültigen Namen direkt im kanonischen endgültigen Result-Ordner angelegt, beispielsweise:

```text
<result-dir>/.patchharbor_result_<timestamp>_<run-id>.tmp
```

Verbindlicher Veröffentlichungsablauf:

1. Result-Ordner vor der ersten Repository-Änderung validieren und anlegen.
2. Temporäre ZIP-Datei im endgültigen Result-Ordner exklusiv erzeugen.
3. Bundle vollständig schreiben und schließen.
4. ZIP-Struktur, Pflichtdateien und CRCs erneut prüfen.
5. Temporäre Datei und erforderliche Verzeichnismetadaten best effort synchronisieren.
6. Über `os.replace()` beziehungsweise eine äquivalente dateisystemgleiche Operation auf den endgültigen Namen austauschen.

Weil temporäre und endgültige Datei im selben Verzeichnis liegen, ist kein dateisystemübergreifender Rename erforderlich.

Bei erfolgreicher Veröffentlichung wird das private Run-Verzeichnis entfernt.

Bei fehlgeschlagener Bundle-Erzeugung:

- wird die temporäre ZIP-Datei best effort entfernt,
- bleibt keine unvollständige Datei unter dem endgültigen Bundle-Namen liegen,
- werden `execution.log` und `run.json` best effort im Notfallverzeichnis erhalten,
- wird der Notfallpfad deutlich auf stderr und im strukturierten Abschlussobjekt ausgegeben,
- entsteht daraus keine dauerhafte automatische Logverwaltung.

Kann selbst die Notfallrettung wegen desselben Systemfehlers nicht geschrieben werden, meldet PatchHarbor dies auf stderr und behält den nach der Prioritätsregel bestimmten Exit-Code.

### 18.6 Manueller Bundle-Auftrag

Für:

```bash
patchharbor bundle [REPOSITORY]
```

ist die Bundle-Erzeugung selbst der primäre Auftrag.

- erfolgreich: Exit `0`,
- fehlgeschlagen: Exit `11`.

Es wird kein erfundener Entrypoint-Log erzeugt. `execution_present` ist `false`; `logs/` enthält mindestens `run.json`.

---

## 19. PatchHarbor Result Bundle

### 19.1 Zweck

Das PatchHarbor Result Bundle ist die vollständige portable Darstellung des aktuellen lokalen Repository-Zustands ohne `.git`-Historie.

Es dient:

- dem Upload in einen Chat,
- der Erzeugung des nächsten Patches,
- der Diagnose eines erfolgreichen oder fehlgeschlagenen Auftrags,
- der Übergabe an Repo Assist,
- der unabhängigen Betrachtung des Repository-Zustands.

Ein bloßer Commit-Hash reicht nicht aus, weil der Empfänger den Commit möglicherweise nicht besitzt.

### 19.2 Automatische und manuelle Erzeugung

Manuell:

```bash
patchharbor bundle [REPOSITORY]
```

Automatisch versucht `patchharbor apply` nach jedem Auftrag ein Result Bundle zu erzeugen, sobald das Ziel-Repository sicher aufgelöst und gesperrt wurde.

Das gilt auch bei:

- Base-Commit-Mismatch,
- Fingerprint-Mismatch,
- ungültigem Entrypoint nach sicherer Auflösung,
- Entrypoint-Fehler,
- Timeout,
- Strg+C,
- internem Fehler nach sicherer Auflösung.

### 19.3 Vollständigkeitsregel

Das Result Bundle enthält immer:

- den vollständigen aktuellen Base-Commit als Dateien,
- staged Änderungen,
- unstaged Änderungen,
- alle nicht ignorierten untracked regulären Dateien,
- Repository-Kontext und Fingerprint,
- Run-Metadaten,
- vollständigen Entrypoint-Output, sofern eine Ausführung stattgefunden hat,
- Warnings und Tool-Fehler.

Es gibt keinen reduzierten Standardmodus, der nur den Commit-Hash enthält.

### 19.4 Struktur

```text
patchharbor_result_<timestamp>_<run-id>.zip
├── manifest.json
├── context.json
├── base/
│   └── ... alle regulären Dateien des aktuellen Base-Commits ...
├── changes/
│   ├── staged.patch
│   └── unstaged.patch
├── untracked/
│   └── ... nicht ignorierte untracked reguläre Dateien ...
└── logs/
    ├── execution.log
    └── run.json
```

`execution.log` fehlt bei einem manuellen Bundle oder Dry-Run ohne Entrypoint-Ausführung.

### 19.5 `manifest.json`

Verkürztes Beispiel:

```json
{
  "marker": "patch-harbor-result-bundle",
  "format_version": 1,
  "created_at": "2026-08-04T06:00:00Z",
  "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
  "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
  "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
  "state_fingerprint": "a1b2c3d4e5f67890",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "dirty": true,
  "dry_run": false,
  "execution_present": true,
  "primary_result": "entrypoint_exit",
  "result_bundle_status": "created"
}
```

Das vollständige Manifest enthält zusätzlich zwei nach UTF-8-Pfadbytes sortierte Arrays:

- `base_entries` mit `path`, `git_mode`, `object_id` und `size`,
- `untracked_entries` mit `path`, `mode`, `size` und `sha256`.

Diese Metadaten sind die plattformunabhängige Quelle für Dateimodi. Die ZIP-Einträge tragen zusätzlich passende reguläre Dateirechte, soweit das ZIP-Format sie abbilden kann.

Bei `apply` enthält das Manifest außerdem die aus `patch.json` erwarteten und die tatsächlich ermittelten Zustandswerte, sodass ein Mismatch eindeutig nachvollziehbar bleibt.

### 19.6 `context.json`

`context.json` enthält den aktuellen Zustand zum Zeitpunkt der konsistenten Snapshot-Aufnahme:

```json
{
  "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
  "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
  "dirty": true,
  "state_fingerprint": "a1b2c3d4e5f67890",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "created_at": "2026-08-04T06:00:00Z"
}
```

### 19.7 `base/`

`base/` wird unabhängig von Exportattributen direkt aus dem unveränderlichen Git-Baum materialisiert.

Verbindliches Verfahren:

```text
git ls-tree -r -z --full-tree <base_commit>
git cat-file --batch
```

PatchHarbor:

1. liest alle Baumdatensätze als Bytes,
2. akzeptiert ausschließlich reguläre Blob-Einträge mit Modus `100644` oder `100755`,
3. fordert die vollständigen Blob-Inhalte über `git cat-file --batch` an,
4. prüft zurückgegebenen Objekttyp und Größe,
5. schreibt exakt diese unveränderten Blob-Bytes unter `base/<repository-path>`,
6. dokumentiert Pfad, Modus, Objekt-ID und Größe in `manifest.json`.

Dieses Verfahren wertet insbesondere keine Exportattribute oder Ersetzungsanweisungen aus. Eine committed Datei wird nicht aufgrund einer Exportregel ausgelassen oder inhaltlich verändert.

Enthalten sind alle unterstützten, im Base-Commit verwalteten regulären Dateien.

Nicht enthalten sind:

- `.git`,
- frühere Commits,
- Branch- und Tag-Historie,
- lokale Git-Konfiguration,
- das reservierte lokale PatchHarbor-Verzeichnis.

Externe Git-LFS-Objekte werden nicht nachgeladen. Das Bundle enthält den tatsächlich im Git-Commit gespeicherten Blob, beispielsweise gegebenenfalls eine LFS-Zeigerdatei.

### 19.8 `changes/staged.patch`

Die staged Patch-Datei wird unter derselben kontrollierten Git-Umgebung wie der Fingerprint erzeugt:

```bash
git -c color.ui=false -c diff.renames=false diff \
  --cached --binary --full-index --no-renames \
  --no-ext-diff --no-textconv --no-color \
  <base_commit> --
```

Zusätzlich gelten `LC_ALL=C`, `LANG=C`, `GIT_OPTIONAL_LOCKS=0` und ein deaktiviertes externes Diff-Programm.

Die Datei beschreibt die staged Änderungen gegenüber dem festgehaltenen Base-Commit einschließlich binärer Änderungen und Modusänderungen.

### 19.9 `changes/unstaged.patch`

Die unstaged Patch-Datei wird ebenfalls unter der kontrollierten Git-Umgebung erzeugt:

```bash
git -c color.ui=false -c diff.renames=false diff \
  --binary --full-index --no-renames \
  --no-ext-diff --no-textconv --no-color --
```

Die Datei beschreibt die unstaged Änderungen zwischen Index und Working Tree.

Zur Rekonstruktion wird zuerst `staged.patch` und anschließend `unstaged.patch` auf `base/` angewendet.

Die Patch-Dateien dienen der Rekonstruktion und Ansicht. Der Sicherheits-Fingerprint wird ausschließlich nach Abschnitt 14 berechnet.

### 19.10 `untracked/`

`untracked/` enthält alle nicht ignorierten untracked regulären Dateien:

- vollständiger UTF-8-Repository-Pfad,
- vollständiger bytegenauer Inhalt,
- erhaltene Verzeichnisstruktur,
- kanonischer Modus `100644` oder `100755` gemäß Abschnitt 14,
- SHA-256 des Inhalts im Manifest.

Ignorierte Dateien werden nicht aufgenommen. Nicht reguläre Einträge werden nicht dereferenziert und führen zu einem klaren Fehler.

### 19.11 Vollständiger aktueller Snapshot

Die Kombination:

```text
base/
+ changes/staged.patch
+ changes/unstaged.patch
+ untracked/
```

ist der vollständige aktuelle Snapshot innerhalb der definierten Git- und Dateigrenzen.

Ein zweites materialisiertes `snapshot/`-Verzeichnis ist nicht erforderlich und würde dieselben Daten unnötig verdoppeln.

### 19.12 Logs

`logs/execution.log` enthält den vollständigen während der Ausführung beobachteten stdout-/stderr-Strom.

`logs/run.json` enthält mindestens:

- Startzeit,
- Endzeit,
- Laufzeit,
- Operation,
- Patch-Paket-Anzeigename,
- Repository-ID und Pfad,
- erwartete und tatsächliche Zustandswerte,
- Dry-Run-Status,
- Entrypoint,
- Interpreter,
- Timeout,
- Warnings,
- Entrypoint-Exit-Code,
- Tool-Fehler,
- Result-Bundle-Status,
- endgültigen Prozess-Exit-Code.

Zusätzliche Diagnose-, Test- oder Build-Dateien des Zielprojekts werden nicht automatisch gesucht oder eingesammelt. Sie können manuell übertragen oder durch Repo Assist verwaltet werden.

### 19.13 Datenschutz und Secrets

Ein Result Bundle kann vollständigen Quellcode und nicht ignorierte untracked Dateien enthalten.

PatchHarbor:

- nimmt `.git` nicht auf,
- nimmt standardmäßig ignorierte Dateien nicht auf,
- schreibt bekannte sensible Umgebungswerte nicht unkontrolliert in strukturierte Logs,
- weist im Help-Screen klar auf den vollständigen Snapshot-Inhalt hin.

Eine allgemeine automatische Secret-Erkennung ist nicht Bestandteil von 1.1.0.

---

## 20. Exit-Codes

Wenn ein Entrypoint oder manuelles Skript gestartet wurde, bestimmt grundsätzlich dessen Exit-Code das primäre Ergebnis. PatchHarbor-Tool-Fehler müssen in der sichtbaren und strukturierten Ausgabe klar von Skript-Exit-Codes unterscheidbar sein.

| Code | Bedeutung |
|---:|---|
| `2` | ungültige CLI-Verwendung oder fehlende Eingabe |
| `3` | kein gültiges PatchHarbor-Skript beziehungsweise kein gültiger Entrypoint |
| `4` | Eingabe oder ZIP nicht lesbar, unsicher oder Ressourcenbudget überschritten |
| `5` | Interpreter fehlt oder kann nicht gestartet werden |
| `6` | sichere Bereitstellung einer Nutzdatei fehlgeschlagen |
| `7` | sonstiger interner Ausführungsfehler vor Prozessstart |
| `8` | Repository nicht registriert, nicht mehr gültig oder Registrierung mehrdeutig |
| `9` | Base-Commit, Fingerprint oder Fingerprint-Algorithmus stimmt nicht überein |
| `10` | `patch.json` oder Paketformat ungültig |
| `11` | Result Bundle ist der primäre oder einzige fehlgeschlagene Auftrag |
| `12` | Repository ist bereits exklusiv gesperrt |
| `13` | Repository-Zustand wird im sicheren 1.1.0-Pfad nicht unterstützt |
| `124` | Timeout |
| `130` | Abbruch durch Strg+C |

Bei mehreren Skripten im manuellen ZIP-PatchBundle gilt:

- alle erfolgreich: Exit-Code des letzten Skripts, normalerweise 0,
- erstes fehlerhaftes Skript: dessen Exit-Code,
- spätere Skripte werden nicht gestartet.

Da ein Skript dieselben numerischen Werte zurückgeben kann, nennt `run.json` immer getrennt:

- `entrypoint_exit_code`,
- `patchharbor_error_code`,
- `process_exit_code`.

---

## 21. Architektur und Modulgrenzen

Das Python-Paket bleibt so flach wie sinnvoll.

Empfohlene Verantwortlichkeiten:

- `cli.py` – argparse und öffentliche Befehle,
- `application.py` – Orchestrierung genau eines Auftrags,
- `sources.py` – Datei, Ordner und STDIN als neutrales `InputArtifact`,
- `bundles.py` – manuelle direkte Skripte und ZIP-Container zu `PatchBundle`s auflösen,
- `bundle_paths.py` – gemeinsame sichere ZIP-Pfadregeln,
- `payload_files.py` – sichere ZIP-Nutzdateien und atomisches Schreiben,
- `parser.py` – Pflichtmarker, META und MESSAGE,
- `resource_policy.py` – unveränderliche Ressourcenbudgets,
- `interpreters.py` – Interpreter-Whitelist und feste Prozessargumente,
- `execution.py` – temporäre Skriptdatei, Prozessstart, Timeout und Ergebnis,
- `run_log.py` – vollständiger Run-Log und strukturierter Run-Bericht,
- `presentation.py` – Plain-Ausgabe, TUI, Farben und Rolling Buffer,
- `registry.py` – zentrale Repository-Registrierung,
- `repository_state.py` – Base-Commit, kanonischer Fingerprint und Snapshot-Zustand,
- `repository_lock.py` – exklusive Sperre pro Repository-ID,
- `patch_manifest.py` – `patch.json` und Schema,
- `result_bundle.py` – vollständiges Result Bundle und atomare Veröffentlichung,
- `models.py` – kleine unveränderliche Datenträger,
- `errors.py` – Tool-Fehler und Exit-Codes,
- `platform/` – notwendige Linux- und Windows-Grenzen,
- separater Watcher-Einstiegspunkt – Ordnerbeobachtung und Aufruf der öffentlichen Core-Schnittstelle.

Abhängigkeitsregeln:

- `cli` komponiert ausschließlich öffentliche Anwendungsgrenzen.
- `application` ist der einzige fachliche Orchestrator eines Auftrags.
- `sources` kennt weder ZIP-Regeln noch Parser, Git oder Execution.
- `bundles` klassifiziert und beschreibt Inhalte, schreibt aber keine Nutzdateien.
- `parser` ist rein und kennt keine Dateischreib- oder Prozesslogik.
- `payload_files` schreibt Dateien, steuert aber keine Execution.
- `patch_manifest` kennt weder Git noch Execution.
- `registry` kennt weder TUI noch ZIP-Inhalte.
- `repository_state` kennt weder TUI noch Watcher.
- `repository_lock` kennt keine Ausführungs- oder Bundle-Semantik.
- `interpreters` kennt nur den kleinen Interpretervertrag.
- `execution` kennt weder Registry, Git-Zustand, Result-Bundle-Struktur noch TUI.
- `result_bundle` verwendet Repository-State- und Run-Log-Daten, führt aber keinen Patch aus.
- `presentation` steuert keine fachliche Logik.
- Der Watcher kennt nur die öffentliche PatchHarbor-Aufrufsgrenze.
- Repo Assist und PromptBridge sind keine internen Module.
- Es gibt keine Sammelpakete namens `utils`, `helpers` oder `common`.
- Es gibt keine Plugin-Registry und keine asynchrone Kernarchitektur.

---

## 22. Teststrategie und Freigabe

### 22.1 Grundsatz

PatchHarbor wird pragmatisch verhaltensorientiert entwickelt.

- Schwerpunkt auf End-to-End- und Integrationstests,
- wenige gezielte Unit-Tests für isolierte kritische Logik,
- echte Dateien, echte Git-Repositories und echte Prozesse,
- Verhalten statt interner Implementierungsdetails,
- keine dogmatische Forderung nach vollständiger Testabdeckung,
- jeder Testlauf besitzt einen äußeren Timeout.

### 22.2 Beizubehaltende 1.0.0-Verträge

Mindestens zu erhalten und weiter zu testen sind:

- direkter Datei-Run,
- exakter Pflichtmarker,
- META- und MESSAGE-Warnings,
- STDIN und Pipe mit direktem Skript,
- STDIN und Pipe mit binärem ZIP-PatchBundle,
- einmaliger nicht rekursiver Ordnerscan und Auswahl,
- mehrere ZIP-Skripte in Archiv-Reihenfolge,
- Binärdateien einschließlich Nullbytes,
- bytegenaue Erhaltung von Nutzdateien,
- Nutzdateien vor dem ersten Skript verfügbar,
- markerlose Shell- oder PowerShell-Dateien werden nicht automatisch ausgeführt,
- enthaltenes Archiv wird nicht rekursiv geöffnet,
- reines Datei-ZIP ohne Skript wird im manuellen Pfad abgelehnt,
- unsichere, besondere, doppelte oder mehrdeutige ZIP-Einträge,
- tatsächlicher Schreibfehler verhindert Ausführung,
- Abbruch beim ersten fehlerhaften Skript,
- Exit-Code des letzten ausgeführten Skripts,
- atomisches Überschreiben,
- Timeout pro Skript,
- Strg+C und vollständiger Prozessbaum,
- fehlender Interpreter,
- viel Output und Rolling Buffer zehn beziehungsweise Anzeige fünf,
- sehr lange Zeile und letzte Zeile ohne Zeilenumbruch,
- ANSI-Ausgabe zerstört die TUI nicht,
- schneller Prozess zeigt finalen Zustand,
- Plain-Modus ohne Cursorsequenzen,
- temporäre Logdatei bei `--log`,
- ursprüngliches Arbeitsverzeichnis,
- Ressourcenlimits und ZIP-Bomben-Schutz,
- Wheel- und pipx-Installation.

### 22.3 Neue Pflichtszenarien für 1.1.0

- Registrierung und UUID-v4-Format,
- globaler Registry-Lock und atomarer Registry-Austausch,
- vollständiges lokales Exclude von `.patchharbor/`,
- Ablehnung einer getrackten oder besonderen `.patchharbor`-Struktur,
- zwei Klone desselben Remotes erhalten verschiedene IDs,
- idempotente Registrierung,
- verlorene ID entfernt alte Pfadzuordnungen vor der Neuregistrierung,
- `registry list`, `unregister` und `register --new-id`,
- verschobener Pfad bei nicht mehr vorhandenem Altpfad,
- kopierte ID wird abgelehnt,
- partielle Registry-Aktualisierung wird zurückgerollt oder als Inkonsistenz gemeldet,
- Kontextausgabe für clean und dirty unter Repository-Lock,
- vier feste Encoder-Testvektoren für `patchharbor-state-v1`, darunter staged und unstaged,
- exakte ASCII-, UTF-8-, Objekt-ID-, Status-, Inhalts-, Zähler- und Größen-Payloadcodierung,
- staged Hinzufügung, Änderung, Löschung und Modusänderung,
- unstaged Änderung und Löschung regulärer Dateien,
- untracked Pfad, Modus und vollständiger Inhalt,
- Binärdatei im Fingerprint,
- Base-Commit ist nicht Teil des Fingerprints,
- nicht aufgelöster Index wird klar abgelehnt,
- Assume-Unchanged und Skip-Worktree werden klar abgelehnt,
- Intent-to-add wird klar abgelehnt,
- Sparse-Checkout und Sparse-Index werden klar abgelehnt,
- Submodule und getrackte Symlinks werden klar abgelehnt,
- nicht reguläre Working-Tree- und untracked Einträge werden klar abgelehnt,
- nicht als UTF-8 darstellbare Repository-Pfade werden klar abgelehnt,
- Windows-reservierte, steuerzeichenhaltige, mit Punkt oder Leerzeichen endende und anderweitig nicht portable Repository-Pfade werden klar abgelehnt,
- Groß-/Kleinschreibungs-Kollisionen werden über den festgelegten `casefold()`-Vergleichsschlüssel abgelehnt,
- verbotene `.git`- und `.patchharbor`-Segmente werden in Base-Baum und Index ohne Beachtung der Groß-/Kleinschreibung erkannt,
- `core.fileMode` bestimmt den kanonischen Modus eindeutig,
- Kontextänderung führt zur Ablehnung,
- eine Zustandsänderung zwischen erster Prüfung und unmittelbar vor der ersten Repository-Schreiboperation führt ohne Repository-Schreibzugriff zur Ablehnung,
- genau eine Root-`patch.json` bei weiteren erlaubten Paketdateien,
- ungültiger Paketmarker, Algorithmus oder Formatversion,
- striktes `patch.json`-Schema mit verbotenen unbekannten Feldern, kanonischer UUID, vollständiger Objekt-ID und exakt 16-stelligem Fingerprint,
- unbekannte Repository-ID,
- Base-Commit- und Fingerprint-Mismatch,
- `.git` und `.patchharbor` in jedem Eingabepfadsegment werden abgelehnt,
- Entrypoint bleibt temporär und CWD ist das Ziel-Repository,
- Entrypoint-Marker und Interpreter werden vor der ersten Repository-Änderung geprüft,
- nur der manifestierte Entrypoint wird automatisch ausgeführt,
- Dry-Run schreibt und startet nichts,
- exklusive Sperre verhindert parallele Aufträge,
- feste Lock-Reihenfolge verhindert Deadlocks zwischen Registry und Repository,
- äußerer Zustandswechsel während Snapshot-Erzeugung verwirft das Bundle,
- Result-Ordner innerhalb irgendeines registrierten Repositorys wird abgelehnt,
- temporäre und endgültige Bundle-Datei liegen im selben Result-Ordner,
- dateisystemgleiche atomare Veröffentlichung über `os.replace()`,
- vollständiges Result Bundle ohne `.git`,
- Base-Commit wird vollständig über Baumabfrage und Blob-Lesen materialisiert,
- Exportattribute dürfen keine committed Datei auslassen oder verändern,
- Base-Dateimodi und Objekt-IDs stehen im Manifest,
- staged und unstaged Patch werden unter kontrollierter Git-Umgebung erzeugt,
- untracked Dateien werden bytegenau samt Modus und Inhalts-Hash aufgenommen,
- vollständiger Run-Log,
- automatische Bundle-Erzeugung nach sicherer Repository-Auflösung,
- Fehlerpriorität bei primärem Fehler plus Bundle-Fehler,
- Exit `11` bei ausschließlich fehlgeschlagener Bundle-Erzeugung,
- Notfallrettung ohne halbfertige endgültige ZIP-Datei,
- JSON-Modus mit genau einem Objekt auf stdout,
- exakte JSON-Verträge für `registry list`, `context`, `bundle` und `apply` einschließlich Fehlerobjekten,
- temporäre STDIN-Artefakte werden über den zentralen Cleanup-Pfad entfernt,
- Watcher delegiert ohne duplizierte Core-Logik,
- Watcher-Eingangsordner außerhalb aller registrierten Repositories und ohne Überlappung mit Result-Ordnern,
- Repo Assist und Watcher werden nicht gleichzeitig für dieselben Repositories aktiviert.

### 22.4 Release-Audit

Der Release-Audit prüft mindestens die Existenz und Konsistenz von:

```text
spec/SPECIFICATION.md
spec/SPECIFICATION_CHANGELOG.md
planning/1.0.0/commit-plan.md
planning/1.1.0/commit-plan-cleanup.md
```

Der erste 1.1.0-Dokumentationscommit aktualisiert den Audit-Test auf diese Struktur, ohne Produktionscode zu verändern.

### 22.5 Freigaberegel

- Jeder Implementierungscommit hat eine erkennbare Absicht.
- Feature und zugehöriger Verhaltenstest gehören zusammen.
- Nach jedem Commit ist die bis dahin geltende Testsuite mit harten Timeouts grün.
- Bei fehlgeschlagenen Tests entsteht kein Commit.
- Plattform- und Akzeptanztests werden vor Release vollständig ausgeführt.
- Ubuntu 24.04, Ubuntu 26.04 und der echte Windows-Runner sind blockierende Release-Gates; eine rote verbindliche Lane verhindert die Freigabe.

---

## 23. Bewusst ausgeschlossene Funktionen

Folgende Funktionen gehören nicht zu PatchHarbor 1.1.0:

- Netzwerk- oder Chatquelle im Core,
- Clipboard- oder SSH-Quelle,
- öffentliches Plugin-System,
- Save-Modus mit chmod,
- Zielprojekt-Testmanagement,
- Git-Commit-, Branch-, Tag- oder Release-Management,
- interaktive Kindskripte,
- aus Skriptkommentaren erzeugte Nutzdateien,
- automatische Dekodierung textuell transportierter Binärdaten,
- rekursive Ordnersuche,
- rekursive Auflösung enthaltener Archive,
- universelle Pakettransaktion und automatische globale Rückabwicklung,
- dauerhafte Logverwaltung und Logrotation im Core,
- automatisches Einsammeln beliebiger zusätzlicher Diagnoseartefakte,
- Netzwerk-, Chat-, Upload- oder Downloadlogik im Core,
- Submodule im sicheren 1.1.0-Kontext und Result Bundle.

Tests, Commits und Journal gehören zu Repo Assist. Dauerhafte Ordnerüberwachung gehört zum separaten PatchHarbor Watcher. Chat- und Transportfunktionen gehören zu PromptBridge.

---

## 24. Unterschiedliche Bundle-Arten

### 24.1 PatchHarbor Result Bundle

Beantwortet:

> Wie sieht die konkrete lokale Repository-Instanz technisch jetzt aus, und was hat der PatchHarbor-Auftrag ausgegeben?

Es enthält Snapshot, Kontext, Fingerprint und PatchHarbor-Run-Logs.

### 24.2 Repo-Assist-Journal-Bundle

Beantwortet:

> Welche Aufgabe und welcher Entwicklungsworkflow wurden durchgeführt, warum wurden Entscheidungen getroffen, und welches Gesamtergebnis entstand?

Es kann enthalten:

- Aufgabe,
- Prompts,
- Patch-Pakete,
- Testergebnisse,
- Commit-Ergebnis,
- Retry- und Abort-Informationen,
- Journal,
- ein eingebettetes oder referenziertes PatchHarbor Result Bundle.

Repo Assist dupliziert nicht die technische Snapshot-Logik von PatchHarbor.

---

## 25. Migration von 1.0.0 auf 1.1.0

### 25.1 Erster Commit

Der erste 1.1.0-Commit ist ein Spezifikations-, Changelog- und Dokumentstruktur-Audit-Commit ohne Produktionscodeänderung.

Er:

- trennt Produktspezifikation und Commit-Plan,
- setzt das vollständige Produktziel auf 1.1.0,
- übernimmt alle fortgeltenden 1.0.0-Verträge,
- ergänzt Registry, Kontext, Fingerprint, Apply, Dry-Run, Lock und Result Bundle,
- aktualisiert den Release-Audit-Test auf die neue Dokumentstruktur,
- befüllt `SPECIFICATION_CHANGELOG.md`.

### 25.2 Allererstes Code-Cleanup-TODO

Als allererste Produktionscodeänderung wird der alte zweite Dateiübertragungsweg vollständig entfernt.

Betroffen sind insbesondere:

- dessen Parser und Datenmodelle,
- dessen Verarbeitung in der Anwendungsorchestrierung,
- dessen Darstellung,
- dessen Unit-, End-to-End- und Sicherheitstests,
- dessen Dokumentation.

`payload_files.py` wird nicht pauschal gelöscht. Das Modul oder seine Nachfolge bleibt für sichere ZIP-Nutzdateien und atomisches Schreiben erforderlich. Entfernt wird ausschließlich der nicht mehr vorgesehene Inline-Pfad.

Es existiert im aktuellen Stand kein automatischer Decoder für textuell codierte Binärdaten. Daher ist kein Decoder zu entfernen; alte Tests und Aussagen zu diesem früher vorgesehenen Transportweg werden entfernt oder auf den alleinigen ZIP-Nutzdateivertrag umgestellt.

### 25.3 Danach folgende Zielblöcke

1. Registry-Minimum und UUID,
2. kanonischer Kontext und Fingerprint,
3. `patch.json` und sicherer Apply-Pfad,
4. Repository-Lock,
5. Dry-Run,
6. vollständiger Run-Bericht und Fehlerpriorität,
7. vollständiges Result Bundle,
8. separater PatchHarbor Watcher,
9. Integrationsgrenzen zu Repo Assist und PromptBridge,
10. vollständige Regression-, Plattform- und Release-Prüfung.

---

## 26. Zusammenfassung der verbindlichen Entscheidungen

- PatchHarbor Core ist ein kontrollierter Runner ohne Hintergrunddienst, Netzwerk oder Betriebsmodi.
- Der PatchHarbor Watcher ist eine separate dünne systemd-fähige Komponente.
- Watcher-Eingangsordner liegen außerhalb registrierter Repositories und überlappen keine Result-Ordner.
- Repo Assist ist der Workflow-Orchestrator für Tests, Commits und Journal.
- PromptBridge besitzt Chat- und Transportfunktionen.
- Jede lokale Repository-Instanz erhält eine eigene UUID v4.
- Die UUID liegt lokal im vollständig reservierten Verzeichnis `.patchharbor/` und wird nicht committet.
- Registry-Minimum: `register`, `register --new-id`, `registry list`, `unregister`.
- Registry-Mutationen sind global gesperrt und werden atomar veröffentlicht.
- Registry- und Repository-Locks besitzen eine feste Lock-Reihenfolge.
- `patchharbor context` liefert Base-Commit und 16-stelligen Fingerprint unter Repository-Lock.
- Der Fingerprint-Algorithmus ist normativ als `patchharbor-state-v1` definiert.
- Jede Fingerprint-Payload besitzt eine exakt festgelegte Bytecodierung; vier Referenzvektoren decken clean, untracked, staged und unstaged ab.
- Base-Commit und Fingerprint werden getrennt geprüft.
- Der Fingerprint umfasst staged, unstaged und untracked Pfad, Modus und vollständigen Inhalt.
- Nicht eindeutige Git-Sonderzustände, getrackte Symlinks, Submodule und nicht als UTF-8 darstellbare Pfade werden im sicheren Pfad abgelehnt.
- Nicht portable Repository-Pfade, Windows-Gerätenamen, Groß-/Kleinschreibungs-Kollisionen sowie verbotene interne Segmente in Base-Baum oder Index werden abgelehnt.
- Das sichere Patch-Paket ist ZIP-basiert und enthält genau eine Root-`patch.json` sowie weitere sichere Paketdateien.
- Der Entrypoint wird privat temporär bereitgestellt und mit dem Repository als CWD ausgeführt.
- Entrypoint-Marker und Interpreter werden vor der ersten Repository-Änderung geprüft.
- Paketpfade mit `.git` oder `.patchharbor` als Segment sind verboten.
- Pro Repository-ID gilt eine exklusive Sperre.
- Bei jeder Zustandsabweichung wird hart abgelehnt.
- Base-Commit und Fingerprint werden unmittelbar vor der ersten Repository-Schreiboperation ein zweites Mal geprüft.
- Dry-Run validiert vollständig, schreibt und startet aber nichts.
- Primäres Auftragsergebnis und Result-Bundle-Ergebnis bleiben getrennt.
- Alle öffentlichen `--json`-Befehle besitzen einen vollständigen versionierten und strikten Abschlussvertrag.
- Ein Bundle-Fehler überschreibt nur einen ansonsten erfolgreichen Auftrag und liefert dann Exit `11`.
- Result-Ordner dürfen nicht innerhalb registrierter Repositories liegen.
- Temporäre Result-ZIP und endgültige Result-ZIP liegen im selben Ausgabeordner und werden dateisystemgleich atomar ausgetauscht.
- Ein Result Bundle enthält immer Base-Commit-Dateien, staged Patch, unstaged Patch, untracked Dateien, Kontext und Run-Logs.
- Der Base-Commit wird direkt aus Git-Baum und Git-Blobs materialisiert; Exportattribute verändern den Snapshot nicht.
- Das Manifest dokumentiert Base- und untracked Dateimodi plattformunabhängig.
- Das Result Bundle enthält keine Git-Historie.
- Der fortgeführte manuelle Runner behält Datei, Ordner, Pipe, mehrere ZIP-Skripte, Interpreter-, Prozess-, TUI-, Logging- und Ressourcenverträge aus 1.0.0.
- Temporäre Eingabe- und Skriptdateien werden über einen gemeinsamen Cleanup-Pfad entfernt.
- PatchHarbor verwaltet keine Zielprojekt-Tests und keine Commits.
- PatchHarbor ist keine Sandbox; nur vertrauenswürdige Pakete dürfen ausgeführt werden.
- Ubuntu 24.04, Ubuntu 26.04 und der echte Windows-Runner sind blockierende Release-Gates.
