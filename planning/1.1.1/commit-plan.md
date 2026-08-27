# PatchHarbor 1.1.1 – Konsolidierter Commit-Plan

**Ziel:** Gemeinsamen Exchange-Ordner und eine verbindliche Chat-Initialisierung auf der vollständig implementierten 1.1.0-Basis liefern.

**Vorgesehener Repository-Pfad:** `planning/1.1.1/commit-plan.md`<br>
**Vorbereitender Commit außerhalb des Zählers:** `docs: define PatchHarbor 1.1.1 implementation plan`<br>
**Plan-Konsolidierung außerhalb des Zählers:** `docs(plan): consolidate PatchHarbor 1.1.1 implementation plan` (`OFF-PLAN` `PLAN12`)<br>
**Planstatus:** 6 / 12 Plan-Commits umgesetzt; nächster Plan-Commit: `3.a.W`; 6 Plan-Commits offen.<br>
**Umfang:** 5 Meilensteine, 12 fachlich eigenständige Plan-Commits.

---

## 1. Anlass und unverändertes Produktziel

Der ursprüngliche 1.1.1-Plan zerlegte 11 Steps mechanisch in jeweils drei W-R-C-Commits und kam dadurch auf 33 Plan-Commits. Diese Zerlegung war für den begrenzten Funktionsumfang von 1.1.1 unnötig kleinteilig.

Die Konsolidierung reduziert den Plan auf 12 fachlich sinnvolle Commits. Sie entfernt keine Produktfunktion und verändert keinen fachlichen 1.1.1-Funktionsumfang. Zusätzlich präzisiert sie die bereits beschlossene Ausführungsregel für Christians Pixel: Ausgelieferte Termux-Commit-Skripte laufen ohne künstliche Einzeltest- oder Gesamtsuite-Timeouts, während produktinterne Timeout-Verträge sowie CI- und Release-Grenzen bestehen bleiben. Insbesondere bleiben vollständig erhalten:

- die allgemeine benutzerspezifische `config.json` mit `exchange_directory`,
- sichere Exchange-/Repository-Pfadgrenzen,
- der Exchange-Ordner als Standardziel für manuelle und automatische Result Bundles,
- `patchharbor apply` ohne Dateipfad mit eindeutiger zustandsgebundener Auswahl,
- persistente Dateidentität und definierte Wiederverarbeitungssemantik,
- die gemeinsame Konfigurations- und Erkennungslogik für Core und Watcher,
- `CHAT_INSTRUCTIONS.md` einschließlich Plan-/Spec-Prüfung, Tests, Commit-Arten, Warning, STOP und schmaler Smartphone-UI,
- README, CLI-Help, Akzeptanz, Packaging und Release 1.1.1.

Es gibt weiterhin keine produktiv zu migrierende 1.1.0-Konfiguration. Deshalb entstehen kein Leser und kein Fallback für alte `watcher.json`- oder `paths.json`-Verträge.

---

## 2. W-R-C als Werkzeug statt Pflichtschema

Die Kennungsbestandteile `W`, `R` und `C` behalten ihre Bedeutung:

- **W – Let it work:** einen kleinsten vertikalen, benutzbaren Durchlauf liefern,
- **R – Do it right:** Sicherheits-, Fehler-, Race-, Plattform- und Vertragsgrenzen härten,
- **C – Make it clean:** Doppelungen, Übergangsreste und unnötige Komplexität entfernen.

Sie werden jedoch nur eingesetzt, wenn daraus ein eigenständiger sinnvoller Commit entsteht. Es gibt ausdrücklich:

- keine leeren vorsorglichen Cleanup-Commits,
- keine künstliche Dreiteilung reiner Dokumentationsänderungen,
- keine Aufteilung, die nur die Commit-Zahl erhöht,
- keinen Commit, der ausschließlich bereits bekannte Arbeit erneut beschreibt.

Jeder Plan-Commit muss für sich verständlich, testbar und grün sein. Ein Commit darf mehrere eng zusammengehörige W-R-C-Aspekte bündeln, wenn dadurch eine klarere und kleinere Gesamtumsetzung entsteht.

---

## 3. Verbindliche Arbeits- und Auslieferungsregeln

Für jeden Plan-Commit gilt:

1. Der aktuelle Result-Bundle-Snapshot, dieser Plan, die zugehörigen Spezifikationsabschnitte und der reale Code werden vor der Umsetzung gegeneinander geprüft.
2. Die Spezifikation ist der fachliche Vertrag; der Plan ist die vorgesehene Zerlegung. Kleine eindeutig commitbezogene Lücken dürfen geschlossen werden. Scope-Erweiterungen, Widersprüche oder unlogische Vorgaben führen zu Warning beziehungsweise STOP nach Abschnitt 26 der Spezifikation.
3. Ein Patch enthält genau einen Plan-Commit, Fix oder ausdrücklich gekennzeichneten Off-Plan-Commit.
4. Ein Plan-Commit übernimmt Kennung und Commit-Message exakt aus diesem Dokument.
5. Passende Tests sind Bestandteil desselben Commits. Breite oder riskante Änderungen führen zusätzlich die vollständige Suite aus.
6. Auf Christians Pixel unter Termux laufen die ausgelieferten Commit-Skripte ohne künstliche Einzeltest- oder Gesamtsuite-Timeouts. Projektinterne Timeout-Verträge werden dadurch nicht verändert.
7. Ein roter Test oder ein anderer Ausführungsfehler erzeugt keinen Git-Commit. Das Patch-Skript setzt seine eigenen noch nicht veröffentlichten Änderungen auf den geprüften Ausgangsstand zurück.
8. Nach einem erfolgreichen Commit werden ein aktuelles PatchHarbor Result Bundle und das vollständige Patch-/Ausführungslog in `$HOME/Downloads` abgelegt. Bis `apply` ohne Pfad vollständig verfügbar ist, erledigt dies das ausgelieferte Bootstrap-Shellskript mit `patchharbor bundle --output-dir "$HOME/Downloads"`.
9. Ein späteres echtes PatchHarbor-Paket ruft `patchharbor bundle` nicht rekursiv aus seinem Entrypoint auf. `patchharbor apply` übernimmt den Result-Bundle-Versuch selbst.
10. PatchHarbor verschiebt, löscht, archiviert oder sortiert Dateien im Exchange-Ordner nicht. Diese spätere Ablage gehört zu Repo Assist.
11. Nach jedem erfolgreichen Plan-Commit werden die Statuszeile und die Fortschrittstabelle dieses Plans im selben Commit auf den neuen Stand gebracht. Dadurch kann auch ein neuer Chat den Planfortschritt aus dem Snapshot lesen.

Fixes verwenden `<PLAN-ID>-FIX<n>` und verändern den Plan-Zähler nicht. Off-Plan-Commits erhalten eine freie sinnvolle Kennung und verändern den Plan-Zähler ebenfalls nicht.

---

## 4. Aktueller Fortschritt

| Pos. | Kennung | Status | Commit-Message | Hauptergebnis |
|---:|---|---|---|---|
| 1 | `1.a.W` | DONE | `feat(config): add shared exchange directory configuration` | Gemeinsame `config.json` und Configure-CLI sind vertikal vorhanden. |
| 2 | `1.a.R` | DONE | `fix(config): harden exchange configuration persistence` | Schema, Lesen, Schreiben und Fehlervertrag sind gehärtet. |
| 3 | `1.b.W` | DONE | `feat(config): complete exchange repository boundaries` | Pfadpolitik und Konfigurationsgrenze sind vollständig abgeschlossen. |
| 4 | `2.a.W` | DONE | `feat(bundle): publish result bundles to the exchange directory` | Manuelle und automatische Bundles verwenden standardmäßig Exchange. |
| 5 | `2.b.W` | DONE | `feat(apply): discover one state-bound exchange patch` | `apply` findet ohne Pfad genau ein passendes Paket. |
| 6 | `2.b.R` | DONE | `fix(exchange): harden processing identity and retry semantics` | Wiederverarbeitung und Retry-Vertrag werden persistent und eindeutig. |
| 7 | `3.a.W` | NEXT | `feat(watcher): use shared exchange discovery` | Watcher verwendet dieselbe Core-Konfiguration und Erkennung. |
| 8 | `3.a.C` | OPEN | `refactor(watcher): remove legacy exchange configuration` | Doppelte Watcher-Konfiguration und Übergangslogik entfallen. |
| 9 | `4.a.W` | OPEN | `docs(chat): add the complete PatchHarbor chat contract` | Vollständige `CHAT_INSTRUCTIONS.md` wird ausgeliefert. |
| 10 | `4.a.C` | OPEN | `test(chat): lock the initialization and status contract` | Chat-Vertrag, UI und Packaging werden strukturell abgesichert. |
| 11 | `5.a.W` | OPEN | `docs(readme): document PatchHarbor 1.1.1 workflows` | README und Help erklären alle Initialisierungs- und Betriebsfälle. |
| 12 | `5.b.C` | OPEN | `release: finalize PatchHarbor 1.1.1` | Akzeptanz, Plattformen, Packaging und Version 1.1.1 sind freigegeben. |

Statuswerte sind ausschließlich `DONE`, `NEXT` und `OPEN`. Die `DONE`-Zeilen müssen lückenlos am Anfang stehen; solange der Plan nicht abgeschlossen ist, folgt genau eine `NEXT`-Zeile.

---

# Meilenstein 1 – Gemeinsame Konfiguration und sichere Pfadgrenze

## Ziel

Eine einzige benutzerspezifische `config.json` legt den Exchange-Ordner plattformübergreifend, atomar und ohne Überschneidung zu registrierten Repositorys fest.

### 1.a.W – Exchange-Konfiguration und CLI einführen

**Commitposition:** 1 / 12<br>
**Commit-Message:** `feat(config): add shared exchange directory configuration`<br>
**Status:** DONE

- allgemeines Core-Modul für `config.json` anlegen,
- Format-1-Schema mit `format_version` und `exchange_directory` bereitstellen,
- `patchharbor configure exchange-directory VERZEICHNIS` und `patchharbor configure show` einführen,
- plattformabhängige Benutzerpfade über die vorhandene Plattformgrenze bestimmen,
- Happy-Path-CLI-, Datei-, Packaging- und Audit-Tests ergänzen.

### 1.a.R – Konfigurationspersistenz und Validierung härten

**Commitposition:** 2 / 12<br>
**Commit-Message:** `fix(config): harden exchange configuration persistence`<br>
**Status:** DONE

- geschlossenes Schema einschließlich doppelter, fehlender und unbekannter Felder erzwingen,
- UTF-8, LF, atomaren Austausch und stabile reguläre Dateilesung absichern,
- nur absolute, existierende beziehungsweise sicher erstellbare Verzeichnisse akzeptieren,
- physisch kanonisieren und Fehler als eigene Konfigurationskategorie ausgeben,
- Unit-, CLI-, Registry-, Run-Report-, Architektur- und Release-Tests ergänzen.

### 1.b.W – Exchange-/Repository-Grenzen vollständig abschließen

**Commitposition:** 3 / 12<br>
**Commit-Message:** `feat(config): complete exchange repository boundaries`<br>
**Status:** DONE

- Exchange innerhalb, oberhalb oder identisch zu einem registrierten Repository ablehnen,
- Registrierung innerhalb, oberhalb oder identisch zum Exchange-Ordner ablehnen,
- Symlink-/Junction-Auflösung und physische Pfade auf beiden Plattformgrenzen prüfen,
- Registry-Snapshot, Konfigurationsschreiben und Pfadprüfung in eindeutiger Lock-Reihenfolge ausführen,
- TOCTOU-relevante Pfade unmittelbar vor Veröffentlichung erneut prüfen,
- kleine unveränderliche Modelle verwenden und doppelte JSON-/Pfadhelfer entfernen,
- alte `paths.json`-/Watcher-Überlappungskonzepte weder migrieren noch als Fallback behalten,
- gezielte Pfad-, Registry-, Architektur- und vollständige Regressionstests ausführen.

**Definition of Done Meilenstein 1:** `config.json` ist die einzige Benutzerkonfiguration für `exchange_directory`; `register` bleibt nicht interaktiv; keine zulässige Konfiguration kann Exchange und Repository überlappen lassen.

---

# Meilenstein 2 – Exchange-Ausgabe und automatische Apply-Auswahl

## Ziel

Der Exchange-Ordner ist die zentrale Übergabestelle in beide Richtungen. Der Benutzer muss beim normalen manuellen Ablauf weder Bundle-Ziel noch Patch-Dateipfad angeben.

### 2.a.W – Result Bundles standardmäßig im Exchange-Ordner veröffentlichen

**Commitposition:** 4 / 12<br>
**Commit-Message:** `feat(bundle): publish result bundles to the exchange directory`<br>
**Status:** DONE

- `patchharbor bundle [REPOSITORY]` ohne `--output-dir` in `exchange_directory` veröffentlichen,
- Apply-Result-Bundles ohne explizites Ziel ebenfalls dort veröffentlichen,
- `--output-dir` als bewussten Vorrang erhalten,
- manuelle und automatische Zielauflösung über eine gemeinsame Core-Grenze führen,
- temporäre und endgültige Ziele physisch prüfen und atomar veröffentlichen,
- fehlende oder ungültige Konfiguration vor Repository-Mutation ablehnen,
- Result Bundles im Exchange-Ordner eindeutig als Result Bundles klassifizierbar halten,
- Unit-, E2E-, Fehler-, Race- und vollständige Regressionstests ergänzen.

### 2.b.W – Genau ein zustandsgebundenes Patch-Paket ohne Pfad finden

**Commitposition:** 5 / 12<br>
**Commit-Message:** `feat(apply): discover one state-bound exchange patch`<br>
**Status:** DONE

- `patchharbor apply` und `patchharbor apply --dry-run` ohne `PATCH_ZIP` erlauben,
- ausschließlich die direkte Ebene von `exchange_directory` untersuchen,
- Kandidaten anhand des Inhalts und nicht anhand von Dateiname oder Endung klassifizieren,
- Result Bundles, Unterverzeichnisse, temporäre Dateien und fremde Dateien ignorieren,
- `repo_id`, `base_commit`, Fingerprint-Algorithmus und Fingerprint gegen Registry und realen Zustand prüfen,
- genau einen passenden Kandidaten akzeptieren,
- bei keinem oder mehreren Treffern vor Mutation mit stabilen Fehlern abbrechen,
- ein explizit übergebener Pfad behält Vorrang vor der automatischen Suche,
- CLI-, E2E-, Mehr-Repository-, Mismatch- und Mutationsfreiheitstests ergänzen.

### 2.b.R – Dateidentität, Retry und Wiederverarbeitung härten

**Commitposition:** 6 / 12<br>
**Commit-Message:** `fix(exchange): harden processing identity and retry semantics`<br>
**Status:** DONE

- persistente Dateidentität aus physischem Pfad und SHA-256 einführen,
- unveränderte bereits automatisch versuchte Dateien nicht ungeplant erneut ausführen,
- geänderte Bytes am selben Pfad als neue Identität behandeln,
- Dry-Run, Preflight-Fehler, Entrypoint-Fehler, Erfolg und Bundle-Fehler eindeutig dokumentieren,
- Race zwischen Klassifikation, Hashing, Auswahl und Öffnen absichern,
- Exchange-Dateien niemals verschieben, löschen, umbenennen, archivieren oder aufräumen,
- denselben Statusvertrag für späteren Watcher-Verbrauch bereitstellen,
- Retry-, Race-, Persistenz-, Plattform- und vollständige Regressionstests ergänzen.

**Definition of Done Meilenstein 2:** `bundle` und `apply` funktionieren im manuellen Standardablauf ohne lokale Pfadangaben; alte Patches, Result Bundles, Logs und andere Dateien dürfen gefahrlos nebeneinander liegen bleiben.

---

# Meilenstein 3 – Watcher auf denselben Core-Vertrag reduzieren

## Ziel

Der optionale Watcher ist nur noch ein dauerhafter Auslöser. Konfiguration, Klassifikation, Auswahl und Dateidentität kommen aus dem Core.

### 3.a.W – Watcher an gemeinsame Exchange-Erkennung anschließen

**Commitposition:** 7 / 12<br>
**Commit-Message:** `feat(watcher): use shared exchange discovery`<br>
**Status:** NEXT

- Watcher ohne eigenen Eingangsordner aus der gemeinsamen `config.json` starten,
- dieselbe flache Paketklassifikation und persistente Dateidentität wie `apply` verwenden,
- Result Bundles und fremde Dateien zuverlässig ignorieren,
- genau dieselbe Apply-Grenze statt einer zweiten Ausführungslogik aufrufen,
- verständliche Start-, Warte-, Auswahl- und Fehlerausgaben erhalten,
- Core-/Watcher-Integrations-, E2E- und Subprozess-Tests ergänzen.

### 3.a.C – Legacy-Konfiguration und doppelte Watcher-Logik entfernen

**Commitposition:** 8 / 12<br>
**Commit-Message:** `refactor(watcher): remove legacy exchange configuration`<br>
**Status:** OPEN

- `watcher.json`, alte Configure-Pfade und doppelte Input-Verzeichnis-Modelle entfernen,
- systemd-Unit auf parameterlosen Start mit gemeinsamer Config umstellen,
- Restart-, Signal-, Fehler- und Loop-Prevention-Verhalten härten,
- Watcher auf Lifecycle plus Core-Aufruf reduzieren,
- keine Termux-Dauerbetriebszusage oder systemd-Sonderlösung einführen,
- Watcher-, systemd-, Packaging-, Architektur- und vollständige Regressionstests ausführen.

**Definition of Done Meilenstein 3:** Manueller Modus und Watcher besitzen nur verschiedene Auslöser, aber denselben fachlichen Exchange- und Apply-Vertrag.

---

# Meilenstein 4 – Chat-Initialisierung und deterministische UI

## Ziel

Ein neuer Entwicklungs-Chat versteht PatchHarbor vollständig, wenn er `CHAT_INSTRUCTIONS.md`, ein aktuelles Result Bundle und die Benutzeraufgabe erhält.

### 4.a.W – Vollständigen Chat-Vertrag in einer Datei ausliefern

**Commitposition:** 9 / 12<br>
**Commit-Message:** `docs(chat): add the complete PatchHarbor chat contract`<br>
**Status:** OPEN

- Root-Datei `CHAT_INSTRUCTIONS.md` vollständig anlegen,
- PatchHarbor-Fähigkeiten, Sicherheitsgrenze, Paketformat und Result-Bundle-Kreislauf erklären,
- Auswertung von `manifest.json`, `context.json`, Snapshot, Patches, untracked Dateien, `run.json` und `execution.log` festlegen,
- Plan- und Spezifikationssuche in der vereinbarten Reihenfolge beschreiben,
- Spec-vs.-Plan-vs.-Code-Prüfung und begrenzte Scope-Korrektur festlegen,
- passende Tests und genau einen Commit nach grünen Tests verlangen,
- `PLAN`, `FIX` mit `<PLAN-ID>-FIX<n>` und `OFF-PLAN` samt Zählerregeln definieren,
- standardisierte Warning- und STOP-Codes aufnehmen,
- schmale Smartphone-UI mit `PATCH BEREIT` oben und als letzter Zeile exakt übernehmen,
- klarstellen, dass der Chat keine lokalen Repository- oder Exchange-Pfade benötigt.

### 4.a.C – Chat-Vertrag, UI und Auslieferung strukturell absichern

**Commitposition:** 10 / 12<br>
**Commit-Message:** `test(chat): lock the initialization and status contract`<br>
**Status:** OPEN

- Release-Audit und Packaging um `CHAT_INSTRUCTIONS.md` erweitern,
- Pflichtabschnitte, Paketmarker, UI-Reihenfolge und exakte Statuszeilen testen,
- Widersprüche zwischen Spezifikation, Chat-Datei, README-Vorbereitung und CLI erkennen,
- sicherstellen, dass `PATCH BEREIT` nur bei genau einer vorhandenen Download-Datei verwendet wird,
- Dokument knapp, versionsgebunden und ohne erfundene Produktfähigkeiten halten,
- gezielte Dokument-, Packaging-, Architektur- und vollständige Regressionstests ausführen.

**Definition of Done Meilenstein 4:** Die Chat-Ausgabe ist für Menschen aus der Entfernung sichtbar und für einen späteren Orchestrator stabil erkennbar, ohne PatchHarbor selbst zum Chat- oder Planwerkzeug zu machen.

---

# Meilenstein 5 – Benutzerführung, Akzeptanz und Release 1.1.1

## Ziel

README, Help, Verhalten, Tests und Paketversion beschreiben denselben vollständigen 1.1.1-Workflow.

### 5.a.W – Alle Initialisierungs- und Betriebsfälle dokumentieren

**Commitposition:** 11 / 12<br>
**Commit-Message:** `docs(readme): document PatchHarbor 1.1.1 workflows`<br>
**Status:** OPEN

- README für neues Repository, bestehendes unregistriertes Repository und bereits registriertes Repository aktualisieren,
- Lage und geschlossenes Schema von `config.json` erklären,
- Exchange-Verzeichnis konfigurieren und anzeigen,
- neuen Chat mit `CHAT_INSTRUCTIONS.md` plus aktuellem Result Bundle initialisieren,
- manuellen Ablauf mit `bundle`, Patch-Download und parameterlosem `apply` beschreiben,
- Watcher-Ablauf als optionalen systemd-fähigen Modus beschreiben,
- Termux bewusst beim manuellen Modus belassen,
- explizite Pfadoptionen als Overrides dokumentieren,
- argparse-Help, README-Beispiele und tatsächliche CLI konsistent machen,
- Dokumentations-, Help-, Packaging- und vollständige Regressionstests ausführen.

### 5.b.C – Vollständige Akzeptanz und Release freigeben

**Commitposition:** 12 / 12<br>
**Commit-Message:** `release: finalize PatchHarbor 1.1.1`<br>
**Status:** OPEN

- vollständigen manuellen 1.1.1-Kreislauf End-to-End prüfen,
- Watcher-Delegation, Result-Bundle-Ignorierung und persistente Dateidentität prüfen,
- Linux-, Windows-, Packaging-, Wheel-, pipx- und Release-Audits schließen,
- alle Spezifikationspflichtszenarien 1.1.1 gegen Code und Dokumentation abgleichen,
- tote Übergangsreste und nicht mehr gültige 1.1.0-Hinweise entfernen,
- Paketversion erst jetzt auf `1.1.1` setzen,
- vollständige Suite sowie die vorhandenen Release-Gates ausführen,
- Planstatus auf 12 / 12 setzen und keine `NEXT`-Zeile mehr führen.

**Definition of Done Meilenstein 5:** Version 1.1.1 ist vollständig implementiert, dokumentiert, paketiert und freigegeben.

---

## Abdeckungsmatrix

| Spezifikationsbereich | Plan-Commits |
|---|---|
| `config.json`, CLI, Schema und Fehlervertrag | `1.a.W`, `1.a.R` |
| Exchange-/Repository-Pfadpolitik und Architekturgrenze | `1.b.W` |
| Bundle-Standardziel und gemeinsame Zielauflösung | `2.a.W` |
| Parameterloses `apply` und zustandsgebundene Auswahl | `2.b.W` |
| Persistente Identität, Retry und unangetastete Exchange-Dateien | `2.b.R` |
| Gemeinsame Watcher-Nutzung und Entfernung alter Konfiguration | `3.a.W`, `3.a.C` |
| Vollständige Chat-Initialisierung und Smartphone-UI | `4.a.W`, `4.a.C` |
| README, Help und Betriebsfälle | `5.a.W` |
| Akzeptanz, Plattformen, Packaging und Release | `5.b.C` |

Diese Matrix ist die Vollständigkeitskontrolle der Konsolidierung. Eine Anforderung darf nicht allein deshalb entfallen, weil mehrere frühere Kleinst-Commits zu einem größeren fachlich geschlossenen Commit zusammengeführt wurden.
