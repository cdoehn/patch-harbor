# PatchHarbor – Implementierungsplan: Result-PYZ und `pack`

**Plan-ID:** `PYZ-PACK`
**Planpfad:** `planning/pyz-pack/commit-plan.md`
**Revision:** 18
**Stand:** 8. Oktober 2026
**Status:** PP-00 bis PP-06B tatsächlich angewendet/gepusht. PP-07 / Bundle 041 gleicht Dokumentation und funktionale Beispiele ab; Apply noch offen.
**Geplanter Umfang:** 9 Arbeitspakete `PP-00` bis `PP-08`, zunächst 16 vorgeschlagene Commit-Schritte. Keine feste Anzahl von Patch-Bündeln.
**Fortschritt:** 13/16 ursprüngliche Planpositionen committed. PP-07 ist Position 14; native Abschlussabnahme bleibt separat.
**Nächster Schritt:** PP-07 mit neu gebauten Ressourcen und vollständiger paralleler Suite übergeben; anschließend PP-08A Testzuordnung und PP-08B Abschlussnachweise.
**Ziel-Produktversion:** noch festzulegen; keine erfundene Releaseversion, kein automatischer Tag oder Release.

> **Verbindliche Grundlage ist der gemeinsame Spezifikationssatz:**
> [Hauptspezifikation](../../spec/SPECIFICATION.md) **und**
> [Spezifikationserweiterung PYZ/PACK, Revision 2](../../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md).
> Dieser Plan konkretisiert ihre Umsetzung. Er ersetzt keine ihrer Regeln und führt keine zusätzlichen Produktfunktionen ein.

## Inhalt

1. Auftrag, Geltung und Ausgangsbasis
2. Architektur und unveränderliche Grenzen
3. Arbeitspakete, Abhängigkeiten und sichere Zwischenstände
4. Vorgeschlagene Commitfolge
5. Detaillierte Umsetzungsschritte
6. Integrations- und Umstellungsgates
7. Testausführung, Plattformen und CI
8. Anforderungszuordnung
9. Vollständige Zuordnung der spezifizierten Tests
10. Dokumentationsplan
11. Fortschritt, Patch-Bündel und Nachweise
12. Abschluss, Risiken und offene Freigabeentscheidungen
13. Prüfung dieses Plans und Änderungsprotokoll

---

## 1. Auftrag, Geltung und Ausgangsbasis

### 1.1 Gemeinsamer Vertrag

Für diesen ausdrücklich beauftragten Featureplan gelten genau diese beiden normativen Dateien gemeinsam:

```text
spec/SPECIFICATION.md
spec/SPECIFICATION_EXTENSION_PYZ_PACK.md
```

Es handelt sich nicht um konkurrierende Spezifikationen. Die Vorrang- und Auswahlregeln der Ergänzung `GOV-01`, `GOV-03` und `GOV-04` sind anzuwenden. Nicht eingeordnete konkurrierende Fassungen bleiben ein Konflikt. Fehlt eine benötigte Datei, darf sie nicht durch eine vermutete Fassung ersetzt werden.

Die Ergänzung bleibt eine nebenliegende Datei. Dieser Auftrag erzeugt weder eine zweite Gesamtspezifikation noch einen Core-Spezifikationsscanner. Die Hauptspezifikation wird durch die Erstellung dieses Plans nicht verändert. Die aktuellen Planverweise sind durch PP-00 in Anleitung, README und Changelog integriert; alte Statuspassagen sind nicht eigenständig der Nachweis eines aktuellen Arbeitsauftrags.

Der ausdrücklich aktive Featureplan ist dieser Plan, nicht ein aus `1.2.1` erratener historischer Versionsplan. Die vorhandenen Watcher- und Result-/CIFS-Pläne werden nicht überschrieben oder pauschal reaktiviert.

### 1.2 Gebundene Analysegrundlage

Die folgenden Werte identifizieren ausschließlich die für diese Planung gelesenen Dateien. **Sie sind keine dauerhaften Bindungswerte zukünftiger Patch-Pakete.**

| Gegenstand | Gelesene Grundlage |
|---|---|
| Result-Archiv | `patch-harbor_Result_055059_1007_b463c4.zip` |
| Result-SHA-256 | `7f400edeee9dcd3369b1ab82a46527cb6f80062cf1a1699018d66f4eafe26dda` |
| Repository-ID im Result | `23a55eed-715d-4a28-926e-5410a23bf6e8` |
| Base-Commit | `bf0b82e5de1eaf3afb2d645d77cd7799e7b6e0b7` |
| State-Fingerprint / Algorithmus | `7c9d2a24e397e0e5` / `patchharbor-state-v1` |
| Quellstand | Snapshot `base/` mit 289 inventarisierten Dateien; im Result als nicht dirty aufgezeichnet |
| Produkt-/Formatstand | Produktversion `1.2.1`, Resultformat `2`, Runtime-Metadatenformat `1`, eingebettetes Wheel |
| Hauptspezifikation SHA-256 | `8d75b43bc8739a5c1864ebb48e5d05af1233edb23fd0345d26cf2d3a12609280` |
| Ergänzung Revision 2 SHA-256 | `7fbdc21111da2a8d74c55b4da03e40d80c91d928731eb427335a4197256d8111` |

Bei der Erstellung dieses Plans wurden die 289 Snapshot-Dateien anhand ihrer Größe und Git-Blob-ID gegen `base_entries` abgeglichen; es gab keine Abweichung. Das ist eine Quellenkontrolle, **kein erneuter Lauf der Produkttests, kein Apply- und kein CI-Nachweis**.

Für die Planung der Codeänderungen ist der Snapshot maßgeblich. Das eingebettete Wheel kann aus einer anderen ausführenden Installation stammen; gleiche Versionsstrings garantieren keine Codegleichheit. Frühere Versuchsberichte zur Runtime sind keine Tests der noch zu implementierenden Funktionen.

### 1.3 Vor Implementierungsbeginn erneut abzugleichen

`PP-00` liest das dann aktuelle Result beziehungsweise den ausdrücklich bereitgestellten aktuellen Arbeitsstand und prüft vorhandene Projektregeln, insbesondere tatsächlich verfügbare `AGENTS.md`. Dieser Plan behauptet keine Kenntnis ignorierter lokaler Dateien, des aktuellen GitHub-HEAD oder inzwischen ausgeführter CI.

Im gelesenen Snapshot bezeichnet sich `planning/watcher-events/commit-plan.md` als Revision 7 und abgeschlossen. `planning/result-publication/commit-plan.md` führt `CIFS-1` als vorbereitet und tatsächliche Apply-/Zielplattformnachweise noch als offen. Diese Angaben sind beim Umsetzungsstart anhand realer Nachweise zu aktualisieren, nicht aus vorhandenen Codezeilen als erledigt abzuleiten. Bereits angewendete Änderungen werden nicht zurückgesetzt oder erneut eingespielt.

Die ursprüngliche Planerstellung führte nichts auf dem Host aus. Die folgenden Abschnitte 1.4–1.6 dokumentieren Vorbereitung und Reparatur von PP-00; den PP-00-Abschluss und die frühere PP-01-Basis enthält Abschnitt 1.7. Die Pixel-Testpolicy in Abschnitt 1.8 ist historisch. Maßgeblich ist die spätere Nutzerentscheidung und Reparaturgrundlage in Abschnitt 1.10.

### 1.4 PP-00: aktueller Abgleich für Bundle 024

**Auftrag vom 7. Oktober 2026:** Erstes Bundle des Features erstellen und integrieren.
Die repositoryweite Bundlezählung wird nach dem zuletzt dokumentierten Bundle 023
mit **024** fortgesetzt; dies ist das erste PYZ/PACK-Bundle, nicht Commit 24.
Die Nummer ist Handoff-Metadatum und kein neuer Zählerdienst.

| Gegenstand | Für PP-00 tatsächlich bereitgestellter Stand |
|---|---|
| Result | `patch-harbor_Result_132210_1007_306573.zip` |
| SHA-256 | `672d3d59479787132fe517d0a0dff7c2e4d0e65eba3c5d766a522711897556de` |
| repo_id | `23a55eed-715d-4a28-926e-5410a23bf6e8` |
| base_commit | `bf0b82e5de1eaf3afb2d645d77cd7799e7b6e0b7` |
| state_fingerprint | `7c9d2a24e397e0e5` |
| fingerprint_algorithm | `patchharbor-state-v1` |
| Resultoperation | Manuelles `bundle`, erfolgreich erstellt; kein vorausgehender Apply in diesem Result |
| Quellabgleich | Alle 289 Base-Dateien: Größen und Git-Blob-IDs stimmen; bytegleich mit der Analysegrundlage aus Abschnitt 1.2 |
| Änderungen im Result | `dirty: false`; beide Änderungsdiffs leer; keine untracked Einträge |
| Zielumgebung laut Result | Pixel / Ubuntu 26.04 in PRoot, Linux aarch64, CPython 3.14.4; keine neu erfundene Hostprüfung |
| Hauptspezifikation und Ergänzung | Basis unverändert; Ergänzung Revision 2 bytegleich mit Abschnitt 1.2 aufgenommen |
| Lokale Regeln | Keine `AGENTS.md` im übergebenen Inventar; ignorierte lokale Dateien nicht mitgeliefert und nicht als gelesen behauptet |

Der Watcher-Plan bleibt abgeschlossen. CIFS-Code und -Dokumentation sind im
neuen sauberen Snapshot enthalten. Das ist kein nachgelieferter CIFS-Apply-,
Windows- oder Freigabenachweis. Die dort weiterhin offenen Nachweise bleiben
offen. CI-Run `37459998721` ist der jüngste in den gelieferten Dokumenten
als erfolgreich bezeichnete Lauf, auf dem dort genannten Commit
`44cc77a42b492fc1f31267db5139253ef7545b9f`; er ist **kein hier erneut abgerufener
oder auf den aktuellen Commit übertragener CI-Nachweis**. Die neue CI bindet
sich an den erst beim Apply von PP-00 erzeugten vollständigen Commit.

Die Produktversion bleibt `1.2.1`; die neue Zielversion entscheidet der Nutzer
spätestens vor der Releasefreigabe. PP-00 führt weder `pack` noch PYZ,
Resultformat 3, eine Neuinstallation oder einen Watcher-Neustart ein.

### 1.5 Ausdrückliche einmalige Testausnahme: PP-00 auf dem Pixel

Die nachträgliche Nutzerentscheidung vom 7. Oktober 2026 hat gemäß `GOV-01`
Vorrang: **Im Apply dieses ersten Feature-Bundles laufen keinerlei
Projekttests; sie laufen ausschließlich in der automatisch gestarteten CI,
parallel.** Grund ist die begrenzte Rechenleistung des Pixels.

Für **Bundle 024 / PP-00 allein** gilt deshalb:

- Kein lokaler Testlauf im Apply, weder seriell noch parallel, auch keine
  Teil-/Smoke-Suite, kein Modusvergleich und keine Installation von
  Entwicklungs- oder Testabhängigkeiten. Für diese Auslieferung werden auch in
  der Chat-Umgebung keine Produkttests als Ersatz gestartet. Paketinspektion,
  Referenzvalidierung, Syntax-/Hash- und Git-Scopeprüfungen sind davon getrennte
  Übergabesicherungen, keine behaupteten Produkttests.
- Der eine Dokumentationscommit darf ausdrücklich **vor** dem CI-Ergebnis
  entstehen; anschließend erfolgt genau ein normaler Push nach `origin/dev`.
  Damit ist für diesen Schritt auch das sonstige lokale Vorcommit- und
  serielle/parallele Bundle-Endgate ersetzt. Es wird keine bestandene lokale
  Suite protokolliert. Git-Hooks werden nur für diese Commit-/Push-Aufrufe
  mit einem kommando-lokalen `core.hooksPath=/dev/null` ausgeschaltet, damit
  keine benutzerdefinierten Testhooks den Pixel belasten. Keine persistente
  Git-Konfiguration, keine Hookdatei und keine Registry werden verändert.
- Der vorhandene Helfer `scripts/run_handoff_ci.py` startet danach **einmal**
  `acceptance-tests.yml` per `workflow_dispatch`, gebunden an vollständigen
  Commit, Branch `dev` und eine eindeutige Handoff-ID. Kein zusätzlicher
  Push-/PR-/Schedule-Trigger, kein automatisch wiederholter Dispatch.
  Sein historisches ID-Präfix `patchharbor-riv-` bleibt unverändert; es ist
  eine Korrelationskennung, keine Reaktivierung des RIV-Plans.
- Alle sechs bestehenden nativen und Docker-Jobs bleiben Pflicht. Die
  Workflow- und Docker-Aufrufe benutzen bereits den gemeinsamen Runner mit
  xdist-Default `auto`; keine zusätzliche serielle Vollsuite und kein
  automatischer Modusverifier. Die Suite-Phasen eines Jobs dürfen wie bisher
  nacheinander laufen; die Testausführung erfolgt parallel. Keine zusätzlichen
  CPU-Lasten durch Tests auf dem Pixel während des Wartens.
- Der Entrypoint wartet auf die vollständige CI-Auswertung des vorhandenen
  Helfers. Run-ID, URL, Commit, Jobs und Controller-Nachweise bzw. Fehler
  erscheinen im Ausführungslog und damit im Result. Fehlender Zugang,
  Push-/Dispatchfehler, rote oder unvollständige CI ergeben **keinen**
  Gesamterfolg. Entstandene Commits bleiben erhalten; kein Reset, Force-Push,
  blinder Retry oder automatisches Folgebundle.
- Der feste lokale Workspace des Handoff-Versuchs verhindert seine erneute
  Dispatch-Ausführung. Ein unklarer/abgebrochener Versuch wird anhand des
  vorhandenen Belegs aufgeklärt, nicht mit einer neuen ID blind wiederholt.

Diese Ausnahme gilt nicht automatisch für PP-01 oder spätere Bundles und
ändert weder Produkt-Sicherheitsprüfungen noch die allgemeine Test-/CI-Policy.
Die 120 Minuten des nativen Matrix-Jobs bleiben erhalten. Reguläre CI nach
024 bleibt entsprechend der bisherigen Zählregel 029, soweit kein späterer
Nutzerauftrag etwas anderes bestimmt. Ein Erfolg von 024 ersetzt den noch
fehlenden tatsächlichen Test auf der betroffenen CIFS-Freigabe nicht.

### 1.6 PP-00-FIX1 / Bundle 025: fehlgeschlagenen ersten Apply fortsetzen

Der ausdrückliche Reparaturauftrag bezieht sich auf denselben PP-00-Schritt.
**Quelle:** `patch-harbor_Result_134816_1007_61119e.zip`, SHA-256
`3ba13122fb57985fb081cc51260abf8f495a849a7be00a071b6c4a433b703bfa`.
Die tatsächliche Bindung lautet `repo_id=23a55eed-715d-4a28-926e-5410a23bf6e8`,
`base_commit=bf0b82e5de1eaf3afb2d645d77cd7799e7b6e0b7`,
`state_fingerprint=05876fabe128cc05`, `fingerprint_algorithm=patchharbor-state-v1`.
Sie beschreibt diesen Reparaturausgangspunkt, keine dauerhafte Planbindung.

**Belegt:** Apply 024 schrieb die sechs vorgesehenen Dokumente. Der Entrypoint
brach in der `origin`-Prüfung mit Exit 1 ab, noch vor Staging, Commit, Push und
Workflow-Dispatch. Das Result ist dirty, der Basiscommit unverändert, der
staged Diff leer. Vier bestehende Dokumente sind verändert; Plan und Ergänzung
sind untracked. Alle sechs Inhalte entsprechen dem zuvor gelieferten Paket.
Die 289 Base-Dateien und beide untracked Inventare wurden erneut gegen die
Result-Bytes geprüft. `.git/config` und `.ssh/config` sind nicht enthalten;
eine frühere bekannte SSH-Alias-Konfiguration ist kein aktueller Hostnachweis.

**Ursache und Reparatur:** Die starre Liste von sechs wörtlichen GitHub-URLs
akzeptierte keine SSH-Host-Aliase. Der neue Entrypoint prüft unterstützte HTTPS-,
SSH-URL- und SCP-Schreibweisen strukturell. Bei SSH wird mit `ssh -G` die für
diesen Aufruf wirksame Host-/User-/Port-Konfiguration geprüft, ohne sie zu
ändern. Erwartet bleiben GitHub und das konkrete Repository, kein beliebiger
Alias oder Fork. Origin-Fetch und -Push werden getrennt geprüft; Git-Remote-Ref
und GitHub-API-Ref müssen vor Commit und nach Push zum selben vollständigen
Commit passen. Zugangsdaten, vollständige Remote-URLs und Schlüsselpfade
werden nicht protokolliert. Kein automatisches `remote set-url`, Rebase,
Reset, Force-Push, Checkout oder neue Registrierung.

**Scope:** Der neue Paket-Fingerprint bindet an den tatsächlichen dirty Zustand.
Bereits geschriebene Dateien werden nicht verworfen. Fünf der vorhandenen
Dokumente erhalten nur diesen Fehler-/Fortsetzungsnachweis; die Ergänzung
Revision 2 bleibt bytegleich. Genau dieselben sechs fachlich vorgesehenen
Dokumentpfade werden kontrolliert zusammen committed. Produktcode,
Hauptspezifikation, Workflow, Testpolicy-Code und CI-Helfer bleiben unverändert.
Es gibt weiterhin genau einen geplanten PP-00-Dokumentationscommit mit der
bisherigen Message. FIX1 ist keine zusätzliche fachliche Position der 16er-Folge.

**Einmalige Pixel-Ausnahme:** Abschnitt 1.5 gilt für die Fortsetzung dieses
noch nicht abgeschlossenen ersten Schritts auch in Bundle 025. Kein lokaler
Produkttest, kein Test-/Build-Setup, keine Testhooks. Übergabeprüfungen bleiben
erforderlich. Der bereits vorhandene CI-Helfer startet nach normalem Commit/Push
automatisch genau einmal die parallele Acceptance-CI mit einer festen neuen
Handoff-ID für 025. Dass 024 keinen Dispatch erreichte, ist durch das Result
belegt; ein vorhandener alter oder neuer Handoff-Workspace blockiert trotzdem
einen neuen Versuch. Keine Wiederholung bei unklarem Start oder roter CI.

Das Skript wartet auf alle sechs vorgeschriebenen Jobs und Nachweise. Erst
der vollständige grüne, commitgebundene CI-Beleg und unveränderter sauberer
Arbeitsstand erlauben `PATCHHARBOR-BUNDLE-NR: 025 | APPLIED SUCCESSFULLY`.
Vorhandene Commits/Änderungen bleiben bei einem späteren Fehler erhalten.
Produkt- oder native Freigaben werden durch das Reparaturpaket nicht behauptet.
PP-01 und spätere Schritte erhalten keine Ausnahme. Der weitere reguläre
CI-Termin 029 wird durch den ausdrücklich notwendigen Reparaturlauf nicht
stillschweigend neu gezählt; tatsächlich erbrachte Läufe werden dokumentiert.

**Historischer Status zu Bundle 025:** PP-00-FIX1 vorbereitet; tatsächliche
Apply-/CI-Bestätigung damals noch offen. Ein Prüfversuch des Entrypoints in der
Chat-Umgebung war kein Produkt-, Host- oder CI-Nachweis.

### 1.7 PP-00 bestätigt; PP-01 / Bundle 026 vorbereitet

**Historischer Stand von Bundle 026:** Die dort vorgesehenen lokalen Gates
und der CI-Termin 029 gelten nicht mehr für die Fortsetzung. Abschnitt 1.8
ersetzt sie aufgrund des späteren Nutzerauftrags für die gesamte Pixel-Phase.

Das Result `patch-harbor_Result_141601_1007_ef9735.zip` (SHA-256
`ca5149bd2ad89abaa204a460736a4f6cd71b1d8ff6446c4b82da72661683859a`)
belegt den erfolgreichen Reparatur-Apply von Bundle 025. Der tatsächliche neue
Commit ist `7a28bbc2189cdb2a78590e62a45e4d96b0ff893d`, Message
`docs(plan): establish PYZ and pack implementation baseline [PP-00]`.
Das Ausführungslog bestätigt normalen Push, genau einen Dispatch und CI-Run
`37635401106` mit passender Commitbindung und sechs erfolgreichen Jobs.
Dies ist der Nachweis des gelieferten Results, kein erneuter Live-Abruf.

Alle 291 Base-Dateien wurden auf Größe und Git-Blob-ID abgeglichen. Der aktuelle
Arbeitsstand ist sauber; staged/unstaged Deltas sind leer und es gibt keine
untracked Einträge. Die aktuelle Bindung verwendet den obigen **tatsächlichen**
Commit, `repo_id=23a55eed-715d-4a28-926e-5410a23bf6e8`,
`state_fingerprint=7c9d2a24e397e0e5`, `fingerprint_algorithm=patchharbor-state-v1`.
Die alten `expected_*`-Werte des Reparatur-Applies sind keine neue Patchbindung.
Hauptspezifikation und Erweiterung Revision 2 bleiben bytegleich.

**PP-01, 2/16, Bundle 026:** `capture_result_reference` hält vollständige
ResultFacts, Result-SHA-256, geprüftes Suffix und die exakten unveränderlichen
Handoff-Bytes aus einer stabilen Erfassung zusammen. `read_result_reference`
behält Signatur und Tupelergebnis. Der interne Endvalidierungspfad
`validate_patch_against_reference` liest die tatsächlichen Patchbytes und
benutzt dieselbe Bindungsprüfung/Ergebnisbildung wie `validate_patch`, ohne
die Referenzdatei erneut zu öffnen. Kein öffentlicher neuer Pack-Befehl,
keine PYZ, kein Formatwechsel und keine geänderte Publikationspolitik.

Der Refactor bekommt 52 funktionale Prüffälle in
`tests/test_captured_reference.py`; P-05/P-06/P-07/S-04 werden damit auf
Referenzbausteinebene vorbereitet, nicht als vollständige Pack-Abnahme markiert.
Die neue Testdatei wurde erfolgreich gesammelt und syntaktisch geprüft.
Elf manuelle API-Gegenproben in zwei parallel gestarteten Prozessen bestanden.
Die reguläre parallele Development-Suite konnte in der Chat-Laufzeit nicht
starten: pytest-xdist/build-Abhängigkeiten fehlen, Paketbezug war nicht
verfügbar. Das ist `REDUCED_TEST_SCOPE`, keine bestandene Vollsuite und keine
neue Ausnahme für den Zielrechner. Native Windows-/CIFS-Abnahmen bleiben separat.

**Apply-Gate für 026:** Die einmalige PP-00-Pixel-Ausnahme ist beendet.
Der Entrypoint richtet nur die bestehende Entwicklungs-venv ein, führt vor dem
einen Commit dieselbe vollständige Suite seriell und parallel (`auto`) aus
und verlangt äquivalente Controller-Nachweise auf unveränderten Quellen.
Es gibt keinen zusätzlichen identischen parallelen Vorlauf. Fehler verhindern
Commit/Push; keine Deaktivierung von Hooks, kein Rollback und kein Retry.
Normale Push-Zielprüfung einschließlich SSH-Aliassen bleibt erhalten.

Bundle 026 löst gemäß unveränderter Fünferregel **keinen zusätzlichen CI-Lauf**
aus. Nächster regulärer Termin bleibt 029; der ausdrücklich beauftragte
Reparaturlauf 025 verschiebt ihn nicht. Nach erfolgreichem lokalen Endgate
gibt es einen normalen Push nach `origin/dev`. Alte CI ist kein Testnachweis
für PP-01. Dessen tatsächliche Ausführung bleibt bis zum nächsten Result offen.

### 1.8 PP-01-FIX1 / Bundle 027: Pixel-Phase nur parallele CI

**Historisch; seit dem ausdrücklichen Laptop-Wechsel durch Abschnitt 1.9 ersetzt.**

**Spätere ausdrückliche Nutzerentscheidung vom 7. Oktober 2026:** Ab jetzt
keinerlei Produkttests oder Testinstallationen auf dem Pixel, bis Christian
explizit den Wechsel auf den Laptop bestätigt. Tests nur in der automatisch
gestarteten parallelen GitHub-CI. Gemäß GOV-01 hat diese Entscheidung Vorrang
vor den bisherigen lokalen Vorcommit-/Endgates, dem Modusvergleich, der nur
PP-00 betreffenden Ausnahme und der Fünferregel. Die Phase endet nicht durch
einen neuen Planpunkt, eine Bundle-Nummer, ein Datum oder Linux-Erkennung.

| Gegenstand | Aktuelle Fortsetzungsgrundlage |
|---|---|
| Result | `patch-harbor_Result_160403_1007_ee4cb0.zip` |
| Result-SHA-256 | `ebfae4a0657017604e658ffe42fd71ddb30782612b59e64fc3ce882da65a905f` |
| repo_id | `23a55eed-715d-4a28-926e-5410a23bf6e8` |
| base_commit | `7a28bbc2189cdb2a78590e62a45e4d96b0ff893d` |
| Tatsächlicher state_fingerprint | `44ec92f72a0fd9dd` |
| fingerprint_algorithm | `patchharbor-state-v1` |
| Resultstatus | `interrupted`, Prozess-Exit 130; kein completed_commit |
| Index | Staged-Diff leer; sieben modifizierte bestehende Pfade und zwei untracked Dateien im übergebenen Arbeitsstand |
| Quellkontrolle | 291 Base-Dateien in Größe/Git-Blob-ID geprüft; neun PP-01-Nutzdateien nach Rekonstruktion bytegleich mit Bundle 026 |
| Ausführung 026 | Lokale Testinstallation erfolgt, serieller Lauf vor Abschluss unterbrochen; kein neuer Commit, Push oder CI-Dispatch erreicht |
| Fortsetzung | Bundle 027, PP-01-FIX1, unverändert Planposition 2/16; keine 17. Planposition |

Die `actual_*`-/Context-Werte sind die Bindung. Insbesondere darf der alte
saubere Fingerprint `7c9d2a24e397e0e5` nicht für das Fortsetzungs-ZIP verwendet
werden. Der neue Apply prüft diesen aktuellen dirty Zustand erneut. Kein
Reset, Clean, Stash oder erneutes Ausbringen aus dem alten Bundle 026.

**Umfang:** Keine Änderung an den bereits ausgebrachten beiden PP-01-Coredateien,
der neuen funktionalen Testdatei oder `docs/pack.md`. Bundle 027 passt fünf
Dokumente und seinen privaten Entrypoint an. Der eine tatsächliche Commit
enthält dadurch die neun noch uncommitteten PP-01-Pfade insgesamt, Message
`refactor(reference): share verified reference facts for packing [PP-01]`.
PP-01-FIX1 bezeichnet die Reparatur des Ablaufs, nicht einen zusätzlichen
Produktplan-Commit. Beide Spezifikationen, CI-Workflow, CI-Helfer, Testwerkzeuge,
normal installierte Runtime und Watcher bleiben unverändert.

**Verbindlicher Ablauf während der aktiven Pixel-Phase:**

1. Keine lokale Voll-/Teil-/Smoke-Suite, kein pytest/Collection, kein serieller
   oder paralleler lokaler Lauf, kein Modusverifier, kein venv-/pip-/uv-Testsetup
   und keine Testhooks. Fehlende CI löst keine lokale Ersatzprüfung aus.
   Vorhandene ignorierte Testumgebungen/Berichte bleiben erhalten. Paket-,
   Bindungs-, Hash-, Syntax-, Git-Scope- und CI-Ergebnisprüfungen bleiben erlaubt
   und werden nicht als Produkttests bezeichnet.
2. Nach unveränderten Datei-/Scope-/Branch-/Remote- und CI-Zugangsprüfungen
   genau den vorgesehenen Commit erzeugen und normal nach `origin/dev` pushen.
   Die Commit-/Push-Aufrufe verwenden ausschließlich kommando-lokal
   `core.hooksPath=/dev/null`; keine persistente Konfigurationsänderung.
3. Unmittelbar danach automatisch einmal `scripts/run_handoff_ci.py` mit
   vollständigem tatsächlichem Commit und eindeutiger Handoff-ID aufrufen.
   Der vorhandene Workflow bleibt `workflow_dispatch`-only. Alle sechs
   nativen/Docker-Jobs und ihre Nachweise bleiben Pflicht, parallel über die
   vorhandenen xdist-`auto`-Aufrufe; keine zusätzliche serielle CI-Suite.
4. Der Pixel wartet nur und liest CI-Berichte. Für die nativen Berichte werden
   positive Workerzahlen verlangt; ein serieller Bericht erfüllt das Gate
   nicht. Gesamterfolg erst nach zugeordneter grüner CI, bestätigtem Commit und
   sauberem unverändertem Arbeitsstand. Keine frühzeitige Erfolgsmarkierung.
5. Rote, fehlende oder unvollständige CI, fehlender Zugang oder Abbruch bleiben
   offen. Bereits erzeugte Commits bleiben erhalten; kein automatischer
   Retry/Rerun, Force-Push oder Rollback. Die im Log genannte Handoff-ID ist
   vor jedem bewussten Wiederholungsauftrag auf vorhandene Nachweise zu prüfen.

Dies gilt für **jedes änderungsführende Pixel-Bundle**, nicht nur 027. Die
Fünferregel ist währenddessen ausgesetzt; keine zweite CI am alten Termin 029.
Für mehrere echte Zwischenzustände darf erst nach erfolgreicher gebundener CI
des jeweiligen Zustands weitergearbeitet werden; im Zweifel getrennte Bundles.
Der Abschluss von PP-01 reaktiviert lokale Tests ausdrücklich **nicht**.
Ein späterer Laptop-Wechsel wird nur aus Christians ausdrücklicher Mitteilung
abgeleitet; dann wird die gültige lokale/CI-Policy neu eingeordnet.

**Prüfstatus dieser Auslieferung:** Quell-/ZIP-/Bindungs-/Syntaxkontrollen sind
keine Produkttests. Auf dem Host wurde durch das Erstellen von Bundle 027
nichts ausgeführt. Apply, Commit, Push und neue CI sind bis zum zugehörigen
Result offen. Die 52 neuen PP-01-Fälle bleiben in den regulären CI-Suites und
werden weder weggelassen noch aufgrund des abgebrochenen Laufs als bestanden
gezählt. Offene native/CIFS-Nachweise bleiben von dieser Änderung unberührt.

### 1.9 PP-01-FIX2 / Bundle 028: Laptop und konsistente Legacy-Fixture

Historischer Vorbereitungsstand; tatsächlicher Abbruch und spätere Policy siehe 1.10.

Christian hat am 7. Oktober 2026 ausdrücklich die Fortsetzung auf dem Laptop
beauftragt. Damit ist die Pixel-CI-only-Phase beendet. Development bleibt in
`patchharbor-codex`; allein der vorhandene Watcher wendet das fertige Paket auf
`patchharbor-apply` an. Kein direkter Commit, Checkout oder Apply durch Development.

| Gegenstand | Bestätigte aktuelle Grundlage |
|---|---|
| Result | `patchharbor-apply_Result_201726_1007_21672a.zip` |
| Result-SHA-256 | `e930a4ab76dcec9cf44962383187b57866af2c6b824013ad2fe67b07b52bfcba` |
| repo_id | `e7a93d72-62dc-4759-97e8-6bf6cdf10e90` |
| base_commit | `e6ed2895c6922c1bf0f8f13ec6af58bb70fd7c3d` |
| state_fingerprint / Algorithmus | `7c9d2a24e397e0e5` / `patchharbor-state-v1` |
| Ergebnis | Erfolgreiches manuelles `bundle`, clean, kein Dry-Run; kein Apply-/Testnachweis dieses Results |
| Quellkontrolle | 293 Base-Dateien gegen Größen, Git-Blob-IDs, tatsächlichen Apply-Commit und sauberen Apply-Working-Tree abgeglichen |
| Runtime | `unavailable: source_not_prepared`; etablierte Prüfung mit vertrauenswürdigem vorhandenen Core, kein vorgetäuschter Wheel-Test |
| Entwicklung | Lokaler Dev-Git-HEAD noch `68dba9216b72dc0b6441df83f49c9047b8b038b9`, vorhandene Änderungen erhalten; isolierter Result-Snapshot innerhalb der Development-Arbeitskopie |

Der Nutzer meldet PP-01 als committed und nach origin/dev gepusht. Der lokale
Apply-HEAD und sein sauberer Snapshot bestätigen den Commit; dieses manuelle
Result belegt weder den vorausgehenden Push noch eine grüne PP-01-CI.
Die gemeldeten Laptop-Gruppen waren core 1807/1, platform 30/2, packaging 96/3
(passed/skipped), E2E 4 failed / 544 passed / 4 skipped. Die vier betroffenen
`frozen_format1`-Fälle wurden auf der unveränderten Referenz parallel reproduziert.

**Ursache und Umfang:** Das Fixture ersetzte drei Reader-Module durch historische
Dateien, behielt aber die neue `patch_inspection.py` aus PP-01. Deren Import von
`CapturedResultReference` und `capture_result_reference` scheitert am alten
Reader, bevor der Prozess seine konservative Entscheidung treffen kann.
Zusätzlich wird jetzt ausschließlich die dazugehörige `patch_inspection.py`
aus demselben historischen Commit `d31047b2feca049c2db5443bb61df2ce7ce5e7f6`
mit Provenienz/SHA-256 eingefroren. Die Kindprozessprobe prüft alle inventarisierten
historischen Module. Die echte Exit-10-, Archivierungs- und Unverändertheitsprüfung
bleibt erhalten. Keine optionalen Produktimports, Test-Skips oder API-Aufweichung.
Der produktive PP-01-Code und beide normativen Spezifikationen bleiben bytegleich.

**Gates:** Gezielte Regression und PP-01-Prüfer, anschließend vollständige lokale
Development-Suite ausschließlich parallel, mit Quellbindung und Controller-Bericht.
Die Auslieferung ist erst nach erfolgreichem vollständigem Gate zulässig; konkrete
Befehle, Zähler und Hashes stehen im Handoff-/Ausführungsnachweis. Im Apply laufen
vor dem einen Korrekturcommit auf demselben Endstand die vollständige serielle
und danach parallele Suite mit Ergebnisvergleich. Danach genau ein normaler
Push nach origin/dev, ohne Hook-Bypass. Es werden keine Tests oder Installationen
im tatsächlichen Apply-Repository außerhalb dieses geprüften Entrypoints gestartet.

Die reguläre Fünferregel gilt wieder: Bundle 028 verlangt keinen Zusatzlauf;
der nächste reguläre CI-Termin bleibt 029 einschließlich Windows nach Apply/Push.
Bekannte fehlgeschlagene CI und offene native/CIFS-Nachweise bleiben offen,
bis neue passende Nachweise vorliegen. Ein Linux-Lauf ersetzt sie nicht.

**Status:** PP-00 bis PP-03 tatsächlich angewendet/gepusht. PP-04A / Bundle 034 bereitet das kanonische PYZ-Datenprofil und beide getrennten Buildprofile vor; Apply noch offen.
ist vorgesehen. Kein PP-02-Schritt, keine neue PYZ, kein `pack`, kein Writerwechsel.
PP-01-Abnahme erst nach erfolgreichem tatsächlichen Reparatur-Apply und seinen
vorgeschriebenen lokalen Endgates; keine automatische Planfortsetzung durch 028.

### 1.10 PP-01-FIX3 / Bundle 029: erhaltenen Teilzustand fortsetzen

Das vollständig geprüfte tatsächliche Apply-Result
`patchharbor-apply_Result_204228_1007_dba7f3.zip`, SHA-256
`b4be31d89de55cd9485dc8ad350dbf474189277825b9daff90d9e53b783e78d0`,
bestätigt für Patch-SHA-256
`04ac3941e0ed38ac14402fcf3bfc2b6a35b0524220e21eaa3f6652b0db06ec6a`
einen Entrypoint-Abbruch mit Exit 1. `git diff --check` beanstandete fünf
nachgestellte Leerzeichen in diesem Plan. Keine Tests, kein Commit, kein Push.
Alle acht vorgesehenen Dateien sind im dirty Teilzustand erhalten und vollständig
gegen die ausgelieferten Bytes und das tatsächliche Apply-Repository geprüft.

Neue Patchbindung: `repo_id=e7a93d72-62dc-4759-97e8-6bf6cdf10e90`,
`base_commit=e6ed2895c6922c1bf0f8f13ec6af58bb70fd7c3d`,
`state_fingerprint=5b93b0f9950d5100`, `fingerprint_algorithm=patchharbor-state-v1`.
Die erwartete clean Bindung des alten Patches ist keine Reparaturgrundlage.

Die ursprüngliche historische Fixture-Reparatur bleibt erhalten. FIX3 bereinigt
die problematischen Planzeilen und passt ausschließlich die Übergabe- und
Statusdokumentation an die neueste ausdrückliche Nutzeranweisung an:

- Development und jeder Apply-Commit erhalten eine vollständige parallele Suite;
  auch am Bundle-Ende keine serielle Suite und kein Vergleich mit einer solchen.
- GitHub-CI bleibt `workflow_dispatch`; ausschließlich Christian startet sie.
  Kein automatischer Dispatch durch Codex oder Entrypoints und kein Fünfertakt.
- Die Schleife setzt nach bestätigten Results den bestehenden Plan fort.
  Belegte Korrekturen sind ohne feste Versuchszahl erlaubt; Sicherheitsgrenzen
  und das Verbot spekulativer Patches bleiben bestehen.

Die finale Payload wird vor Auslieferung zusätzlich mit dem echten lesenden
`git diff --no-index --check` gegen die Commitbasis geprüft. Der Entrypoint
gibt bei einem fehlgeschlagenen Git-Befehl dessen konkrete Diagnose weiter.
Ein Commit `test(result): complete consistent historical fixture recovery [PP-01-FIX3]`
ist vorgesehen; tatsächliche Abnahme bleibt bis zum Watcher-Result offen.
Neue Produktfunktionen, globale Installation und Watcher-Neustart sind kein Teil
dieser Korrektur. Produktquellen und beide normativen Dateien bleiben bytegleich.

### 1.11 PP-01 bestätigt; PP-02A / Bundle 031

Das echte Apply-Result `patchharbor-apply_Result_213505_1007_b74ddc.zip`, SHA-256
`615f40caebc6265973a44227507e5a51b513a40d7f56636e436717559cadbbbe`, bestätigt die PP-01-Fixture-Reparatur durch Bundle 030.
Commit und normaler Push: `e34a81c517d66c079f85cc43033b233f8c9f90a8`,
`test(result): complete consistent historical fixture recovery [PP-01-FIX4]`.
Alle 294 Result-Base-Dateien sind gegen den ausgelieferten Stand und den tatsächlichen
Arbeitsbaum geprüft. Keine staged/unstaged Deltas oder untracked Einträge.

Neue Bindung: `repo_id=e7a93d72-62dc-4759-97e8-6bf6cdf10e90`,
`base_commit=e34a81c517d66c079f85cc43033b233f8c9f90a8`,
`state_fingerprint=7c9d2a24e397e0e5`,
`fingerprint_algorithm=patchharbor-state-v1`.
Nur dieses neue Result bildet die technische Grundlage von Bundle 031.

Das vollständige parallele Apply-Gate bestand mit 2.480 Tests und acht Skips,
zwölf Workern und Exit 0. Report-SHA-256:
`0e9c70e9ee93c972f70bee61ba875fc8825d6e6fba9027627b8f78c09205bff9`.
Development bestand mit 2.505 Tests und sieben Skips einschließlich 24 separater
Entrypoint-Prüffälle. Ein vorheriger lokaler Lauf enthielt einen korrigierten
Handoff-Testaufruf und einen im vollständigen Wiederholungslauf nicht erneut
aufgetretenen Signal-/Prozessbaumfehler. Dessen genaue Umgebungsursache bleibt offen.

Bundle 029 hatte bereits ein grünes Apply-Gate, brach aber vor dem Commit an
einem falsch verglichenen Test-Hash ab: Die lokale ignorierte `AGENTS.override.md`
gehört zum Apply-Testkontext, nicht zum portablen Snapshot. FIX4 erfasst diesen
Kontext vor dem Gate und bindet Bericht sowie Nachkontrolle daran. Alle Projekt-
dateien bleiben zusätzlich vor/nach Tests und Commit vollständig gehasht.
Keine gelockerte Testprüfung, Produktimport-Fallbacks oder neue PP-01-Produktfunktion.

**PP-02A:** Interne begrenzte Aufnahme des expliziten Inhaltsbaums. Gemeinsame
Verzeichnishandles sind aus dem vorhandenen Archivadapter extrahiert; dessen
Publikationslogik bleibt unverändert. Quelldateien verwenden den bestehenden
No-follow-Dateiadapter, POSIX-relative Handles und auf Windows gepinnte Vorfahren.
Bytes, Pfade, Modi, statischer Entrypoint, 10.000 Knoten und 1.000 spätere
ZIP-Einträge einschließlich generierter Metadaten werden geprüft. Abschließende
Inventur vergleicht auch erneut geöffnete Handle-Metadaten, ohne Inhalte erneut
aufzunehmen oder eine Stabilitätswiederholung einzuführen.

Neue fachliche Tests in `tests/test_pack_sources.py` behandeln P-08–P-11,
S-01–S-06, S-14/S-15/S-17 auf Bausteinebene. `docs/pack.md` beschreibt Grenzen
und internen Stand. `pack_sources` ist bis PP-02B ein ausdrücklich vorbereiteter
Architektur-Einstieg; danach übernimmt sein tatsächlicher Verbraucher diese Rolle.
Öffentliche API/CLI, Format-2-Writer und Runtime-Wheel bleiben unverändert.
Vor Auslieferung und vor dem tatsächlichen Commit ist das volle parallele Gate
Pflicht. Das folgende Result liefert den Nachweis; CI startet ausschließlich der
Nutzer. Native Windows-/3.12-/Docker-/CIFS-Freigaben werden nicht vorweggenommen.

### 1.12 PP-02A bestätigt; PP-02B/C gemeinsam in Bundle 032

Result `patchharbor-apply_Result_215703_1007_0001d3.zip`, SHA-256
`f0560b5635c06858babbdc8869b4dc524f03870ac0f026397b99a54a78d68db2`,
bestätigt den tatsächlichen Apply von Bundle 031, ein vollständiges paralleles
Gate mit 2.561 bestandenen Tests und 8 Skips, einen normalen Push und sauberen
Baum. Commit: `d487a84c55857ea0f64914f1cd636e5fc796a3fb`.
Alle 298 Snapshot-Dateien stimmen mit der geprüften Übergabe überein.

Nur dieses neue Result bindet Bundle 032: Repository-ID
`e7a93d72-62dc-4759-97e8-6bf6cdf10e90`, Base-Commit wie oben, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`. Beide normativen
Spezifikationen behalten ihre in Abschnitt 1.2 genannten Bytes.

**Nachvollziehbare Zusammenlegung vor Übergabe:** PP-02B (Manifest, Handoff,
ZIP-Kandidat) und PP-02C (Endvalidierung, Veröffentlichung, öffentliche API)
werden als ein echter Dateizustand mit einem Commit `PP-02BC` geprüft. Es werden
keine künstlichen W/R/C-Zwischenzustände oder zwei bereits ausgeführte Commits
behauptet. Die ursprünglichen 16 fachlichen Positionen bleiben zur Zuordnung
erhalten; die vorgesehene Commitanzahl sinkt durch diese Zusammenlegung auf 15.

`api.pack_patch` erzeugt ein referenzgebundenes Format-1-Paket, prüft die realen
temporären Bytes vollständig und veröffentlicht exklusiv. Die finale Datei
wird über ihren gepinnten Handle ausgewählt: Linux nutzt `linkat` über procfs,
Windows `SetFileInformationByHandle(FileRenameInfo)` ohne Ersetzen. Ein Ziel
mit nicht unterstützter sicherer Primitive wird abgelehnt. Eigentum, Sync,
Quellinventar und abschließender Hash werden ohne Stabilitäts-Retry geprüft.
Cleanup bleibt im gepinnten Ausgabeverzeichnis; nach bestätigter Publikation
bleibt vollständiger Erfolg mit Warnung zugänglich, auch wenn ein Watcher die
finale Datei bereits übernommen hat. Kein Git, Build, Installer, Netzwerk oder
Entrypoint-Aufruf durch Pack. Die CLI folgt in PP-03.

`tests/test_pack_candidate.py` und `tests/test_pack_api.py` prüfen P-01–P-18
soweit ohne CLI/PYZ anwendbar, S-07–S-11/S-14–S-18 sowie die begrenzte Aussage
E-04. Die vorhandenen PP-01-/PP-02A- und Result-Regressionsfälle bleiben im vollen
parallelen Gate. Neue Module sind Teil der expliziten Distributionsinventare;
die temporäre Architektur-Ausnahme für `pack_sources` entfällt.

Vor Veröffentlichung sowie im Apply vor dem Commit gilt jeweils die gesamte
parallele Suite. Lokale Testreceipts, Paket-Hashes und der spätere tatsächliche
Apply stehen im Handoff/Result. Native Windows-, Python-3.12- und CIFS-Nachweise
bleiben bis zu realen Läufen offen. CI startet ausschließlich Christian.

### 1.13 PP-02B/C bestätigt; PP-03 / Bundle 033

Result `patchharbor-apply_Result_222538_1007_1e14cf.zip`, SHA-256
`5ef313afbe5c63ca51b0d2cb64cc0353d8fd3f1be39da3c14906d238d32ae826`, bestätigt den echten Apply/Push des gemeinsamen PP-02BC-Commits
`e2f6388c7d511b700ad825b64aea2aca6841ca51`. Das vollständige parallele Gate bestand mit 2687 bestandenen
Tests und 8 Skips; Repository sauber. Dieses Result ist die neue
Bindungsgrundlage für Bundle 033. Die vier vollständigen Bindungswerte werden
aus genau seinem Kontext übernommen; es gibt keine Wiederverwendung von 031.

PP-03 ergänzt `patchharbor pack` als dünnen Adapter auf `api.pack_patch`, mit
Pflichtreferenz, Entrypoint, genau einem Ausgabeziel und geprüften wiederholbaren
Modusangaben. JSON verwendet Version 2 und vollständige Referenzvalidierung.
Fehler nach Veröffentlichung bei Schreiben/Flushen der CLI-Ausgabe erhalten
Code 7 beziehungsweise 130, ohne Neubau oder angehängten zweiten Fehler-Envelope.
Die bestmögliche Diagnose nennt den schon veröffentlichten Pfad und Hash.

`tests/test_pack_cli.py` prüft Routing/Parität, fehlende/konkurrierende Optionen,
Modussyntax und semantische Fehler, vollständiges JSON sowie defekte/unterbrochene
Ausgabeströme. Dazu kommen ein echter gebauter Core außerhalb des Checkouts und
ein regulärer Apply-Durchstich einschließlich späterer State-Abweichung.
Die Beispiele werden funktional geprüft; keine Prosa-/Farb-/Layout-Snapshots.
Lokale und Apply-Gates bleiben vollständig parallel, CI ausschließlich manuell
durch Christian. PYZ, Format 3 und endgültige Plattformabnahme folgen später.

### 1.14 PP-03 bestätigt; PP-04A / Bundle 034

Result `patchharbor-apply_Result_224010_1007_f54fa4.zip`, SHA-256
`cb2200aa50cb4709b83b8473eea8a46ba7a70efe5aa2921e7f1097c5577b1c09`, bestätigt den tatsächlichen PP-03-Commit
`9bebc3c5a9da4da0cb6f846469a79bf9965a415a`, normalen Push und sauberen Baum. Das vollständige parallele Gate
bestand mit 2734 bestandenen Tests und 8 Skips.
Dieses Result liefert alle vier vollständigen Bindungswerte für Bundle 034.

PP-04A implementiert den geschlossenen kanonischen PYZ-Datenvertrag einschließlich
zyklusfreier Producer-/Content-ID und vollständiger bytegleicher Archivprüfung.
Das finite Core-Inventar schließt Watcher, dist-info, alte generierte Wheel-Daten,
Bytecode, Start-Hooks und eingebettete Artefakte aus. Der Materializer liest nur
geprüfte Ressourcen; er importiert oder startet keinen beschriebenen Code.
Die gemeinsame begrenzte Vorprüfung des ZIP-Zentralverzeichnisses wird von beiden
Profilreadern verwendet; der Legacy-Wheel-Datenvertrag bleibt unverändert.

Der normale Build bereitet zusätzlich das getrennte PYZ-Profil vor. Private,
am Build-Quellpfad verankerte Modulimporte verhindern eine Verwechslung mit einer
zufällig installierten Distribution. Beide Identitätsableitungen sind unabhängig:
der kanonische Legacy-Wheel-Satz enthält keine generierten PYZ-Daten, der PYZ-Satz
keine alten generierten Wheel-Daten. Die Installation trägt beide vorbereiteten
Sätze, aber der produktive Format-2-Writer liefert weiterhin nur sein Wheel.
`scripts/build_release.py` erzeugt daneben den bytegleichen PYZ-Kandidaten.

`tests/test_runtime_pyz.py` prüft Profile, Inventare, geschlossene JSON-Schemata,
Hashableitung, Budgets, manipulierte ZIP-Strukturen, Nichtausführung beschriebener
Module sowie den frühen Python-Versionsschutz. Die echten Build-/Installations-
und Legacy-Runtime-Regressionsfälle bleiben Teil der vollen parallelen Suite.
Der Root-Einstieg importiert die gemeinsame CLI; volle ZIP-Ressourcenfähigkeit,
Python-only-Bootstrap und spätere Result-Erzeugung folgen PP-04B/C und PP-05/06.
Dies ist noch keine Freigabe resultgenerierender PYZ-Kommandos.

### 1.15 PP-04A bestätigt; PP-04B / Bundle 035

Result `patchharbor-apply_Result_225941_1007_7e86ff.zip`, SHA-256
`f219d300d2c0841b97db572018316cf1c92f9e505f320e063d40739985fded4f`, bestätigt den tatsächlichen PP-04A-Commit
`a9ac74e00fd0ac0042d7474a52a95e1fb17a4d59`, normalen Push und sauberen Baum. Das vollständige parallele Gate
bestand mit 2802 bestandenen Tests und 8 Skips.
Dieses Result liefert alle vier vollständigen Bindungswerte für Bundle 035.

PP-04B führt einen gemeinsamen begrenzten Verzeichnisleser und einen am
Ausführungsarchiv verankerten ZIP-Ressourcenzugang ein. Der neue PYZ-Provider
prüft das gesamte vorbereitete Profil gegen das beim Paketimport geladene
Identitätsliteral. Lizenz, API-Dokumentation und Chatvorlage stammen aus genau
diesen geprüften Bytes. Wiederholte oder gleichzeitige Zugriffe eines Auftrags
verwenden seinen unveränderlichen Capture; ein neuer Auftrag prüft neu.
Gleichnamige Fremdinstallationen, CWD-Vorlagen, Buildcache, Netzwerk und temporäre
Extraktion werden nicht als Ersatz herangezogen. Ein altes Shared-Data-Layout
wird nur akzeptiert, wenn die Distribution das tatsächlich geladene Modul besitzt.

`pack` bevorzugt das eigene vorbereitete PYZ-Profil, sobald dessen Identität
geladen ist. Ein defektes ausgewähltes Profil führt zu einem Fehler statt zum
unbemerkten Rückfall auf das Wheel. Der frühere Provider verwendet denselben
begrenzten Verzeichnisleser und bewahrt seine Legacy-Daten- und Fehlerverträge.
Der produktive Writer bleibt Format 2. Die vollständige gemeinsame
Result-Ressourcenfixierung und deren Selbstupdateintegration folgen PP-06.

`tests/test_pyz_resources.py` prüft Identitätswechsel bei gleicher Version,
Mutation, fehlende/zu große Ressourcen, Symlinks, Konkurrenz, einmalige Captures,
keine externen Aufrufe sowie reale Verzeichnis- und PYZ-Importe ohne Checkout.
Die gebaute PYZ packt und validiert mit eigenen Ressourcen aus einem schreibgeschützten
Runtimebereich; die funktionierenden Legacy-Build-/Writerpfade bleiben Vollsuite.
Das ist noch keine Freigabe des neuen Result-Writers oder ein nativer CI-Nachweis.

### 1.16 PP-04B bestätigt; PP-04C / Bundle 036

Result `patchharbor-apply_Result_231520_1007_7f1796.zip`, SHA-256
`04216c2f6c38be74dc9120e525ef0e020bbf5a67c9c2df9e5eb6193419bd8d13`, bestätigt den tatsächlichen PP-04B-Commit
`25057ec9fa5c108a92a6a31be434c0d2c5e30118`, normalen Push und sauberen Baum. Das vollständige parallele Gate
bestand mit 2831 bestandenen Tests und 8 Skips.
Dieses Result liefert alle vier vollständigen Bindungswerte für Bundle 036.

PP-04C ergänzt mit `scripts/pyz_bootstrap.py` einen unabhängigen Standardbibliothek-
Vorabcheck und kontrollierten Importzugang. Das bisherige Wheel-Beispiel in
`runtime_bootstrap.py` bleibt für Legacy-Results erhalten; seine bestehenden
öffentlichen Beispiel-Funktionen werden nicht heimlich auf ein anderes Format
umgedeutet. Der kleine neue Helfer prüft vor jeder Codeausführung Resultmarker,
Runtime-Deskriptoren, Membertypen/-pfade, Größen, Python-Anforderung und Hashes.
Er kennzeichnet den Umfang als `runtime_descriptor_precheck`, ausdrücklich nicht
als vollständige native Referenzprüfung. Bewusste Nutzung einer vertrauten
Runtime bleibt erforderlich; ein selbst mitgelieferter Hash ist keine Signatur.

Die Entnahme schreibt genau eine geprüfte PYZ in ein neues privates Verzeichnis,
ohne pip, venv, Cache, Netz oder vollständiges Entpacken. Der Python-only-Zugang
weist bereits geladene Module anderer Herkunft zurück, erhält vorhandene Module
und behält den kontrollierten Importpfad für Lazy-Imports. Auch nach dem Import
werden Herkunft, eigene Ressourcen und erwarteter Artefakthash abgeglichen.
Der direkte CLI-Start mit und ohne `-I -S -B` benutzt denselben Core.

Synthetische Format-3-Runtimefixtures dienen hier ausschließlich dem Bootstrap-
Vorabcheck. Ihr Vorhandensein aktiviert keinen Writer und behauptet keine native
Format-3-Lesefähigkeit. Die reale gebaute PYZ packt/prüft gültige Bestandsreferenzen
in einem frischen Prozess; vollständiger neuer Result-Reader folgt PP-05A.
PP-05B integriert den geprüften minimalen Bootstrap vollständig in die tatsächlich
mitgelieferte Anleitung, vor dem verpflichtenden E-10-Gate der Writerumschaltung.
Resultgenerierende Core-Parität und drei neue Generationen bleiben PP-06-Gates.

### 1.17 PP-04C bestätigt; PP-05A / Bundle 037

Result `patchharbor-apply_Result_232439_1007_4e70d8.zip`, SHA-256
`f4762f5f2e5f2e94bbe347b9584e9104502a738dc7d19c03a42899f09e7a46ab`, bestätigt den tatsächlichen PP-04C-Commit
`d13709e8ccb9e4b45bd126fcb41829f784270861`, normalen Push und sauberen Baum. Das vollständige parallele Gate
bestand mit 2859 bestandenen Tests und 8 Skips.
Dieses Result liefert alle vier vollständigen Bindungswerte für Bundle 037.

PP-05A erweitert die gemeinsame vollständige Referenzprüfung auf Result 1/2/3.
Ein getrennter reiner Datenreader prüft den geschlossenen Runtime-2-/PYZ-Vertrag,
beide übereinstimmenden Deskriptoren, ganze kanonische PYZ, Profil, Rezept und
Ressourcenhashes, Version/Herkunft, Capabilities und das gemeinsame Bytebudget.
Das neue unveränderliche Faktenobjekt verwendet `artifact`; das alte Wheel-
Faktenobjekt und sein Datenvertrag bleiben unverändert. Beschriebener Code wird
beim Prüfen niemals importiert oder ausgeführt.

Format 2/3 verlangt weiterhin passive Handoff-Daten. `unavailable` ist ein
gekennzeichneter Diagnosezustand mit Runwarnung und ohne Artefaktbehauptungen.
Der private Repository-Diagnosefallback darf auch bei Format 3 ausschließlich
`runtime/` ausnehmen. Alle Snapshot-/Binding-/Loganforderungen bleiben erhalten;
`pack` und vollständiges `validate` benutzen immer den strikten Reader.
Öffentliche API-Signaturen, Prüfscopes und Fehlerkategorien ändern sich nicht.

`tests/test_result_format3.py` deckt alle Runtimezustände und Fehler-/Dry-Run-
Varianten, geschlossene Schemata, bool/float-Fallen, falsche Metadaten und
Inventare, exakte gemeinsame Budgets, Unveränderlichkeit und striktes Packen ab.
Die eigentliche Writerproduktion bleibt Format 2. Vollständige Verbraucher-
und Frozen-Legacy-Nachweise sowie die eingebettete Anleitung folgen PP-05B;
Writeraktivierung und erste eigene E-10-Durchstiche bleiben PP-06 vorbehalten.
Result-Sync-/CIFS-/Retry-/Hashpolitik bleibt unverändert.

Beim Review dieses Eingabepfads wurde außerdem eine kleine PP-04C-Lücke behoben:
der Bootstrap prüft Spezialdateien jetzt vor dem Open und verwendet unter POSIX
zusätzlich Nonblocking, damit ein ausgetauschter FIFO nicht beim Öffnen hängen
bleibt. Ein kontrollierter FIFO-Test prüft die frühe Ablehnung. Keine Änderung
an Produkt-Result-Retries, keine zusätzliche Planposition.

### 1.18 PP-05A bestätigt; PP-05B / Bundle 038

Result `patchharbor-apply_Result_233502_1007_366a9b.zip`, SHA-256
`e21da28fc922efad8520a7f540121bebfec99626ed8285bbb266c6ef486d00a5`, bestätigt den tatsächlichen PP-05A-Commit
`f892ae6aaaeebcabb83baf25997799d259b63e6f`, normalen Push und sauberen Baum. Das vollständige parallele Gate
bestand mit 2939 bestandenen Tests und 8 Skips.
Dieses Result liefert alle vier vollständigen Bindungswerte für Bundle 038.

Der Reader-first-Zwischenstand integriert sämtliche Result-Verbraucher durch
ihren vorhandenen gemeinsamen vollständigen Reader. Klassifikation bleibt ein
Typhinweis, Archivierung und Recovery verlangen vollständige Runtime-, Snapshot-,
Binding-, Run- und lokale Erfolgsnachweise. Neue E2E-Fälle führen echte Scan- und
Recoveryprozesse aus: gültige überholte Format-3-Erfolge dürfen archiviert werden;
unavailable, beschädigte und zukünftige Results sowie standalone PYZ bleiben
unverändert und werden nie als Patch gestartet. Auch Unicode-Snapshotpfade und
vollständige Publikationsverifikation werden mit Format 3 geprüft.

Die eingefrorene Format-1-Grenze bleibt unverändert. Zusätzlich enthält
`tests/fixtures/result_format2` eine vollständige historische 1.2.1-Laufzeit aus
dem geprüften Result 036, mit vollständiger Quell-Result-SHA, Wheel-SHA und
Originalmetadaten. Kein aktuelles Modul wird in diese historische Installation
kopiert. Kindprozesse belegen geladene Modulbytes; beide Altleser müssen neue
Format-3-Results konservativ liegen lassen.

Die kanonische Root-Anleitung enthält jetzt den tatsächlich ausführbaren
stdlib-only Bootstrap. Eine neue Fixture-Vorstufe von E-10 entnimmt ausschließlich
den eingebetteten Code aus der gebauten Ressource, startet ihn ohne Core/Checkout
in einem frischen Prozess und führt Python-only pack/inspect/validate gegen genau
dasselbe Format-3-Result aus. Eine beschädigte Snapshotdatei wird nach erfolgreichem
Runtime-Vorcheck nativ abgelehnt; der Vorcheck behauptet keine Vollvalidierung.
Der Bootstrap prüft geschlossene Metadaten, genaue Capabilities und Profilwerte,
verweigert zukünftige Formate und Herkunftskonflikte. Der Legacy-Wheel-Helfer
kennzeichnet Format 3 ausdrücklich für den PYZ-Weg, statt Wheel-Felder umzudeuten.

Fachlicher Anweisungsreview: Der ausdrücklich aktive Featureplan wählt weiterhin
beide gemeinsam geltenden Spezifikationen. Fehlende Normteile und echte Konkurrenz
bleiben blockierend; die unveränderte Paketversion reaktiviert keinen alten Plan.
Der Format-2-Weg ist während dieser Übergangsproduktion weiterhin vollständig
vorhanden. Keine Tests auf Prosa, Layout oder Farben; getestet wird ausführbarer
Bootstrapcode mit seinen tatsächlichen Operationen und Fehlergrenzen.

Der Writer bleibt Format 2. Die eigene produktive E-10-Erstnutzung, dreifache
PYZ-Result-Reproduktion und Core-Parität bleiben vor Freigabe PP-06B fällig.
Result-Publikationspolitik und Pack-No-retry bleiben getrennt und unverändert.

### 1.19 PP-05B bestätigt; PP-06A / Bundle 039

Result `patchharbor-apply_Result_234637_1007_eda9b5.zip`, SHA-256
`7c055dd34959cef90ddb387be67510020b4e245f313eeee7aeccddd8e1888d16`, bestätigt den tatsächlichen PP-05B-Commit
`1da90f0c080cb6e5dd8feed5d204fbc2826e55ab`, normalen Push und sauberen Baum. Das vollständige parallele Gate
bestand mit 2968 bestandenen Tests und 8 Skips.
Dieses Result liefert alle vier vollständigen Bindungswerte für Bundle 039.

PP-06A ergänzt die gemeinsamen Result-Ressourcen für die nachfolgende sichere
Writerumschaltung. Das interne unveränderliche Payloadobjekt benutzt allgemeine
Artefaktfelder und trägt seinen expliziten Resultvertrag. Das alte Format-2-
Dokument bleibt ein Wheel-Dokument; das neue Format-3-Dokument hat `artifact`
mit Typ `pyz` und Runtime-Metadaten 2. Der Writer schreibt weiterhin denselben
vorgeprüften Dokument-/Snapshotbestand durch die vorhandene Publikationsgrenze.
Sein Budgetfallback behält jeweils das passende Format, ohne Umdeutung.

Der private PYZ-Capturepfad hält Runtime und Pflichtvorlage vor Mutation aus
Daten des tatsächlich geladenen Erzeugers fest. Bei einem defekten optionalen
Ressourceneintrag darf eine Pflichtvorlage nur anhand des geladenen Producer-IDs,
seines geschlossenen Rezepts und ihrer exakten Größe/SHA weiterverwendet werden.
Das gilt für eigene Verzeichnisse und eigene PYZ. Ein fremder Erzeuger oder
fehlendes/defektes Template bleibt ein Resultfehler. Dieses begrenzte Template-
Prüfergebnis ist ausdrücklich keine vollständige Runtime- oder Resultvalidierung.

Neue Tests üben den vorbereiteten Pfad über reale registrierte Fixture-Repositories
und die vorhandenen bundle/apply/dry-run/failure/Watcher-Core-Wege aus. Sie belegen
vollständige native Format-3-Lesbarkeit, Template-/Runtime-Pinning, Format-3-
Budgetfallback, Erhalt von Snapshot und tatsächlichen Fehlerlogs bei optionalen
Ausfällen sowie unveränderte Fehlerpriorität bei fehlender Pflichtvorlage.
Programmierfehler und Abbrüche werden nicht als harmloses unavailable verschluckt.

Die Auswahl in der laufenden Produktanwendung bleibt bis PP-06B ausdrücklich
Format 2. Es gibt keinen neuen Benutzerumschalter. Die Tests verwenden eine
private Capturegrenze zur Vorbereitung desselben Writers; PP-06B entfernt die
nicht mehr benötigte Übergangsproduktion und aktiviert den PYZ-Pfad gemeinsam
mit echten Installations-, Selbstupdate-, Core-Paritäts-, E-10- und dreifachen
Result-/PYZ-Roundtripnachweisen. Keine geänderte Result-Sync-/Retry-/CIFS-Politik.

### 1.20 PP-06A bestätigt; PP-06B / Bundle 040

Result `patchharbor-apply_Result_000135_1008_03307a.zip`, SHA-256
`859218dc35f6bdbe5d216cf90bb11f80b874f496a73096873b40735fc0a5909e`, bestätigt den tatsächlichen PP-06A-Commit
`0a806c1b2c00b8e2b3c3a6e9d03559ca9c36fa51`, normalen Push und sauberen Baum. Das vollständige parallele Gate
bestand mit 2997 bestandenen Tests und 8 Skips.
Dieses Result liefert alle vier vollständigen Bindungswerte für Bundle 040.

PP-06B aktiviert atomar den vorbereiteten request-lokalen PYZ-Pfad für alle
regulären Resultproduzenten. Es gibt nur noch ein produktives Runtime-2-Payload
mit genau einer PYZ oder begründetem unavailable; die interne Übergangsauswahl
und die produktive Wheel-Erzeugung entfallen. Der normale Build bereitet nur
noch das eigene PYZ-Profil vor. Wheel/sdist als normale Installationsartefakte
und der separat installierte Watcher bleiben erhalten. Alte Result-1/2-Reader
und explizite historische Daten-/Bootstrapfixtures werden nicht umgedeutet.

Die Gates sind Teil dieses auslieferbaren Stands, nicht auf PP-07 verschoben:

- `tests/test_pyz_result_e2e.py`: erste Resultproduktion aus echter normaler
  Installation, Bootstrap ausschließlich aus der eigenen eingebetteten Root-
  Anleitung, frischer Python-only-Prozess ohne Checkout/Installation des Cores,
  pack/inspect/validate gegen genau diese unveränderte Referenz, danach regulärer
  Apply vollständiger Dateien, Diff-Payloads und gemischter Pakete. Die gleiche
  PYZ benutzt Context, Registry/Konfiguration, bundle und fs run; ihr eigenes
  Verzeichnis bleibt dabei schreibgeschützt.
- `tests/test_runtime_packaging.py`: Wheel-/Source-/sdist-Installation ohne
  erhaltene Buildquellen/Caches, danach drei echte Result-/PYZ-Generationen.
  Folgegenerationen starten nur die vorherige Result-PYZ ohne Neuinstallation.
  Größe, SHA und Bytes bleiben gleich; Messwerte werden pro Generation erfasst.
- Bestehende tatsächliche Self-update-Tests prüfen jetzt PYZ-Pinning bei Erfolg
  und Fehler nach einer Neuinstallation derselben Version und neuem Commit.
- Bestehende Writer-/Publikations-/CIFS-Fault-Tests prüfen den neuen Format-3-
  Produktionsvertrag. Ergänzende Zustandsfälle prüfen embedded/unavailable,
  typisierte Wartewiederholung, harte Integritätsablehnung ohne Retry und die
  gebundene SHA bis zur echten Veröffentlichung. Kein realer CIFS-Nachweis wird
  aus diesen Simulationen abgeleitet.
- Die installierte Watcher-Worker-Prüfung verlangt einen tatsächlichen Format-3-
  Output mit genau einer PYZ. Die PYZ selbst enthält keinen Watcher.

Eine bisher formatgebundene Testkennung wird ausdrücklich von
`test_mixed_exchange_selects_only_real_patch_and_writer_produces_format2` zu
`test_mixed_exchange_selects_only_real_patch_and_writer_produces_current_format`
umbenannt; ihr realer Apply-/Auswahltest bleibt erhalten und prüft jetzt Format 3.
Die lokale Nachweisprüfung bildet genau diese Kennung ab, ohne Testfälle zu verlieren.

Alle unmittelbar betroffenen Bootstrap-, API-, Format-, Produktions- und
Artefakttexte sind angepasst. Die eigentliche eingebettete Bootstrapimplementierung
stammt unverändert aus dem bereits geprüften PP-05B-Vertrag. Der übergreifende
Redaktions-/Anforderungsabgleich folgt PP-07/08. Beide Normdateien bleiben bytegleich.

Der extern installierte globale Watcher bleibt unverändert und kann weiterhin
Result 2 aus seinem eigenen alten Core liefern. Das ist eine gültige Referenz
für den Zwei-Klon-Workflow, aber kein Upgradebeleg für die globale Installation.
Neue Produktversion, manuell gestartete native CI und reale CIFS-Abnahme bleiben
separate Abschlussvoraussetzungen. Kein Tag, Release oder Hostupgrade.

### 1.21 PP-06B bestätigt; PP-07 / Bundle 041

Result `patchharbor-apply_Result_002417_1008_e88eaf.zip`, SHA-256
`a9736e58035b18df364cda19ddfb76d05b2eb85d0130b0b7db5450e14c11fa0b`, bestätigt tatsächlichen Apply, sauberen Baum und normalen Push
von Commit `f3edbeb7216101f2435a2752f1168562097673f3`. Sein vollständiges paralleles Gate meldet
3004 bestandene Tests und 8 Skips. Dieses Result
liefert die vollständige Bindung für das nächste Bundle.

PP-07 bereinigt überholte aktive Wheel-/Reader-first- und Pollinghinweise, erhält
historische Verträge als solche und grenzt die projektspezifische Test-/CI-Policy
von anderen Zielrepositorys ab. Die Dokumentationsmatrix und die fachlichen
E-08/E-09-Reviews stehen in `documentation-review.md`. Beide Normdateien bleiben
unverändert; kein neuer Produktvertrag wird aus einem Beispiel abgeleitet.

`docs/pack-examples.md` und `tests/test_pack_examples.py` behandeln vollständige
Dateien, Diff, Mischpakete, Diagnose ohne Commit und formal gültige kaputte Shell-
Syntax über installierte CLI, PYZ-CLI und PYZ-API. Tatsächlicher Apply beweist
Payload-vor-Entrypoint, sichtbare Diagnoseausgabe, fehlende implizite Commits und
reale Fehler. Statische Validierung wird nicht als Skripterfolg ausgegeben.
Es werden keine Prosa-/Layouttests eingeführt.

Chat- und API-Ressourcen gehören zum Artefakt. Deshalb werden auf diesem Stand
Artefakte neu gebaut und die volle parallele Suite einschließlich eigener
E-10-Anleitung, drei Result-/PYZ-Generationen, Installation und Self-update erneut
geprüft. Der PP-06B-Nachweis ist kein Nachweis für geänderte Artefaktbytes.
Native Windows-/Python-3.12-/CIFS-Abnahme, Versionsentscheidung und manuell vom
Nutzer zu startende CI bleiben PP-08B zugeordnet. Kein automatischer Dispatch.

## 2. Architektur und unveränderliche Grenzen

### 2.1 Produktumfang

**PYZ:** Die neue Result-Runtime enthält den gemeinsamen PatchHarbor-Core mit CLI, API und allen vorgesehenen Core-Kommandos. Sie enthält **kein `patchharbor_watcher`**, keine Watcher-Worker-Orchestrierung und keine Dienstinstallation. Neutrale Core-Verträge wie `patchharbor.watch_contract` bleiben zulässig. Der Watcher bleibt Teil der normalen Installation und wird als Bestandsfunktion regressionstestet.

**`pack`:** Eine explizite Result-Referenz und ein ausdrücklich vorbereiteter Inhaltsordner werden zu genau einem Patchformat-1-Paket. CLI und PYZ delegieren auf dieselbe öffentliche Funktion `api.pack_patch(...)`. Kein Live-Repositorymodus, kein Diff-Generator, kein automatisch geschriebener Entrypoint, kein automatischer Apply, Commit, Push oder Versand.

```text
installierte CLI ─┐
PYZ-CLI ──────────┼── öffentliche API ── gemeinsame Fachlogik
Python-Sitzung ───┘

bundle: Repository → Result mit PYZ
pack:   vorbereitete Inhalte + geprüftes Result → geprüftes Patch-ZIP
```

### 2.2 Nicht verhandelbare Integrationsgrenzen

1. **Bestehende Apply-Semantik bleibt erhalten.** Nutzdateien werden vor dem Entrypoint an ihre relativen Repositorypfade geschrieben. `payload/` ist kein privater Stagingbereich. Ein Diff wird nur durch den vorbereiteten Entrypoint angewendet. Handoff-Dateien bleiben passiv.
2. **Eine Referenzerfassung ist eine Wahrheit.** Bindung, Suffix, Zielumgebung und Referenzhash müssen aus derselben stabil erfassten und vollständig geprüften Referenz stammen. Kein `expected_*` statt tatsächlichem Kontext und kein schwächerer Diagnosefallback in `pack`.
3. **Nur tatsächlich validierte Bytes werden veröffentlicht.** No-replace für `pack`, vollständige Endvalidierung und Identitäts-/Hashbindung bis zur Publikation. Kein Schreiben unter dem endgültigen Namen während des Bauens.
4. **Result-Publikation bleibt ein anderer Vertrag.** Deren bestehendes Replace-, Sync-, endliches CIFS-Retry-, Hash- und Diagnoseverhalten wird nicht durch Pack-No-replace oder dessen fehlende Stabilitäts-Retries ersetzt.
5. **Ein erfolgreicher Pack-Vorgang bleibt nach Veröffentlichung erfolgreich.** Ein nachlaufender Cleanup-Fehler ergibt vollständige Erfolgsdaten mit Warnung; Ausgabeprobleme der CLI werden separat behandelt. Kein erneutes Öffnen der finalen Datei als Voraussetzung der Erfolgsantwort.
6. **Keine doppelten fachlichen Prüfer.** Bestehende Pfad-, Modus-, Entrypoint-, Manifest-, Ressourcen- und Bindungsregeln wiederverwenden. Fehlerkategorien bleiben auch bei frühen Prüfungen erhalten.
7. **Reader und Bootstrap vor Writer.** Format 3 darf nicht produktiv ausgegeben werden, bevor seine Verbraucher, der Runtime-Provider und die tatsächlich eingebettete Anleitung funktionieren. `E-10` ist Gate der Umschaltung selbst.
8. **Keine neue Nutzerinfrastruktur.** Kein Zählerdienst, kein zusätzlicher Runtime-Buildschritt für den Nutzer, keine Registry für Pläne und keine neue CI-Automatik. Normale Installation weiterhin Wheel/sdist; genau eine PYZ als Runtime neuer Results.

### 2.3 Konkrete Änderungsstellen im analysierten Stand

Die bestehenden Pfade wurden im Snapshot geprüft. Neue Modulnamen sind Vorschläge zur lokalen Zuständigkeit, keine zusätzliche öffentliche Schnittstelle. Eine nachvollziehbare kleine Umbenennung ist zulässig; ein neues allgemeines Framework ist nicht geplant.

| Aufgabe | Vorhandene Ansatzpunkte | Geplante Ergänzung / Verantwortung |
|---|---|---|
| Öffentliche Funktion und Ergebnis | `src/patchharbor/api.py`, `api_types.py`, `patch_inspection.py` | `pack_patch` und unveränderliches `PatchPackResult`; bestehende API-Signaturen erhalten |
| CLI und strukturierte Ausgabe | `src/patchharbor/cli.py`, `inspection_output.py`, vorhandene Ausgabe-/Fehleradapter | Unterkommando, Parameterprüfung und Pack-JSON; keine Geschäftslogik im Parser |
| Stabile Referenzfakten | `src/patchharbor/result_reader.py`, `result_runtime.py` | Interner erfasster Referenzwert mit geprüftem Handoff/Suffix; bisherigen `read_result_reference`-Vertrag erhalten |
| Paketregeln | `patch_manifest.py`, `patch_package.py`, `patch_inspection.py`, `bundle_paths.py`, `payload_modes.py`, `resource_policy.py` | Wiederverwendung; etwa neues `patch_pack.py` als schmale Orchestrierung |
| Inhaltsinventar | `platform/filesystem.py`, `platform/file_handles.py`, bestehende Pfadadapter | Begrenzt erfassender Scanner, etwa `pack_sources.py`; No-follow, Identität, Modi und Budgets |
| Handoff und Name | `bundle_handoff.py`, `chat_instructions.py`, `bundle_names.py`, Konfigurations-Suffixvalidator | Zielmetadaten aus Referenz und reine Renderingfunktionen, keine neue Hostabfrage |
| Pack-Publikation | Bestehende Plattformadapter; Resultmechanik in `result_bundle_publication.py` nur als geprüfte Orientierung | Schmaler No-replace-Adapter, etwa `pack_publication.py`; kein Result-Retry-Durchgriff |
| PYZ-Datenprofil | `runtime_wheel.py` bleibt Legacy-Leser | Neues stdlib-basiertes `runtime_pyz.py`: Rezept, Identität, Inventar, kanonischer Materializer und reiner Reader |
| Build und Installation | `build_backend.py`, `scripts/build_release.py`, `pyproject.toml`, `MANIFEST.in` | Vorbereitete PYZ-Ressourcen; saubere Wheel-/sdist-Inventare und Releaseaudit |
| Eigene Ressourcen | `runtime_artifact.py`, `result_resources.py`, `chat_instructions.py` | ZIP-taugliche, herkunftsgebundene Ressourcen und request-lokales Pinning |
| Result und Verbraucher | `result_bundle_writer.py`, `result_reader.py`, `result_verification.py`, Exchange-/Archiv-/Recovery-Module | Getrennte Formate 1/2/3, korrekte vollständige Prüf- und Nachweisgrenzen |
| Bootstrap | `scripts/runtime_bootstrap.py`, `CHAT_INSTRUCTIONS.md`, `docs/runtime-bootstrap.md` | Vorprüfung ohne Core-Installation, PYZ-Start, kontrollierter In-Process-Zugang und Legacyweg |

Ein Build darf Code aus seinem eindeutig verankerten Quellstand laden. Ein laufender `bundle`-/Apply-Auftrag darf dagegen kein Buildbackend oder Installationswerkzeug starten. Die PYZ-Reproduktion aus vorbereiteten Ressourcen ist eine Datenoperation.

## 3. Arbeitspakete, Abhängigkeiten und sichere Zwischenstände

### 3.1 Die neun Arbeitspakete der Ergänzung bleiben erhalten

| Arbeitspaket | Zweck | Vorgesehene Commit-Schritte | Fachliche Voraussetzung |
|---|---|---|---|
| PP-00 | Vertrags-, Status- und Ausgangsabgleich | PP-00 | Aktueller Quell-/Resultstand, beide Spezifikationen |
| PP-01 | Gemeinsame stabile Referenz-/Pack-Bausteine | PP-01 | PP-00 |
| PP-02 | Pack-Core und öffentliche API | PP-02A bis PP-02C | PP-01 |
| PP-03 | Pack-CLI und erste Nutzerdokumentation | PP-03 | PP-02 |
| PP-04 | PYZ-Profil, ZIP-Ressourcen, Core-Start und minimaler Bootstrap | PP-04A bis PP-04C | PP-00; Pack-Parität nach PP-03 |
| PP-05 | Result-3-Reader, alle Verbraucher und Bootstrapintegration | PP-05A, PP-05B | PP-01 und funktionsfähiges PYZ-Profil aus PP-04 |
| PP-06 | Runtime-Provider und gemeinsame Writerumschaltung | PP-06A, PP-06B | PP-03, benötigte PP-04-Bausteine und PP-05 samt Bootstrap |
| PP-07 | Übergreifender Chat-/Dokumentationsabschluss | PP-07 | PP-03 bis PP-06 |
| PP-08 | Gesamtregression, finale Artefakte und Freigabenachweise | PP-08A, PP-08B | Alle vorherigen Arbeitspakete |

Die lineare Standardreihenfolge in Abschnitt 4 verhindert unnötige gleichzeitige Änderungen an Build, Readern und Publikation. PYZ-Profil-/Reader-Arbeit darf nach `PP-00` parallel vorbereitet werden, sofern die angegebenen Eingangsvoraussetzungen, tatsächlichen Commitzustände und Gates erhalten bleiben. Das bedeutet keine Hintergrundarbeit oder zusätzliche Dienste.

### 3.2 Erlaubte Zwischenstände

| Zustand | Bereits nutzbar | Was noch ausdrücklich nicht zugesagt wird |
|---|---|---|
| Nach PP-01 | Bestehende Prüfer und Resultformat 2 unverändert | Noch kein öffentliches `pack` |
| Nach PP-03 | Vollständiges installiertes `pack` gegen gültige Legacy-Referenzen | Noch keine neue Runtime im produktiven Result |
| Nach PP-04-Vorbereitung | Gebauter, noch nicht als Resultstandard aktivierter PYZ-Kandidat; Core-Import, `inspect`, `validate`, `pack` | Vollständiger Runtime-Roundtrip erst mit PP-06; kein vorgetäuschter Abschluss der resultproduzierenden PYZ-Wege |
| Nach PP-05 | Neue Leser für 1/2/3 und Bootstrap mit neuen Fixtures; Produktion weiterhin Format 2 | Kein eigenmächtiger Writerwechsel |
| Nach PP-06B | Gemeinsame Produktion Format 3, funktionierende eigene Startanleitung, Pack-Durchstich und identische PYZ-Reproduktion | Noch keine Freigabe ohne erforderliche native/CI-/CIFS-Nachweise |
| Nach PP-08 | Konkreter getesteter Commit und konkrete Artefakte erfüllen die vollständige Abnahme | Keine Freigabe späterer ungetesteter Änderungen |

**Wichtige Kopplung:** Vollständige Funktionsparität von `bundle`, `apply` und `fs run` aus der PYZ schließt deren Result-Erzeugung ein. Diese End-to-End-Abnahme kann erst mit den Provider-/Writer-Bausteinen vollständig erfolgen. Die Vorbereitungscommits in PP-04 dürfen deshalb grün für ihren begrenzten Umfang sein, aber nicht die vollständige PP-04-/PYZ-Abnahme behaupten. Das gemeinsame Abschlussgate für diese Wege liegt spätestens in PP-06B; PP-04 bleibt bis zu diesem Nachweis fachlich teilweise offen. Dies konkretisiert die zulässige Kopplung nach `PLAN-03`, statt eine funktional unmögliche frühe Vollfreigabe zu verlangen.

## 4. Vorgeschlagene Commitfolge

Die folgende Folge ist die anfängliche prüfbare Zerlegung. Sie ist **keine Verpflichtung zu 16 Patch-ZIPs**. Kleine sicher zusammengehörige Schritte dürfen mit dokumentierter Plananpassung zusammengelegt werden. Bei Split oder Zusammenlegung werden Positionen, Gesamtzahl, Messages und Nachweiszuordnung vor der betroffenen Auslieferung aktualisiert. Kein nur nominelles Zerlegen eines bereits vollständig installierten Endzustands.

PP-00 ist durch Bundle 025 abgeschlossen. PP-01 steht auf **committed; Regression und Reparatur-Endgates offen (Bundle 028 / PP-01-FIX2)**; die übrigen Schritte bleiben **geplant**. Die Message ist die vorgeschlagene tatsächliche Git-Commitmessage. Die API-/Writer-Funktionen werden erst in den dafür genannten sicheren vollständigen Schritten öffentlich beziehungsweise produktiv aktiviert.

| Position | ID | Arbeitspaket | Abhängigkeit | Vorgeschlagene Commitmessage | Status |
|---:|---|---|---|---|---|
| 1/16 | **PP-00** | PP-00 | Ausgangsabgleich | `docs(plan): establish PYZ and pack implementation baseline [PP-00]` | angewendet: 7a28bbc2189cdb2a78590e62a45e4d96b0ff893d; CI 37635401106 grün |
| 2/16 | **PP-01** | PP-01 | PP-00 | `refactor(reference): share verified reference facts for packing [PP-01]` | abgenommen; Reparaturcommit e34a81c517d66c079f85cc43033b233f8c9f90a8 durch Result 030 bestätigt |
| 3/16 | **PP-02A** | PP-02 | PP-01 | `feat(pack): capture bounded immutable package inputs [PP-02A]` | Bundle 031 tatsächlich angewendet/gepusht; Linux-Gate bestätigt |
| 4/16 | **PP-02B** | PP-02 | PP-02A | `feat(pack): build and publish validated packages through the public API [PP-02BC]` | Bundle 032 tatsächlich angewendet/gepusht, gemeinsam mit PP-02C |
| 5/16 | **PP-02C** | PP-02 | PP-02B | `feat(pack): build and publish validated packages through the public API [PP-02BC]` | Bundle 032 tatsächlich angewendet/gepusht, gemeinsam mit PP-02B |
| 6/16 | **PP-03** | PP-03 | PP-02C | `feat(cli): expose pack with validated output and mode options [PP-03]` | Bundle 033 tatsächlich angewendet/gepusht |
| 7/16 | **PP-04A** | PP-04 | PP-03 | `feat(runtime): define canonical core-only PYZ artifacts [PP-04A]` | Bundle 034 tatsächlich angewendet/gepusht |
| 8/16 | **PP-04B** | PP-04 | PP-04A | `refactor(runtime): load producer resources from directories or PYZ [PP-04B]` | Bundle 035 tatsächlich angewendet/gepusht |
| 9/16 | **PP-04C** | PP-04 | PP-04B | `feat(runtime): launch the shared core directly from PYZ [PP-04C]` | Bundle 036 tatsächlich angewendet/gepusht |
| 10/16 | **PP-05A** | PP-05 | PP-04C | `feat(result): read PYZ runtime metadata and Result format 3 [PP-05A]` | Bundle 037 tatsächlich angewendet/gepusht |
| 11/16 | **PP-05B** | PP-05 | PP-05A | `feat(result): integrate format 3 consumers before writer activation [PP-05B]` | Bundle 038 tatsächlich angewendet/gepusht |
| 12/16 | **PP-06A** | PP-06 | PP-05B | `feat(runtime): pin reproducible PYZ resources for Result production [PP-06A]` | Bundle 039 tatsächlich angewendet/gepusht |
| 13/16 | **PP-06B** | PP-06 | PP-06A | `feat(result): ship PYZ runtimes with a working bootstrap [PP-06B]` | Bundle 040 tatsächlich angewendet/gepusht |
| 14/16 | **PP-07** | PP-07 | PP-06B | `docs(runtime): complete PYZ and pack workflows and compatibility guidance [PP-07]` | Bundle 041 vorbereitet; tatsächlicher Apply offen |
| 15/16 | **PP-08A** | PP-08 | PP-07 | `test(runtime): complete cross-platform PYZ and pack acceptance coverage [PP-08A]` | geplant |
| 16/16 | **PP-08B** | PP-08 | PP-08A | `chore(release): audit PYZ and pack artifacts and acceptance readiness [PP-08B]` | geplant |


Die Initialfolge folgt bereits einer topologischen Ordnung. Querschnittliche Anforderungen wie API-/CLI-Parität und PYZ-Resultproduktion erhalten zusätzlich die Abschlussgates aus Abschnitt 6. Ein bestandener früher Unit-Test ersetzt nicht deren späteren Artefaktdurchstich.

**W → R → C:** Jeder fachliche Abschnitt wird zunächst als kleinste sichere durchgängige Funktion bearbeitet, mit Robustheits-/Grenzfällen abgesichert und anschließend auf sinnvolle Bereinigung geprüft. Sicherheitsprüfungen gehören schon zum ersten nutzbaren Zustand. Tatsächlich vorgeschriebene getrennte W/R/C-Zustände werden real hergestellt und nach ihren Tests committet, nicht nachträglich aus einem Endzustand simuliert. Die explizite Erlaubnis aus `PLAN-02`, kleine sichere Änderungen zusammenzulegen und leere Cleanup-Commits zu vermeiden, bleibt erhalten. Ein neuer Schnitt wird vor Auslieferung nachvollziehbar im Plan festgehalten.

## 5. Detaillierte Umsetzungsschritte

Die folgenden Testangaben sind **zu erbringende Nachweise**, keine Ergebnisse bereits ausgeführter Produkttests. Alle hier neu vorgeschlagenen Test-/Modulnamen sind bis zu ihrer Implementierung als neu zu behandeln. Gezielte Tests ergänzen die unverändert geltenden Vollsuite-Gates; sie ersetzen diese nicht.

### PP-00 – Vertrag und tatsächlichen Ausgangsstand festhalten

**Normbezug:** GOV-01–04, PLAN-01–04, TEST-04/05/07, CHAT-06.
**Voraussetzung:** aktueller bereitgestellter Ausgangsstand.
**Betroffene Stellen:** Beide Spezifikationen, dieser Plan, `README.md`, `CHAT_INSTRUCTIONS.md`, `spec/SPECIFICATION_CHANGELOG.md`; vorhandene Watcher-/CIFS-Pläne und Test-/CI-Regeln lesen.

**Umsetzung:** Aktuelles Result und Arbeitsstand abgleichen, neue Änderungen gegenüber dem hier gebundenen Snapshot erfassen und keine alten Bindungswerte fest einbauen. Den ausdrücklich aktiven Plan und beide Normpfade in den bestehenden Dokumentverweisen einordnen. Vorhandene abgeschlossene Pläne nicht umschreiben. Aktuelle Bundle-Zählung, letzte tatsächlich geprüfte CI, offene CIFS-/Windows-Nachweise und verfügbare lokale Regeln aufnehmen. Die schon vorhandenen 120 Minuten am Acceptance-Job erhalten statt erneut als unerledigtes Feature zu planen. Ziel-Releaseversion und deren Festlegungszuständigkeit dokumentieren; eine noch offene Entscheidung nicht durch eine erfundene Versionsnummer ersetzen. Requirement-/Test-Zuordnung dieses Plans gegen den aktuellen Stand bestätigen.

**Prüfungen:** Fachlicher Review E-09 und sichere Paket-/Referenz-/Scopeprüfung. Für Bundle 024 ersetzt die ausdrückliche Ausnahme aus Abschnitt 1.5 sämtliche lokalen Produkttest-Gates: kein Test im Apply; nach dem einen Commit und Push automatisch die vollständige bestehende parallele CI. Keine wortgleichen Texttests hinzufügen.

**Dokumentation:** Ergänzung Revision 2 unverändert integrieren, Planverweis und Changelog aufnehmen. Alte Statusangaben sichtbar einordnen, nicht als Freigabe kopieren.

**Abschlussgate:** Der gemeinsame Normsatz und aktive Plan sind integriert; tatsächlicher Commit/Push und vollständige erfolgreiche parallele CI der PP-00-Fortsetzung (Bundle 025) sind im Result belegt. Keine lokale Testsuite ist dafür gefordert oder als bestanden auszugeben. Fehlende Alt-Nachweise bleiben offen. Ein vorbereiteter Dateistand ist noch kein Apply-Nachweis.

### PP-01 – Eine stabile, vollständig geprüfte Referenzerfassung wiederverwenden

**Normbezug:** ARCH-01, PACK-06/07, GOV-04, CHECK-01/02, MIG-05/06.
**Voraussetzung:** PP-00.
**Betroffene Stellen:** `result_reader.py`, `patch_inspection.py`, `bundle_handoff.py`, `json_document.py`; bestehende sichere Reader und Publikationsadapter.

**Umsetzung:** Einen schmalen internen erfassten Referenzwert vorsehen: geprüfte ResultFacts, Referenzhash, benötigte unveränderliche passive Kontext-/Environmentdaten und Suffix aus derselben Byteerfassung. Der aktuelle ResultFacts-Wert enthält nicht alle für pack benötigten Handoff-Daten; deshalb keine zweite ungeschützte ZIP-Lesestrecke ergänzen. Öffentliche Ergebnisse und den bisherigen read_result_reference-Aufruf kompatibel halten. Einen gemeinsamen internen Validierungsweg über diese erfassten Fakten ermöglichen, während die öffentliche API weiterhin ausdrücklich Dateipfade akzeptiert. Bestehende Pfad-/Modus-/Interpreterprüfer und reine Renderer auffinden und unverändert wiederverwenden. Result-Retry-/Replace-Zuständigkeiten markieren; hier noch keinen globalen Publikationsumbau durchführen.

**Prüfungen:** Vorhandene `test_patch_inspection*`, `test_reference_validation*`, `test_result_format2`, `test_result_verification` und `test_result_bundle_publication`; P-05–P-07 und S-04 als Vorbereitungsfälle. Keine Shell-, Git- oder Registry-Nutzung durch den neuen Referenzpfad.

**Dokumentation:** Interne Zuständigkeiten in Runtime-/Pack-Dokumentation kurz beschreiben; bestehender öffentlicher inspect-/validate-Vertrag bleibt identisch.

**Abschlussgate:** Alle bisherigen gültigen/ungültigen Referenzfälle und ihre Fehlerklassen bleiben gleich. Getrennte Quellenstände, Hostpfadauflösung und schwächerer Diagnosefallback sind ausgeschlossen; Writer weiterhin Format 2.

### PP-02A – Begrenzte sichere Inhaltsaufnahme und Modusprüfung

**Normbezug:** PACK-02/08–13/21–23, SEM-01/02, TEST-03.
**Voraussetzung:** PP-01.
**Betroffene Stellen:** Neuer schmaler interner Scanner, z. B. `pack_sources.py`; `platform/filesystem.py`, `platform/file_handles.py`, `bundle_paths.py`, `payload_modes.py`, `resource_policy.py`.

**Umsetzung:** Inhaltswurzel einmal kontrolliert auflösen. Den expliziten Baum vollständig, aber mit Knotenzähler erfassen; leere Verzeichnisse zusammengefasst melden. Keine .gitignore-Filter und kein stilles Weglassen. Reservierte Eingaben, unsichere Pfade, case-/Präfixkollisionen und Sonderdateien ablehnen. Sichere Datei-/Verzeichnisidentitäten über Öffnen und Lesen erhalten, unterhalb der Wurzel keine Symlink-/Reparse-Umleitungen; erkennbare Quellhardlinks ablehnen. Begrenzte Byteerfassung oder Spooling nur im später ausdrücklich freigegebenen Ausgabebereich; vor Finalisierung erneut Inventarkonsistenz prüfen. Modi standardmäßig 0644, explizite geprüfte Anforderungen separat erfassen. Entrypoint ausschließlich statisch prüfen; keine installierte Shell verlangen. Noch keine unvollständige öffentliche Pack-Funktion anbieten.

**Prüfungen:** P-08–P-11, S-01–S-06, S-14/S-15/S-17. Rennen mit kontrollierten Synchronisationspunkten; relevante Windows-Reparse-Fälle später nativ belegen. Grenztests für 10.000 Knoten, 1.000 Paketeinträge einschließlich generierter Dateien und geltende Bytebudgets; keine unkontrolliert großen Testallokationen.

**Dokumentation:** In `docs/pack.md` Inhaltsordner, explizite Auswahl, Modi, unveränderte Bytes und bekannte Snapshotgrenze beschreiben; bis zur CLI-Freigabe als vorbereitet markieren.

**Abschlussgate:** Der interne Scanner liefert nur begrenzte, geprüfte, unveränderte Eingaben oder einen kategorisierten Fehler. Er ist keine ungeschützte Alternative zum bestehenden Dateisystemadapter und veröffentlicht nichts.

### PP-02B – Paketmetadaten, Name, Handoff und ZIP-Kandidat

**Normbezug:** PACK-04/12–17, SEM-01/02, DOC-02.
**Voraussetzung:** PP-02A.
**Betroffene Stellen:** Neue Pack-Fachlogik; `patch_manifest.py`, `bundle_handoff.py`, `chat_instructions.py`, `bundle_names.py`, bestehende Suffixprüfung.

**Umsetzung:** Aus der geprüften Referenz genau das siebenfeldrige Patchformat-1-Manifest generieren. Für beide Ausgabearten eine UUID v4 und einen UTC-Zeitpunkt pro Auftrag fixieren. Automatischen Namen, Repositorynamen-Sanitizing, Legacyfallback und Suffix gemäß PACK-15 erzeugen; explizite Namen nicht umbenennen. Handoff mit der eigenen kanonischen statischen Vorlage rendern, aber alle Zielsystemdaten einschließlich ursprünglichem captured_at aus der Referenz übernehmen. Fehlende Legacywerte bleiben unbekannt. Die referenzspezifisch gerenderte alte Root-Anleitung niemals nochmals als Vorlage verwenden. Pflichtdateien und Nutzinventar in sortiertes ZIP_DEFLATED/Level-6-Format mit festen Zeitstempeln und expliziten Modi überführen. Paket-UUID, Chat-Nummer und Referenz-Run-ID getrennt halten; kein zusätzliches Manifestfeld oder Zählerzustand.

**Prüfungen:** P-01/P-02, P-05, P-10–P-15, P-17/P-18; Handoff-Limits aus S-05. E-02-Fakten zur Apply-Reihenfolge vorbereiten. Kontrollierte Metadaten statt zufälliger Zeit-/UUID-Abhängigkeiten in Tests.

**Dokumentation:** Manifest-/Handoff- und Namensbeispiele in `docs/pack.md`; Voll-Datei-, Diff-, Misch- und Diagnosefall korrekt abgrenzen.

**Abschlussgate:** Der noch interne Kandidat enthält die richtigen Bytes und Metadaten; keine Hostdatenlecks, keine Umschreibung des Entrypoints. Ein Kandidatenbau allein ist noch kein öffentliches erfolgreiches pack und keine Veröffentlichung.

### PP-02C – Endvalidierung, sichere Veröffentlichung und öffentliche Pack-API

**Normbezug:** PACK-03/04/18–23, ARCH-01, GOV-04, CHECK-01/02.
**Voraussetzung:** PP-02B.
**Betroffene Stellen:** `api.py`, `api_types.py`, neues `patch_pack.py` und gegebenenfalls `pack_publication.py`; gezielte Plattformadapter und bestehender Validator.

**Umsetzung:** Den vollständigen Requestpfad implementieren: Argumenttypen und eigenes Modusmapping, Referenz-/Vorlagenbindung, Inventar, Kandidat, eigene .partial-Datei, Flush/Close/Sync, native Endvalidierung gegen dieselbe Referenz, erneuter Hash-/Identitätsabgleich und No-replace-Publikation. Ausgabeverzeichnis muss existieren; physische Aliase zu Quelle, Referenz oder verwendeter Runtime verhindern. Geeignete exklusive Publikationsprimitive je Plattform testen; bei fehlender Unterstützung abbrechen, nie auf überschreibendes Rename oder Schreiben unter finalem Namen ausweichen. Result-Publikation nicht auf diese Politik umstellen. pack wartet bei FileChangedDuringRead nicht automatisch. Unveränderliches PatchPackResult erst mit bestätigter Veröffentlichung liefern. Cleanupfehler danach ergeben vollständigen Erfolg mit Warnung, auch ohne Observer. Alle fachlichen Daten vor dem Veröffentlichungspunkt sichern, damit ein separater Watcher die Enddatei sofort übernehmen darf. Erlaubte/unerlaubte Nebenwirkungen und Unterbrechungsphasen gezielt unterscheiden.

**Prüfungen:** Alle bis dahin API-relevanten P-/S-Fälle, besonders S-07–S-12, S-14/S-15/S-17/S-18 sowie P-16. Referenz und Quellen bleiben unverändert. Zwei gleichzeitig konkurrierende Publisher ergeben höchstens einen Gewinner. API-Aufrufe sind ohne Observer still und benötigen keine Shell/Git/Registry.

**Dokumentation:** `docs/python-api.md` mit exakter Signatur, Resulttyp, Typ-/Fachfehlern und Erfolgsschwelle; Pack-Publikationsgrenze in `docs/pack.md`.

**Abschlussgate:** Eine echte installierte Distribution kann per API vollständige sichere Pakete gegen unterstützte Results 1/2 erzeugen. Alle Publikations-/Sicherheitsprüfungen sind schon vorhanden; sie werden nicht als spätere Robustheit vertagt.

### PP-03 – Reguläres Unterkommando, JSON und manueller Pack-Durchstich

**Normbezug:** PACK-01–05/15/20/22, ARCH-01, SCOPE-04, DOC-01/02.
**Voraussetzung:** PP-02C.
**Betroffene Stellen:** `cli.py`, vorhandener Ausgabe-/JSON-Adapter, `api.py`; neue Pack-CLI-/API-Tests, README und API-Dokumentation.

**Umsetzung:** Parser auf den festgelegten Pflichtvertrag erweitern: Inhaltsordner, Referenz, Entrypoint und exakt eine Ausgabealternative. Wiederholte Modusangaben vor Mappingbildung auf Duplikate prüfen; Oktalsyntax und fachlich verbotene Modi trennen. CLI ausschließlich auf api.pack_patch delegieren. Vollständiges output_version-2-Pack-Envelope inklusive bestehendem validation_json_result serialisieren; keine gekürzten IDs und kein Prosa-stdout im JSON-Modus. Parserfehler behalten Usage 2. Nach bestätigter Veröffentlichung Ausgabefehler 7 beziehungsweise Ausgabeunterbrechung 130 getrennt behandeln; kein zweiter widersprüchlicher Envelope, kein Neubau. Beide Ausgabewege in einer regulär installierten Distribution manuell nachvollziehbar testen.

**Prüfungen:** P-03/P-04/P-12/P-13/P-16–P-18, S-12/S-15/S-16/S-18; `test_cli_api`, `test_api_contract`, neue `test_pack_cli`; parallele volle Suite. Keine Prüfung exakter Hilfetexte oder Konsolenzeilenfolgen.

**Dokumentation:** `README.md`, `docs/pack.md`, `docs/python-api.md` und funktional richtige CLI-Hilfe. Die PYZ-Anleitung darf bis zu deren Bereitstellung keine produktive Verfügbarkeit behaupten.

**Abschlussgate:** Installiertes pack ist vollständig nutzbar und verhält sich fachlich wie die API. Bestehende Kommandos und deren Ausgabeversionen bleiben kompatibel; der produktive Result-Writer bleibt Format 2.

### PP-04A – Kanonisches PYZ-Datenprofil und Build-Rezept

**Normbezug:** PYZ-03/06–09/12, SCOPE-01/03, PLAN-03.
**Voraussetzung:** PP-03.
**Betroffene Stellen:** Neues `runtime_pyz.py`, `build_backend.py`, `scripts/build_release.py`, `MANIFEST.in` und Packaging-Tests; `runtime_wheel.py` als Legacyvertrag erhalten.

**Umsetzung:** Marker/Profile/Content-ID-Verfahren und das geschlossene Rezept nach Revision 2 umsetzen. Die zyklusfreie producer_id → Identitätsdatei → content_id → Artefakthash-Ableitung exakt abbilden. Root-Einstieg aus inventarisierter pyz-main-Ressource erzeugen, ohne Interpreter-kompatibilitätsabhängigen Code vor der Versionskontrolle. Kanonischen ZIP_STORED-Writer und reinen Datenreader mit lokalen/zentralen Header- und Inventarprüfungen implementieren. Watcher, dist-info, alte generierte Wheel-Identitäten, fremde Module und rekursiv eingebettete Artefakte aus dem PYZ-Profil ausschließen, Legacy-Lesecode aber erhalten. Build erzeugt/verifiziert vorbereitete Ressourcen ohne verunreinigten Checkout. Wenn beide Profile übergangsweise vorbereitet werden, ihre Inventare und Identitäten ausdrücklich trennen; keine Hashzyklen oder doppelten Runtime-Artefakte im Result.

**Prüfungen:** Z-05/Z-08/Z-14–Z-16 sowie reproduzierbare Golden-/Mutationsvektoren. Build-/Wheel-/sdist-Inventare und gleichnamige Neubuilds prüfen. Ein Reader muss manipulierte Daten verwerfen, nicht nur den eigenen Writeroutput akzeptieren.

**Dokumentation:** `docs/runtime-artifact.md`, Builddokumentation, Lizenz-/Ressourceninventar; historische Wheel-Readerregeln nicht umdeuten.

**Abschlussgate:** Kanonischer, streng lesbarer PYZ-Kandidat lässt sich aus dem Build herstellen; kein Watcher im Profil. Normale Installation und bisherige Runtimeproduktion bleiben intakt. Noch keine Vollfreigabe resultgenerierender PYZ-Kommandos.

### PP-04B – ZIP-taugliche, herkunftsgebundene Ressourcen

**Normbezug:** PYZ-04/06/07/10, ARCH-01/03, PLAN-03.
**Voraussetzung:** PP-04A.
**Betroffene Stellen:** `chat_instructions.py`, `runtime_artifact.py`, `result_resources.py`, Ressourcenadapter und Build-Paketdaten.

**Umsetzung:** Dateisystemannahmen aus eigenen Ressourcenlesern entfernen. Derselbe verankerte Reader muss installierte Paketressourcen und ZIP-Ressourcen unterstützen, ohne auf CWD, Zielrepository oder zufällige gleichnamige Distribution auszuweichen. Eigene geladenen Identitätsliterale gegen den überprüften Ressourcensatz binden. Lizenz, API-Dokumentation, Rezept, Einstieg und statische Chat-Vorlage über diesen Pfad verfügbar machen. Lesende Prüffunktionen dürfen keine Extraktion/Schreibzugriffe erhalten; pack lädt nur seine benötigten Vorlagen. Übergang mit altem Provider bewusst kompatibel halten. Gemeinsames frühes Pinning vorbereiten; dessen vollständige Apply-Selbstupdateabnahme gehört zum Provider-Durchstich.

**Prüfungen:** Z-07/Z-08 und vorbereitende Z-10/Z-13; kaputte oder nach Start geänderte Ressourcen, fremde gleichnamige Installation, read-only-Runtimeverzeichnis. Bestehende `test_chat_contract`, `test_runtime_artifact`, `test_runtime_packaging` fachlich fortführen, nicht um neue Textassertions ergänzen.

**Dokumentation:** Ressourcenherkunft und zulässiger Entwicklungs-/unavailable-Fall in Runtime-Dokumentation; normale unveränderte Installation darf keinen neuen manuellen Vorbereitungsschritt brauchen.

**Abschlussgate:** Code und Vorlagen kommen aus derselben eigenen Distribution. Keine versteckte Pfadmaterialisierung für inspect/validate. Bisherige Wheel-Produktion funktioniert bis zur ausdrücklich vorgesehenen Umschaltung weiter.

### PP-04C – PYZ-Einstieg, Core-Import und Python-only-Bootstrap vorbereiten

**Normbezug:** PYZ-01/02/05, ARCH-02/03, CHAT-01/02/04, TEST-01.
**Voraussetzung:** PP-04B.
**Betroffene Stellen:** `__main__.py` als generiertes Artefakt, `patchharbor/_runtime/pyz-main.py`, `scripts/runtime_bootstrap.py`, kanonische `CHAT_INSTRUCTIONS.md`; isolierte Runtime-/Bootstraptests.

**Umsetzung:** Root-Einstieg direkt auf die Core-CLI führen, inklusive früher Python-3.12-Untergrenzenkontrolle. Direktaufruf und -I -S -B außerhalb des Checkouts prüfen. Alle Core-Kommandos müssen importierbar sein; einzelne Repositoryfunktionen benötigen weiterhin Git/Registry/Interpreter. Statische Chat-Werkzeuge und pack ohne Git/Shell testen. Einen kontrollierten In-Process-Zugang mit vorheriger Herkunftsprüfung vorbereiten; vorhandene fremde patchharbor-Module nicht durch sys.modules-Löschen austauschen. Bootstrap-Vorcheck allein mit Standardbibliothek, ohne installierten Core; sichere Einzelextraktion statt extractall. Für Format 3 zunächst Testartefakte/Fixtures verwenden, bis der neue vollständige Reader integriert ist. Die tatsächlich einzubettende Vorlage bereits mit dem neuen Startweg abstimmen.

**Prüfungen:** Z-01–Z-05/Z-07–Z-09, P-03, E-05/E-06; Z-06 zunächst für bereits vollständig ausführbare Wege. Kleine Version-Gates mit passendem alten Testinterpreter; kein stiller Rückfall auf Hostinstallation. Übergangsbedingte noch offene Result-Parität sichtbar führen.

**Dokumentation:** `docs/runtime-bootstrap.md`, vorbereitete kanonische Chat-Vorlage und API-Beispiel. Die Anleitung trennt Vorabhashcheck, native Prüfung, Authentizität und Codeausführung.

**Abschlussgate:** Gebauter PYZ-Kandidat startet installationsfrei, pack/inspect/validate laufen aus seinen Bytes. Resultgenerierende Core-Parität und vollständiger Bootstrap gegen Format 3 bleiben bis PP-05/PP-06 als zu belegende Integration offen, nicht als bestanden markiert.

### PP-05A – Resultformat 3 und Runtime-Metadaten 2 streng lesen

**Normbezug:** FMT-01–05, MIG-01/05, PYZ-12, PACK-06/07.
**Voraussetzung:** PP-04C.
**Betroffene Stellen:** `result_reader.py`, `result_runtime.py`, `result_verification.py`, `runtime_pyz.py`, gemeinsame Ressourcenbilanz; neue `test_result_format3`-Fixtures.

**Umsetzung:** Alte Resultformate 1/2 explizit von Format 3 trennen. In Format 3 artifact.type=pyz und das neue Metadatenschema einschließlich Profil, capabilities und null-Vertrag für unavailable prüfen. Alte wheel-Felder nicht umdeuten. Geschlossene Objekte, bool-statt-int, doppelte Schlüssel, Hash-/Größen-/Pfad-/Versionswidersprüche sowie zusätzliche Archiveinträge ablehnen. Äußere und innere Runtimebudgets gemeinsam bilanzieren. Pythoncode aus der Referenz niemals importieren. Die über PP-01 genutzte gemeinsame Referenzprüfung erschließt automatisch pack mit gültigen Format-3-Fixtures; kein eigener Pack-Reader. Defekte deklarierte Runtime bleibt Referenzfehler, gültiges unavailable bleibt lesbar.

**Prüfungen:** F-01–F-05, F-02 mit eingefrorenem echten Legacy-Wheelprofil, Z-15/Z-16, P-06/P-07. Unabhängig erzeugte und gezielt manipulierte Fixtures; nicht allein eigene Writer/Reader gegenseitig bestätigen lassen.

**Dokumentation:** Neues `docs/result-format-3.md`; `docs/result-format-2.md` bleibt historische Beschreibung und verweist auf den Nachfolger. Neue Schemata mit gültigen ausführbaren Fixtures neben illustrativen Beispielen.

**Abschlussgate:** Vollständige native Referenzvalidierung und pack verstehen 1/2/3 mit ihren tatsächlichen Verträgen. Produktiver Writer und seine bisherigen Tests schreiben weiterhin Format 2.

### PP-05B – Alle Result-Verbraucher und den eingebetteten Bootstrap integrieren

**Normbezug:** MIG-02/03/05, FMT-05, CHAT-01/02/06, GOV-03/04.
**Voraussetzung:** PP-05A.
**Betroffene Stellen:** `exchange.py`, `exchange_archive.py`, `archive_evidence.py`, `exchange_recovery.py`, `result_verification.py` und ihre Aufrufpfade; Bootstrap-Skript und kanonische Vorlage.

**Umsetzung:** Klassifikation, Wiederverarbeitung, Archivierung und Recovery auf vollständige korrekte Format-3-Lesefähigkeit prüfen. Strukturelle Erkennung, vollständige Referenzprüfung und Erfolgs-/Commitbeleg bewusst auseinanderhalten. Eingefrorene Altleser mit belegter Herkunft ergänzen, ohne sie beim Ändern des neuen Readers mitzupatchen. Nachweisen, dass neue Results und standalone PYZ weder als Patch gestartet noch ohne belegten Erfolg entfernt werden. Bootstrap mit exakt dem neuen Metadaten-/Profilvertrag abstimmen; Legacywege bleiben ausdrücklich versioniert. Beide Spezifikationen in der kanonischen Anweisung gemeinsam auswählen. Eine noch wheelbasierte Produktion benötigt eine weiterhin zutreffende formatabhängige Anleitung; kein vorzeitiger Wegfall ihres funktionierenden Startwegs.

**Prüfungen:** F-08/F-09/F-10/F-14, E-06/E-09 und Fixture-Vorstufe von E-10; relevante bestehende Exchange-/Archiv-/Recoverytests. Für installed Watcher nur unveränderte Nutzung gemeinsamer Core-Verbraucher nachweisen, keinen Watcher in die PYZ kopieren.

**Dokumentation:** Bootstrap-/Resultformat-Dokumentation, Legacybehandlung und fachlicher Review der tatsächlich paketierten Vorlage; keine optischen UI-Tests.

**Abschlussgate:** Alle Verbraucher können die kommende Produktion lesen. Minimaler installationsfreier Bootstrap und einzubettende Vorlage sind bereit; sie werden nicht erst nach der Writerumschaltung geschrieben. Writer bleibt bis PP-06B unverändert.

### PP-06A – Gemeinsamen PYZ-Provider und request-lokale Result-Ressourcen vervollständigen

**Normbezug:** PYZ-06/10/11, FMT-02–04, MIG-04/06, PLAN-03.
**Voraussetzung:** PP-05B.
**Betroffene Stellen:** `runtime_artifact.py`, `result_resources.py`, `result_bundle_writer.py`, Result-Capture-/Handoff-Grenzen, Buildbackend und Runtimeproduktions-Tests.

**Umsetzung:** Den Provider so vervollständigen, dass reguläre vorbereitete Installation und geladene PYZ aus demselben endlichen Ressourceninventar denselben kanonischen Artefaktbestand erzeugen. Runtime, Identität und statische Vorlage vor Apply-Mutation gemeinsam request-lokal fixieren. Aktuell wheelbenannte interne Werte gezielt verallgemeinern, ohne Legacyreader umzudeuten. Die Format-3-Payload und Writerbausteine intern/über Tests bereitstellen, aber noch keinen unabhängig auslieferbaren Produktionswechsel aktivieren. Runtime-only-Fehler, vollständiger Snapshot/Logerhalt und begrenzter bestehender Fallback vorbereiten; Pflichtvorlagenfehler nicht als harmlos verschleiern. Kein Build, kein Installer-Cache und kein Netzwerk im Request. Testpfade für dreifache Reproduktion und Selbstupdate herstellen.

**Prüfungen:** Z-10–Z-13, F-07/F-11 und private Kandidaten für F-13; tatsächliche Wheel-/sdist-Installationen ohne Checkout/Cache. Reale Importherkunft und vor/nach Mutation gleiche Erzeugerressourcen erfassen.

**Dokumentation:** `docs/result-runtime-production.md`, `docs/runtime-artifact.md`, Build-/Releaseinventare. Result-CIFS-Vertrag unverändert benennen; keine Pack-Retryoption einführen.

**Abschlussgate:** Provider und Format-3-Writerbausteine sind für die gemeinsame Umschaltung bereit. Vorherige auslieferbare Resultproduktion bleibt funktionsfähig. Falls sich Ressourcen- und Umschaltänderung nicht sicher trennen lassen, PP-06A/B als einen geprüften Commit zusammenführen statt kaputten Zwischenstand auszuliefern.

### PP-06B – Format-3-Writer atomar mit seinem funktionsfähigen Bootstrap aktivieren

**Normbezug:** MIG-02/04/06, FMT-01–05, PYZ-10/11, ARCH-02, CHAT-01/02, E-10.
**Voraussetzung:** PP-06A.
**Betroffene Stellen:** Gemeinsame Result-Erzeugungsgrenze, `result_bundle_writer.py`, `result_resources.py`, Publikations-/Fallbackpfade, kanonische Anleitung und Runtime-Buildressourcen.

**Umsetzung:** Neue Produktion an der gemeinsamen Grenze auf Result 3/Runtime-Metadaten 2 umstellen: manuelles bundle, Apply-Erfolg/-Fehler, Dry-Run, manueller Runner und installierter Watcher über den Core. Genau eine PYZ bei embedded, keine parallele Runtime-Wheelproduktion; Legacyreader und normale Installationswheels behalten. Minimalen Bootstrap und tatsächlich gebaute/eingebettete Anleitung synchron aktivieren. Result-Replace/Sync/typisierte endliche CIFS-Retries/geteiltes Budget und Hashbindung bis zur Veröffentlichung unverändert erhalten. Neue Standardinstallation darf nicht regelmäßig unavailable liefern. Vollständige PYZ-Core-Parität einschließlich resultproduzierender Wege und drei echte isolierte Result/PYZ-Generationen testen. Den ersten umgestellten Resultoutput ausschließlich anhand seiner eigenen Anweisung in frischer Umgebung benutzen und damit gegen genau sich selbst packen/validieren.

**Prüfungen:** **E-10 vor Freigabe dieses Schritts**, nicht erst PP-07/08. Dazu E-01/E-02/E-06, Z-06/Z-11–Z-13, F-06/F-07/F-10/F-13/F-14. Lokale unterstützte Plattformnachweise sind sofort fällig; native Windows-/reale CIFS-Freigaben bleiben zusätzlich offen, soweit noch nicht tatsächlich ausgeführt.

**Dokumentation:** Alle unmittelbar vom Standardwechsel betroffenen Nutzungs-/Bootstrap-/Format-/Produktionstexte jetzt konsistent, einschließlich neu gebauter Ressourcen. PP-07 ist nur noch der übergreifende Abschlussreview.

**Abschlussgate:** Erster produktiver Format-3-Durchstich besteht mit realem Artefakt, eigener Anleitung, pack und Referenzprüfung. Keine ausgelieferte PYZ mit Wheel-only-Anleitung. PP-04-Resultparität darf erst jetzt vollständig abgenommen werden; fehlende E-10-Prüfung sperrt die Writerfreigabe.

### PP-07 – Chat-Vertrag, Beispiele und Dokumentation vollständig abgleichen

**Normbezug:** CHAT-01–06, DOC-01/02, GOV-01/03/04, CHECK-01/02, PLAN-04.
**Voraussetzung:** PP-06B.
**Betroffene Stellen:** Alle Dokumente aus Abschnitt 10; kanonische Chat-Vorlage, gebaute Ressourcen und vorhandene Release-/Buildaudits.

**Umsetzung:** Voll-Datei-, Diff-, Misch- und Diagnosebeispiele über installierte CLI, PYZ und API funktional nachvollziehen. Plan-/Normsatzwahl, Inhaltserstellerverantwortung, obligatorische Referenz und explizites Ausgabeziel deutlich machen. Technischen Startfallback von inhaltlicher Validatorablehnung trennen; kein Umgehen kaputter Bindung oder nativer Referenzprüfung. Finale kanonische ZIP, Paket-Hash und unabhängige Chat-Bundle-Nummer erhalten; kein automatischer Versand oder Watcherstart. Eine syntaktisch kaputte, formal gültige Entrypointdatei als Grenze des Prüfnachweises demonstrieren, ohne Erfolg einer Ausführung zu behaupten. Historische Dokumente nicht auf neues Format umschreiben. Änderungen an eingebetteten Vorlagen ändern die PYZ-Identität; danach Artefakte neu bauen und betroffene E-10-/Roundtrip-Prüfungen wiederholen.

**Prüfungen:** E-04/E-07–E-09; E-10 und Z-11/Z-12 erneut, wenn Artefaktressourcen verändert wurden; volle parallele Development-Suite vor tatsächlichem Commit. Sprachlicher Review, keine Regex-/Wortlauttests für Dokumentprosa.

**Dokumentation:** Vollständige Dokumentationsmatrix schließen, Zielrechnerdaten und Cleanup-/Ausgabefehler korrekt erklären. Hauptspezifikation und Ergänzung bleiben getrennte gemeinsame Grundlagen.

**Abschlussgate:** Keine unzutreffenden Beispiele, keine Einschränkung der PYZ auf nur drei Kommandos, kein Watcher in ihrem Umfang. Eine Dokumentationsänderung gilt nicht als nachweisneutral, wenn sie im Artefakt enthalten ist.

### PP-08A – Gesamte Funktions-/Robustheitsmatrix in den bestehenden Lanes absichern

**Normbezug:** TEST-01–07, DONE-01; gesamte Z-/F-/P-/S-/E-Matrix.
**Voraussetzung:** PP-07.
**Betroffene Stellen:** Neue und bestehende Testmodule, `tools/test_policy.py` nur bei nötiger fachlicher Zuordnung, bestehende CI-/Docker-/native Windows-Acceptanceeinbindung.

**Umsetzung:** Die 76 spezifizierten Testszenarien mit konkreten Test-Node-IDs oder ausdrücklich manuellen Review-/Praxisnachweisen vervollständigen. Prüfen, dass Marker/Selektoren neue Tests tatsächlich in die vorgesehenen Lanes aufnehmen; besonders der gesonderte Windows-PowerShell-7-Selektor ist derzeit dateibasiert und darf neue relevante Applyfälle nicht versehentlich auslassen. Race-/Fehlerinjektion mit deterministischen Synchronisationspunkten, sichere Nebenwirkungsinstrumentierung und Quell-/Referenz-/Outputstabilität vollständig abdecken. Laufende normale Installation mit Watcher unverändert testen, ohne realen systemd-Dienst zu starten. Bestehende Ressourcen-/Mode-/Replay-/Recovery-/Publikationsregressionen erhalten. Größen-, Start-, Pack- und Speicherwerte kontrolliert messen; keine pauschale Leistungszusage und keine künstlich engen Timingassertions.

**Prüfungen:** Gesamte Matrix einschließlich realer gebauten Wheel-/sdist-/PYZ-Artefakte außerhalb des Checkouts. Plattformbedingte Nichtausführung explizit benennen; Linux-Simulation ersetzt keine native Windows- oder reale CIFS-Prüfung.

**Dokumentation:** Testzuordnung und Messmethode dokumentieren. Tatsächliche Fehlerkorrekturen mit passendem Schritt/FIX-Scope ausweisen statt als rein redaktionelle Abnahme tarnen.

**Abschlussgate:** Keine neuen Produktgrenzen erst jetzt erfinden; alle zuvor aktivierten Sicherheitsfunktionen waren bereits getestet. Vollständige Testabdeckung ist eingerichtet, tatsächliche externe/native Abschlussnachweise bleiben PP-08B zugeordnet.

### PP-08B – Finale Artefakte auditieren und Abschlussnachweise binden

**Normbezug:** DONE-01, TEST-04–07, PLAN-01/04, GOV-02, MIG-06.
**Voraussetzung:** PP-08A.
**Betroffene Stellen:** `scripts/build_release.py`, bestehende Release-/Packaging-Audits und finale Dokumentation; Result-/Log-/CI-Nachweise des tatsächlichen geprüften Stands.

**Umsetzung:** Nur noch erforderliche Releaseaudit-/Inventar-/Dokumentkorrekturen vornehmen, die gewählte Produktversion konsistent setzen und alle finalen Installationsartefakte sowie die kanonische PYZ aus genau diesem Stand neu erzeugen. Bei keinem tatsächlichen Dateidelta keinen leeren Commit verlangen, sondern diesen Schritt als dokumentiertes Abnahmegate schließen. Vollständige lokalen Gates und tatsächlichen Apply-Nachweis erbringen. Die nach bestehender Policy fällige oder ausdrücklich autorisierte CI auf den vollständigen Endcommit binden und sämtliche vorgeschriebenen Jobs auswerten. Reale Linux→Windows-CIFS-Prüfung separat erbringen; offene Alt-Abnahmen nicht umetikettieren. Artefakthashes, Interpreter, Tests, Skips, CI und Praxisnachweise zu einer eindeutigen Abschlussbewertung zusammenführen. Kein Tag, Releaseupload oder globales Hostupgrade ohne eigenen Auftrag.

**Prüfungen:** Finale lokale/Apply-/native/CI-/CIFS-Abnahme, E-01–E-10 sowie Roundtrip mit finalen Bytes. Änderungen nach einer bestandenen Abnahme erfordern die jeweils betroffenen erneuten Tests; alte Artefakthashes sind dann nicht mehr der Nachweis des neuen Stands.

**Dokumentation:** Endgültiger Prüfnachweis über die bestehenden Result-/Logwege. Ein Bericht darf extern neben dem Result liegen; kein obligatorischer weiterer Repositorycommit nur um eine externe CI-ID einzutragen.

**Abschlussgate:** Freigabe nur bei vollständig belegtem DONE-01. Nicht fällige beziehungsweise nicht autorisierte zusätzliche CI wird nicht automatisch gestartet: erforderliche finale externe Nachweise bleiben bis zum regulären/autorisierten Lauf offen. Kein ungetesteter Nachtrag nach dem geprüften Endcommit als ebenfalls freigegeben ausgeben.


## 6. Integrations- und Umstellungsgates

### 6.1 Harte Freigabepunkte

| Gate | Muss spätestens erfüllt sein | Erforderlicher Nachweis | Was ausdrücklich nicht genügt |
|---|---|---|---|
| **G-REF** | PP-01 | Alte Prüfergebnisse und Fehlerkategorien bleiben erhalten; Packdaten stammen aus einer gemeinsamen stabilen Referenz | Nur JSON-Felder aus dem ZIP lesen |
| **G-PACK** | PP-02C/PP-03 | Fertige ZIP-Bytes gegen fixierte Referenz validiert, anschließend identitätsgebunden und exklusiv veröffentlicht; API/CLI konsistent | Nur ein gültiges Manifest oder ein ZIP ohne Publication-Test |
| **G-PYZ** | Erste Nutzbarkeit PP-04C; volle Core-Parität PP-06B | Ausführung aus echter PYZ ohne Checkout/Installation; No-Watcher-Inventar; eigene Ressourcen; am Ende alle Core-Wege | `sys.path` auf den Quellbaum setzen oder den installierten Core statt PYZ testen |
| **G-READ** | Vor Writerumschaltung, PP-05B | Format-3-Reader und sämtliche relevanten Verbraucher sowie Bootstrap-Startweg bereit | Nur `result_reader.py` anpassen und Exchange/Recovery vergessen |
| **G-WRITE / E-10** | **PP-06B vor dessen Freigabe** | Erstes reales neues Result mit eigener tatsächlich eingebetteter Anleitung verwenden, PYZ starten, damit gegen genau dieses Result packen und validieren | Späteres Dokumentationsversprechen, nur eine synthetische Fixture oder Nutzung eines Bootstrap aus dem Checkout |
| **G-ROUNDTRIP** | PP-06B; nach artefaktwirksamen Änderungen erneut | Mindestens drei isolierte Result/PYZ-Generationen mit gleicher Runtimegröße und identischem SHA-256; Installation und PYZ erzeugen gleiche kanonische Bytes | Nur identische Versionsstrings oder ein einzelner erfolgreicher Start |
| **G-PUBLICATION** | PP-06B lokal, vollständige native/Praxisabnahme PP-08B | Unveränderte Result-Sync-/Retry-/Hashregeln für Format 3 und separate Pack-No-replace-/No-retry-Regeln | Result und Pack auf dieselbe überschreibende oder wartende Politik vereinheitlichen |
| **G-FINAL** | Abschluss PP-08B | Vollständige lokale, Apply-, erforderliche native/CI-/CIFS-Nachweise auf konkretem Endcommit und konkreten Artefakten | Code vorhanden, lokale Teilsuite grün, früherer CI-Lauf oder bloß geplante Plattformprüfung |

Ein fehlgeschlagenes Gate wird nicht durch Verschieben seines Tests in PP-08 oder durch eine Capability-Ankündigung ersetzt. Der betreffende aktivierende Schritt wird nicht ausgeliefert. Bereits erfolgreich durchlaufene echte Commits bleiben im vorhandenen Entwicklungs-/Apply-Vertrag erhalten; kein globales Zurückrollen eines Teilfortschritts.

### 6.2 Minimaler reproduzierbarer Writer-Durchstich

Der E-10-Nachweis muss mindestens diese tatsächlich ausgeführten Stationen erkennen lassen:

1. Reguläre vorbereitete Installation aus dem zu prüfenden Build verwenden; ein isoliertes Git-Repository mit normaler lokaler Registrierung/Konfiguration erzeugt ein neues Result. Das Anlegen dieses Testrepositorys ist Testaufbau für `bundle`/`apply`, **keine Voraussetzung von `pack`**.
2. In einer zweiten frischen Python-Umgebung ohne installierten Core und außerhalb des Checkouts ausschließlich das Result und die vorbereiteten Patchinhalte bereitstellen. Die mitgelieferte Anleitung muss selbst den korrekten Startweg beschreiben. Darin nicht dokumentierte Hilfen aus dem Buildcheckout dürfen den Durchstich nicht retten.
3. Die einzelne deklarierte Runtime mit Vorprüfung entnehmen; tatsächliche Pythonversion, vollständigen Artefakthash und Importherkunft erfassen. Kein pauschales `extractall`, keine Wheelinstallation und keine Netzabhängigkeit.
4. Mit dieser PYZ `pack` gegen genau dieses unveränderte Result aufrufen. Vollständige CLI-/API-Daten, Ausgabehash und `scope=reference` mit `binding_matches=true` erfassen. Die Tatsachenprüfung kommt aus dem gemeinsamen Core, nicht nur aus dem Bootstrap.
5. Das erzeugte Paket zusätzlich inspizieren und in der passenden isolierten Repositoryinstanz über den regulären Apply-Weg testen. Voll-Datei- und Diff-/Mischfälle belegen die unveränderte Einspielreihenfolge. Eine später veränderte Zielinstanz muss weiterhin an der Bindungsprüfung scheitern.
6. Aus der geladenen PYZ weitere Results erzeugen und jeweils die neu entnommene PYZ verwenden. Drei Generationen vergleichen; Resultzeitstempel dürfen sich ändern, Runtimebytes nicht. Der Test darf nicht immer wieder dieselbe zuvor installierte Hostruntime benutzen.

Ein bloßes Installieren des Builds im Testsetup verletzt nicht das Ziel: Nach diesem Setup müssen **Resultproduktion aus vorbereiteter Installation und die portable Nutzung** ohne Build, Installer oder Netz auskommen. Die erlaubten Build-/Test-Setup-Nebenwirkungen werden von den instrumentierten Produktoperationen getrennt.

### 6.3 Übergang und mögliche Zusammenlegungen

PP-02A/B/C bilden interne Vorbereitung und die abschließende sichere öffentliche API. Sie dürfen in einem Paket oder bei überschaubarem Umfang in einem Commit umgesetzt werden. Eine unfertige `pack`-CLI mit `--skip-validation` oder stiller Überschreiblogik ist niemals ein zulässiger Zwischenstand.

Bei PP-04 bis PP-06 sind vorübergehend getrennte Legacy- und PYZ-Ressourcen zulässig, sofern ihre Inventare, Herkunft und Hashverfahren nicht vermischt werden. Ein kanonisches PYZ-Profil darf das alte komplette Wheel nicht enthalten. Der alte Wheel-Lesecode bleibt auch nach der Umschaltung im Core.

Eng gekoppelte Provider-/Bootstrap-/Writeränderungen dürfen zusammenfallen. Die **Lesefähigkeit muss vor der produktiven Aktivierung vorhanden und getestet sein**, auch innerhalb desselben größeren Arbeitspakets. Ein temporärer privater Testzugang ist kein neuer öffentlicher Umschalter; nach Abschluss bleibt kein unnötiger dualer Writer oder neues Nutzerflag zurück.

## 7. Testausführung, Plattformen und CI

**Aktueller Vorrang:** Der ausdrücklich bestätigte Laptop-Wechsel beendet die
Pixel-Phase. Abschnitt 1.9 und die folgenden Development-/Apply-Gates gelten.
Development ausschließlich parallel; Apply-Endstand seriell und danach parallel
vor dem letzten Commit und dem einzigen Push. Reguläre CI wieder im Fünfertakt,
nächster Termin 029. Offene native/CIFS-Nachweise bleiben bestehen.

### 7.1 Bestehende Tests wiederverwenden

Alle Befehle in diesem Abschnitt sind **Anweisungen für die spätere Umsetzung**. Bei dieser Planerstellung wurden keine Produkttests, Builds, Applys oder CI-Läufe ausgeführt.

Im gelieferten Stand existiert `tools/run_tests.py`. Seine benannten Suites und seine Passthrough-Regeln wurden geprüft. Eine benannte Teilsuite darf nicht gleichzeitig durch eigene Selektoren verändert werden. Beispielaufrufe aus einer bereits korrekt eingerichteten Entwicklungsumgebung:

```bash
# Vollständige Development-Prüfung: standardmäßig parallel.
python tools/run_tests.py --suite all

# Gezielt an bestehenden Prüfern arbeiten; kein Ersatz für das Vollsuite-Gate.
python tools/run_tests.py --workers 2 --   tests/test_patch_inspection.py   tests/test_reference_validation.py

# Bestehende fachliche CI-/Testbereiche, ebenfalls standardmäßig parallel.
python tools/run_tests.py --suite core
python tools/run_tests.py --suite e2e
python tools/run_tests.py --suite platform
python tools/run_tests.py --suite packaging
```

Neue Testdateien werden erst nach ihrer Implementierung mit ihrem wirklichen Namen aufgerufen. Bestehende Suite-Marker und der tatsächliche Collection-Nachweis müssen ihre Aufnahme belegen. Es wird kein zweiter Testscheduler oder eigener Testlauncher eingeführt.

### 7.2 Development und Apply nicht vermischen

Die ausdrückliche Nutzeranweisung aus Abschnitt 1.10 hat Vorrang vor älteren
seriellen Endgates. Jeder Entwicklungs- und Apply-Stand wird vollständig parallel
mit `python tools/run_tests.py --suite all` geprüft. Vor jedem tatsächlichen
Commit müssen dessen unveränderte Quellen und vollständige Controller-Nachweise
erfolgreich geprüft sein. Auch am Bundle-Ende läuft keine serielle Suite.
Nach den geprüften Commits erfolgt genau ein normaler Push auf den bestätigten
Zielbranch. Ein Fehler erhält bereits eingespielte Dateien und erfolgreiche
Teilcommits; die Fortsetzung bindet das neue tatsächliche Result.

Verwendet wird die bestehende Entwicklungsumgebung. Berichte liegen außerhalb
des getesteten Quellstands. Keine verkürzten Timeouts, Testauswahl als Vollabnahme
oder neue Tests auf Prosa, UI, Farben und Formatierung. Der vorhandene
Modusverifier bleibt als Werkzeug erhalten, wird in dieser Schleife aber nicht
ausgeführt. Native Plattformnachweise werden nicht aus Linux-Tests abgeleitet.

### 7.3 Plattformmatrix auf Grundlage des gelieferten Workflows

Dies ist die **im bereitgestellten Snapshot gelesene** Matrix, nicht die Behauptung einer aktuellen externen CI-Ausführung. PP-00 gleicht spätere autorisierte Änderungen ab.

| Bestehende Lane | Interpreter / Plattform | Nachweis für diese Features |
|---|---|---|
| Native Acceptance Ubuntu 24.04 | CPython 3.12, Linux | Untergrenze, Pack-Dateisystem, Bash-Apply, CLI/API und Packaging/PYZ |
| Native Acceptance Windows 2025 | CPython 3.12, Windows PowerShell | Native Datei-/Reparse-/No-replace-Pfade, PowerShell-Apply, Packaging/PYZ |
| Native Acceptance Ubuntu 26.04 | CPython 3.14, Linux | Zweiter unterstützter Interpreter und repräsentativer uv-Installationsweg |
| Gesonderte Windows-PowerShell-7-Abnahme | CPython 3.12, `pwsh` | Tatsächliche Pack→Apply-/Runner-Shellintegration ohne Ausweichen auf anderen Interpreter |
| Docker Ubuntu 24.04 und 26.04 | Bestehende Integrationsimages | Fortgeltende Integrations-/Installationsgates; keine native Windows-Ersatzbehauptung |
| Reale Linux→Windows-CIFS-Freigabe | Tatsächlich betroffene Konstellation | Unveränderte Result-Publikationspolitik für Format 3; getrennt von Simulation und native Windows |
| Optional | ARM64/Ubuntu-in-Termux | Gesonderter Zusatznachweis; keine allgemeine Android-Garantie und kein Ersatz für Pflichtlanes |

Die Python-Untergrenze 3.12 und der zusätzliche Interpreter 3.14 werden nicht durch einen alleinigen Test auf der zufällig verfügbaren Chat-Pythonversion ersetzt. Der gesonderte Test eines älteren Interpreters prüft nur dessen verständliche Ablehnung, nicht dessen Produktunterstützung. Fehlender Testinterpreter oder fehlende Plattform sind offene Nachweise, keine bestandenen Tests.

Normale Wheel-/sdist-/pip-/pipx-/uv-Wege werden nach der vorhandenen repräsentativen Packaging-Policy geprüft. Kein unnötiges vollständiges Kreuzprodukt aller Varianten. Echte gebaute Artefakte, ihre installierten Inventare und ihre Importherkunft müssen nachweisbar sein.

### 7.4 CI-Start und Freigabe

CI bleibt ausschließlich per `workflow_dispatch` startbar. Nur Christian selbst
startet den Workflow; weder Codex noch ein Apply-Entrypoint lösen ihn aus.
Der frühere Fünfertakt entfällt. Keine Push-/PR-/Zeitplantrigger, keine automatischen
Retries. Die vorhandenen parallelen Lanes und ihre Timeouts bleiben unverändert.

Fehlende CI allein blockiert keinen Entwicklungsschritt. Tatsächliche native
Abnahme und Releasefreigabe bleiben davon getrennt: fehlende Windows-, Python-3.12-,
Docker- oder CIFS-Nachweise werden offen ausgewiesen, niemals als bestanden
behauptet. Ein später vom Nutzer gestarteter passender Lauf kann ausgewertet werden.

### 7.5 Messungen und negative Nachweise

Mit finalen Artefakten werden PYZ-Größe, zusätzlicher komprimierter Resultumfang, Startzeit sowie Pack-Zeit und begrenzter Speicherbedarf für ein kleines Skriptpaket, ein gemischtes Paket und einen repräsentativen größeren Fall erfasst. Messungen nennen System, Python, Eingabegrößen und Anzahl der Dateien. Keine pauschale Garantie und kein millisekundenscharfer Timingtest.

Für `inspect`, paket-/referenzbasiertes `validate` und `pack` werden Prozess-/Netzwerkzugriffe und erlaubte Dateischreibbereiche instrumentiert. Build-/Installationssetup und späterer regulärer Apply sind davon getrennte Testphasen. Observer-Callbacks sind Aufrufercode; der Packer darf ihre Möglichkeiten nicht als eigene garantierte Sandbox darstellen.

## 8. Anforderungszuordnung

Jede der **83 normativen Anforderungskennungen** aus Revision 2 hat mindestens eine Umsetzungszuständigkeit. Die Tabelle ist eine Zuordnung, keine zweite Spezifikation. Der exakte Vertragswortlaut bleibt ausschließlich in den beiden normativen Dokumenten. Abschnitt 9 ordnet die konkreten spezifizierten Prüfungen zu.

| Anforderung | Umsetzung / spätester Nachweis |
|---|---|
| `GOV-01` | PP-00, PP-07 |
| `GOV-03` | PP-00, PP-07 |
| `GOV-02` | PP-00, PP-08B |
| `GOV-04` | PP-01, PP-02C, PP-05B, PP-06B, PP-07 |
| `SCOPE-01` | PP-04A, PP-06B, PP-08B |
| `SCOPE-02` | PP-04C, PP-06B |
| `SCOPE-03` | PP-04A, PP-04C, PP-06B, PP-08A |
| `SCOPE-04` | PP-02C, PP-03, PP-04C |
| `SCOPE-05` | PP-01, PP-02C, PP-03 |
| `SCOPE-06` | PP-04B, PP-06A, PP-06B |
| `SEM-01` | PP-02A, PP-02B, PP-06B, PP-08A |
| `SEM-02` | PP-02A, PP-02B, PP-06B, PP-08A |
| `ARCH-01` | PP-01, PP-02C, PP-03, PP-04B |
| `ARCH-02` | PP-04C, PP-06B, PP-08A |
| `ARCH-03` | PP-04C, PP-06B, PP-08A |
| `PYZ-01` | PP-04C, PP-05B, PP-08A |
| `PYZ-02` | PP-04C, PP-05B, PP-08A |
| `PYZ-03` | PP-04A, PP-05A, PP-08A |
| `PYZ-04` | PP-04B, PP-04C, PP-06A |
| `PYZ-05` | PP-04C, PP-05B, PP-08A |
| `PYZ-06` | PP-04A, PP-04B, PP-06A, PP-08B |
| `PYZ-07` | PP-04A, PP-05A, PP-08A |
| `PYZ-08` | PP-04A, PP-05A, PP-08A |
| `PYZ-09` | PP-04A, PP-05A, PP-08A |
| `PYZ-10` | PP-04B, PP-06A, PP-06B, PP-08B |
| `PYZ-11` | PP-06A, PP-06B, PP-07, PP-08B |
| `PYZ-12` | PP-04A, PP-05A, PP-08A |
| `FMT-01` | PP-05A, PP-05B, PP-06B |
| `FMT-02` | PP-05A, PP-05B, PP-06B |
| `FMT-03` | PP-05A, PP-05B, PP-06B |
| `FMT-04` | PP-05A, PP-05B, PP-06B |
| `FMT-05` | PP-05A, PP-05B, PP-06B |
| `MIG-01` | PP-05A, PP-05B |
| `MIG-02` | PP-05B, PP-06B |
| `MIG-03` | PP-05B, PP-08A |
| `MIG-04` | PP-06A, PP-06B |
| `MIG-05` | PP-01, PP-05A, PP-05B, PP-07 |
| `MIG-06` | PP-01, PP-06B, PP-08A, PP-08B |
| `PACK-01` | PP-03, PP-04C |
| `PACK-02` | PP-02A, PP-02C, PP-03 |
| `PACK-03` | PP-02C, PP-03 |
| `PACK-04` | PP-02B, PP-02C, PP-03 |
| `PACK-05` | PP-03 |
| `PACK-06` | PP-01, PP-02C, PP-05A |
| `PACK-07` | PP-01, PP-02C, PP-05A |
| `PACK-08` | PP-02A, PP-02C |
| `PACK-09` | PP-02A, PP-02C |
| `PACK-10` | PP-02A, PP-02C |
| `PACK-11` | PP-02A, PP-02C |
| `PACK-12` | PP-02A, PP-02B, PP-02C |
| `PACK-13` | PP-02A, PP-02B, PP-02C |
| `PACK-14` | PP-02B, PP-03 |
| `PACK-15` | PP-02B, PP-03 |
| `PACK-16` | PP-02B, PP-03 |
| `PACK-17` | PP-02B, PP-03 |
| `PACK-18` | PP-02C, PP-03, PP-08A |
| `PACK-19` | PP-02C, PP-03, PP-08A |
| `PACK-20` | PP-02C, PP-03, PP-08A |
| `PACK-21` | PP-02C, PP-03, PP-08A |
| `PACK-22` | PP-01, PP-02A, PP-02C, PP-03 |
| `PACK-23` | PP-02C, PP-03, PP-08A |
| `CHECK-01` | PP-01, PP-02C, PP-07, PP-08A |
| `CHECK-02` | PP-01, PP-02C, PP-07, PP-08A |
| `CHAT-01` | PP-04C, PP-05B, PP-06B, PP-07 |
| `CHAT-02` | PP-04C, PP-05B, PP-06B, PP-07 |
| `CHAT-03` | PP-03, PP-07 |
| `CHAT-04` | PP-04C, PP-05B, PP-07 |
| `CHAT-05` | PP-03, PP-07 |
| `CHAT-06` | PP-00, PP-05B, PP-07 |
| `DOC-01` | PP-00, PP-03, PP-04A, PP-04B, PP-04C, PP-05A, PP-05B, PP-06A, PP-06B, PP-07, PP-08B |
| `DOC-02` | PP-00, PP-03, PP-04A, PP-04B, PP-04C, PP-05A, PP-05B, PP-06A, PP-06B, PP-07, PP-08B |
| `TEST-01` | PP-00, PP-02A, PP-02C, PP-03, PP-04A, PP-04C, PP-05A, PP-05B, PP-06B, PP-08A |
| `TEST-02` | PP-00, PP-02A, PP-02C, PP-03, PP-04A, PP-04C, PP-05A, PP-05B, PP-06B, PP-08A |
| `TEST-03` | PP-00, PP-02A, PP-02C, PP-03, PP-04A, PP-04C, PP-05A, PP-05B, PP-06B, PP-08A |
| `TEST-04` | PP-00, PP-08A, PP-08B |
| `TEST-05` | PP-00, PP-08A, PP-08B |
| `TEST-06` | PP-08A, PP-08B |
| `TEST-07` | PP-00, PP-08A, PP-08B |
| `PLAN-01` | PP-00, PP-07, PP-08B |
| `PLAN-02` | PP-00, PP-07, PP-08B |
| `PLAN-03` | PP-00, PP-07, PP-08B |
| `PLAN-04` | PP-00, PP-07, PP-08B |
| `DONE-01` | PP-08B |


## 9. Vollständige Zuordnung der spezifizierten Tests

Die **76 Szenarien** werden nicht mit 76 einzelnen pytest-Funktionen gleichgesetzt. Ein Szenario kann mehrere Testfälle benötigen oder mehrere Szenarien können einen sauber abgegrenzten parametrisierten Test teilen. Jede Kennung muss auf konkrete tatsächlich ausgeführte Node-IDs, Fixtures oder dokumentierte manuelle Nachweise zurückführbar bleiben.

Alle Szenarien stehen in diesem Plan auf **offen**. Die Beschreibung folgt Revision 2. Ein früher Owner bezeichnet den vorgesehenen Implementierungsschritt; plattformabhängige Abschlussnachweise werden zusätzlich auf PP-08B gebunden. `E-08`/`E-09` sind ausdrücklich fachliche Reviews, keine neue Wortlaut-/UI-Testreihe.

### 9.1 Ablage und Ausführung der Tests

| Testbereich | Vorhandene Tests fortführen | Sinnvolle neue Testmodule, sofern benötigt |
|---|---|---|
| Referenz-/Prüfervertrag | `test_patch_inspection*`, `test_reference_validation*`, `test_api_contract` | Erweiterung der vorhandenen Module genügt meist |
| Pack-Daten und Scanner | `test_bundle_handoff`, `test_payload_modes`, `test_resource_policy` | `test_pack.py`, `test_pack_sources.py` |
| Pack-Publikation und CLI | Plattform-/Handle-/Resultregressionen getrennt erhalten, `test_cli_api` | `test_pack_publication.py`, `test_pack_cli.py` |
| Pack→Apply | `test_apply_package`, `test_payload_modes_e2e`, bestehende Windows-Acceptance | `test_pack_e2e.py` oder eindeutig markierte Ergänzungen |
| PYZ-Profil und Ressourcen | `test_runtime_artifact`, `test_runtime_packaging`, `test_runtime_robustness` | `test_runtime_pyz.py` |
| PYZ-Bootstrap/Parität | `test_runtime_bootstrap`, Packaging-/Importisolationshilfen | `test_pyz_e2e.py` |
| Format 3 und Übergang | `test_result_format2`, Exchange-/Archiv-/Recoverytests, eingefrorene Altfixtures | `test_result_format3.py`, versionierte Legacyfixtures |
| Resultproduktion/CIFS | `test_result_runtime_writer`, `test_result_runtime_roundtrip`, `test_result_bundle_publication`, `test_result_file_handles` | Ergänzungen für Format 3 statt unabhängiger zweiter Publikationssuite |

Die tatsächlichen Modulnamen und Node-IDs werden bei Implementierung in die Nachweise übernommen. Reine Dokumentationsbeispiele werden über ihre ausführbaren Funktionen getestet, nicht durch `grep` auf den Wortlaut. Architekturtests dürfen den fachlichen Importgraphen und das Artefaktinventar prüfen.

### 9.2 Szenarien und Zuständigkeiten


#### Z – PYZ und Artefakterzeugung

| ID | Verbindlicher Nachweis aus Revision 2 | Umsetzung | Gate / Nachweisart |
|---|---|---|---|
| `Z-01` | Frischer Interpreter startet die gebaute PYZ ohne PatchHarbor-Installation, `pip`, venv-Erzeugung, Netzwerk oder Checkout. | PP-04C | G-PYZ; native/Packaging |
| `Z-02` | `--version`, CLI und API beziehen ihren Code nachweislich aus der ausgewählten PYZ, auch bei gleichnamigen Modulen im Arbeitsverzeichnis. | PP-04C | G-PYZ; native/Packaging |
| `Z-03` | Empfohlener Aufruf `-I -S -B` funktioniert; technische Isolation wird nicht als Sandbox behauptet. | PP-04C | G-PYZ; native/Packaging |
| `Z-04` | `inspect`, paket-/referenzbasiertes `validate` und `pack` funktionieren ohne Git/Bash/PowerShell. | PP-04C | G-PYZ; native/Packaging |
| `Z-05` | Kein `patchharbor_watcher/` und keine Watcher-Ressourcen im echten PYZ-Inventar; Core-Import benötigt sie nicht. | PP-04A, PP-04C | G-PYZ; Archiv/Importgraph |
| `Z-06` | Alle vorgesehenen Core-CLI-/API-Wege funktionieren aus der PYZ bei vorhandenen regulären Voraussetzungen, einschließlich `fs run`, Registry/Konfiguration und Apply. | PP-04C, PP-06B | G-PYZ vollständig ab PP-06B; native E2E |
| `Z-07` | Kanonische Vorlage, Lizenz und API-Daten werden aus der PYZ gelesen; kein CWD-/Fremdinstallations-Fallback bei defekten eigenen Ressourcen. | PP-04B, PP-04C | G-PYZ; Resource-/Importtests |
| `Z-08` | Zu alter Interpreter, fehlende Ressourcen, beschädigte Identität, widersprüchliche Rezeptdaten und nicht unterstütztes Profil werden korrekt behandelt. | PP-04A, PP-04B, PP-04C | G-PYZ; Daten-/Interpreterfehler |
| `Z-09` | In-Process-API ohne Unterprozess; Konflikt mit vorher importierter anderer Version wird erkannt, nicht per unsicherem Entladen kaschiert. | PP-04C | G-PYZ; native/Packaging |
| `Z-10` | Installierte, cachebereinigte Standarddistribution materialisiert die korrekte PYZ ohne Build oder Netz. | PP-06A, PP-06B | G-WRITE; echte Installation |
| `Z-11` | Installation und daraus erzeugte PYZ materialisieren identische kanonische Archivbytes. | PP-06A, PP-06B | G-ROUNDTRIP; nach Ressourcendeltas erneut |
| `Z-12` | Mindestens drei aufeinanderfolgende Result-/PYZ-Generationen; gleiche Runtime-Bytes, Größe und Hash, kein rekursives Wachstum. | PP-06A, PP-06B | G-ROUNDTRIP; nach Ressourcendeltas erneut |
| `Z-13` | Selbstupdate nach eingefrorener Erzeugeridentität erzeugt keine Mischung alter Runtime mit später geladener neuer Vorlage. | PP-04B, PP-06A, PP-06B | G-WRITE; Selbstupdate |
| `Z-14` | Andere Builds mit gleichem Versionsstring bleiben unterscheidbar. Änderungen an Version/Provenienz werden von Änderungen der inventarisierten Core-Dateihashes unterschieden; ausgeschlossene Watcher-Dateien werden nicht mitgehasht. | PP-04A | G-PYZ; unabhängige Hashvektoren |
| `Z-15` | Fremdmodule, native Dateien, `.pth`, zusätzliche/fehlende Einträge, manipulierte lokale ZIP-Header, CRC-/Hashfehler und gefälschte Verzeichniszähler werden abgelehnt. | PP-04A, PP-05A | G-READ; Daten-/Budgettests |
| `Z-16` | Laufzeitbudget, Rezeptlimit und gemeinsame äußere/innere Budgetierung greifen vor unbeschränktem Einlesen. | PP-04A, PP-05A | G-READ; Daten-/Budgettests |

#### F – Resultformate und Kompatibilität

| ID | Verbindlicher Nachweis aus Revision 2 | Umsetzung | Gate / Nachweisart |
|---|---|---|---|
| `F-01` | Neue Reader lesen gültige Results 1, 2 und 3; formatbezogene Inventare bleiben getrennt. | PP-05A | G-READ; Format-/Legacytests |
| `F-02` | Alte Wheels werden nur lesend nach altem Profil geprüft; kein Import/Installieren und keine Umdeutung zu PYZ. | PP-05A | G-READ; Format-/Legacytests |
| `F-03` | Deskriptoren, Bytegrößen, Hashes, Profil, Content-ID, Versionsangaben und Capability-Daten werden konsistent geprüft. | PP-05A | G-READ; Format-/Legacytests |
| `F-04` | `unavailable` hat genau die erlaubte Struktur, Gründe und null-Werte; keine behaupteten Artefakte. | PP-05A | G-READ; Format-/Legacytests |
| `F-05` | Zusätzliche Runtime-Dateien, Wheel+PYZ-Doppelbelegung, unbekannte Schlüssel und unbekannte Formate werden konservativ abgelehnt. | PP-05A | G-READ; Format-/Legacytests |
| `F-06` | Result-Erzeugung funktioniert manuell, nach Apply-Erfolg/-Fehler, im Dry-Run, mit explizitem Ziel und über installierten Watcher. | PP-06B | G-WRITE; Core/installed-Watcher-E2E |
| `F-07` | Runtime-only-Ausfall erhält Snapshot/Logs als `unavailable`; echte Resultfehler, Abbruch und Notfallrettung behalten ihre Priorität. | PP-06A, PP-06B | G-WRITE; Fault-Injection |
| `F-08` | Archivierung/Recovery verwenden keine bloß strukturelle Klassifikation oder schwächere Diagnoseprüfung als Erfolgsbeweis. | PP-05B | G-READ; Archiv/Recovery/Altleser |
| `F-09` | Eingefrorene Altleser führen Format-3-Results oder eine standalone PYZ nicht als Patch aus und löschen sie nicht aufgrund unbewiesener Fakten. | PP-05B | G-READ; Archiv/Recovery/Altleser |
| `F-10` | Reader-first-Zwischenstand schreibt noch Format 2; auslieferbare Writerumschaltung erst mit gemeinsamer Lesefähigkeit, Runtime-Provider und funktionsfähigem eingebettetem Bootstrap. | PP-05B, PP-06B | G-WRITE; E-10 ist sofort fällig |
| `F-11` | Normale Wheel-/sdist-Installationswege samt installiertem Watcher bleiben funktional; nur das Result-Runtime-Artefakt wechselt. | PP-04A, PP-06A, PP-08B | G-FINAL; Installationsgates |
| `F-12` | Legacy-Patch-Pakete und bestehende CLI-/API-/Fingerprint-/Replay-/Mode-Verträge bleiben gültig. | PP-01, PP-02C, PP-06B, PP-08A | G-FINAL; Bestandsregression |
| `F-13` | Vorhandene Result-Publikations-Fault-Tests auch für Format 3 mit PYZ und `unavailable`: Sync/No-follow, typisierte endliche Retries, gemeinsames Budget, Hashbindung, Runtime-Fallback und Diagnosepriorität bleiben erhalten. | PP-06B, PP-08A, PP-08B | G-PUBLICATION; zusätzlich reale CIFS-Abnahme |
| `F-14` | Pack-No-replace und dessen fehlende Stabilitäts-Retries verändern weder Result-Replace/Retry noch die bisherige nichtrekursive Exchange-/Runner-Suche. | PP-02C, PP-05B, PP-06B | G-PUBLICATION; Politiktrennung |

#### P – Pack-Funktion und Metadaten

| ID | Verbindlicher Nachweis aus Revision 2 | Umsetzung | Gate / Nachweisart |
|---|---|---|---|
| `P-01` | Voll-Datei-Paket aus vorbereitetem Inhaltsordner, Manifest mit vollständiger Referenzbindung, korrektes finales ZIP. | PP-02B, PP-02C | G-PACK; zusätzlich Apply-E2E |
| `P-02` | Entrypoint mit Diff-Payload, gemischtes Paket und Diagnosepaket ohne Nutzdateien funktionieren; Packer führt nichts aus. | PP-02B, PP-02C | G-PACK; zusätzlich Apply-E2E |
| `P-03` | CLI, öffentliche API, installierte Anwendung und PYZ verwenden dieselbe fachliche Pack-Implementierung. | PP-03, PP-04C | G-PYZ; drei Zugänge, ein Core |
| `P-04` | Fehlende Pflichtparameter, Optionskonflikte, Byte-/Leerpfade, falsche API-Typen und doppelte CLI-Moduspfade werden korrekt abgewiesen. | PP-02C, PP-03 | G-PACK; Argumentgrenzen |
| `P-05` | Alle vier Bindungswerte werden exakt übernommen; `expected_*`, Anzeigenamen und gekürzte IDs werden nicht als Ersatz genutzt. | PP-01, PP-02B | G-PACK; exakte Bindung |
| `P-06` | Gültige Dirty-, Dry-Run-, Fehler- und Legacy-Referenzen funktionieren; falsche/intern inkonsistente Referenzen scheitern. | PP-01, PP-02C, PP-05A | G-READ; gültige 1/2/3-Referenzen |
| `P-07` | Runtime-`unavailable` als gültige Referenz funktioniert; deklarierte kaputte Runtime führt nicht zu heimlichem schwächerem Erfolg. | PP-01, PP-02C, PP-05A | G-READ; gültige 1/2/3-Referenzen |
| `P-08` | Manifest- und `PATCHHARBOR_META`-Kollisionen, falsche Groß-/Kleinschreibung und nicht vorhandener Entrypoint werden abgewiesen. | PP-02A | G-PACK; vollständiges Inventar |
| `P-09` | Zulässige Unterverzeichnisse, Dotfiles und Repository-Anleitungen im Inhaltsbaum werden übernommen; angrenzende Projektdateien nicht. Keine `.gitignore`-Heuristik oder automatische Dateiänderung. | PP-02A | G-PACK; vollständiges Inventar |
| `P-10` | Binärinhalte, Zeilenenden und sonstige Nutzbytes bleiben exakt erhalten; fehlende Skriptmarker werden nicht ergänzt. | PP-02A, PP-02B | G-PACK; Modi später auch Apply-E2E |
| `P-11` | Default `0644`, explizit `0755`, verbotene Bits, unbekannte Modusschlüssel und vorhandene POSIX-Zielmodi werden korrekt behandelt. | PP-02A, PP-02B | G-PACK; Modi später auch Apply-E2E |
| `P-12` | Automatischer UTC-/UUID-Dateiname, Namensanpassung, Legacy-Fallback und leeres/gesetztes Suffix; Uploadname ist keine Quelle. | PP-02B, PP-03 | G-PACK; Name/Suffix |
| `P-13` | Expliziter Ausgabename bleibt unverändert; falsches Suffix und temporärer Downloadname werden abgelehnt. | PP-02B, PP-03 | G-PACK; Name/Suffix |
| `P-14` | Handoff enthält Zielrechnerdaten und ursprüngliches `captured_at`, nicht Pack-Hostdaten; neue Bindung/Dateiname passen exakt. | PP-02B | G-PACK; passive Zielmetadaten |
| `P-15` | Legacy-Environment mit unbekannten Werten erzeugt keine erfundenen OS-/Tooldaten; keine mehrfach angehängte alte generierte Anleitung. | PP-02B | G-PACK; passive Zielmetadaten |
| `P-16` | Typisiertes Ergebnis und JSON-Envelope enthalten identische vollständige Fakten, Referenzhash, Prüfumfang und Nichtprüfungen. | PP-02C, PP-03 | G-PACK; API/JSON-Parität |
| `P-17` | Sowohl `--output` als auch `--output-dir` erzeugen genau eine Paket-UUID und einen UTC-Zeitpunkt pro Auftrag; diese werden stabil zurückgegeben, nur der automatische Name verwendet sie. | PP-02B, PP-03 | G-PACK; Identitäten, kein Zähler |
| `P-18` | Paket-UUID/ID6, Referenz-Run-ID und Chat-Bundle-Nummer bleiben getrennt; kein Zählerzustand wird angelegt und der Entrypoint bleibt bytegleich. | PP-02B, PP-03 | G-PACK; Identitäten, kein Zähler |

#### S – Sicherheit, Veröffentlichung und Unterbrechung

| ID | Verbindlicher Nachweis aus Revision 2 | Umsetzung | Gate / Nachweisart |
|---|---|---|---|
| `S-01` | Traversal, absolute/Windows-/UNC-Pfade, Gerätebezeichnungen, interne Pfade, case-Kollisionen und Datei-/Verzeichnispräfixkonflikte werden abgelehnt. | PP-02A | G-PACK; native Datei-/Reparsefälle zusätzlich |
| `S-02` | Symlink-/Reparse-Austausch und Quelldateiwechsel zwischen Scan/Öffnen werden erkannt; keine Aufnahme außerhalb der Wurzel. | PP-02A | G-PACK; native Datei-/Reparsefälle zusätzlich |
| `S-03` | Hardlinks, FIFOs, Sockets und Geräte werden nicht gelesen oder blockierend geöffnet. | PP-02A | G-PACK; native Datei-/Reparsefälle zusätzlich |
| `S-04` | Veränderte Quelldatei, verändertes Quellinventar und ausgetauschte Referenz erzeugen keinen gemischten Erfolg. | PP-01, PP-02A, PP-02C | G-PACK; stabile Referenz/Quellen |
| `S-05` | Eingabe-, ZIP-, Gesamt-, Handoff- und Scanlimits inklusive vieler leerer Verzeichnisse greifen begrenzt. | PP-02A, PP-02B, PP-02C | G-PACK; begrenzte Aufnahme |
| `S-06` | Ausgabe im Eingabebaum, Alias auf Referenz/Eingabedatei und bestehendes Ziel werden ohne Fremdmutation abgelehnt. | PP-02A, PP-02C | G-PACK; Alias-/Zielprüfung |
| `S-07` | Zwei konkurrierende Aufträge mit gleichem Ziel veröffentlichen höchstens einen Gewinner; kein Überschreiben durch TOCTOU-Rennen. | PP-02C | G-PACK; native Pub./Fault-Injection |
| `S-08` | Schreibfehler, Platzmangel, Zugriffsfehler, Fehler beim Schließen und Publikationsfehler hinterlassen keinen freigegebenen Teilinhalt. | PP-02C | G-PACK; native Pub./Fault-Injection |
| `S-09` | Validatorfehler oder absichtlich nachträglich beschädigtes temporäres ZIP verhindert Veröffentlichung; auch bei korrektem ursprünglichem Manifest. | PP-02C | G-PACK; native Pub./Fault-Injection |
| `S-10` | Austausch des temporären Artefakts nach Validierung wird vor Veröffentlichung erkannt. | PP-02C | G-PACK; native Pub./Fault-Injection |
| `S-11` | Kontrollierter Abbruch vor Veröffentlichung; eigene Reste bereinigt oder wahrheitsgemäß genannt, fremde Dateien unverändert. | PP-02C | G-PACK; native Pub./Fault-Injection |
| `S-12` | Injizierter Cleanup-Fehler nach Publikation liefert auch ohne Observer vollständiges API-Ergebnis und bei intakter Ausgabe Erfolgs-JSON/Exit 0 mit Warnung samt Restpfad; kein Verlust von Pfad/Hash, keine Rücknahme oder Doppelveröffentlichung. | PP-02C, PP-03 | G-PACK; Erfolg mit Warnung |
| `S-13` | Beobachtetes Exchange nimmt erst die fertige Ausgabe wahr, nie die technische `.partial`-Datei; `pack` startet keinen Watcher. | PP-02C, PP-08A | G-PACK; separate installierte Beobachtung |
| `S-14` | Instrumentierte Prozess-/Netzwerk-/Dateizugriffe: keine verbotenen Aufrufe, keine Registry-/Repositorywrites, nur expliziter Ausgabebereich. | PP-02A, PP-02C, PP-04C | G-PACK/G-PYZ; Nebenwirkungsinstrumentierung |
| `S-15` | Isolierte Fehlerfallmatrix für Marker 3, Interpreter 5, Pfad/Modus/Budget 4, fehlenden Entrypoint/Manifest 10, Ausgabe 6 und Bindung 9; frühe Pack-Prüfung und entsprechender gemeinsamer Prüfer liefern dieselbe Kategorie. Keine Umdeutung zu fiktivem Result-Write. | PP-02A, PP-02C, PP-03 | G-PACK; isolierte Fehlermatrix |
| `S-16` | Nach bestätigt erfolgreichem Packen scheiterndes Schreiben/Flushen der CLI-Ausgabe führt zu Exit 7, kontrollierte Unterbrechung dieser Ausgabe zu 130; Paket bleibt veröffentlicht, kein zweiter Envelope und kein automatischer Neubau. | PP-03 | G-PACK; nachgelagerte CLI-Ausgabe |
| `S-17` | `FileChangedDuringRead` bei Pack-Referenz, Quelle und eigener temporärer Ausgabe führt ohne Stabilitäts-Retry/Wartebudget zum Abbruch; nötige Sync-/Identitäts-/Hashprüfungen und sichere No-replace-Voraussetzungen bleiben erhalten. | PP-02C | G-PUBLICATION; kein Pack-Retry |
| `S-18` | Kontrollierte Unterbrechung der optionalen Bereinigung nach bestätigter Veröffentlichung lässt geordnet rückgebbare vollständige Erfolgsdaten samt Warnung bestehen; vor der Grenze bleibt der Vorgang abgebrochen. Kein erforderliches Wiederöffnen der schon vom Watcher übernommenen finalen Datei. | PP-02C, PP-03 | G-PACK; Unterbrechung nach Publikation |

#### E – Durchstich und fachlicher Review

| ID | Verbindlicher Nachweis aus Revision 2 | Umsetzung | Gate / Nachweisart |
|---|---|---|---|
| `E-01` | Result aus echter Installation → PYZ entnehmen → `pack` → `inspect`/Referenzvalidierung → regulärer Apply in isoliertem registriertem Repository. | PP-06B, PP-08B | G-WRITE und G-FINAL; echter Durchstich |
| `E-02` | Derselbe Durchstich mit vollständigen Dateien, Diff-Payload und gemischtem Paket; Nutzdateien werden vor Entrypoint geschrieben. | PP-06B, PP-08B | G-WRITE und G-FINAL; echter Durchstich |
| `E-03` | Tatsächliche spätere Repositoryänderung nach Pack-Erfolg wird beim regulären Apply abgelehnt. | PP-02C, PP-06B | G-PACK; späterer State-Mismatch beim Apply |
| `E-04` | Paketkonformer, aber syntaktisch defekter beziehungsweise fachlich fehlerhafter Entrypoint wird nicht als erfolgreich ausgeführt/testiert behauptet. | PP-02C, PP-07 | G-PACK; begrenzter Prüfnachweis |
| `E-05` | Startbar ohne Schreibrechte im PYZ-Verzeichnis; `pack` schreibt nur ins freigegebene Ausgabeziel. | PP-04C, PP-06B | G-PYZ; read-only Runtimeverzeichnis |
| `E-06` | Bootstrap ohne installierten Core, falsche Python-Version, Herkunftskonflikt und fehlende Ausführungsmöglichkeiten werden ehrlich unterschieden. | PP-04C, PP-05B, PP-06B | G-WRITE; frische/ungeeignete Umgebungen |
| `E-07` | Nutzbare CLI-/API-Dokumentationsbeispiele werden funktional geprüft, nicht ihre wortgetreue Darstellung. | PP-03, PP-07 | G-FINAL; ausführbare Beispiele |
| `E-08` | Fachliches Review der finalen Chat-Anweisungen: eine kanonische ZIP, kein Watcher in PYZ, kein erfundener Prüferfolg, kein automatischer Versand. | PP-07 | G-FINAL; fachlicher Review |
| `E-09` | Fachlicher Anweisungs-/Planreview: Hauptdatei plus erklärte Ergänzung werden gemeinsam gewählt, fehlender Satzteil wird gemeldet, echte Konkurrenz bleibt mehrdeutig und die alte Paketversion reaktiviert keinen abgeschlossenen Plan. Kein wortgleicher UI-Test. | PP-00, PP-05B, PP-07 | G-READ/G-FINAL; fachlicher Review |
| `E-10` | **Writerfreigabe-Gate:** Das erste Result des umgestellten Writers ist anhand seiner tatsächlich eingebetteten Anleitung in frischer Umgebung nutzbar; PYZ-Prüfung/Start und `pack` gegen genau dieses Result ohne Wheel-Installation oder Checkout. Nicht bis PP-07/PP-08 aufschieben. | PP-06B | **G-WRITE: vor Freigabe PP-06B** |


## 10. Dokumentationsplan

Dokumentation wird im zugehörigen Commit mitgeführt. PP-07 ist ein übergreifender Abgleich, keine Erlaubnis, den für PP-06B notwendigen Bootstrap nachzureichen. Änderungen an mitgelieferten Ressourcen erfordern neue Artefakte und die betroffenen Prüfungen.

| Dokument | Erster verantwortlicher Schritt | Abschluss / Besonderheit |
|---|---|---|
| `spec/SPECIFICATION_EXTENSION_PYZ_PACK.md` | PP-00 | Revision 2 als normativer Satzteil integrieren; fachliche Änderungen nur als ausdrücklich gekennzeichnete Spezifikationsrevision |
| `planning/pyz-pack/commit-plan.md` | PP-00 | Tatsächliche Schritte/Abweichungen/Nachweise laufend nach vorhandenem Workflow führen; nichts vorab als angewendet markieren |
| `spec/SPECIFICATION_CHANGELOG.md` | PP-00 | Beide Features, gezielte Bestandsausnahmen und Formatwechsel dokumentieren; nicht die gesamte Hauptspezifikation duplizieren |
| `README.md` | PP-00/PP-03 | Packnutzung, Core-PYZ ohne Watcher, normale Installation und aktive Norm-/Planverweise; umstellungsrelevante Teile spätestens PP-06B |
| CLI-Hilfe | PP-03 | Exakte Optionen, keine Ausführung durch pack, explizites Ziel; funktional prüfen, nicht wortgetreu |
| `docs/python-api.md` | PP-02C/PP-03 | Signatur, `PatchPackResult`, Referenzpflicht, Warnungserfolg, In-Process-Herkunft; PP-04C/PP-07 nachführen |
| Neues `docs/pack.md` | PP-02A/PP-02B | Spätestens PP-03 vollständige manuelle Anleitung; unveränderte Apply-Semantik, No-replace ohne Stabilitäts-Retries und getrennte Identitäten |
| `docs/runtime-artifact.md` | PP-04A | Profil, Pflicht-/Ausschlussinventar, Content-ID, Rezept und kanonische PYZ; Legacy nur als historische Lesefähigkeit |
| `docs/runtime-bootstrap.md` | PP-04C | Spätestens PP-05B/PP-06B funktionierender neuer Startweg; alleinige API-Beispiele ersetzen den Loader-/Vertrauenscheck nicht |
| `scripts/runtime_bootstrap.py` | PP-04C/PP-05B | Implementiertes Beispielwerkzeug, nicht nur Dokumenttext; funktionale Fixture- und echte Resulttests |
| `docs/result-format-2.md` | PP-05A | Historisch korrekt lassen, Nachfolger verlinken |
| Neues `docs/result-format-3.md` | PP-05A | Neue geschlossene Schemata, Runtimezustände, Leser-/Writerkompatibilität und Grenzen |
| `docs/result-runtime-production.md` | PP-06A | Automatische vorbereitete Bereitstellung, Pinning, Selbstupdate, dreifacher Roundtrip, Runtime-only-Fallback |
| `docs/result-publication-cifs.md` | PP-06B | Bestandsvertrag für Format 3 erhalten, tatsächliche Nachweise/Status gesondert ausweisen |
| Kanonische `CHAT_INSTRUCTIONS.md` | PP-00/PP-04C/PP-05B | Eigene eingebettete Anleitung muss schon PP-06B bestehen; finale Redaktion/Review in PP-07 |
| Vorhandene Release-/Builddokumentation | PP-04A/PP-08B | Wheel/sdist versus PYZ, getrennte Inventare, finaler Artefakthash und keine behauptete Watcher-PYZ |

Die hier bereits erklärte Aufhebung einzelner alter Regeln kommt aus der Ergänzung, nicht aus dieser Tabelle. Beispiel: Nur `pack` darf neu Pakete erzeugen und seinen ausdrücklich gewählten Inhaltsbaum rekursiv erfassen; die Exchange-Suche bleibt nichtrekursiv. Eine nicht verfügbare Runtime kann einen technischen Fallback erlauben, aber niemals eine inhaltliche Validatorablehnung in einen Erfolg umwandeln.

## 11. Fortschritt, Patch-Bündel und Nachweise

### 11.1 Statusmodell ohne neue Infrastruktur

Der Plan wird als gewöhnliches Markdown geführt. Es gibt keinen neuen Scheduler, Journalservice oder Zähler im Core.

| Status | Erforderliche Bedeutung |
|---|---|
| **geplant** | Aufgabe und Gate definiert, nicht als implementiert nachgewiesen |
| **in Bearbeitung** | Tatsächliche Änderungen laufen; noch kein Abschlussnachweis |
| **lokal geprüft / vorbereitet** | Betroffener echter Stand besteht die vorgeschriebenen lokalen Tests; Patch oder Commit kann vorbereitet sein, ist aber nicht automatisch angewendet |
| **angewendet / gepusht** | Tatsächliches Result beziehungsweise überprüfbarer Commit-/Push-Nachweis bestätigt diesen Zustand |
| **abgenommen** | Alle für diesen Schritt verlangten Nachweise vorhanden, einschließlich noch offener Artefakt-/Plattform-/Writer-Gates |
| **blockiert / Nachweis offen** | Konkreter fehlender Sachverhalt wird genannt; kein erfundener Erfolg |

Ein Arbeitspaket kann inhaltlich implementiert sein, während seine plattformübergreifende Abnahme noch offen ist. Beispiel: PP-04-Importtests sind grün, aber der PYZ-Result-Roundtrip ist noch nicht nachgewiesen. Commitfortschritt und fachliche Abnahme werden daher getrennt geführt.

Ein Vorschlag mit 16 Positionen wird nicht zum falschen Zähler, wenn tatsächlich Schritte zusammengelegt werden. Vor der betroffenen Übergabe wird die Tabelle nachvollziehbar revidiert; bereits angewendete Kennungen bleiben als Historie erhalten. FIX-Kennungen folgen dem bestehenden Vertrag und erhöhen nicht heimlich den Planfortschritt.

### 11.2 Mindestnachweis pro tatsächlich bearbeitetem Schritt

Die folgenden Felder werden in vorhandenen Plan-/Result-/Lognachweisen ausgefüllt, nicht automatisch von `pack` erzeugt:

```text
Schritt / Status:
Tatsächliche Ausgangsreferenz: Dateiname + vollständiger SHA-256
Tatsächliche Bindung: repo_id / base_commit / state_fingerprint / Algorithmus
Verwendeter Normsatz: beide Spezifikationspfade + Revisionen
Planrevision und beauftragter Scope:
Geänderte Dateien / erzeugte Artefakte:
Ausgeführte Testbefehle und tatsächliche getestete Source-/Commitidentität:
Ergebnisse: bestanden / fehlgeschlagen / übersprungen / nicht ausgeführt
Requirement- und Test-IDs sowie reale Test-Node-IDs:
Bei PYZ: Interpreter, tatsächliche Importherkunft, content_id und SHA-256
Bei pack: finaler Pfad, Größe, Paket-SHA-256, Referenz-SHA-256, Prüfumfang
Bei Apply: tatsächlicher Commit / Push / Result; kein vorweggenommener Erfolg
Bei CI: tatsächliche Fälligkeit, Run-ID, vollständiger geprüfter Commit, Jobs
Bei Plattform/CIFS: reale Umgebung und Nachweis oder ausdrücklich offen
Planabweichung / verbleibende Risiken:
```

Keine künstliche Pflicht, eine weitere Commitrunde nur für Statusfelder oder externe CI-IDs zu erzeugen. Vorhandene Ausführungslogs und das tatsächliche Result sind zulässige Nachweisorte. Ein späterer Repositorynachtrag ist ein eigener geprüfter Stand und wird nicht unbemerkt dem früheren CI-Commit gleichgesetzt.

### 11.3 Bündelbildung und Selbstverwendung des neuen Packers

Die **16 vorgeschlagenen Commits sind keine Zusage über die Zahl der Bündel**. Ein Bündel kann null, einen oder mehrere beauftragte Commits enthalten. Die KI darf kleine, lokal prüfbare und sicher zusammengehörige Änderungen zusammenlegen. Bei getrennten Commits werden reale Zwischenstände hergestellt und jeweils vor ihrem Commit geprüft; bereits vor dem Entrypoint ausgebrachte Nutzdateien müssen dabei berücksichtigt werden.

Vor Fertigstellung von `pack` wird der bestehende geprüfte manuelle Verpackungsweg verwendet. Eine noch nicht vorhandene Funktion darf nicht als Voraussetzung ihres eigenen ersten Patches angenommen werden. Nach PP-03 kann eine passende vertrauenswürdige installierte Variante verwendet werden; ab einer tatsächlich bereitgestellten passenden PYZ ist deren `pack` der bevorzugte Weg. Jede Anwendung muss mit dem tatsächlich eingesetzten Prüfer und seinen unterstützten Referenzformaten dokumentiert werden.

Für Entwicklungsübergaben bleibt genau eine abschließend geprüfte kanonische Patch-ZIP maßgeblich. `pack` erzeugt kein neues Result für seine eigene Verpackung, führt keine Tests oder Commits aus und übernimmt nicht die Chat-Bundle-Zählung. Nach einem tatsächlichen Apply kommt der Ergebnisnachweis weiterhin aus dem regulären Result-Bundle des Core.

Wird ein beobachtetes Exchange-Verzeichnis ausdrücklich als Pack-Ausgabe gewählt, kann der separat laufende installierte Watcher die fertige Datei übernehmen. Die interne temporäre Datei muss nach der bestehenden Erkennungspolitik unbrauchbar als fertiges Paket bleiben. Es wird kein zusätzlicher Watcher-Prozess zum Verpacken gestartet.

## 12. Abschluss, Risiken und offene Freigabeentscheidungen

### 12.1 Definition of Done

Die Erweiterung gilt erst als vollständig umgesetzt, wenn die folgende Liste mit tatsächlichen Nachweisen geschlossen werden kann. Aktuell sind sämtliche Implementierungs-/Abnahmefelder offen:

- [ ] Beide Spezifikationen sind gemeinsam eingeordnet, der aktive Featureplan ist eindeutig und der aktuelle Ausgangsstand einschließlich offener Alt-Nachweise wurde abgeglichen.
- [ ] Installiertes `pack`, PYZ-`pack` und `api.pack_patch` verwenden dieselbe vollständige Fachlogik und erfüllen den spezifizierten Eingabe-, Modus-, Namens-, Handoff-, Fehler- und Publikationsvertrag.
- [ ] Kein Git, keine Shell, keine Tests, kein Netzwerk, kein Apply und keine Registrymutation durch die Pack-Operation; nur der explizite Ausgabebereich wird beschrieben.
- [ ] Vollständige Endvalidierung, Hash-/Identitätsbindung und exklusive Veröffentlichung sind nachgewiesen; Cleanup nach Publikation erhält vollständigen Erfolg, CLI-Ausgabefehler sind getrennt.
- [ ] Die PYZ enthält keinen Watcher, aber alle vorgesehenen Core-Funktionen mit unveränderten Voraussetzungen und Sicherheitsregeln, einschließlich Result-Erzeugung aus der PYZ selbst.
- [ ] Normale Installation samt separat installiertem Watcher, Wheel/sdist und repräsentativen Installationswegen bleibt funktionsfähig; neue Results enthalten standardmäßig genau eine passende PYZ.
- [ ] Resultformate 1/2/3, Legacy-Wheel-Datenprüfung, strikte neue Schemata, Budgets, Klassifikation, Archivierung, Recovery und konservative Altbehandlung sind nachgewiesen.
- [ ] E-10 wurde vor Freigabe des ersten neuen Writers mit dessen realer eigener Anleitung bestanden; betroffene finale Ressourcenänderungen wurden danach erneut geprüft.
- [ ] Installation und PYZ materialisieren dieselben kanonischen Bytes; drei isolierte Generationen und request-lokales Pinning/Selbstupdate sind mit finalen Artefakten belegt.
- [ ] Result-Sync-/Retry-/Hash-/CIFS-Vertrag bleibt erhalten; Pack-No-replace ohne Stabilitäts-Retries ist davon unabhängig getestet.
- [ ] Alle 76 spezifizierten Szenarien besitzen ausgeführte Tests oder die ausdrücklich erforderlichen manuellen Nachweise; keine bloßen Text-, Layout- oder Farbtests wurden als Featureabnahme ergänzt.
- [ ] Pflichtinterpreter 3.12/3.14, native Linux-/Windows-/PowerShell-/Docker-Lanes und tatsächliche CIFS-Nachweise sind entsprechend ihrem jeweiligen Vertrag vorhanden; Skips/Nichtausführung sind korrekt eingeordnet.
- [ ] Dokumentation, API, Beispiele, gebaute Ressourcen und Chat-Anweisungen stimmen überein; ein gültiges Paket wird nicht mit funktionierendem Code, Authentizität oder erfolgreicher CI gleichgesetzt.
- [ ] Finale Produktversion, vollständiger geprüfter Commit und konkrete Artefakthashes sind eindeutig; kein späterer ungetesteter Stand wird als derselbe freigegeben.

Diese Abnahme ist eine Feature-/Artefaktfreigabe, **kein impliziter Auftrag zum Veröffentlichen eines Releases, Erzeugen von Tags, globalen Neuinstallieren oder Neustarten des Host-Watchers**.

### 12.2 Entscheidungen und Risiken, die vor der jeweiligen Aktivierung geschlossen werden müssen

| Punkt | Wann / Verantwortlicher Schritt | Vorgehen ohne Vertragsaufweichung |
|---|---|---|
| Tatsächlicher neuer Ausgangsstand und offene CIFS-/CI-Nachweise | PP-00 | Neueste bereitgestellte Nachweise prüfen; historische Angaben nicht überschreiben oder als gegenwärtig raten |
| Ziel-Produktversion | PP-00 vorbereiten; spätestens vor finaler versionierter Artefaktfreigabe | Autorisierte Versionsentscheidung festhalten; nicht automatisch aus Format 3 auf Produktversion 3 schließen |
| Aktuelle Bundlezählung und nächste reguläre CI | PP-00 und jede Auslieferung | Tatsächliche Zählung fortführen; keine Nummer oder zusätzliche CI aus der Commitanzahl ableiten |
| No-replace auf unterstützten Plattformen/Dateisystemen | PP-02C vor öffentlicher Freigabe | Geeignete vorhandene/eng ergänzte Primitive nativ testen; unsicheres Dateisystem ablehnen statt überschreiben |
| Spooling und Quellstabilität bei großen Eingaben | PP-02A/C | Vorhandene Budgets und expliziten Ausgabebereich einhalten; keine Garantie eines atomaren Snapshots beliebig gleichzeitig manipulierter Bäume erfinden |
| Gemeinsame Referenzfakten ohne API-Bruch | PP-01 | Schmaler interner erfasster Wert; bisherige öffentlichen Ergebnisse und Fehler behalten |
| ZIP-Ressourcen und duale Übergangsprofile | PP-04/PP-06 | Alte/neue Identitäten trennen; früheren Writer lauffähig halten; nötigenfalls sichere atomare Zusammenlegung |
| Bootstrap-Vertrauen und bereits importierter fremder Core | PP-04C/PP-05B | Vorcheck und Importherkunft; Ablehnung/frischer Prozess statt unsicherem Entladen; keine Hash-gleich-Authentizität-Behauptung |
| Auswirkung von Dokumentänderungen auf Runtimehash | Jeder Schritt mit kanonischen Ressourcen | Neu bauen, betroffene Checks und Roundtrip erneut ausführen; keine nachträglich ungeprüften Bytes ausliefern |
| Finale CI noch nicht fällig oder Plattform nicht verfügbar | PP-08B | Kein Zusatzlauf ohne Auftrag, kein fingierter Nachweis; Releaseabnahme bleibt offen, lokale Implementierung darf korrekt als solche dokumentiert sein |

Echte Spezifikationskonflikte werden mit genauer Stelle und betroffenem Schritt dokumentiert und vor dessen Aktivierung geklärt. Der Plan ist keine Ermächtigung, dabei zusätzliche Flags, Dienste, Modi, Sicherheitsausnahmen oder ein anderes Patchformat zu erfinden.

## 13. Prüfung dieses Plans und Änderungsprotokoll

### 13.1 Dokumentprüfung bei Erstellung

Die Planung wurde gegen die bereitgestellte Ergänzung Revision 2, die betroffenen Basisverträge und die tatsächlichen einschlägigen Module/Build-/Test-/Workflowpfade des Snapshots abgeglichen. Alle 289 inventarisierten Snapshot-Dateien wurden auf Größe und Git-Blob-ID kontrolliert; beide Spezifikationshashes stehen in Abschnitt 1.2.

Die mechanische Prüfung dieses Markdownplans kontrolliert eindeutige Schrittkennungen, auflösbare und zyklusfreie Abhängigkeiten, Vollständigkeit der 83 Requirement- und 76 Testzuordnungen, eindeutige Writer-Gate-Verantwortung, geschlossene Codeblöcke sowie die unveränderten Eingabedateien. Diese Dokumentprüfung ist ausdrücklich kein Produkt-, Plattform-, Apply- oder CI-Test.

### 13.2 Änderungsprotokoll

| Revision | Datum | Änderung |
|---|---|---|
| 1 | 2026-10-07 | Gemeinsamer Implementierungsplan aus Ergänzung Revision 2 und gebundenem Bestand. Neun Arbeitspakete, zunächst 16 sichere Commit-Schnitte, vollständige Requirement-/Testzuordnung, konkretes Writer-/Bootstrap-Gate und fortgeltende Test-/CI-/Publikationspolicy. Keine Produktimplementierung. |
| 2 | 2026-10-07 | PP-00 / Bundle 024 integriert: aktuelle bytegleiche Referenz vom Pixel, Norm-/Planverweise, offene Alt-Nachweise, vorbereiteter Status; ausdrücklich einmalige CI-only-Ausnahme ohne Tests oder Testinstallation im Apply, ein Commit/Push und automatische parallele CI mit Ergebnisprüfung. |
| 3 | 2026-10-07 | PP-00-FIX1 / Bundle 025: Abbruch von 024 vor Staging/Commit/CI belegt; dirty Result als Reparaturbasis, SSH-Alias-Auflösung statt URL-Stringliste, unveränderte Konfiguration und Fortsetzung der ersten Pixel-CI-only-Ausnahme. Kein Fortschritt vor Apply-/CI-Nachweis. |
| 4 | 2026-10-07 | PP-00-Erfolg und CI 37635401106 aus dem damaligen Result bestätigt; PP-01 in 026 vorbereitet. Die damaligen lokalen Endgates und CI-Pause sind durch Revision 5 für die Pixel-Phase ersetzt. |
| 18 | 2026-10-08 | PP-06B durch tatsächliches Result bestätigt; PP-07 Dokumentreview und funktionale Beispiele mit erneuertem Artefaktgate vorbereitet. |
| 17 | 2026-10-08 | PP-06A durch tatsächliches Result bestätigt; PP-06B atomare Result-3-/PYZ-Produktion mit eigener E-10-Erstnutzung, Core-Parität und drei tatsächlichen Generationen vorbereitet. |
| 16 | 2026-10-08 | PP-05B durch tatsächliches Result bestätigt; PP-06A request-lokale PYZ-Result-Ressourcen und begrenzter Pflichtvorlagenfallback vorbereitet. Produktiver Writer bleibt Format 2. |
| 15 | 2026-10-08 | PP-05A durch tatsächliches Result bestätigt; PP-05B vollständige Verbrauchernachweise, eingefrorene Format-2-Laufzeit und ausführbarer eingebetteter PYZ-Bootstrap vorbereitet. Writer bleibt Format 2. |
| 14 | 2026-10-08 | PP-04C durch tatsächliches Result bestätigt; PP-05A vollständiger Format-3-/Runtime-2-Reader, gemeinsames Budget und strikte Pack-Referenzen vorbereitet. Writer bleibt Format 2. |
| 13 | 2026-10-08 | PP-04B durch tatsächliches Result bestätigt; PP-04C installationsfreier Bootstrap und direkter/API-Core-Start vorbereitet. Native Format-3-Prüfung und Writerumschaltung bleiben nachfolgenden Gates vorbehalten. |
| 12 | 2026-10-08 | PP-04A durch tatsächliches Result bestätigt; PP-04B herkunftsgebundene Verzeichnis-/PYZ-Ressourcen und request-lokaler Provider vorbereitet. Legacy-Writer bleibt erhalten. |
| 11 | 2026-10-08 | PP-03 durch echtes Result bestätigt; PP-04A kanonisches Core-PYZ-Profil, Datenreader, getrennte Buildidentitäten und bytegleicher Release-Kandidat vorbereitet. Format-2-Writer bleibt erhalten. |
| 10 | 2026-10-08 | PP-02B/C durch Result/Commit/Push bestätigt; PP-03 CLI mit Pflichtoptionen, Modesyntax, Version-2-JSON, getrennten Ausgabefehlern und funktionalen Distributions-/Apply-Beispielen vorbereitet. |
| 9 | 2026-10-08 | PP-02A durch Result/Commit/Push bestätigt. PP-02B/C nachvollziehbar in einem Commit für Bundle 032 zusammengeführt; vollständige Pack-API, No-replace, verpflichtende Endvalidierung und funktionale Fehler-/Konkurrenztests. Native Abnahme bleibt offen. |
| 8 | 2026-10-07 | Bundle 030 bestätigt PP-01 samt parallelem Apply-Gate und sauberem Commit/Push. PP-02A: begrenzte unveränderte Inhaltsaufnahme, gemeinsame sichere Handles, Modi/Inventur und kontrollierte Fehlertests; noch keine öffentliche Pack-Funktion. |
| 7 | 2026-10-07 | Bundle 028 scheitert nach Payload-Ausbringung vor Tests/Commit am Whitespace-Gate; FIX3 / 029 setzt die bestätigte dirty Bindung fort. Vollständige Tests ausschließlich parallel, CI nur durch den Nutzer, Schleife ohne feste Korrekturgrenze. |
| 6 | 2026-10-07 | Laptop-Wechsel bestätigt, aktueller clean PP-01-Commit gebunden; vier Legacy-Importfehler reproduziert und konsistente historische Inspection-Fixture für PP-01-FIX2 / Bundle 028 vorbereitet. Reguläre lokale Gates und CI-Termin 029 wieder aktiv. Kein Produktcode oder Normsatz geändert. |
| 5 | 2026-10-07 | PP-01-FIX1 / Bundle 027: unterbrochenes dirty Result ausgewertet; bestehende PP-01-Code-/Testbytes erhalten. Spätere Nutzeranweisung dauerhaft für die Pixel-Phase verankert: keine lokalen Produkttests/Testinstallationen, Commit/Push und automatisch genau eine parallele CI pro Änderung; Fünferregel ausgesetzt bis ausdrücklich bestätigtem Laptop-Wechsel. Kein vorweggenommener Abschlussnachweis. |

---

**PP-00 bis PP-06B sind tatsächlich angewendet. PP-07 wird in Bundle 041
vorbereitet; tatsächlicher Apply bleibt bis zum nächsten Result offen.
PP-08A und PP-08B folgen. Keine Releasefreigabe.**
