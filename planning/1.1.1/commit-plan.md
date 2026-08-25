# PatchHarbor 1.1.1 – W-R-C-Commit-Plan

**Ziel:** Gemeinsamen Exchange-Ordner und eine verbindliche Chat-Initialisierung auf der vollständig implementierten 1.1.0-Basis liefern.

**Vorgesehener Repository-Pfad:** `planning/1.1.1/commit-plan.md`<br>
**Vorbereitender Commit außerhalb dieses Zählers:** `docs: define PatchHarbor 1.1.1 implementation plan`<br>
**Planstatus:** Umsetzung noch nicht begonnen; 0 / 33 W-R-C-Plan-Commits.<br>
**Umfang:** 5 Meilensteine, 11 Steps, 33 W-R-C-Plan-Commits.

---

## 1. Ausgangspunkt und Abgrenzung

Dieser Plan beginnt nach dem vollständig abgeschlossenen 1.1.0-Plan mit 96 / 96 Commits.

Der vorbereitende 1.1.1-Commit hat ausschließlich:

- `spec/SPECIFICATION.md` auf das Ziel 1.1.1 fortgeschrieben,
- `spec/SPECIFICATION_CHANGELOG.md` ergänzt,
- diesen Commit-Plan angelegt,
- den Release-Audit um die neue Planstruktur erweitert.

Er hat weder Produktionscode noch README, CLI, Paketversion oder `CHAT_INSTRUCTIONS.md` implementiert. Diese Änderungen erfolgen ausschließlich in den nachfolgenden Plan-Commits.

Die Zielversion bleibt im Produktionscode bis zum finalen Release-Commit `1.1.0`. Erst `5.b.C` setzt die Paketversion auf `1.1.1`.

Es gibt keine produktiv zu migrierende 1.1.0-Konfiguration. Deshalb entstehen ausdrücklich:

- kein Leser für eine alte `watcher.json`,
- kein Leser für eine alte `paths.json`,
- kein dualer Konfigurationsvertrag,
- kein stiller Fallback auf den früheren Standard-Result-Ordner.

Zwischencommits dürfen vorhandene 1.1.0-Module vorübergehend noch verwenden, solange jeder Commit grün bleibt. Der finale 1.1.1-Zustand besitzt jedoch nur den neuen Vertrag.

---

## 2. Verbindliches W-R-C-Prinzip

Jeder Step besteht aus genau drei Plan-Commits und liefert nach jedem Commit ein lauffähiges Repository.

### W – Let it work!

- den kleinsten vertikalen benutzbaren Durchlauf herstellen,
- Feature und zugehörigen Verhaltenstest im selben Commit liefern,
- echte Dateien, echte Git-Repositories, echte ZIPs und echte Prozesse bevorzugen,
- Fehlerfälle nur soweit ergänzen, wie sie für den ersten funktionierenden Durchlauf erforderlich sind.

### R – Do it right!

- Verantwortlichkeiten und Abhängigkeitsrichtung korrekt schneiden,
- Sicherheits-, Fehler-, Race-, Cleanup- und Plattformgrenzen vollständig härten,
- Spezifikation und bestehende Verträge vollständig erfüllen,
- kein verstecktes neues Feature einführen.

### C – Make it clean!

- Doppelungen, tote Pfade und temporäre Kompatibilitätsreste entfernen,
- Namen, Datenfluss und Tests vereinfachen,
- Architektur-Audit und Dokumentation konsistent halten,
- kein neues Produktverhalten einführen.

Der Plan-Zähler zählt ausschließlich diese 33 regulären Plan-Commits. Ein Fix erhält die Unterkennung `<PLAN-ID>-FIX<n>`, verwendet eine Commit-Message mit `Fix`, und verändert den Plan-Zähler nicht. Ein Off-Plan-Commit erhält eine frei gewählte sinnvolle Kennung und Message und ist sichtbar als `OFF-PLAN` zu markieren.

---

## 3. Verbindliche Arbeits-, Test- und Commit-Regeln

Für jeden Plan-Commit gilt:

- Vor der Umsetzung werden aktueller Result-Bundle-Zustand, dieser Commit-Plan und die zugehörigen Spezifikationsabschnitte gegeneinander geprüft.
- Die Spezifikation ist der fachliche Vertrag; der Commit-Plan ist die geplante Zerlegung.
- Eine kleine eindeutig zum Commit gehörende Lücke darf im selben Scope geschlossen werden.
- Eine merkliche Scope-Erweiterung, ein Widerspruch, eine fehlende Voraussetzung oder eine unlogische Vorgabe führt vor der Umsetzung zu einer standardisierten Rückfrage beziehungsweise STOP-Ausgabe.
- Der Patch enthält genau einen Plan-Commit, sofern der Benutzer nicht ausdrücklich einen Fix oder Off-Plan-Schritt verlangt.
- Die exakte Commit-Message wird aus diesem Plan übernommen und nicht kreativ umformuliert.
- Der Entrypoint führt mindestens die für die Änderung passenden Tests mit harten Timeouts aus; bei breitem oder riskantem Scope läuft die vollständige Suite.
- Ein roter Test oder ein anderer Entrypoint-Fehler erzeugt keinen Git-Commit.
- PatchHarbor verspricht keine globale Rückabwicklung. Der tatsächlich zurückgebliebene Zustand und vollständige stdout/stderr werden soweit möglich im automatischen Result Bundle erfasst.
- Der Patch-Entrypoint ruft nicht selbst `patchharbor bundle` auf. `patchharbor apply` übernimmt den Result-Bundle-Versuch nach sicherer Repository-Auflösung.
- Erst ein grüner Testlauf darf den exakt einen vorgesehenen Git-Commit erzeugen.
- Nach dem lokalen Apply wird das erzeugte Result Bundle in den Chat zurückgegeben; der Chat prüft zuerst `logs/run.json`, danach bei Bedarf `logs/execution.log` und den realen Snapshot.

Empfohlener vollständiger lokaler Testlauf:

```bash
PATCHHARBOR_TEST_TIMEOUT_SECONDS=120 \
PATCHHARBOR_TEST_SUITE_TIMEOUT_SECONDS=600 \
./scripts/test.sh
```

Release-nahe Commits führen zusätzlich die passenden Docker-, Packaging- und Plattform-Gates mit eigenen äußeren Timeouts aus.

---

## 4. Plan- und Chat-Fortschritt

Der Chat liest Kennung, Commitposition, Commit-Message und Scope aus diesem Plan.

Kann der bereits erreichte Planstand aus aktuellem Chat, aktuellem Result Bundle und eindeutigem Repository-Zustand nicht zuverlässig bestimmt werden, darf der Chat nicht raten. Er stoppt mit `PLAN_POSITION_UNKNOWN` und fragt nach dem letzten bestätigten Plan-Commit.

Bei jedem fertigen Patch zeigt die Chat-UI mindestens:

- `PLAN`, `FIX` oder `OFF-PLAN`,
- Commit-Kennung,
- Position und Gesamtzahl der Plan-Commits, soweit anwendbar,
- exakte Commit-Message,
- verwendeten Commit-Plan,
- verwendete Spezifikation,
- fünf bis zehn kurze Zeilen zu Änderungen und Tests,
- verbleibende Plan-Commits.

`PATCH BEREIT` darf erst erscheinen, wenn genau eine herunterladbare Patch-Datei tatsächlich erzeugt wurde. Die Ausgabe beginnt und endet exakt mit:

```text
🟩🟩 PATCH BEREIT 🟩🟩
```

---

## 5. Meilensteinübersicht

| Meilenstein | Name | Steps | Commits | Ergebnis |
|---:|---|---:|---:|---|
| 1 | Gemeinsame Konfiguration und Pfadgrenze | 2 | 6 | `config.json` ist die einzige Benutzerkonfiguration für einen sicheren Exchange-Ordner. |
| 2 | Exchange-Ausgabe und automatische Paketauswahl | 3 | 9 | Bundles landen standardmäßig im Exchange-Ordner und `apply` findet genau ein passendes Paket ohne Pfadangabe. |
| 3 | Watcher auf denselben Vertrag umstellen | 2 | 6 | Core und Watcher teilen Konfiguration, Klassifikation und persistente Dateidentität. |
| 4 | Chat-Initialisierung und deterministische UI | 2 | 6 | `CHAT_INSTRUCTIONS.md` initialisiert einen neuen Chat und erzwingt Workflow, Plan-/Spec-Prüfung und schmale Statusausgaben. |
| 5 | Bedienung, Akzeptanz und Release 1.1.1 | 2 | 6 | README, Help, plattformübergreifende Gates, Packaging und Release sind konsistent und grün. |
| **Gesamt** |  | **11** | **33** | Vollständige Umsetzung und Freigabereife der Spezifikation 1.1.1. |

Die Reihenfolge ist absichtlich:

```text
config.json und Pfadpolitik
→ Result-Bundle-Ziel
→ automatische Apply-Auswahl
→ persistente Dateidentität
→ Watcher
→ CHAT_INSTRUCTIONS.md und UI
→ README, Akzeptanz und Release
```

---

# Meilenstein 1 – Gemeinsame Konfiguration und Pfadgrenze

## Ziel

Eine einzige benutzerspezifische `config.json` legt den Exchange-Ordner plattformübergreifend und atomar fest.

## Definition of Done

- Linux, Termux-kompatible Linux-Umgebungen und Windows verwenden die spezifizierten Benutzerpfade.
- Das Format-1-Schema ist geschlossen und direkt editierbar.
- CLI und direkter Dateiinhalt führen zum selben kanonischen Modell.
- Exchange-Ordner und registrierte Repositorys überlappen sich in keiner Richtung.
- `register` fragt den Exchange-Ordner nicht ab.

## Step 1.a – Allgemeine `config.json` vertikal bereitstellen

**Ergebnis:** Ein Benutzer kann den gemeinsamen Exchange-Ordner sicher setzen und anzeigen.

### 1.a.W – Let it work! – Exchange-Konfiguration und CLI einführen

**Commitposition:** 1 / 33<br>
**Commit-Message:** `feat(config): add shared exchange directory configuration`

- allgemeines Core-Modul für `config.json` anlegen,
- Format-1-Schema mit `format_version` und `exchange_directory` implementieren,
- `patchharbor configure exchange-directory VERZEICHNIS` einführen,
- `patchharbor configure show` einführen,
- Linux- und Windows-Konfigurationspfade über die bestehende Plattformgrenze bestimmen,
- Happy-Path-CLI- und Dateiverhalten testen.

### 1.a.R – Do it right! – Konfigurationspersistenz und Validierung härten

**Commitposition:** 2 / 33<br>
**Commit-Message:** `fix(config): harden exchange configuration persistence`

- unbekannte und fehlende Felder strikt ablehnen,
- absoluten Pfad, Verzeichnistyp und physische Kanonisierung prüfen,
- Zielverzeichnis bei CLI-Konfiguration sicher anlegen,
- direkte gültige und ungültige Dateibearbeitung testen,
- atomaren Austausch, LF-Abschluss, UTF-8 und Fehlerpriorität absichern,
- Konfigurationsfehler von Registry- und Result-Bundle-Fehlern sauber trennen.

### 1.a.C – Make it clean! – Konfigurationsgrenze vereinfachen

**Commitposition:** 3 / 33<br>
**Commit-Message:** `refactor(config): simplify the shared configuration boundary`

- lose Pfadstrings durch kleine unveränderliche Modelle ersetzen,
- doppelte JSON-, Dateischreib- und Pfadhelfer entfernen,
- CLI, Application und Konfigurationsmodul nach dem gerichteten Schichtenmodell ausrichten,
- Architektur- und Release-Inventar für neue Runtime-Module aktualisieren,
- Tests auf fachlich unterschiedliche Fälle reduzieren.

## Step 1.b – Exchange-Pfadpolitik repositorysicher machen

**Ergebnis:** Konfiguration und Registrierung können niemals eine Exchange-/Repository-Überlappung erzeugen.

### 1.b.W – Let it work! – Exchange- und Repository-Grenzen erzwingen

**Commitposition:** 4 / 33<br>
**Commit-Message:** `feat(config): enforce exchange repository boundaries`

- Konfiguration innerhalb oder oberhalb eines registrierten Repositorys ablehnen,
- Registrierung innerhalb oder oberhalb des Exchange-Ordners ablehnen,
- identische Pfade ablehnen,
- Symlink-/Junction-Auflösung über echte temporäre Verzeichnisse testen,
- `register` weiterhin ohne interaktive Exchange-Abfrage betreiben.

### 1.b.R – Do it right! – Gemeinsame Pfadpolitik zentralisieren

**Commitposition:** 5 / 33<br>
**Commit-Message:** `refactor(config): centralize exchange path policy`

- Registry-Snapshot, physische Pfadprüfung und Konfigurationsschreiben in fester Lock-Reihenfolge ordnen,
- TOCTOU-relevante Pfade vor Veröffentlichung erneut prüfen,
- explizite Result-Ausgabeziele außerhalb registrierter Repositories erlauben,
- den Exchange-Ordner ausdrücklich als zulässiges Result-Ziel behandeln,
- keine alte Watcher-/Result-Überlappungsregel in neue Module übernehmen.

### 1.b.C – Make it clean! – Pfadkonfiguration auf den 1.1.1-Vertrag reduzieren

**Commitposition:** 6 / 33<br>
**Commit-Message:** `refactor(config): remove obsolete path configuration concepts`

- nicht mehr benötigte allgemeine Pfad-Inventar-Abstraktionen reduzieren,
- keine Migrations- oder Fallbackpfade für `watcher.json` oder `paths.json` einführen,
- Tests und Namen vollständig auf `exchange_directory` umstellen,
- vollständige Suite ausführen und Meilenstein 1 reviewen.

---

# Meilenstein 2 – Exchange-Ausgabe und automatische Paketauswahl

## Ziel

Der Exchange-Ordner funktioniert als zentrale Übergabestelle in beide Richtungen, ohne dass der Chat lokale Pfade kennen muss.

## Definition of Done

- `bundle` und Apply-Result-Bundles verwenden standardmäßig den Exchange-Ordner.
- `apply` ohne Pfad findet genau ein passendes repositorygebundenes Paket.
- Kein Treffer und Mehrdeutigkeit mutieren nichts.
- Alte Patches, Result Bundles und beliebige andere Dateien dürfen liegen bleiben.
- Unveränderte bereits versuchte Dateien werden nicht automatisch erneut ausgeführt.

## Step 2.a – Result Bundles standardmäßig im Exchange-Ordner veröffentlichen

**Ergebnis:** Manuelle und automatische Result Bundles stehen ohne Pfadangabe direkt für den Chat-Austausch bereit.

### 2.a.W – Let it work! – Manuellen Bundle-Standard auf Exchange umstellen

**Commitposition:** 7 / 33<br>
**Commit-Message:** `feat(bundle): publish manual bundles to the exchange directory`

- `patchharbor bundle [REPOSITORY]` ohne `--output-dir` auf `exchange_directory` umstellen,
- fehlende oder ungültige Konfiguration mit Exit `11` melden,
- explizites `--output-dir` als Override erhalten,
- JSON- und Plain-Ausgabe auf den tatsächlichen Pfad prüfen,
- End-to-End-Test mit echtem registriertem Repository ergänzen.

### 2.a.R – Do it right! – Automatische Apply-Bundles auf Exchange umstellen

**Commitposition:** 8 / 33<br>
**Commit-Message:** `fix(bundle): route apply result bundles through exchange configuration`

- Apply-, Dry-Run-, Mismatch- und Fehler-Bundles standardmäßig im Exchange-Ordner veröffentlichen,
- Ausgabeziel vor erster Mutation reservieren und unmittelbar vor Veröffentlichung revalidieren,
- explizites `--output-dir` ohne Exchange-Konfiguration ermöglichen,
- primäres Ergebnis und Bundle-Fehlerpriorität unverändert erhalten,
- atomare Veröffentlichung im selben Dateisystem testen.

### 2.a.C – Make it clean! – Result-Zielauflösung vereinheitlichen

**Commitposition:** 9 / 33<br>
**Commit-Message:** `refactor(bundle): unify result bundle target resolution`

- manuellen und automatischen Zielresolver zusammenführen,
- alten Standard-Result-Verzeichnispfad aus der fachlichen Auswahl entfernen,
- überholte persistente Result-Pfadlisten entfernen,
- bestehende Result-Bundle-Tests ohne Text-Snapshot-Doppelung konsolidieren,
- vollständige Suite ausführen.

## Step 2.b – `apply` ohne Pfad genau einen Kandidaten finden lassen

**Ergebnis:** Der Benutzer kann im manuellen Modus nur `patchharbor apply` aufrufen.

### 2.b.W – Let it work! – Flache Exchange-Kandidatensuche einführen

**Commitposition:** 10 / 33<br>
**Commit-Message:** `feat(apply): discover one exchange patch without a path`

- `PATCH_ZIP` in argparse optional machen,
- ohne Pfad den konfigurierten Exchange-Ordner einmalig und nicht rekursiv scannen,
- nur reguläre stabile Dateien berücksichtigen,
- Browser-Temporärdateien überspringen,
- anhand des tatsächlichen ZIP-Inhalts Patch-Pakete von Result Bundles und sonstigen Dateien unterscheiden,
- genau einen einfachen passenden Happy Path end-to-end anwenden.

### 2.b.R – Do it right! – Kandidaten repositoryzustandsgebunden auswählen

**Commitposition:** 11 / 33<br>
**Commit-Message:** `fix(apply): bind exchange selection to repository state`

- Root-`patch.json` streng genug zur Kandidatenbestimmung lesen,
- `repo_id`, Base-Commit und Fingerprint gegen Registry und aktuellen Zustand prüfen,
- Auswahlzustand und finalen Apply-Preflight getrennt halten,
- Lock-Reihenfolge und erneute Prüfung vor Mutation erhalten,
- unbekannte IDs, Mismatches, ungültige Manifeste und äußere Zustandswechsel testen.

### 2.b.C – Make it clean! – Apply-Auswahl und Fehlervertrag bereinigen

**Commitposition:** 12 / 33<br>
**Commit-Message:** `refactor(apply): simplify exchange candidate resolution`

- Paketklassifikation, Registry-Auflösung und CLI-Orchestrierung sauber trennen,
- bei keinem Treffer klar und ohne Mutation fehlschlagen,
- bei mehreren passenden Kandidaten klar und ohne Heuristik fehlschlagen,
- expliziten Pfad als eindeutigen Override erhalten,
- JSON-Fehlervertrag und Help ohne breite Text-Snapshots testen.

## Step 2.c – Wiederverarbeitung und Exchange-Chaos beherrschen

**Ergebnis:** Viele alte Dateien im Exchange-Ordner sind sicher und verursachen keine ungeplanten Wiederholungen.

### 2.c.W – Let it work! – Persistente Exchange-Dateidentität einführen

**Commitposition:** 13 / 33<br>
**Commit-Message:** `feat(exchange): persist processed file identities`

- stabile Identität aus kanonischem Pfad und vollständigem SHA-256 bilden,
- benutzerspezifischen Exchange-Status atomar im Zustandsverzeichnis speichern,
- Inhaltsklasse und Patch-Auswahldaten unveränderter Dateien wiederverwenden,
- nur tatsächlich versuchte Patches dauerhaft von der automatischen Ausführung ausschließen,
- zustandsbedingt noch nicht passende Patch-Kandidaten bei späteren Scans erneut bewerten,
- geänderten Inhalt unter demselben Namen als neue Identität erkennen.

### 2.c.R – Do it right! – Retry-, Dry-Run- und Fehlersemantik härten

**Commitposition:** 14 / 33<br>
**Commit-Message:** `fix(exchange): harden retry and processing semantics`

- Dry-Run niemals als versucht markieren,
- automatischen Nicht-Dry-Run nach vollständigem Preflight unmittelbar vor Mutation atomar als versucht markieren,
- bei fehlgeschlagener Statuspublikation vor jeder Mutation abbrechen,
- explizites `apply PATCH_ZIP` als bewussten Retry trotz gespeicherter Identität erlauben,
- Entrypoint-, Test- und Result-Bundle-Fehler von der bereits gesetzten Versuch-Markierung trennen,
- Absturzgrenzen verhaltensorientiert testen.

### 2.c.C – Make it clean! – Exchange-Dateien unangetastet lassen

**Commitposition:** 15 / 33<br>
**Commit-Message:** `refactor(exchange): keep exchange storage unmanaged`

- jede Verschiebe-, Lösch-, Archiv-, Rename- oder Sortierlogik ausdrücklich fernhalten,
- große Mengen alter Patches, Result Bundles und Fremddateien verhaltensorientiert testen,
- wiederholte unnötige ZIP-Analyse unveränderter Nichtkandidaten vermeiden,
- State-Modelle und Tests vereinfachen,
- vollständige Suite ausführen und Meilenstein 2 reviewen.

---

# Meilenstein 3 – Watcher auf denselben Vertrag umstellen

## Ziel

Der Watcher bleibt ein dünner Linux-Auslöser und verwendet exakt dieselbe Konfiguration, Klassifikation und Dateidentität wie der Core.

## Definition of Done

- kein eigener Watcher-Eingangsordner,
- keine eigene `watcher.json`,
- keine Watcher-`--configure`-Option und kein positionaler Input-Pfad,
- Result Bundles im Exchange-Ordner erzeugen keine Schleife,
- Neustart und mehrere stabile Downloads verhalten sich deterministisch.

## Step 3.a – Watcher an die gemeinsame Exchange-Grenze anschließen

**Ergebnis:** Der Watcher startet ausschließlich mit `config.json` und delegiert über Core-Verträge.

### 3.a.W – Let it work! – Watcher aus `config.json` starten

**Commitposition:** 16 / 33<br>
**Commit-Message:** `feat(watcher): use the shared exchange configuration`

- Watcher-Start ohne positionalen Eingangsordner auf `exchange_directory` umstellen,
- vorhandene Stabilitätsbeobachtung beibehalten,
- stabile Patch-Datei über die öffentliche Apply-Grenze delegieren,
- Happy-Path und Neustart mit echtem Unterprozess testen,
- Systemd-Installation vorerst nur auf vorhandene gemeinsame Konfiguration prüfen.

### 3.a.R – Do it right! – Klassifikation und Dateistatus mit Core teilen

**Commitposition:** 17 / 33<br>
**Commit-Message:** `fix(watcher): share exchange classification and processing state`

- keine eigene Patch-/Result-Bundle-Klassifikation im Watcher behalten,
- denselben persistenten Identitätsstatus wie `apply` ohne Pfad verwenden,
- Result Bundles und unveränderte Nichtkandidaten ohne Delegationsschleife behandeln,
- bei mehreren gleichzeitig passenden Paketen dieselbe Mehrdeutigkeitsablehnung wie der Core verwenden und niemals eine Reihenfolge erraten,
- Race zwischen Stabilitätsprüfung, Hashing und Dateiaustausch testen.

### 3.a.C – Make it clean! – Alte Watcher-Konfiguration entfernen

**Commitposition:** 18 / 33<br>
**Commit-Message:** `refactor(watcher): remove legacy input configuration`

- `watcher.json`-Lese-/Schreibcode entfernen,
- `--configure` und positionalen `INPUT_DIRECTORY` aus CLI und Tests entfernen,
- tote Pfadstatus- und Adaptermodule entfernen oder auf gemeinsame Core-Modelle reduzieren,
- Runtime-Inventar und Architekturtests aktualisieren,
- keinen Migrationscode hinzufügen.

## Step 3.b – Watcher-Lifecycle und systemd vollständig absichern

**Ergebnis:** Der gemeinsame Exchange-Vertrag funktioniert auch dauerhaft und nach Neustarts.

### 3.b.W – Let it work! – Systemd-Unit auf den parameterlosen Watcher umstellen

**Commitposition:** 19 / 33<br>
**Commit-Message:** `feat(watcher): install the shared-config systemd unit`

- Unit ohne eingebetteten Eingangsordner erzeugen,
- Installation nur bei gültiger `config.json` erlauben,
- Installer weiterhin weder enable noch start ausführen lassen,
- Unit-Inhalt, Pfade und Help verhaltensorientiert testen.

### 3.b.R – Do it right! – Dauerbetrieb und Fehlergrenzen härten

**Commitposition:** 20 / 33<br>
**Commit-Message:** `fix(watcher): harden restart and exchange loop prevention`

- Neustart mit persistenter Dateidentität absichern,
- während Apply erzeugte Result Bundles niemals als neue Patches behandeln,
- Konfigurationsänderung, gelöschten Exchange-Ordner und ungültigen Status klar behandeln,
- Strg+C, Signal-Cleanup und Unterprozessfehler erhalten,
- konkurrierende Core-Aufträge weiterhin durch Repository-Lock begrenzen.

### 3.b.C – Make it clean! – Watcher auf die dünne Auslöserrolle reduzieren

**Commitposition:** 21 / 33<br>
**Commit-Message:** `refactor(watcher): minimize the shared exchange watcher`

- verbleibende duplizierte Core-Logik entfernen,
- Polling-, Lifecycle-, systemd- und Boundary-Module klar schneiden,
- `paths.json` und nicht mehr benötigte Pfad-Inventar-Persistenz vollständig entfernen,
- Watcher-Tests auf unterschiedliche Verhaltensfälle reduzieren,
- vollständige Suite ausführen und Meilenstein 3 reviewen.

---

# Meilenstein 4 – Chat-Initialisierung und deterministische UI

## Ziel

Ein neuer Chat versteht PatchHarbor vollständig, ohne lokale Pfade zu kennen, und erzeugt konsistente Patch-Pakete mit einer festen schmalen Oberfläche.

## Definition of Done

- `CHAT_INSTRUCTIONS.md` liegt im Repository-Root und ist versionsgebunden.
- Ein neuer Chat benötigt nur diese Datei und ein aktuelles Result Bundle.
- Der Chat kennt Patch-Paket, Result Bundle, Tests, Commit-Verhalten und Fehlerzustände.
- Plan, Spezifikation und realer Snapshot werden gegeneinander geprüft.
- UI und STOP-/WARNING-Zeilen sind deterministisch und smartphone-tauglich.

## Step 4.a – Den technischen Chat-Workflow verbindlich beschreiben

**Ergebnis:** Der Chat kann aus einem Result Bundle ein korrektes PatchHarbor-Paket erzeugen und das Rückgabe-Bundle auswerten.

### 4.a.W – Let it work! – `CHAT_INSTRUCTIONS.md` mit Kernworkflow anlegen

**Commitposition:** 22 / 33<br>
**Commit-Message:** `docs(chat): add the PatchHarbor chat initialization contract`

- Root-Datei `CHAT_INSTRUCTIONS.md` für Version 1.1.1 anlegen,
- Fähigkeiten und Sicherheitsgrenzen von PatchHarbor erklären,
- Initialisierung mit Chat-Datei plus aktuellem Result Bundle festlegen,
- klarstellen, dass Repository- und Exchange-Pfad nicht benötigt werden,
- korrektes repositorygebundenes ZIP-Paket mit Root-`patch.json` verlangen,
- genau eine herunterladbare Patch-Datei pro Antwort verlangen.

### 4.a.R – Do it right! – Tests, Commits und Result-Bundle-Rücklauf definieren

**Commitposition:** 23 / 33<br>
**Commit-Message:** `docs(chat): define tests commits and result review`

- passende Tests mit harten Timeouts als Standard festlegen,
- bei Testfehler keinen Git-Commit erzeugen,
- bei grünen Tests exakt einen vorgesehenen Commit mit exakter Message erzeugen,
- keinen rekursiven `patchharbor bundle`-Aufruf im Entrypoint erlauben,
- fehlende globale Rückabwicklung und tatsächlichen Fehlerzustand erklären,
- `logs/run.json`, `logs/execution.log`, staged, unstaged und untracked Zustand als Rückgabegrundlage festlegen.

### 4.a.C – Make it clean! – Chat-Vertrag knapp und versionssicher machen

**Commitposition:** 24 / 33<br>
**Commit-Message:** `test(chat): audit the initialization document contract`

- Wiederholungen entfernen und klare Muss-/Darf-nicht-Regeln verwenden,
- Release-Audit ab diesem Commit um `CHAT_INSTRUCTIONS.md` erweitern,
- zentrale Marker, Version, Paketregeln und Result-Log-Regeln gezielt testen,
- keine vollständigen Fließtext-Snapshots einführen,
- README und Help noch nicht vorwegnehmen.

## Step 4.b – Plan-/Spec-Prüfung und schmale Chat-UI festlegen

**Ergebnis:** Fortschritt, Patch-Art und blockierende Situationen sehen in jedem Chat gleich aus.

### 4.b.W – Let it work! – Plan- und Spezifikationssuche definieren

**Commitposition:** 25 / 33<br>
**Commit-Message:** `docs(chat): define plan and specification discovery`

- aktuelle Version aus dem Repository bestimmen,
- zuerst `planning/<version>/commit-plan.md`, danach `implementation-plan.md` und erst danach eindeutige repositoryweite Kandidaten prüfen,
- für Spezifikationen zuerst eine ausdrückliche Planreferenz, danach den versionsbezogenen Planning-Bereich, `spec/SPECIFICATION.md` und erst danach eindeutige repositoryweite Kandidaten prüfen,
- gefundene Plan- und Spec-Pfade immer anzeigen,
- bei mehreren plausiblen Quellen mit standardisiertem Code stoppen,
- bei nicht bestimmbarer Planposition nicht raten.

### 4.b.R – Do it right! – Scope, Commit-Arten und Stop-Regeln härten

**Commitposition:** 26 / 33<br>
**Commit-Message:** `docs(chat): enforce plan scope and stop semantics`

- Spezifikation als fachlichen Vertrag und Plan als Zerlegung definieren,
- kleine eindeutig commitbezogene Planlücken erlauben,
- größere Scope-Erweiterung oder Designentscheidung vor Umsetzung stoppen,
- `PLAN`, `FIX` und `OFF-PLAN` verbindlich unterscheiden,
- Fix-Unterkennung `<ID>-FIX<n>` und unveränderten Plan-Zähler festlegen,
- Off-Plan-Kennung und Message frei, aber sichtbar markiert erlauben,
- kleine geschlossene WARNING- und STOP-Code-Sätze definieren.

### 4.b.C – Make it clean! – Smartphone-UI exakt standardisieren

**Commitposition:** 27 / 33<br>
**Commit-Message:** `test(chat): lock the narrow PatchHarbor status UI`

- schmale Darstellung ohne breite Tabellen festlegen,
- `🟩🟩 PATCH BEREIT 🟩🟩` exakt oben und als letzte Zeile verlangen,
- Commit-Art, Kennung und Planfortschritt untereinander anzeigen,
- Commit-Message, Plan, Spec, fünf bis zehn Änderungszeilen, Tests und Restzähler festlegen,
- `PATCH BEREIT` erst nach tatsächlicher Dateierzeugung erlauben,
- geplante Tests vor lokalem Apply nicht als erfolgreich ausgeben,
- rote STOP- und gelbe WARNING-Ausgaben exakt testbar machen,
- vollständige Suite ausführen und Meilenstein 4 reviewen.

---

# Meilenstein 5 – Bedienung, Akzeptanz und Release 1.1.1

## Ziel

Ein Benutzer kann PatchHarbor 1.1.1 aus README und Help korrekt einrichten; alle neuen und fortgeltenden Verträge sind plattformübergreifend freigabefähig.

## Definition of Done

- README beschreibt alle vereinbarten Initialisierungsfälle.
- Help zeigt ausschließlich implementierte Befehle und Optionen.
- Manueller und Watcher-Workflow funktionieren mit demselben Exchange-Ordner.
- Linux, Ubuntu-Docker und echte Windows-Runner sind grün.
- Paketversion, Changelog, Commit-Plan und Release-Artefakte stimmen überein.

## Step 5.a – README und Help als vollständige Kurzanleitung liefern

**Ergebnis:** Ein Benutzer kann ohne Vorwissen ein neues oder bestehendes Repository und einen neuen Chat starten.

### 5.a.W – Let it work! – Manuellen Einstieg dokumentieren

**Commitposition:** 28 / 33<br>
**Commit-Message:** `docs(readme): add the manual exchange workflow`

- `config.json`-Pfad und `configure exchange-directory` erklären,
- neues Git-Repository mit auflösbarem `HEAD` und `register` beschreiben,
- bereits registriertes Repository beschreiben,
- `bundle`, Upload von Bundle plus `CHAT_INSTRUCTIONS.md`, Download und `patchharbor apply` ohne Pfad erklären,
- Result Bundle nach Erfolg oder Fehler zurück zum Chat führen.

### 5.a.R – Do it right! – Watcher-, Chat- und Plattformfälle ergänzen

**Commitposition:** 29 / 33<br>
**Commit-Message:** `docs(readme): cover watcher and new chat initialization`

- neuen Chat für neues und bestehendes Repository klar trennen,
- Watcher-Konfiguration, Unit-Installation, enable/disable und journald beschreiben,
- vor konkurrierenden Automatikpfaden warnen,
- Termux-kompatibles Beispiel mit `~/Downloads` und Windows-Konfigurationspfad ergänzen,
- direkte `config.json`-Bearbeitung und Fehler bei fehlender Konfiguration erklären,
- explizite Pfad-/`--output-dir`-Overrides dokumentieren.

### 5.a.C – Make it clean! – README und argparse-Help konsolidieren

**Commitposition:** 30 / 33<br>
**Commit-Message:** `refactor(docs): align readme help and chat instructions`

- doppelte Langtexte entfernen,
- README als Kurzanleitung und Help als vollständige CLI-Referenz abgrenzen,
- alte Watcher-`--configure`- und Eingangsordner-Beispiele vollständig entfernen,
- alle dokumentierten Befehle gegen argparse testen,
- Spec, README, Help und `CHAT_INSTRUCTIONS.md` auf Widersprüche auditieren.

## Step 5.b – Vollständige Akzeptanz und Release 1.1.1 abschließen

**Ergebnis:** Der exakte finale Commit ist auf allen verbindlichen Plattformen freigabefähig.

### 5.b.W – Let it work! – 1.1.1-End-to-End-Akzeptanz schließen

**Commitposition:** 31 / 33<br>
**Commit-Message:** `test(acceptance): cover the complete 1.1.1 workflow`

- neues und bestehendes Repository end-to-end prüfen,
- manuellen `bundle → Chat-Patch → apply → Result Bundle`-Kreislauf prüfen,
- Watcher-Kreislauf im gemeinsamen Exchange-Ordner prüfen,
- kein Treffer, Mehrdeutigkeit, Result-Bundle-Clutter, alter Patch und expliziter Retry prüfen,
- Testfehler im Entrypoint samt realem Snapshot und Logs prüfen,
- README-Kommandos als Akzeptanzpfade ausführen.

### 5.b.R – Do it right! – Plattform- und Packaging-Gates härten

**Commitposition:** 32 / 33<br>
**Commit-Message:** `test(release): harden cross-platform 1.1.1 gates`

- Ubuntu 24.04 und 26.04 Docker-Gates aktualisieren,
- echte Windows-Runner mit PowerShell und Pfadsemantik aktualisieren,
- Termux-kompatible Linux-Pfade ohne systemd-Annahme im Core prüfen,
- Wheel-, Source-Distribution- und pipx-Smoke für CLI und Watcher prüfen,
- `CHAT_INSTRUCTIONS.md` als kanonisches Release-Dokument auditieren,
- Runtime- und Dokumentinventar exakt abschließen.

### 5.b.C – Make it clean! – Version 1.1.1 final freigeben

**Commitposition:** 33 / 33<br>
**Commit-Message:** `release: finalize PatchHarbor 1.1.1`

- Paketversion erst jetzt auf `1.1.1` setzen,
- Changelog-Status und Planstatus auf abgeschlossen stellen,
- tote 1.1.0-Konfigurationsreste und temporäre Adapter entfernen,
- `git diff --check`, vollständige Tests, Docker-Gates, Packaging und Release-Audit auf dem exakten finalen Commit ausführen,
- Wheel und Source-Distribution aus sauberer Stage bauen und auditieren,
- keine Veröffentlichung zulassen, solange eine blockierende Lane rot ist.

---

## 6. Abschlusszustand

Nach `5.b.C` gilt:

- 33 / 33 reguläre W-R-C-Plan-Commits sind umgesetzt,
- Fix- und Off-Plan-Commits sind getrennt dokumentiert und nicht in den Plan-Zähler eingerechnet,
- `config.json` ist die einzige persistente Exchange-Konfiguration,
- `bundle`, `apply` und Watcher verwenden denselben Exchange-Ordner,
- Exchange-Dateien bleiben unangetastet liegen,
- `CHAT_INSTRUCTIONS.md` und die schmale Chat-UI sind verbindlich,
- README, Help, Spezifikation, Tests und Code sind widerspruchsfrei,
- PatchHarbor 1.1.1 ist nur bei vollständig grünen Release-Gates freigabefähig.
