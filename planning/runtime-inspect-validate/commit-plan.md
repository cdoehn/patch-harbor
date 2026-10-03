# PatchHarbor – RIV-Implementierungsplan, Repository-Revision 3
## Inspect / Validate über API und CLI · Offline-Runtime · Result-Format 2 · Chat-Handoff

**Stand:** 3. Oktober 2026. **Status:** aktive Entwicklung;
**3 von 18 Umsetzungsschritten im Dateistand vorbereitet**. Nächster Schritt: `1.b.W`.
Apply-Commits und Push dieses neuen Stands sind erst durch das zurückgegebene Result bestätigt.
**Bereich:** RIV (Runtime / Inspect / Validate). **Paketbasis:** 1.2.1.
**Zielversion:** gesondert festzulegen; keine Versionsanhebung oder Releasefreigabe durch Dokumentation.

**Normative Grundlage:** `spec/SPECIFICATION.md`, insbesondere 35–41 sowie die
fortgeltenden Bestandsverträge. Dieser Plan liegt unter
`planning/runtime-inspect-validate/commit-plan.md` und ist ausdrücklich aktiv;
der abgeschlossene `planning/1.2.1/commit-plan.md` bleibt historisch.

**Technische Integrationsbasis:** `patchharbor-apply_Result_073436_1003_116272.zip`.
Result-SHA-256: `dd7b26e68c741707416a445e8e570c14f363606e193b46172c8605435e5fbaa4`.

| Bindungsfeld | Vollständiger Wert aus `context.json` |
|---|---|
| `repo_id` | `e7a93d72-62dc-4759-97e8-6bf6cdf10e90` |
| `base_commit` | `68dba9216b72dc0b6441df83f49c9047b8b038b9` |
| `state_fingerprint` | `7c9d2a24e397e0e5` |
| `fingerprint_algorithm` | `patchharbor-state-v1` |

Das Result dokumentiert einen sauberen erfolgreichen Apply; die 218 Base-Dateien
stimmen mit dem Development-Checkout überein. Die erzeugende Engine im Result
ist 1.2.0, der Repository-Quellstand 1.2.1. Die historische R2-Planungsbasis war
`9e3a6f9036dc681f463d2fdd6b603aee9b409598` aus
`patch-harbor_Result_145659_0913_35292b.zip`; sie ist kein neuer Patch-Bindungsinput.

**Vorbereitung P0:** `OFF-PLAN RIV-DOCS-1`, ein Dokumentationscommit
`docs: integrate runtime inspection and validation specification`.
Umfang: `spec/SPECIFICATION.md`, dieser Plan und `spec/SPECIFICATION_CHANGELOG.md`.
Diese Übernahme zählt nicht zu den 18 Feature-Schritten. P0 ist durch
`patchharbor-apply_Result_122057_1003_77a6b0.zip` bestätigt: echter Apply,
Vollsuite parallel und seriell je 1.581 bestanden / 5 übersprungen, Commit
`289fa32b8a295c91e456abe0f61c2ae232966719` und normaler Push auf `dev`.
Result-SHA-256: `755664f001e0bfaf7e4052f7d0185c01e553d667c120f23434321492125560f4`.
Diese neue Basis ist für Bundle 003 maßgeblich; die Integrationsbasis oben
bleibt historisch. repo_id, state_fingerprint und fingerprint_algorithm
bleiben unverändert. Die 219 Base-Dateien stimmen mit Development überein.

**Paketgrenze P1a / Bundle 003:** Gruppe 1.a wird vor der eigenständigen
allgemeinen Result-/Repositorybindung (1.b / P1b) ausgeliefert. Deren neuer
Referenzleser und Zustandsaufnahme verdienen eine eigene prüfbare Grenze.
Reihenfolge, 18 Planpositionen und Funktionsumfang bleiben gleich.
Dieser Dateistand umfasst 1.a.W, 1.a.R, 1.a.C; keine künstlich
aufgeteilten Endzustände. Vor jedem Apply-Commit vollständige parallele,
danach vollständige serielle Suite; genau ein Push nach der ganzen Folge.
Lokale Belege: `exchange/reports/patchharbor-riv-003-1.a.C-parallel.json`
und `exchange/reports/patchharbor-riv-003-1.a.C-serial.json`
(projektspezifischer Exchange, erst nach tatsächlichem Lauf vorhanden).
Prüfbefehle: `.venv/bin/python tools/run_tests.py --suite all`, danach
`--suite all --serial`; keine Versionsanhebung, kein Tag, keine CI-Behauptung.

**Repositoryrollen:** Development unter
`/home/christian/Codex/patchharbor/patchharbor-codex` erzeugt und prüft Dateistände
und die finale ZIP, ohne Git-Commits oder Push. Das unabhängige Apply-Repository
`/home/christian/Codex/patchharbor/patchharbor-apply` übernimmt über den geprüften
Entrypoint Tests, Commits und den abschließenden Push. Übergabe:
`/home/christian/Codex/patchharbor/exchange`. Registry, Replay-Daten und globale
Engine sind kein Entwicklungsziel. Vor Arbeit `pwd` und Git-Toplevel prüfen;
bei abweichender Development-Wurzel `CWD_MISMATCH`, keine Änderung.

---

## 1. Review-Ergebnis und begründete Korrekturen

| Befund | Korrektur | Begründung / Stelle |
|---|---|---|
| Original-Wheel nach normaler Installation vorausgesetzt, Bereitstellung offen | Kanonische Runtime aus vorbereiteten Ressourcen mit getrenntem Inhaltsnachweis und Archivhash; kein Quellbuild im Request | 38.3–38.5; Wheel-Installation ist nicht Archivaufbewahrung. [Q1, Q2] |
| Referenzleser und zwei neue Bindungsarten in `1.a.R` versteckt | Eigenständige Gruppe 1.b für beide Bindungsarten | Neue fachliche Fähigkeit, nicht nur Robustheit des Paketprüfers. |
| Writer, neue Leser und Nachweispolicy in einem W überladen | Gruppe 1.d liefert zuerst Leser 1/2; 1.e aktiviert danach Writer 2 | Ein neuer Writer darf seinen eigenen Verbrauchern nicht vorauslaufen. |
| Absolute Read-only-Zusage kollidiert mit Lockdateien | Fachliche Zustände unverändert; enge Synchronisations-/OS-Effekte ausdrücklich abgegrenzt | 37.1; Bestand `locks.py`/`repository_state.py`. |
| Alte Laufzeit könnte neue statische Vorlage nachladen | Runtime, Erzeuger und Vorlage vor Mutation gemeinsam einfrieren | 38.4 und korrigierter Basisabschnitt 19.6a. |
| Bytegleichheit mit beliebigem ursprünglichen Transportarchiv verlangt | Kanonisches Runtime-Archiv ist Referenz; dessen Roundtrip ist byteidentisch | 38.3/38.4; keine Selbstarchiv-/Selbsthash-Rekursion. |
| Fehlerfall „Runtime fehlt“ nicht von Pflichtdateifehler getrennt | Nur Runtime-Zugabe darf `unavailable` werden; Snapshot/Log/Handoff bleiben Pflicht | 39.4; keine erfolgreiche Notfalldiagnose erfinden. |
| Legacy-Integrität und Vertrauensnachweis zu pauschal | Vorhandene Hashes prüfen; fehlende Hashes/Live-Fingerprint/Authentizität nicht behaupten | 37.2 und 40.1. |
| Keine konkreten inneren Budgets; Wheel als beliebiger Python-Code | Enges Runtime-Inhaltsprofil und begrenztes gemeinsames Entpackbudget | 38.1 und 39.3; .pth ist ein zusätzlicher Startmechanismus. [Q4] |
| Erstes Upgrade oder Wheel-Ausfall könnte die Übergabe blockieren | Etablierte Paketprüfung und dauerhafter Fallback; native Prüfung nur bei verfügbarer geeigneter Runtime | 40.3; kein Bootstrap-Zirkel. |

**R2-Zerlegung bleibt erhalten.** Die sechs gegenüber Revision 1 zusätzlichen Commits verteilen bestehende Arbeit auf zwei zusätzliche WRC-Gruppen. Die Repository-Revision ergänzt den verpflichtenden Fallback und die explizite Abnahme von null/einem/mehreren Commits in den vorhandenen Gruppen. Es kommen keine weiteren öffentlichen Kommandos, kein Runtime-Paketmanager, keine Cloud-Funktion und kein neues UI-Projekt hinzu. Der Materialisierungsweg ist eine konkretisierte Entwurfsentscheidung; dessen echtes Packaging-Gate ist noch auszuführen.

## 2. WRC, Status und Paketgrenzen

**W – Let it Work:** Die zugesagte Teilfunktion funktioniert durchgängig über die vorgesehenen Schnittstellen. Ihre Sicherheitsgrenzen und Mindesttests sind bereits vorhanden. Nicht implementierte Fähigkeiten werden klar abgelehnt, niemals durch Platzhalter als erfolgreich angeboten.

**R – Do it Right:** Fehler-, Race-, Ressourcen-, Integritäts- und Plattformvarianten derselben Fähigkeit vervollständigen. Keine neue große Fachfunktion nachträglich als Robustheit tarnen. Neue unsichere Eingabeklassen dürfen auch vor R nicht akzeptiert werden.

**C – Make it Clean:** Reale Strukturverbesserung und Duplikatabbau ohne neue Fachfunktion oder Versionswechsel. Gibt es keinen sinnvollen Cleanup, wird der Plan vor Umsetzung angepasst; kein leerer oder kosmetisch aufgeblähter Commit nur für die Zahl 18.

Jeder Zwischenstand wird wirklich hergestellt, getestet und erst dann committed. Ein finaler Working Tree mit künstlich aufgeteiltem Staging ist kein WRC-Nachweis. Commit-IDs werden nach dem Commit aus Git übernommen, nicht im eigenen Commit vorweg erfunden.

### 2.1 Commitübersicht – 3/18 im Dateistand vorbereitet

| Nr. | Kennung | Commit-Subject | Voraussetzung | Paket |
|---:|---|---|---|---|
| 1 | `1.a.W` | `feat(inspect): add read-only package API and CLI [RIV 1.a.W]` | aktuelle geprüfte Basis | P1 |
| 2 | `1.a.R` | `fix(inspect): harden immutable input and error contracts [RIV 1.a.R]` | 1.a.W | P1 |
| 3 | `1.a.C` | `refactor(inspect): consolidate static package facts [RIV 1.a.C]` | 1.a.R | P1 |
| 4 | `1.b.W` | `feat(validate): compare reference and repository bindings [RIV 1.b.W]` | 1.a.C | P1 |
| 5 | `1.b.R` | `fix(validate): preserve readonly state across binding failures [RIV 1.b.R]` | 1.b.W | P1 |
| 6 | `1.b.C` | `refactor(validate): separate result integrity from evidence policy [RIV 1.b.C]` | 1.b.R | P1 |
| 7 | `1.c.W` | `feat(runtime): materialize canonical wheel from packaged resources [RIV 1.c.W]` | 1.b.C; D-01-Entwurf konkretisiert | P2 |
| 8 | `1.c.R` | `fix(runtime): verify provenance bounds and cold-cache roundtrips [RIV 1.c.R]` | 1.c.W | P2 |
| 9 | `1.c.C` | `refactor(runtime): isolate artifact lifecycle and packaging data [RIV 1.c.C]` | 1.c.R; GATE-RUNTIME erfüllt | P2 |
| 10 | `1.d.W` | `feat(result): accept format-2 inputs before enabling writers [RIV 1.d.W]` | 1.b.C und 1.c.C | P3 |
| 11 | `1.d.R` | `fix(result): harden mixed-version inventories and evidence checks [RIV 1.d.R]` | 1.d.W | P3 |
| 12 | `1.d.C` | `refactor(result): centralize versioned read contracts [RIV 1.d.C]` | 1.d.R | P3 |
| 13 | `1.e.W` | `feat(result): embed pinned runtime in all result creation paths [RIV 1.e.W]` | 1.d.C; GATE-READERS und GATE-RUNTIME erfüllt | P3 |
| 14 | `1.e.R` | `fix(result): preserve snapshots across runtime and self-update failures [RIV 1.e.R]` | 1.e.W | P3 |
| 15 | `1.e.C` | `refactor(result): simplify pinned publication lifecycle [RIV 1.e.C]` | 1.e.R | P3 |
| 16 | `1.f.W` | `feat(handoff): document and exercise verified offline bootstrap [RIV 1.f.W]` | 1.e.C; D-04 Übergang geklärt | P4 |
| 17 | `1.f.R` | `test(handoff): verify offline bootstrap and release integration [RIV 1.f.R]` | 1.f.W | P4 |
| 18 | `1.f.C` | `refactor(handoff): consolidate final runtime guidance and audit [RIV 1.f.C]` | 1.f.R | P4 |


### 2.2 Vier Pakete als Ausgangsplanung

**P1:** 1.a + 1.b, sechs Commits, aufgeteilt in P1a (Bundle 003, 1.a) und P1b (1.b). Paketprüfung und Bindungsprüfung sind danach vollständig benutzbar; Results bleiben Format 1. **P2:** 1.c, drei Commits. Runtime-Bereitstellung wird separat praktisch abgesichert. **P3:** 1.d + 1.e, sechs Commits. Erst alle Leser, dann gemeinsamer Writer. **P4:** 1.f, drei Commits. Aktuelle Anleitung und installierte Ende-zu-Ende-Abnahme.

Die Grenzen bleiben ausdrücklich flexibel. Bei großer Referenzleser-Arbeit kann P1 geteilt werden; bei großem Reader-Audit P3. P2 und P3 dürfen erst nach bestandenem Runtime-Gate zusammenrücken. P4 kann mit P3 zusammengelegt werden, wenn nur ein kleiner, gut geprüfter Abschluss verbleibt. Keine Zusammenlegung, die ungeklärtes Packaging, lange Tests oder Fehlerzuordnung verdeckt. Keine neue Nutzerfrage allein wegen einer risikoangemessenen Paketgrenze erforderlich.

Die fachliche Reihenfolge bleibt lesbar: Paketprüfung → Bindung → Runtime → neue Leser → neue Writer → Chat. Eine geänderte Paketzahl ändert die Commitzahl nicht. Umfangreiche unabhängige Zusatzarbeit kann eine weitere WRC-Gruppe rechtfertigen; sie wird begründet, nicht prophylaktisch erfunden.

**Ein Bundle darf null, einen oder mehrere Commit-Schritte enthalten.** Mehrere
fachliche Schritte oder W/R/C-Folgen brauchen allein wegen ihrer Anzahl keine
Sondergenehmigung. Diagnosebundles mit null Commits führen die beauftragten
Prüfungen aus und liefern Ergebnisse über Result/Logs; sie erzeugen keinen
Commit, Push, Tag oder Implementierungsfortschritt (Spec 26.5, 41.3).

Bei einer Commitfolge führt ausschließlich der Apply-Entrypoint nach allen
grünen Stufen und Abschlussprüfungen genau einen normalen Push auf den
bestätigten Zielbranch aus; für P0 ist dies `origin`, `refs/heads/dev`.
Kein Zwischenpush, Force-Push, automatischer Tag oder Push-Retry. GitHub-CI
startet ausschließlich manuell per `workflow_dispatch`; der Push startet sie
nicht. Für das nächste Paket gilt das tatsächlich zurückgegebene neue Result.

## 3. Geprüfte Ansatzpunkte und Verantwortungen

Die Bestandspfade beziehen sich auf den genannten Snapshot. Neue Modulnamen sind Vorschläge, keine Verpflichtung zur Dateivermehrung.

| Aufgabe | Bestand | Zielgrenze |
|---|---|---|
| Öffentliche API / Ergebnisse | `src/patchharbor/api.py`, `api_types.py` | Neue Aufrufe, unveränderliche Typen; Exporte stabil und explizit. |
| CLI / JSON / Fehler | `cli.py`, `errors.py`, `exit_status.py` | CLI → API; Ausgabeversion 2 nur für neue Kommandos, zentraler Fehlervertrag. |
| Stabile Paketbytes | `patch_package.py`, `patch_manifest.py`, `zip_payloads.py`, `platform/filesystem.py`, `bundle_handoff.py` | Ein sicherer Paketleser; Inventar und SHA derselben Bytes. |
| Statischer Entrypoint | `parser.py`, `models.py` | Marker/Messages ohne Interpreterstart oder Temp-Skript. |
| Reales Repository | `repository_state.py`, `registry.py`, `locks.py`, `git_commands.py` | Reiner Kontextpfad; nicht `SafeResolvedRepository` inklusive Result-Reservierung missbrauchen. |
| Referenz / Policy | `archive_evidence.py`, `exchange.py`, `exchange_recovery.py` | Neu etwa `result_reader.py`: allgemeine Integrität; Archiv-/Recovery-Policy bleibt darüber. |
| Runtime | `pyproject.toml`, `scripts/build_release.py`, Paketdaten | Neu etwa `runtime_artifact.py`, `runtime_metadata.py`: vorbereitete Ressourcen/kanonische Materialisierung. |
| Result | `result_bundle.py`, `result_bundle_capture.py`, `result_bundle_snapshot.py`, `result_bundle_writer.py`, `result_bundle_publication.py` | Gemeinsame Aufnahme, Inventar und atomare Publikation, Reader-first. |
| Vorlage | `chat_instructions.py`, `result_bundle_handoff.py`, `CHAT_INSTRUCTIONS.md`, `docs/python-api.md`, `README.md` | Mit Erzeuger fixierte statische Ressource, frische dynamische Daten. |
| Tests / Gates | `tests/`, `.github/workflows/acceptance-tests.yml`, Docker-Gates, `src/patchharbor_watcher/` | Bestehende Wege nutzen; kein zweiter Watcher-/Apply-Pfad. |

`patch_package.validate_patch_package()` gibt bisher lediglich das Manifest zurück. `archive_evidence._result_evidence()` kombiniert Format-1-Integrität mit strengen Erfolgsbedingungen. `apply_repository.py` reserviert einen Result-Ausgabeplatz. Diese drei bestehenden Funktionen dürfen deshalb nicht unbesehen zur neuen gesamten öffentlichen Validate-Implementierung erklärt werden.

Das bestehende `platform/runtime.py` bleibt Plattforminformation. Es wird nicht zu einem zweiten Runtime-Artefaktprovider. Alte JSON-Kommandos, Patchschema, Fingerprint und Recovery-Belege werden nicht beiläufig umdefiniert.

## 4. Verbindliche Entscheidungen und frühe Gates

### D-01: Runtime-Materialisierung praktisch belegen, bevor Writer-Arbeit beginnt

Die alte Forderung „das Original-Wheel ist nach normaler Installation noch da“ wird nicht implementiert. Gewählte Richtung ist ein kanonischer, mit festen ZIP_STORED-Regeln materialisierbarer Dateisatz. Build-/Installationsressourcen enthalten logisches Inventar, benötigte Original-Metadaten und endliche Reproduktionsregeln; nicht ein sich selbst enthaltendes Wheel. Ausführbare Produktdateien werden nur aus diesem überprüften Inventar gelesen. Lokale Installer-RECORDs, Launcher und pyc-Dateien sind keine Quelle für das portable Artefakt.

In `1.c.W` müssen Build und Provider dieselben kanonischen Bytes erzeugen. Die Reproduktionsbeschreibung und RECORD besitzen ausdrücklich einen zyklusfreien Ableitungsvertrag. Der Request darf standardbibliotheksgestützt Archivbytes materialisieren, aber keine fremden Python-Dateien importieren, Backends aufrufen oder Dependencies auflösen. Eine fertige Dateizuordnung und Hashprüfung ersetzt das pauschale Durchsuchen beliebiger `site-packages`-Inhalte.

Das **GATE-RUNTIME** muss vor `1.d.W` vorliegen: echte Standardinstallation und Chat-Wheel-Installation; Quell-/Downloadverzeichnisse und Installer-Caches entfernt; Aufruf außerhalb Checkout; erneute offline Materialisierung derselben kanonischen Bytes; geänderte Ressource erkannt. Dazu der Nachweis, dass unbeschreibbare Installation oder leerer Cache keinen normalen In-Memory-/Temp-Pfad verhindert. Ein einzelner Mockpfad auf ein vorher abgelegtes Wheel genügt nicht.

Scheitert der konkrete Mechanismus, bleibt Writer 2 deaktiviert. Eine alternative interne Umsetzung ist zulässig, wenn sie alle Revision-2-Invarianten ohne zusätzlichen manuellen Standardschritt erfüllt. Führt sie zu einem neuen Produktvertrag, ist diese Abweichung vorher offenzulegen. Die Planrevision selbst behauptet keinen bestandenen Prototyp.

### D-02: Schemas und Ressourcen vor Akzeptanz einfrieren

Vor dem ersten W des betroffenen Bereichs werden genaue Ergebnisfelder, Enumwerte, JSON-Hüllen, ResourcePolicy-Erweiterungen und Fixturedateien definiert. Maßgeblich sind Spec 36–39, insbesondere `runtime.status`, zyklusfreie Hashablage und Typstrenge. Unbekannte Formate werden abgelehnt, nicht nach bestem Vermuten als Format 1 gelesen.

Anfangsbudgets: 128 KiB Runtime-Metadaten, 1 MiB Reproduktionsbeschreibung, 16 MiB Wheel, 1.000 Wheel-Einträge, 32 MiB innere Daten; zusätzlich verbleibendes äußeres Request-Budget. Messung darf zu einer begründeten Spec-Anpassung führen, nicht zu unbegrenztem Durchwinken. Transportarchiv, kanonisches Wheel und Inhalts-ID haben getrennte Identitäten.

### D-03: Allgemeine Referenzgültigkeit und Recovery-Policy trennen

Ein Fehler-/Dirty-/Dry-Run-Bundle kann konsistente Referenzdaten besitzen, ohne archivierungs- oder recoveryfähig zu sein. Der neue Leser übernimmt Basiskonsistenz, nicht die komplette Erfolgspolicy. Umgekehrt darf seine breitere Akzeptanz niemals die Nachweisanforderungen von Archivierung und Recovery abschwächen.

Format-2-Reader unterstützen `embedded` und `unavailable`. Ein fehlendes Wheel bei deklariertem `embedded` ist Korruption, kein impliziter Unavailable-Fallback beim Lesen. Eine bereits als unavailable veröffentlichte gültige Referenz darf zur Bindungsprüfung benutzt werden.

### D-04: Bootstrap, Fallback und Freigabe getrennt aktivieren

Der erste API-Upgrade-Patch wird mit vorhandenen gültigen Paketprüfern und
ergänzend mit dem neuen getesteten Kandidaten geprüft. Kandidatentests werden
als solche ausgewiesen. Der neue Bootstrap wird erst in 1.f aktiviert.

Der Fallback nach Spec 40.3 ist dauerhaft verpflichtend: fehlendes, beschädigtes
oder inkompatibles Wheel sowie Installations-, Import- und technische
Nutzungsfehler führen zum bisherigen sicheren Entwicklungs-/Übergabeablauf.
Keine Blockade allein wegen fehlender nativer Prüfung. Ausfallgrund, Werkzeuge,
ausgeführte und fehlende Nachweise werden ausgewiesen. Fachlich ungültige
Paket-/Repositorydaten bleiben Ablehnungen. Bei reinem Runtime-Defekt werden
Repository-Referenzdaten separat nach dem bestehenden Vertrag geprüft; die
vollständige Format-2-Validierung darf dabei nicht als erfolgreich gelten.
Die unabhängige lesende Auswertung nutzt gemeinsame Faktenbausteine oder die
bisherigen verfügbaren Werkzeuge; keine zusätzliche öffentliche API erforderlich.

Diese Nutzungsfähigkeit ersetzt nicht GATE-RUNTIME: unveränderte unterstützte
Standardinstallationen müssen für die Feature-Abnahme weiterhin `embedded`
erreichen. Das laufende Werkzeug wird im Fallback nicht umgebaut; Snapshot,
Logs, tatsächliche Bindung und spätere Apply-Rechecks bleiben verbindlich.

Eine Zielversion wird vor Veröffentlichung gesondert entschieden. Keine
Versionserhöhung in C; Tag und Veröffentlichung sind getrennte beauftragte
Aktionen nach tatsächlicher CI-Freigabe.

## 5. Konkrete Umsetzungsschritte

### Schritt 1.a – Lesende Paketprüfung

#### 1.a.W – 1/18: `feat(inspect): add read-only package API and CLI`

**Status:** im Dateistand umgesetzt; Apply-Nachweis im späteren Result. **Abhängigkeit:** aktuelle geprüfte Basis. **Spec:** 36.1–36.4, 37.1.

**Ergebnis:** Inspect und Validate im Prüfbereich package sind über API und CLI benutzbar, ohne Git, Registry oder Shell.

**Umsetzung:** Stabile Paketbytes einmal sicher lesen; Paketgröße, SHA-256, Manifest, normalisierte Einträge und MESSAGE-Daten daraus ableiten. Bestehenden Manifest-/ZIP-/Handoff-/Markerparser verwenden. Keine schreibende Entrypointvorbereitung und keinen Apply-Preflight aufrufen. Keine zweite Nutzdatenkopie im öffentlichen Ergebnis speichern.

Unveränderliche PatchInspection-/PatchValidationResult-Typen und explizite Exporte definieren; CLI ausschließlich über API anbinden. Standard still in der Library, request-lokaler observer. Neues JSON-Schema 2 nur für diese beiden Kommandos; scope=package, binding_matches=null. Nicht implementierte repository/reference-Optionen werden noch nicht als funktionsfähig angeboten. Größen-/Pfadsicherheit und korrekte Fehlerrückgaben sind schon in W erforderlich.

**Dateifokus:** `api.py`, `api_types.py`, `cli.py`, `patch_package.py`, `parser.py`, ggf. neues `patch_inspection.py`.

**Prüfungen vor Commit:** T-A1, Mindestfälle T-A2/T-A3/T-A4; vorhandene ZIP-/Parser-/API-Regressionen.

**Fertig, wenn:** Beide Oberflächen prüfen dasselbe sichere Paket; Markerdatei eines Test-Entrypoints bleibt ungeschrieben; kein RunSession-/Result-/Runtime-/Exchange-Lebenszyklus gestartet.

#### 1.a.R – 2/18: `fix(inspect): harden immutable input and error contracts`

**Status:** im Dateistand umgesetzt; Apply-Nachweis im späteren Result. **Abhängigkeit:** 1.a.W. **Spec:** 36–37.1.

**Ergebnis:** Statische Prüfung bleibt auch unter fehlerhaften Eingaben, verändertem Dateipfad und Beobachterfehlern eindeutig.

**Umsetzung:** Grenzwerte, Duplikate, Pfadkollisionen, ZIP-Typen, verschlüsselte/defekte Inhalte, CRC, falsche Rollen, JSON-BOM/Bool/NaN, ungültige Typen und reservierte Metadaten prüfen. Unterschied zwischen berechneten Inhaltsdigests und tatsächlich deklarierten Integritätsnachweisen erhalten. Dateien nicht nach erfolgreicher Prüfung unabhängig für die SHA neu öffnen.

Argumenttypen und gegenseitige Fehlerprioritäten im öffentlichen Vertrag festziehen; Fehlergründe und Codes aus bestehendem Mapping nutzen. Ein später ersetzter Dateiname ändert nicht die zuvor geprüfte SHA, legitimiert aber keine spätere Anwendung ohne erneutes Lesen. Parallel aufgerufene Observer bleiben request-lokal. API/JSON dürfen keine Kennungen kürzen.

**Dateifokus:** Leser-/Parsergrenzen, Ergebnistypen, API-Validierung, JSON-Adapter.

**Prüfungen vor Commit:** T-A1–T-A4 vollständig, vorhandene Ressourcen-/Manifest-/Metadatenregressionen.

**Fertig, wenn:** Keine neue Eingabeklasse wird ohne vollständige statische Prüfung akzeptiert; alle Paketfehler bleiben fachlich unterscheidbar, keine UI-Wortlauttests.

#### 1.a.C – 3/18: `refactor(inspect): consolidate static package facts`

**Status:** im Dateistand umgesetzt; Apply-Nachweis im späteren Result. **Abhängigkeit:** 1.a.R. **Spec:** 36.1, 37.1, 41.2.

**Ergebnis:** Ein kleiner wiederverwendbarer statischer Faktenpfad statt mehrfacher Parser-/Serialisierungslogik.

**Umsetzung:** Rohlesen, Rollenauflösung, statische Skriptprüfung und Ergebnisserialisierung trennen. Duplikate entfernen; neutralen Faktenvertrag stabil halten. Apply verwendet weiterhin dieselben vorhandenen Sicherheitsprüfungen und zusätzlich seinen eigenen Lebenszyklus. Keine neue Referenzprüfung in diesem Cleanup.

Öffentliche Exporte, Ownership von Bytes und temporären Ressourcen sowie Beispiele bereinigen. Nur tatsächlich aufgetretene Doppelungen beseitigen. Ein funktional notwendiger neuer Prüfzweig gehört nicht als heimliches Feature in C.

**Dateifokus:** Paketfaktenmodule, API-Typen/-Dokumentation, CLI-Adapter.

**Prüfungen vor Commit:** T-A vollständig plus bestehende Apply-/Dry-Run-/Payload-Regressionen; bei Paketende vollständiges lokales Gate.

**Fertig, wenn:** Paketprüfung ist eigenständig verwendbar; Runtime und Bindung sind noch offen und werden nicht als vorhanden ausgegeben.

### Schritt 1.b – Referenz- und Repositorybindung

#### 1.b.W – 4/18: `feat(validate): compare reference and repository bindings`

**Status:** offen. **Abhängigkeit:** 1.a.C. **Spec:** 36.1/36.3/36.4, 37.2–37.3.

**Ergebnis:** Beide ausdrücklichen Bindungsmodi funktionieren in einem sicheren minimalen Durchstich.

**Umsetzung:** Allgemeinen Format-1-Result-Leser bereitstellen: Schemas und Typen, vollständiges Inventar, base-Blob-Hashes, Untracked-SHA, vorhandene Metadaten, Run-/Kontextkonsistenz. Keine künstliche Clean-/Success-Pflicht für allgemeine Referenzgültigkeit. Gültige Dirty-/Fehler-/Dry-Run-Daten sind erlaubt; unbekannte Varianten werden vor Erfolg abgelehnt. Deltas nicht ausführen und keinen Live-Fingerprint aus dem Bundle erfinden.

In der API repository und reference_bundle ergänzen, gegenseitig ausschließen und CLI darüber anbinden. Im Referenzmodus tatsächlichen Kontext statt expected_* verwenden. Im Repositorymodus existierende Registrierung, Locks und konsistenten Kontext lesen, ohne Result-Zielreservierung oder Exchange-Wartung. Vollständige bekannte Bindung inklusive Algorithmus vergleichen; Mismatch ablehnen. Prüfzeitpunkt, Referenz-SHA und nicht geprüfte Aspekte zurückgeben.

**Dateifokus:** Neu `result_reader.py`/Bindungsorchestrierung; `api.py`, `cli.py`, `repository_state.py`, lesende Hilfen aus `archive_evidence.py`.

**Prüfungen vor Commit:** T-B1–T-B4 Mindestmatrix; T-A als Regression. Mindestens eine reale registrierte Instanz und eine Referenz ohne Registry/Git.

**Fertig, wenn:** Paket-, Referenz- und Repositoryaussagen sind getrennt. Keine großen Bindungsfeatures bleiben als angebliche Robustheitsarbeit verborgen.

#### 1.b.R – 5/18: `fix(validate): preserve readonly state across binding failures`

**Status:** offen. **Abhängigkeit:** 1.b.W. **Spec:** 37 vollständig, 36.3/36.4.

**Ergebnis:** Alle zulässigen Referenz-/Fehlervarianten und die enge Read-only-Grenze sind abgesichert.

**Umsetzung:** Partielle/falsche Inventare, falsche Objektformate, Bool-als-Integer, erwarteter statt tatsächlicher Kontext, Dirty-/Fehlerresultate und unbekannte Formate testen. Unbekannte Fingerprintalgorithmen nicht nur als gleiche Strings passieren lassen. Fehlende Legacy-Dateihashes als fehlenden Nachweis behandeln, nicht als generelles Format-1-Verbot.

Registrierungswechsel und konkurrierende Änderungen während der Aufnahme sicher ablehnen. Lockeffekte getrennt vom fachlichen Vorher-/Nachher-Zustand prüfen; keine Registry-, Index-, Attempt-, Replay- oder Resultdateiänderung. Kontrollierte Git-Konfiguration nicht mit bequemen status-/diff-Aufrufen umgehen. Nach erfolgreichem Validate veränderten Zustand bei Apply erneut ablehnen. Eine Referenz mit fehlender Originalhistorie benötigt keinen fake git-init.

**Dateifokus:** Result-Leser, Bindungsgrenze, Repositorykontext, Fehleradapter und funktionale Fixtures.

**Prüfungen vor Commit:** T-B1–T-B4 vollständig; Recovery-/Archiv-/Repository-Lock-Regressionen.

**Fertig, wenn:** Erfolg benennt exakt den geprüften Zustand und keine Sicherheitsgarantie darüber hinaus; alle Mutationsverbote bleiben testbar.

#### 1.b.C – 6/18: `refactor(validate): separate result integrity from evidence policy`

**Status:** offen. **Abhängigkeit:** 1.b.R. **Spec:** 37.2, 39.3, 41.2.

**Ergebnis:** Allgemeine Integrität und strengere Archiv-/Recovery-Policy sind explizit getrennt.

**Umsetzung:** Gemeinsame JSON-, Inventar- und Bindungsbausteine nur bei identischem Vertrag zusammenziehen. Archiv-/Recovery-Code verwendet geprüfte Fakten und behält seine zusätzliche Erfolgs-/Clean-/Receipt-Policy. Lesepfade erhalten klare Ressourcen-/Hash-Ownership. Keine Format-2-Unterstützung in diesem C einschmuggeln.

API- und JSON-Vertragsdokumentation konsolidieren. Gezielte Kontrolltests sichern, dass eine gültige Dirty-Referenz nicht plötzlich archivalisch freigegeben wird. Alte Package-/Result-Erzeugung bleibt unverändert.

**Dateifokus:** `result_reader.py`, `archive_evidence.py`, Referenz- und Zustandsorchestrierung.

**Prüfungen vor Commit:** T-A/T-B und Nachweisregressionen; P1-Ende vollständige lokale Suite einschließlich Packaging.

**Fertig, wenn:** P1 ist allein nützlich; jede neue Validierung läuft über denselben geprüften Pfad, Results werden weiterhin als Format 1 erzeugt.

### Schritt 1.c – Kanonische Runtime-Bereitstellung

#### 1.c.W – 7/18: `feat(runtime): materialize canonical wheel from packaged resources`

**Status:** offen. **Abhängigkeit:** 1.b.C; D-01-Entwurf konkretisiert. **Spec:** 38.1–38.5.

**Ergebnis:** Eine Standardinstallation kann ohne Quelldownload oder Installer-Cache offline ein passendes Runtime-Wheel bereitstellen.

**Umsetzung:** Buildverfahren erzeugt endliche Reproduktionsbeschreibung, Hashinventar und erforderliche Original-Metadaten als installierte Paketressourcen. Code, Watcher, Typing, Lizenz und statische Vorlage gehören zum Inhaltsvertrag. Console-Launcher, pyc und installerbezogene Metadaten gehören nicht hinein. Package-data-Ablage für Vorlage einführen und Legacy-Loader gezielt kompatibel halten.

Kleinen standardbibliotheksbasierten Materializer für definierte Reihenfolge, feste ZIP_STORED-Metadaten und deterministisches RECORD implementieren. Content-ID und Archivhash trennen; Selbstbeschreibung und abgeleitete Dateien zyklusfrei behandeln. Materializer nur über Runtime-Provider für Resultoperationen nutzen, nicht bei Inspect/Validate oder generellem API-Import. Sichere Pfade, Hashprüfung und Begrenzungen ab erster Fassung. Noch kein Writer-Formatwechsel.

**Dateifokus:** `pyproject.toml`, Build-Hook/-Helfer, `scripts/build_release.py`, Paketressourcen, neue Runtime-Module, `chat_instructions.py` nur für Ressourcenauflösung.

**Prüfungen vor Commit:** T-C1/T-C2/T-C3 Mindestnachweise: tatsächlich bauen, offline installieren, Ursprung/Caches entfernen, Materialisierung außerhalb des Checkouts und aus installiertem kanonischem Wheel vergleichen.

**Fertig, wenn:** Es existiert ein echter nichtrekursiver Bereitstellungsweg; kein Test mit künstlich übergebenem unverändertem Original-Wheel als einziger Erfolgsnachweis.

#### 1.c.R – 8/18: `fix(runtime): verify provenance bounds and cold-cache roundtrips`

**Status:** offen. **Abhängigkeit:** 1.c.W. **Spec:** 38 vollständig; 39.3 Vorbedingungen.

**Ergebnis:** Der Provider erkennt geänderte Daten und bleibt bei Fehlern, Reinstallation und parallelen Requests eindeutig.

**Umsetzung:** Same-version/different-content, geänderte Paketdatei, fremde Metadaten, falsche SHA, Cachekorruption und fehlende Ressourcen prüfen. Nicht-editierbare Source-/sdist-Installation funktioniert ohne Git; editable unverifiziert liefert ausdrücklich source_not_prepared/source_changed statt still altes Artefakt. Endliche Byteslebensdauer ohne Vervielfachen der Nutzdaten.

Das enge Profil verbietet .pth, Fremdmodule, nativen Code und zusätzliche Launcher. Ressourcenlimits und RECORD prüfen. Kalter/fehlender/schreibgeschützter Cache darf den erlaubten reinen Datenpfad nicht blockieren; keine Installer- oder Netzwerkaufrufe. Parallele private Temporärdateien sicher und nur selbst angelegte Dateien entfernen. Erzeugeridentität und Vorlage für spätere Request-Pins zusammen anbieten, ohne schon einen Writer anzuschließen.

**Dateifokus:** Runtime-Provider, Materializer, Ressourcen-/Provenienzmodell, Packaging-Tests.

**Prüfungen vor Commit:** T-C1–T-C5 vollständig, Linux/Windows installierte Stichproben; GATE-RUNTIME dokumentieren. Keine Behauptung einer vollständigen Cross-Platform-Freigabe nur aus Linux.

**Fertig, wenn:** Kanonischer Artefakt-Roundtrip und sämtliche unterstützten Standardinstallationen nachgewiesen; Fehler sind strukturierte Providerfakten, keine unkontrollierte Result-Auslöschung.

#### 1.c.C – 9/18: `refactor(runtime): isolate artifact lifecycle and packaging data`

**Status:** offen. **Abhängigkeit:** 1.c.R; GATE-RUNTIME erfüllt. **Spec:** 38, 41.2.

**Ergebnis:** Die spätere Resultschicht benötigt nur eine kleine unveränderliche Providerantwort.

**Umsetzung:** Build-Rezept, lesenden Materializer und request-lokalen Besitz trennen; keine unabhängigen CLI/API/Watcher-Provider. Doppelte Hash-/Pfadhelfer nur bei gleichen Regeln vereinheitlichen. Legacy share-Fallback und kanonische Paketressourcen klar ordnen, Generator nicht in einem fremden CWD suchen lassen.

Reproduktionsregeln und Content-ID-Algorithmus dokumentieren, die während W/R entstandenen Hilfsduplikate entfernen. Keine neuen Provenienzfähigkeiten und keine Ergebnisformatänderung. Temporäre Prototypen nicht in das Produkt aufnehmen.

**Dateifokus:** Runtime-Module, Build-/Ressourcenhelfer, technische Dokumentation.

**Prüfungen vor Commit:** T-C vollständig plus vorhandene Packaging-/API-/Vorlagenregressionen; P2-Ende vollständige lokale Suite.

**Fertig, wenn:** Standarddistribution ist selbständig reproduzierbar; Reader/Writer-Arbeit kann darauf aufbauen, ohne einen ungeklärten Installationsschritt vorauszusetzen.

### Schritt 1.d – Result-Format-2-Leser vor den Schreibern

#### 1.d.W – 10/18: `feat(result): accept format-2 inputs before enabling writers`

**Status:** offen. **Abhängigkeit:** 1.b.C und 1.c.C. **Spec:** 39.2–39.3/39.5, 37.2.

**Ergebnis:** Alle neuen Verbraucher verstehen Format 1 und 2; produktive Erzeugung bleibt ausdrücklich Format 1.

**Umsetzung:** Geschlossene Format-2-Schemas, Runtime-Metadaten und Deskriptoren anhand fester Fixtures implementieren. Positive embedded- und unavailable-Fälle; mindestens vollständige Hash-/Inventar-/Budgetprüfung ab W. Reader importiert oder installiert keine Runtime.

Allgemeinen Result-Leser, Referenzvalidierung, schnelle Klassifikation und die nachgelagerten Archiv-/Recovery-Verbraucher aktualisieren. Veröffentlichungsprüfung für beide Versionen vorbereiten. Die schnelle Klassifikation bleibt bloßer Typnachweis, keine behauptete Vollvalidierung. Policybedingungen nicht aus Metadaten wie capability oder Runtime-Version ableiten. Format-1-Writer und Fingerprint bleiben gleich.

**Dateifokus:** `result_reader.py`, `exchange.py`, `archive_evidence.py`, `exchange_recovery.py`, `result_bundle_publication.py`, Runtime-Schemahilfen.

**Prüfungen vor Commit:** T-D1/T-D2/T-D3 Mindestmatrix, T-B-Referenzen; gültige künstliche Format-2-Fixtures und echte Format-1-Results.

**Fertig, wenn:** Ein veröffentlichter Zwischenstand kann weiter regulär arbeiten und bereits neue Inputs sicher lesen. Kein eigener Writer ist seinen Lesern voraus.

#### 1.d.R – 11/18: `fix(result): harden mixed-version inventories and evidence checks`

**Status:** offen. **Abhängigkeit:** 1.d.W. **Spec:** 39.2–39.5, 37.2.

**Ergebnis:** Gemischte Ordner und manipulierte Archive führen nicht zu falschen Apply-/Recovery-/Archiventscheidungen.

**Umsetzung:** Unbekannte Versionen, doppelte Runtime-Dateien, Manifest/Runtime/Wheel-Widersprüche, manipulierte content_id/RECORD, falsche inneren Pfade und base/runtime-Namensraum testen. Unavailable akzeptiert kein unerwartetes zusätzliches Wheel. Inneres Budget bleibt unter gemeinsamem Requestlimit; keine beliebige Rekursion und keine mehrfachen vollständigen Entpackkopien.

Dirty-/Fehlerreferenz mit neuer Runtime bleibt Referenz und nicht automatisch Erfolgsevidence. Runtime-Ausfall/Warnung ändert nicht die alte konservative Nachweispolicy. Mit eingefrorenen Altlesern nachweisen, dass Format 2 nicht als Patch angewandt wird; alte Binaries nicht nachträglich kompatibel nennen. Manipulierte vorhandene Runtime nicht beim Lesen still in unavailable umdeuten.

**Dateifokus:** Reader-/Policygrenzen, versionierte Fixtures, Limits, Klassifikationstests.

**Prüfungen vor Commit:** T-D1–T-D4 vollständig, bestehende Archiv-/Recovery-/flacher-Scan-Tests.

**Fertig, wenn:** Das neue Format ist vollständig lesbar und konservativ verarbeitet; unbekannte oder kaputte Daten scheitern ohne Mutation.

#### 1.d.C – 12/18: `refactor(result): centralize versioned read contracts`

**Status:** offen. **Abhängigkeit:** 1.d.R. **Spec:** 39.3/39.5, 41.2.

**Ergebnis:** Ein nachvollziehbarer Versionsdispatch und keine auseinanderlaufenden Runtime-Inventarprüfer.

**Umsetzung:** Gemeinsame Faktenmodelle und Formatdispatches konsolidieren. Sicherheits-/Ressourcenregeln je Namensraum sauber benennen; Root-Metadaten nicht mit Repository-Payload-Normalisierung verwechseln. Archiv- und Recoverypolicy behalten ihren eigenen Zweck, nutzen aber dieselbe vollständige Integrität.

Doppelte Versionstabellen und ad-hoc JSON-Prüfungen entfernen. Fixtures teilen, soweit die semantischen Aussagen gleich sind. Writer bleibt auch nach C bei Format 1. Änderung auf 2 gehört ausschließlich in den nächsten W-Schritt.

**Dateifokus:** Result-/Runtime-Leser und deren interne Model-/Schemahilfen.

**Prüfungen vor Commit:** T-A/T-B/T-D, T-C Profil-/Metadatenregressionen; bei getrenntem Paketabschluss vollständiges Gate.

**Fertig, wenn:** GATE-READERS erfüllt; Leserkompatibilität kann unabhängig von der späteren Erzeugung freigegeben werden.

### Schritt 1.e – Runtime-Einbettung und gemeinsame Result-Erzeugung

#### 1.e.W – 13/18: `feat(result): embed pinned runtime in all result creation paths`

**Status:** offen. **Abhängigkeit:** 1.d.C; GATE-READERS und GATE-RUNTIME erfüllt. **Spec:** 39.1–39.4, 38.4.

**Ergebnis:** Gemeinsamer Writer erzeugt Format 2 samt Runtime; minimale Fehlerdiagnose funktioniert ab dem ersten aktivierten Writer.

**Umsetzung:** Zu Beginn Result-erzeugender Requests Erzeuger, vorbereitete Runtime und statische Chat-Vorlage gemeinsam pinnen. Daten durch bestehende Capture-/Snapshot-/Handoff-/Writer-/Publication-Pfade führen, statt getrennte CLI/API/Watcher-Bundler zu bauen. Dynamische Run-/Targetdaten spät korrekt ergänzen; echte Repositorydaten bleiben unberührt.

Format 2 standardmäßig aktivieren und genau zwei neue Runtime-Einträge bei embedded, nur Metadaten bei unavailable schreiben. Tatsächlich geschriebene Bytes verifizieren. Runtime-only-Ausfall oder Überschreitung des Zusatzbudgets führt schon in W zur bezeichneten Diagnose, soweit vollständiges Result möglich. Echte Snapshot-/Handoff-/Publikationsfehler bleiben Fehler; kein stiller Datenverlust. Keine neuen Results vor sicherer Repositoryauflösung erfinden.

**Dateifokus:** `application.py`, Result-Capture/-Handoff/-Writer/-Publikation, Provideranbindung, Warnungsfakten.

**Prüfungen vor Commit:** T-E1/T-E2/T-E3 Mindestmatrix: manuelles Fremdprojekt-Bundle, echter Apply-Erfolg, Fehler, Dry-Run, Writerintegrität und Runtime-Ausfall; T-D vollständig.

**Fertig, wenn:** Alle gemeinsamen Eintrittspfade verwenden denselben neuen Writer. Normale Standardinstallation liefert embedded; Runtime-only-Fehler vernichtet kein sonst mögliches Result.

#### 1.e.R – 14/18: `fix(result): preserve snapshots across runtime and self-update failures`

**Status:** offen. **Abhängigkeit:** 1.e.W. **Spec:** 38.4–38.5, 39 vollständig.

**Ergebnis:** Selbstupdates, Watcher und Fehlerpublikation bleiben reproduzierbar und diagnostisch eindeutig.

**Umsetzung:** Erzeugungsmatrix vervollständigen: Watcher, explizites Ziel, Dirty/Untracked, abgebrochener/fehlgeschlagener Apply, alte Laufzeit mit neuem Repo sowie echte geänderte Installation nach Pin. Vorlagenbytes und Runtime gehören zum alten Erzeuger; aktueller Snapshot darf den neuen Commit zeigen.

Fehlerinjektion vor/während Publikation, Cacheänderung, Ressourcenlimit, unzureichende Rechte und kaputtes Result-Ziel testen. Runtime weglassen nur vor endgültiger Publikation; begrenzter neuer Tempversuch erlaubt, keine Retry-Schleife und kein unbeabsichtigtes Löschen fremder Dateien. Abbruchsignale nicht in Erfolg umwandeln. Notfallrettung für echte Resultfehler bleibt erhalten.

Result A → frische installierte Runtime → Result B → weitere frische Runtime → Result C durchführen. Kanonische Wheel-SHA/-Größe identisch; äußere ZIPs dürfen variieren. RAM und zusätzliche komprimierte Bytes messen, keine pauschale Aussage „kaum Speicher“ ohne Messung.

**Dateifokus:** Result-Lebenszyklus und funktionale Self-update-/Watcher-/Fehlerfixtures.

**Prüfungen vor Commit:** T-E1–T-E5 vollständig, T-C-Provenienz, T-D-Policy, Prozess-/Recovery-Regressionen.

**Fertig, wenn:** Alle unterstützten regulären Wege erreichen embedded; gezielte Störungen liefern belegte Einschränkungen statt falscher Erfolgsmeldung.

#### 1.e.C – 15/18: `refactor(result): simplify pinned publication lifecycle`

**Status:** offen. **Abhängigkeit:** 1.e.R. **Spec:** 38.4, 39, 41.2.

**Ergebnis:** Ein kleiner gemeinsamer Lifecycle für gepinnte Ressourcen und atomare Results.

**Umsetzung:** Doppelte Runtime-/Vorlagen-Passthroughs und Inventarerzeugung vereinheitlichen. Temporärdatei-/Bytesbesitz von Erfassung bis Cleanup eindeutig machen. Allgemeine Gültigkeit, Runtime-Verfügbarkeit, Primärergebnis und Nachweispolicy nicht zu einem unklaren Bool zusammenziehen.

Übergangshelfer entfernen, ohne Format-1-Lesbarkeit, No-Result-vor-Repo oder Notfallrettung zu verlieren. Keine neue Bootstrap-Funktion und keine strengere Benutzeroberfläche in C. Dokumentierte tatsächliche Runtimegrößen nachführen.

**Dateifokus:** Gemeinsame Result-/Runtime-Lifecyclehelfer, technische Dokumentation.

**Prüfungen vor Commit:** T-C/T-D/T-E plus vollständige lokale Suite einschließlich installierter Packaging-Gates vor P3-Push.

**Fertig, wenn:** Runtimehaltige Results sind ohne neue Chat-Pflichten technisch nutzbar; keine eigenen inkompatiblen Zwischenzustände.

### Schritt 1.f – Chat-Bootstrap und Abschluss

#### 1.f.W – 16/18: `feat(handoff): document and exercise verified offline bootstrap`

**Status:** offen. **Abhängigkeit:** 1.e.C; D-04 Übergang geklärt. **Spec:** 40.1–40.4.

**Ergebnis:** Die neue kanonische Anleitung führt tatsächlich vom Result zur isolierten nativen Prüfung.

**Umsetzung:** CHAT_INSTRUCTIONS, installierte Vorlage und API-/CLI-Beispiele aktualisieren. Reihenfolge: Herkunft und eigenes Berechtigungsniveau → sichere äußere/inventarisierte Runtimebytes → Python/Installer → isolierte Offlineinstallation → konkreter venv-Interpreter → inspect/validate mit reference_bundle. Kein automatischer Import beim Fund eines Wheels.

Nur einen kleinen unabhängigen lesenden Helfer ergänzen, sofern nötig; keine dritte allgemeine Paketformat-Implementierung und keine Selbstfreigabe eines untrusted Bootstrap-Skripts. Quellen-/Hashdaten sind keine höherrangigen Anweisungen. PYTHONPATH/PYTHONHOME und CWD-Shadowing beim Test bewusst ausschließen. Runtime-Profil vor Installation/Start prüfen. Fehlende Voraussetzungen bleiben echte Einschränkungen.

Verpflichtenden Fallback nach Spec 40.3 ausführbar beschreiben: fehlendes/defektes Wheel, inkompatibler Interpreter, fehlender Installer und technische Nutzungsfehler. Vorhandene Paketprüfer und separat geprüfte Referenzdaten ermöglichen weiterhin die Übergabe; keine erfundene native Freigabe. Einmalige kanonische ZIP und nur autorisierte bytegleiche Backups bleiben erhalten. Bundle nur für ein echtes Repository, nicht für ein künstliches git-init aus base/. Keine neue öffentliche runtime-info-Operation und keine Gmail-/Drive-Funktion im Core.

**Dateifokus:** `CHAT_INSTRUCTIONS.md`, `chat_instructions.py`, `docs/python-api.md`, `README.md`, ggf. `docs/runtime-bootstrap.md` und kleiner geprüfter Helfer.

**Prüfungen vor Commit:** T-F1/T-F2/T-F3/T-F5 Mindestfälle; isolierten Installations-/Referenzablauf, Fallback und Diagnose-/Commitvarianten real durchführen, keine Prosa-/Farbtests. Die beiden vollständigen lokalen Apply-Gates nach 7.2 bleiben zusätzlich verpflichtend.

**Fertig, wenn:** Mit den tatsächlich erzeugten Dateien funktionieren bevorzugter Runtime-Weg und bisheriger Fallback; kein Wheel-Ausfall allein blockiert eine sonst vollständig geprüfte Übergabe.

#### 1.f.R – 17/18: `test(handoff): verify offline bootstrap and release integration`

**Status:** offen. **Abhängigkeit:** 1.f.W. **Spec:** 40, 41.1.

**Ergebnis:** Die vollständige Übergabekette ist in blockierende funktionale Gates eingebunden.

**Umsetzung:** Python 3.12 und mindestens einen zusätzlich festgelegten Interpreter, Linux und Windows gezielt abdecken. Nicht sämtliche Kombinationen vervielfachen: Grundmatrix auf der Untergrenze, repräsentative installierte Wheel-/uv-/pipx-Wege, kanonischen Roundtrip auf mindestens zwei Zielvarianten. Gateverdrahtung für neuere Tests darf nicht bis hier fehlen; hier die Gesamtintegration vervollständigen.

Fehlender lokaler Installer/venv, inkompatibles Requires-Python, manipulierter Hash, unzulässige .pth/Fremdmodule, geänderte Wheel-Datei zwischen Prüfung und Nutzung, unbekannte Herkunft und Schattenmodul im CWD prüfen. Netzwerk muss in den eigentlichen Runtime-/Bootstrap-Tests blockiert sein; lokale Testfixture-/Buildvorbereitung ist getrennt dokumentiert. Keine Bibliotheksabhängigkeit allein wegen eines Testhelfers einführen.

Auslieferungskette mit kontrollierten Fixtures prüfen: finale Bytes ändern → Prüfung erneut erforderlich.
Fallback real ohne benutzbares Wheel durchführen, einschließlich separater
Referenzdatenprüfung bei reinem Runtime-Defekt und Ablehnung beschädigter
Snapshot-/Bindungsdaten. Null-Commit-Diagnose, Einzelcommit und mehrere echte
Commitzustände in isolierten Testrepositorys prüfen: Logs/Result, Gate-Reihenfolge,
Teilerfolg, kein Push bei Diagnose oder Fehler, genau ein finaler Push bei
erfolgreicher Commitfolge. Produktionsregistry und echter Remote bleiben tabu. Externe Backup-Fehler nicht durch neue ZIPs beheben. Keine echten Drive-/Mail-Transaktionen in der Projektsuite.

**Dateifokus:** Installierte Integrations-/Packaging-Tests, bestehende CI-Lanes/Markierungen, Bootstrap-Beispiele.

**Prüfungen vor Commit:** T-F1–T-F5 vollständig und vollständige lokale Suite; passende CI anschließend, ohne lokale Plattformtests zu erfinden.

**Fertig, wenn:** Neue Tests werden wirklich von blockierenden Gates ausgeführt. Netzwerkfreiheit und korrekter Importpfad sind nachgewiesen, nicht nur aus Flags abgeleitet.

#### 1.f.C – 18/18: `refactor(handoff): consolidate final runtime guidance and audit`

**Status:** offen. **Abhängigkeit:** 1.f.R. **Spec:** 35–41.

**Ergebnis:** Eine konsistente dokumentierte Übergabe und ehrliche Abschlussbilanz ohne neue Features.

**Umsetzung:** Doppelte Bootstrap-Erklärungen, veraltete Zwischenoptionen und unnötige Helfer entfernen. Spezifikation, API-Exporte, Beispielpfade, Paketdaten, Changelog und Plan abgleichen. Technische Fixtures und Ownership vereinfachen; keine wörtlichen Dokumentations-Snapshots hinzufügen.

Abdeckungsmatrix und wirkliche Prüfbelege vervollständigen. Alle nicht erledigten Punkte offen lassen; CI erst nach realer Bestätigung als grün vermerken. Keine eigene SHA im zu erzeugenden Commit behaupten. Ein späterer Versions-/Releaseauftrag bleibt außerhalb dieses Cleanup; das Papier allein erzeugt keinen Tag.

**Dateifokus:** Handoff-/Dokumentationshelfer, Plan-/Changelog-Verweise, Testfixturen.

**Prüfungen vor Commit:** Alle Gruppen, vollständiges lokales Gate einschließlich Packaging; Review der Abweichungen und finalen Result-Handoff-Daten.

**Fertig, wenn:** 18 Positionen wirklich umgesetzt oder vorab sachlich umgeplant. Fachliche Freigabe zusätzlich erst mit CI für den tatsächlichen finalen HEAD; Veröffentlichung bleibt separat.

---

## 6. Testgruppen und Anforderungsabdeckung

Kennungen sind geplante funktionale Nachweise, keine bereits bestandenen Tests. Bestehende Fixtures wiederverwenden; neue Dateien nur bei eigenständigen Verantwortungen, etwa `test_patch_inspection.py`, `test_reference_validation.py`, `test_runtime_artifact.py`, `test_result_reader.py`, `test_runtime_roundtrip.py` und `test_runtime_bootstrap.py`. Teure Artefaktbuilds je unverändertem Stand wiederverwenden, statt für jede einzelne Assertion ein neues Wheel zu bauen.

| Gruppe | Geplanter Nachweis | Verantwortlich |
|---|---|---|
| T-A1 | Paketfakten, MESSAGE, Rollen und vollständige SHA aus denselben Bytes; API/CLI-Parität. | 1.a.W/R |
| T-A2 | ZIP-/JSON-/Pfad-/Ressourcenfehler; instabile Datei, keine falschen Teilresultate. | 1.a.W/R |
| T-A3 | Kein Git/Shell/Registry/Runtime-Provider/Entrypoint/Result bei package; fachliche Nebenwirkungsfreiheit. | 1.a.W/R |
| T-A4 | Unveränderliche Typen, Exporte, JSON 2, bisheriges JSON 1 und Fehlercodes, Observerisolation. | 1.a.W/R/C |
| T-B1 | Zwei Bindungsziele, Keyword-Ausschluss, explizite Pfade und vollständige bekannte Bindungen. | 1.b.W/R |
| T-B2 | V1-Inventar/Blob-ID/Untracked-SHA, Dirty/Fehler/Dry-Run, tatsächlicher statt erwarteter Kontext, Legacy-Integritätsgrenzen. | 1.b.W/R |
| T-B3 | Registry/Index/Attempt/Replay unverändert, nur erlaubte Locks; reeller Repo-Recheck nach Änderung. | 1.b.W/R |
| T-B4 | Integrität ≠ Archiv-/Recovery-Erfolg ≠ Absendervertrauen; kein automatischer Git-Rekonstruktionspfad. | 1.b.W/R/C |
| T-C1 | Standard-Wheel, nicht-editierbare Source-/sdist- und Chat-Installation, Ressourcen und keine Runtime-Dependencies. | 1.c.W/R |
| T-C2 | Entfernte Quellen/Caches, korrekte kanonische Bytes und RECORD, getrennte content_id/wheel_sha256. | 1.c.W/R |
| T-C3 | Profil- und Ressourcenprüfung; kein .pth/Fremdmodul/Launcher/pyc; keine Build-/Installer-/Netzaufrufe im Provider. | 1.c.W/R |
| T-C4 | Same-version/different-content, veränderter editable-Stand, falsche Ressource, Provenienz nicht bloß Versionsstring. | 1.c.R |
| T-C5 | Parallelität, kalter Cache, Rechte, Cleanup, keine Selbsthash-/Archivrekursion. | 1.c.R/C |
| T-D1 | Reader 1/2, exaktes Schema/Inventar, richtige Runtime-Statusvarianten, Writer weiterhin 1. | 1.d.W/R |
| T-D2 | Klassifikation, Referenz, Publikationsprüfung, Archiv-/Recoverypolicy, unknown Version konservativ. | 1.d.W/R |
| T-D3 | Innere/äußere Budgets, falsche SHA, Namen/Kollisionen, base/runtime getrennt, keine Runtime-Imports. | 1.d.W/R |
| T-D4 | Eingefrorener Altleser auf neuen Fixtures: keine falsche Patchauswahl oder destruktive Archivierung. | 1.d.R |
| T-E1 | Gemeinsamer Writer 2 in allen regulären Resultwegen, Fremdprojekt und explizites Ziel. | 1.e.W/R |
| T-E2 | Request-Pin von Runtime/Erzeuger/Vorlage, neuer Repo-Snapshot, reale Self-update-Variante. | 1.e.W/R |
| T-E3 | Unavailable nur für Runtime; Snapshot/Logs/Handoff und Primärergebnis, Temp-Publikation, echte Notfallrettung. | 1.e.W/R |
| T-E4 | Drei Generationen isolierter Installation/Result mit gleichen kanonischen Bytes. | 1.e.R |
| T-E5 | Runtimegröße, komprimierter Mehrbedarf und Peak-RAM; richtige Budgets ohne ausgeblendete Snapshotdateien. | 1.e.R |
| T-F1 | Installierte Vorlage, ausführbarer Offlineablauf, richtige CLI/API-Interpreterumgebung ohne Shadowing. | 1.f.W/R |
| T-F2 | Herkunft/Integrität vor Code; inkompatibles Python, fehlender Installer, fehlendes/defektes Wheel und technische Nutzungsfehler: verpflichtender bisheriger Übergabeweg, kein Netzwerkfallback; Runtime-only-Defekt von ungültiger Repositorybasis unterscheiden. | 1.f.W/R |
| T-F3 | Finale Patchbytes bevorzugt nativ, andernfalls über den dokumentierten bisherigen Weg prüfen; Byteänderung erfordert erneute Prüfung. Keine erfundenen nativen/Originalrepo-/Test-/CI-Nachweise und keine zweite Backup-ZIP. | 1.f.W/R |
| T-F4 | Vollständige lokale Suite, Packaging/Typing/Plattform-Gates, fachlich reviewed Anweisungen. | 1.f.R/C |
| T-F5 | Bundles mit null/einem/mehreren Commits; reale Diagnose-Ergebnisse in Result/Logs, unveränderter Planzähler bei Diagnose, Gates pro Commit, Teilerfolg und Push nur nach vollständiger Commitfolge. | 1.f.W/R |

### 6.1 Spezifikationsmatrix

| Spezifikationsbereich | Primärer Durchstich | Vervollständigung / Nachweise |
|---|---|---|
| 35 Scope, Versionsachsen | alle Gruppen | Abschlussreview 1.f.C |
| 36.1–36.2 Paket-API/CLI | 1.a.W | T-A1–T-A4, 1.a.R/C |
| 36.3–36.4 Resultate/Bindung/Fehler | 1.a.W + 1.b.W | T-A4, T-B1–T-B4 |
| 37.1 Read-only | 1.a.W + 1.b.W | T-A3, T-B3; erlaubte Locks separat |
| 37.2 Referenz | 1.b.W | T-B2/T-B4; neue Formate T-D1/T-D2 |
| 37.3 Repo/Recheck | 1.b.W | T-B1/T-B3 |
| 38.1–38.2 Profil und Python | 1.c.W | T-C1/T-C3, T-F2/T-F4 |
| 38.3 Materialisierung | 1.c.W | GATE-RUNTIME, T-C2–T-C5 |
| 38.4 Erzeuger/Vorlage/Roundtrip | 1.c.W + 1.e.W | T-C4/T-C5, T-E2/T-E4 |
| 38.5 Installationswege | 1.c.W | T-C1/T-C2, T-F1/T-F4 |
| 39.1 standardmäßige Einbettung | 1.e.W | T-E1 |
| 39.2 Format und Metadaten | 1.d.W | T-D1/T-D3; tatsächliche Ausgabe T-E1 |
| 39.3 Integrität/Verbraucher/Budgets | 1.d.W | T-D2–T-D4, T-E5 |
| 39.4 Fehlerdiagnose | 1.e.W | T-E3 und Publikationsfehlerinjektion |
| 39.5 Reader-first | 1.d.W–C vor 1.e.W | GATE-READERS, T-D1/T-D4 |
| 40.1–40.2 Bootstrap | 1.f.W | T-F1/T-F2 |
| 40.3 Übergang und echte Referenz | 1.f.W | D-04, T-F2/T-F3 |
| 40.4 Einmalige Auslieferung | 1.f.W | T-F3, menschlich/fachliches Prozessreview |
| 41 Funktion, WRC und Diagnosebundles | alle Gruppen; Diagnose-/Commitanzahl 1.f.W/R | Paketgates, T-F5 und finaler Abgleich |

### 6.2 Bewusst keine Darstellungstests

Keine neuen Assertions auf Farben, Punkte, Symbolwahl, Anzahl gewöhnlicher Logzeilen, exakte Fehlermeldungen oder wortgetreue README-/Chat-Prosa. Dokumentationswortlaut wird reviewed, nicht eingefroren. Installierbare Paketressourcen und tatsächlich ausführbare Beispielabläufe sind dagegen Verhalten. Neue maschinenlesbare JSON-Daten, stabile Fehlergründe und Exitcodes bleiben funktionale Verträge.

Bereits vorhandene Darstellungs-/Dokumenttests nicht nebenbei massenhaft löschen. Bei einer notwendigen Änderung von Prosa solche Tests von Wortlaut entkoppeln, statt den neuen Wortlaut ebenfalls festzuschreiben. Sicherheits-, Parser-, Daten- und Packagingtests dürfen nicht als UI-Tests wegerklärt werden.

## 7. Prüfpunkte je Commit und Paket

### 7.1 Vor Änderungen

Aktuelles Result, Kontext, vollständige Bindung, Manifest, relevante Deltas, Logs und kanonische Chat-Anweisung lesen. Vollständigen Quellumfang prüfen. Vorhandene menschliche Änderungen nicht überschreiben. Neue vorgeschlagene Pfade am realen Repository prüfen. Die Dokument-SHA aus dieser Revision ist keine gültige Bindung an einen irgendwann späteren Arbeitsstand.

### 7.2 Vor jedem Commit

Development stellt jeden Zwischenstand tatsächlich her und prüft ihn lokal,
ohne einen Commit zu erzeugen. Für jeden später zu committenden Zielzustand
muss der Apply-Entrypoint erneut diese beiden vollständigen Gates in genau
dieser Reihenfolge erfolgreich ausführen:

```sh
.venv/bin/python tools/run_tests.py --suite all
.venv/bin/python tools/run_tests.py --suite all --serial
```

Der zweite Lauf folgt nach erfolgreichem ersten Lauf, der Commit erst nach
beiden. Dies gilt für W, R, C und Dokumentationscommits einschließlich P0.
Die in Abschnitt 5 genannten funktionalen Gruppen beschreiben den fachlichen
Prüffokus und sind keine Erlaubnis, die Vollsuite nur am Paketende auszuführen.
Zusätzliche Bereichs-/Plattformnachweise bleiben gemäß dem jeweiligen Schritt
erforderlich. Ein Lauf auf dem späteren Gesamtstand prüft keinen früheren W.

Python-Syntax und `git diff --check` prüfen; ausschließlich im Apply-Entrypoint
die vorgesehenen Pfade stagen und Indexbytes mit dem geprüften Inhalt abgleichen.
Tests verwenden isolierte Fixtures und temporäre Testrepositorys; produktive
Registry, Replay-State und Exchange sind kein Testmaterial. Ein fehlendes
Werkzeug oder eine fehlende Plattform ist kein grüner Nachweis. Bei Fehler kein
Commit dieses Zustands und keine nächste Änderungsphase; frühere erfolgreiche
Commits und Diagnosebelege bleiben erhalten. Development-Tests ersetzen die
erneuten Apply-Gates nicht.

Bei Diagnosebundles mit null Commits richtet sich der Prüfumfang nach dem
Auftrag; es gibt keine commitbedingte Vollsuite, kein Staging und keinen Push.

### 7.3 Vor Paketpush

Sämtliche gewählten Stufen und ihre Gates erfolgreich, voller lokal möglicher Regressionstest einschließlich Packaging für den tatsächlichen Endstand. Bestehende CI-Lanes/120-Minuten-Budget nicht ohne sachlichen neuen Auftrag ändern. Testgruppen früh passend markieren; nicht bis zum letzten Paket auf ungetestete CI-Integration warten.

Keine zusätzlichen knappen Gesamtsuite-Timeouts für Pixel-Läufe erfinden. Ein bestehender Wrapper wie `scripts/test.sh` ist auf seine tatsächlichen Limits zu prüfen, nicht blind zu übernehmen. Der Entrypoint braucht ein für Umfang/Hardware geeignetes Laufzeitbudget; bei zu langem Paket lieber Grenze teilen als Tests streichen. Einzelne bewusst getestete Prozess-Timeouts bleiben funktional erforderlich.

Nur der Apply-Entrypoint pusht nach erfolgreicher Commitfolge genau einmal normal auf den bestätigten Zielbranch. Diagnosebundles pushen nicht. Kein Zwischenpush oder automatisches Release. Acceptance-CI ausschließlich manuell per `workflow_dispatch`; ein ausstehender Lauf bleibt als ausstehend ausgewiesen. Ein bekannter CI-Fehler wird vor dem nächsten produktiven Paket bewertet.

### 7.4 Fehler und Wiederaufnahme

Bei Test-/Buildfehler bleibt der tatsächliche Zwischenstand mit vorherigen erfolgreichen lokalen Commits erhalten. Kein automatischer Reset, Clean oder Rollback. Der äußere laufende Runner erzeugt nach seinen Regeln das Result; ein Entrypoint baut keinen zweiten widersprüchlichen Ergebnisstand.

Bei Netz-/Pushfehler nach lokalen Commits wird nicht blind derselbe alte basisgebundene Patch wiederholt. Zuerst HEAD, Index, Arbeitsbaum, Remote und Result prüfen; danach gezielte Fortsetzung oder neu gebundener Patch. Keine erzwungene Korrektur fremder Remotehistorie.

### 7.5 Spätere Patch-Auslieferung

Nur eine abschließend geprüfte kanonische ZIP. Bei jeder Byteänderung erneut validieren. SHA-256, Größe und Name festlegen, dann Chat-Link; externe Sicherung derselben Datei nur bei ausdrücklicher Autorisierung und verfügbarem Werkzeug. Fehler externer Sicherung verändert den fertigen Patch nicht und erzeugt keine zweite Fertigmeldung. P0 übernimmt diese Planungsdokumente als eigenes Dokumentationsbundle; es implementiert keinen Feature-Schritt.

## 8. Statusführung und Endabnahme

Jeder später abgeschlossene Eintrag enthält Plan-ID, tatsächlichen Commit, ursprüngliche Basis, Datei-/Löschumfang, Specbezug, konkrete Prüfkommandos, Interpreter/Plattform, Exitcode und Fundstelle der Logs. Status: offen → in Arbeit → lokal geprüft → committed → gepusht → CI bestätigt. Der Repo-Commit kann seine eigene SHA nicht als bereits bekannten Text voraussetzen; endgültige IDs im Result/Audit nachtragen.

Fertig ist die Erweiterung erst mit nutzbarer API und CLI, konstant reproduzierbarer Runtime aus Standardinstallationen, sicherer Formatintegration, erhaltenen Sicherheitsgrenzen, ausgeführten Offline-/Roundtrip-Gates, aktueller installierter Anleitung und grüner CI für den tatsächlichen finalen HEAD. „0 Commits offen“ allein ist kein Freigabenachweis.

**Status dieses Dateistands:** 3/18 vorbereitet, 15 weitere Schritte offen.
P0 ist nachgewiesen; für Bundle 003 sind konkrete Commit-IDs und Apply-Erfolg
noch durch das spätere Result zu ergänzen. Paketprüfung ist implementiert,
Referenz-/Repositorybindung, Runtime, Format 2 und deren Plattformabnahme
stehen aus. Die ursprünglichen Standardquellen wurden nicht erneut extern
geprüft; ihr Quellenstand bleibt derjenige der Exchange-Revision 2.

## 9. Dokumentidentität und Quellen

### 9.1 Unveränderte Exchange-Quellen der Revision 2

| Datei | Bytes | SHA-256 |
|---|---:|---|
| `SPECIFICATION_PatchHarbor_Runtime_Inspect_Validate_r2.md` | 224758 | `38a105f7181227e53f2b484bf72292bef4637f79dfb0cb62660ebb5eebc816b4` |
| `PatchHarbor_Erweiterungsspezifikation_Runtime_Inspect_Validate_r2.md` | 48678 | `c99cfb42997201beb3a29ad2b1282eb2a358e660117eea491c32f6cf427d9731` |


Diese Hashes identifizieren ausschließlich die ursprünglichen Exchange-Dateien,
nicht die integrierte Repositoryfassung. Der Auszug war mit Abschnitten 33–39
und Referenzen der ursprünglichen Gesamtdatei bytegleich. Die neue kanonische
Quelle ist `spec/SPECIFICATION.md` mit RIV-Kapiteln 35–41; dieser Plan verweist
darauf und dupliziert ihren Normtext nicht.

Ursprünglicher R2-Plan: `PatchHarbor_Implementierungsplan_WRC_Runtime_Inspect_Validate_r2.md`,
55296 Bytes, SHA-256
`59befd61846db5baea1f1ec479b984f6e6c188c9578dea1d05f711eb131b02ab`.
Die drei gelieferten Dateien bleiben als Herkunft im Exchange unverändert.

### 9.2 Nachgesehener Code

Der aktuelle 1.2.1-Quellstand enthält `requires-python = ">=3.12"`, `dependencies = []` und getrennte API-, Paketleser-, Result-, Archiv-/Recovery- und Watcher-Module. Die lesende Bestandsaufnahme zur Integration betraf vor allem `pyproject.toml`, `patch_package.py`, `apply_repository.py`, `repository_state.py`, `archive_evidence.py`, `resource_policy.py`, `result_bundle_writer.py`, `result_bundle_handoff.py`, `git_commands.py`, `locks.py`, `exit_status.py` und die Spec-Verträge. Es wurde dafür kein aktueller Remote-Stand vorausgesetzt.

### 9.3 Primärreferenzen

- **[Q1]** PyPA, Binary distribution format: https://packaging.python.org/en/latest/specifications/binary-distribution-format/ — Archivstruktur, Installation und RECORD. Die konkrete kanonische Materialisierung ist eine eigene Produktentscheidung, keine behauptete Installerfunktion.
- **[Q2]** PyPA, Recording installed projects: https://packaging.python.org/en/latest/specifications/recording-installed-packages/ — Grenzen installierter Metadaten als Archivnachweis.
- **[Q3]** pip, pip install: https://pip.pypa.io/en/stable/cli/pip_install/ — Offlineinstallation lokaler Wheels, Metadaten und getrennte Buildphase für Quellen.
- **[Q4]** Python, site: https://docs.python.org/3/library/site.html — Startverhalten ausführbarer .pth-Zeilen.
- **[Q5]** Python, zipfile: https://docs.python.org/3/library/zipfile.html — feste ZIP-Einträge und ZIP_STORED.
- **[Q6]** Python, venv: https://docs.python.org/3/library/venv.html — isolierte neu erzeugte Umgebung, nicht Betriebssystem-Sandbox.

Quellenstand: 2. Oktober 2026. Keine Quelle ist ein Beleg dafür, dass die neue PatchHarbor-Funktion bereits implementiert ist.
