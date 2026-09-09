# PatchHarbor – Spezifikations-Changelog

**Dateiname:** `SPECIFICATION_CHANGELOG.md`<br>
**Stand:** 2026-09-09

Dieses Dokument protokolliert Änderungen am verbindlichen Produktziel. Es ist kein Git-Commit-Log und ersetzt nicht die getrennten Umsetzungspläne unter `planning/`.

---

## [1.1.1] – 2026-08-28

**Status:** Freigegeben und vollständig umgesetzt; der abgeschlossene Plan liegt unter `planning/1.1.1/commit-plan.md`.

### Post-release nachweisbasierte Exchange-Archivierung – 2026-09-09

- Korrektur des noch nicht erfolgreich angewendeten Archivierungs-Patches: gemeinsame funktionale CLI-Testhelfer ohne pauschalen 20-Sekunden-Subprozess-Timeout; ausdrücklich angeforderte Timeout-/Prozesstests bleiben erhalten.
- Validierte Kandidaten teilen je Repository und Scan genau eine anfängliche konsistente Zustandserfassung. Doppelte Vorab-Revalidierung entfällt; jeder tatsächliche Move erhält nach dem letzten Datei-Hash weiterhin eine frische vollständige State-/Git-/Registry-/Konfigurations-/Replay-Prüfung. Aktuelle Resultate und fehlende Abschlussbelege werden ohne Historienabfrage behalten.
- Zusätzliche Regressionen zählen Zustandsabfragen statt Laufzeiten und simulieren Änderungen nach dem Datei-Hash; keine veraltete Freigabe wird gecacht und kein fachlicher Drei-Stunden-Timeout geändert.

- `configure archive-dir NAME` verwendet die bestehende Konfiguration; Standard `PatchHarbor-Archive`, leerer Wert/`--clear` deaktiviert. Direkter Exchange-Unterordner, führender Punkt erlaubt, keine Windows-Hidden-Logik.
- Konfiguration Format 3 erhält Exchange-Pfad und Suffix; Formate 1/2 werden ohne Schreibzugriff mit sicherem Standard gelesen.
- Der bestehende Replay-State Format 3 speichert nach erfolgreichem Vorwärts-Commit optional `completed_commit`; alte attempted/succeeded-Daten erhalten keine erfundenen Commit-Belege.
- Nur exakt gebundene erfolgreiche Patches mit Abschlussbeleg und validierte saubere Result-Snapshots echter Git-Vorfahren werden archiviert. Fehlende/unklare Beweise, fremde oder beschädigte Dateien, Dirty-/Fehler-Bundles und unvollständige/ersetzte Historien bleiben liegen.
- Manueller Repository-Scope, explizite Paketauswahl und globaler Watcher bleiben getrennt; Dry-Run archiviert nichts. Alter/Dateiname beeinflussen die Entbehrlichkeit nicht.
- Gepinnte Verzeichnisse, wiederholte Hash-/State-Prüfung und No-Replace-Rename verhindern Zielumleitung und Überschreiben; Kollisionen erhalten eindeutige Namen, fehlgeschlagene Moves behalten die Quelle. Kein Löschen, keine rekursive Archivsuche.
- Regressionen decken Migration, Konfiguration, echte Git-Nachweise, Replay/Retry, Repository-Trennung, manipulierte Bundles, Symlinks, Kollisionen und Fehlerpfade ab. Paketformat, Fingerprint, Bundle-Benennung und 10.800-Sekunden-Timeout bleiben unverändert.

### Post-release selbstbeschreibende Bundle-Übergabe – 2026-09-08

- Jede Result-Bundle-Erzeugung rendert frisch die installierte statische Chat-Vorlage plus konkrete lokale Daten; `CHAT_INSTRUCTIONS.md` und `environment.json` werden atomar mitveröffentlicht, ohne Zusatzbefehl oder Sidecar.
- Repository-Pfad, konfigurierter Exchange-Pfad, tatsächliches Ausgabeziel, Suffix, Namensschema und vollständige Bindungswerte sind konsistent; Pfade bleiben reine Hilfen für lokale Befehle und niemals Sicherheitsbindung.
- Allowlist für Distribution, Kernel, Architektur, Python, uv, konfigurierte Shell und PatchHarbor-Version; fehlende optionale Daten sind `null`, uv-Probe begrenzt. Keine Netzwerkabfragen, Hostnamen, IPs oder Umgebungsdumps.
- Die statische Vorlage bleibt fachliche Quelle und wird bei installiertem Betrieb aus dem versionierten Datenartefakt geladen. Keine Zielrepository-Datei überschreibt den Vertrag, keine zurückgelieferten Instructions werden ausgeführt.
- Externe Patch-Pakete enthalten ein optionales, strikt geprüftes `PATCHHARBOR_META`-Paar, getrennt von Nutzdateien/Entrypoint; bestehende Pakete und `patch.json` bleiben kompatibel. Bootstrap-Regel für den ersten älteren Runner dokumentiert.
- Regressionen decken alle Result-Pfade, frische Konfiguration, Fremdrepository/Watcher, fehlende Systemdaten, Metadaten-Isolation, Paketierung, unveränderte Bindung und atomare Fehlerbehandlung ab.

### Post-release konfigurierbares Bundle-Suffix – 2026-09-08

- `configure bundle-suffix SUFFIX` und `configure bundle-suffix --clear` ergänzen die bestehende Configure-CLI; `configure show` zeigt den Wert.
- Die Konfiguration verwendet das geschlossene Format 2 mit `exchange_directory`, `format_version` und `bundle_suffix`. Format 1 bleibt ohne Suffix lesbar; erst ein expliziter Schreibvorgang migriert atomar. Beide Konfigurationsbefehle erhalten jeweils die andere Einstellung und nutzen denselben globalen Lock.
- Das Suffix wird nach `.zip` an alle neu erzeugten Result-Bundle-Namen angehängt, auch bei Fehler, Dry-Run, Watcher und explizitem Ausgabeziel. Der leere String erhält das bisherige Namensschema.
- Result-`context.json` trägt den bei der Ausgabe verwendeten Wert als optionale, nicht zustandsbindende Metadaten für die Patch-Dateinamen externer Chats. Alte Bundles ohne Feld gelten als suffixlos; `patch.json` und das geschlossene `context --json`-Schema bleiben unverändert.
- Ein zentraler reiner Helfer validiert portable Suffixe und fügt sie an. Temporäre Download-Endungen werden nicht als fertiges Suffix zugelassen. Ziel und Suffix werden vor Veröffentlichung revalidiert.
- Inhaltsbasierte Erkennung akzeptiert alte und suffigierte ZIPs weiterhin ohne Umbenennen. CWD-Bindung, Replay-/Retry-Regeln, Watcher-Schutz, `mtime_ns`, vollständige Kennungen, Fingerprint und 10.800-Sekunden-Timeout bleiben unverändert.
- README, CLI-Hilfe, Chat-Vertrag und Spezifikation dokumentieren Einrichtung, Abschalten, Migration und die Grenzen reiner Dateiumbenennung. Regressionen umfassen Konfiguration, atomare Persistenz, Suffix-Erkennung, automatische Resultate, manuellen Retry, Watcher und Änderungen während der Ausgabe.

### Post-release repository-scoped manual Apply – 2026-08-31

- Ein manueller parameterloser `patchharbor apply` löst zuerst das registrierte Repository des aktuellen Arbeitsverzeichnisses auf; Aufrufe aus Unterverzeichnissen werden der Repository-Wurzel zugeordnet.
- Pakete anderer registrierter Repositorys sind für diesen manuellen Aufruf keine Kandidaten. Ist das aktuelle Repository nicht eindeutig registriert, endet der Auftrag ohne globalen Fallback.
- Ein explizites `patchharbor apply PATCH_ZIP` bleibt eine bewusste paketgesteuerte Auswahl und darf weiterhin das über `repo_id` bestimmte andere registrierte Repository verwenden.
- Der Watcher bleibt mit seinem internen automatischen Ursprung repositoryübergreifend und verwendet weiterhin den Schutz gegen die sofortige Wiederholung fehlgeschlagener Pakete.
- Unter den nach Repository-, State- und Replay-Prüfung verbleibenden Kandidaten gewinnt der höchste `mtime_ns`; bei identischem Zeitstempel entscheidet der Unicode-NFC-normalisierte und anschließend der unveränderte Dateiname deterministisch.
- Ein neuerer fremder, state-inkompatibler oder replaygeschützter Kandidat blockiert keinen älteren zulässigen Kandidaten.
- Paketformat, Fingerprint-Algorithmus, Drei-Stunden-Standardtimeout und das bereits veröffentlichte Bundle-Namensschema bleiben unverändert.

### Post-release complete-identifier guidance – 2026-08-30

- Die Kurzansichten von `register`, `context` und `registry list` werden ausdrücklich als reine Präsentation dokumentiert und dürfen nicht als Chat- oder Maschineninput beziehungsweise für `patch.json` verwendet werden.
- Der Kontext-Hinweis nennt jetzt den tatsächlich unterstützten Befehl `patchharbor context --json`; `register` besitzt weiterhin bewusst keine `--json`-Option.
- README und CLI-Hilfe verweisen für vollständige Registry-UUIDs auf `patchharbor registry list --json` und stellen klar, dass gekürzte Präfixe keine gültigen `unregister`-Selektoren sind.
- Der normale Chat-Workflow verwendet weiterhin `CHAT_INSTRUCTIONS.md` und das aktuelle Result Bundle, dessen `context.json` alle Bindungswerte vollständig enthält.
- JSON-Schema, persistierte Identitäten und sämtliche Sicherheitsvergleiche bleiben unverändert.

### Post-release replay and presentation update – 2026-08-30

- Der persistente Replay-State unterscheidet `attempted`, `failed` und `succeeded`; erfolgreiche Pakete bleiben gesperrt, während ein bewusster manueller parameterloser Apply einen weiterhin exakt gebundenen fehlgeschlagenen Patch erneut versuchen darf.
- Der Watcher kennzeichnet seinen Core-Aufruf intern als automatisch und wiederholt eine fehlgeschlagene unveränderte Paketidentität bei späteren Polls nicht erneut.
- Bei mehreren vollständig passenden Kandidaten gewinnt erst nach allen Sicherheits- und State-Prüfungen der eindeutige höchste `mtime_ns`; ein exakter Höchstwert-Tie wird fail-safe abgelehnt.
- Patch- und Result-Dateinamen folgen `<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip` beziehungsweise `<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip`; Uhrzeit ist UTC, das Jahr entfällt und ID6 enthält kein Auslassungszeichen.
- Menschenlesbare Terminalausgaben kürzen lange technische Kennungen zentral auf sechs Zeichen plus `…`; JSON, Manifeste, Logs, Persistenz und Sicherheitsvergleiche behalten vollständige Werte.
- Ein öffentlicher `--retry-failed`-Schalter wird nicht eingeführt, weil der normale manuelle parameterlose Apply bereits die bewusste Retry-Aktion ist.

### Post-release fix – 2026-08-29

- `2.b.R-FIX1` hält die automatische Exchange-Erkennung auf gemeinsamem Android-/Termux-Speicher funktionsfähig, wenn Pfad- und Deskriptoransicht keine vergleichbare Inode-Identität liefern.
- Der Fallback bleibt auf Exchange-Dateien begrenzt und verlangt weiterhin übereinstimmenden Dateityp, Größe und Änderungszeit sowie den vollständigen SHA-256; ausgewählte Pakete werden vor der Mutation erneut geöffnet und gehasht.
- Eine einzelne instabile, nicht lesbare oder gleichzeitig veränderte Fremddatei wird nur für den aktuellen Scan übersprungen und macht nicht mehr den gesamten Exchange-Ordner unbrauchbar.
- Der gemeinsame Standard-Timeout für `patchharbor apply` und `patchharbor fs run` steigt von 300 auf 10.800 Sekunden (drei Stunden); `--timeout` bleibt die explizite Überschreibung pro Aufruf. Der Watcher verwendet denselben Core-Default.

### Release – 2026-08-28

- Paketversion und Release-Artefakte verwenden verbindlich `1.1.1`.
- Der konsolidierte Plan ist mit 12 / 12 Plan-Commits vollständig abgeschlossen und enthält keine `NEXT`- oder `OPEN`-Zeile mehr.
- Der vollständige manuelle Exchange-Kreislauf, die Watcher-Delegation, persistente Dateiidentität, Linux- und Windows-Verträge sowie Wheel-, Source-Distribution- und pipx-Installation sind blockierend abgesichert.
- Spezifikation, README, Chat-Vertrag, CLI, Packaging und Release-Audits beschreiben denselben freigegebenen 1.1.1-Stand.

### Planning correction – 2026-08-26

- Der mechanische 33-Commit-Plan wurde ohne Änderung des Produktziels auf 12 fachlich eigenständige Plan-Commits konsolidiert.
- Die bereits umgesetzten Commits `1.a.W` und `1.a.R` ergeben den Planstand 2 / 12; die Konsolidierung selbst ist ein Off-Plan-Commit und verändert den Zähler nicht.
- W-R-C bleibt als Qualitätsprinzip erhalten, wird aber nicht mehr als zwingendes Dreiermuster für jeden Step verwendet.
- Die Fortschrittstabelle im Plan wird ab jetzt mit jedem Plan-Commit aktualisiert, damit ein neuer Chat den Stand aus dem Result-Bundle-Snapshot bestimmen kann.
- Das UI-Beispiel in der Spezifikation wurde hinsichtlich der neuen Gesamtzahl angepasst.
- Die Testausführungsregel wurde plattformgerecht präzisiert: Termux-Commit-Skripte auf Christians Pixel laufen ohne künstliche Einzeltest- oder Gesamtsuite-Timeouts; produktinterne Timeout-Verträge sowie CI- und Release-Grenzen bleiben bestehen.
- Alle fachlichen 1.1.1-Produktfunktionen bleiben unverändert.

### Added

- Allgemeine benutzerspezifische `config.json` mit geschlossenem Format-1-Schema und `exchange_directory`.
- Sichere CLI zum Setzen und Anzeigen des Exchange-Ordners.
- Gemeinsamer Exchange-Ordner als Standardziel für manuelle und automatische PatchHarbor Result Bundles.
- `patchharbor apply` ohne Dateipfad mit nicht rekursiver, inhaltsbasierter und repositoryzustandsgebundener Paketauswahl.
- Persistente Dateidentität aus kanonischem Pfad und SHA-256 zur Verhinderung ungeplanter automatischer Wiederverarbeitung.
- Gemeinsamer Konfigurations-, Klassifikations- und Dateidentitätsvertrag für Core und Watcher.
- Root-Datei `CHAT_INSTRUCTIONS.md` zur Initialisierung eines neuen Entwicklungs-Chats.
- Verbindliche Chat-Regeln für Plan- und Spezifikationssuche, Spec-vs.-Plan-Prüfung, Tests, Commit-Arten und Result-Bundle-Auswertung.
- Schmale deterministische Chat-UI mit `PLAN`, `FIX`, `OFF-PLAN`, `WARNING`, `STOP` und doppelter `PATCH BEREIT`-Zeile.
- README-Abläufe für neues und bestehendes Repository, neuen Chat, manuellen Modus und Watcher-Modus.

### Changed

- Der frühere Watcher-Eingangsordner und der frühere Standard-Result-Ordner werden durch eine gemeinsame Exchange-Grenze ersetzt.
- `patchharbor bundle` und Apply-Result-Bundles veröffentlichen ohne `--output-dir` im Exchange-Ordner.
- Der Watcher besitzt keine eigene Eingangsordner-Konfiguration mehr und liest ausschließlich `config.json`.
- Result Bundles dürfen bewusst neben Patch-Paketen im Exchange-Ordner liegen und werden zuverlässig nicht als Patch ausgeführt.
- PatchHarbor räumt Exchange-Dateien nicht auf; Archivierung, Sortierung und Journalisierung bleiben außerhalb des Core.
- Repo Assist wird als Werkzeug für Commit-Plan, Journal, Reproduzierbarkeit, Tests und Commits beschrieben, nicht als zwingend oberster Orchestrator.
- Exakte Chat-Statuszeilen sind als maschinenlesbarer UI-Vertrag von der sonstigen Regel gegen Human-Text-Snapshot-Tests ausgenommen.

### Clarified

- Der Chat benötigt weder den lokalen Repository-Pfad noch den Exchange-Pfad; `CHAT_INSTRUCTIONS.md` und ein aktuelles Result Bundle genügen zur Initialisierung.
- `patchharbor apply` erzeugt nach sicherer Repository-Auflösung selbst das Result Bundle; der Patch-Entrypoint ruft `patchharbor bundle` nicht rekursiv auf.
- Projekttests können und sollen durch den vertrauenswürdigen Patch-Entrypoint ausgeführt werden, bleiben aber außerhalb der fachlichen Verantwortung des Core.
- Testfehler oder andere Entrypoint-Fehler führen nicht zu einer globalen PatchHarbor-Rückabwicklung; das Result Bundle enthält soweit möglich den tatsächlich zurückgebliebenen Zustand und die vollständigen Logs.
- Fixes verwenden `<PLAN-ID>-FIX<n>` und erhöhen den Plan-Commit-Zähler nicht; Off-Plan-Kennungen und -Messages dürfen sinnvoll frei gewählt werden.

### Removed / No migration

- Keine 1.1.1-Laufzeitquelle `watcher.json`.
- Keine 1.1.1-Laufzeitquelle `paths.json`.
- Kein Migrations- oder Fallbackcode für frühere Entwicklungs-Konfigurationen, da keine produktiv verwalteten 1.1.0-Installationen übernommen werden müssen.

---

## [1.1.0] – 2026-08-04

**Status:** Verbindliche, implementierungsreife Spezifikationsfassung; Umsetzung gegenüber der vorhandenen 1.0.0-Codebasis erfolgt über den getrennten 1.1.0-Commit-Plan.

### Added

- Vollständige eigenständige Produktspezifikation, getrennt vom Commit-Plan.
- Vollständige Übernahme aller fortgeltenden 1.0.0-Produktverträge.
- Registrierung konkreter lokaler Git-Repository-Instanzen.
- UUID v4 als stabile `repo_id` pro lokalem Klon oder Worktree.
- Lokale ID-Datei `.patchharbor/id`, die nicht committet wird.
- Lokales Git-Exclude über `git rev-parse --git-path info/exclude`.
- Zentrale benutzerspezifische Zuordnung von Repository-ID zu kanonischem Pfad.
- Registry-Minimum mit `register`, `register --new-id`, `registry list` und `unregister`.
- Idempotente Registrierung und definierter Umgang mit verschobenen oder kopierten Repository-Instanzen.
- Befehl `patchharbor context` mit fertigem Copy-Paste-Block.
- Getrenntes Zustandsmodell aus vollständigem Base-Commit und Dirty-State-Fingerprint.
- Normativer Algorithmus `patchharbor-state-v1`.
- Kanonische byteweise Erfassung von staged, unstaged und untracked Zustand.
- SHA-256-Fingerprint, gekürzt auf 16 kleingeschriebene Hex-Zeichen.
- Feste Byte-Rahmung, exakte Payloadcodierung und vier verbindliche Testvektoren einschließlich staged und unstaged.
- Sicherer Mehr-Repository-Pfad `patchharbor apply PATCH_ZIP`.
- Verpflichtende Root-Datei `patch.json` mit Paketmarker, Formatversion, Repository-ID, Base-Commit, Fingerprint-Algorithmus, Fingerprint und Entrypoint.
- Genau ein automatisch gestarteter Entrypoint.
- Privates temporäres Entrypoint-Verzeichnis bei gleichzeitigem Repository-Wurzelverzeichnis als CWD.
- Verbot aller ZIP-Pfade mit `.git` oder `.patchharbor` als Pfadsegment.
- Exklusive betriebssystemübergreifende Sperre pro Repository-ID.
- Erkennung äußerer Zustandsänderungen während der Snapshot-Aufnahme.
- Dry-Run über `patchharbor apply --dry-run PATCH_ZIP`.
- Trennung von primärem Auftragsergebnis und Result-Bundle-Ergebnis.
- Verbindliche Fehlerpriorität bei gleichzeitigem Skript- und Bundle-Fehler.
- Exit-Code `11`, wenn ausschließlich die Result-Bundle-Erzeugung fehlschlägt.
- Strukturierter `logs/run.json`-Bericht.
- Vollständige versionierte `--json`-Abschlussverträge für `registry list`, `context`, `bundle` und `apply`.
- Atomare Veröffentlichung eines vollständig erzeugten Result Bundles.
- Best-effort-Notfallrettung von `execution.log` und `run.json` bei Bundle-Fehlern.
- Vollständiges PatchHarbor Result Bundle mit Base-Dateien, staged Patch, unstaged Patch, untracked Dateien, Kontext und Run-Logs.
- Separater PatchHarbor Watcher als dünne systemd-fähige Komponente.
- Verbindliche Abgrenzung gegenüber Repo Assist und PromptBridge.
- Expliziter Hinweis, dass PatchHarbor keine Sandbox und keine Absenderauthentifizierung ist.
- Aktualisierter Release-Audit-Vertrag für die neue Dokumentstruktur.

### Changed

- Die Hauptspezifikation ist jetzt vollständig selbständig und verweist für unverändertes 1.0.0-Verhalten nicht mehr nur auf eine verkürzte Zusammenfassung.
- Der sichere Mehr-Repository-Workflow verwendet ausschließlich echte Dateien in ZIP-Paketen.
- Im ZIP-Wurzelverzeichnis muss genau eine Datei `patch.json` heißen; weitere sichere Dateien und Verzeichnisse sind ausdrücklich zulässig.
- Der äußere Download-Dateiname und seine Endung sind keine Zuordnungs- oder Sicherheitsinformation.
- Repository-Name, Remote-URL, Branch und zuletzt verwendetes Repository dürfen nicht zur automatischen Auswahl dienen.
- Der Entrypoint wird nicht in das Repository geschrieben, sondern privat temporär ausgeführt.
- Alle übrigen sicheren Paketdateien sind bytegenaue Nutzdateien.
- Das Result Bundle ist immer vollständig rekonstruierbar und kein leichter Commit-Verweis.
- Der Base-Commit wird als vollständige Dateibasis ohne `.git`-Historie aufgenommen.
- Die Base-Dateibasis wird direkt aus Baum- und Blob-Objekten gelesen und ist unabhängig von Exportattributen.
- Result Bundles werden über eine temporäre Datei im endgültigen Result-Ordner atomar veröffentlicht.
- Der sichere Apply-Pfad prüft Entrypoint und Interpreter vor dem Schreiben endgültiger Nutzdateien.
- Der aktuelle Snapshot besteht aus `base/`, `changes/staged.patch`, `changes/unstaged.patch` und `untracked/`.
- Run-Logs sind verbindlicher Bestandteil des Result Bundles, sofern eine Ausführung stattgefunden hat.
- Ein sicher aufgelöstes Repository erhält auch bei späterer Ablehnung oder Ausführungsfehler einen Result-Bundle-Versuch.
- Ein Bundle-Fehler überschreibt einen vorhandenen primären Fehler nicht.
- `patchharbor bundle` behandelt die Bundle-Erzeugung selbst als primären Auftrag.
- Dauerhafte Logaufbewahrung und Rotation liegen nicht im Core; Watcher-Betriebslogs können durch systemd/journald verwaltet werden.
- `payload_files.py` beziehungsweise seine Nachfolge bleibt für sichere ZIP-Nutzdateien und atomisches Schreiben erhalten.
- `parser.py` bleibt für Pflichtmarker, META und MESSAGE zuständig.
- `patchharbor fs run` bleibt als expliziter manueller Runner bestehen und wird vom sicheren `apply`-Pfad klar getrennt.
- Die vorhandenen Verträge für Datei, Ordner, Pipe, ZIP-Reihenfolge, Interpreter, PowerShell, Timeout, Prozessbaum, TUI, temporäres Logging und Ressourcenlimits wurden vollständig in die neue Spezifikation übernommen.
- Der frühere Save-Modus mit chmod wird durch einen klar definierten Dry-Run ersetzt.
- Submodule werden im sicheren 1.1.0-Kontext abgelehnt, da ein vollständiger externer Snapshot nicht garantiert werden kann.

### Corrected during final specification review

- Base-Commit-Snapshots werden nicht mehr über ein exportattributabhängiges Archivverfahren erzeugt, sondern direkt aus Git-Baum und unveränderten Blob-Inhalten materialisiert.
- Committed Dateien können dadurch nicht durch `export-ignore` ausgelassen oder durch `export-subst` verändert werden.
- Der Result-Ordner wird physisch kanonisiert und darf weder identisch mit noch innerhalb irgendeiner registrierten Repository-Instanz liegen.
- Die temporäre Result-ZIP entsteht direkt im endgültigen Result-Ordner und wird dort über `os.replace()` dateisystemgleich atomar veröffentlicht.
- Das private System-Temp-Verzeichnis enthält nur Run- und Notfalldiagnosen, nicht die zu veröffentlichende ZIP-Datei.
- Entrypoint-Marker, Interpreter und Interpreter-Verfügbarkeit werden vor der ersten endgültigen Repository-Änderung geprüft.
- Temporäre STDIN-Artefakte wurden ausdrücklich in den gemeinsamen Cleanup-Vertrag aufgenommen.
- Registry-Mutationen verwenden einen globalen Lock, temporäre Registry-Dateien und atomaren Austausch.
- Für Registry- und Repository-Locks wurde eine verbindliche Lock-Reihenfolge festgelegt.
- Bei verlorener lokaler ID werden alte Zuordnungen desselben kanonischen Pfads vor der Vergabe einer neuen UUID entfernt.
- Das vollständige lokale Verzeichnis `.patchharbor/` ist reserviert, lokal ausgeschlossen und darf keine getrackten Pfade enthalten.
- Eine besondere, verlinkte oder anderweitig unsichere `.patchharbor`-Struktur wird abgelehnt.
- Assume-Unchanged, Skip-Worktree, Intent-to-add, Sparse-Checkout, Sparse-Index und nicht aufgelöste Merge-Stages werden im sicheren Pfad abgelehnt.
- Getrackte symbolische Links, Submodule, nicht reguläre Working-Tree-Einträge und nicht reguläre untracked Einträge werden im sicheren Pfad abgelehnt.
- Repository-Pfade müssen streng als UTF-8 darstellbar sein und werden ohne Unicode-Normalisierung verarbeitet.
- Die Ermittlung von Modus `100644` beziehungsweise `100755` ist über `core.fileMode` und die tatsächlichen Ausführungsbits normiert.
- Staged und unstaged Rekonstruktions-Patches werden unter einer kontrollierten Git-Umgebung ohne externe Diff-Programme, Textkonvertierung, Rename-Erkennung oder Farbe erzeugt.
- Das Result-Manifest enthält plattformunabhängige Metadaten zu Base- und untracked Dateimodi sowie Objekt- beziehungsweise Inhalts-Hashes.
- Ein eigener Tool-Exit-Code kennzeichnet nicht unterstützte Repository-Zustände.
- CLI-Optionen sind jetzt pro öffentlichem Befehl ausdrücklich begrenzt.

### Corrected during implementation-readiness review

- Für sämtliche Fingerprint-Felder ist die Payloadcodierung jetzt vollständig festgelegt: Pfade als ursprüngliche UTF-8-Bytes, Modi und Status als ASCII, Objekt-IDs als vollständige kleingeschriebene ASCII-Hex-Strings, Inhalte als rohe Bytes sowie Zähler und Größen als acht Byte unsigned big-endian.
- Zwei zusätzliche Referenzvektoren sichern eine staged Hinzufügung und eine unstaged Änderung ab.
- Base-Commit und Fingerprint werden unmittelbar vor der ersten Repository-Schreiboperation erneut geprüft; bei einer äußeren Änderung wird ohne Zielschreibzugriff abgelehnt.
- Repository-Pfade werden über Base-Baum, Index, getrackten Working Tree und untracked Dateien hinweg auf plattformübergreifende Darstellbarkeit geprüft.
- Groß-/Kleinschreibungs-Kollisionen, Windows-Gerätenamen, abschließende Punkte oder Leerzeichen, Steuerzeichen und Windows-ungültige Segmentzeichen werden abgelehnt.
- Die reservierten Segmente `.git` und `.patchharbor` werden in Base-Baum und Index ohne Beachtung der Groß-/Kleinschreibung erkannt.
- Paketformat 1 besitzt ein geschlossenes `patch.json`-Schema; unbekannte Felder, nicht kanonische UUIDs, abgekürzte Objekt-IDs und falsch formatierte Fingerprints werden abgelehnt.
- Die maschinenlesbaren Ausgaben aller vier öffentlichen `--json`-Befehle besitzen jetzt einen gemeinsamen versionierten Envelope und exakt definierte befehlsspezifische Resultate.
- Watcher-Eingangsordner müssen außerhalb aller registrierten Repositories liegen und dürfen sich mit Result-Ordnern nicht überlappen.
- Ubuntu 26.04 ist zusammen mit Ubuntu 24.04 und dem echten Windows-Runner ein normales blockierendes Release-Gate; die frühere Preview-Ausnahme entfällt.

### Removed

- FILE-Blöcke als zweiter Dateiübertragungsweg.
- FILE-spezifischer Parser-, Modell-, Anwendungs-, Darstellungs- und Testpfad.
- Base64 als vorgesehener Inline-Transport für Binärinhalte.
- Automatische Base64-Dekodierung als mögliche spätere PatchHarbor-Funktion.
- WebSocket-Quelle und WebSocket-Host aus PatchHarbor.
- Der frühere nachgelagerte WebSocket-Meilenstein.
- WebSocket-spezifische Vorbereitungen und Abhängigkeiten im PatchHarbor Core.
- Clipboard-Quelle.
- SSH-Quelle.
- Öffentliches Plugin-System.
- Zielprojekt-Testmanagement durch PatchHarbor.
- Git-Commit-, Branch-, Tag- und Release-Verwaltung durch PatchHarbor.
- Interaktive Kindskripte.
- Rekursive Ordnersuche.
- Rekursive Auflösung verschachtelter ZIP-Archive.
- Vollständige Pakettransaktion und automatische globale Rückabwicklung.
- Dauerhafte Logverwaltung und Logrotation im PatchHarbor Core.
- Automatisches Einsammeln beliebiger zusätzlicher Diagnose-, Test- oder Build-Artefakte.

### Responsibility moved

- Chat- und Netzwerktransport, Upload und Download: **PromptBridge**.
- Tests, Testbewertung, Commit, Retry, Abort und Journal: **Repo Assist**.
- Dauerhafte Download-Ordnerüberwachung: **PatchHarbor Watcher**.
- Technische Patch-Ausführung, Zustandsprüfung, Run-Logging und vollständiger Repository-Snapshot: **PatchHarbor Core**.

### Clarified

- `.git` und `.patchharbor` sind als ZIP-Pfadsegmente ausnahmslos verboten.
- Dieses Pfadverbot ist keine Sandbox und hindert ein gestartetes vertrauenswürdiges Skript nicht technisch an Benutzeraktionen.
- Ein Repository gilt erst nach eindeutiger Registrierung, lokaler ID-Prüfung und erfolgreichem Lock als sicher aufgelöst.
- Sobald ein Repository sicher aufgelöst ist, versucht PatchHarbor am Auftragsende ein Result Bundle zu erzeugen.
- `result_bundle.status=not_attempted` ist nur erlaubt, wenn kein Repository sicher aufgelöst wurde.
- Bei einem erfolgreichen primären Auftrag und fehlgeschlagenem Bundle gilt Exit `11`.
- Bei einem bereits fehlgeschlagenen primären Auftrag bleibt dessen Exit-Code erhalten; der Bundle-Fehler wird sekundär dokumentiert.
- Ein manuelles Bundle enthält keinen erfundenen Entrypoint-Log.
- Halbfertige Result Bundles werden nicht unter einem endgültigen Dateinamen veröffentlicht.
- Der Result-Ordner darf nicht innerhalb einer registrierten Repository-Instanz liegen.
- Nicht unterstützte Index-, Sparse-, Symlink- und Pfadkodierungszustände werden vor Fingerprint und Ausführung abgelehnt.
- Die erste Zustandsprüfung reserviert den erwarteten Zustand; die zweite Prüfung unmittelbar vor dem ersten Zielschreibzugriff schließt das verbleibende Änderungsfenster.
- JSON-Ausgabeformat 1 ist geschlossen und darf ohne Erhöhung von `output_version` keine zusätzlichen Felder erhalten.

### Migration and cleanup

Der erste 1.1.0-Commit ist ein Spezifikations-, Changelog- und Dokumentstruktur-Audit-Commit ohne Produktionscodeänderung.

Er aktualisiert zusätzlich den Release-Audit-Test auf:

```text
spec/SPECIFICATION.md
spec/SPECIFICATION_CHANGELOG.md
planning/1.0.0/commit-plan.md
planning/1.1.0/commit-plan-cleanup.md
planning/1.1.0/commit-plan.md
```

Das allererste anschließende Code-Cleanup ist:

> FILE-Blöcke vollständig aus Parser, Modellen, Anwendung, Darstellung, Tests und Dokumentation entfernen.

Dabei gilt:

- `payload_files.py` nicht pauschal löschen,
- sichere ZIP-Nutzdateien und atomisches Schreiben erhalten,
- ausschließlich den FILE-spezifischen Pfad entfernen,
- bestehende Base64-Nichtdekodierungs-Tests entfernen oder auf den alleinigen ZIP-Nutzdateivertrag umstellen,
- keinen Base64-Decoder entfernen, weil im aktuellen Stand keiner implementiert ist.

Danach folgen Registry mit Lock und atomarer Persistenz, normativer Fingerprint samt Sonderzustandsprüfung, `patch.json`, Apply, Repository-Lock, Dry-Run, Ergebnisvertrag, direkte Baum-/Blob-Materialisierung des vollständigen Result Bundles und separater Watcher.

---

## [1.0.0] – Implementierungsbasis vor 1.1.0

**Status:** Vorhandene stabile Produkt- und Codebasis.

### Included

- Kontrollierter plattformübergreifender Runner.
- Python 3.12 oder neuer.
- pipx-Installation und Konsolenbefehl `patchharbor`.
- `patchharbor fs run [PFAD]`.
- Direkte Datei, einmaliger nicht rekursiver Ordnerscan, ZIP und STDIN.
- Exakter Skriptmarker `# PATCHHARBOR`.
- Optionale META- und MESSAGE-Inhalte.
- ZIP-PatchBundles mit mehreren geordneten Skripten.
- Bytegenaue Text- und Binär-Nutzdateien.
- Sichere relative ZIP-Pfade und atomisches Schreiben.
- Bash, Windows PowerShell und PowerShell 7 über geprüfte Zuordnung.
- PowerShell ohne Execution-Policy-Bypass.
- Timeout, zweisekündige Beendigungsfrist und vollständiger Prozessbaum.
- Strg+C-Vertrag.
- Plain-Ausgabe, Terminaldashboard, Rolling Buffer und finaler Redraw.
- Optionales vollständiges temporäres Run-Log.
- Ressourcenlimits und ZIP-Bomben-Schutz.
- Linux-, Windows-, Wheel- und pipx-Testpfade.

### Superseded by 1.1.0

Die frühere Produktspezifikation war mit dem Commit-Plan kombiniert und enthielt zusätzliche inzwischen verworfene oder neu zugeordnete Zukunftspfade. Die neue 1.1.0-Spezifikation übernimmt alle fortgeltenden Verträge vollständig und ersetzt diese alte Produktbeschreibung.
