# PatchHarbor 2.0.0 – WRC-Implementierungsplan

**Plan-ID:** `PH-200` · **Revision:** 2 · **Stand:** 11. November 2026<br>
**Zielversion:** **2.0.0**<br>
**Status:** `200-02.W1` durch Apply 092 bestätigt; Bundle 093 repariert `200-02.W2` und setzt die Folgephasen fort.<br>
**Fortschritt:** **4 / 38 Umsetzungscommits**, zwölf WRC-Schritte; die Protokoll-Work-Phase besteht aus drei Teilcommits.<br>
**Aktiver Planpfad:** `planning/2.0.0/commit-plan.md`<br>
**Zugehöriger Detailentwurf:** [Lokale Testmessung und Profiling](test-profiling.md).
Dieser Detailentwurf gehört zu diesem Plan; er ist kein konkurrierender Plan.

## 1. Auftrag, Ausgangsbasis und Entscheidungen

Das Produktleitbild ist **Task Bundle → Execute → Result Bundle**. Eine KI
bereitet einen zustandsgebundenen Auftrag vor; PatchHarbor prüft und führt ihn
lokal aus und liefert den tatsächlichen Zustand zurück. Ein Auftrag darf reine
Diagnose sein, ohne Dateiänderung und ohne neuen Commit. PatchHarbor bleibt der
Produktname. Die Integritätsprüfung ersetzt weder Herkunftsvertrauen noch eine
Sandbox.

Geprüfte Planungsbasis ist das veröffentlichte **1.9.1** auf
`7a10a315361627340ecd9ac594b860e81ac78f07`:

- `main`, `dev` und `v1.9.1` waren beim Releaseabschluss auf diesem Commit.
- Tatsächlicher Apply 087: 3.727 bestandene Tests, 16 Skips, vier Worker.
- Alle 13 Abnahmelanes in [CI 42979436142](https://github.com/cdoehn/patch-harbor/actions/runs/42979436142)
  erfolgreich; [Release 1.9.1](https://github.com/cdoehn/patch-harbor/releases/tag/v1.9.1)
  mit fünf heruntergeladenen und geprüften Artefakten veröffentlicht.
- Der alte Development-Hauptcheckout enthält fremde/uncommittete Arbeit. Er
  wird weder zurückgesetzt noch als aktueller 1.9.1-Quellstand ausgegeben.
  Neue Umsetzungsstände werden aus einem aktuellen bestätigten Result innerhalb
  der Development-Kopie vorbereitet. Diese SHA ist Planungsprovenienz, keine
  pauschale Bindung für zukünftige Bundles.

Ausgangspunkt ist der bereitgestellte Auftrag
`PatchHarbor_Task_Bundle_Execute_Result_Bundle_Coder_Prompt.md`. Die folgenden
späteren Nutzerentscheidungen ersetzen seine widersprechenden Anforderungen:

| Entscheidung | Verbindliche Konsequenz |
| --- | --- |
| Keine API-Rückwärtskompatibilität | Alte Python-Namen, Typ-Aliase und Keyword-Übersetzungen entfallen. Keine Kompatibilitätsschicht für externe Aufrufer. |
| `ScriptBundle` ist angenommen | Der bisherige generische Skript-/ZIP-Typ `models.PatchBundle` wird `ScriptBundle`; er ist kein repositorygebundenes Task Bundle. |
| Zwischenstände werden nicht produktiv eingesetzt | Keine Zwischenreleases, kein Parallelbetrieb alter/neuer Protokolle, kein Rolling Upgrade. Interne APIs und Datenmodelle dürfen direkt umgebaut werden. |
| WRC ist ausdrücklich gewünscht | Echte, aufeinanderfolgende und geprüfte Work-/Right-/Clean-Zustände; keine nachträgliche Aufteilung eines fertigen Endzustands. |
| Testvorbereitung von Testlaufzeit trennen | `setup`, `call` und `teardown` getrennt erfassen; Start/Collection und gemeinsame Fixtures gesondert ausweisen. |
| Profiling ausschließlich lokal, ausdrücklich gestartet | Eigener lokaler Befehl; SQLite, Python-Profile und `strace`-Daten bleiben lokal. Keine Profiling-CI, Uploads oder Hintergrunddienste. |
| GitHub-Empfehlungen berücksichtigen | Topics sofort per `gh`; Badges und Job Summaries als Repositoryänderungen in diesem Plan. |

Die CLI-Ausnahmen aus dem Auftrag bleiben bewusst bestehen: `apply` ist ein
deprecated Alias für `execute`; `fs run` bleibt als deprecated Skriptweg
funktionsfähig. Das begründet keine Python-API- oder Altformatkompatibilität.

Die bestehenden Sicherheitsverträge in `spec/SPECIFICATION.md`,
`spec/SPECIFICATION_EXTENSION_PYZ_PACK.md` und
`spec/SPECIFICATION_EXTENSION_CPYTHON_310_311.md` bleiben die Grundlage.
Aktuelle Muss-Regeln zu 1.x-API-/Bundle-Kompatibilität werden beim Protokollwechsel
gezielt ersetzt. Historische Pläne und Nachweise bleiben historisch. Alte
Rollback-, Test- und CI-Regeln aus dem 1.1.0-WRC-Plan werden nicht übernommen.

**Ursprünglicher Planungsauftrag:** Plan und lokale Nachweise anlegen sowie
GitHub-Topics setzen. Der anschließende Auftrag liefert mit Bundle 088 den
ersten Produktstand `200-01.W` und übernimmt die Planunterlagen im selben Commit.
Die Dokumentübernahme erzeugt keinen zusätzlichen Plancommit. Ein vorbereiteter
Stand bestätigt keinen tatsächlichen Apply und keine Abnahme.

## 2. GitHub-Empfehlungen: Aufwand, Nutzen, Risiken und Erledigung

| Punkt | Aufwand / Nutzen | Konkretes Risiko und Entscheidung | Status |
| --- | --- | --- | --- |
| Repository-Topics | Sehr klein; bessere Auffindbarkeit | Nur Metadaten, vorhandene Topics nicht entfernen; Ergebnis zurücklesen | **Erledigt, 11.11.2026:** `python`, `ai-assisted-development`, `git`, `developer-tools`, `cli`, `cross-platform`, `automation` per `gh repo edit --add-topic` gesetzt und geprüft. |
| Release-, Python- und MIT-Badges | Klein; aktueller Einstieg in Installation und Lizenz | Badge-Ausfall darf Lesbarkeit nicht verhindern; Release-Badge zeigt veröffentlichte stabile Version, nicht den Entwicklungsstand | In `200-11.W`. |
| Optionales CI-Badge | Kleiner Einbau, aber irreführender Status möglich | Der Workflow unterscheidet prepare/acceptance/publish; der letzte grüne Lauf ist kein Nachweis für einen beliebigen HEAD | **Kein allgemeines grünes CI-Badge einbauen.** Auf CI-/Abnahmenachweis mit voller SHA und Run-Link verweisen. |
| Actions Job Summaries | Mittel; vorhandene Resultate direkt sichtbar | Bisherige JSONs enthalten keine Phasenlaufzeiten. Fehlerberichte darf der strenge Erfolgsvalidator nicht zu grünen Reports umdeuten | Phasenmessung in `200-05`, Summaries in `200-10`; ausschließlich additive Beobachtung. |
| Lokales Profiling | Größer; Ursachen statt bloßer Langsamkeitsliste | Messaufwand, Speichergrenzen und Prozesszuordnung können Befunde verfälschen | Eigene Schritte `200-06` bis `200-09`, kontrollierte Messmodi und belegte Unsicherheit. |

Topics wurden ohne Quellcommit, Änderung von Branchregeln oder CI-Dispatch gesetzt.
Badges und Summaries gehören in den geprüften Quelländerungsweg; sie werden nicht
als direkte GitHub-Dateiedits an diesem vorbei eingeschoben. Neue Python-
Runtime-Abhängigkeiten sind dafür nicht vorgesehen.

## 3. WRC und überprüfbare Zwischenstände

**W – Let it Work:** Kleinsten durchgängigen Durchlauf des Schritts implementieren,
einschließlich notwendiger Sicherheitsprüfungen und eines echten Verhaltenstests.
Es darf kein unsicherer Zwischenstand mit Verweis auf ein späteres R akzeptiert werden.

**R – Do it Right:** Dieselbe Fähigkeit gegen Fehler, Rennen, Abbruch, Ressourcen-
und Plattformgrenzen absichern. Keine neue große Funktion als Härtung verstecken.

**C – Make it Clean:** Nachgewiesene Doppelungen und tote Übergangspfade entfernen,
Namen und Verantwortlichkeiten vereinfachen. Kein neues Produktverhalten, kein
Versionssprung und keine künstlich erzeugte Unordnung für einen Cleanup-Commit.

WRC-Stände sind Entwicklungsstände und brauchen keine eigene Veröffentlichung
oder Produktionsmigration. Die vollständigen lokalen Commit-Gates bleiben
erhalten. Der zusammengehörige Protokollwechsel wird in einem vertikalen W
hergestellt, weil seine Komponenten gemeinsam geprüft werden müssen; nicht um
einen parallelen 1.x-Produktionsbetrieb zu ermöglichen.

Jeder Commit entsteht erst nach seinem Gate im Apply-Repository und wird durch
das tatsächliche Result bestätigt. Nach der Nutzerpräzisierung vom 11. November
2026 führt Development ausschließlich statische Analyse durch; Tests laufen nur
im Apply, vor jedem Commit als vollständige parallele Suite.
Diagnostisches Profiling einzelner Tests ist **kein serielles Commit-Gate**.
Keine Vollsuite in Development, keine abgeschwächten Gates, keine Wiederholung
unveränderter grüner Prüfungen ohne neuen Anlass.

Bei Fehlern bleiben Dateien und bereits erfolgreiche Commits erhalten. Kein
globaler Rollback, kein Reset/Clean, keine Verschiebung historischer Tags.
Korrekturbundles heißen `200-XX-PHASE-FIXn`. Bei einem bereits vorhandenen
fehlerhaften Commit beginnt der zusätzliche Korrekturcommit mit `Fix:` und
erhöht nicht den Planzähler. Scheitert das Gate vor dem ersten Commit, wird der
noch offene Plancommit einschließlich Korrektur unter seinem geplanten Subject
erstellt; es entsteht kein zusätzlicher Commit. Ein C ohne tatsächlichen Bereinigungsbedarf
führt zu einer begründeten Planrevision, nicht zu einem leeren Commit.

## 4. Zielarchitektur, Umbenennungen und Verträge

### 4.1 Begriffliche Grenzen

| Bestand | Ziel / Behandlung |
| --- | --- |
| `models.PatchBundle`, `resolve_patch_bundle` für den generischen Runner | `ScriptBundle`, `resolve_script_bundle`; geordnete Skripte plus Nutzdateien, keine Task-Zustandsbindung erfinden. |
| `PatchManifest`, `PatchInspection`, `PatchValidationResult`, `PatchPackResult` | `TaskManifest`, `TaskInspection`, `TaskValidationResult`, `TaskPackResult`. |
| `PatchEntry`, `PatchEntryRole`, `PatchMessage`, `PatchValidationScope`, `PatchAdmission` | Entsprechende `Task…`-Namen, einschließlich expliziter API-Exports. |
| `pack_patch`, `inspect_patch`, `validate_patch` | `pack_task`, `inspect_task`, `validate_task`. |
| `apply`, `apply_guarded`, `apply_next`, `apply_readiness` | `execute`, `execute_guarded`, `execute_next`, `execute_readiness`. |
| `ApplyLock`, `ApplyLockKind`, `ApplyReadiness`, `AutomaticApplyResult`, `AutomaticApplyStatus` | Entsprechende `Execute…`-/`AutomaticExecute…`-Typen. Physische Lockidentitäten nicht allein wegen Typnamen ändern. |
| `RunOperation.APPLY`, `ApplyPrimaryOutcome`, `apply_json_envelope` und zugehörige Reportmethoden | `EXECUTE`, `ExecutePrimaryOutcome`, `execute_json_envelope`; neue Maschinenverträge. |
| `api.run` für den eigenständigen Skriptweg | `api.run_scripts`; dokumentiert deprecated wie `fs run`. Keine `run`-Weiterleitung. |
| `api.dry_run` | Neutraler Name bleibt; delegiert an denselben Execute-Kern mit `dry_run=True`. |
| `patch_manifest.py`, `patch_package.py`, `patch_inspection.py`, `patch_pack.py` | `task_manifest.py`, `task_package.py`, `task_inspection.py`, `task_pack.py`; Aufrufer/Tests im selben Zwischenstand umstellen. |
| `apply_*.py`, `application_apply.py`, Watcher-`apply_boundary.py` | Semantisch entsprechende `execute_*.py`, `application_execute.py`, `execute_boundary.py`; vorhandene Grenzziehung weiterverwenden. |
| Git-Patches, `git apply`, Produkt-/Entrypointmarker | Fachlich richtige Git-Begriffe, `PatchHarbor`, `patchharbor`, `PATCHHARBOR_META` und `# PATCHHARBOR` bleiben. |

Keine globale Textsubstitution. Die Bestandsinventur umfasst alle API-Exports,
Enums, Fehlercodes, Keyword-Argumente, Imports, Testhelfer und generierten Texte.
Neutrale Typen wie `BundlePayload`, `PackageFile`, `RepositoryContext` und
`RunReport` brauchen keinen künstlichen neuen Namen. Es entsteht kein zweiter
Paketleser, Payload-Writer, Git-Adapter, Test-Scheduler oder Execute-Kern.

### 4.2 Geplante Versionierung

Die folgende Matrix ist der Zielentwurf. Vor `200-02.W` werden die geschlossenen
Feldlisten und betroffenen Verbraucher gegen die dann bestätigte Basis fixiert.
Produktversion, Bundleformat, Beobachtungsformat und Testdatenbank sind getrennte
Verträge; ihre Nummern werden nicht pauschal gleichgesetzt.

| Vertrag | 1.9.1 / Ausgangslage | 2.0.0-Ziel |
| --- | --- | --- |
| Task-Manifest | `patch.json`, Marker `patch-harbor`, Format 1 | `task.json`, Marker `patch-harbor-task-bundle`, **Task-Format 2**. |
| Result-Manifest | `manifest.json`, Marker `patch-harbor-result-bundle`, Format 3 | Derselbe Result-Marker, **Result-Format 4**, Zuordnung über `task_sha256` und Execute-Bericht. |
| Eingebettetes `logs/run.json` | Kein eigenes Formatfeld, durch Resultvertrag gebunden; `operation: apply` | Durch Result 4 gebundener Run-Vertrag mit `operation: execute` und angepassten Fehler-/Ergebnisfeldern; alle Leser gemeinsam umstellen. |
| Environment/Handoff | Format 1, `filename_schemas.Patch` | Format 2, Task-/Result-Bundle-Namen und neue Befehle. |
| Eingebettete Runtime-Metadaten | Format 2, `patch_formats`, alte Operationsnamen | Format 3, `task_formats: [2]`, `result_formats: [4]`, neue Operationen. |
| Execute-CLI-JSON | Apply-Ausgabeversion 1 | Execute-Ausgabeversion 2; CLI-Alias liefert denselben neuen Vertrag. |
| Pack/Inspect/Validate-JSON | Ausgabeversion 2 | Ausgabeversion 3 für geänderte Task-Felder/Typen. |
| Snapshot-/Integrationsfähigkeiten | Vertragsfamilie 1 | Integrationsvertrag 2, `guarded_execute_contract_version`; geänderte Snapshot-Enums/Operationsnamen ebenfalls explizit versionieren. Unveränderte Safe-Reference-Semantik nicht beiläufig ändern. |
| Monitor | Snapshot-Hülle 1; Live-Publisher 2 | Snapshot-Hülle 2 und Live-Format 3 für neue Felder/Enums. Alte Beobachtungsdateien gelten als nicht aktuelle Fremdgeneration. |
| Watcher-Worker | Privater Scope-/Fortschrittsvertrag 1 | Nur tatsächlich geänderte Verträge versionieren. Neutraler Scope/Lock-Vertrag kann 1 bleiben; neuer Execute-Report muss eindeutig erkannt werden. |
| Lokaler Exchange-/Replay-State | Format 4, teils historische ältere Datensätze | Datenmodell frei refaktorieren; Speicherformat nur bei Feldänderung auf 5. Bestehende Historie und aktive Attempts nicht löschen oder als neue Erfolge umdeuten. |
| Konfiguration/Registry, Fingerprint, PYZ-Rezept/-Profil | Eigenständige bestehende Verträge | Keine Änderung allein wegen neuer Produktversion. UUIDs, Bindung, Algorithmus und watcherfreies Core-Profil erhalten. |
| Testnachweis-JSON | Format 2; Phasen ohne Zeitmessung | Erfolgsnachweis unverändert; additive, separat versionierte `telemetry` mit Format 1. |
| Lokale Profiling-Datenbank | Noch nicht vorhanden | SQLite-Schema 1; eigenständige Messläufe und lokale Rohartefakte. |

Alte Patch-/Result-ZIPs werden von repositorygebundenen Routen klar abgelehnt,
auch über `apply`, bei umbenannter ZIP oder gemischten Manifesten. Kein
Kompatibilitätsleser und keine Bundlekonvertierung. `fs run` bleibt der gesonderte
Skriptweg und wird nie zum automatischen Fallback nach gescheitertem Execute.
Seine allgemeine Skriptsemantik ist kein Versprechen, Task-/Result-ZIPs zu validieren.

### 4.3 Dateinamen, Herkunft und tatsächliche Ergebnisse

Automatische Dateinamen enthalten zentral `_Task_Bundle_` oder `_Result_Bundle_`.
Explizite Ausgabedateinamen werden exakt respektiert; sie sind die dokumentierte
Ausnahme zur automatischen Benennung. Keine stille Umbenennung. Ein explizites
Ausgabeverzeichnis verwendet weiterhin die kanonische automatische Benennung.
Identität und Gültigkeit ergeben sich aus Inhalt und Manifest, nicht dem Namen.

Suffixe, Browser-Zusätze, Unicode-/Großkleinschreibung, Kollisionen und unfertige
Downloads werden unter Linux/Windows geprüft. Vollständige IDs und Hashes bleiben
in JSON/Bindungen erhalten; Kürzungen gelten nur für die Anzeige.

Ein gültiges Result kann einen fehlgeschlagenen Auftrag und einen dirty Zustand
belegen. Entrypoint-Code 0 bei fehlgeschlagener Result-Publikation ist kein
Gesamterfolg. Commit, Rücknahme und nächster Entrypointschritt werden nur angezeigt,
wenn dafür tatsächliche Informationen vorliegen.

## 5. Schritte, Abhängigkeiten und Commitfolge

| Schritt | Ergebnis | Voraussetzung |
| --- | --- | --- |
| 200-01 | ScriptBundle klar abgrenzen, direkten API-Umbau beginnen | Bestätigte aktuelle Basis |
| 200-02 | Neue durchgängige Task-/Execute-/Result-Protokollgeneration | 200-01.C |
| 200-03 | Watcher und Monitor vollständig auf Task/Execute ausrichten | 200-02.C |
| 200-04 | Installierte Runtime, Handoff und kontrollierter Umstieg | 200-03.C |
| 200-05 | Vorbereitung, Testkörper und Aufräumen getrennt messen | 200-04.C |
| 200-06 | Lokaler Startbefehl und persistente Messdatenbank | 200-05.C |
| 200-07 | Python-Laufzeit- und Speichermessung je Phase | 200-06.C |
| 200-08 | Lokale Linux-Systemaufrufe mit strace auswerten | 200-07.C |
| 200-09 | Nachvollziehbare Optimierungskandidaten und Vergleiche | 200-08.C |
| 200-10 | GitHub-Job-Zusammenfassungen aus normalen Testreports | 200-05.C; regulär nach 200-09.C |
| 200-11 | README, Badges, aktuelle Anleitungen und Integrationshinweise | 200-10.C |
| 200-12 | Finalen 2.0.0-Stand herstellen und vollständig abnehmen | 200-11.C |

`200-01.W` und `200-01.R` sind durch die Commits
`3670347923c107c8ae2b76d0d4c65ce2516fa63c` und
`bdba905c4cb982bca0e2f86384c3b97ea729a886` bestätigt. Result
`930a7e0d-497e-4009-9462-df7ea75a0d57` belegt den sauberen letzten Stand.
`200-01.C` ist zusätzlich durch Commit
`682b042407048f5e0b6da23f70aad5c845ce0f37` bestätigt. `200-02.W1` ist durch
Commit `c7fe8f991fd877c10acd4c73f3d6f1b9d229792a` und Result
`86c0251b-7102-4bd4-95d0-099e695053f6` bestätigt. Der folgende W2-Lauf
scheiterte vor dem Commit; sein tatsächlicher uncommitteter Zustand ist die
gebundene Ausgangsbasis. Die übrigen 34 Positionen sind **OFFEN**;
Bundle 093 bereitet die reparierten Positionen 5–10 vor.
Die Commit-Subjects sind verbindliche
Planvorlagen; Fortschritt wird erst mit tatsächlichem Commit und Result eingetragen.

| Position | Kennung | Commit-Subject |
| ---: | --- | --- |
| 1 / 38 | `200-01.W` | `refactor(scripts)!: separate ScriptBundle and explicit script execution [200-01.W]` |
| 2 / 38 | `200-01.R` | `test(scripts): preserve deprecated runner boundaries [200-01.R]` |
| 3 / 38 | `200-01.C` | `refactor(scripts): remove ambiguous script bundle terminology [200-01.C]` |
| 4 / 38 | `200-02.W1` | `refactor(protocol)!: name task models and Python boundaries explicitly [200-02.W1]` |
| 5 / 38 | `200-02.W2` | `feat(protocol)!: switch producers and consumers to Task 2 and Result 4 [200-02.W2]` |
| 6 / 38 | `200-02.W3` | `feat(execute)!: expose execution reports and deprecated CLI alias [200-02.W3]` |
| 7 / 38 | `200-02.R` | `test(protocol): harden task result and execution contracts [200-02.R]` |
| 8 / 38 | `200-02.C` | `refactor(protocol): remove obsolete readers and public API names [200-02.C]` |
| 9 / 38 | `200-03.W` | `feat(monitor): expose task execution across watcher views [200-03.W]` |
| 10 / 38 | `200-03.R` | `test(watcher): preserve polling locks and live observation [200-03.R]` |
| 11 / 38 | `200-03.C` | `refactor(monitor): consolidate task activity projections [200-03.C]` |
| 12 / 38 | `200-04.W` | `feat(handoff): verify installed version 2 bundle roundtrips [200-04.W]` |
| 13 / 38 | `200-04.R` | `test(runtime): verify offline bootstrap and isolated cutover [200-04.R]` |
| 14 / 38 | `200-04.C` | `refactor(handoff): consolidate generation and capability sources [200-04.C]` |
| 15 / 38 | `200-05.W` | `feat(tests): capture separate setup call and teardown timings [200-05.W]` |
| 16 / 38 | `200-05.R` | `test(tests): verify phase attribution and incomplete timings [200-05.R]` |
| 17 / 38 | `200-05.C` | `refactor(tests): isolate telemetry from acceptance evidence [200-05.C]` |
| 18 / 38 | `200-06.W` | `feat(profiling): add local command and SQLite run history [200-06.W]` |
| 19 / 38 | `200-06.R` | `test(profiling): preserve local data across interruption [200-06.R]` |
| 20 / 38 | `200-06.C` | `refactor(profiling): separate capture storage and reporting [200-06.C]` |
| 21 / 38 | `200-07.W` | `feat(profiling): record phase-specific Python time and memory [200-07.W]` |
| 22 / 38 | `200-07.R` | `test(profiling): expose process coverage and measurement overhead [200-07.R]` |
| 23 / 38 | `200-07.C` | `refactor(profiling): normalize Python profile evidence [200-07.C]` |
| 24 / 38 | `200-08.W` | `feat(profiling): collect local strace process evidence [200-08.W]` |
| 25 / 38 | `200-08.R` | `test(profiling): harden syscall attribution and trace limits [200-08.R]` |
| 26 / 38 | `200-08.C` | `refactor(profiling): separate syscall parsing and correlation [200-08.C]` |
| 27 / 38 | `200-09.W` | `feat(profiling): rank evidence-backed optimization candidates [200-09.W]` |
| 28 / 38 | `200-09.R` | `test(profiling): reject incomparable runs and uncertain conclusions [200-09.R]` |
| 29 / 38 | `200-09.C` | `refactor(profiling): share phase-aware report queries [200-09.C]` |
| 30 / 38 | `200-10.W` | `feat(ci): summarize existing test reports in Actions [200-10.W]` |
| 31 / 38 | `200-10.R` | `test(ci): preserve gates with failed and missing summaries [200-10.R]` |
| 32 / 38 | `200-10.C` | `refactor(ci): reuse bounded report rendering [200-10.C]` |
| 33 / 38 | `200-11.W` | `docs: explain the Task Execute Result workflow and release badges [200-11.W]` |
| 34 / 38 | `200-11.R` | `test(docs): exercise current commands and upgrade examples [200-11.R]` |
| 35 / 38 | `200-11.C` | `docs: remove conflicting active terminology and duplicate guidance [200-11.C]` |
| 36 / 38 | `200-12.W` | `chore(release): prepare the complete 2.0.0 candidate [200-12.W]` |
| 37 / 38 | `200-12.R` | `test(release): verify version 2 end-to-end acceptance [200-12.R]` |
| 38 / 38 | `200-12.C` | `refactor(release): remove remaining development scaffolding [200-12.C]` |

### 200-01 – ScriptBundle und vorbereitende Entflechtung

**W:** `ScriptBundle` samt Aufrufern und Testhelfern einführen; `run_scripts`
klar vom repositorygebundenen Execute trennen. `fs run` und seine neue benannte
Python-Funktion als deprecated markieren; CLI-Warnung auf stderr, Library-Warnung
mit Aufruferbezug, keine globalen Warning-Filter. Mit dem ersten API-Bruch
Quellversion `2.0.0.dev0` verwenden; dies ist kein Zwischenrelease.

**R:** Echte Skript-/Verzeichnis-/ZIP-Fälle, Ausführungsreihenfolge, Payloads,
Exit-Codes, Timeout, Streams und Marker-/Pfadprüfungen erhalten. Keine Warnung
in neue Execute-Aufrufe einschleusen. Kein Task-Fallback über den Skriptweg.

**C:** Irreführende Script-`patch`-Bezeichner und doppelte Auflösung beseitigen;
neutrale Datenträger und gemeinsame sichere Primitive weiterverwenden.

**Fertig, wenn:** Skriptweg und Task-Konzept sind im Code unterscheidbar;
vorhandenes Runnerverhalten bleibt belegt. Fokus: `models.py`, `bundles.py`,
Runner, API/CLI und zugehörige Directory-/ZIP-/Interpretertests.

### 200-02 – Kohärenter Protokollwechsel

**Revision 2:** Der große Work-Schritt wird in drei aufeinanderfolgende, jeweils
vollständig im Apply geprüfte Teilstände gegliedert: W1 benennt Task-Modelle,
Module und Python-Grenzen um; W2 stellt die gekoppelten Erzeuger, Leser und
Runtime-Metadaten auf Task 2 / Result 4 um; W3 schließt Execute-Berichte, CLI-Alias
und aktuelle ausführbare Hinweise ab. Dies sind unveröffentlichte interne
Zwischenstände ohne Kompatibilitätsbrücken. W ist erst nach W3 abgeschlossen.
Die zwei zusätzlichen Teilcommits erhöhen die Gesamtzahl auf 38; es entstehen
keine leeren Commits und keine Zwischenreleases.

**W:** Task-2-Erzeuger/Leser, Execute inklusive guarded/automatic/dry-run,
Result-4-Erzeuger/Leser, öffentliche API, CLI-Alias, neue Dateinamen,
Runtime-Capabilities, ausführbarer Bootstrap und zwingende Watcher-Aufrufer
gemeinsam umstellen. Aktive Spezifikationspflichten und minimale ausführbare
Handoff-Anweisungen im selben Zustand korrigieren. Normale Erfolgskette und
ein Fehlerresult funktionieren bereits. Kein temporärer öffentlicher Altleser.

**R:** Fehlende/falsche/doppelte Manifeste, manipulierte Hashes, alte/future
Formate, Symlinks, ZIP-Ressourcen, stale Referenzen, Repo-ID-/Fingerprintfehler,
Race vor Mutation, Abbruch, Teilfortschritt, Resultfehler und No-clobber prüfen.
Registry-, Replay- und Lockgrenzen schon in W erhalten und hier vertiefen.

**C:** Unerreichbare alte Leser/Serialisierer, Python-Exports und Importpfade
entfernen; Paketfacts, Ausführung und Result-Publikation über vorhandene
Verantwortlichkeiten führen. Alte Fixtures nur dort behalten, wo sie Ablehnung
oder historische Provenienz belegen. Sicherheitsnachweise an unterschiedlichen
Zeitpunkten nicht zur vermeintlichen Laufzeitoptimierung zusammenlegen.

**Fertig, wenn:** Ein frisches Result 4 führt über Task 2 und Execute zu Result 4
und einem zweiten Task. Alte CLI-Namen reaktivieren kein altes Format; alle
Maschinenverträge sind vollständig und versioniert. Der große W ist eine
fachliche Protokolleinheit, keine Staffelung inkompatibler Produktionsreleases.

### 200-03 – Watcher, Exchange und Monitor

**W:** Sichtbare Begriffe, Ereignistypen und Ausführungsdetails auf Task/Execute
umstellen. In jeder Monitoransicht bleibt die Fünf-Zeilen-Aktivität sichtbar:
zwei vergangene Ereignisse, aktuelle Aktivität mit Spinner, zwei nur aus dem
bekannten Ablauf ableitbare nächste Schritte. Unbekannte Zukunft offen benennen.
Repo, Artefakttyp, Kennung und Bundle-Nummer anzeigen, sofern vorhanden.

**R:** Grün für bestätigten Erfolg, Rot für bestätigten Fehler, Lila für erwartete
oder ungesicherte Zukunft, Grau für neutral/inaktiv; keine Lampe und kein
zusätzlicher Pfeil. Kompakte Zeiten und sechs Zeichen plus `...` mit Vollansicht-
Umschaltung erhalten. Repository-/Exchange-Zustand hervorheben. Polling mit vier
Sekunden Standard und frei einstellbarem positivem endlichem Intervall,
Eventmodus, Debouncing, Locks, Replay und tatsächliche Timeoutweitergabe prüfen.
Auch stale/malformed State, parallele Instanzen, fehlender Exchange, CIFS und
die Windows-Publikationskorrektur aus 1.9.1 bleiben abgedeckt.

**C:** Gemeinsame typisierte Zustandsprojektion für Übersichten/Details verwenden;
keine zusätzliche Zustandsmaschine in der TUI. Beobachtung darf keine Ausführung,
Archivierung oder automatische Reparatur auslösen.

**Fertig, wenn:** Alle Ansichten erklären die tatsächliche Aktivität; der Monitor
erfindet weder Commits noch sichere zukünftige Aktionen. Tests prüfen Verhalten,
Zustandsdaten und Lesefreiheit, keine Farben, Spinnerframes oder Layout-Snapshots.

### 200-04 – Runtime, Handoff und einmaliger Umstieg

**W:** Öffentliche 2.0-API und CLI aus frisch installiertem Wheel, gebautem sdist
und Core-PYZ gegen reale clean/dirty Referenzen prüfen. Der Result-Bootstrap
arbeitet offline und watcherfrei. Erstes frisches 2.0-Result kann ohne altes
Result erzeugt werden. Laufende Aufträge benötigen keine nachträgliche Runtimeänderung.

**R:** Manipulierte Runtime/Metadaten, unbekannte Capability, `unavailable`,
read-only Installation, leerer Cache, Abbruch und Self-update-Grenze prüfen.
Der gesamte Zwei-Runden-Zyklus muss auch Diagnose ohne Commit, fehlgeschlagenen
Entrypoint mit erhaltenen Änderungen, Timeout und Publikationsfehler abdecken.
Lokalen Umstieg in isolierten Verzeichnissen proben; keine automatische
Migration alter Bundles oder unbemerkte Umstellung installierter Dienste.

**C:** Ausführbaren Bootstrap weiterhin aus einer Quelle generieren; gemeinsame
Runtime-Fakten und Verpackungsprüfungen nutzen. Dokument-/Template-Duplikate
bereinigen, aber voneinander unabhängige Sicherheitsgrenzen erhalten.

**Fertig, wenn:** Der portable Verbraucher kann ohne Entwicklungscheckout arbeiten.
Ein Integrationsleitfaden nennt alte Aufrufe/Pins und die neuen Verträge. Er
ändert keine SpecRoad-Kopie, Control-Instanz oder globale Installation.

### 200-05 – Vorbereitung, reine Testausführung und Aufräumen

**W:** Die vorhandenen `setup`-/`call`-/`teardown`-Reports um getrennte
Zeitmessung in einer additiven `telemetry` erweitern. Prozessstart, Collection,
Session-Ende und Workerzuordnung separat erfassen. Standardranking nach `call`,
eigene Ranglisten für `setup` und `teardown`; keine Gesamtzeit als reine Testzeit.

**R:** Skips, Setup-/Teardownfehler, Subtests, Abbruch und fehlende Worker sauber
abbilden. Session-/Module-/Class-Fixtures mit Scope, Lebenszyklus und Verbrauchern
erfassen; ihre Kosten nicht jedem Test zuschlagen. Parallel überlappende Zeitspannen
nicht als Job-Walltime addieren. Messung darf Teststatus und Beweissignaturen
nicht verändern. Ein kontrollierter Versuch mit unterschiedlicher Vorbereitung,
Testkörper und Cleanup belegt die Trennung.

**C:** Messadapter und fachliche Messmodelle vom strengen Erfolgsvalidator
trennen. `tools/test_evidence.py`, `test_results.py`, `result_io.py` und den
vorhandenen Launcher nutzen; keinen neuen Scheduler einführen.

**Fertig, wenn:** Die Beispiele und Abnahmen im
[Detailentwurf, Abschnitte 2 und 8](test-profiling.md#2-messvertrag-vorbereitung-testkörper-und-aufräumen)
erfüllt sind. Die bestehenden CI-Artefaktnamen, Report-Format-2-Gates und
Worker-Nachweise bleiben gültig; Telemetrie fehlt sichtbar statt als Nullwert.

### 200-06 – Lokales Werkzeug und SQLite

**W:** `python tools/profile_tests.py run …` sowie lesende `report`- und
`compare`-Befehle bereitstellen. Eindeutige Runs, Quellbindung, ausgewählte Tests,
Phasen, Wiederholungen und Rohartefaktpfade lokal transaktional speichern.
Dieser erste W kann zunächst den Baseline-Modus; noch nicht vorhandene Messmodi
werden ausdrücklich abgelehnt und nicht erfolgreich simuliert.

**R:** Abbruch, voller Datenträger, Datenbanksperre, beschädigte/unbekannte
Schema-Version und gleichzeitige Läufe prüfen. Ein Controller schreibt;
Worker liefern begrenzte Ereignisse. Keine Historie überschreiben, keine
unvollständige Messung als vollständig bestätigen.

**C:** Schlanke Trennung von lokalem Launcher, Messmodell, SQLite und Report.
Keine Runtime-Abhängigkeit, kein Core-/Watcher-Import des Entwicklerwerkzeugs.

**Fertig, wenn:** Ein lokaler Befehl erzeugt nachvollziehbare neue DB-Einträge,
ein zweiter erhält den ersten Lauf; Reporting startet keine Tests. Keine
Verbindung zu GitHub, SSH-Testhosts oder Uploadpfaden.

### 200-07 – Python-Laufzeit und Speicher

**W:** Getrennte lokale Durchläufe für Baseline, `cProfile`/`pstats` und
`tracemalloc`; je Phase Funktionen/Zeilen, Aufrufzahlen, Eigen-/kumulative
Profilzeit und Python-Speichermessungen speichern. Prozessspeicher nur mit
tatsächlich unterstütztem und ausgewiesenem Collector zusätzlich erfassen.

**R:** Instrumentierungsaufwand, Thread-/Kindprozessabdeckung, Start vor
Import/Collection, geteilte Fixtures, fehlende Messpunkte und Plattformunterschiede
sichtbar machen. Python-Allokationen nicht als gesamten Prozessspeicher,
Snapshotdifferenzen nicht als gesamte Allokationsmenge ausgeben. Keine globale
Profiling-Injektion in installierte Programme oder alle Python-Subprozesse.

**C:** Collector-Ausgaben in eine einheitliche lokale Struktur überführen,
ohne wichtige Rohdaten/Tracebacks zu verlieren. Datensätze statt gerenderter
`pstats`-Texte auswerten; Originalprofile lokal referenzieren.

**Fertig, wenn:** Bekannte CPU-/Allokationsfälle dem richtigen Test und seiner
Phase zugeordnet sind. Nicht instrumentierte Prozesse sind sichtbar unbekannt.

### 200-08 – strace und Prozesszuordnung

**W:** Unter Linux den ausdrücklich ausgewählten Testprozess samt seinen
Kindprozessen mit vorhandenem `strace` starten. Prozess-/Thread-IDs, Zeitspannen,
Systemaufrufe, Fehler und Dauern lokal speichern und mit Phasen korrelieren.
Kein Attach an laufenden Watcher, Apply oder fremde Prozesse.

**R:** `unfinished`/`resumed`, Signale, `exec`, PID-Wiederverwendung,
Kindprozesse über Phasengrenzen, Zeitkorrelation, fehlende Berechtigung,
fehlerhafte/abgeschnittene Traces und Größenlimits prüfen. Mehrdeutige
Zuordnungen als unbekannt erhalten. Nicht-Linux oder fehlendes strace ist
`unavailable` mit Grund; keine erfundenen Nullmessungen.

**C:** Bounded Parser, Prozessmodell und Phasenkorrelation voneinander trennen.
Der Parser wird nicht zu einem zweiten Test-Scheduler oder Prozessmanager.

**Fertig, wenn:** Datei-I/O, Prozessstart und Warten in kontrollierten lokalen
Fällen erkennbar sind; Wartezeit wird nicht als verbrauchte CPU-Zeit verkauft.

### 200-09 – Optimierungspotenzial und vergleichbare Nachweise

**W:** Lokale Ranglisten für langsame Testkörper, teure Vorbereitung/Cleanup,
häufige Funktionsaufrufe, Python-Speicher und I/O-/Wartehäufungen ausgeben.
Jeder Kandidat nennt Test-ID, Phase, Quellort, Messwert, Run und Einschränkungen.
`compare` stellt bewusst gewählte, vergleichbare Baseline-/Kandidatenläufe gegenüber.

**R:** Wiederholungen/Streuung, Plattform, Python, Testauswahl, Worker und
Collector-Konfiguration berücksichtigen. Unvollständige oder nicht vergleichbare
Daten ablehnen/kennzeichnen. Keine behaupteten Einsparungen aus instrumentierten
Laufzeiten und keine automatische Quelländerung.

**C:** Gemeinsame SQL-/Modellabfragen für Text/JSON/Markdown verwenden;
Optimierungskriterien, Provenienz und Messgrenzen nachvollziehbar dokumentieren.

**Fertig, wenn:** Ein Entwickler erkennt getrennt, welcher Test, welche
Vorbereitung und welcher Produktcode Untersuchung verdienen. Eine spätere
Optimierung braucht ihren eigenen vorher/nachher gemessenen Nachweis.

### 200-10 – GitHub Actions Job Summaries

**W:** Nach dem vorhandenen Artefaktupload je bestehender Lane eine Summary nach
`GITHUB_STEP_SUMMARY` schreiben: bestanden/fehlgeschlagen/übersprungen, nicht
ausgeführt/unvollständig, Walltime, Plattform/Python/Shell, volle Commitbindung,
Run/Attempt und Artefaktlink. Top 10 nach **reiner `call`-Zeit**, mit separaten
Setup-/Teardown-Spalten und gesonderten Vorbereitungshinweisen.
Ergebnisse zunächst pro Suite zeigen. Bei Aggregation ausdrücklich zwischen
Testausführungen und eindeutigen Testfällen unterscheiden, weil bestehende
Suiteauswahlen überlappen können. Test-Walltime und eine tatsächlich gemessene
gesamte Jobdauer getrennt beschriften; keine Summe paralleler Testdauern als
Gesamtlaufzeit ausgeben.

**R:** Auch rote/abgebrochene Jobs darstellen, soweit ihr Summary-Schritt noch
laufen kann; später übersprungene Tests nicht als Pytest-Skips zählen.
Fehlende Reports, Collection-/Setup-/Teardownfehler, xfail/xpass und Subtests
korrekt behandeln. Ein Ergebnis pro Test statt drei als bestanden zählenden
Phasen. Markdown/Steuerzeichen begrenzen und entschärfen. Fehler im zusätzlichen
Renderer melden, ohne bestehende Test-/Releaseentscheidungen umzuschreiben.

**C:** Ein stdlib-basierter Renderer für native und Docker-Reports; Plattform-
und Lane-Metadaten aus dem vorhandenen Acceptance-Katalog verwenden. Keine
zusätzliche Reporting-Plattform, kein neuer aggregierender Release-Gatejob.

**Fertig, wenn:** Alle bestehenden 13 Lanes bieten vergleichbare Summaries.
Die strengen Erfolgsprüfungen in `tools/test_results.py` und
`scripts/run_handoff_ci.py` bleiben maßgeblich. Artefaktinventare, Testauswahl,
Timeouts, Releasebedingungen und manuelle Auslösung werden nicht abgeschwächt.
**Kein Profiling in GitHub und kein Upload lokaler Profiling-Daten.**

### 200-11 – README, Badges und aktuelle Anleitung

**W:** README mit Produktzweck und Task/Execute/Result-Zyklus eröffnen; KI
bereitet vor, Anwender lädt herunter/überträgt. Dynamisches Badge für die neueste
stabile GitHub-Release-Version, Python `3.10+` und MIT ergänzen; sinnvoll auf
Release, Installationsinformation und Lizenz verlinken. Kein ungebundenes CI-Badge.
Lokalen Profiling-Befehl und getrennte Messphasen dokumentieren.

**R:** Ausführbare Beispiele für API, CLI, PYZ, watcher poll, Suffixe und
deprecated CLI prüfen. Upgradehinweise zu Python-Aufrufern, alten Bundles,
Runtime-Pins und gestoppten alten Diensten vervollständigen. SpecRoad benötigt
einen getrennten Integrationsauftrag, nicht nur eine Systeminstallation.

**C:** Aktive Dokumentation und generierte Handoff-Texte konsistent kürzen;
historische Dokumente nicht umschreiben. Keine Regeln für Tokenersparnis entfernen.
Keine Tests für Badgegrafiken, Markdownlayout oder README-Wortlaut hinzufügen.

**Fertig, wenn:** Neue Anwender können einen vollständigen Zyklus ausführen und
das lokale Diagnosewerkzeug bewusst starten. Keine automatische Übertragung,
Sandbox oder erfolgreiche zukünftige Git-Aktion wird versprochen.

### 200-12 – Finaler 2.0.0-Stand

**W:** Vollständigen Featurestand, Dokumentation, Metadaten und Paketversion
auf `2.0.0` setzen. Wheel, sdist, watcherfreie Core-PYZ, Manifest und Prüfsummen
mit den vorhandenen Release-Skripten vorbereiten. Lokale Diagnosewerkzeuge
werden nicht in die ausführbare Core-PYZ aufgenommen.

**R:** Gesamte Vertragsmatrix und Zwei-Runden-E2E gegen reale installierte
Artefakte verifizieren; Linux/Windows, unterstützte Python-Versionen, Shells,
Event-/Pollingbetrieb und relevante CIFS-/Publikationsgrenzen abnehmen.
Profiling-Parser, Datenmodelle und Fehlerwege bleiben durch kleine kontrollierte
Testfälle testbar. Echte Profiling-Messläufe werden ausschließlich lokal manuell
gestartet und mit eigener Provenienz belegt; dafür wird kein CI-Profilingjob
angelegt und kein strace-Paket in allen CI-Lanes nachinstalliert.

**C:** Verbliebenes Entwicklungsmaterial und tote Übergangspfade entfernen,
aktive Verweise und Inventare endgültig abgleichen. Ein dadurch geänderter
Commit benötigt eigene finale Artefakte und Abnahme; ältere grüne CI kann
seinen neuen Quellstand nicht ersetzen.

**Fertig, wenn:** Der finale Commit einschließlich C hat tatsächliche Apply-
Nachweise und die komplette manuelle native Abnahme. Externe Blocker dürfen
als offen dokumentiert, aber nicht als fertige Abnahme gezählt werden.
Release, Tag, Main-Merge und Installation sind getrennte spätere Aufträge;
der frühere einmalige 1.9.1-Auftrag autorisiert keine Veröffentlichung von 2.0.0.

## 6. Übergabe, Umstieg und Paketgrenzen

Entwicklungsbundles können mehrere aufeinanderfolgende WRC-Commits enthalten.
Jeder bekommt seinen echten Dateistand und sein eigenes vollständiges Apply-Gate.
Nach der Nutzerpräzisierung vom 11. November 2026 bleiben diese Commits zunächst
lokal: Push und Tag erst am Abschluss der 2.0.0-Arbeit, keine Zwischen-Pushes
und keine Tags durch Entwicklungs- oder Korrekturbundles. Anzahl und
Grenzen der Bundles richten sich nach tatsächlicher Größe und Prüfbarkeit,
nicht nach einem neuen Release je Schritt. Bundle-Nummern werden erst bei der
realen Lieferung vergeben und sind nicht mit Planpositionen identisch.

Der Entwicklungstransport darf bis zum kontrollierten Hostwechsel einen
festgehaltenen, geprüften 1.9.1-Core nutzen, während die Zielquellen bereits
2.0-Entwicklungsstände sind. Dies ist eine Trennung von Werkzeug und Testobjekt,
keine alte API-/Bundle-Unterstützung im neuen Produkt. Result-3-Nachweise dieses
alten Werkzeugs werden mit dessen Leser ausgewertet. 2.0-Tests und ihre
Registries/Exchanges laufen isoliert; der alte Host darf kein 2.0-Modul aus dem
gerade überschriebenen Zielcheckout nachimportieren.

Für den einmaligen späteren Hostwechsel: tatsächlichen letzten Lauf auswerten,
aktive Prozesse beenden lassen, Zustand sichern, neue vollständige Runtime und
Watcher zusammen umstellen, Konfiguration/IDs und benötigte lokale Historie
gezielt erhalten, erstes frisches Result 4 erzeugen, dann Task 2 verwenden.
Es wird kein automatischer Dualbetrieb und keine allgemeine Migration alter
Artefakte entwickelt. Eine notwendige enge State-Konvertierung betrifft nur
lokale Persistenz; sie erhält unbekannte/alte Belege konservativ und erfindet
keinen abgeschlossenen Auftrag. Alte Dateien werden nicht gelöscht.

SpecRoad wird in diesem Projekt nicht geändert. Die spätere Integrationsanleitung
nennt beide getrennten Dev-/Apply-/Exchange-Linien, feste Runtime-/Capability-Pins,
Control-Aufrufe und die notwendige Prüfung wirksamer Timeoutweitergabe. Lokale
SpecRoad-Hostvorgaben werden nicht in PatchHarbor-Produkt-Payloads eingebaut.

CI bleibt manuell. Ein neuer Plan allein ist kein Dispatchauftrag. Bei später
ausdrücklich beauftragter Releasearbeit gelten die bestehenden geprüften Prepare-,
Acceptance- und Publish-Skripte mit voller Commit-/Artefaktbindung.

## 7. Abnahmematrix und Abschlussnachweis

| ID | Pflichtnachweis | Schritte |
| --- | --- | --- |
| A-01 | ScriptBundle und Task sind getrennt; deprecated CLI warnt nur auf stderr; keine alten Python-Exports | 01–02 |
| A-02 | Frisches Result 4 → Task 2 → Execute → Result 4 → zweiter Task, clean und dirty, native API/CLI/PYZ | 02, 04, 12 |
| A-03 | Diagnose ohne Commit, Dry-run, Fehler/Timeout/Abbruch, Teiländerungen und Publikationsfehler korrekt | 02, 04, 12 |
| A-04 | Alte/gemischte/manipulierte Formate werden vor Mutation abgelehnt; Pfade, Hashes, Limits und Bindung bleiben streng | 02, 12 |
| A-05 | Replay, Lockreihenfolge, shared Exchange, Archivierung und lokale Historie bleiben korrekt | 02–04 |
| A-06 | Monitor zeigt tatsächliches Repo/Artefakt/Bundle/Aktivität; Eventmodus und 4-s-Polling funktionieren | 03 |
| A-07 | Vorbereitung, call, teardown und gemeinsame Fixtures getrennt; Parallel-Walltime nicht aufsummiert | 05–09 |
| A-08 | Profiling nur ausdrücklich lokal; SQLite enthält Daten, Provenienz, Teilfehler und lokale Rohartefakte | 06–09 |
| A-09 | Python-Zeit/Speicher und strace liefern richtige Test-/Phasenbezüge und ehrliche Abdeckung | 07–09 |
| A-10 | Vergleiche sind reproduzierbar; fehlende Daten nicht null; Profilzeit nicht Benchmark; keine automatischen Optimierungen | 09 |
| A-11 | CI-Summaries zeigen echte Ergebnisse und Artefaktlinks; alle bisherigen Test-/Release-Gates unverändert wirksam | 10 |
| A-12 | Aktuelle Beispiele/Badges/Handoff erklären den neuen Workflow; Integrationsumstieg dokumentiert | 11 |
| A-13 | Finales 2.0.0, alle Plattformnachweise auf exaktem Endcommit, Originalartefakte gebunden | 12 |

Zu jedem später bestätigten Plancommit werden Commit-SHA, tatsächliches Result,
Bundle-SHA, statische Development-Prüfung und vollständiges Apply-Gate
nachgetragen. Externe CI und eine spätere Veröffentlichung werden separat
nachgewiesen. Der Planstatus bleibt bis dahin offen.

## 8. Fachliche Quellen

Die konkreten Messgrenzen und die lokale Befehlsoberfläche stehen im
[Profiling-Entwurf](test-profiling.md). Für GitHub-Summaries werden die
[offizielle Summary-Schnittstelle](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary)
und die tatsächlichen
[Artefakt-Outputs des vorhandenen Uploadschritts](https://github.com/actions/upload-artifact#outputs)
verwendet. Der Artefaktlink kann eine Anmeldung erfordern und nach Ablauf seiner
Aufbewahrung ungültig werden; Run-Link und vollständige Commitbindung bleiben
zusätzlich im Bericht. Das ist Anzeigeinformation, keine neue Releasefreigabe.

## Lieferung 088 – 200-01.W, Apply fehlgeschlagen

Ein gebundenes Bundle liefert genau den ersten Work-Zustand (Position 1/36),
zusammen mit diesen Planunterlagen. Referenz ist das erfolgreiche Result 087
auf `7a10a315361627340ecd9ac594b860e81ac78f07`. Es entstehen keine künstlichen
Right-/Clean-Commits. Development prüft eine dokumentierte parallele Auswahl
für ScriptBundle, API/CLI, bestehende Runner-Sicherheitsfälle, Architektur und
Packaging. Der damalige Entrypoint verlangte danach die vollständige parallele
Suite vor Commit und Push. Das Gate scheiterte; beide Git-Aktionen wurden nicht
erreicht. Für folgende Bundles gilt die oben präzisierte Abschlussregel.

Result `b83ff0a4-f729-44a1-85cd-a15aa8e24fc3` bestätigt 3.730 bestandene Tests,
einen Fehler und 16 Skips bei vier Workern. Der tatsächliche HEAD blieb
`7a10a315361627340ecd9ac594b860e81ac78f07`; die 27 vorbereiteten Dateien
blieben unverändert im Worktree. Der fehlgeschlagene Test
`test_wheel_sdist_pyz_public_export_byte_equality` gelangte mit `2.0.0.dev0`
in die ausschließlich für stabile Veröffentlichungen gedachte Versionsprüfung.

## Lieferung 089 – 200-01.W-FIX1

Gebunden an das vollständige, tatsächliche Fehler-Result von 088 mit Fingerprint
`fa47c3bd91179438`. Die lokale Distributionsprüfung erhält eine eigene sichere
Namensauflösung für stabile und `.devN`-Versionen. Release-Vorbereitung,
Manifestprüfung und Veröffentlichung verlangen weiterhin stabile Versionen;
keine Release-Sperre wird gelockert. Der vorhandene echte Wheel-/sdist-/PYZ-Test
bleibt erhalten. Ergänzende Tests prüfen ungültige Versionspfade sowie den
Abbruch der Release-Pipeline bei Entwicklungsversionen vor Git/GitHub-Zugriff.

Die Entwicklungsprüfung dieser Korrektur ist ausschließlich statisch; es wird
kein neuer bestandener Testlauf behauptet. Der Apply-Entrypoint übernimmt den
exakt gebundenen uncommitteten Stand von 088, prüft alle vorgesehenen Commitdateien
und führt die vollständige Suite parallel mit vier Workern aus. Erst dann entsteht
der noch offene Commit `200-01.W` mit seinem ursprünglichen Subject. Kein Push,
Tag, CI-Start, Release oder Hostupdate im Entrypoint.

**Ergebnis:** Result `fd6fce0a-0f4f-46e9-ab51-3cfdd8591c28` bestätigt den
erfolgreichen Apply 089: 3.743 bestandene Tests, 16 Skips, vier Worker und den
lokalen Commit `3670347923c107c8ae2b76d0d4c65ce2516fa63c`. Die 29 Commitdateien
stimmen mit der geplanten Lieferung überein; der Worktree ist sauber. Kein Push
oder Tag. Damit ist genau Position 1/36 bestätigt.

## Lieferung 090 – 200-01.R

Referenz ist das erfolgreiche Result 089 auf dem oben genannten Commit.
Der Right-Schritt ergänzt Verhaltenstests über die öffentliche `run_scripts`-API:

- Echte ZIP-Dateien und Binärstreams: Nutzdateien stehen dem ersten Skript
  bytegenau bereit; Exitcodes 17, 124 und 130 bleiben normale Skriptergebnisse
  und verhindern die Ausführung des zweiten Skripts.
- Ein echter Timeout bleibt ein Toolfehler mit `FailureReason.TIMEOUT` und
  beendet das Bundle vor dem folgenden Skript.
- Traversal, Groß-/Kleinschreibungskollisionen und Symlinks im Archiv werden
  vor Nutzdateischreibzugriffen und Skriptausführung abgewiesen.
- Fehlende Marker, kollidierende Zielverzeichnisse und nach der Auswahl
  veränderte Verzeichniskandidaten erhalten ihre Sicherheitsgrenzen.
- Eingabestreams und Ausgabesenken bleiben im Besitz des Aufrufers. Ein
  paralleler CLI-Aufruf unterdrückt keine Warnung eines anderen API-Threads;
  `KeyboardInterrupt` und `SystemExit` stellen den Warnkontext wieder her.

Die 17 neuen parametrisierten Fälle sind ausschließlich statisch geprüft;
kein Development-Testlauf. Bestehende Runner- und Release-Gates bleiben erhalten.
Der Entrypoint verlangt die vollständige parallele Apply-Suite vor genau einem
lokalen Commit mit dem geplanten Subject für `200-01.R`. Push, Tag und CI bleiben
aus. Vor dessen tatsächlichem Result bleibt der Fortschritt 1/36; als Nächstes
folgt nach erfolgreichem Right-Stand `200-01.C`.

## Lieferung 091 – sechs aufeinanderfolgende Commitstände

Result 090 bestätigt `200-01.R` auf `bdba905c4cb982bca0e2f86384c3b97ea729a886`:
3.760 bestandene Tests, 16 Skips, vier Worker und sauberer Worktree. Push und Tag
bleiben bis zum Abschluss aus. Revision 2 zählt damit 2/38 bestätigte Commits.

Dieses Bundle umfasst `200-01.C`, `200-02.W1`, `200-02.W2`, `200-02.W3`,
`200-02.R` und `200-02.C`. Jeder Stand wird erst nach dem vorherigen erfolgreichen
Commit hergestellt und vollständig parallel im Apply geprüft. Ein Fehler stoppt
vor dem betreffenden Commit; bereits bestätigte Commits bleiben erhalten.
Reparaturen werden in alle betroffenen späteren vorbereiteten Stände übernommen.
Development führt ausschließlich statische Analyse und Paketvalidierung durch.

Im Script-Cleanup wird der bereits validierte Parserwert im `BundleScript`
weitergereicht; Ausführung und Beobachtung verwenden dieselben geparsten Daten.
Die notwendige erneute Prüfung eines ausgewählten Dateikandidaten bleibt bestehen.
Die sechs tatsächlichen Ergebnisse sind vor dem neuen Result weiterhin offen.

## Apply 091 und Reparaturbundle 092

Result `patchharbor-apply_Result_123041_1111_5bc9a5.zip`, SHA-256
`de237a9f95d45bfe4de1df1dd4a2c36d79aca648ca76d9aaa33597eb6f268f4f`,
bestätigt `200-01.C` auf `682b042407048f5e0b6da23f70aad5c845ce0f37`:
3.760 bestandene Tests und 16 Skips. Der folgende W1-Testlauf scheiterte vor
seinem Commit mit 44 Fehlern bei 3.716 bestandenen Tests und 16 Skips. Vier
dynamisch zusammengesetzte Testaufrufe verwendeten noch `_patch` statt `_task`.

Bundle 092 bindet exakt den erhaltenen uncommitteten W1-Zustand. Die Reparatur
gilt auch für W2, W3, R und C; umbenannte spätere Testdateien übernehmen sie.
Die bereits bestätigte Script-C-Phase wird nicht erneut committed. Es folgen
W1, W2, W3, R, C und der Work-Schritt `200-03.W` mit jeweils vollständigem
parallelem Apply-Gate. Statische Nachprüfung gleicht zusätzlich gekoppelte
Artefakttypen und die versionierte Replay-Ablage ab. Keine dieser Vorbereitungen
ist ein Erfolgsnachweis für die noch offenen Commits.


## Apply 092 und Reparaturbundle 093

Result `patchharbor-apply_Result_133613_1111_86c025.zip`, SHA-256
`0b96af975a56a9ab79c56d670bb2fde948df887a5a1b59e2bedf288285bac863`,
bestätigt `200-02.W1` auf `c7fe8f991fd877c10acd4c73f3d6f1b9d229792a`:
3.760 bestandene Tests, 16 Skips, vier Worker. Die vorherigen 44 API-Namensfehler
sind damit behoben. W2 stoppte vor seinem Commit mit fünf Fehlern, 3.744
bestandenen Tests und 16 Skips. Vier Varianten einer Ressourcenprüfung
erwarteten noch Result 3; ein Dateinamentest verwechselte Repository-Name und
Task-Marker. Die festen Erwartungen werden passend zum neuen Vertrag korrigiert;
die echten Reader-, Fallback- und Dateinamenprüfungen bleiben bestehen.

Bundle 093 bindet exakt den erhaltenen W2-Zustand und führt W2, W3, R, C,
`200-03.W` und `200-03.R` mit je einem vollständigen parallelen Apply-Gate fort.
Beide Reparaturen gelten für jeden betroffenen Folgestand. Die neue Right-Phase
sichert die Task-Beobachtung und die Trennung zwischen Watcherzustand und
tatsächlichen Ausführungsdaten ab. Development bleibt ausschließlich statisch;
Push, Tag und CI bleiben aus. Bestätigt sind 4/38 Schritte; die sechs Schritte
dieses Bundles gelten erst nach ihren tatsächlichen Commit- und Result-Nachweisen
als abgeschlossen.
