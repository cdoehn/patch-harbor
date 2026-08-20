# PatchHarbor 1.1.0 – W-R-C-Commit-Plan

**Ziel:** Vollständige Umsetzung der verbindlichen Produktspezifikation 1.1.0 auf Basis des bereinigten 1.0.0-Codes.

**Vorgesehener Repository-Pfad:** `planning/1.1.0/commit-plan.md`<br>
**Separater bereits ausgeführter Rückbauplan:** `planning/1.1.0/commit-plan-cleanup.md`<br>
**Planstatus:** Umsetzungsplan; dieses Dokument enthält noch keinen Codepatch.<br>
**Umfang:** 7 Meilensteine, 32 Steps, 96 W-R-C-Commits.

---

## 1. Ausgangspunkt und Planabgrenzung

Dieser Plan beginnt **nach** dem abgeschlossenen 1.1.0-Cleanup. Der Rückbau von Inline-`FILE`-Blöcken, alten Transportvorbereitungen und totem Payload-Code wird nicht erneut geplant.

Vor dem ersten Implementierungspatch wird der reale Repository-Stand aus dem neuesten Ergebnis-ZIP verifiziert. Der Implementierungsplan setzt voraus:

- Arbeitsverzeichnis sauber.
- Cleanup-Commits und Pfadkorrektur grün.
- manueller 1.0.0-Runner weiterhin grün.
- Spezifikation und Changelog im aktuellen Repository vorhanden.
- Cleanup-Plan bleibt als historische und fachliche Rückbaugrundlage erhalten.

Der Plan ändert das Produktziel nicht. Er zerlegt ausschließlich die bestehende Spezifikation in kleine vertikale Umsetzungsschritte.

---

## 2. Verbindliches W-R-C-Prinzip

Jeder Step besteht aus genau drei Commits und liefert nach jedem Commit ein lauffähiges Repository.

### W – Let it work!

- den kleinsten vertikalen benutzbaren Durchlauf herstellen.
- Feature und zugehörigen Verhaltenstest im selben Commit liefern.
- echte Dateien, echte Git-Repositories und echte Prozesse bevorzugen.
- Fehlerfälle nur soweit ergänzen, wie sie für den ersten funktionierenden Durchlauf erforderlich sind.

### R – Do it right!

- Verantwortlichkeiten und Abhängigkeitsrichtung richtig schneiden.
- Sicherheits-, Fehler-, Cleanup- und Plattformgrenzen vollständig härten.
- bereits eingeführtes Verhalten beibehalten.
- kein verstecktes neues Feature einführen.

### C – Make it clean!

- Doppelungen, tote Pfade und überflüssige Abstraktionen entfernen.
- Tests auf fachlich unterschiedliche Fälle reduzieren.
- Namen und Datenfluss vereinfachen.
- kein neues Produktverhalten einführen.

Der Zähler wird erst erhöht, wenn der jeweilige Commit tatsächlich erzeugt, vollständig getestet und durch ein Ergebnis-ZIP bestätigt wurde.

---

## 3. Testregeln: Verhalten statt Ausgabe oder Text

Die Umsetzung folgt ausdrücklich diesen Regeln:

- Human-readable Konsolentexte, Tabellen, Help-Beschreibungen und TUI-Frames werden nicht wort- oder zeichengetreu getestet.
- CLI-Verhalten wird über Argumentakzeptanz, Exit-Code, erzeugte Dateien, Prozessverhalten, Locks und Zustandsänderungen geprüft.
- Der geschlossene JSON-Vertrag ist selbst Produktverhalten. Tests parsen JSON und prüfen exakt Felder, Typen und Semantik, aber weder Whitespace noch Schlüsselreihenfolge.
- Binärinhalte, Zeilenenden, Hashes, Objekt-IDs, Modi und ZIP-Einträge werden dort bytegenau geprüft, wo Bytegenauigkeit der Vertrag ist.
- TUI-Tests prüfen Redraw, Begrenzung, Terminal-Cleanup und fehlende Steuersequenzen im Plain-/JSON-Modus, nicht einen vollständigen Text-Snapshot.
- Git-Verhalten wird überwiegend mit echten temporären Repositorys geprüft; reine Unit-Tests bleiben auf Encoder, Schema, Pfadregeln und Prioritätsfunktionen begrenzt.
- Parallelität und Race-Fälle verwenden Prozessbarrieren oder steuerbare Hooks statt lange Sleeps.
- Jeder Pytest-Lauf besitzt `--timeout=120`; vollständige Suites und Docker-Läufe erhalten zusätzliche äußere Timeouts.
- Bei einem roten Test entsteht kein Commit; der Patch rollt vollständig auf den Ausgangs-HEAD zurück.

Dokumentation bleibt grob: kurze README, argparse-Help und notwendige Betriebsinformation für den Watcher. Es entstehen keine umfangreichen Tutorial- oder Architektur-Dokumente neben Spezifikation und Commit-Plan.

---

## 4. Meilensteinübersicht

| Meilenstein | Name | Steps | Commits | Ergebnis |
|---:|---|---:|---:|---|
| 1 | Lokale Repository-Identität und Registry | 4 | 12 | Eine konkrete lokale Git-Repository-Instanz kann sicher registriert, wiedergefunden, auf Konflikte geprüft und exklusiv gesperrt werden. |
| 2 | Kanonischer Repository-Kontext und Fingerprint | 6 | 18 | `patchharbor context` beschreibt einen registrierten Git-Zustand reproduzierbar durch Base-Commit und den normativen Fingerprint `patchharbor-state-v1`. |
| 3 | Vollständiges PatchHarbor Result Bundle | 5 | 15 | `patchharbor bundle` erzeugt einen vollständigen, konsistenten und atomar veröffentlichten Repository-Snapshot ohne Git-Historie. |
| 4 | Sicheres Patch-Paket und vollständiger Dry-Run | 5 | 15 | Ein selbstbeschreibendes ZIP-Paket kann streng validiert, genau einem registrierten Repository-Zustand zugeordnet und ohne Mutation vollständig vorgeprüft werden. |
| 5 | Mutierender Apply-Pfad und vollständiger Auftragslebenszyklus | 5 | 15 | `patchharbor apply` schreibt sichere Nutzdateien atomar, führt genau einen Entrypoint kontrolliert aus und erzeugt nach jedem sicher aufgelösten Auftrag das vollständige Ergebnis. |
| 6 | Separater PatchHarbor Watcher | 3 | 9 | Eine dünne Linux-Komponente erkennt abgeschlossene Download-Dateien und delegiert sie unverändert an die öffentliche Apply-Grenze, ohne Core-Logik zu duplizieren. |
| 7 | Regression, Plattformen und Release 1.1.0 | 4 | 12 | Die vollständige 1.1.0-Spezifikation ist auf Linux und Windows verhaltensorientiert geprüft, pipx-fähig paketiert und nur mit grünen blockierenden Gates freigabefähig. |
| **Gesamt** |  | **32** | **96** | Vollständige Implementierung und Freigabereife der Spezifikation 1.1.0 |

Die Reihenfolge ist absichtlich:

```text
Registry und Locks
→ Context und Fingerprint
→ vollständiges Result Bundle
→ sicheres Paket und Dry-Run
→ mutierender Apply
→ separater Watcher
→ Plattform- und Release-Gates
```

Das Result Bundle kommt bewusst vor dem mutierenden Apply. Dadurch verwenden Dry-Run, Mismatch, Entrypoint-Fehler und erfolgreicher Apply von Anfang an dieselbe echte Snapshot-Engine.

---

# Meilenstein 1 – Lokale Repository-Identität und Registry

## Ziel

Eine konkrete lokale Git-Repository-Instanz kann sicher registriert, wiedergefunden, auf Konflikte geprüft und exklusiv gesperrt werden.

## Scope

- plattformgerechte Benutzer-, Konfigurations-, Zustands-, Result- und Lock-Verzeichnisse.
- UUID v4 pro lokalem Klon oder Worktree.
- reserviertes lokales Verzeichnis `.patchharbor/` und lokale Git-Exclude-Regel.
- globale Registry mit atomarer Persistenz.
- `register`, `register --new-id`, `registry list` und `unregister`.
- globale Registry-Sperre, Repository-Sperre und feste Lock-Reihenfolge.

## Definition of Done

- Zwei lokale Klone desselben Remotes besitzen verschiedene IDs.
- Registry und lokale ID sind nach jeder erfolgreichen Mutation konsistent.
- Idempotenz, Verschieben, verlorene ID und kopierte ID verhalten sich wie spezifiziert.
- Ein gesperrtes Repository kann nicht parallel durch einen zweiten PatchHarbor-Auftrag verändert werden.
- PatchHarbor verändert nicht die versionierte `.gitignore`.
- Alle Tests prüfen Zustände, Dateien, Locks und Exit-Codes, nicht konkrete Meldungstexte.

---

## Step 1.a – Eine lokale Repository-Instanz erstmals registrieren

**Ergebnis:** Ein echtes Git-Repository erhält eine stabile lokale ID und einen zentralen Registry-Eintrag.

### 1.a.W – Let it work! – Lokale Repository-Registrierung vertikal bereitstellen

**Commitposition:** 1 / 96

- `patchharbor register [REPOSITORY]` mit aktuellem Verzeichnis als Standard einführen.
- plattformgerechte Standardverzeichnisse bestimmen und physisch kanonisieren.
- Repository-Wurzel und auflösbares `HEAD` mit einem echten temporären Git-Repository prüfen.
- Base-Baum und Index auf bereits getrackte `.patchharbor`-Segmente prüfen und die Registrierung dann ablehnen.
- `.patchharbor/id` mit einer kanonischen UUID v4 anlegen.
- das vollständige Verzeichnis `.patchharbor/` über den von Git gelieferten lokalen Exclude-Pfad ausschließen.
- die Zuordnung `repo_id → kanonischer Pfad` unter einem globalen Registry-Lock speichern.
- Verhaltenstest: Registrierung erzeugt ID und Registry-Eintrag, `git status` bleibt davon unberührt.

### 1.a.R – Do it right! – Registrierungsgrenzen und atomare Persistenz richtig schneiden

**Commitposition:** 2 / 96

- Benutzerpfade, physische Kanonisierung, Registry-Persistenz und Repository-Prüfung trennen.
- ID-Datei und Registry jeweils über temporäre Datei im selben Verzeichnis atomar ersetzen.
- besondere `.patchharbor`-Pfade wie Symlink, Junction oder reguläre Datei klar ablehnen.
- UUID- und Pfadwerte als kleine unveränderliche Modelle weiterreichen statt als lose Strings.
- Teilfehler als Registry-Fehler behandeln und keinen scheinbaren Erfolg melden.

### 1.a.C – Make it clean! – Registrierungsbasis auf das notwendige Minimum reduzieren

**Commitposition:** 3 / 96

- doppelte Pfad-, UUID- und Dateischreibhelfer entfernen.
- kein allgemeines Konfigurationsframework und keine Plugin-Abstraktion einführen.
- Tests auf beobachtbare Registry-, Datei- und Git-Zustände begrenzen.
- ungenutzte Zwischenmodelle und textbasierte Ausgabeerwartungen löschen.

---

## Step 1.b – Registry inspizieren und Zuordnungen entfernen

**Ergebnis:** Registrierte Instanzen können konsistent aufgelistet und zentral abgemeldet werden.

### 1.b.W – Let it work! – Registry-Liste und Unregister-Verhalten implementieren

**Commitposition:** 4 / 96

- `patchharbor registry list` und `patchharbor unregister REPOSITORY_OR_REPO_ID` einführen.
- Registry-Lesezugriffe ebenfalls unter dem globalen Lock ausführen.
- Status `ok`, `missing` und `conflict` aus dem realen Registry- und Dateisystemzustand bestimmen.
- Einträge stabil nach den ASCII-Bytes der `repo_id` sortieren.
- beim Unregister nur die zentrale Zuordnung entfernen und `.patchharbor/id` erhalten.
- `registry list --json` als exakt versioniertes, geparstes JSON-Ergebnis implementieren.
- Verhaltenstests für vorhandene, fehlende und abgemeldete Repositorys ergänzen.

### 1.b.R – Do it right! – Registry-Snapshot und Mutationen fachlich trennen

**Commitposition:** 5 / 96

- konsistenten Registry-Snapshot von Statusauflösung und Darstellung trennen.
- Pfad- und ID-Auflösung für Unregister eindeutig machen; keine Fuzzy-Auswahl zulassen.
- JSON-Envelope aus strukturierten Ergebnissen erzeugen und nicht aus Konsolentext rekonstruieren.
- Fehlerkategorien und Exit-Code 8 für Registry- und Auflösungsfehler zentral abbilden.

### 1.b.C – Make it clean! – Registry-Verwaltung und Tests vereinfachen

**Commitposition:** 6 / 96

- gemeinsame Lese- und Schreibpfade der Registry zusammenführen.
- doppelte Test-Setups für Registry-Dateien zu verhaltensorientierten Fixtures reduzieren.
- keine exakten Human-Readable-Tabellen oder Fehlersätze testen.
- nur den geschlossenen JSON-Vertrag exakt als Datenstruktur prüfen.

---

## Step 1.c – Verschobene, kopierte und neu identifizierte Instanzen behandeln

**Ergebnis:** Alle in der Spezifikation beschriebenen Identitätsübergänge sind deterministisch und ohne Raten lösbar.

### 1.c.W – Let it work! – Idempotenz, Verschieben, ID-Verlust und `--new-id` umsetzen

**Commitposition:** 7 / 96

- erneutes Registrieren desselben Pfads mit derselben ID idempotent behandeln.
- eine verschobene Instanz auf den neuen Pfad umhängen, wenn der alte Pfad nicht mehr existiert.
- eine kopierte ID bei zwei gleichzeitig vorhandenen Pfaden als Konflikt ablehnen.
- bei verlorener ID alte Zuordnungen exakt desselben kanonischen Pfads entfernen und eine neue UUID erzeugen.
- `patchharbor register --new-id` zur bewussten Trennung einer kopierten Instanz implementieren.
- die gültige Zuordnung des anderen Pfads mit der alten ID unverändert lassen.
- Verhaltenstests mit echten verschobenen und kopierten Repository-Verzeichnissen ergänzen.

### 1.c.R – Do it right! – Identitätsübergänge als eindeutige Zustandsmaschine absichern

**Commitposition:** 8 / 96

- Übergänge aus Registry-Snapshot, lokalem ID-Zustand und Pfadexistenz explizit modellieren.
- lokale ID und Registry unter demselben globalen Lock konsistent aktualisieren.
- bei Teilfehlern den vorherigen Zustand best effort wiederherstellen und verbleibende Inkonsistenz melden.
- kanonische UUID-Schreibweise an jeder Eingabe- und Persistenzgrenze prüfen.

### 1.c.C – Make it clean! – Konfliktlogik und Testmatrix entschlacken

**Commitposition:** 9 / 96

- überlappende Fallunterscheidungen durch eine kleine Übergangstabelle ersetzen.
- doppelte Pfad- und ID-Vergleiche entfernen.
- Tests auf fachlich unterschiedliche Übergänge begrenzen.
- keine historische Registry-Migration oder automatische Fern-Repository-Erkennung hinzufügen.

---

## Step 1.d – Exklusive Repository-Sperren und sichere Mutationsgrenzen etablieren

**Ergebnis:** Registry-Mutationen und spätere Repository-Aufträge besitzen eine portable, deadlockfreie Sperrgrundlage.

### 1.d.W – Let it work! – Repository-Lock und Busy-Verhalten integrieren

**Commitposition:** 10 / 96

- eine exklusive Sperre pro `repo_id` im benutzerspezifischen Lock-Verzeichnis implementieren.
- `unregister` und `register --new-id` den betroffenen Repository-Lock beachten lassen.
- einen zweiten konkurrierenden Prozess mit Exit-Code 12 als beschäftigt ablehnen.
- den Lock nach normalem Ende, Fehler und Prozessabbruch wieder verfügbar machen.
- die Reihenfolge globaler Registry-Lock vor Repository-Lock in echten Paralleltests prüfen.
- getrackte Pfade unter `.patchharbor/` ohne Beachtung der Groß-/Kleinschreibung ablehnen.

### 1.d.R – Do it right! – Plattformgrenzen und Lock-Lebenszyklus richtig kapseln

**Commitposition:** 11 / 96

- Linux- und Windows-Lockmechanik hinter einer kleinen Plattformgrenze kapseln.
- Registry-Zuordnung, Pfad und lokale ID unter beiden Locks erneut validieren.
- Lock-Ownership über Kontextmanager und einen gemeinsamen Cleanup-Pfad steuern.
- keinen dauerhaften Stale-Lock allein aufgrund einer zurückgebliebenen Datei erzeugen.
- Lock-Inversion durch Architektur- und Paralleltests verhindern.

### 1.d.C – Make it clean! – Sperrimplementierung und Architektur bereinigen

**Commitposition:** 12 / 96

- nur einen gemeinsamen Lock-Vertrag für Registry und Repository behalten.
- Polling, Retry und Fehlermapping auf das notwendige Maß reduzieren.
- zeitabhängige Tests durch Prozess-Synchronisationspunkte statt lange Sleeps stabilisieren.
- Meilensteinreview durchführen und keine Watcher- oder Apply-Logik vorwegnehmen.

## Review nach Meilenstein 1

**Ergebnis nach 1.d.C:**

- Die Definition of Done ist durch echte Repository-, Registry- und Paralleltests abgedeckt.
- Ein wartender Lock-Retry ist für den spezifizierten Busy-Vertrag nicht erforderlich; Locks werden einmalig und sofort erworben oder abgelehnt.
- Der verbleibende Plan benötigt keine fachliche Änderung.
- Es wurde keine Watcher-, Apply-, Fingerprint- oder Result-Bundle-Logik vorweggenommen; PatchHarbor bleibt ein kontrollierter Runner.

---

# Meilenstein 2 – Kanonischer Repository-Kontext und Fingerprint

## Ziel

`patchharbor context` beschreibt einen registrierten Git-Zustand reproduzierbar durch Base-Commit und den normativen Fingerprint `patchharbor-state-v1`.

## Scope

- vollständiger Base-Commit unabhängig vom Git-Objektformat.
- kanonische staged, unstaged und untracked Datensätze.
- exakte Byte-Rahmung und vier Referenzvektoren.
- portable Repository-Pfade und unterstützte Dateitypen.
- Ablehnung nicht eindeutiger Git-Sonderzustände.
- menschlicher Kontextblock und strikter JSON-Vertrag.

## Definition of Done

- Clean, staged, unstaged und untracked Zustände liefern reproduzierbare Fingerprints.
- Die vier normativen Encoder-Testvektoren stimmen bytegenau.
- Base-Commit und Fingerprint bleiben getrennte Werte.
- Nicht unterstützte Git-, Pfad- und Dateitypzustände werden vor Kontextausgabe abgelehnt.
- Context hält den Repository-Lock nur während der konsistenten Zustandsaufnahme.
- Tests verwenden echte Git-Repositories; reine Unit-Tests bleiben auf Encoder und Pfadregeln begrenzt.

---

## Step 2.a – Clean-Kontext als ersten vertikalen Fingerprint-Durchlauf liefern

**Ergebnis:** Ein registriertes sauberes Repository liefert Base-Commit, Dirty-Status und den normativen Clean-Fingerprint.

### 2.a.W – Let it work! – Clean-Kontext und leeren Referenzvektor implementieren

**Commitposition:** 13 / 96

- `patchharbor context [REPOSITORY]` unter dem Repository-Lock einführen.
- den vollständigen `HEAD`-Objektnamen als `base_commit` bestimmen.
- den Fingerprint-Stream mit Header und drei Nullzählern exakt codieren.
- SHA-256 bilden und auf 16 kleingeschriebene Hex-Zeichen kürzen.
- den normativen leeren Testvektor bytegenau erfüllen.
- `context --json` mit exakt den spezifizierten Feldern als geparstes Objekt ausgeben.
- nach erfolgreicher Registrierung denselben Context-Dienst für den fertigen Kopierblock verwenden.

### 2.a.R – Do it right! – Git-Aufnahme, Encoder und Darstellung richtig trennen

**Commitposition:** 14 / 96

- reinen Fingerprint-Encoder von Git-Befehlen und CLI-Ausgabe trennen.
- Git-Ausgaben als Bytes unter kontrollierter Umgebung lesen.
- Base-Commit nicht in den Fingerprint-Stream aufnehmen.
- SHA-1- und SHA-256-Objektformate ohne künstliche 40-Zeichen-Annahme modellieren.
- Context-Ergebnis als unveränderlichen Datenträger an Human- und JSON-Darstellung übergeben.

### 2.a.C – Make it clean! – Clean-Kontext und Tests vereinfachen

**Commitposition:** 15 / 96

- keine generische Hash- oder Serialisierungsbibliothek im Projekt aufbauen.
- Human-Ausgabe nicht zeichengetreu testen; nur enthaltene Werte und Verhalten prüfen.
- JSON-Whitespace und Schlüsselreihenfolge nicht testen.
- ungenutzte Encoder-Zwischenobjekte entfernen.

---

## Step 2.b – Staged Zustand kanonisch erfassen

**Ergebnis:** Indexänderungen werden unabhängig von Patchdarstellung und Rename-Erkennung vollständig gehasht.

### 2.b.W – Let it work! – Staged Datensätze aus Base-Baum und Index erzeugen

**Commitposition:** 16 / 96

- Base-Baum über `git ls-tree -r -z --full-tree` als Bytes lesen.
- Index über `git ls-files --stage -z` erfassen.
- Hinzufügung, Änderung, Löschung und Modusänderung als kanonische Datensätze bilden.
- Datensätze byteweise nach ursprünglichen Pfadbytes sortieren.
- Modi und vollständige Objekt-IDs exakt nach Spezifikation rahmen.
- den normativen Referenzvektor für eine staged Hinzufügung erfüllen.
- Integrationstests mit echten Indexzuständen und Binärblobs ergänzen.

### 2.b.R – Do it right! – Base- und Indexmodelle fachlich korrekt schneiden

**Commitposition:** 17 / 96

- Baum- und Indexparser als kleine bytesichere Grenzen strukturieren.
- Umbenennungen bewusst als Löschung plus Hinzufügung behandeln.
- fehlende Base- oder Indexwerte als vorhandenes Feld mit leerem Payload codieren.
- Objekttyp, Objekt-ID-Länge und unterstützte Modi validieren.

### 2.b.C – Make it clean! – Staged Vergleich und Tests entschlacken

**Commitposition:** 18 / 96

- doppelte Maps und Sortierdurchläufe entfernen.
- keine Git-Patchtexte als Fingerprint-Testvertrag verwenden.
- Testfälle auf fachlich verschiedene staged Übergänge reduzieren.
- Encoder-Feldnamen an genau einer Stelle halten.

---

## Step 2.c – Unstaged Zustand einschließlich Binärinhalt erfassen

**Ergebnis:** Änderungen zwischen Index und Working Tree werden mit Status, Modus und vollständigen Bytes gehasht.

### 2.c.W – Let it work! – Unstaged Änderungen und Löschungen kanonisch aufnehmen

**Commitposition:** 19 / 96

- `git diff-files --raw -z --no-renames --no-ext-diff --` unter kontrollierter Umgebung auswerten.
- reguläre Änderungen mit Indexmodus, Objekt-ID, Working-Tree-Modus und rohem Inhalt erfassen.
- Löschungen mit Working-Tree-Art `missing` und leeren Inhaltfeldern erfassen.
- `core.fileMode` bei der kanonischen Wahl zwischen `100644` und `100755` berücksichtigen.
- Binärinhalt einschließlich NUL-Bytes und originale Zeilenenden unverändert hashen.
- den normativen Referenzvektor für eine unstaged Änderung erfüllen.
- Verhaltenstests für Änderung, Löschung und Ausführungsbit ergänzen.

### 2.c.R – Do it right! – Working-Tree-Lesen und Modusbestimmung absichern

**Commitposition:** 20 / 96

- `lstat` verwenden und symbolischen Links niemals folgen.
- Dateiart, Modus und Inhalt als einen konsistenten Datensatz aufnehmen.
- nur die spezifizierten Statuswerte `M` und `D` akzeptieren.
- Dateilese- und Git-Parserfehler als nicht unterstützten Zustand oder klaren Tool-Fehler abbilden.

### 2.c.C – Make it clean! – Unstaged Pfad vereinfachen

**Commitposition:** 21 / 96

- Moduslogik für staged, unstaged und später untracked zentral, aber klein halten.
- unnötige Textdecodierung und Zeilenendennormalisierung entfernen.
- Tests über Fingerprintänderung und Datensatzsemantik statt interne Funktionen formulieren.
- keine Dateiwatcher- oder Cachelogik einführen.

---

## Step 2.d – Untracked Dateien vollständig in den Fingerprint aufnehmen

**Ergebnis:** Nicht ignorierte reguläre Dateien beeinflussen den Fingerprint mit Pfad, Modus, Größe und vollständigem Inhalt.

### 2.d.W – Let it work! – Untracked Zustand bytegenau implementieren

**Commitposition:** 22 / 96

- `git ls-files --others --exclude-standard -z --` als einzige untracked Quelle verwenden.
- Pfade byteweise sortieren und ignorierte Dateien ausschließen.
- Modus, acht Byte große Dateigröße und vollständige Inhaltsbytes codieren.
- den normativen Referenzvektor für `note.txt` erfüllen.
- Binärdateien, leere Dateien und Ausführungsbits in echten Repositorys testen.
- nachweisen, dass ein geänderter Base-Commit allein den Dirty-Fingerprint nicht verändert.

### 2.d.R – Do it right! – Untracked Aufnahme sicher und konsistent machen

**Commitposition:** 23 / 96

- Dateiart vor und nach dem Öffnen ausreichend prüfen, ohne Symlinks zu dereferenzieren.
- ursprüngliche UTF-8-Pfadbytes und kanonischen Vergleichspfad getrennt halten.
- Größe und tatsächlich gelesene Bytes auf Konsistenz prüfen.
- untracked Datensätze in dasselbe unveränderliche Zustandsmodell integrieren.

### 2.d.C – Make it clean! – Untracked Encoder und Fixtures bereinigen

**Commitposition:** 24 / 96

- gemeinsame rohe Dateileselogik nur einmal behalten.
- umfangreiche Fixture-Bäume durch wenige semantisch unterschiedliche Fälle ersetzen.
- keine ignorierten Dateien oder `.patchharbor/` in den Zustand aufnehmen.
- Fingerprinttests nicht an JSON- oder Konsolendarstellung koppeln.

---

## Step 2.e – Nicht eindeutige Git-Sonderzustände ablehnen

**Ergebnis:** Der sichere Repository-Pfad akzeptiert nur Git-Zustände, die vollständig und reproduzierbar beschrieben werden können.

### 2.e.W – Let it work! – Sonderzustandsprüfung vor Context und Fingerprint ergänzen

**Commitposition:** 25 / 96

- nicht aufgelöste Merge-Stages über `git ls-files --unmerged -z` ablehnen.
- Assume-Unchanged und Skip-Worktree aus `git ls-files -v -z` erkennen und ablehnen.
- Intent-to-add aus dem Raw-Diff erkennen und ablehnen.
- Sparse-Checkout und Sparse-Index aus Git-Konfiguration erkennen und ablehnen.
- Gitlinks, Submodule, getrackte Symlinks und andere Modi als `100644` oder `100755` ablehnen.
- besondere Dateitypen an getrackten und untracked Pfaden ablehnen.
- für alle Fälle Exit-Code 13 und verhaltensorientierte Integrationstests ergänzen.

### 2.e.R – Do it right! – Kanonische Git-Umgebung und Sonderzustandsgrenze zentralisieren

**Commitposition:** 26 / 96

- alle Git-Befehle mit `LC_ALL=C`, `LANG=C`, `GIT_OPTIONAL_LOCKS=0`, ohne Farbe, Textconv, externe Diffs und Rename-Erkennung ausführen.
- Git-Ausgaben NUL-getrennt und byteweise parsen.
- fehlende boolesche Git-Konfigurationen nach Spezifikation als `false` behandeln.
- Sonderzustandsprüfung vor jeder späteren Context-, Apply- und Bundle-Aufnahme wiederverwendbar machen.

### 2.e.C – Make it clean! – Git-Abfragen und Fehlerfälle konsolidieren

**Commitposition:** 27 / 96

- doppelte Subprocess-Konfigurationen entfernen.
- Sonderzustandsfehler auf wenige stabile Kategorien abbilden.
- Tests nicht an konkrete Git-Fehlermeldungen oder interne Befehlsreihenfolgen koppeln.
- keine Submodule-Unterstützung als Zukunftsabstraktion vorbereiten.

---

## Step 2.f – Portable Pfade und konsistente Context-Aufnahme abschließen

**Ergebnis:** Alle beteiligten Repository-Pfade sind auf Linux und Windows eindeutig darstellbar; Context liefert nur konsistente Zustände.

### 2.f.W – Let it work! – Repository-weite Pfad- und Kollisionsprüfung implementieren

**Commitposition:** 28 / 96

- die Pfadvereinigung aus Base-Baum, Index, unstaged und untracked Zustand prüfen.
- strikte UTF-8-Decodierung ohne Unicode-Normalisierung erzwingen.
- Steuerzeichen, Windows-ungültige Zeichen, abschließenden Punkt oder Leerraum und reservierte Gerätenamen ablehnen.
- Segmente `.git` und `.patchharbor` nach `casefold()` in Base und Index ablehnen.
- verschiedene Pfade mit identischem `casefold()`-Schlüssel als Kollision ablehnen.
- Context-Aufnahme unter Repository-Lock als einen konsistenten Snapshot abschließen.
- Verhaltenstests mit echten problematischen Pfaden ergänzen, soweit das Host-Dateisystem sie darstellen kann.

### 2.f.R – Do it right! – Originalbytes, portable Sicht und Context-Lebenszyklus richtig schneiden

**Commitposition:** 29 / 96

- ursprüngliche Pfadbytes, streng decodierten Pfad und Kollisionsschlüssel getrennt modellieren.
- dieselbe Pfadgrenze für Context, Apply und Result Bundle bereitstellen.
- Repository-Lock nach erfolgreicher Context-Aufnahme unmittelbar freigeben.
- Race- und Leseinkonsistenzen als klaren Fehler behandeln statt einen gemischten Zustand auszugeben.

### 2.f.C – Make it clean! – Fingerprint-Meilenstein bereinigen und reviewen

**Commitposition:** 30 / 96

- Pfadprüfungen aus Fingerprint-Record-Erzeugern herausziehen und doppelte Checks entfernen.
- Unit-Tests auf Encoder und reine Pfadregeln begrenzen; übrige Fälle als echte Git-Integration testen.
- keine Ausgabe-Snapshots, privaten Funktionsnamen oder Git-Befehlsstrings als Vertrag testen.
- Meilensteinreview durchführen und den normativen Algorithmus als abgeschlossen einfrieren.

## Review nach Meilenstein 2

**Ergebnis nach 2.f.C:**

- Die Definition of Done ist durch die vier normativen Encoder-Vektoren sowie echte Git-Integrationstests für clean, staged, unstaged und untracked Zustände abgedeckt.
- `patchharbor-state-v1` ist als Kompatibilitätsgrenze abgeschlossen; jede spätere Änderung der Byte-Rahmung benötigt eine neue Algorithmuskennung.
- Portable Pfade werden einmal vor der Datensatzaufnahme validiert; Fingerprint-Datensätze enthalten nur bereits geprüfte Pfadbytes.
- Eine zusätzliche Normalisierungs-, Cache- oder Git-Patch-Abstraktion ist nicht erforderlich; der verbleibende Plan benötigt keine fachliche Änderung.
- Es wurde keine Result-Bundle-, Apply- oder Watcher-Logik vorweggenommen; PatchHarbor bleibt ein kontrollierter Runner.

---

# Meilenstein 3 – Vollständiges PatchHarbor Result Bundle

## Ziel

`patchharbor bundle` erzeugt einen vollständigen, konsistenten und atomar veröffentlichten Repository-Snapshot ohne Git-Historie.

## Scope

- Run-ID, Context und Result-Manifest.
- Base-Dateien direkt aus Git-Baum und Blobs.
- staged und unstaged Rekonstruktions-Patches.
- untracked Dateien mit Modus und Hash.
- atomare ZIP-Veröffentlichung und Notfalldiagnose.
- strikter `bundle --json`-Abschlussvertrag.

## Definition of Done

- Das Bundle rekonstruiert den vollständigen unterstützten Zustand aus `base/`, Patches und `untracked/`.
- Exportattribute verändern oder entfernen keine committed Dateien.
- Während der Aufnahme veränderte Repositorys führen zu keiner veröffentlichten Enddatei.
- Temporäre und endgültige ZIP liegen im selben Result-Ordner.
- Ein manueller Bundle-Auftrag erzeugt kein erfundenes Execution-Log.
- Ein ausschließlich fehlgeschlagenes Bundle liefert Exit-Code 11.

---

## Step 3.a – Cleanes Repository als vollständige Base materialisieren

**Ergebnis:** Ein registriertes cleanes Repository kann als echtes Result Bundle ohne Git-Historie exportiert werden.

### 3.a.W – Let it work! – Manuellen Bundle-Happy-Path mit Base-Dateien implementieren

**Commitposition:** 31 / 96

- `patchharbor bundle [REPOSITORY]` unter dem Repository-Lock einführen.
- pro Auftrag eine UUID-v4-`run_id` und UTC-Zeitstempel erzeugen.
- `manifest.json`, `context.json`, `logs/run.json` und `base/` in einem ZIP erstellen.
- Base-Baum über `git ls-tree -r -z --full-tree <base_commit>` lesen.
- Blob-Inhalte über `git cat-file --batch` bytegenau materialisieren.
- `.git`, `.patchharbor` und Historie nicht aufnehmen.
- Verhaltenstest mit `export-ignore` und `export-subst`: committed Blobs bleiben vollständig und unverändert enthalten.
- Verhaltenstest: Bundle enthält exakt die committed regulären Dateien und kein `execution.log`.

### 3.a.R – Do it right! – Git-Objektlesen und Bundle-Modelle richtig kapseln

**Commitposition:** 32 / 96

- Batch-Cat-File-Protokoll als bytesichere Git-Grenze kapseln.
- Objekttyp, gemeldete Größe, gelesene Größe, Modus und vollständige Objekt-ID prüfen.
- Base-Einträge nach ursprünglichen UTF-8-Pfadbytes sortieren.
- LFS-Zeiger als tatsächlich gespeicherten Blob behandeln und keine externen Objekte nachladen.
- Result-Bundle-Schreiben von Repository-State-Aufnahme trennen.

### 3.a.C – Make it clean! – Base-Materialisierung und ZIP-Aufbau vereinfachen

**Commitposition:** 33 / 96

- keinen zweiten materialisierten `snapshot/`-Baum erzeugen.
- doppelte Blob- und ZIP-Pufferung vermeiden, soweit die Sicherheitsprüfung erhalten bleibt.
- Tests auf ZIP-Inhalt und Bytegleichheit statt interne Writer-Struktur ausrichten.
- keine Git-Archiv- oder Exportattribut-Abhängigkeit zurücklassen.

---

## Step 3.b – Staged und unstaged Änderungen rekonstruierbar aufnehmen

**Ergebnis:** Das Result Bundle enthält kontrolliert erzeugte binärfähige Rekonstruktions-Patches.

### 3.b.W – Let it work! – Staged- und Unstaged-Patches in das Bundle aufnehmen

**Commitposition:** 34 / 96

- `changes/staged.patch` mit `--cached --binary --full-index --no-renames --no-ext-diff --no-textconv --no-color` erzeugen.
- `changes/unstaged.patch` mit denselben kontrollierten Grenzen erzeugen.
- staged und unstaged Binär- sowie Modusänderungen abbilden.
- Rekonstruktionstest: Base plus staged Patch plus unstaged Patch ergibt den erwarteten getrackten Zustand.
- Fingerprint weiterhin ausschließlich aus dem normativen Zustandsencoder berechnen.

### 3.b.R – Do it right! – Patch-Erzeugung auf dieselbe kontrollierte Git-Umgebung stellen

**Commitposition:** 35 / 96

- Git-Prozesskonfiguration mit der Context-Aufnahme teilen, ohne Module zyklisch zu koppeln.
- externe Diff-Programme, Farbe, Rename-Erkennung und Textkonvertierung sicher deaktivieren.
- Patch-Dateien als rohe Bytes und nicht als plattformabhängigen Text behandeln.
- Fehler der Patch-Erzeugung als Bundle-Fehler und nicht als Fingerprintfehler einordnen.

### 3.b.C – Make it clean! – Rekonstruktionspfad und Tests bereinigen

**Commitposition:** 36 / 96

- doppelte Git-Diff-Aufrufe und Shell-Zwischendateien entfernen.
- keine exakten Headerzeilen oder Zeilenenden der Patchdarstellung testen.
- nur Anwendbarkeit, Binärtreue und Moduswirkung als Verhalten prüfen.
- unnötige Patch-Parser im PatchHarbor-Code vermeiden.

---

## Step 3.c – Untracked Dateien samt portablen Metadaten aufnehmen

**Ergebnis:** Alle nicht ignorierten untracked regulären Dateien stehen bytegenau und nachvollziehbar im Bundle.

### 3.c.W – Let it work! – Untracked Baum, Modi und Inhalts-Hashes ergänzen

**Commitposition:** 37 / 96

- untracked Dateien unter `untracked/<repository-path>` mit vollständiger Struktur ablegen.
- Inhalte bytegenau einschließlich NUL-Bytes übernehmen.
- `untracked_entries` mit Pfad, Modus, Größe und SHA-256 in das Manifest schreiben.
- `base_entries` mit Pfad, Git-Modus, Objekt-ID und Größe vervollständigen.
- ZIP-Rechte passend zu `100644` oder `100755` setzen, soweit darstellbar.
- ignorierte und besondere Dateien nicht aufnehmen.
- Verhaltenstest für Binärdatei, Modus und Hash ergänzen.

### 3.c.R – Do it right! – Snapshotdaten und Manifest aus derselben Aufnahme ableiten

**Commitposition:** 38 / 96

- Dateiinhalt, Hash, Größe und ZIP-Eintrag aus derselben gelesenen Bytefolge erzeugen.
- Pfad- und Dateitypprüfung aus dem Context-Modul wiederverwenden.
- Manifest-Metadaten als plattformunabhängige Quelle der Modi festlegen.
- keine `.patchharbor/id` und keine ignorierten Secrets automatisch aufnehmen.

### 3.c.C – Make it clean! – Untracked Aufnahme und Manifest vereinfachen

**Commitposition:** 39 / 96

- doppelte Datei-Lese- und Hashdurchläufe entfernen.
- Manifestlisten ausschließlich nach ursprünglichen UTF-8-Pfadbytes sortieren.
- Tests auf Bytes, Hashes und Rekonstruktion statt JSON-Pretty-Printing ausrichten.
- keine allgemeine Secret-Erkennung hinzufügen.

---

## Step 3.d – Konsistente Aufnahme und atomare Veröffentlichung garantieren

**Ergebnis:** Nur ein vollständig geprüftes Bundle eines unveränderten Repository-Zustands erhält den endgültigen Dateinamen.

### 3.d.W – Let it work! – Vorher-Nachher-Prüfung und atomare Result-Veröffentlichung implementieren

**Commitposition:** 40 / 96

- kanonischen Result-Ordner bestimmen und gegen alle registrierten Repository-Wurzeln prüfen.
- expliziten `--output-dir` unterstützen und vor Verwendung physisch kanonisieren.
- temporäre ZIP direkt im endgültigen Result-Ordner exklusiv anlegen.
- Context vor und nach der Aufnahme bestimmen und äußere Änderungen klar ablehnen.
- ZIP schließen, Pflichtdateien und CRCs erneut prüfen und erst dann mit `os.replace()` veröffentlichen.
- bei Fehler keine Datei unter endgültigem Namen zurücklassen.
- Race-Test mit einem während der Aufnahme veränderten Repository ergänzen.

### 3.d.R – Do it right! – Result-Ziel, Konsistenzprüfung und Veröffentlichung richtig trennen

**Commitposition:** 41 / 96

- physische Grenzprüfung einschließlich Symlinks und Junctions zentralisieren.
- temporären Namen, finalen Namen und Veröffentlichung als expliziten Lebenszyklus modellieren.
- Datei- und Verzeichnismetadaten best effort synchronisieren, ohne Erfolg vorzutäuschen.
- Repository-Lock bis zum Abschluss oder Fehlschlag der Veröffentlichung halten.
- Snapshotdaten und Vorher-Nachher-Context auf dieselbe Zustandsdefinition beziehen.

### 3.d.C – Make it clean! – Bundle-Veröffentlichung und Race-Tests stabilisieren

**Commitposition:** 42 / 96

- nur einen Cleanup-Pfad für temporäre ZIP und Run-Verzeichnis behalten.
- Pollingtests durch steuerbare Synchronisationspunkte statt Zeitannahmen stabilisieren.
- keine dateisystemübergreifende Rename-Fallbacklogik einführen.
- Result-Pfadprüfungen auf reale Grenzverletzungen statt Fehlermeldungstext testen.

---

## Step 3.e – Run-Bericht, JSON-Vertrag und Bundle-Fehler abschließen

**Ergebnis:** Manuelle Bundle-Aufträge besitzen einen stabilen maschinenlesbaren Abschluss und eine sichere Notfalldiagnose.

### 3.e.W – Let it work! – Strukturierten Bundle-Abschluss und Exit-Code 11 implementieren

**Commitposition:** 43 / 96

- `logs/run.json` mit Operation, Zeiten, Laufzeit, Kontext, Warnings und Bundle-Status erzeugen.
- `bundle --json` mit dem exakt spezifizierten Envelope und Resultat ausgeben.
- stdout im JSON-Modus auf genau ein parsebares Objekt plus abschließenden LF begrenzen.
- bei fehlgeschlagenem manuellen Bundle Exit-Code 11 zurückgeben.
- bei Bundle-Fehler temporäre Enddatei entfernen und `run.json` best effort im Notfallverzeichnis retten.
- den Notfallpfad strukturiert und auf stderr melden.
- Verhaltenstests für Erfolg, Bundle-Fehler und fehlgeschlagene Notfallrettung ergänzen.

### 3.e.R – Do it right! – Run-Ergebnis und Bundle-Ergebnis als gemeinsame Modelle ordnen

**Commitposition:** 44 / 96

- einen einheitlichen Run-Bericht als Quelle für `run.json`, JSON-CLI und spätere Apply-Darstellung verwenden.
- RFC-3339-UTC-Zeitstempel, kanonische UUIDs und physische absolute Pfade zentral erzeugen.
- nicht endliche Zahlen und geheime Umgebungswerte aus strukturierten Logs ausschließen.
- `execution_present=false` ohne erfundenes `execution.log` modellieren.
- Bundle-Fehler von Repository- und Context-Fehlern trennen.

### 3.e.C – Make it clean! – Result-Bundle-Meilenstein bereinigen und reviewen

**Commitposition:** 45 / 96

- mehrfache JSON-Serialisierer und Statusumrechnungen entfernen.
- nur den geschlossenen Datenvertrag, nicht Whitespace oder Schlüsselformatierung testen.
- README lediglich um den vollständigen Snapshot- und Secret-Hinweis ergänzen, keine Langdokumentation erzeugen.
- Meilensteinreview durchführen und die Bundle-Engine für Dry-Run und Apply freigeben.

## Review nach Meilenstein 3

**Ergebnis nach 3.e.C:**

- Die Definition of Done ist durch echte Rekonstruktions-, Binär-, Modus-, Race-, Lock- und Publikationstests abgedeckt.
- Strukturierte JSON-Dokumente verwenden eine gemeinsame Serialisierungsgrenze; Tests prüfen die geschlossenen Datenverträge statt Whitespace oder Schlüsselformatierung.
- Die Bundle-Engine besteht aus unveränderlicher Aufnahme, Writer, Zielprüfung und atomarer Veröffentlichung und ist damit für Dry-Run und Apply freigegeben.
- Ein reduziertes Bundle, ein zweiter `snapshot/`-Baum und automatische Secret-Erkennung sind nicht erforderlich; die README weist knapp auf den vollständigen Snapshot und mögliche Secrets hin.
- Der verbleibende Plan benötigt keine fachliche Änderung; es wurde keine Apply-, Entrypoint- oder Watcher-Logik vorweggenommen und PatchHarbor bleibt ein kontrollierter Runner.

---

# Meilenstein 4 – Sicheres Patch-Paket und vollständiger Dry-Run

## Ziel

Ein selbstbeschreibendes ZIP-Paket kann streng validiert, genau einem registrierten Repository-Zustand zugeordnet und ohne Mutation vollständig vorgeprüft werden.

## Scope

- tatsächliche ZIP-Erkennung unabhängig vom Dateinamen.
- geschlossenes `patch.json`-Schema.
- genau ein manifestierter Entrypoint und sichere Nutzdateien.
- sichere Repository-Auflösung unter beiden Locks.
- Base-Commit- und Fingerprintvergleich.
- vollständiger Dry-Run mit Result Bundle und JSON-Vertrag.

## Definition of Done

- Ungültige Pakete werden vollständig vor jeder Repository-Änderung abgelehnt.
- Repository-Name, Remote, Branch und Dateiname werden niemals als Ersatzschlüssel verwendet.
- Nach sicherer Repository-Auflösung wird auch bei späterer Ablehnung ein Result Bundle versucht.
- Dry-Run schreibt keine Repository-Datei und startet keinen Prozess.
- Entrypoint, Marker und Interpreter werden vor jeder möglichen Mutation geprüft.
- Alle Paketpfade und Ressourcenlimits werden vorab validiert.

---

## Step 4.a – Striktes `patch.json` und echtes ZIP-Format validieren

**Ergebnis:** PatchHarbor kann ein Format-1-Paket unabhängig von Dateiname und Endung eindeutig lesen oder ablehnen.

### 4.a.W – Let it work! – Geschlossenes Patch-Manifest implementieren

**Commitposition:** 46 / 96

- `patchharbor apply --dry-run PATCH_ZIP` zunächst bis zur reinen Paketvalidierung führen.
- das tatsächliche ZIP-Format anhand der Bytes prüfen.
- genau eine reguläre Root-Datei `patch.json` verlangen.
- UTF-8 ohne BOM, genau ein JSON-Objekt, keine doppelten Schlüssel, Kommentare, Nachdaten oder nicht endlichen Zahlen akzeptieren.
- exakt die sieben spezifizierten Felder und Typen validieren.
- kanonische UUID v4, vollständige Objekt-ID, 16-stelligen Fingerprint und Algorithmuskennung prüfen.
- Verhaltenstests für jede fachlich unterschiedliche Manifestverletzung ergänzen.

### 4.a.R – Do it right! – Manifestvalidierung als reine Grenze strukturieren

**Commitposition:** 47 / 96

- `patch_manifest.py` ohne Git-, Dateischreib-, Execution- oder TUI-Abhängigkeit einführen.
- Boolesche Werte klar von JSON-Integern unterscheiden.
- Objekt-ID-Länge zunächst syntaktisch und nach Repository-Auflösung gegen SHA-1 oder SHA-256 prüfen.
- Formatversion und unbekannte Felder fail closed behandeln.
- Exit-Code 10 für Manifest- und Paketformatfehler zentral zuordnen.

### 4.a.C – Make it clean! – Manifestparser und Schema-Tests vereinfachen

**Commitposition:** 48 / 96

- keine allgemeine JSON-Schema-Bibliothek oder erweiterbare Manifest-Registry einführen.
- Testmatrix auf unterschiedliche Vertragsverletzungen statt jede Zeichenvariante begrenzen.
- Roh-JSON-Formatierung und Fehlermeldungswortlaut nicht testen.
- Marker und Algorithmuskonstanten an genau einer Stelle halten.

---

## Step 4.b – Entrypoint und übrige Paketdateien sicher klassifizieren

**Ergebnis:** Nur der manifestierte Entrypoint ist ausführbar; alle anderen sicheren Einträge sind bytegenaue Nutzdateien.

### 4.b.W – Let it work! – Paketpfade, Eintragstypen und Ressourcen vollständig vorprüfen

**Commitposition:** 49 / 96

- Entrypoint-Pfad gegen die gemeinsamen sicheren ZIP-Pfadregeln prüfen.
- `patch.json`, Entrypoint und alle übrigen regulären Einträge eindeutig klassifizieren.
- Pfade mit `.git` oder `.patchharbor` in irgendeinem Segment unabhängig von Groß-/Kleinschreibung ablehnen.
- Links, Geräte, FIFOs, Sockets, doppelte Ziele und Case-Kollisionen ablehnen.
- markerhaltige andere Dateien nicht automatisch ausführen.
- verschachtelte ZIPs ausschließlich als reguläre Nutzdateien behandeln.
- Eintragszahl sowie deklarierte und tatsächlich gelesene Größen gegen die gemeinsame ResourcePolicy prüfen.

### 4.b.R – Do it right! – Sichere Paketauflösung ohne Parallelformat richtig schneiden

**Commitposition:** 50 / 96

- `bundle_paths.py`, `resource_policy.py` und Payload-Modelle mit dem manuellen ZIP-Pfad teilen.
- Manifest- und Entrypoint-Sonderrollen von der allgemeinen ZIP-Eintragsprüfung trennen.
- das komplette Paket vor dem ersten Zielschreiben beschreiben, ohne es pauschal ins Repository zu entpacken.
- ursprüngliche ZIP-Mitgliedsnamen vor jeder OS-Pfadnormalisierung prüfen.

### 4.b.C – Make it clean! – Paketklassifikation und gemeinsame ZIP-Grenze bereinigen

**Commitposition:** 51 / 96

- doppelte Sicherheitsregeln zwischen manuellem Bundle und Apply entfernen.
- keinen zweiten Bundletyp oder rekursive Archivabstraktion einführen.
- Tests auf Ausführungsanzahl, Zielbytes und Ablehnung statt Klassennamen ausrichten.
- unnötige vollständige Archivkopien vermeiden.

---

## Step 4.c – Manifest sicher einem lokalen Repository-Zustand zuordnen

**Ergebnis:** Ein Paket wird ausschließlich der durch `repo_id`, Base-Commit und Fingerprint beschriebenen Instanz zugeordnet.

### 4.c.W – Let it work! – Sichere Repository-Auflösung und Zustandsvergleich implementieren

**Commitposition:** 52 / 96

- `repo_id` unter globalem Registry-Lock eindeutig auflösen.
- Pfad, Git-Repository, `.patchharbor/`, lokale ID und ungetrackten reservierten Bereich prüfen.
- Repository-Lock in der festgelegten Reihenfolge erwerben und alle Zuordnungen unter beiden Locks revalidieren.
- erst danach das Repository als sicher aufgelöst markieren und den Registry-Lock freigeben.
- Objektformat, vollständigen `HEAD`, Algorithmus und Fingerprint mit dem Manifest vergleichen.
- unbekannte ID mit Exit 8 sowie Base-, Algorithmus- oder Fingerprint-Mismatch mit Exit 9 ablehnen.
- nach sicherer Auflösung auch bei Mismatch ein Result Bundle des tatsächlichen Zustands versuchen.

### 4.c.R – Do it right! – Safe-Resolved-Repository und Lock-Lebenszyklus explizit modellieren

**Commitposition:** 53 / 96

- einen unveränderlichen Datenträger für sicher aufgelösten Pfad, ID, Locks und tatsächlichen Context einführen.
- keine Repository-Auswahl über Name, Remote, Branch, Dateiname oder letzten Lauf zulassen.
- Result-Ordner vor jeder späteren Mutation bestimmen, anlegen, prüfen und temporären Bundle-Pfad reservieren.
- Repository-Lock bis zum Abschluss oder Fehlschlag des Result Bundles halten.
- `result_bundle.status=not_attempted` nur vor sicherer Auflösung erlauben.

### 4.c.C – Make it clean! – Auflösungs- und Mismatchpfade vereinfachen

**Commitposition:** 54 / 96

- Registry-, ID- und Lock-Prüfung nicht in CLI oder Manifestmodul duplizieren.
- Fehlerfälle nach sicherer und vor sicherer Auflösung klar gruppieren.
- Tests auf Schreibfreiheit, Bundle-Versuch und Exit-Code statt Fehlertext ausrichten.
- keine Fuzzy- oder Recovery-Auswahl hinzufügen.

---

## Step 4.d – Entrypoint und Nutzdateien vollständig außerhalb des Repositorys vorbereiten

**Ergebnis:** Marker, Interpreter und alle Paketbytes sind geprüft, bevor ein Repository-Zielpfad berührt wird.

### 4.d.W – Let it work! – Privaten Entrypoint-Preflight und Payload-Vorbereitung implementieren

**Commitposition:** 55 / 96

- Entrypoint in ein privates auftragsbezogenes System-Temp-Verzeichnis extrahieren.
- den exakten Marker prüfen und META sowie MESSAGE weiter rein informativ behandeln.
- Interpreter aus der bestehenden Whitelist bestimmen und Verfügbarkeit vorab prüfen.
- alle Nutzdateiinhalte vollständig außerhalb des Repositorys lesen oder temporär bereitstellen.
- Größen und Inhalts-Hashes gegen die bereits validierten ZIP-Einträge prüfen.
- bei Marker-, Interpreter- oder Payloadfehler keine temporäre Datei in einem Repository-Zielverzeichnis erzeugen.
- temporäre Entrypoint- und Paketressourcen auf allen Fehlerpfaden entfernen.

### 4.d.R – Do it right! – Preflight von Mutation und Execution richtig trennen

**Commitposition:** 56 / 96

- Parser und Interpreterzuordnung wiederverwenden, ohne den manuellen Runner mit Repositorylogik zu koppeln.
- vorbereitete Payloads als unveränderliche, geprüfte Eingaben an die spätere Mutationsgrenze übergeben.
- Interpreterfehler mit Exit 5 und ungültigen Entrypoint mit Exit 3 abbilden.
- einen gemeinsamen temporären Auftragslebenszyklus für Entrypoint, STDIN-Artefakte und Notfalldaten schaffen.

### 4.d.C – Make it clean! – Preflight-Pipeline bereinigen

**Commitposition:** 57 / 96

- mehrfache Marker-, Interpreter- und ZIP-Lesevorgänge entfernen.
- keine Repository-Datei als temporären Entrypoint verwenden.
- Tests auf fehlende Zieländerung und fehlenden Prozessstart fokussieren.
- keine frei konfigurierbaren Interpreterkommandos hinzufügen.

---

## Step 4.e – Dry-Run als vollständigen Auftrag abschließen

**Ergebnis:** Der Dry-Run durchläuft dieselbe Sicherheitskette bis zur Mutationsgrenze, startet nichts und erzeugt ein Result Bundle.

### 4.e.W – Let it work! – Dry-Run end-to-end mit Result Bundle und JSON-Vertrag liefern

**Commitposition:** 58 / 96

- vollständige Paket-, Registry-, Lock-, Context-, Entrypoint-, Interpreter- und Payloadprüfung verbinden.
- vor der Mutationsgrenze bewusst abbrechen, ohne Nutzdatei, Temp-Zieldatei oder Kindprozess.
- Result Bundle des unveränderten Repository-Zustands mit `dry_run=true` und `execution_present=false` erzeugen.
- `apply --dry-run --json` mit dem spezifizierten Apply-Envelope ausgeben.
- `primary_result.kind=dry_run_success` und `entrypoint_started=false` berichten.
- Tests über Repository-Baum, Prozessbeobachtung und Bundle-Inhalt nachweisen lassen, dass nichts verändert oder gestartet wurde.
- Mismatch- und Validierungsfälle nach sicherer Auflösung mit Result-Bundle-Versuch abdecken.

### 4.e.R – Do it right! – Dry-Run und späteren Apply bis zur Mutationsgrenze vereinheitlichen

**Commitposition:** 59 / 96

- eine gemeinsame Preflight-Pipeline mit explizitem Mutations-Gate verwenden.
- primäres Auftragsergebnis und Result-Bundle-Ergebnis getrennt modellieren.
- Run-Bericht, JSON-Envelope und Bundle-Manifest aus demselben Ergebnisobjekt erzeugen.
- Repository-Lock bis nach Bundle-Erzeugung halten und danach sicher freigeben.

### 4.e.C – Make it clean! – Dry-Run-Meilenstein bereinigen und reviewen

**Commitposition:** 60 / 96

- keinen zweiten Validator oder Dry-Run-Sonderparser behalten.
- Text- und TUI-Ausgaben nicht als Vertrag testen; Exit, Side Effects und JSON-Daten prüfen.
- doppelte Result- und Fehlerumrechnungen entfernen.
- Meilensteinreview durchführen und die Mutationsgrenze für echten Apply einfrieren.

## Review nach Meilenstein 4

**Ergebnis nach 4.e.C:**

- Die Definition of Done ist durch echte ZIP-, Manifest-, Ressourcen-, Repository-, Lock-, Mismatch-, Preflight- und Dry-Run-Tests abgedeckt.
- Paketauflösung und Preflight verwenden jeweils genau eine gemeinsame Pipeline; ein zweiter Repository-Validator und ein Dry-Run-Sonderparser sind nicht erforderlich.
- Toolfehler werden einmal in das primäre Apply-Ergebnis überführt; die Priorität zwischen primärem Ergebnis und Result-Bundle-Fehler ist zentral festgelegt.
- Tests behandeln Exit-Codes, Repository- und Prozesswirkungen sowie geschlossene JSON-Daten als Vertrag, nicht Text- oder TUI-Formulierungen.
- Das `ApplyMutationGate` ist als Grenze vor der ersten Repository-Mutation eingefroren; Meilenstein 5 setzt dort an, ohne den manuellen Runner oder den verbleibenden Plan fachlich zu ändern.
- Es wurde keine Mutation, Execution- oder Watcher-Funktion vorweggenommen; PatchHarbor bleibt ein kontrollierter Runner.

---

# Meilenstein 5 – Mutierender Apply-Pfad und vollständiger Auftragslebenszyklus

## Ziel

`patchharbor apply` schreibt sichere Nutzdateien atomar, führt genau einen Entrypoint kontrolliert aus und erzeugt nach jedem sicher aufgelösten Auftrag das vollständige Ergebnis.

## Scope

- zweite Zustandsprüfung unmittelbar vor der ersten Repository-Schreiboperation.
- atomare Bereitstellung jeder einzelnen Nutzdatei.
- ein manifestierter Entrypoint im Repository-CWD.
- Timeout, Strg+C und vollständiger Prozessbaum.
- Fehlerpriorität und Exit-Codes.
- Apply-JSON, Run-Log, Plain-Modus und TUI.

## Definition of Done

- Ein gültiges Paket verändert nur die vorgesehenen Nutzdateien und startet genau den manifestierten Entrypoint.
- Eine äußere Zustandsänderung vor dem ersten Schreiben führt zu keinerlei Repository-Schreibzugriff.
- Jede Datei wird einzeln atomar ersetzt; eine globale Pakettransaktion wird nicht behauptet.
- Entrypoint-Exit, Timeout und Strg+C behalten ihre primäre Priorität auch bei Bundle-Fehlern.
- Nach sicherer Auflösung wird ein Result Bundle bei Erfolg und Fehler versucht.
- Der manuelle Runner bleibt vollständig funktionsfähig und frei von Repository-Zuordnung.

---

## Step 5.a – Gültiges Patch-Paket erstmals schreiben und ausführen

**Ergebnis:** Der vollständige Happy Path von `patch.json` bis Result Bundle funktioniert mit echten Dateien und echtem Prozess.

### 5.a.W – Let it work! – Apply-Happy-Path vertikal implementieren

**Commitposition:** 61 / 96

- nach erfolgreichem Preflight sichere Zielverzeichnisse anlegen.
- jede Nutzdatei in eine temporäre Datei im jeweiligen Zielverzeichnis schreiben und atomar ersetzen.
- vorhandene reguläre Dateien ohne Nachfrage überschreiben.
- den Entrypoint ausschließlich aus dem privaten Temp-Verzeichnis mit Repository-Wurzel als CWD starten.
- Kind-STDIN schließen und Standard-Timeout 300 Sekunden anwenden.
- stdout und stderr vollständig in `logs/execution.log` erfassen.
- nach Exit 0 ein vollständiges Result Bundle mit aktuellem Zustand erzeugen.

### 5.a.R – Do it right! – Mutation, Execution und Result-Aufnahme richtig orchestrieren

**Commitposition:** 62 / 96

- `application.py` als einzigen fachlichen Orchestrator behalten.
- Payload-Schreiben, Execution und Result-Bundle-Erzeugung über klar getrennte Dienste komponieren.
- tatsächlichen Schreibfehler mit Exit 6 behandeln und Entrypoint dann nicht starten.
- keine Gesamttransaktion oder automatische globale Rückabwicklung versprechen.
- Run-ID, Warnings und erwartete sowie tatsächliche Zustandswerte durch den ganzen Auftrag tragen.

### 5.a.C – Make it clean! – Happy-Path und Datenfluss vereinfachen

**Commitposition:** 63 / 96

- doppelte Payload-Puffer, Statusobjekte und verschachtelte Try-Blöcke entfernen.
- keine Kopie des Entrypoints im Repository zurücklassen.
- Verhaltenstest auf Zielbytes, CWD, Startanzahl und Bundle-Inhalt begrenzen.
- keine Zielprojekt-Tests oder Git-Commits in PatchHarbor einbauen.

---

## Step 5.b – Race zwischen Preflight und erster Mutation schließen

**Ergebnis:** Ein fremder Editor oder Git-Prozess kann nach der ersten Prüfung keinen Patch auf einen anderen Zustand umleiten.

### 5.b.W – Let it work! – Zweite Context-Prüfung und Zielpfad-Revalidierung implementieren

**Commitposition:** 64 / 96

- unmittelbar vor der ersten Repository-Schreiboperation Base-Commit und Fingerprint erneut bestimmen.
- zweite Werte sowohl mit dem Manifest als auch mit der ersten Aufnahme vergleichen.
- bei jeder Abweichung ohne temporäre oder endgültige Datei im Repository ablehnen.
- Eltern- und Zielpfade direkt vor dem Schreiben erneut gegen Symlink, Junction und besondere Dateitypen prüfen.
- Austausch eines sicheren Elternpfads während des Preflights in einem steuerbaren Race-Test simulieren.
- bei Zustandsmismatch weiterhin das Result Bundle des tatsächlichen Zustands versuchen.

### 5.b.R – Do it right! – Mutations-Gate als einzelne überprüfbare Grenze kapseln

**Commitposition:** 65 / 96

- zweite Context-Aufnahme, Zielpfadprüfung und Erzeugung der ersten Temp-Zieldatei unmittelbar zusammenführen.
- keine bereits geöffneten unsicheren Pfadobjekte aus dem Preflight blind wiederverwenden.
- Mismatch, unsicheren Zielpfad und Schreibfehler als getrennte primäre Resultate modellieren.
- Repository-Lock während des gesamten Gates halten, aber fremde Änderungen zusätzlich erkennen.

### 5.b.C – Make it clean! – Race-Schutz und Tests stabilisieren

**Commitposition:** 66 / 96

- doppelte Context-Vergleichslogik entfernen.
- Race-Tests ohne zufällige Sleeps über Barrieren oder Hooks synchronisieren.
- keine falsche Sandbox- oder Transaktionsgarantie dokumentieren.
- Pfadprüfung nur einmal zentral definieren.

---

## Step 5.c – Entrypoint-Fehler, Timeout und Abbruch vollständig behandeln

**Ergebnis:** Alle Prozessausgänge behalten ihren spezifizierten Exit-Code und hinterlassen weder Prozessbaum noch Locks.

### 5.c.W – Let it work! – Execution-Fehlerpfade in den sicheren Apply integrieren

**Commitposition:** 67 / 96

- normalen von null verschiedenen Entrypoint-Exit exakt zurückgeben.
- Timeout mit geordnetem Stopp, Zwei-Sekunden-Frist, hartem Prozessbaumende und Exit 124 behandeln.
- Strg+C mit vollständigem Prozessbaumende und Exit 130 behandeln.
- Linux-Prozessgruppe und Windows Job Object aus der vorhandenen Execution wiederverwenden.
- bei fehlendem oder nicht startbarem Interpreter keinen Entrypoint starten.
- nach Entrypoint-Fehler, Timeout und Abbruch jeweils ein Result Bundle versuchen.
- echte Kind- und Enkelprozess-Tests ergänzen.

### 5.c.R – Do it right! – Primäres Prozessresultat und Cleanup fachlich ordnen

**Commitposition:** 68 / 96

- Priorität Benutzerabbruch, Timeout, Entrypoint-Exit und Tool-Fehler zentral abbilden.
- Entry-Point-Exit-Code, PatchHarbor-Fehlercode und Prozess-Exit-Code getrennt halten.
- Temp-Verzeichnis, Output-Handles, Prozessbaum und Repository-Lock über einen gemeinsamen Cleanup-Pfad freigeben.
- Windows-Wartepfade pollingfähig halten und `CTRL_BREAK_EVENT` nicht als PowerShell-Standardstopp verwenden.

### 5.c.C – Make it clean! – Execution-Integration und Prozess-Tests bereinigen

**Commitposition:** 69 / 96

- keine zweite Prozesssteuerung speziell für Apply behalten.
- doppelte Timeout- und Interrupt-Tests mit dem manuellen Runner konsolidieren.
- Tests auf beendete Prozesse, Exit-Codes und Logs statt konkrete Konsolenmeldungen ausrichten.
- unnötige künstliche Wartezeiten entfernen.

---

## Step 5.d – Fehlerpriorität, Notfallrettung und Apply-JSON finalisieren

**Ergebnis:** Primärer Auftrag und Bundle-Ergebnis werden in jeder Kombination korrekt berichtet und beendet.

### 5.d.W – Let it work! – Vollständige Resultatmatrix und Apply-Abschlussvertrag implementieren

**Commitposition:** 70 / 96

- erfolgreichen Auftrag plus Bundle-Fehler mit Exit 11 beenden.
- Entrypoint-Fehler plus Bundle-Fehler mit dem Entrypoint-Code beenden.
- Timeout oder Strg+C plus Bundle-Fehler mit 124 beziehungsweise 130 beenden.
- bei Bundle-Fehler `execution.log` und `run.json` best effort im Notfallverzeichnis erhalten.
- keine halbfertige ZIP unter endgültigem Namen zurücklassen.
- `apply --json` mit exakt dem spezifizierten Result-, Primary- und Bundle-Objekt ausgeben.
- rohen Entrypoint-Output im JSON-Modus ausschließlich im Log und nicht auf stdout führen.

### 5.d.R – Do it right! – Eine einzige Ergebnisquelle für Run-Log, JSON und Präsentation herstellen

**Commitposition:** 71 / 96

- alle Abschlussdarstellungen aus demselben unveränderlichen Auftragsresultat erzeugen.
- normale Entrypoint-Exits von PatchHarbor-Tool-Fehlern im JSON-Vertrag trennen.
- `not_attempted` ausschließlich vor sicherer Repository-Auflösung erlauben.
- Fehlerkategorien auf die spezifizierten `primary_result.kind`-Werte abbilden.
- sekundären Bundle-Fehler niemals den primären Fehler überschreiben lassen.

### 5.d.C – Make it clean! – Resultatmatrix und JSON-Tests vereinfachen

**Commitposition:** 72 / 96

- verzweigte Exit-Code-Berechnungen durch eine kleine Prioritätsfunktion ersetzen.
- JSON als geparstes geschlossenes Objekt testen, nicht als String-Snapshot.
- Notfalltests auf vorhandene Dateien und fehlende End-ZIP statt Textmeldungen ausrichten.
- doppelte Run-Report-Felder entfernen.

---

## Step 5.e – Darstellung, gemeinsamer Lifecycle und manuellen Runner absichern

**Ergebnis:** Apply ist interaktiv und nicht interaktiv nutzbar, ohne die stabilen 1.0.0-Verträge zu beschädigen.

### 5.e.W – Let it work! – Plain-, TUI- und Cleanup-Verhalten vollständig integrieren

**Commitposition:** 73 / 96

- Apply im TTY mit Bereichen für Source, Repository, Messages, Files, Execution und Result darstellen.
- `--plain` und Nicht-TTY ohne Cursorsteuerung verwenden.
- `--no-color` und JSON-Modus ohne Farbcodes sicherstellen.
- ANSI- und Steuersequenzen aus sichtbarer Ausgabe entschärfen, Rohlog jedoch bytegenau erhalten.
- temporäre Entrypoint-, ZIP- und STDIN-Artefakte nach Erfolg, Fehler, Timeout und Strg+C entfernen.
- `patchharbor fs run` vollständig ohne Registry-, Base- oder Fingerprintprüfung weiter betreiben.
- Regressionsfälle für Datei, Ordner, Pipe, mehrere ZIP-Skripte und Binärpayloads ausführen.

### 5.e.R – Do it right! – Gemeinsamen Runner-Lebenszyklus ohne Schichtenbruch herstellen

**Commitposition:** 74 / 96

- Execution frei von Registry-, Git-, Result-Bundle- und TUI-Semantik halten.
- Presentation nur Zustände darstellen und keine fachliche Entscheidung treffen lassen.
- Run-Log und Rolling Buffer zwischen manuellem Runner und Apply sinnvoll wiederverwenden.
- CLI nur öffentliche Anwendungsgrenzen komponieren lassen.
- Exit-Code- und Cleanup-Verhalten über beide Ausführungswege vereinheitlichen.

### 5.e.C – Make it clean! – Apply-Meilenstein bereinigen und reviewen

**Commitposition:** 75 / 96

- doppelte CLI-, Output- und Cleanup-Pfade entfernen.
- TUI-Tests auf Begrenzung, Redraw und Cleanup statt exakte Frames oder Texte ausrichten.
- keine Netzwerk-, Testmanager-, Commit- oder Plugin-Funktion sichtbar machen.
- Meilensteinreview durchführen und Apply als Core-Vertrag einfrieren.

## Review nach Meilenstein 5

- Definition of Done gegen das reale Verhalten prüfen.
- falsche Annahmen und unnötig gewordene spätere Schritte dokumentieren.
- verbleibenden Plan nur minimal anpassen.
- sicherstellen, dass PatchHarbor weiterhin ein kontrollierter Runner bleibt.
- Review im letzten Clean-Commit des Meilensteins abschließen; kein separater Review-Commit.

**Review-Ergebnis nach 5.e.C:**

- Die Definition of Done ist durch Dry-Run, mutierenden Apply, Prozessfehler, Result Bundle sowie Plain-, JSON- und TUI-Betrieb erfüllt.
- `ApplyMutationGate`, `RunReport` und die gemeinsame Execution-Grenze sind als Core-Vertrag für 1.1.0 eingefroren.
- PatchHarbor übernimmt weiterhin weder Netzwerktransport noch Zielprojekttests, Git-Commits, Testmanagement oder Plugin-Orchestrierung.
- Meilenstein 6 ergänzt ausschließlich den separaten Watcher und verändert den endenden Core-Auftrag nicht.

---

# Meilenstein 6 – Separater PatchHarbor Watcher

## Ziel

Eine dünne Linux-Komponente erkennt abgeschlossene Download-Dateien und delegiert sie unverändert an die öffentliche Apply-Grenze, ohne Core-Logik zu duplizieren.

## Scope

- nicht rekursive Überwachung eines konfigurierten Eingangsordners.
- Stabilitätsprüfung fertiger Downloads.
- Delegation an `patchharbor apply --json`.
- Vermeidung ungeplanter Wiederverarbeitung unveränderter Dateien.
- Pfadgrenzen zu Repositorys und Result-Ordnern.
- systemd-fähiger Benutzerbetrieb und journald-Logging.

## Definition of Done

- Der Watcher führt keine Manifest-, Git-, Fingerprint-, Lock-, Execution- oder Bundle-Logik selbst aus.
- Unfertige oder offensichtliche Browser-Tempdateien werden nicht delegiert.
- Eine unveränderte Datei wird nach Neustart nicht ungeplant erneut verarbeitet.
- Eingangsordner liegt außerhalb aller registrierten Repositorys und überlappt keinen Result-Ordner.
- Result Bundles werden niemals erneut als Eingabepaket behandelt.
- Der Watcher ist separat aktivierbar; PatchHarbor Core bleibt ein endender Einzelauftrag.

---

## Step 6.a – Abgeschlossene Download-Datei erkennen und an Apply delegieren

**Ergebnis:** Der separate Watcher verarbeitet eine stabile Datei genau über den öffentlichen Core-Aufruf.

### 6.a.W – Let it work! – Minimalen Watcher-Happy-Path als separate Komponente liefern

**Commitposition:** 76 / 96

- einen separaten Watcher-Einstiegspunkt im Paket einführen; Arbeitsname des Konsolenskripts ist `patchharbor-watcher`.
- einen konfigurierten Eingangsordner periodisch und nicht rekursiv scannen.
- nur reguläre Dateien berücksichtigen und offensichtliche Browser-Tempnamen ignorieren.
- Größe und Änderungszeit über mindestens zwei Beobachtungen als Stabilitätskriterium verwenden.
- eine stabile Datei unverändert an `patchharbor apply --json` übergeben.
- Prozess-Exit-Code und parsebares Abschlussobjekt im Betriebslog erfassen.
- Integrationstest mit einem echten Apply-Stubprozess ergänzen, ohne Core-Logik zu mocken.

### 6.a.R – Do it right! – Watcher und Core strikt voneinander trennen

**Commitposition:** 77 / 96

- Watcher kennt nur Dateistabilität und die öffentliche Subprozessgrenze.
- keine `patch.json`, Registry, Fingerprints oder Repository-Pfade im Watcher auswerten.
- Signalbehandlung und Beendigung des Watcher-Loops sauber kapseln.
- fehlerhafte oder nicht parsebare Apply-Antwort protokollieren, aber nicht fachlich neu interpretieren.
- keinen Hintergrundloop in `patchharbor` Core einbauen.

### 6.a.C – Make it clean! – Watcher-Grundlage vereinfachen

**Commitposition:** 78 / 96

- keine Inotify-Abhängigkeit, asynchrone Architektur oder Plugin-Registry einführen.
- Polling und Stabilitätszustand auf wenige klare Daten reduzieren.
- Tests auf Delegationsanzahl und Dateistabilität statt Logtext ausrichten.
- temporäre Testdateien und Prozesse zuverlässig aufräumen.

---

## Step 6.b – Wiederverarbeitung und Pfadüberlappungen verhindern

**Ergebnis:** Der Watcher verarbeitet unveränderte Inputs nicht erneut und kann keine Repository- oder Result-Bäume beobachten.

### 6.b.W – Let it work! – Persistente Dateidentität und Eingangsordner-Grenzen implementieren

**Commitposition:** 79 / 96

- eine unveränderte Datei über kanonischen Pfad und stabilen Inhalts-Hash als bereits verarbeitet erkennen.
- eine inhaltlich geänderte Datei am selben Pfad erneut zulassen.
- Watcher-Zustand atomar im benutzerspezifischen Zustandsverzeichnis speichern.
- Eingangsordner physisch kanonisieren und gegen alle registrierten Repository-Wurzeln prüfen.
- Überlappung in beide Richtungen mit allen Result-Ordnern ablehnen.
- Dateien mit PatchHarbor-Result-Bundle-Marker niemals an Apply delegieren.
- Repository-Registrierung um die Rückwärtsprüfung gegen konfigurierte Watcher- und Result-Pfade ergänzen.

### 6.b.R – Do it right! – Pfadpolitik und Watcher-Zustand konsistent machen

**Commitposition:** 80 / 96

- dieselbe physische Grenzprüfung wie Registry und Result Bundle verwenden.
- Watcher-State-Schreiben mit temporärer Datei und atomarem Austausch absichern.
- Stabilitätsbeobachtung, Inhaltsidentität und Verarbeitungsstatus getrennt modellieren.
- Result-Bundle-Erkennung nur zur Schleifenvermeidung nutzen und nicht als Paketparser nachbauen.

### 6.b.C – Make it clean! – Deduplizierung und Pfadtests bereinigen

**Commitposition:** 81 / 96

- keine permanente allgemeine Dateidatenbank oder Logrotation aufbauen.
- alte verarbeitete Einträge nur minimal verwalten; keine unbestellte Aufbewahrungsstrategie hinzufügen.
- Race-Tests ohne lange Polling-Wartezeiten stabilisieren.
- Grenztests auf kanonische Pfadbeziehungen statt Stringpräfixe ausrichten.

---

## Step 6.c – systemd-Betrieb und Orchestratorgrenze abschließen

**Ergebnis:** Der Watcher kann als schlanker Linux-Benutzerdienst betrieben werden, ohne Repo Assist oder den Core zu vereinnahmen.

### 6.c.W – Let it work! – Systemd-fähigen Betriebsweg und Neustartverhalten bereitstellen

**Commitposition:** 82 / 96

- eine minimale systemd-User-Unit beziehungsweise installierbare Vorlage für den separaten Einstiegspunkt bereitstellen.
- Konfiguration des Eingangsordners über die benutzerspezifische Konfigurationsgrenze ermöglichen.
- Betriebslogs an stdout/stderr für journald ausgeben und keine eigene Logrotation implementieren.
- Neustarttest: bereits erfolgreich verarbeitete unveränderte Datei wird nicht erneut delegiert.
- Dienst standardmäßig nicht automatisch aktivieren.
- die Betriebsregel dokumentieren, dass Watcher und Repo Assist nicht für dieselben Repositorys gleichzeitig aktiviert werden.
- Repository-Lock als letzte technische Schutzschicht bei dennoch konkurrierenden Aufträgen nachweisen.

### 6.c.R – Do it right! – Watcher-Packaging und Integrationsgrenzen richtig schneiden

**Commitposition:** 83 / 96

- Watcher-Modul und Konsoleneinstieg getrennt vom Core-CLI halten.
- Repo Assist und PromptBridge nicht als Python-Abhängigkeiten oder interne Module einführen.
- keine nicht spezifizierte automatische Repo-Assist-Erkennung oder Netzwerkkommunikation erfinden.
- systemd-spezifische Dateien auf Linux beschränken; Core bleibt auf Windows installierbar.

### 6.c.C – Make it clean! – Watcher-Meilenstein minimal dokumentieren und reviewen

**Commitposition:** 84 / 96

- Betriebsdokumentation auf Installation, Konfiguration, Aktivierung und Deaktivierung begrenzen.
- keine allgemeine Daemon-Verwaltung, Weboberfläche oder Service-Orchestrierung hinzufügen.
- Architecture-Test sicherstellen lassen, dass der Watcher nur die öffentliche Core-Grenze kennt.
- Meilensteinreview durchführen und Watcher-Scope schließen.

## Review nach Meilenstein 6

**Review-Ergebnis nach 6.c.C:**

- Die Definition of Done ist durch Stabilitäts-, Neustart-, Deduplizierungs-, Pfadgrenzen-, Schleifenvermeidungs-, Signal-, systemd- und echte Delegationstests abgedeckt.
- Der Watcher ist als separates Paket und eigener Konsoleneinstieg abgegrenzt; seine einzige fachliche Core-Verbindung bleibt der öffentliche Subprozessaufruf `patchharbor apply --json`.
- Gemeinsame Core-Nutzung ist auf bereits vorhandene Pfad- und Dateisystemgrenzen begrenzt; Manifest-, Registry-, Git-, Fingerprint-, Lock-, Execution- und Result-Bundle-Logik bleiben vollständig im Core.
- Die Betriebsdokumentation bleibt auf Installation, Konfiguration, Aktivierung, Deaktivierung und journald beschränkt; eine allgemeine Daemon-Verwaltung oder Service-Orchestrierung ist nicht erforderlich.
- Repo Assist und PromptBridge bleiben externe Komponenten, und der verbleibende Release-Plan benötigt keine fachliche Änderung. PatchHarbor Core bleibt ein endender kontrollierter Einzelauftrag.

---

# Meilenstein 7 – Regression, Plattformen und Release 1.1.0

## Ziel

Die vollständige 1.1.0-Spezifikation ist auf Linux und Windows verhaltensorientiert geprüft, pipx-fähig paketiert und nur mit grünen blockierenden Gates freigabefähig.

## Scope

- vollständige 1.0.0-Regression.
- durchgängige 1.1.0-Akzeptanzflüsse.
- Architektur- und Scope-Audit.
- Ubuntu 24.04 und Ubuntu 26.04 als blockierende Docker-/CI-Gates.
- echter Windows-Runner mit Windows PowerShell und PowerShell 7.
- Wheel, Source-Distribution, pipx, minimale README und Release-Audit.

## Definition of Done

- Alle fortgeltenden 1.0.0-Verträge sind grün.
- Alle neuen Pflichtszenarien aus Spezifikationsabschnitt 22.3 sind abgedeckt.
- Ubuntu 24.04, Ubuntu 26.04 und Windows sind blockierende grüne Release-Gates.
- Wheel und Source-Distribution enthalten nur den vereinbarten Scope und laufen nach pipx-Installation.
- Keine ausgeschlossene Funktion ist öffentlich oder als Runtime-Modul enthalten.
- Dokumentation bleibt kurz und beschreibt ausschließlich tatsächlich implementiertes Verhalten.

---

## Step 7.a – Architektur und vollständige Akzeptanzflüsse auditieren

**Ergebnis:** Die gesamte Produktspezifikation ist durch wenige durchgängige und gezielte Verhaltenstests abgedeckt.

### 7.a.W – Let it work! – End-to-End-Akzeptanz für den kompletten 1.1.0-Workflow ergänzen

**Commitposition:** 85 / 96

- einen durchgängigen Flow `register → context → bundle → dry-run → apply → result bundle` mit echtem Repository testen.
- Erfolg, Zustandsmismatch, Entrypoint-Fehler und Bundle-Fehler als separate Akzeptanzflüsse prüfen.
- Watcher-Delegation in einen echten Apply-Aufruf integrieren.
- alle fortgeltenden Datei-, Ordner-, Pipe-, ZIP-, Interpreter-, TUI-, Logging- und Ressourcenverträge aus 1.0.0 erneut ausführen.
- jeden Testlauf mit Pytest- und äußerem Suite-Timeout begrenzen.
- langsamste Tests sichtbar machen, ohne Retries als Standard einzuführen.

### 7.a.R – Do it right! – Modulgrenzen und Testpyramide gegen die Spezifikation prüfen

**Commitposition:** 86 / 96

- Importgraph auf Zyklen und die vereinbarte Richtung prüfen.
- `application.py` als einzigen Orchestrator bestätigen.
- Registry, State, Lock, Manifest, Result Bundle, Execution, Presentation und Watcher auf getrennte Verantwortungen prüfen.
- doppelte Happy-Path-Subprozesse durch wenige Akzeptanztests und gezielte Fehler-E2E-Tests ersetzen.
- keine Tests auf private Klassen, Funktionsnamen oder Konsolentexte behalten.

### 7.a.C – Make it clean! – Architektur- und Testballast entfernen

**Commitposition:** 87 / 96

- tote Module, ungenutzte Optionen und spekulative Abstraktionen löschen.
- keine Module `utils`, `helpers`, `common`, Plugin-Registry oder asynchronen Core behalten.
- verbotene Begriffe und Scope wie WebSocket, Clipboard, SSH, Save-Modus, Testmanager und Git-Commit-Funktionen auditieren.
- doppelte oder ausschließlich implementierungsnahe Tests entfernen.

---

## Step 7.b – Linux- und Ubuntu-Gates vollständig blockierend machen

**Ergebnis:** Linux-Verhalten einschließlich Locks, Git, Bash, Prozesse, Bundles und Watcher ist auf beiden Ubuntu-Versionen reproduzierbar grün.

### 7.b.W – Let it work! – Ubuntu 24.04 und 26.04 als vollständige Integrationsgates ausführen

**Commitposition:** 88 / 96

- Docker-Integration auf Ubuntu 24.04 und Ubuntu 26.04 mit Python 3.12, Git, Bash, pipx und Pytest-Timeout ausführen.
- Container mit Init-Prozess für Prozessbaumtests starten.
- Registry- und Repository-Locks mit echten konkurrierenden Prozessen prüfen.
- Fingerprint, Apply, Result Bundle und Watcher auf realen Dateisystemen testen.
- Build-, Test- und Docker-Läufe jeweils mit getrennten äußeren Timeouts begrenzen.
- beide Ubuntu-Lanes im Acceptance-Workflow blockierend konfigurieren.

### 7.b.R – Do it right! – Linux-CI reproduzierbar und diagnosefähig machen

**Commitposition:** 89 / 96

- Dev-Abhängigkeiten aus `pyproject.toml` vollständig installieren und verifizieren.
- Locale, Git-Konfiguration und Testumgebung deterministisch setzen.
- keine langen Sleeps, zufälligen Retries oder Host-Verzeichnisannahmen verwenden.
- Docker-Logs und langsamste Tests bei Fehlern vollständig bereitstellen.

### 7.b.C – Make it clean! – Linux-Gates und Docker-Helfer bereinigen

**Commitposition:** 90 / 96

- doppelte Docker-Buildpfade und veraltete Preview-Ausnahmen entfernen.
- Ubuntu 26.04 nicht mehr als `continue-on-error` behandeln.
- Shellskripte auf klare Fehlerweitergabe und Cleanup reduzieren.
- keine zusätzliche Linux-Distribution ohne spezifizierten Bedarf hinzufügen.

---

## Step 7.c – Windows-Verhalten auf echtem Runner absichern

**Ergebnis:** Registry, Pfade, Locks, PowerShell, Prozessbaum und JSON funktionieren auf dem blockierenden Windows-Runner.

### 7.c.W – Let it work! – Native Windows-Akzeptanz für alle sicherheitsrelevanten Pfade ergänzen

**Commitposition:** 91 / 96

- Windows-Benutzerverzeichnisse unter `%APPDATA%` und `%LOCALAPPDATA%` prüfen.
- Repository-Locks mit echten parallelen Windows-Prozessen testen.
- Junctions, reservierte Gerätenamen, Case-Kollisionen und nicht portable Pfade ablehnen.
- Windows PowerShell ohne Profil, ohne Interaktion und ohne Execution-Policy-Bypass ausführen.
- PowerShell 7 als zusätzliche blockierende Lane verwenden, sobald verfügbar.
- Timeout, Strg+C, Job Object und Kind-/Enkelprozessende nativ testen.
- JSON-Pfade, UTF-8 und CRLF-neutralen sichtbaren Vertrag prüfen.

### 7.c.R – Do it right! – Windows-Plattformgrenzen und Portabilität richtig härten

**Commitposition:** 92 / 96

- Junction-, Pfad- und Lock-Erkennung in `platform/` kapseln.
- lange blockierende Waits vermeiden und Python-Interrupts pollingfähig halten.
- keine festen Unix-Pfade, LF-Annahmen oder kurzfristigen PowerShell-Starttimeouts in Tests verwenden.
- Rohlogs bytegenau belassen und nur sichtbare Darstellung normalisieren.

### 7.c.C – Make it clean! – Windows-Tests und Plattformcode bereinigen

**Commitposition:** 93 / 96

- plattformübergreifende Tests nicht unnötig duplizieren; nur native Grenzen separat halten.
- temporäre Windows-Pfade kanonisch statt als Stringliterale vergleichen.
- keine Windows-spezifische Sonderarchitektur außerhalb `platform/` verteilen.
- flaky Timingannahmen und Ausgabe-Snapshots entfernen.

---

## Step 7.d – Version 1.1.0 paketieren und final freigeben

**Ergebnis:** Das veröffentlichbare Paket enthält die vollständige spezifizierte Funktion und keine halbfertige Oberfläche.

### 7.d.W – Let it work! – Release-Paket, pipx-Smoke und minimale Bedienoberfläche herstellen

**Commitposition:** 94 / 96

- Paketversion und Release-Metadaten auf 1.1.0 setzen.
- Wheel und Source-Distribution aus einem sauberen expliziten Quellbestand bauen.
- `patchharbor` und den separaten Watcher-Einstiegspunkt nach pipx-Installation smoke-testen.
- exakten Laufzeitmodulbestand, Konsolen-Entry-Points, Lizenz und fehlende externe Runtime-Abhängigkeiten prüfen.
- Help-Screens nur für tatsächlich implementierte Befehle und Optionen anbieten.
- README auf Installation, Kernablauf, vollständigen Snapshot-/Secret-Hinweis und Watcher-Betrieb begrenzen.
- Release-Audit auf Spezifikation, Changelog, Cleanup-Plan und diesen Implementierungsplan ausrichten.

### 7.d.R – Do it right! – Release-Artefakte und öffentliche Grenzen final auditieren

**Commitposition:** 95 / 96

- Wheel und Source-Distribution aus derselben Version und denselben Metadaten erzeugen.
- veraltete lokale `build/`-Inhalte sicher ausschließen.
- öffentliche CLI exakt auf die spezifizierten Optionen begrenzen.
- Repo Assist und PromptBridge als externe Verantwortungen bestätigen.
- keine Sandbox-, Authentifizierungs- oder Transaktionsgarantie suggerieren.

### 7.d.C – Make it clean! – Finalen Ballast entfernen und 1.1.0-Gates schließen

**Commitposition:** 96 / 96

- tote Testhilfen, ungenutzte Codepfade und doppelte Dokumentation entfernen.
- vollständige lokale Suite, alle Testgruppen, beide Ubuntu-Docker-Läufe und echten Windows-Workflow ausführen.
- Release nur bei grünen blockierenden Gates auf dem exakten finalen Commit zulassen.
- Restplan reviewen; keine neue 1.1.x-Funktion in den finalen Clean-Commit aufnehmen.

## Review nach Meilenstein 7

- Definition of Done gegen das reale Verhalten prüfen.
- falsche Annahmen und unnötig gewordene spätere Schritte dokumentieren.
- verbleibenden Plan nur minimal anpassen.
- sicherstellen, dass PatchHarbor weiterhin ein kontrollierter Runner bleibt.
- Review im letzten Clean-Commit des Meilensteins abschließen; kein separater Review-Commit.

---

# 5. Abdeckung der Spezifikation

| Spezifikationsbereich | Geplante Umsetzung |
|---|---|
| Abschnitte 2–4: Produktgrenze, Komponenten, Plattformpfade | 1.a–1.d, 3.d, 6.a–6.c, 7.b–7.d |
| Abschnitt 5: öffentliche CLI und JSON-Verträge | 1.a–1.b, 2.a, 3.e, 4.e, 5.d–5.e, 7.d |
| Abschnitte 6–12: fortgeführter manueller Runner | 5.e sowie vollständige Regression in 7.a–7.c |
| Abschnitt 13: Registry und lokale Identität | 1.a–1.d |
| Abschnitt 14: Context und `patchharbor-state-v1` | 2.a–2.f |
| Abschnitt 15: sicheres Patch-Paket | 4.a–4.d |
| Abschnitte 16–17: Repository-Lock, Apply-Reihenfolge und Dry-Run | 1.d, 4.c–4.e, 5.a–5.b |
| Abschnitt 18: primäres Ergebnis, Bundle-Fehler und Run-Bericht | 3.e, 4.e, 5.c–5.d |
| Abschnitt 19: vollständiges Result Bundle | 3.a–3.e sowie Integration in 4.e und 5.a–5.d |
| Abschnitt 20: Exit-Codes | 1.b, 1.d, 2.e, 3.e, 4.a–4.e, 5.a–5.d |
| Abschnitt 21: Architekturgrenzen | Right- und Clean-Commits aller Meilensteine, Abschlussaudit 7.a |
| Abschnitt 22: Teststrategie und Release | verbindliche Planregeln sowie 7.a–7.d |
| Abschnitte 23–24: ausgeschlossener Scope und Repo-Assist-Abgrenzung | 5.e, 6.c, 7.a und 7.d |
| Abschnitte 25–26: Migration und Zusammenfassung | Cleanup als Voraussetzung; Implementierung durch Meilensteine 1–7 |

---

# 6. Verbindliche Commit- und Patch-Gates

- Jeder Commit besitzt genau eine erkennbare Absicht.
- Der Work-Commit enthält Feature und Verhaltenstest gemeinsam.
- Der Right-Commit ändert Grenzen und Fehlerbehandlung, aber keinen Scope.
- Der Clean-Commit entfernt Ballast und führt kein neues Produktverhalten ein.
- Nach jedem Commit laufen gezielte Tests und die bis dahin relevante vollständige Suite mit harten Timeouts.
- Bei Fehlern wird nicht committed; der Ausgangsstand wird vollständig wiederhergestellt.
- Jeder Patch ist idempotent und erzeugt beim erneuten Lauf keinen zweiten identischen Commit.
- Jeder Patch erzeugt bei Erfolg und Fehler ein Ergebnis-ZIP mit Log, Testlog, Git-Stand und Repository-Snapshot.
- Cross-Platform-Verhalten wird nicht durch Linux-only Mocks als erledigt betrachtet.
- Ein Meilenstein gilt erst als abgeschlossen, wenn sein letztes C-Ergebnis und alle bis dahin bindenden Gates grün sind.

---

# 7. Bewusst nicht Teil dieses Plans

- Netzwerk- oder Chattransport im PatchHarbor Core.
- Clipboard-, SSH- oder WebSocket-Quelle.
- öffentliches Plugin-System.
- Zielprojekt-Testmanagement oder Testbewertung.
- Git-Commit-, Branch-, Tag- oder Release-Verwaltung im Produkt.
- interaktive Kindskripte.
- Inline-Dateien oder automatische Base64-Dekodierung.
- rekursive Ordnersuche oder rekursive Archivauflösung.
- globale Pakettransaktion oder automatische Vollrückabwicklung.
- dauerhafte zentrale Logrotation im Core.
- automatische Secret-Erkennung.
- Submodule im sicheren 1.1.0-Kontext.

Die Betriebsregel „Watcher oder Repo Assist für dieselben Repositorys“ wird ohne ein nicht spezifiziertes Erkennungsprotokoll umgesetzt: Der Watcher ist separat und standardmäßig deaktiviert, die Aktivierung wird grob dokumentiert, und die Repository-Sperre verhindert technische Gleichzeitigkeit. Eine automatische Repo-Assist-Erkennung würde eine neue Produktspezifikation erfordern und wird nicht stillschweigend erfunden.

---

# 8. Gesamtzählung und Abschlusskriterium

- **Meilensteine:** 7
- **Steps:** 32
- **Commits:** 96
- **Let it work!-Commits:** 32
- **Do it right!-Commits:** 32
- **Make it clean!-Commits:** 32

PatchHarbor 1.1.0 ist nach diesem Plan vollständig umgesetzt, wenn:

- alle 96 geplanten W-R-C-Commits bestätigt sind.
- Registry, Context, Fingerprint, Result Bundle, Dry-Run, Apply und Watcher wie spezifiziert funktionieren.
- alle fortgeltenden 1.0.0-Verträge grün bleiben.
- alle neuen Pflichtszenarien verhaltensorientiert abgedeckt sind.
- Ubuntu 24.04, Ubuntu 26.04 und der echte Windows-Runner grün sind.
- Wheel und Source-Distribution nach pipx-Installation funktionieren.
- keine ausgeschlossene Funktion und keine halbfertige öffentliche Oberfläche enthalten ist.

Die Leitlinie für jeden Step lautet unverändert:

> **Let it work! → Do it right! → Make it clean!**

Erst den kleinsten vertikalen Durchlauf herstellen, dann fachlich richtig schneiden und anschließend konsequent vereinfachen.
