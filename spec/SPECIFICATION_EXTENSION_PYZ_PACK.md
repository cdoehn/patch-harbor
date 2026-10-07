# PatchHarbor – Spezifikationserweiterung: Result-PYZ und `pack`

**Dokument-ID:** `PYZ-PACK`  
**Revision:** 2  
**Stand:** 7. Oktober 2026  
**Vorgesehener Ablageort:** `spec/SPECIFICATION_EXTENSION_PYZ_PACK.md`  
**Basisdokument:** danebenliegende [`SPECIFICATION.md`](SPECIFICATION.md), gebundener Bestandsvertrag 1.2.1 einschließlich RIV und der bereits enthaltenen Result-/CIFS-Publikationsregeln  
**Status:** Korrigierter Zielvertrag nach dem Integrationsreview; ersetzt Revision 1 dieser Ergänzung, nicht die Hauptspezifikation; noch kein Implementierungs-, Test- oder Release-Nachweis  
**Ziel-Produktversion:** vor der Release-Umsetzung gesondert festzulegen; dieses Dokument behauptet keine neue veröffentlichte Version

> **Ziel:** Neue Result-Bundles liefern PatchHarbor als direkt mit Python aufrufbare PYZ statt als zu installierendes Runtime-Wheel. Die PYZ enthält den PatchHarbor-Core mit dessen CLI und öffentlicher Python-API, **aber keinen Watcher**. Zusätzlich erhält PatchHarbor das reguläre Unterkommando `pack` und die öffentliche Funktion `api.pack_patch(...)`, um vorbereitete Inhalte als referenzgebundenes, abschließend validiertes Patch-Paket zu erzeugen.

---

## Inhalt

1. Geltung, Vorrang und Ausgangsbasis
2. Verbindliche Produktentscheidungen und Nichtziele
3. Begriffe und unveränderte Einspielsemantik
4. Gemeinsame Architektur und Funktionsumfang
5. PYZ: Ausführung, Inhalt und Paketressourcen
6. PYZ: Herkunft, Identitäten und reproduzierbare Erzeugung
7. Result-Format 3 und Runtime-Metadatenformat 2
8. Kompatibilität, Reader-first-Umstellung und Diagnosefälle
9. `pack`: CLI-Vertrag
10. `pack`: öffentliche Python-API und JSON-Ausgabe
11. `pack`: Referenz, Inhaltsauswahl und Dateirechte
12. `pack`: Manifest, Dateiname und Begleitdokumente
13. `pack`: Ablauf, Veröffentlichung und Fehlerverhalten
14. `inspect`, `validate` und Grenzen des Prüfnachweises
15. Bootstrap und Nutzung im Chat
16. Dokumentationsumfang
17. Teststrategie und verbindliche Testmatrix
18. Umsetzungsplan, Abhängigkeiten und Arbeitspakete
19. Abnahme und Definition of Done
20. Nachweise, Quellen und Änderungsprotokoll

---

## 1. Geltung, Vorrang und Ausgangsbasis

### 1.1 Eigenständige Ergänzung neben der Hauptspezifikation

**GOV-01.** Dieses Dokument wird neben der bestehenden Hauptspezifikation abgelegt. Es ist eine **Erweiterung**, keine vollständige Ersatzspezifikation. Das Basisdokument muss für diese Auslieferung nicht umgeschrieben oder durch eine zusammenkopierte Fassung ersetzt werden.

Für die beiden hier behandelten Features bilden Hauptspezifikation und diese Ergänzung gemeinsam den Zielvertrag. Die Aussage in Abschnitt 35 der bisherigen Hauptspezifikation, dass es keine zusätzliche normative Spezifikationsdatei geben soll, wird **für diese ausdrücklich beauftragte Ergänzung aufgehoben**. Diese Ausnahme berechtigt nicht zum Anlegen beliebig vieler widersprüchlicher Parallelfassungen.

Bei Widersprüchen gilt in absteigender Reihenfolge:

1. Eine spätere ausdrückliche Entscheidung des Nutzers für den betreffenden Sachverhalt.
2. Eine ausdrücklich abweichende Regel dieser Ergänzung, beschränkt auf deren Geltungsbereich.
3. Die fortgeltenden Regeln der Hauptspezifikation und bereits autorisierten sonstigen Erweiterungen.
4. Umsetzungspläne, Beispiele und technische Dokumentation, die den Spezifikationsvertrag nicht eigenständig verändern dürfen.

Ein Implementierungsdetail im vorhandenen Code setzt den Zielvertrag nicht stillschweigend außer Kraft. Ein festgestellter Konflikt ist vor der betreffenden Änderung sichtbar zu dokumentieren.

**GOV-03. Gemeinsamer Spezifikationssatz und Auswahl.** Für den Auftrag `PYZ-PACK` bilden genau diese beiden Dateien den gemeinsam auszuwertenden normativen Dokumentensatz:

```text
spec/SPECIFICATION.md
spec/SPECIFICATION_EXTENSION_PYZ_PACK.md
```

Die Auswahlregel der Hauptspezifikation §26.3 wird für diesen Auftrag gezielt erweitert: Ein ausdrücklicher Planverweis darf den oben erklärten **zusammengehörigen Satz** anstelle eines einzelnen Dokuments benennen. Der zugehörige Implementierungsplan unter `planning/pyz-pack/commit-plan.md` muss beide Pfade ausdrücklich referenzieren. Auch bei einem direkten Auftrag auf Grundlage dieser Ergänzung muss das Basisdokument mitgelesen werden; die allgemeine Suche darf die Ergänzung nicht zugunsten der Hauptdatei fallen lassen.

Die beiden so eingeordneten Dateien sind keine konkurrierenden Kandidaten und lösen allein **kein `SPEC_AMBIGUOUS`** aus. Tatsächlich konkurrierende, nicht aufgelöste Fassungen bleiben mehrdeutig. Fehlt ein ausdrücklich benötigtes Dokument, ist der unvollständige Vertragsstand sichtbar zu melden; die vorhandene Datei ist dann kein stiller Ersatz für den vollständigen Satz.

Der neue Plan wird aufgrund des ausdrücklich beauftragten Features und seines eindeutigen aktiven Planverweises gewählt. Eine noch unveränderte Paketversionsnummer aktiviert weder einen abgeschlossenen Versions-/RIV-/Watcher-Plan noch verdrängt sie `PYZ-PACK`. Die bisherige Behandlung echter Planmehrdeutigkeit und unbekannter Planpositionen bleibt bestehen. Solange der neue Plan noch nicht angelegt ist, darf er nicht als bereits vorhandene Datei ausgegeben werden; dieses Dokument beschreibt bis dahin den vorgesehenen Arbeitsplan.

Plan- und Spezifikationsnachweise müssen beide verwendeten Spezifikationspfade erkennen lassen. Dafür werden die vorhandenen Anweisungen und Dokumentverweise angepasst, **kein Core-Spezifikationsscanner, keine Registry und kein neuer Dienst** eingeführt. Die konkrete optische Darstellung wird nicht zum UI-Testvertrag.

### 1.2 Konkrete Ausgangsbasis

Die Bestandsanalyse dieses Dokuments beruht auf dem bereitgestellten Result:

| Merkmal | Wert |
|---|---|
| Result-Datei | `patch-harbor_Result_055059_1007_b463c4.zip` |
| SHA-256 des gesamten Uploads | `7f400edeee9dcd3369b1ab82a46527cb6f80062cf1a1699018d66f4eafe26dda` |
| Base-Commit des Repository-Snapshots | `bf0b82e5de1eaf3afb2d645d77cd7799e7b6e0b7` |
| Result-Format | `2` |
| Runtime-Metadatenformat | `1` |
| Eingebettetes Artefakt | `patchharbor-1.2.1-py3-none-any.whl` |
| SHA-256 dieses Wheels | `4cd0b56f6cb2c584950015f5542de5c8f53d54120226754fed5a8254844543e8` |
| SHA-256 von `base/spec/SPECIFICATION.md` | `8d75b43bc8739a5c1864ebb48e5d05af1233edb23fd0345d26cf2d3a12609280` |

Die 289 Dateien des `base_entries`-Inventars wurden bei der Dokumenterstellung anhand ihrer Größen und Git-Blob-IDs mit den bereitgestellten Snapshot-Bytes abgeglichen; dabei wurde keine Abweichung festgestellt. Dies ist ein Quellenabgleich, **kein Produkttest**.

Die ausführende Runtime eines Results und der übergebene Repository-Snapshot sind unterschiedliche Gegenstände. Gleiche Versionsstrings beweisen keine Codegleichheit. Dieses Dokument verwendet für Aussagen über die zu ändernde Implementierung den Snapshot unter `base/`, nicht unbesehen das eingebettete Wheel. [B1–B5]

**GOV-02.** Vor der Implementierung muss der dann tatsächlich aktuelle Repositorystand mit dieser Grundlage abgeglichen werden. Bereits fortgeschrittene Arbeiten dürfen nicht auf den alten Snapshot zurückgesetzt werden. Die obigen Kennungen sind Herkunftsangaben dieses Dokuments, **keine fest eingebauten Bindungswerte für spätere Patches**.

Zum Statusabgleich gehören ausdrücklich `planning/watcher-events/commit-plan.md`, `planning/result-publication/commit-plan.md` und `docs/result-publication-cifs.md`. Im gebundenen Snapshot bezeichnet sich der Watcher-Plan als Revision 7, **abgeschlossen**. Der nachfolgende CIFS-Plan beschreibt `CIFS-1` dagegen als in Bundle 023 vorbereitet und führt tatsächlichen Apply/Push, native Windows-Abnahme sowie den Test auf der betroffenen Linux→Windows-CIFS-Freigabe noch als offen. Das sind dokumentierte Statusangaben dieser Quelle, keine hier neu erbrachten Ausführungsnachweise. [B7, B8]

PP-00 muss diese Angaben mit den dann tatsächlich verfügbaren Result-, Commit- und CI-Nachweisen abgleichen. Bereits erledigte Arbeiten werden nicht erneut aktiviert; noch offene Zielplattformnachweise gelten nicht aufgrund lokaler Tests oder eines vorhandenen Quellstands als erledigt. Alte Statuspassagen in der Hauptspezifikation ändern den belegten Planfortschritt nicht automatisch.

### 1.3 Betroffene und fortgeltende Basisregeln

| Basisbereich | Änderung durch diese Ergänzung und ihre Grenze |
|---|---|
| §§ 4 und 32: Installation und öffentliche API | Normale Installation bleibt erhalten; PYZ als zusätzliche Distribution; `pack_patch` wird ergänzt. |
| § 5 und § 36: CLI | Neues Unterkommando `pack`; vorhandene Core-Kommandos bleiben erhalten. |
| §§ 10, 15–17 und 34: Paket, Apply und Modi | Werden wiederverwendet, nicht durch eine neue Einspielstrategie ersetzt. |
| § 19.6a: „Der Core erzeugt keine Patch-Pakete.“ | Ausschließlich für die ausdrücklich aufgerufene neue Pack-Operation aufgehoben; kein automatisches Packen durch `bundle`, `apply` oder den Watcher. |
| §§ 2.2 und 23: keine rekursive Ordnersuche | Begrenzte Ausnahme für die vollständige Inventarisierung des ausdrücklich gewählten Pack-Inhaltsordners. Exchange-/Runner-Suche und die Auswahl angrenzender Projektdateien bleiben unverändert. |
| §§ 19.6a und 21: Chat-Handoff und externe Paketnamen | Technische Erzeugung des Pflichtpaars und des kanonischen Namens darf an `pack` delegiert werden. Der Ersteller verantwortet weiterhin Inhalt und Auslieferung. Die manuelle Namenswahl gemäß `PACK-15` ist eine ausdrückliche Ausnahme nur außerhalb der kanonischen Chat-Auslieferung. |
| § 18.5: Result-Veröffentlichung | Bestehender Sync-/Retry-/Hash-/Diagnosevertrag einschließlich Result-`os.replace()` bleibt für Format 3 erhalten (`MIG-06`). Pack-No-replace und dessen ausdrücklich getrennte Dateisystempolitik gelten nur für `pack` (`PACK-19/23`). |
| §§ 19 und 39: Result | Neuer Writer für Result-Format 3 mit PYZ; Leser für 1/2 bleiben erhalten. |
| § 26.3: Auswahl eines Spezifikationsdokuments | Für `PYZ-PACK` gilt der gemeinsam erklärte Satz nach `GOV-03`, nicht eine Wahl zwischen Hauptdatei und Ergänzung. Echte nicht aufgelöste Konkurrenz bleibt mehrdeutig. |
| § 35: keine zusätzliche normative Spezifikationsdatei | Eng begrenzte Ausnahme für diese beauftragte nebenliegende Ergänzung; keine beliebigen Parallelfassungen. |
| § 38: Runtime-Wheel | Für **neu erzeugte** Results ersetzt durch das PYZ-Profil dieses Dokuments; Legacy-Lesen und normale Installationsartefakte bleiben erhalten. |
| § 40: Bootstrap | Installationsfreier PYZ-Start ersetzt den regulären Wheel-Installationsschritt; der neue Startweg ist Voraussetzung der Writerfreigabe. |
| §§ 22, 33 und 41: Tests/Freigabe | Zusätzliche Funktionsnachweise; keine Aufweichung bestehender Gates oder noch offener Plattformabnahmen. |
| Watcher-Produktvertrag | Kein neues Watcher-Feature; Watcher bleibt Bestandteil der normalen Installation, nicht der PYZ. |

**GOV-04.** Die Ausnahmen in dieser Tabelle gelten nur im jeweils bezeichneten Bereich. Rekursion im vorbereiteten Inhaltsordner macht die Exchange-Suche nicht rekursiv; das Erzeugen eines Patch-Pakets führt es nicht aus. Die Wiederverwendung von Hilfsfunktionen darf die getrennten Publikationsverträge von Results und Patch-Ausgaben nicht vereinheitlichen oder unbemerkt ändern. Gemeinsame Mechanik benötigt dafür explizite Politikparameter oder getrennte schmale Adapter.

Unverändert bleiben insbesondere repositorylokale Konfiguration, Registry-Identität, State-Fingerprint, Replay- und Recovery-Regeln, Sperren, Plattformgrenzen, Entrypoint-Vertrauensmodell, Commit-/Push-Verantwortung und die aktuell autorisierte CI-Policy. Es gibt keine automatische Konfigurationsmigration.

## 2. Verbindliche Produktentscheidungen und Nichtziele

### 2.1 Festgelegter Umfang

**SCOPE-01.** Das Wheel wird **im Runtime-Abschnitt neuer Results** durch genau eine kanonische `.pyz` ersetzt. Wheel und sdist bleiben als normale Installationsartefakte erhalten. Ein neu erzeugtes Result enthält nicht dauerhaft zusätzlich das alte Runtime-Wheel.

**SCOPE-02.** Die PYZ enthält dieselben Core-Implementierungen wie die zugehörige Installation. Sie ist nicht auf `inspect`, `validate` und `pack` beschränkt. Alle übrigen Core-Kommandos bleiben mit ihren regulären Voraussetzungen aufrufbar.

**SCOPE-03.** `patchharbor_watcher` und dessen Startprogramme, Worker-Orchestrierung und Dienstinstallation werden **nicht** in die PYZ aufgenommen. Es gibt keinen neuen PYZ-Watcher-Aufruf und keine PYZ-systemd-Integration.

**SCOPE-04.** `pack` ist ein allgemeines Werkzeug für Menschen, KI-Laufzeiten und andere Programme. Es wird über `patchharbor pack`, `python patchharbor.pyz pack` und dieselbe öffentliche Python-API angeboten.

**SCOPE-05.** Für den ersten `pack`-Vertrag ist ein ausdrücklich benanntes, gültiges **Result-Bundle als Referenz obligatorisch**. Eine zweite Betriebsart mit live ermittelter Repositorybindung wird nicht zusätzlich eingeführt.

**SCOPE-06.** Der Nutzer muss für die Runtime-Bereitstellung keinen zusätzlichen manuellen Schritt ausführen. Die PYZ wird beim regulären Result-Erzeugen automatisch bereitgestellt. Eine normale, unveränderte, unterstützte Installation muss dazu ohne Installer-Cache und ohne Projekt-Checkout in der Lage sein.

### 2.2 Ausdrücklich nicht Bestandteil

Diese Erweiterung enthält keinen automatischen Dateivergleich zwischen bearbeitetem Arbeitsverzeichnis und Result, keine selbstständige Auswahl gewünschter Änderungen, keinen Diff-Generator, keinen automatisch geschriebenen Entrypoint und keinen Commit-Planer.

`pack` installiert nichts, führt kein Skript aus, startet keine Tests, committet oder pusht nicht und wendet kein Paket an. Es beobachtet keine Ordner. Es erhält weder `--apply` noch einen impliziten anschließenden Apply.

Es werden kein neuer Python-Interpreter, keine virtuelle Umgebung, keine externen Runtime-Dependencies, kein allgemeiner Plugin-Loader, kein Netzwerkdienst und keine neue Sicherheits-Sandbox ausgeliefert. Unterstützung älterer Python-Versionen, native EXE-Launcher, Signaturen, eine Multi-Wheel-Abhängigkeitssammlung und ein universeller Runtime-Updater sind ebenfalls nicht Gegenstand dieses Auftrags.

## 3. Begriffe und unveränderte Einspielsemantik

### 3.1 Begriffe

| Begriff | Bedeutung |
|---|---|
| **Result-Bundle** | Vom Core erzeugter Repositorykontext samt Snapshot, Änderungen, Logs und Begleitinformationen; Übergabe zur Bearbeitung. |
| **Patch-Paket** | Sicheres PatchHarbor-ZIP mit `patch.json`, genau einem referenzierten Entrypoint sowie optionalen Nutzdateien; Rückgabe zur späteren Anwendung. |
| **Inhaltsordner** | Vom Ersteller bewusst vorbereitetes Verzeichnis mit Entrypoint und den einzupackenden Nutzdateien. Der Ordnername ist frei wählbar. |
| **PYZ** | Direkt mit einem geeigneten Python-Interpreter aufrufbare ZIP-Anwendung, kein Installations-Wheel. |
| **Handoff-Metadaten** | Passive Begleitdateien unter `PATCHHARBOR_META/`; sie werden nicht angewendet oder ausgeführt. |
| **Erzeuger** | Genau die PatchHarbor-Installation beziehungsweise PYZ, deren Code den aktuellen Auftrag ausführt. |

Die Richtungen bleiben getrennt:

```text
Repository --bundle--> Result-Bundle --Bearbeitung--> vorbereitete Inhalte
vorbereitete Inhalte + Result-Bundle --pack--> Patch-Paket --apply--> Repository
```

### 3.2 Bestehender Apply-Vertrag

**SEM-01.** `pack` erzeugt weiterhin **Patchformat 1**. Dessen Einspielsemantik wird nicht geändert. Der Core prüft Paket und Zielbindung, schreibt die regulären Nutzdateien vor dem Entrypoint an ihre relativen Repositorypfade und führt anschließend den Entrypoint mit dem Repository als Arbeitsverzeichnis aus. Entrypoint, Manifest und passive Handoff-Metadaten werden nicht als gewöhnliche Nutzdateien ins Repository geschrieben. [B2, B3]

Daraus folgen verbindlich:

- Eine vollständige Datei unter `src/module.py` wird vom Core nach `src/module.py` geschrieben. Der Entrypoint muss sie nicht nochmals kopieren.
- Eine Datei unter `patches/change.patch` ist zunächst eine gewöhnliche Nutzdatei. Erst ein entsprechend geschriebener Entrypoint wendet ihren Diff an.
- `payload/` ist **kein spezielles privates Staging-Verzeichnis**. Ein solcher Paketpfad landet als Nutzpfad im Repository.
- Löschungen, Umbenennungen und auftragsspezifische Orchestrierung bleiben Aufgaben des ausdrücklich vorbereiteten Entrypoints, soweit sie nicht bereits durch den bestehenden Core-Vertrag erfolgen.
- Hilfsdateien dürfen nicht mit einer bestehenden Zieldatei kollidieren. Ihre bewusste Platzierung und gegebenenfalls Entfernung vor Tests/Commit muss der Ersteller planen.

**SEM-02.** `pack` interpretiert weder Skriptinhalt noch Dateiendungen als Beschreibung der gewünschten Mutation. Es errät keine Commitanzahl und keine Testergebnisse. Auch ein Diagnosepaket mit nur Entrypoint und null vorgesehenen Commits ist ein normales unterstütztes Patch-Paket.

### 3.3 Beispiel für einen Inhaltsordner

```text
patch-inhalt/
├── apply.sh
├── src/
│   └── geaenderte_datei.py
└── scripts/
    └── neuer_helfer.sh
```

Nach `pack` enthält das ZIP zusätzlich das generierte `patch.json` und die beiden Handoff-Dateien. `src/geaenderte_datei.py` und `scripts/neuer_helfer.sh` sind Nutzdateien; `apply.sh` ist in diesem Beispiel der private Entrypoint. Dieses Beispiel ist keine Vorschrift für die Benennung des Inhaltsordners oder Entrypoints.

## 4. Gemeinsame Architektur und Funktionsumfang

### 4.1 Ein fachlicher Pfad

**ARCH-01.** Die CLI ist ein Adapter auf die öffentliche synchrone Python-API. `pack`, `inspect` und `validate` benutzen gemeinsame Core-Funktionen für Pfade, JSON, Manifest, statischen Entrypoint-Vertrag, Ressourcenbudgets und Bindungsprüfung. Eine zweite, schwächere „KI-Prüfung“ ist unzulässig.

```text
installierte CLI ─┐
PYZ-CLI ──────────┼── öffentliche API ── Application/Core
Python-Aufruf ────┘
```

Ein gemeinsamer interner Service darf geprüfte Referenzbytes und daraus abgeleitete Fakten innerhalb eines Auftrags wiederverwenden. Dazu muss nicht der gesamte öffentliche API-Vertrag um interne Container erweitert werden.

### 4.2 Core-Parität ohne Watcher

**ARCH-02.** Zum PYZ-Funktionsumfang gehören die vorhandenen Core-CLI-Pfade für Konfiguration, Registrierung, Registry-Verwaltung, Kontext, `bundle`, `apply`, den manuellen Runner `fs run`, `inspect`, `validate` und das neue `pack`, einschließlich fortgeltender Core-Optionen und kompatibler Aufrufformen. Die öffentliche Core-API bleibt erhalten.

Neutrale Core-Datenverträge wie `patchharbor.watch_contract` sowie bereits öffentliche, vom installierten Watcher verwendete Core-API-Funktionen dürfen erhalten bleiben. Ihr Vorhandensein ist nicht gleichbedeutend mit dem Mitliefern des Watchers. Es darf keine Importabhängigkeit vom **ausgeschlossenen Paket** `patchharbor_watcher` entstehen.

| Operation | Zusätzliche Voraussetzungen neben passendem Python |
|---|---|
| `inspect`, `validate` ohne Repository, `validate --reference-bundle` | Lesbare lokale Eingabedateien; kein Git oder Shellinterpreter. |
| `pack` | Zusätzlich lesbarer Inhaltsordner und ausdrücklich freigegebener beschreibbarer Ausgabebereich. |
| Repositoryvalidierung, `context`, `bundle` | Reguläre Git-, Repository-, Registry- und Konfigurationsvoraussetzungen. |
| `apply`, `fs run` | Je nach Operation zusätzlich passende Shell, Prozessausführung und reguläre Dateisystemrechte. |

**ARCH-03.** Fehlende Voraussetzungen führen zu den regulären Fehlern der jeweiligen Funktion. Die PYZ darf dafür keine Sicherheitsprüfungen umgehen und kein künstliches Git-Repository registrieren. Die Parität betrifft Softwarefunktionen, nicht die Ausstattung einer Chat-Laufzeit.

## 5. PYZ: Ausführung, Inhalt und Paketressourcen

### 5.1 Aufrufvertrag

**PYZ-01.** Die reguläre Startform lautet:

```bash
python /pfad/patchharbor.pyz --version
python /pfad/patchharbor.pyz inspect /pfad/patch.zip --json
python /pfad/patchharbor.pyz validate /pfad/patch.zip --reference-bundle /pfad/result.zip --json
python /pfad/patchharbor.pyz bundle /pfad/zum/registrierten-repository
```

`patchharbor.pyz` ist hier ein verkürzter Beispielname. Im Result steht der tatsächliche Pfad in den Runtime-Metadaten. Die Aufrufe setzen keine Dateiendungszuordnung des Betriebssystems, keinen ausführbaren Modus der PYZ und keinen Wrapper im `PATH` voraus.

Python ZIP-Anwendungen benötigen einen Root-Einstieg `__main__.py`; der Python-Interpreter kann weitere Module aus dem Archiv laden. Die PYZ bringt den Interpreter nicht selbst mit. [Q1, Q2]

**PYZ-02.** Die Mindestanforderung bleibt für diese Erweiterung **Python 3.12**. `requires_python` muss aus den tatsächlichen Produkt-/Builddaten stammen. Der Einstieg erkennt einen zu alten Python-3-Interpreter vor dem Import inkompatibler Produktmodule und endet mit einem verständlichen Fehler. Eine Zusage für alle künftigen Python-Versionen wird nicht gegeben.

### 5.2 Sicherer empfohlener Start im Chat

Die Bootstrap-Dokumentation beschreibt für einen verfügbaren frischen Prozess vorzugsweise:

```bash
python -I -S -B /absoluter/pfad/patchharbor.pyz inspect /absoluter/pfad/patch.zip --json
```

Die Python-Schalter stehen **vor** dem PYZ-Pfad. Sie vermindern Einflüsse aus Umgebung, Site-Initialisierung und Bytecode-Schreibzugriffen; sie ersetzen weder eine vertrauenswürdige Python-Installation noch eine Sandbox. Die konkrete Kombination ist in den unterstützten CPython-Lanes funktional zu testen. [Q3]

Der einfache Aufruf ohne diese Schalter bleibt unterstützt. Die Anwendung darf keine globale Umgebung verändern, um sich automatisch „zu isolieren“.

### 5.3 Enthaltene und ausgeschlossene Dateien

**PYZ-03.** Das Profil enthält nur inventarisierte reguläre Dateien:

- `__main__.py` im Archivroot;
- den benötigten Code im Namensraum `patchharbor/` einschließlich CLI, öffentlicher API und Paketlesern;
- kanonische Paketressourcen, insbesondere statische Chat-Vorlage, API-Dokumentation, Lizenz, Typing-Marker und das versionierte Reproduktionsrezept;
- die generierte Identitätsdatei des PYZ-Profils.

Nicht enthalten sind `patchharbor_watcher/`, Watcher-Launcher, systemd-Units als auslieferbare Watcher-Ressourcen, virtuelle Umgebungen, Tests, Build-Werkzeuge, Entwicklungsabhängigkeiten, Benutzerdaten, Installer-Caches, alte Results oder komplette eingebettete Runtime-Artefakte.

Im PYZ-Profil gibt es keine `.pth`-Dateien, `sitecustomize.py`, `usercustomize.py`, fremden importierbaren Top-Level-Pakete, nativen Erweiterungen, lokalen Launcher-Kopien, `.pyc` oder `__pycache__`. Das normale Installations-Wheel darf weiterhin seine erforderlichen Installationsmetadaten und den Watcher enthalten. Diese werden nicht ungeprüft in die PYZ kopiert.

Zu den expliziten Pflichtdateien gehören neben dem Root-Einstieg mindestens `patchharbor/__init__.py`, `patchharbor/api.py`, `patchharbor/cli.py`, `patchharbor/py.typed`, `patchharbor/_pyz_identity.py`, `patchharbor/_runtime/pyz-main.py`, `patchharbor/_runtime/pyz-recipe.json`, `patchharbor/_runtime/CHAT_INSTRUCTIONS.md`, `patchharbor/_runtime/python-api.md` und `patchharbor/_runtime/LICENSE`. Sämtliche weiteren tatsächlich benötigten Core-Module werden ebenfalls inventarisiert; die Liste erlaubt keinen unvollständigen Importgraphen. Alte generierte Wheel-Identitäts-/Reproduktionsressourcen sind nicht Teil des neuen PYZ-Inventars. Der Legacy-Wheel-**Lesecode** bleibt dagegen im Core verfügbar.

Eine `.dist-info`-Struktur ist **kein Pflichtbestandteil der PYZ und wird im ersten Profil nicht eingebettet**. Der PYZ-Code darf seine eigene Version und seine eigenen Ressourcen nicht aus einer zufällig installierten Distribution gleichen Namens beziehen.

### 5.4 ZIP-taugliche Ressourcen

**PYZ-04.** Ressourcen werden aus genau der geladenen Distribution gelesen. Zugriffe, die aus `__file__` ein vermeintlich reales Paketverzeichnis konstruieren, müssen für den PYZ-Weg ersetzt werden. Geeignet sind verankerte Resource-Reader, etwa `importlib.resources.files(...)`, beziehungsweise kontrollierte Archivleser. Paketressourcen können innerhalb eines ZIPs liegen; ein echter Dateisystempfad ist nicht generell vorhanden. [Q4]

Das betrifft insbesondere `chat_instructions.py`, `runtime_artifact.py`, die gemeinsame Result-Ressourcenbindung und die neue Paketgenerierung. Ein defekter eigener Ressourcensatz darf nicht zu einer Vorlage aus CWD, dem Zielrepository oder einer anderen PatchHarbor-Installation führen.

Für `inspect`, referenzbasiertes `validate` und die Vorlagenverwendung von `pack` ist kein Entpacken des vollständigen Python-Pakets erforderlich. Temporäre Materialisierung einzelner Ressourcen ist nur zulässig, wenn die jeweilige Operation sie fachlich benötigt und ihre Nebenwirkungsgrenzen eingehalten werden. Die lesenden Prüffunktionen dürfen dadurch keine fachlichen Schreibzugriffe erhalten.

### 5.5 Python-only-Aufruf

**PYZ-05.** Ein Aufruf der öffentlichen API aus einer Python-Sitzung ohne Terminal-Unterprozess ist unterstützt. Nach kontrollierter Aufnahme des **zuvor geprüften** PYZ-Pfads in den Importpfad müssen `api.inspect_patch`, `api.validate_patch` und `api.pack_patch` verwendbar sein. ZIP-Import wird vom Python-Importsystem unterstützt. [Q2]

Dabei gelten folgende Grenzen:

- Die Bootstrap-Vorprüfung und Vertrauensentscheidung erfolgen vor dem Import.
- Bereits geladene `patchharbor`-Module aus einer anderen Herkunft dürfen nicht unbemerkt weiterverwendet werden.
- Bei Herkunftskonflikt wird der direkte Zugang abgelehnt oder ein ausdrücklich verfügbarer frischer Prozess verwendet. Kein erzwungenes `sys.modules`-Löschen als vermeintlich sicherer Versionswechsel.
- Der geprüfte Importpfad muss für spätere Lazy-Imports und Ressourcen verfügbar bleiben. Ein Zurücksetzen nach dem Erstimport ist kein vollständiges Entladen.
- Ein vom Bootstrap geänderter Importpfad wird nicht als Sandbox oder als garantiert nebenwirkungsfreie Prozessisolation dargestellt.

Der bevorzugte In-Process-Weg ist die öffentliche API, nicht ein erneuter CLI-Start über `runpy`. Ein dokumentierter Aufrufadapter darf kleine Vorprüfungen bündeln, aber keine zweite Implementierung der Produktfunktionen enthalten.

## 6. PYZ: Herkunft, Identitäten und reproduzierbare Erzeugung

### 6.1 Herkunft und automatische Bereitstellung

**PYZ-06.** Die PYZ gehört zum ausführenden PatchHarbor, nicht zum bearbeiteten Zielrepository. Die normale Build-Pipeline bereitet alle zur reproduzierbaren PYZ-Materialisierung erforderlichen Daten vor und liefert sie mit der regulären Installation aus.

Während `bundle` oder eines Apply-Auftrags dürfen weder Buildbackend, `pip`, `uv`, Git zur Artefakterzeugung, ein Paketindex noch ein Netzwerkzugriff gestartet werden. Das Zusammenstellen einer ZIP aus bereits vorbereiteten, gehashten Ressourcen ist eine begrenzte Datenoperation und kein spontaner Quellbuild.

Ein offizieller Build muss denselben kanonischen PYZ-Kandidaten erzeugen beziehungsweise verifizieren können. Ein Cache ist eine Optimierung, keine Voraussetzung. Das Löschen von Installer-Caches darf die Runtime-Bereitstellung nicht verhindern.

### 6.2 Drei getrennte Identitäten

**PYZ-07.** Zu unterscheiden sind:

| Identität | Bedeutung |
|---|---|
| `version` | Produkt-/Distributionversion; allein kein eindeutiger Buildnachweis. |
| `content_id` | SHA-256 über den versionierten fachlichen PYZ-Inventarvertrag einschließlich funktionaler Ressourcen. |
| `artifact.sha256` | SHA-256 über alle Bytes des tatsächlich gelieferten kanonischen PYZ-Archivs. |

Das neue Content-ID-Verfahren heißt `patchharbor-pyz-content-v1`. IDs des bisherigen Wheel-Verfahrens `patchharbor-runtime-content-v1` werden nicht als PYZ-IDs weiterverwendet. Der Ausschluss des Watchers und die Aufnahme des Programmeinstiegs sind reale Profiländerungen.

`source_commit` wird nur ausgegeben, wenn seine Zuordnung zum Build belegt ist; ansonsten ist der Wert `null`. Eine Herkunftsangabe oder eine Prüfsumme ist keine digitale Signatur und keine Releasefreigabe.

### 6.3 Reproduktionsrezept und zyklusfreie Ableitung

**PYZ-08.** Das neue Rezept liegt im kanonischen Profil unter:

```text
patchharbor/_runtime/pyz-recipe.json
```

Es hat genau diese Felder:

| Feld | Vertrag |
|---|---|
| `marker` | `patch-harbor-pyz-recipe` |
| `format_version` | Integer `1` |
| `distribution` | `patchharbor` |
| `version` | Tatsächliche gültige Produktversion gemäß bestehendem Versionsprofil. |
| `requires_python` | Tatsächlicher Python-Vertrag, in dieser Erweiterung `>=3.12`. |
| `profile` | `patchharbor-core-no-watcher-v1` |
| `content_id_algorithm` | `patchharbor-pyz-content-v1` |
| `content_id` | 64 kleingeschriebene Hex-Zeichen. |
| `source_commit` | Belegte volle Git-Objekt-ID oder `null`. |
| `entries` | Nach `path` sortierte Liste der Nutzinventareinträge. |

Jeder Eintrag enthält genau `path`, `source`, `size` und `sha256`. `size` ist eine nichtnegative Ganzzahl, kein Boolean; `sha256` hat 64 kleingeschriebene Hex-Zeichen. Pfade, Kollisionen, Dateitypen und Ressourcenbudgets werden vor dem Materialisieren vollständig geprüft.

Für gewöhnliche Paketdateien gilt `source == path`. Der Root-Einstieg darf aus der mitgelieferten Ressource `patchharbor/_runtime/pyz-main.py` stammen. Diese Ressource ist selbst inventarisiert; ihre Bytes müssen mit den Bytes von `__main__.py` übereinstimmen. Weitere freie Quellpfadumleitungen sind in diesem Profil nicht erlaubt.

Die kanonische JSON-Kodierung ist ASCII-kompatibles UTF-8 ohne BOM: lexikografisch sortierte Objektschlüssel, `ensure_ascii=True`, Separatoren `,` und `:`, keine nicht endlichen Zahlen, genau ein abschließendes LF. Doppelte JSON-Schlüssel werden abgelehnt. Dies führt die bestehende kanonische Rezeptkodierung fort, aber nicht deren altes Wheel-Inventar. [B4]

Die Ableitung erfolgt in dieser Reihenfolge:

1. Alle vorgesehenen Inventardaten außer dem Rezept selbst und der generierten Datei `patchharbor/_pyz_identity.py` bestimmen.
2. `producer_id` als SHA-256 der kanonischen Kodierung eines Objekts mit genau `algorithm`, `version`, `requires_python`, `profile`, `source_commit` und diesen `entries` bilden. `algorithm` ist `patchharbor-pyz-producer-v1`.
3. Die Identitätsdatei aus diesem Wert deterministisch generieren. Ihre Bytes lauten: `# Generated for the PatchHarbor PYZ profile.` plus LF, anschließend `RESOURCE_ID = "<producer_id>"` plus LF.
4. Die Identitätsdatei mit Größe und Hash in das sortierte Inventar aufnehmen.
5. Das Rezept mit allen Feldern außer `content_id` kanonisch kodieren; dessen SHA-256 wird `content_id`.
6. Das endgültige Rezept einschließlich `content_id` kodieren und dem Archiv als genau ein zusätzlicher Eintrag hinzufügen.
7. Das vollständige Archiv deterministisch erzeugen und erst danach `artifact.sha256` berechnen.

Das Rezept inventarisiert sich nicht selbst. Die vollständigen Rezeptbytes werden durch den äußeren Artefakthash und den strikten Archivvertrag erfasst. Der Artefakthash wird nicht in das Archiv hineingeschrieben. Es gibt keine Selbsthash-Schleife und kein Wheel-`RECORD` im PYZ-Profil.

Die neue Datei `patchharbor/_pyz_identity.py` ist vom bisherigen Wheel-Identitätsmodul getrennt. Legacy-Wheel-Rezepte und deren Identitätsprüfung bleiben als Datenvertrag unverändert. Das bei normalem Paketimport geladene PYZ-Identitätsliteral muss zum vom Provider geprüften PYZ-Ressourcensatz passen. Ein fremder oder während des Prozesses unpassend geänderter Satz wird nicht als eigene Runtime ausgegeben.

### 6.4 Kanonische ZIP-Regeln

**PYZ-09.** Für das erste PYZ-Profil gelten:

- `ZIP_STORED`, keine innere Kompression; die äußere Result-ZIP komprimiert die Zugabe.
- Keine Shebang-Vorsilbe, kein EXE-Stub, keine Archivkommentare, keine Präfix-/Suffixdaten und kein angehängtes zweites Archiv.
- Alle Einträge reguläre Dateien, Namen ASCII und mit `/`, lexikografisch sortiert; keine separaten Verzeichniseinträge.
- Fester DOS-Zeitstempel `1980-01-01 00:00:00`, `create_system=3`, regulärer Unix-Modus `0644`, keine Extra-Felder oder Kommentare.
- ZIP-Versionfelder `20`, keine Verschlüsselung, keine Data-Descriptor- oder ZIP64-Variante; CRC, Größen, Flags, lokale Header, Zentralverzeichnis und Endverzeichnis müssen widerspruchsfrei zum kanonischen Profil passen.
- Vollständige zentrale und lokale Inventarprüfung, keine Akzeptanz versteckter Zusatzeinträge aufgrund gefälschter Endverzeichniszähler.

Diese Determinismusregeln sind PatchHarbor-Produktentscheidungen; das allgemeine ZIP-Anwendungsformat wäre weniger eng. [Q1, Q5]

### 6.5 Selbstupdate und Roundtrip

**PYZ-10.** Vor möglichen Apply-Mutationen werden Erzeugeridentität, benötigte Runtime-Ressourcen und statische Chat-Vorlage gemeinsam request-lokal fixiert. Ein späterer Snapshot darf einen neueren Repositoryzustand zeigen; die Runtime darf dabei nicht mit Ressourcen einer anderen Version vermischt werden.

**PYZ-11.** `bundle` aus einer PYZ muss wiederum ein Result mit derselben kanonischen PYZ erzeugen können. Weder benötigt es dazu eine installierte PatchHarbor-Distribution, noch darf es sein vollständiges Archiv als zusätzliche Ressource in eine neue PYZ einbetten.

Der Materializer verwendet das endliche vorbereitete Inventar. Mindestens drei aufeinanderfolgende isolierte Result-/PYZ-Generationen müssen identische PYZ-Bytes, Größe und SHA-256 liefern. Unterschiedliche Result-Zeitstempel, Run-IDs und Logs sind davon nicht betroffen.

Eine unveränderte Installation und die aus ihren Ressourcen erzeugte PYZ müssen für denselben Core-Profilstand dieselbe kanonische PYZ materialisieren. Die normalen Installations-Wheel-Bytes müssen nicht mit der PYZ identisch sein.

### 6.6 Ressourcenlimits

**PYZ-12.** Die bisherigen engen Runtime-Budgets werden zunächst fortgeführt:

| Grenze | Wert |
|---|---:|
| Gesamte PYZ-Datei | 16 MiB |
| Summe innerer Dateiinhalte | 32 MiB |
| Innere Einträge einschließlich Rezept | 1.000 |
| Rezept | 1 MiB |
| Äußeres `runtime/runtime.json` | 128 KiB |

Die allgemeinen Result-/ZIP-Grenzen gelten zusätzlich. Beim Lesen der in einem Result eingebetteten PYZ wird kein unabhängiges unbegrenztes Ressourcenbudget eröffnet. Äußere Inhalte, inneres Inventar und expandierte Daten werden nach dem vorhandenen gemeinsamen Ressourcenmodell bilanziert. Zu große Runtime-Zugaben dürfen nicht durch Weglassen von Repositorydateien passend gemacht werden.

## 7. Result-Format 3 und Runtime-Metadatenformat 2

### 7.1 Versionierung statt Umdeutung alter Felder

**FMT-01.** Der neue Result-Writer erzeugt **Result-Format 3**. Das neue `runtime/runtime.json` hat **Formatversion 2**. Das bisherige Feld `wheel` wird nicht mit PYZ-Inhalt befüllt und nicht unter derselben alten Formatversion semantisch umgedeutet.

Das Patchformat bleibt `1`. Environment-/Handoff-Format bleibt `1`. Bestehende CLI-Ausgabeversionen werden nicht allein wegen des neuen Result-Dateiformats angehoben.

### 7.2 Result-Struktur

```text
manifest.json
context.json
CHAT_INSTRUCTIONS.md
environment.json
logs/...
base/...
changes/staged.patch
changes/unstaged.patch
untracked/...
runtime/runtime.json
runtime/patchharbor-<version>.pyz     # nur bei status=embedded
```

Bis auf Result-Formatnummer und Runtime-Vertrag bleibt das versionsbezogene Inventar des bisherigen Resultformats erhalten. Die übrigen Pflichtdateien, Snapshot-, Änderungs- und Logprüfungen werden nicht gelockert.

**FMT-02.** `manifest.json.runtime` besitzt in Format 3 genau die Schlüssel `status`, `reason`, `metadata` und `artifact`:

```json
{
  "status": "embedded",
  "reason": null,
  "metadata": {
    "path": "runtime/runtime.json",
    "size": 1234,
    "sha256": "<64 lowercase hex characters>"
  },
  "artifact": {
    "type": "pyz",
    "path": "runtime/patchharbor-<version>.pyz",
    "size": 123456,
    "sha256": "<64 lowercase hex characters>"
  }
}
```

Die Zahlen und Winkelklammerwerte in diesem Schema-Beispiel sind Platzhalter, keine prüfbaren Testdaten. `metadata` ist ein Deskriptor mit genau `path`, `size`, `sha256`; `artifact` hat zusätzlich genau `type: "pyz"`. Größen sind nichtnegative Ganzzahlen, keine Booleans. Vorhandene Artefakte sind nicht leer. Digest- und Pfadwerte müssen zu den tatsächlichen Bytes passen.

### 7.3 Runtime-Metadaten

**FMT-03.** Das Runtime-Metadatenobjekt besitzt genau die folgenden Felder:

| Feld | Wert bei `embedded` |
|---|---|
| `marker` | `patch-harbor-runtime` |
| `format_version` | Integer `2` |
| `status` | `embedded` |
| `reason` | `null` |
| `distribution` | `patchharbor` |
| `version` | Tatsächliche Erzeugerversion. |
| `requires_python` | Tatsächlicher Python-Vertrag. |
| `profile` | `patchharbor-core-no-watcher-v1` |
| `content_id` | Geprüfte vollständige Content-ID des PYZ-Rezepts. |
| `content_id_algorithm` | `patchharbor-pyz-content-v1` |
| `artifact` | Mit dem äußeren Manifest identischer Artefaktdeskriptor. |
| `runtime_dependencies` | Leere Liste. |
| `provenance` | Objekt mit genau `mode`, `source_commit`, `recipe_format_version`. |
| `capabilities` | Objekt mit genau `operations`, `patch_formats`, `result_formats`. |

`provenance.mode` lautet `canonical_resources`, `source_commit` entspricht dem Rezept, `recipe_format_version` ist `1` für das neue ausdrücklich durch seinen Marker identifizierte PYZ-Rezept.

Für das erste vollständig freigegebene Profil lautet `capabilities`:

```json
{
  "operations": ["inspect_patch", "validate_patch", "pack_patch"],
  "patch_formats": [1],
  "result_formats": [1, 2, 3]
}
```

`operations` benennt wie der bisherige Runtime-Vertrag die vorgesehenen **Chat-Werkzeugoperationen**. Es ist **keine Sperrliste für die übrige Core-CLI oder API**. Deren Funktionsumfang wird durch das Profil und `ARCH-02` festgelegt. Ein Hersteller darf damit insbesondere nicht das funktionierende `bundle` aus der PYZ herauslassen.

Wheel-Tags wie `py3-none-any` und das alte Feld `tags` entfallen im Metadatenformat 2. Sie werden nicht als PYZ-Kompatibilitätsnachweis ausgegeben.

### 7.4 Zustand `unavailable`

**FMT-04.** Bei einem ausschließlich die Runtime betreffenden Bereitstellungsfehler wird, soweit das vollständige Result weiterhin erzeugbar ist, geschrieben:

- `status: "unavailable"` und ein erlaubter maschinenlesbarer `reason`;
- `artifact: null` sowohl im Manifest als auch in `runtime.json`;
- kein PYZ- und kein Wheel-Eintrag im Runtime-Verzeichnis;
- im Metadatenobjekt `profile`, `content_id`, `content_id_algorithm`, `runtime_dependencies`, `provenance` und `capabilities` jeweils `null`;
- `version` und `requires_python` nur soweit zuverlässig bekannt, ansonsten `null`;
- der korrekte Deskriptor der tatsächlich geschriebenen `runtime/runtime.json`.

Die fortgeführten Gründe sind `source_not_prepared`, `source_changed`, `artifact_missing`, `artifact_mismatch`, `artifact_corrupt`, `artifact_unsupported`, `resource_limit` und `read_error`. Ein Grund wird aus dem beobachteten Fehler gewählt, nicht zur Verschleierung eines anderen Resultfehlers.

### 7.5 Strikte vollständige Prüfung

**FMT-05.** Reader prüfen äußere und innere Deskriptoren, Version, Profil, Inventar, Rezept, Code-/Ressourcenhashes und Archivstruktur konsistent. Unter `runtime/` sind nur die für den jeweiligen Zustand deklarierten Dateien erlaubt. Unbekannte Felder in den geschlossenen Objekten, Duplikate, zusätzliche Artefakte und widersprüchliche Angaben werden abgelehnt.

Beim Prüfen wird die beschriebene Runtime **nicht importiert oder ausgeführt**. Auch die Begleitdokumentation ist Dateninhalt, keine auszuführende Anweisung. Ein hashkonsistent manipuliertes Paket kann durch diesen Mechanismus nicht als authentisch bewiesen werden.

## 8. Kompatibilität, Reader-first-Umstellung und Diagnosefälle

### 8.1 Lesematrix

**MIG-01.** Neue Reader unterstützen die bisherigen Results 1 und 2 sowie das neue Format 3 entsprechend deren jeweiligem Vertrag:

| Eingang | Verhalten des neuen Readers |
|---|---|
| Gültiges Format 1 ohne Runtime | Weiterhin als Referenz lesbar. |
| Gültiges Format 2 mit Wheel | Nach dem **alten Wheel-Vertrag** vollständig prüfen; nicht als PYZ interpretieren. |
| Gültiges Format 2 mit `unavailable` | Weiterhin als Referenz lesbar. |
| Gültiges Format 3 mit PYZ | Nach dem neuen Vertrag vollständig prüfen. |
| Gültiges Format 3 mit `unavailable` | Als Referenz lesbar; keine Runtime-Verfügbarkeit behaupten. |
| Deklarierte, aber defekte Runtime | Vollständige native Referenzprüfung schlägt fehl. |
| Unbekanntes Result- oder Runtimeformat | Konservativ als nicht unterstützt behandeln; nicht als Patch ausführen. |

Der Legacy-Wheel-Reader bleibt ein Datenleser. Er installiert das alte Wheel nicht. Neue Produktions-Results enthalten nur die neue Runtimeform.

### 8.2 Reader vor Writer

**MIG-02.** Die Lesefähigkeit für Format 3 muss mit künstlichen Testfixtures vollständig integriert sein, **bevor** der produktive Writer auf Format 3 umgeschaltet wird. Das schließt Referenzvalidierung, Result-Verifikation, Exchange-Klassifikation, Archivierungsnachweise und Recovery-Leser ein.

Ein Zwischenstand, der 1/2/3 lesen kann und weiterhin Format 2 schreibt, ist zulässig. Ein Writer, dessen eigener Scanner oder Nachweisleser die erzeugten Results nicht sicher versteht, ist unzulässig.

**Reader-first schließt einen funktionsfähigen Bootstrap als Writer-Gate ein.** Vor einer auslieferbaren Writerumschaltung müssen auch Runtime-Provider, der installationsfreie Bootstrap und die **tatsächlich in neuen Results eingebettete kanonische Anleitung** dieselbe neue Format-/Artefaktkombination unterstützen. Diese minimale Bootstrap-Integration erfolgt vor PP-06 oder atomar mit PP-06, niemals erst in PP-07.

Das erste mit dem umgestellten Writer erzeugte Result muss in einer frischen Umgebung anhand seiner eigenen Anleitung nutzbar sein: geprüfte PYZ entnehmen, ohne Wheel-Installation und ohne zufällig installierten Core starten und ein Paket gegen genau dieses Result erzeugen und validieren. Der entsprechende Durchstich (`E-10`, mit den Funktionsbausteinen aus `E-01/E-06`) ist **Freigabegate für PP-06**, nicht nur eine spätere Endabnahme. Eine gemeinsame atomare Umsetzung ist erlaubt; ein separat ausgelieferter Stand mit PYZ-Result und Wheel-only-Anleitung ist es nicht.

Die Aktivierung des Format-3-Writers erfolgt an der gemeinsamen Result-Erzeugungsgrenze für manuelle Bundles, Apply-Erfolg und -Fehler, Dry-Run und die durch den **installierten** Watcher ausgelösten Core-Aufträge. Für letztere wird kein Watcher in die PYZ aufgenommen.

### 8.3 Altprogramme und vorhandene Paketformate

**MIG-03.** Altprogramme müssen neue Format-3-Results zumindest konservativ behalten oder ablehnen. Mit eingefrorenen Altleser-Fixtures ist nachzuweisen, dass sie diese weder ausführen noch aufgrund eines unbewiesenen Erfolgshinweises löschen/archivieren.

Die neuen Patch-Pakete bleiben Format 1. Ihre Kompatibilität mit älteren Apply-Engines wird anhand des bereits vorhandenen Handoff- und Modivertrags beschrieben und getestet, nicht allein aus der Formatnummer abgeleitet. Eine neue generelle Bootstrap- oder Migrationsautomatik für sehr alte Runner wird nicht eingeführt.

### 8.4 Diagnose hat Vorrang vor Runtime-Komfort

**MIG-04.** Eine fehlende PYZ darf nicht den einzigen ansonsten vollständigen Snapshot oder das Ausführungsprotokoll vernichten. Ein Runtime-only-Fehler führt nach Möglichkeit zum gekennzeichneten `unavailable`-Result. Fehlende kanonische Pflichtvorlagen, defekte Snapshotdaten oder gescheiterte Veröffentlichung sind davon nicht pauschal ausgenommen.

Ein begrenzter erneuter Publikationsversuch ohne Runtime ist nach dem bestehenden Vertrag zulässig. Es gibt keine Endlosschleife, kein stilles Downgrade auf ein anderes Resultformat, keinen Rückfall auf ein fremdes Wheel und kein Verbergen von Abbruchsignalen. Scheitert die sichere Result-Erzeugung insgesamt, gelten die bisherigen Fehlerprioritäten und Notfallregeln.

**MIG-05.** Runtime-Defekt, allgemein gültige Repositoryreferenz und archivierungs-/recoveryfähiger Erfolgsbeleg bleiben getrennte Bewertungen. Ein bereits bestehender ausdrücklich begrenzter Daten-Fallback darf für Diagnose und den dokumentierten manuellen Übergabeweg erhalten bleiben. `pack` und ein vollständiger `validate --reference-bundle` dürfen diesen schwächeren Fallback **nicht heimlich als vollständige erfolgreiche Referenzprüfung benutzen**.

**MIG-06. Bestandsschutz der Result-Publikation.** Der Formatwechsel ersetzt ausschließlich den beschriebenen Format-/Runtime-Inhalt, nicht den Publikationsvertrag aus Hauptspezifikation §18.5 und `docs/result-publication-cifs.md`. Dieser gilt für Format 3 sowohl mit eingebetteter PYZ als auch mit `unavailable`. Er umfasst insbesondere die Eigentums-/No-follow-Prüfung eigener temporärer Results, Synchronisation, die unveränderte endliche typisierte Wiederholung bei `FileChangedDuringRead`, das über Verifikation und spätere Hash-Reads geteilte Wartebudget sowie die durchgängige Bindung an den vollständig verifizierten Hash. Result-Veröffentlichung, begrenzter Runtime-Fallback, Recovery-Beleg und sichere Notfalldiagnose behalten ihre bisherigen Zuständigkeiten und Prioritäten. [B1, B7]

Die in der Bestandsquelle festgelegten Pausen und die begrenzte CIFS-Budgetanpassung werden nicht in einer zweiten abweichenden Implementierung nachgebaut. Weder ein Runtime-Fallback noch ein späterer Hash-Read erhält still ein neues unbegrenztes Wartebudget. Fremde oder ausgetauschte Dateien, Symlinks, Inhalts-, Bindungs- und Ressourcenfehler erhalten keine Retry-Freigabe; Entrypoint, Commit und Push bleiben außerhalb der Wiederholung.

Die spätere Implementierung muss diese Bestandsfälle mit Format-3-Results regressionstesten. Lokale Fault-Injection und native Windows-Läufe ersetzen keinen realen Nachweis auf der betroffenen Linux→Windows-CIFS-Freigabe. Die **davon abweichende** engere Erstfassung für `pack` ist ausdrücklich in `PACK-23` festgelegt; sie darf nicht auf Result-Writer übertragen werden.

## 9. `pack`: CLI-Vertrag

### 9.1 Syntax und Optionen

**PACK-01.** Das reguläre Unterkommando lautet:

```text
patchharbor pack CONTENT_DIRECTORY
    --reference-bundle RESULT_ZIP
    --entrypoint RELATIVE_PATH
    (--output OUTPUT_FILE | --output-dir OUTPUT_DIRECTORY)
    [--mode RELATIVE_PATH=OCTAL_MODE ...]
    [--json] [--verbose | -v] [--no-color]
```

Die Schreibweise der gemeinsamen Darstellungsoptionen folgt der bestehenden Parserstruktur; sie erzeugt keinen zweiten CLI-Adapter. Die PYZ erhält dieselben Argumente nach ihrem Dateipfad.

| Parameter | Vertrag |
|---|---|
| `CONTENT_DIRECTORY` | Pflicht; ausdrücklich vorbereiteter Inhaltsordner. |
| `--reference-bundle` | Pflicht; ausdrücklich benannte Result-Datei. |
| `--entrypoint` | Pflicht; sicherer relativer Paketpfad innerhalb des Inhaltsordners, mit `/` als Separator. |
| `--output` | Expliziter endgültiger Dateipfad; schließt `--output-dir` aus. |
| `--output-dir` | Expliziter vorhandener Zielordner; `pack` generiert den kanonischen Dateinamen. |
| `--mode` | Optional wiederholbar; expliziter Unix-Modus für eine übergebene Datei, etwa `scripts/helper.sh=0755`. |
| `--json` | Strukturierte Ausgabe ohne Konsolenprosa auf stdout. |

Genau eine Ausgabeoption ist erforderlich. Es gibt keinen Standard-Ausgabeort über Registry, CWD oder Exchange. Relative ausdrücklich übergebene Dateisystempfade werden einmal gegen das Aufrufverzeichnis aufgelöst; daraus folgt keine automatische Repositorywahl.

Nicht angeboten werden in diesem Umfang `--repository`, `--force`, `--overwrite`, `--skip-validation`, `--no-validate`, `--apply`, `--no-handoff`, freie Bindungsüberschreibungen, ein frei übergebenes Manifest, URL-Eingaben oder STDIN-Paketinhalte.

### 9.2 Beispiele

Kanonischer Dateiname aus dem Result:

```bash
patchharbor pack ./patch-inhalt \
  --reference-bundle ./result.zip \
  --entrypoint apply.sh \
  --output-dir ./ausgabe \
  --mode scripts/neuer_helfer.sh=0755 \
  --json
```

Derselbe Vorgang mit der PYZ:

```bash
python ./runtime/patchharbor-<version>.pyz pack ./patch-inhalt \
  --reference-bundle ./result.zip \
  --entrypoint apply.sh \
  --output-dir ./ausgabe \
  --json
```

Bewusst gewählter manueller Dateiname bei leerem Referenzsuffix:

```bash
patchharbor pack ./patch-inhalt \
  --reference-bundle ./result.zip \
  --entrypoint apply.sh \
  --output ./ausgabe/mein-patch.zip
```

Ein vorhandenes Referenzsuffix `.txt` erfordert beim expliziten Dateinamen beispielsweise `mein-patch.zip.txt`. Es wird bei `--output` nicht heimlich angehängt oder entfernt.

### 9.3 Ausgabeziel und Kollisionsregeln

**PACK-02.** Der Zielordner beziehungsweise der Elternordner von `--output` muss bereits existieren und für die sichere Veröffentlichung geeignet sein. `pack` erzeugt nicht automatisch einen Verzeichnisbaum oder eine Exchange-Konfiguration.

Der endgültige Dateipfad darf weder mit der Referenzdatei noch mit einer Eingabedatei oder der verwendeten Runtime identisch sein. Ziel und temporäre Dateien dürfen nicht im Inhaltsordner oder einem seiner Unterverzeichnisse liegen. Physische Aliasbeziehungen und relevante Symlink-/Reparse-Point-Fälle sind mitzuberücksichtigen.

Ein vorhandenes Ziel wird niemals überschrieben. Das gilt auch für ein während des Vorgangs neu entstehendes Ziel, ein Symlinkziel und zwei konkurrierende `pack`-Aufträge mit demselben expliziten Namen. Es gibt keine unbegrenzten automatischen Wiederholungen und keine zufällige Umbenennung, die dem Aufrufer verschwiegen wird.

### 9.4 Formale CLI-Fehler

Fehlende Pflichtoptionen, widersprüchliche Optionen und syntaktisch ungültige `--mode`-Angaben werden als Nutzungsfehler behandelt. Ein Modus hat in der CLI genau vier oktale Ziffern, beispielsweise `0644`. Doppelte Pfadangaben bei `--mode` werden abgelehnt, nicht nach „letzter Wert gewinnt“ aufgelöst.

Ein Dateisystempfad zum Inhalts- oder Ausgabeordner kann normale plattformeigene Syntax haben. Paketinterne Pfade wie der Entrypoint und die Modusschlüssel unterliegen dagegen ausdrücklich dem sicheren Archivpfadvertrag; Backslashes werden dort nicht still in `/` umgeschrieben.

## 10. `pack`: öffentliche Python-API und JSON-Ausgabe

### 10.1 API-Signatur

**PACK-03.** Im unterstützten Import-Namensraum `patchharbor.api` wird ergänzt:

```python
def pack_patch(
    content_directory: str | os.PathLike[str],
    *,
    reference_bundle: str | os.PathLike[str],
    entrypoint: str,
    output: str | os.PathLike[str] | None = None,
    output_directory: str | os.PathLike[str] | None = None,
    modes: Mapping[str, int] | None = None,
    observer: ProgressObserver | None = None,
) -> PatchPackResult:
    ...
```

Genau eine von `output` und `output_directory` muss gesetzt sein. `modes` enthält sichere relative Paketpfade und numerische POSIX-Modi, etwa `{"scripts/helper.sh": 0o755}`. Mutierbare Eingabemappings werden am Requestanfang in eine eigene geprüfte Darstellung übernommen. Ein nachträgliches Ändern des Aufrufermappings darf die laufende Pack-Operation nicht verändern.

Die Operation ist synchron, ohne Beobachter still und liefert erst nach erfolgreicher Veröffentlichung ein Erfolgsresultat. Keine CLI wird als Unterprozess aufgerufen. Wie im bestehenden API-Vertrag sind falsche Argumenttypen `TypeError`; ungültige reine Argumentkombinationen, Leerwerte oder formale Werte sind `ValueError`. Fachliche Paket-/Sicherheitsprüfungen werden dagegen auch bei früher Erkennung als `PatchHarborError` mit dem passenden bestehenden `FailureReason` nach `PACK-22` gemeldet, nicht pauschal in `ValueError` umgewandelt.

Nach bestätigter Veröffentlichung gilt die Erfolgsschwelle aus `PACK-20`: Ausschließlich nachlaufende Bereinigungsprobleme ergeben ein vollständiges `PatchPackResult` mit Warnung, auch ohne Observer. Sie sind keine fehlgeschlagene Pack-Operation und dürfen Pfad, Größe, Hash und Validierungsnachweis nicht unzugänglich machen. Unerwartete Programmfehler werden dadurch nicht allgemein zu Erfolgen umklassifiziert.

Insbesondere sind Bytepfade, leere Pfade, `bool` als Dateimodus und fremde Observer-Typen ungültig. Ein API-Aufruf ändert CWD, Umgebungsvariablen oder globale Konfiguration nicht.

### 10.2 Ergebnisobjekt

**PACK-04.** `PatchPackResult` ist ein öffentlich exportierter unveränderlicher typisierter Wert mit mindestens diesem verbindlichen Vertrag:

| Attribut | Typ und Bedeutung |
|---|---|
| `path` | `Path`: absoluter endgültiger Veröffentlichungspfad. |
| `package_id` | `UUID`: einmalig für diesen Verpackungsauftrag erzeugte UUID v4. |
| `created_at` | Zeitzonenbewusster UTC-`datetime` des Verpackungsauftrags. |
| `validation` | `PatchValidationResult` der tatsächlich finalisierten ZIP-Bytes, mit `scope=reference`. |
| `warnings` | Unveränderliches `tuple[str, ...]` der fachlichen Pack-Warnungen, einschließlich relevanter Prüfhinweise und gegebenenfalls nachlaufender Cleanup-Warnungen gemäß `PACK-20`. |
| `package_sha256` | Abgeleitete Property aus `validation.inspection.package_sha256`. |
| `package_size` | Abgeleitete Property aus `validation.inspection.package_size`. |
| `reference_sha256` | Abgeleitete vollständige Referenz-SHA-256 aus der Validierung. |

Für ein erfolgreiches Pack-Resultat sind `binding_matches == True`, ein nichtleerer Referenzhash und ein geprüftes Manifest obligatorisch. Doppelt abgeleitete Werte dürfen keine abweichende zweite Wahrheit erhalten. `package_id` und `created_at` werden nicht als neue Felder in das geschlossene `patch.json` geschrieben.

Dieses Ergebnis ist auch dann vollständig zurückzugeben, wenn nach bestätigter Veröffentlichung lediglich ein eigener temporärer Zweitname nicht entfernt werden konnte. Die Warnung benennt den verbleibenden eigenen Pfad; sie behauptet nicht, das Paket sei unveröffentlicht. Dafür wird kein zusätzlicher dauerhafter Statusspeicher oder Recovery-Dienst eingeführt.

Der Veröffentlichungspfad ist ein Nachweis des abgeschlossenen Vorgangs, keine Zusage, dass ein fremder Prozess die Datei später nicht verschiebt oder verändert.

### 10.3 JSON-Vertrag

**PACK-05.** Für erfolgreich geparste CLI-Aufrufe mit `--json` wird der vorhandene versionierte Envelope mit `output_version: 2` und `command: "pack"` verwendet:

```json
{
  "output_version": 2,
  "command": "pack",
  "success": true,
  "result": {
    "path": "<absolute published path>",
    "package_id": "<canonical UUID v4>",
    "created_at": "<UTC timestamp ending in Z>",
    "package_sha256": "<64 lowercase hex characters>",
    "package_size": 123456,
    "reference_sha256": "<64 lowercase hex characters>",
    "validation": {
      "inspection": {},
      "scope": "reference",
      "binding_matches": true,
      "context": {},
      "reference_sha256": "<64 lowercase hex characters>",
      "checked_at": "<UTC timestamp ending in Z>",
      "not_checked": ["<existing unchecked aspects>"]
    },
    "warnings": []
  },
  "error": null,
  "process_exit_code": 0
}
```

Das Beispiel zeigt Feldnamen und Platzhalter; die leeren Objekte `inspection` und `context` sind ausschließlich Platzhalter, keine gültigen vollständigen Erfolgsdaten. In der echten Ausgabe enthält `validation` das vollständige bestehende `validation_json_result`-Objekt einschließlich Inspektion, Kontext, `checked_at` und `not_checked`. Es werden keine Konsolentexte geparst oder Kennungen gekürzt.

Bei einem fachlichen Fehler **vor der bestätigten Veröffentlichung** gilt `success: false`, `result: null` und ein reguläres strukturiertes Fehlerobjekt. Es wird kein Result-Bundle für `pack` erzeugt; `emergency_diagnostics_path` bleibt im übernommenen Fehlerenvelope grundsätzlich `null`. Parserfehler vor vollständiger Argumentauswertung behalten den bestehenden Usage-Vertrag und Exitcode 2; diese Erweiterung baut nicht die gesamte Argumentparser-Fehlerausgabe um.

Bei einem ausschließlich nachlaufenden Bereinigungsproblem bleibt dagegen `success: true`, `error: null`, `process_exit_code: 0` und das **vollständige** `result` erhalten; der Hinweis steht in `result.warnings`. Das gilt bei normaler CLI-Ausgabe ebenso wie bei direktem API-Aufruf ohne Observer.

Die Zustellung der CLI-Ausgabe ist ein eigener nachfolgender Schritt. Scheitert nach bestätigter Veröffentlichung das Schreiben oder Flushen von stdout mit einem behandelten I/O-Fehler, endet der CLI-Adapter mit dem bestehenden Ausgabefehlercode `7`; bei einer kontrollierten Unterbrechung der Ausgabe mit `130`. Das beschreibt die nicht erfolgreich abgeschlossene Ausgabe, **nicht** einen erneut fehlgeschlagenen Paketbau. Soweit stderr noch verwendbar ist, nennt eine bestmögliche Diagnose den bereits veröffentlichten Pfad und dessen Hash. Es wird weder ein zweiter Fehler-Envelope mit `result: null` an eine teilweise geschriebene Erfolgsantwort angehängt noch ein erneuter Bau gestartet. Bei defekter Ausgabeverbindung oder Prozessabsturz kann keine vollständige JSON-Zustellung garantiert werden. Die übrigen Kommandos erhalten dadurch keinen neuen globalen Ausgabevertrag.

Die normalen `inspect`-/`validate`-Ergebnisschemata werden dadurch nicht inkompatibel verändert. Konsolenformulierungen, Zeilenreihenfolge, Farben und Symbole sind kein neuer stabiler Testvertrag.

## 11. `pack`: Referenz, Inhaltsauswahl und Dateirechte

### 11.1 Eine explizite, vollständig geprüfte Referenz

**PACK-06.** Die Referenzdatei wird über den gemeinsamen kontrollierten Result-Reader stabil erfasst und entsprechend ihrer Formatversion geprüft. Aus derselben Erfassung stammen Bindung, Suffix, Umgebungsdaten und Referenzhash. Es ist unzulässig, das Manifest aus einer Dateiversion und die Begleitdaten aus einer später unter demselben Namen liegenden anderen Dateiversion zu lesen.

Die Bindung verwendet genau die tatsächlich im Referenzkontext festgehaltenen Werte:

```text
repo_id
base_commit
state_fingerprint
fingerprint_algorithm
```

Insbesondere werden weder `expected_*` eines fehlgeschlagenen Apply-Laufs noch verkürzte Konsolenkennungen als Ersatz verwendet. Ein gültiges Dirty-, Dry-Run-, Fehler- oder Diagnose-Result kann Referenz sein. Ein erfolgreiches Vor-Apply, ein sauberer Git-Zustand oder eine geplante Commitanzahl sind keine zusätzliche Pack-Voraussetzung.

**PACK-07.** Zur Referenzprüfung werden kein Git-Repository erzeugt, keine Registry gelesen/angelegt und keine Pfade des Zielrechners auf dem Pack-Rechner aufgelöst. Der vollständige native Reader-Vertrag einschließlich einer vorhandenen Runtime bleibt erforderlich. Bei deklarierter, aber defekter Runtime scheitert `pack`; bei einem gültigen Result mit `unavailable` darf es fortfahren.

### 11.2 Bewusste vollständige Inhaltsauswahl

**PACK-08.** Der Inhaltsordner ist die ausdrückliche Auswahl des Erstellers. Es gibt keine implizite `.gitignore`-Auswertung, keine automatische Aufnahme angrenzender Dateien, keinen Repositoryscan und keine selbstständige Filterung nach Dateityp.

Alle zulässigen regulären Dateien unterhalb dieses Ordners werden genau einmal aufgenommen. Leere Verzeichnisse werden nicht als Repositoryänderung repräsentiert; ihr Wegfall wird als zusammengefasster fachlicher Hinweis erkennbar. Der Scan und seine Ressourcen müssen auch bei vielen leeren Verzeichnissen begrenzt bleiben.

Folgende Inhalte werden nicht still verworfen, sondern führen zur Ablehnung:

- Root-`patch.json`, einschließlich case-ambiger Schreibweisen; diese Datei erzeugt ausschließlich `pack`.
- Der reservierte Root-Namensraum `PATCHHARBOR_META` in beliebiger Groß-/Kleinschreibung; die beiden Dateien darin erzeugt ausschließlich `pack`.
- Verbotene interne Pfadsegmente, unzulässige Dateitypen, unsichere Pfade oder Kollisionen nach dem bestehenden Paketvertrag.

Eine normale Nutzdatei namens `CHAT_INSTRUCTIONS.md` außerhalb des reservierten Namensraums ist nicht automatisch eine Handoff-Datei und wird nicht durch heuristische Filter entfernt. Damit bleiben auch Änderungen an solchen Repositorydateien möglich.

Ein beliebiges komplettes Entwicklungsverzeichnis ist nicht automatisch ein geeigneter Inhaltsordner. Enthält es etwa `.git` oder `.patchharbor`, wird es abgelehnt. Der Packer repariert es nicht still durch Weglassen.

### 11.3 Pfade, Dateitypen und stabile Bytes

**PACK-09.** Für alle Paketpfade wird der vorhandene Format-1-Pfadvalidator wiederverwendet. Dazu gehören ASCII-Segmentregeln, maximal 128 Zeichen je Segment und 512 Zeichen je Gesamtpfad, Verbot von Traversal, absoluten Pfaden, Laufwerks-/UNC-/Backslashpfaden, internen `.git`-/`.patchharbor`-Segmenten, reservierten Gerätenamen und case-ambigen Zielkollisionen. [B2, B3]

Paketpfade dürfen nicht durch Normalisierung von unzulässigen Eingaben „gerettet“ werden. Unicode-Hostpfade zum Inhaltsordner sind davon zu unterscheiden; ein unterhalb dieses Ordners enthaltener nicht zulässiger Archivname bleibt ein Fehler.

Verzeichnisse werden kontrolliert traversiert. Symlinks, Hardlinks, Reparse-Point-Umleitungen, Geräte, FIFOs, Sockets und andere Sondertypen werden für die aufgenommenen Inhalte nicht unterstützt. Insbesondere dürfen Symlinkwechsel zwischen Scan und Öffnen nicht zum Lesen einer Datei außerhalb des vorbereiteten Baums führen. Erlaubte explizite Wurzelpfadauflösung ist von verbotenen Umleitungen unterhalb dieser Wurzel zu trennen.

Der vorhandene sichere Dateisystemadapter ist zu verwenden beziehungsweise gezielt zu ergänzen; kein zweiter ungeschützter `rglob`-/`read_bytes`-Pfad neben der bestehenden Schutzlogik. Nachweisbare Hardlink-Aliase beziehungsweise mehrere Links einer Quelldatei werden abgelehnt; notwendige **interne** Veröffentlichungstechniken sind davon getrennt.

**PACK-10.** Dateien werden einmal kontrolliert in einen begrenzten stabilen Bytebestand übernommen. Größen, Identitäten und relevante Dateitypen werden vor/nach dem Lesen geprüft. Bekannte Hinzufügungen, Löschungen, Austausche oder Inhaltsänderungen während der Erfassung führen zum Abbruch. Vor der Finalisierung erfolgt eine erneute Konsistenzkontrolle des erfassten Quellinventars.

Der Vertrag setzt voraus, dass der vorbereitete Inhaltsordner während des Auftrags nicht absichtlich parallel bearbeitet wird. Ein über gewöhnliche Dateisystemzugriffe realisierter Scan ist kein garantierter atomarer Snapshot eines beliebig gleichzeitig manipulierten Verzeichnisbaums. Maßgeblich sind die nachweisbar erfassten Bytes; es darf keinen Erfolg mit einer **bekannten** Inkonsistenz geben.

### 11.4 Unveränderte Nutzdateien und Entrypoint

**PACK-11.** Nutzdateien und Entrypoint werden bytegenau übernommen. Keine automatische Änderung von Zeilenenden, Encoding, BOM, Einrückung, Shebang, Skriptmarker oder Skriptinhalt. Binärdateien sind nach den allgemeinen Grenzen zulässig. Enthaltene Archive bleiben gewöhnliche Nutzdateien und werden nicht rekursiv ausgepackt.

Der Entrypoint muss eine vorhandene reguläre Datei im Inhaltsinventar sein und den bestehenden statischen Bash-/PowerShell-Vertrag einschließlich Pflichtmarker erfüllen. Es wird kein weiterer Interpretertyp neu eingeführt. Fehlende Marker oder widersprüchliche Metadaten werden nicht vom Packer ergänzt.

Die Erkennung darf keinen auf dem Pack-Rechner installierten Bash-/PowerShell-Interpreter verlangen. Statische Parserprüfung ist von Syntaxprüfung durch die tatsächliche Shell und von späterer Ausführung zu unterscheiden.

### 11.5 Dateirechte

**PACK-12.** Dateirechte des Pack-Rechners sind kein verlässlicher Zielvertrag. Für alle übernommenen regulären Dateien wird standardmäßig der sichere **angeforderte Modus `0644`** in das Paket geschrieben. Manifest und Handoff-Dateien erhalten ebenfalls `0644`.

Über `--mode` beziehungsweise `modes` kann der Ersteller für vorhandene Eingabedateien explizite Modi anfordern. Es gelten unverändert die vorhandenen `validate_payload_mode`-Regeln: keine setuid-/setgid-/sticky-Bits und keine neu angeforderten Schreibrechte für Gruppe oder Andere. Werte werden weder still maskiert noch als harmlose Hostattribute ignoriert.

Ein Modusschlüssel muss exakt einen vorhandenen Entrypoint- oder Nutzdateipfad benennen. Verzeichnisse, generierte Dateien, nicht vorhandene Dateien und reservierte Pfade sind unzulässig. Ein Modus für den Entrypoint beeinflusst nicht dessen Zielablage: Er bleibt privat und wird durch den festgelegten Interpreter ausgeführt.

Auf POSIX erhält eine vorhandene reguläre Zieldatei beim späteren Apply nach dem bestehenden Vertrag ihren bereits beobachteten sicheren lokalen Modus; ein angeforderter ZIP-Modus ist kein allgemeiner `chmod`-Befehl. Bei neu angelegten Dateien kann der explizite angeforderte Modus wirken. Das Verhalten auf Windows folgt weiter dem dortigen Core-Vertrag. [B2, B3]

Damit kann ein Windows- oder Chat-Ersteller ein neues ausführbares POSIX-Skript ausdrücklich mit `0755` verpacken, ohne zufällige Rechte aus seiner eigenen Umgebung zu übernehmen. Eine gewünschte Modusänderung an einer bereits vorhandenen Zieldatei muss entsprechend dem bestehenden Apply-/Entrypoint-Vertrag geplant werden.

### 11.6 Ressourcen und Grenzen

**PACK-13.** Die bestehenden Grenzen gelten auch für das erzeugte Paket:

| Grenze | Wert |
|---|---:|
| Größenwarnung | Bestehende 10-MiB-Schwelle und deren vorhandene Vergleichssemantik. |
| Einzelner Eingabeinhalt/ZIP-Eintrag | 256 MiB |
| Fertiges ZIP als späteres Eingabeartefakt | 256 MiB |
| Summe unkomprimierter ZIP-Inhalte | 512 MiB |
| ZIP-Einträge insgesamt | 1.000 |
| Je generierte Handoff-Datei | 128 KiB |

Manifest, Entrypoint und Handoff-Dateien zählen mit. Ein Inhaltsordner darf nicht erst durch unkontrolliertes vollständiges Einlesen gegen die Limits geprüft werden. Zusätzlich wird der lokale Scan auf **10.000 besuchte Dateisystemknoten einschließlich Verzeichnissen** begrenzt; dies ist ein eigener Pack-Scan-Schutz, keine Änderung des allgemeinen Patchformats.

Referenz und Ausgabepaket behalten ihre jeweiligen gemeinsamen Reader-Budgets. Begrenztes Puffern beziehungsweise Spooling ist zulässig, aber kein unkontrolliertes Vervielfachen sämtlicher Inhalte. Größenüberschreitungen werden nicht durch stilles Auslassen von Dateien oder Abschalten der Endvalidierung umgangen.

## 12. `pack`: Manifest, Dateiname und Begleitdokumente

### 12.1 Manifest

**PACK-14.** `pack` erzeugt genau eine Root-Datei `patch.json` in UTF-8 ohne BOM und mit exakt den sieben Feldern des bestehenden geschlossenen Formats:

```json
{
  "marker": "patch-harbor",
  "format_version": 1,
  "repo_id": "<full value from the verified reference>",
  "base_commit": "<full value from the verified reference>",
  "state_fingerprint": "<full value from the verified reference>",
  "fingerprint_algorithm": "<full value from the verified reference>",
  "entrypoint": "<validated relative entrypoint path>"
}
```

UUID-/Git-ID-/Fingerprintformate und der unterstützte Algorithmus werden durch die gemeinsame Manifest-/Referenzprüfung bestimmt. Es gibt keine CLI-Override-Möglichkeit für diese vier Werte. Paket-ID, Suffix, Dateirechte, Prüfergebnis oder beabsichtigte Git-Commits werden nicht als zusätzliche Manifestfelder eingeführt.

### 12.2 Dateiname und Suffix

**PACK-15.** Nach erfolgreicher formaler Argumentprüfung werden **für beide Ausgabearten** einmal pro Verpackungsauftrag eine UUID v4 als `package_id` und ein zeitzonenbewusster UTC-Zeitpunkt als `created_at` festgelegt. Beide Werte bleiben während des Auftrags unverändert und werden bei Erfolg zurückgegeben. Sie werden weder aus dem Referenz-Result übernommen noch bei einem internen Prüfschritt neu erzeugt.

Nur bei `--output-dir` dienen diese Werte zusätzlich zur automatischen Namensbildung. Der Name lautet nach dem bestehenden Chat-Vertrag:

```text
<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip<bundle_suffix>
```

`ID6` sind die ersten sechs Zeichen der vollständigen Paket-UUID, ohne Auslassungszeichen. Der Bezug ist die Paket-ID, nicht die Run-ID des Referenz-Results. `bundle_suffix` stammt aus dem geprüften `context.json`; fehlend in einem zulässigen Legacy-Result oder leer bedeutet kein Suffix. Die existierende Suffixvalidierung wird wiederverwendet.

Der Repository-Anzeigename stammt vorrangig aus dem geprüften Environmentfeld `repository_name`. Fehlt es, darf der letzte Pfadbestandteil des als **Text** aufgezeichneten Repositorypfads nach dessen POSIX-/Windows-Syntax verwendet werden. Der fremde Pfad wird dabei niemals lokal aufgelöst. Gibt es keinen brauchbaren Namen, wird `repository` mit einem fachlichen Hinweis verwendet.

Für den automatisch erzeugten Dateinamen wird der Anzeigename deterministisch portabel gemacht: nicht in `[A-Za-z0-9._-]` enthaltene Zeichen werden durch `_` ersetzt; Randpunkte werden entfernt; der Präfix wird auf höchstens 64 Zeichen begrenzt und danach erneut von Randpunkten bereinigt. Leerer Präfix wird `repository`; ein reservierter Windows-Gerätename erhält vorangestelltes `_`. Anpassungen werden als Hinweis erkennbar, verändern aber weder Repositoryidentität noch originale Environmentwerte.

Bei `--output` ist der Dateiname eine ausdrückliche manuelle Wahl und muss nicht dem automatischen Schema entsprechen. Er muss jedoch die Endung `.zip` plus das Referenzsuffix besitzen und darf kein nach der vorhandenen Policy temporärer Downloadname sein. Es erfolgt keine automatische Umbenennung. `package_id` und `created_at` sind trotzdem wie oben vorhanden. **Für Chat-Patch-Auslieferungen bleibt das kanonische Schema vorgeschrieben**; dort ist `--output-dir` der bevorzugte Weg. Dies ist eine eng begrenzte manuelle Namensfreiheit, keine Änderung des Patchformats.

Die bestehende dreistellige `PATCHHARBOR-BUNDLE-NR` aus dem Chat-/Planvertrag ist davon unabhängig: Sie ist weder die Paket-UUID noch deren `ID6`, die Referenz-Run-ID oder eine Git-Commitanzahl. Der bestehende Chat-/Planprozess verantwortet diese Nummer nach seinen bisherigen Regeln. `pack` führt keinen Zähler, erfindet keine Nummer und schreibt den Entrypoint nicht nachträglich um. Für manuelle Pakete wird kein neuer Chat-Zählerdienst oder zusätzlicher Aufbereitungsschritt vorgeschrieben. [B1 §26.6/§26.8]

### 12.3 Passive Handoff-Dateien

**PACK-16.** Jedes neu mit `pack` erzeugte Paket enthält genau:

```text
PATCHHARBOR_META/CHAT_INSTRUCTIONS.md
PATCHHARBOR_META/environment.json
```

Es wird der vorhandene reine Renderer wiederverwendet. Die statische Vorlage stammt aus dem verifizierten Ressourcensatz des **ausführenden Packers**. Die bereits result-spezifisch gerenderte Root-Anleitung aus dem Referenz-Result wird nicht als statische Vorlage verwendet; dadurch wird eine rekursive Vervielfältigung alter Kontexte vermieden.

Die dynamischen Zielangaben stammen dagegen aus der **geprüften Referenz**, nicht aus der Hostumgebung des Packers:

| Feld/Gruppe | Herkunft beziehungsweise Änderung |
|---|---|
| `marker`, `format_version` | Bestehender Environmentvertrag `patch-harbor-environment`, `1`. |
| `bundle_type` | Wird `Patch`. |
| `bundle_filename` | Endgültig gewählter Paketdateiname. |
| `repository_context` | Exakt die vier Bindungswerte des generierten Manifests. |
| `bundle_suffix` | Geprüfter Referenzsuffix. |
| `captured_at` | Ursprüngliche Ziel-Erfassungszeit unverändert; unbekannt bleibt `null`. |
| `repository_name`, `repository_path` | Bekannte aufgezeichnete Zielangaben, nicht lokal auflösen. |
| `exchange_directory`, `output_directory` | Aufgezeichnete Zielrechnerdaten; nicht durch den lokalen Pack-Ausgabepfad ersetzen. |
| `runtime` | Bekannte Zielsystem-/Interpreter-/Tooldaten aus dem Result; nicht durch Pack-Hostdaten ersetzen. |
| `run_id` | Soweit vorhanden die Referenz-Run-ID; im Patch-Kontext ausdrücklich Herkunft des Ziel-Snapshots, keine neue Apply-Run-ID. |
| `filename_schemas`, `filename_timezone` | Bestehender Vertrag; UTC und die gültigen Schemata. |

Zusätzliche zulässige passive Referenzangaben dürfen übernommen werden, sofern sie strikt als endliche JSON-Daten behandelt werden, nicht mit den verbindlichen Feldern kollidieren und die Größen-/Renderregeln einhalten. Es gibt keine beliebige Auswertung solcher Daten als Code oder lokale Pfade.

Bei einem gültigen Legacy-Result ohne Environmentpaar werden sicher bekannte Angaben aus dessen geprüften Kontext-/Run-Fakten übernommen. Unbekannte Betriebssystem-, Tool-, Shell- und Zielpfadangaben bleiben `null`; keine Erforschung des Pack-Rechners als vermeintlicher Ersatz. Das Fehlen solcher optionalen Altdaten wird als Hinweis ausgegeben, verhindert aber nicht automatisch die Erstellung.

Der aktuelle Pack-Zeitpunkt steht getrennt im API-Ergebnis. Er wird nicht als neue Messung des Zielrechners ausgegeben. Scheitert die Erzeugung des Pflichtpaars oder fehlt die eigene kanonische Vorlage, scheitert `pack`; es gibt kein stilles Paket ohne Begleitdateien.

### 12.4 ZIP-Erzeugung

**PACK-17.** Der Packer schreibt Standard-ZIP-Dateien mit geordnetem regulärem Dateiinventar und den explizit festgelegten Modi. Er erzeugt keine zusätzlichen Dateieinträge für Verzeichnisse, keine Verschlüsselung und keine rekursive Paketstruktur.

Für die erste Implementierung werden `ZIP_DEFLATED` mit festem Kompressionslevel 6, lexikografische Archivpfadreihenfolge, feste ZIP-Zeitstempel `1980-01-01 00:00:00`, Unix-Dateityp „regulär“, die nach `PACK-12` festgelegten Modi sowie leere Extra-Felder und Kommentare verwendet. Die notwendigen ZIP-Version-/Flagfelder müssen den gemeinsamen Reader-Vertrag erfüllen. ZIP64 ist innerhalb der genannten Grenzen nicht erforderlich und wird nicht erzeugt.

Anders als bei der kanonischen PYZ wird keine generelle Bytegleichheit von neu gepackten Patches über beliebige Python-/Kompressionsbibliotheksversionen versprochen. Zufällige Host-mtimes, Hostrechte oder absolute Quellpfade dürfen trotzdem nicht in die Paketstruktur einfließen. Bei gleichen erfassten Eingaben und kontrollierter Metadaten-/Kompressionsumgebung muss das Resultat reproduzierbar testbar sein.

## 13. `pack`: Ablauf, Veröffentlichung und Fehlerverhalten

### 13.1 Verbindliche Reihenfolge

**PACK-18.** Der erfolgreiche Ablauf hat diese fachlichen Phasen:

1. API-/CLI-Argumente prüfen und ausdrücklich benannte Pfade einmal auflösen.
2. Referenz stabil erfassen, vollständig lesen und Bindung sowie benötigte passive Kontextdaten fixieren.
3. Eigenen kanonischen Vorlagensatz binden; Zielnamen, Suffix und Ausgabepolitik festlegen.
4. Inhaltsbaum kontrolliert inventarisieren, Entrypoint und Modi zuordnen, unzulässige Inhalte vor Ausgabe zurückweisen.
5. Alle erforderlichen Eingabebytes begrenzt und stabil erfassen; Größen-/Pfad-/Dateitypgrenzen prüfen.
6. Manifest und beide Handoff-Dateien aus den fixierten Daten erzeugen.
7. Eigenes temporäres Ausgabeartefakt im expliziten Ausgabebereich vollständig schreiben, flushen und schließen; eigene Dateiidentität und Synchronisation nach `PACK-23` prüfen.
8. Die **tatsächlich geschriebenen ZIP-Bytes** durch den gemeinsamen Validator gegen dieselbe fixierte Referenz prüfen.
9. Quell-/Zielidentitäten und Veröffentlichungsvoraussetzungen abschließend kontrollieren; die temporären Ausgabebytes erneut an den vollständig validierten Hash binden. Bei bekannten Änderungen abbrechen. Alle für das Erfolgsresultat nötigen fachlichen Daten sind spätestens jetzt fixiert.
10. Genau die validierte Datei ohne Überschreiben unter dem endgültigen Namen veröffentlichen und den bestätigten Publikationszustand request-lokal festhalten.
11. Eigene temporäre Zweitnamen bestmöglich bereinigen. Aus den bereits geprüften Fakten das vollständige Erfolgsresultat einschließlich etwaiger Cleanup-Warnungen liefern; anschließend erfolgt gegebenenfalls die getrennte CLI-Ausgabe.

Die Implementierung darf stabile In-Memory-Daten und interne gemeinsame Prüffunktionen wiederverwenden. Sie darf jedoch weder Schritt 8 auslassen noch nur ein geplantes Manifest anstelle des geschriebenen Archivs validieren.

Wenn der gemeinsame Referenzvalidator technisch erneut einen Dateipfad liest, muss dessen Referenz-SHA-256 mit der anfangs gebundenen Erfassung übereinstimmen. Bevorzugt wird ein gemeinsamer interner Pfad über die bereits geprüfte Erfassung, ohne einen zweiten schwächeren Parser.

### 13.2 Veröffentlichungsgrenze

**PACK-19.** Vor vollständiger erfolgreicher Validierung gibt es **keinen fertigen Paketnamen**. Die temporäre Datei hat einen eindeutig temporären, von den vorhandenen Exchange-Regeln nicht als fertiges Paket verwendbaren Namen, beispielsweise mit abschließendem `.partial`.

Die Veröffentlichung muss vollständig und exklusiv erfolgen. Ein simples „existiert nicht“-Prüfen mit anschließendem überschreibendem `rename` erfüllt den Vertrag bei konkurrierenden Aufträgen nicht. Es ist eine passende getestete No-replace-Technik des vorhandenen Plattformadapters zu verwenden. Wird eine solche sichere Veröffentlichung vom gewählten Dateisystem nicht unterstützt, wird die Operation abgelehnt; es gibt kein stilles inkrementelles Schreiben unter dem fertigen Namen.

Ein nach erfolgreicher Validierung ausgetauschtes temporäres Artefakt darf nicht veröffentlicht werden. Die geprüfte Dateiidentität muss bis zur Veröffentlichung gebunden bleiben; Änderungen an Bytes oder Identität verwerfen die Freigabe.

Interne Techniken wie ein atomarer Hardlink zur Veröffentlichung werden nicht mit der Aufnahme fremder Hardlinks aus dem Inhaltsordner verwechselt. Erfolg bedeutet: Die geprüften Bytes wurden unter dem endgültigen Namen veröffentlicht. Er bedeutet keine allumfassende Stromausfall-Durability-Garantie für jedes entfernte Dateisystem.

### 13.3 Abbruch und Bereinigung

**PACK-20.** Bei einem Fehler vor der Veröffentlichungsgrenze wird kein finales Paket gemeldet und kein bestehendes Ziel verändert. Eigene temporäre Dateien werden bestmöglich entfernt. Ein nicht entfernbarer eigener Rest wird mit seinem Pfad sichtbar gemacht; fremde Dateien werden niemals zur „Reparatur“ gelöscht. Ein zusätzlicher Bereinigungsfehler ersetzt nicht den primären fachlichen Fehler und dessen Kategorie.

Nach bestätigter Veröffentlichung ist der fachliche Pack-Vorgang erfolgreich. Scheitert ausschließlich die nachlaufende Entfernung eines eigenen temporären Zweitnamens, muss die API **auch ohne Observer** das vollständige `PatchPackResult` einschließlich Pfad, Größe, SHA-256 und Validierungsnachweis zurückgeben. `warnings` enthält den Bereinigungshinweis und den verbleibenden eigenen Pfad. Es wird dafür keine `PatchHarborError` geworfen und kein `success: false`/`result: null` erzeugt. Das bereits veröffentlichte Paket wird nicht zurückgenommen, neu gebaut oder unter einem zweiten Namen veröffentlicht.

Erfolgsdaten werden aus dem vor der Veröffentlichung fixierten Nachweis gebildet, nicht durch ein erforderliches nachträgliches Wiederöffnen der finalen Datei. Ein externer Watcher darf die veröffentlichte Datei bereits übernommen haben; das macht den abgeschlossenen Pack-Nachweis nicht ungültig. Unerwartete Programmfehler dürfen nicht pauschal verschluckt oder zu behauptetem Erfolg umgedeutet werden.

Abbruchsignale werden respektiert. Eine kontrollierbare Unterbrechung vor Veröffentlichung endet ohne Erfolg mit `INTERRUPTED / 130`. Nach bestätigter Veröffentlichung darf eine kontrolliert abgefangene Unterbrechung der **optionalen Bereinigung** diese abbrechen; sofern der API-Aufruf geordnet zurückkehren kann, liefert er den vorhandenen Erfolg mit Warnung. Die Unterbrechung der späteren CLI-Ausgabe wird getrennt nach `PACK-05` behandelt. Es werden keine neuen globalen Signalhandler und keine Abbruch-Wiederholung eingeführt.

Die Diagnose muss immer den tatsächlich bekannten Veröffentlichungszustand nennen. Ein harter Prozessabsturz oder eine nicht sicher feststellbare Unterbrechung an der atomaren Grenze kann keine zuverlässig zugestellte Antwort garantieren; daraus darf weder „sicher nicht veröffentlicht“ noch eine automatische gefahrlose Wiederholung abgeleitet werden. Diese Erweiterung führt dafür kein Journal oder einen allgemeinen Recovery-Dienst ein.

### 13.4 Erlaubte Nebenwirkungen

**PACK-21.** Fachliche Schreibzugriffe beschränken sich auf das ausdrücklich gewählte Ausgabeverzeichnis, das eigene temporäre Paket beziehungsweise begrenzte eigene Spooldateien darin und die endgültige Ausgabe. Inhaltsordner und Referenz werden nicht verändert. Es werden keine Registry-, Konfigurations-, Replay-, Watcher-, Installations- oder Repositoryzustände angelegt oder verändert.

`pack` startet keine Unterprozesse, kein Git, keine Shell, keine Tests, keinen Build und kein Netzwerk. Es erzeugt kein eigenes Result-Bundle. Betriebssystembedingte Leseeffekte wie Access-Timestamps und die Fähigkeiten eines vom Aufrufer selbst gelieferten Observer-Callbacks sind keine vom Packer ausgeführte Projektmutation.

Ein explizit als Ausgabe gewählter überwachte Exchange-Ordner ist ein externer Automatikeingang: Nach der Veröffentlichung kann ein bereits laufender **separat installierter Watcher** reagieren. Deshalb gibt es keinen impliziten Exchange-Ausgabeort. Der Packer startet den Watcher nicht und garantiert nach Veröffentlichung nicht, dass dieser die Datei liegen lässt.

### 13.5 Fehlerzuordnung

**PACK-22.** Bestehende numerische Fehlerklassen werden soweit passend wiederverwendet. Ein aus einem gemeinsam genutzten Bestandsprüfer übernommener Fehler behält seinen `FailureReason`, den zutreffenden `ErrorKind` und seinen Exit-Code. Pack-spezifische Vorprüfungen müssen für **denselben fachlichen Mangel dieselbe Kategorie** liefern. Eine pauschale Umklassifizierung aller Paketprobleme auf Code 10 ist unzulässig. [B3, B5]

Die reinen Argumentgrenzen aus `PACK-03` sind davon getrennt. Beispielsweise sind `bool` als Modus oder ein Optionskonflikt Argumentfehler; ein formal gültig übergebener, aber unsicherer Paketpfad oder ein verbotener Zielmodus sind fachliche Sicherheitsfehler.

| Fehler/Sachverhalt | Vertrag |
|---|---|
| CLI-Pflichtparameter, Optionskonflikt, syntaktisch ungültiger Modus | Usage / Exit `2`. |
| API-Typfehler, Leerwert oder ungültige reine Argumentkombination | `TypeError` / `ValueError`, ohne Erfolgsausgabe; keine Umklassifizierung fachlicher Bestandsprüferfehler. |
| Fehlender Pflichtmarker beziehungsweise vom bestehenden Skriptformatprüfer als ungültig eingestufter Skriptinhalt | `NO_VALID_SCRIPT` / Exit `3`. |
| Nicht unterstützte Interpreterangabe im statisch geprüften Entrypoint | `INTERPRETER_ERROR` / Exit `5`; kein Nachweis eines installierten Zielinterpreters erforderlich. |
| Referenz unlesbar/ungültig, Quelldatei nicht lesbar oder bekannte Änderung während der Erfassung | `SOURCE_ERROR` / Exit `4`, entsprechend dem gemeinsamen Readervertrag. |
| Unsicherer Paketpfad, unzulässiger Dateityp, Pfadkollision oder semantisch verbotener angeforderter Modus | `SOURCE_ERROR` / Exit `4`, auch bei früher Pack-Inventarisierung. |
| Überschrittenes Eingabe-, ZIP-, Inhalts-, Handoff- oder Pack-Scan-Ressourcenbudget | `SOURCE_ERROR` / Exit `4`; kein Budgetfehler wird durch eine Renderer- oder Publikationshülle zu Code 6 oder 10. |
| Manifest-/Paketformatfehler; referenzierter Entrypoint fehlt im vollständigen Inventar | `PATCH_PACKAGE_ERROR` / Exit `10`, wie im vorhandenen Paketprüfer. |
| Nur bei `pack` verbotene Vorgaben für generierte Inhalte: mitgeliefertes Root-`patch.json` oder reserviertes Handoff; Modusschlüssel benennt keinen übergebenen Entrypoint-/Nutzdateipfad | Neue Pack-Eingabefälle: `PATCH_PACKAGE_ERROR` / Exit `10`. Ein zusätzlich vorliegender Sicherheitsmangel behält dagegen seine gemeinsame Kategorie. |
| Pflichtvorlage fehlt oder Renderer scheitert ohne spezifischeren gemeinsamen Prüfgrund; Ziel ungeeignet/existiert; Schreiben, notwendiger Datei-Sync oder No-replace-Publikation scheitert | `PAYLOAD_PREPARATION_ERROR` / Exit `6`. |
| Fehler des geschriebenen Archivs bei gemeinsamer Endvalidierung oder abschließendem sicheren Hash-Read | Dessen vorhandene Kategorie bleibt erhalten; unsicheres/verändertes/unlesbares Artefakt insbesondere `SOURCE_ERROR / 4`, tatsächlicher Paketformatfehler `PATCH_PACKAGE_ERROR / 10`. Nicht pauschal „Schreiben gescheitert“ melden. |
| Bindungsabweichung in der abschließenden gemeinsamen Prüfung | Bestehender `STATE_MISMATCH` / Exit `9`; nicht zur Warnung abschwächen. |
| Kontrollierte Unterbrechung vor Veröffentlichung | `INTERRUPTED` / Exit `130`. |
| Ausschließlich nachlaufender Cleanup-Fehler nach bestätigter Veröffentlichung | Vollständiger **Erfolg mit Warnung**, regulärer CLI-Erfolgsstatus `0`; kein fachlicher Fehler nach `PACK-20`. |
| Behandelter I/O-Fehler der CLI-Ausgabe nach bestätigter Veröffentlichung | Nur Ausgabefehler des CLI-Adapters / Exit `7` nach `PACK-05`; vorhandener Pack-Erfolg bleibt bestehen. Kontrollierte Unterbrechung dieser Ausgabe: `130`. |

Bei mehreren gleichzeitig ungültigen Inhalten darf die erste tatsächlich durchgeführte Prüfung den Fehler bestimmen. Die Pflicht zur gleichen Kategorie bezieht sich auf denselben eindeutig isolierten Sachverhalt, nicht auf eine neue globale Prioritätenordnung aller denkbaren Defekte. Die Tests müssen diese Fälle deshalb einzeln und zusätzlich gegen die gemeinsame Inspektion prüfen.

Eine defekte Referenz ist ein Eingabefehler und kein erfolgreicher Test mit `binding_matches=false`. Der Fehlertext muss die Phase und den betroffenen Gegenstand benennen; sein exakter Wortlaut ist nicht normativ.

`result_bundle_error` aus heute eventuell wiederverwendeten Renderer-Hilfen muss an der Pack-Grenze sinnvoll adaptiert werden, statt eine nicht stattfindende Result-Erzeugung zu behaupten. Bereits eindeutig klassifizierte gemeinsame Fehler bleiben auch bei Weiterleitung durch einen Renderer erhalten; reine neue Vorlagen-/Paketdatei-Erzeugungsfehler erhalten Code 6. Davon getrennte CLI-Ausgabefehler folgen `PACK-05` und werden nicht als Paketdatei-Erzeugung behandelt. Interne Ursachen bleiben diagnostisch nachvollziehbar. Kein Fehler wird durch Überspringen der Endvalidierung „gelöst“.

### 13.6 Getrennte Dateisystem- und Publikationspolitik

**PACK-23.** Die Erstfassung von `pack` verwendet bewusst **keine automatischen Stabilitäts-Retries**. Die endlichen CIFS-Wiederholungen aus Hauptspezifikation §18.5 bleiben auf die bisherigen Result-Publikationswege beschränkt (`MIG-06`). Sie werden weder auf den Inhaltsordner oder die Referenz noch auf die neue Pack-Ausgabe implizit übertragen.

Nach dem Schließen der eigenen temporären ZIP wird deren Eigentümerschaft geprüft, die Datei über einen identitätsgeprüften Handle synchronisiert und der Elternordner im Rahmen des vorhandenen Plattformadapters bestmöglich synchronisiert. No-follow-/Reparse- und Eigentumsprüfungen bleiben erforderlich. Vor Veröffentlichung müssen ein sicherer erneuter Hash-Read und die Dateiidentität zu den vollständig validierten Bytes passen. Ein unveränderter Hash ersetzt keine notwendige Eigentumsprüfung.

Ein typisierter `FileChangedDuringRead` bei der Erfassung/Prüfung einer Pack-Eingabe oder der eigenen temporären Ausgabe führt ohne Warte-/Neuaufnahmeversuch zur Ablehnung nach `PACK-22`. Auch eine gleich lange Inhaltsänderung mit zurückgesetzter `mtime`, ein Austausch, ein Symlink oder ein Bindungs-/Ressourcenfehler darf nicht durch längeres Warten geheilt werden. Es gibt dafür keine neue CLI-Option, kein zusätzliches Retry-Budget und kein erneutes Ausführen der Pack-Operation.

Die ausdrücklich gewählte Ausgabe kann auf einem Netzwerkdateisystem liegen, **wenn** alle sicheren Lese-, Identitäts-, Sync- und No-replace-Voraussetzungen tatsächlich erfüllt sind. Eine allgemeine CIFS-Erfolgs- oder Stromausfallgarantie wird nicht zugesagt. Unterstützt das Ziel die erforderliche exklusive Veröffentlichung nicht oder bleibt eine eigene Ausgabe instabil, scheitert `pack` ohne freigegebenes Teilpaket; vorhandene Dateien bleiben unberührt. Ein späterer Auftrag darf neu begonnen werden, ist aber kein versteckter interner Wiederholungsversuch.

Gemeinsame sichere Low-Level-Mechanik darf verwendet werden; Result-Replace/Result-Retry und Pack-No-replace/Pack-ohne-Retry müssen jedoch durch explizite Politikparameter oder getrennte schmale Adapter auseinandergehalten werden. Insbesondere darf die Pack-Erstfassung die bereits vorhandene CIFS-Robustheit der Result-Erzeugung nicht zurückbauen.

## 14. `inspect`, `validate` und Grenzen des Prüfnachweises

### 14.1 Unterschied der drei Werkzeuge

| Werkzeug | Aufgabe |
|---|---|
| `pack` | Aus bewusst vorbereiteten Dateien ein korrekt gebundenes Paket erzeugen und vor Veröffentlichung referenzvalidieren. |
| `inspect` | Tatsächliche Paketfakten liefern; dabei bereits sichere Struktur und statischen Paketvertrag prüfen. |
| `validate` | Die Inspektion verwenden und gegebenenfalls zusätzlich mit einem Result oder einer realen Repositoryinstanz abgleichen. |

**CHECK-01.** Die bestehende Bedeutung der Prüfbereiche bleibt unverändert:

- `package`: gültiges Paket, aber kein Repository-Bindungsabgleich; `binding_matches=null`.
- `reference`: gültiges Paket und Abgleich gegen eine vollständig geprüfte Referenz; bei Erfolg `binding_matches=true`.
- `repository`: Abgleich mit einer realen passenden registrierten Repositoryinstanz; spätere zeitnahe Apply-Prüfung bleibt notwendig.

Ein erfolgreicher `pack`-Aufruf enthält bereits den `reference`-Nachweis. Ein unmittelbar danach identischer separater `validate`-Aufruf ist für den Pack-Vertrag nicht erforderlich. Eine erneute Prüfung ist erforderlich, wenn das Paket verändert oder seine Byteidentität seitdem nicht mehr gewährleistet ist. `inspect` kann zusätzlich für den inhaltlichen Soll-/Ist-Abgleich genutzt werden.

### 14.2 Keine falschen Erfolgsaussagen

**CHECK-02.** Weder `pack` noch `inspect` oder `validate` bestätigen:

- fachliche Richtigkeit der Änderungen oder ihre Übereinstimmung mit dem Nutzerauftrag;
- vollständige Bash-/PowerShell-Syntax, erfolgreiche Skriptausführung oder das Vorhandensein aller Zielwerkzeuge;
- bestandene Projekttests, Commits, Push oder CI;
- Authentizität, Vertrauenswürdigkeit oder Schadlosigkeit des Pakets;
- unveränderten Zustand des Zielrechners nach Erzeugung der Referenz;
- Replay-/Recovery-Freigabe für einen späteren Apply.

Ein absichtlich syntaktisch fehlerhaftes, aber statisch paketkonformes Shellskript ist deshalb ein notwendiger Negativnachweis für **die Aussagegrenze**, nicht zwingend ein Paketfehler. Die tatsächlichen späteren Apply-, Plattform- und Projektprüfungen bleiben vollständig erhalten.

## 15. Bootstrap und Nutzung im Chat

### 15.1 Vorprüfung ohne Codeausführung

**CHAT-01.** Die generierten Anweisungen erklären zuerst das Resultformat und die Bereitstellung der Runtime. Vor dem Start der PYZ werden mit bereits verfügbaren vertrauenswürdigen Mitteln mindestens äußerer Runtime-Deskriptor, Dateityp, sichere Memberpfade, Größenbudgets, Python-Anforderung und SHA-256 der entnommenen Bytes geprüft. Kein pauschales unkontrolliertes `extractall`.

Der Ort der Runtime wird aus den versionsbezogenen Metadaten entnommen, nicht aus einer erratenen Dateiendung oder einer alten hartcodierten Versionsnummer. Die Auswahl mehrerer Kandidaten durch „nimm die erste PYZ“ ist unzulässig.

Der Bootstrap darf hierfür die Standardbibliothek verwenden und muss ohne bereits installiertes PatchHarbor funktionieren. Sein vorsichtiger Vorabcheck ist vom vollständigen nativen Result-/Runtime-Nachweis getrennt. Er darf keine vollständige Produktvalidierung behaupten, wenn er nur Deskriptoren und Hashes kontrolliert hat.

Die tatsächliche Codeausführung setzt die bewusste Nutzung des mitgelieferten Werkzeugs voraus. Hashes aus derselben untrusted Datei beweisen nicht deren Absender. Die PYZ darf beim automatischen Klassifizieren oder bloßen Lesen eines Results nie nebenbei gestartet werden.

### 15.2 Installationsfreier Standardweg

**CHAT-02.** Für neue Results entfällt die vorherige Aufforderung, zuerst `pip`, eine virtuelle Umgebung oder ein Wheel zu installieren. Die Anleitung zeigt den direkten Aufruf mit einem passenden verfügbaren Python und zusätzlich den kontrollierten API-Weg für Python-only-Umgebungen.

Eine private Entnahme der einzelnen geprüften PYZ aus dem Result ist erlaubt. Sie ist keine Paketinstallation. Das ZIP-Anwendungsformat macht die Runtime nicht direkt aus einem **verschachtelten** ZIP-Pfad aufrufbar; es braucht einen für den vorhandenen Interpreter erreichbaren Archivpfad oder einen ausdrücklich unterstützten Importzugang.

Ein kleines Beispiel für den eigentlichen API-Schritt, **nach abgeschlossener Bootstrap-Prüfung und Herkunftskontrolle**, lautet:

```python
from patchharbor import api

result = api.pack_patch(
    "patch-inhalt",
    reference_bundle="result.zip",
    entrypoint="apply.sh",
    output_directory="ausgabe",
)
assert result.validation.binding_matches is True
print(result.path, result.package_sha256)
```

Das Beispiel ist kein eigenständiger sicherer Loader und darf nicht als Ersatz für die Vorprüfung präsentiert werden.

### 15.3 Bevorzugter Arbeitsablauf

**CHAT-03.** Der normale Entwicklungs-/Übergabeweg lautet:

1. Aktuelles Result und den gemeinsamen Spezifikationssatz nach `GOV-03` auswerten; den ausdrücklich beauftragten Plan und den tatsächlichen Ausgangszustand verstehen.
2. Änderungen, notwendige Projekttests und genau einen geeigneten Entrypoint vorbereiten.
3. Nur die benötigten Dateien im expliziten Inhaltsordner zusammenstellen.
4. Mit der passenden mitgelieferten PYZ `pack` gegen das originale Result ausführen.
5. Die erzeugte Inspektion beziehungsweise einen zusätzlichen `inspect`-Aufruf zum Abgleich des tatsächlichen Inhalts verwenden.
6. Genau die final geprüften ZIP-Bytes zur Übergabe bestimmen und nicht nachträglich verändern.

`pack` ersetzt ausschließlich die bisher manuell nachgebaute Verpackung. Es ersetzt keine Analyse des Auftrags, keinen eigenen Inhaltsreview und keine Teststrategie.

### 15.4 Fallback und ehrliche Nachweise

**CHAT-04.** Fehlendes Python, fehlende Codeausführung, fehlender Dateizugriff, inkompatible Python-Version oder ein technischer Start-/Importfehler werden sichtbar dokumentiert. Die Chat-Anweisungen versprechen keine Ausführbarkeit in jeder Copilot- oder Chat-Umgebung.

Der bestehende sichere manuelle Übergabeweg bleibt als technischer Fallback erhalten. Ein fehlgeschlagener Runtime-Start darf nicht in einen erfundenen Prüferfolg umbenannt werden. Ein ausschließlich die optionale Runtime betreffender Referenzdefekt kann nur nach dem ausdrücklich begrenzten bestehenden Daten-Fallback behandelt werden; ein solches manuell erstelltes Paket ist kein erfolgreiches natives `pack`-Ergebnis.

Eine inhaltliche Ablehnung durch den Validator, eine falsche Bindung oder ein ungültiger Repository-Snapshot darf nicht durch Wechsel des Verpackungswegs umgangen werden. Fehlende fachliche Voraussetzungen bleiben ein Stop-Grund für den betreffenden Auftrag.

### 15.5 Finale Auslieferung

**CHAT-05.** Der bestehende Vertrag über eine kanonische finale Patch-ZIP und genau eine finale Patch-Bereit-Meldung bleibt erhalten. Eine Backup- oder Mail-Funktion wird nicht in `pack` oder die PYZ eingebaut. Externe Sicherung/Versand erfolgen nur durch verfügbare externe Werkzeuge und mit denselben geprüften Bytes.

Ein Backupfehler führt nicht zu einem neuen Paket. Änderungen nach einer erfolgreichen Pack-Operation machen deren Bytefreigabe für die geänderte Datei ungültig und verlangen einen erneuten vollständigen Verpackungs-/Prüfvorgang. Die hier vorliegende **Spezifikationsdatei** ist selbst kein Patch-Paket und löst keinen Apply aus.

Die laufende Chat-Bundle-Nummer wird nach dem bestehenden Chat-/Planvertrag vergeben, nicht von `pack` aus seiner Paket-ID erzeugt. Die Verwendung des Packers ändert weder diesen Zähler noch die CI-Zuständigkeiten (`PACK-15`, `TEST-05`).

### 15.6 Gemeinsame Spezifikations- und Planauswahl

**CHAT-06.** Die kanonische Chat-Vorlage muss die Auswahlregel aus `GOV-03` inhaltlich wiedergeben: Für `PYZ-PACK` sind Hauptspezifikation **und** Ergänzung gemeinsam zu lesen; der aktive Featureplan referenziert beide. Beide Dateien sind keine Konkurrenz. Nicht eingeordnete widersprüchliche Fassungen und tatsächlich mehrere plausible aktive Pläne bleiben nach dem bisherigen Stop-Vertrag mehrdeutig. Ein fehlender Teil des ausdrücklich verlangten Spezifikationssatzes wird sichtbar gemeldet statt still weggelassen.

Ein noch unveränderter Versionsstring darf keinen abgeschlossenen Plan reaktivieren. Die Darstellung des verwendeten Normsatzes muss beide tatsächlichen Pfade enthalten, ohne daraus einen neuen starren Wortlaut-/Layoutvertrag abzuleiten. Diese Regel gehört zu den Anweisungen und der Planung, nicht zu einer neuen Core-Dateisuche.

## 16. Dokumentationsumfang

**DOC-01.** Dokumentation und Implementierung werden gemeinsam aktualisiert. Die folgenden Artefakte müssen den Zielvertrag korrekt wiedergeben:

| Dokument/Ort | Änderung |
|---|---|
| Diese Ergänzung | Normative Featuregrenzen, Schnittstellen, Fehler-/Formatverträge und Nachweisplan; Revisionen nachvollziehbar führen. |
| `spec/SPECIFICATION_CHANGELOG.md` | Einführung der separaten Ergänzung, ausdrücklich abgelöste Wheel-Regeln, neue Kommandos und Formate vermerken. |
| Spezifikations-/Planverweise | Beide Dateien nach `GOV-03` gemeinsam referenzieren; Featureplan ausdrücklich auswählen, echte Konkurrenz weiterhin erkennen und keine zweite Vollkopie erzeugen. |
| `README.md` | Manuelles `pack`, Inhaltsordner, PYZ-Start, normale Installation weiterhin über Wheel, klare Watcher-Abgrenzung. |
| CLI-Hilfe | Eingaben, Ausgabealternativen, Suffix, Modusoptionen und fehlende Ausführung durch `pack` erklären. |
| `docs/python-api.md` | `pack_patch`, `PatchPackResult`, phasenunabhängige Bestandsfehler, Erfolg trotz Cleanup-Warnung, stille Standardaufrufe und In-Process-Verwendung. |
| `docs/runtime-artifact.md` | PYZ-Profil, neues Rezept, Hashverfahren, Normalinstallation versus portable Runtime, Watcher-Ausschluss. |
| `docs/runtime-bootstrap.md` und `scripts/runtime_bootstrap.py` | Installationsfreien Bootstrap und Legacy-Behandlung vor oder atomar mit der Writerfreigabe nutzbar machen; die tatsächlich mitgelieferte Vorlage einbeziehen, keine blind ausgeführte Runtime. |
| `docs/result-format-2.md` | Historischen Format-2-Vertrag erhalten und auf den Nachfolger verweisen; nicht nachträglich zu Format 3 umdeuten. |
| Neues `docs/result-format-3.md` | Geschlossene äußere/innere Schemata, Inventar, `unavailable`, Kompatibilität und Prüfumfang. |
| `docs/result-runtime-production.md` | Automatische Erzeugung, request-lokale Bindung, Selbstupdate, dreifacher Roundtrip, Diagnosepriorität. |
| `docs/result-publication-cifs.md` | Bestehenden Result-Sync-/Retry-/Hash-/Diagnosevertrag auch für Format 3 erhalten; historische Status-/Formatangaben abgleichen, offene reale CIFS-Nachweise nicht als erledigt darstellen. |
| Neues `docs/pack.md` | Vollständige Dateien, Diff-Payloads, gemischte und reine Diagnosepakete; Dateirechte, beide Ausgabearten, Paket-ID versus Chat-Zähler, No-replace ohne Stabilitäts-Retries und Erfolg trotz Cleanup-Warnung. |
| `CHAT_INSTRUCTIONS.md` als kanonische Vorlage | Gemeinsamer Normsatz und Featureplan, rechtzeitig nutzbarer PYZ-Bootstrap, bevorzugter Pack-Weg, Zielrechnerdaten statt Chat-Hostdaten, Fallback und Auslieferungsnachweis. |
| Release-/Build-Dokumentation | Getrennte Installations- und PYZ-Artefakte, Prüfsummen, Testnachweise und keine behauptete Watcher-PYZ. |

**DOC-02.** Beispiele müssen mit den tatsächlichen Schnittstellen übereinstimmen. Besonders wichtig sind die bereits vor dem Entrypoint geschriebenen Nutzdateien und der Unterschied zwischen technischen Byteprüfungen und bestandenen Projekttests.

Die normale Installation muss den Watcher weiterhin korrekt dokumentieren. In der PYZ-Dokumentation darf „gleicher Core“ nicht erneut zu „enthält auch den Watcher“ ausgeweitet werden. Änderungen an den Anweisungstexten werden fachlich reviewed; es werden keine Wortlaut- oder Layouttests eingeführt.

## 17. Teststrategie und verbindliche Testmatrix

### 17.1 Testprinzipien

**TEST-01.** Tests folgen den vorhandenen Core-, E2E-, Plattform- und Packaging-Lanes. Gegen echte gebaute Artefakte muss außerhalb des Checkouts getestet werden. Ein importierbarer Quellbaum oder eine zufällig vorhandene Installation darf keinen defekten PYZ-Test grün machen.

**TEST-02.** Neue Tests prüfen Funktion, strukturierte Daten, Fehlerkategorien, Bytes, Dateirechte, Importherkunft, Prozess-/Netzwerkaufrufe, Zustandsbindung und Dateisystemeffekte. **Keine neuen Tests auf Farben, Symbole, Fortschrittspunkte, Zeilenlayout, exakte Hilfetexte, verkürzte ID-Darstellung oder wortgetreue Dokumentprosa.** Protokollschlüssel, Hash-Testvektoren und kanonische Dateiformate sind fachliche Datenverträge und bleiben testpflichtig.

**TEST-03.** Nebenläufigkeits-/Abbruchtests verwenden kontrollierte Synchronisationspunkte und Fault-Injection statt zufälliger kurzer Sleeps. Ein beobachtetes Dateisystem ohne sichere Publikationsprimitive wird explizit als nicht unterstützter Fall getestet, nicht durch einen permissiven Fallback verschleiert.

### 17.2 PYZ und Artefakterzeugung

| Test-ID | Verbindlicher Nachweis | Anforderungen |
|---|---|---|
| Z-01 | Frischer Interpreter startet die gebaute PYZ ohne PatchHarbor-Installation, `pip`, venv-Erzeugung, Netzwerk oder Checkout. | PYZ-01/02, ARCH-02 |
| Z-02 | `--version`, CLI und API beziehen ihren Code nachweislich aus der ausgewählten PYZ, auch bei gleichnamigen Modulen im Arbeitsverzeichnis. | PYZ-01/05 |
| Z-03 | Empfohlener Aufruf `-I -S -B` funktioniert; technische Isolation wird nicht als Sandbox behauptet. | PYZ-01/02, CHAT-01 |
| Z-04 | `inspect`, paket-/referenzbasiertes `validate` und `pack` funktionieren ohne Git/Bash/PowerShell. | ARCH-02, PACK-21 |
| Z-05 | Kein `patchharbor_watcher/` und keine Watcher-Ressourcen im echten PYZ-Inventar; Core-Import benötigt sie nicht. | SCOPE-03, PYZ-03 |
| Z-06 | Alle vorgesehenen Core-CLI-/API-Wege funktionieren aus der PYZ bei vorhandenen regulären Voraussetzungen, einschließlich `fs run`, Registry/Konfiguration und Apply. | ARCH-02/03 |
| Z-07 | Kanonische Vorlage, Lizenz und API-Daten werden aus der PYZ gelesen; kein CWD-/Fremdinstallations-Fallback bei defekten eigenen Ressourcen. | PYZ-04 |
| Z-08 | Zu alter Interpreter, fehlende Ressourcen, beschädigte Identität, widersprüchliche Rezeptdaten und nicht unterstütztes Profil werden korrekt behandelt. | PYZ-02/07/08 |
| Z-09 | In-Process-API ohne Unterprozess; Konflikt mit vorher importierter anderer Version wird erkannt, nicht per unsicherem Entladen kaschiert. | PYZ-05 |
| Z-10 | Installierte, cachebereinigte Standarddistribution materialisiert die korrekte PYZ ohne Build oder Netz. | PYZ-06 |
| Z-11 | Installation und daraus erzeugte PYZ materialisieren identische kanonische Archivbytes. | PYZ-09/11 |
| Z-12 | Mindestens drei aufeinanderfolgende Result-/PYZ-Generationen; gleiche Runtime-Bytes, Größe und Hash, kein rekursives Wachstum. | PYZ-11 |
| Z-13 | Selbstupdate nach eingefrorener Erzeugeridentität erzeugt keine Mischung alter Runtime mit später geladener neuer Vorlage. | PYZ-10 |
| Z-14 | Andere Builds mit gleichem Versionsstring bleiben unterscheidbar. Änderungen an Version/Provenienz werden von Änderungen der inventarisierten Core-Dateihashes unterschieden; ausgeschlossene Watcher-Dateien werden nicht mitgehasht. | PYZ-07 |
| Z-15 | Fremdmodule, native Dateien, `.pth`, zusätzliche/fehlende Einträge, manipulierte lokale ZIP-Header, CRC-/Hashfehler und gefälschte Verzeichniszähler werden abgelehnt. | PYZ-03/08/09 |
| Z-16 | Laufzeitbudget, Rezeptlimit und gemeinsame äußere/innere Budgetierung greifen vor unbeschränktem Einlesen. | PYZ-12 |

### 17.3 Resultformate, Übergang und Bestandsregression

| Test-ID | Verbindlicher Nachweis | Anforderungen |
|---|---|---|
| F-01 | Neue Reader lesen gültige Results 1, 2 und 3; formatbezogene Inventare bleiben getrennt. | FMT-01, MIG-01 |
| F-02 | Alte Wheels werden nur lesend nach altem Profil geprüft; kein Import/Installieren und keine Umdeutung zu PYZ. | MIG-01 |
| F-03 | Deskriptoren, Bytegrößen, Hashes, Profil, Content-ID, Versionsangaben und Capability-Daten werden konsistent geprüft. | FMT-02/03/05 |
| F-04 | `unavailable` hat genau die erlaubte Struktur, Gründe und null-Werte; keine behaupteten Artefakte. | FMT-04 |
| F-05 | Zusätzliche Runtime-Dateien, Wheel+PYZ-Doppelbelegung, unbekannte Schlüssel und unbekannte Formate werden konservativ abgelehnt. | FMT-05, MIG-01 |
| F-06 | Result-Erzeugung funktioniert manuell, nach Apply-Erfolg/-Fehler, im Dry-Run, mit explizitem Ziel und über installierten Watcher. | MIG-02 |
| F-07 | Runtime-only-Ausfall erhält Snapshot/Logs als `unavailable`; echte Resultfehler, Abbruch und Notfallrettung behalten ihre Priorität. | MIG-04 |
| F-08 | Archivierung/Recovery verwenden keine bloß strukturelle Klassifikation oder schwächere Diagnoseprüfung als Erfolgsbeweis. | MIG-02/05 |
| F-09 | Eingefrorene Altleser führen Format-3-Results oder eine standalone PYZ nicht als Patch aus und löschen sie nicht aufgrund unbewiesener Fakten. | MIG-03 |
| F-10 | Reader-first-Zwischenstand schreibt noch Format 2; auslieferbare Writerumschaltung erst mit gemeinsamer Lesefähigkeit, Runtime-Provider und funktionsfähigem eingebettetem Bootstrap. | MIG-02, E-10 |
| F-11 | Normale Wheel-/sdist-Installationswege samt installiertem Watcher bleiben funktional; nur das Result-Runtime-Artefakt wechselt. | SCOPE-01/03 |
| F-12 | Legacy-Patch-Pakete und bestehende CLI-/API-/Fingerprint-/Replay-/Mode-Verträge bleiben gültig. | GOV-01, SEM-01 |
| F-13 | Vorhandene Result-Publikations-Fault-Tests auch für Format 3 mit PYZ und `unavailable`: Sync/No-follow, typisierte endliche Retries, gemeinsames Budget, Hashbindung, Runtime-Fallback und Diagnosepriorität bleiben erhalten. | MIG-06, B7 |
| F-14 | Pack-No-replace und dessen fehlende Stabilitäts-Retries verändern weder Result-Replace/Retry noch die bisherige nichtrekursive Exchange-/Runner-Suche. | GOV-04, PACK-23 |

### 17.4 Pack-Funktion und Metadaten

| Test-ID | Verbindlicher Nachweis | Anforderungen |
|---|---|---|
| P-01 | Voll-Datei-Paket aus vorbereitetem Inhaltsordner, Manifest mit vollständiger Referenzbindung, korrektes finales ZIP. | PACK-01/14/18 |
| P-02 | Entrypoint mit Diff-Payload, gemischtes Paket und Diagnosepaket ohne Nutzdateien funktionieren; Packer führt nichts aus. | SEM-01/02, PACK-21 |
| P-03 | CLI, öffentliche API, installierte Anwendung und PYZ verwenden dieselbe fachliche Pack-Implementierung. | ARCH-01, PACK-03 |
| P-04 | Fehlende Pflichtparameter, Optionskonflikte, Byte-/Leerpfade, falsche API-Typen und doppelte CLI-Moduspfade werden korrekt abgewiesen. | PACK-01/03/22 |
| P-05 | Alle vier Bindungswerte werden exakt übernommen; `expected_*`, Anzeigenamen und gekürzte IDs werden nicht als Ersatz genutzt. | PACK-06/14 |
| P-06 | Gültige Dirty-, Dry-Run-, Fehler- und Legacy-Referenzen funktionieren; falsche/intern inkonsistente Referenzen scheitern. | PACK-06/07 |
| P-07 | Runtime-`unavailable` als gültige Referenz funktioniert; deklarierte kaputte Runtime führt nicht zu heimlichem schwächerem Erfolg. | PACK-07, MIG-05 |
| P-08 | Manifest- und `PATCHHARBOR_META`-Kollisionen, falsche Groß-/Kleinschreibung und nicht vorhandener Entrypoint werden abgewiesen. | PACK-08/11 |
| P-09 | Zulässige Unterverzeichnisse, Dotfiles und Repository-Anleitungen im Inhaltsbaum werden übernommen; angrenzende Projektdateien nicht. Keine `.gitignore`-Heuristik oder automatische Dateiänderung. | GOV-04, PACK-08/11 |
| P-10 | Binärinhalte, Zeilenenden und sonstige Nutzbytes bleiben exakt erhalten; fehlende Skriptmarker werden nicht ergänzt. | PACK-11 |
| P-11 | Default `0644`, explizit `0755`, verbotene Bits, unbekannte Modusschlüssel und vorhandene POSIX-Zielmodi werden korrekt behandelt. | PACK-12 |
| P-12 | Automatischer UTC-/UUID-Dateiname, Namensanpassung, Legacy-Fallback und leeres/gesetztes Suffix; Uploadname ist keine Quelle. | PACK-15 |
| P-13 | Expliziter Ausgabename bleibt unverändert; falsches Suffix und temporärer Downloadname werden abgelehnt. | PACK-02/15 |
| P-14 | Handoff enthält Zielrechnerdaten und ursprüngliches `captured_at`, nicht Pack-Hostdaten; neue Bindung/Dateiname passen exakt. | PACK-16 |
| P-15 | Legacy-Environment mit unbekannten Werten erzeugt keine erfundenen OS-/Tooldaten; keine mehrfach angehängte alte generierte Anleitung. | PACK-16 |
| P-16 | Typisiertes Ergebnis und JSON-Envelope enthalten identische vollständige Fakten, Referenzhash, Prüfumfang und Nichtprüfungen. | PACK-04/05 |
| P-17 | Sowohl `--output` als auch `--output-dir` erzeugen genau eine Paket-UUID und einen UTC-Zeitpunkt pro Auftrag; diese werden stabil zurückgegeben, nur der automatische Name verwendet sie. | PACK-04/15 |
| P-18 | Paket-UUID/ID6, Referenz-Run-ID und Chat-Bundle-Nummer bleiben getrennt; kein Zählerzustand wird angelegt und der Entrypoint bleibt bytegleich. | PACK-11/15, CHAT-05 |

### 17.5 Pack-Sicherheit, Veröffentlichung und Unterbrechungen

| Test-ID | Verbindlicher Nachweis | Anforderungen |
|---|---|---|
| S-01 | Traversal, absolute/Windows-/UNC-Pfade, Gerätebezeichnungen, interne Pfade, case-Kollisionen und Datei-/Verzeichnispräfixkonflikte werden abgelehnt. | PACK-09 |
| S-02 | Symlink-/Reparse-Austausch und Quelldateiwechsel zwischen Scan/Öffnen werden erkannt; keine Aufnahme außerhalb der Wurzel. | PACK-09/10 |
| S-03 | Hardlinks, FIFOs, Sockets und Geräte werden nicht gelesen oder blockierend geöffnet. | PACK-09 |
| S-04 | Veränderte Quelldatei, verändertes Quellinventar und ausgetauschte Referenz erzeugen keinen gemischten Erfolg. | PACK-06/10/18 |
| S-05 | Eingabe-, ZIP-, Gesamt-, Handoff- und Scanlimits inklusive vieler leerer Verzeichnisse greifen begrenzt. | PACK-13 |
| S-06 | Ausgabe im Eingabebaum, Alias auf Referenz/Eingabedatei und bestehendes Ziel werden ohne Fremdmutation abgelehnt. | PACK-02 |
| S-07 | Zwei konkurrierende Aufträge mit gleichem Ziel veröffentlichen höchstens einen Gewinner; kein Überschreiben durch TOCTOU-Rennen. | PACK-19 |
| S-08 | Schreibfehler, Platzmangel, Zugriffsfehler, Fehler beim Schließen und Publikationsfehler hinterlassen keinen freigegebenen Teilinhalt. | PACK-18/20 |
| S-09 | Validatorfehler oder absichtlich nachträglich beschädigtes temporäres ZIP verhindert Veröffentlichung; auch bei korrektem ursprünglichem Manifest. | PACK-18/19 |
| S-10 | Austausch des temporären Artefakts nach Validierung wird vor Veröffentlichung erkannt. | PACK-19 |
| S-11 | Kontrollierter Abbruch vor Veröffentlichung; eigene Reste bereinigt oder wahrheitsgemäß genannt, fremde Dateien unverändert. | PACK-20/22 |
| S-12 | Injizierter Cleanup-Fehler nach Publikation liefert auch ohne Observer vollständiges API-Ergebnis und bei intakter Ausgabe Erfolgs-JSON/Exit 0 mit Warnung samt Restpfad; kein Verlust von Pfad/Hash, keine Rücknahme oder Doppelveröffentlichung. | PACK-03/04/05/20 |
| S-13 | Beobachtetes Exchange nimmt erst die fertige Ausgabe wahr, nie die technische `.partial`-Datei; `pack` startet keinen Watcher. | PACK-19/21 |
| S-14 | Instrumentierte Prozess-/Netzwerk-/Dateizugriffe: keine verbotenen Aufrufe, keine Registry-/Repositorywrites, nur expliziter Ausgabebereich. | PACK-21 |
| S-15 | Isolierte Fehlerfallmatrix für Marker 3, Interpreter 5, Pfad/Modus/Budget 4, fehlenden Entrypoint/Manifest 10, Ausgabe 6 und Bindung 9; frühe Pack-Prüfung und entsprechender gemeinsamer Prüfer liefern dieselbe Kategorie. Keine Umdeutung zu fiktivem Result-Write. | PACK-22 |
| S-16 | Nach bestätigt erfolgreichem Packen scheiterndes Schreiben/Flushen der CLI-Ausgabe führt zu Exit 7, kontrollierte Unterbrechung dieser Ausgabe zu 130; Paket bleibt veröffentlicht, kein zweiter Envelope und kein automatischer Neubau. | PACK-05/20/22 |
| S-17 | `FileChangedDuringRead` bei Pack-Referenz, Quelle und eigener temporärer Ausgabe führt ohne Stabilitäts-Retry/Wartebudget zum Abbruch; nötige Sync-/Identitäts-/Hashprüfungen und sichere No-replace-Voraussetzungen bleiben erhalten. | PACK-06/10/19/23 |
| S-18 | Kontrollierte Unterbrechung der optionalen Bereinigung nach bestätigter Veröffentlichung lässt geordnet rückgebbare vollständige Erfolgsdaten samt Warnung bestehen; vor der Grenze bleibt der Vorgang abgebrochen. Kein erforderliches Wiederöffnen der schon vom Watcher übernommenen finalen Datei. | PACK-20 |

### 17.6 Durchstich, Grenzen und Dokumentationsbeispiele

| Test-ID | Verbindlicher Nachweis | Anforderungen |
|---|---|---|
| E-01 | Result aus echter Installation → PYZ entnehmen → `pack` → `inspect`/Referenzvalidierung → regulärer Apply in isoliertem registriertem Repository. | Alle Featuregrenzen |
| E-02 | Derselbe Durchstich mit vollständigen Dateien, Diff-Payload und gemischtem Paket; Nutzdateien werden vor Entrypoint geschrieben. | SEM-01 |
| E-03 | Tatsächliche spätere Repositoryänderung nach Pack-Erfolg wird beim regulären Apply abgelehnt. | CHECK-02 |
| E-04 | Paketkonformer, aber syntaktisch defekter beziehungsweise fachlich fehlerhafter Entrypoint wird nicht als erfolgreich ausgeführt/testiert behauptet. | CHECK-02 |
| E-05 | Startbar ohne Schreibrechte im PYZ-Verzeichnis; `pack` schreibt nur ins freigegebene Ausgabeziel. | PYZ-04, PACK-21 |
| E-06 | Bootstrap ohne installierten Core, falsche Python-Version, Herkunftskonflikt und fehlende Ausführungsmöglichkeiten werden ehrlich unterschieden. | CHAT-01/02/04 |
| E-07 | Nutzbare CLI-/API-Dokumentationsbeispiele werden funktional geprüft, nicht ihre wortgetreue Darstellung. | DOC-02, TEST-02 |
| E-08 | Fachliches Review der finalen Chat-Anweisungen: eine kanonische ZIP, kein Watcher in PYZ, kein erfundener Prüferfolg, kein automatischer Versand. | CHAT-03/04/05 |
| E-09 | Fachlicher Anweisungs-/Planreview: Hauptdatei plus erklärte Ergänzung werden gemeinsam gewählt, fehlender Satzteil wird gemeldet, echte Konkurrenz bleibt mehrdeutig und die alte Paketversion reaktiviert keinen abgeschlossenen Plan. Kein wortgleicher UI-Test. | GOV-03, CHAT-06, PLAN-01 |
| E-10 | **Writerfreigabe-Gate:** Das erste Result des umgestellten Writers ist anhand seiner tatsächlich eingebetteten Anleitung in frischer Umgebung nutzbar; PYZ-Prüfung/Start und `pack` gegen genau dieses Result ohne Wheel-Installation oder Checkout. Nicht bis PP-07/PP-08 aufschieben. | MIG-02, CHAT-01/02, PP-06 |

### 17.7 Plattformen, vorhandene CI und Messungen

**TEST-04.** Verpflichtend sind die Python-Untergrenze 3.12 und mindestens ein zusätzlich im Plan festgelegter unterstützter Interpreter. Auf der gelieferten Grundlage sind die vorhandenen nativen Lanes mit CPython 3.12 und 3.14, Linux und Windows sowie deren Bash-/PowerShell-Prüfungen weiterzuverwenden. Ein Linux-Lauf belegt keine native Windows-Funktion.

Die regulären Wheel-/sdist-/pip-/pipx-/uv-Bereitstellungsnachweise werden nach der bestehenden Packaging-Policy abgedeckt; nicht jede Kombination muss zu einem neuen vollständigen Kreuzprodukt ausgebaut werden. Ein optionaler ARM64-/Ubuntu-in-Termux-Nachweis wird gesondert bezeichnet und nicht als allgemeine Android-Unterstützung ausgegeben.

**TEST-05.** Die bestehende manuelle CI-Dispatch-Policy, ihr aktueller Bundle-Zähler und die vorhandenen seriellen/parallelen Testzuständigkeiten werden nicht durch diese Erweiterung ersetzt. Keine neuen Push-/PR-/Zeitplan-Trigger und kein zusätzlicher serieller CI-Volltestlauf allein wegen dieser Features. Das vorhandene 120-Minuten-Timeout des Acceptance-/Release-Gate-Jobs bleibt erhalten. [B6]

**TEST-06.** Zusätzlich sind PYZ-Größe, zusätzlicher komprimierter Resultumfang, begrenzter Speicherbedarf, Start- und Pack-Zeiten für repräsentative Fälle zu dokumentieren. Dies sind Messwerte mit Umgebung und Eingabegröße, keine pauschalen Leistungsversprechen oder künstlich engen Timing-Assertions.

**TEST-07.** Die Result-/CIFS-Nachweise werden getrennt ausgewiesen: lokale Fault-Injection, native Windows-Prüfung und tatsächliche Linux→Windows-CIFS-Abnahme sind unterschiedliche Nachweise. PP-00 klärt den tatsächlichen Stand des vorhandenen CIFS-Auftrags; noch offene Freigaben werden nicht still geschlossen. Für die geänderten Format-3-Resultwege sind der einschlägige Publikationsvertrag und die Praxisabnahme nach `docs/result-publication-cifs.md` beizubehalten beziehungsweise erneut nachzuweisen. Ein lokales Ersatzdateisystem ist keine reale CIFS-Abnahme. Für `pack` gilt nur die engere getestete Zusage aus `PACK-23`; daraus entsteht keine neue allgemeine Netzwerkdateisystemgarantie.

## 18. Umsetzungsplan, Abhängigkeiten und Arbeitspakete

### 18.1 Planungsregeln

**PLAN-01.** Der folgende Plan ist ein ausführbarer fachlicher Arbeitsplan, aber keine Behauptung bereits erledigter Commits. Der konkrete Commitplan soll unter `planning/pyz-pack/commit-plan.md` geführt werden und für jeden Schritt Ausgangsbindung, Status, Tests, Dokumentation und tatsächliche Nachweise enthalten. Er muss `spec/SPECIFICATION.md` **und** `spec/SPECIFICATION_EXTENSION_PYZ_PACK.md` ausdrücklich als gemeinsamen Spezifikationssatz referenzieren und seine Auswahl für den Auftrag `PYZ-PACK` eindeutig machen.

Die neue Planung überschreibt weder den in der gebundenen Quelle abgeschlossenen Watcher-Plan noch den dort nachfolgenden Result-/CIFS-Plan. PP-00 gleicht ihren tatsächlichen aktuellen Fortschritt und offene Apply-/CI-/Zielplattformnachweise ab (`GOV-02`). Eigenständige offene Aufträge bleiben erkennbar; eine noch unveränderte Paketversion entscheidet nicht über den aktiven Featureplan. Es gibt keine neue Infrastruktur oder einen zusätzlichen verpflichtenden Nutzer-Aufbereitungsschritt.

**PLAN-02.** Jeder fachliche Abschnitt wird nach W → R → C bearbeitet: kleinste bereits sichere durchgängige Funktion, Robustheit/Grenzfälle, anschließend sinnvolle Bereinigung ohne verdeckte neue Fachfunktion. W darf Sicherheitsgrenzen nicht auf einen späteren R-Schritt verschieben.

Die Tabelle legt **Arbeitspakete, nicht eine künstlich feste Anzahl Git-Commits oder Patch-ZIPs** fest. Kleine zusammengehörige Änderungen dürfen unter nachvollziehbarer Testbarkeit zusammengelegt werden. Unsicher gekoppelte Änderungen werden getrennt. Es gibt keine leeren „Cleanup-Commits“ nur zur Erfüllung einer Zählung.

### 18.2 Arbeitspakete und Abschlusskriterien

| Schritt | Inhalt | Abhängigkeiten | Abschlussnachweis |
|---|---|---|---|
| **PP-00 – Vertrags- und Bestandsabgleich** | Gemeinsamen Normsatz und ausdrücklich beauftragten Plan einordnen; aktuellen Repo-/Watcher-/Result-CIFS-Stand und offene Nachweise prüfen. Fehlerkategorien, Publikationsgrenzen, Versionierung und Testzuordnung festhalten. Ziel-Releaseversion festlegen, ohne sie vorzeitig zu veröffentlichen. | Aktuelles Result/Repo, beide Spezifikationsdateien, vorhandene Plan-/Abnahmeunterlagen | Reviewfähiger Commitplan mit beiden Normpfaden, Requirement-/Test-Zuordnung und tatsächlichem Status; keine verdeckte Produktänderung oder erfundene Alt-Abnahme. |
| **PP-01 – Gemeinsame Referenz-/Pack-Bausteine** | Geprüfte Referenzerfassung samt Handoff/Suffix intern wiederverwendbar machen. Pfad-/Modus-/Prüferkategorien erhalten; Publikationsmechanik identifizieren und Result-Replace/Retry von Pack-No-replace/ohne Retry trennen. | PP-00 | Bestands-`inspect`/`validate`, Reader und Result-Publikation unverändert korrekt; keine schwächere Lesestrecke oder globale Politikänderung. |
| **PP-02 – Pack-Core und öffentliche API** | Inhaltsinventar, stabile Erfassung, explizite Modi, Manifest/Handoff, temporäres ZIP, Referenzvalidierung, exklusive Veröffentlichung, vollständiges `PatchPackResult` auch bei nachlaufender Cleanup-Warnung. | PP-01 | Sichere Pakete gegen alte unterstützte Referenzen; P-/S-Tests für die angebotenen Eingaben, Fehlermatrix und Erfolgsschwelle bestehen. |
| **PP-03 – Pack-CLI und erste Dokumentation** | `patchharbor pack`, Ausgabealternativen, JSON-Adapter, gleiche Fehlerzuordnung und getrennte CLI-Ausgabefehler; README/API/Pack-Anleitung. | PP-02 | CLI-/API-Parität und manueller Durchstich aus installierter Distribution; S-12/S-15/S-16 geprüft, keine Parser-/Prüferduplikate. |
| **PP-04 – PYZ-Profil, Ressourcen und minimaler Startweg** | Kanonisches Rezept/Identitäten, Build-Erzeugung, Programmeinstieg, Watcher-Ausschluss, ZIP-taugliche Ressourcen und In-Process-Zugang. Minimalen installationsfreien Bootstrap samt zugehöriger kanonischer Anweisung vorbereiten. Alte Produktion bis zur Umschaltung lauffähig halten. | PP-00; endgültige Funktionsprüfung nach PP-03 | Gebaute PYZ kann alle Core-Funktionen einschließlich `pack`; Herkunft, No-Watcher-Inventar und direkter/API-Start ohne Installation geprüft. |
| **PP-05 – Result-3-Reader und Bootstrap-Integration** | Geschlossene Schemata, PYZ-Datenprüfung, Budgets, Legacy-Reader, Klassifikation, Archiv-/Recovery-Verbraucher. Bootstrap und tatsächlich auszuliefernde Vorlage auf denselben Formatvertrag abstimmen; noch kein auslieferbarer Writerwechsel. | PP-01, PYZ-Profil/Startweg aus PP-04 | F-01 bis F-05 und F-08/F-09 bestehen; Bootstrap funktioniert mit neuen Fixtures und Legacy-Vertrag. Neue Vorlage und Provider sind für das Writer-Gate bereit. |
| **PP-06 – Gemeinsamer Runtime-Provider und Writerwechsel** | Automatische PYZ-Materialisierung und request-lokales Pinning; Writer 3 an allen Result-Wegen; `unavailable`, Selbstupdate und Roundtrip. Result-Sync-/Retry-/Hash-/Diagnosevertrag erhalten; alte eingebettete Wheel-Produktion beenden. | PP-03, PP-04, PP-05 **einschließlich minimalem Bootstrap und tatsächlich mitgelieferter Vorlage**; letzte eng gekoppelte Bootstrap-Anteile nötigenfalls atomar mit der Writerumschaltung | **E-10 muss vor Freigabe dieses Schritts bestehen.** Erstes neues Result anhand eigener Anweisung nutzbar; F-10/F-13/F-14, native Resultwege und dreifacher Roundtrip geprüft. Kein normales `unavailable` und kein ausgelieferter Wheel-only-Bootstrap. |
| **PP-07 – Chat-Vertrag und Dokumentationsabschluss** | Bereits funktionsfähigen Bootstrap übergreifend abgleichen; gemeinsame Spezifikationsauswahl, Legacy-/Fehler-Fallback, Pack-Auslieferung und alle betroffenen Dokumente abschließen. **Keine erstmalige Bereitstellung des für PP-06 nötigen Startwegs.** | PP-03 bis PP-06 | Nutzbare Beispiele, E-07/E-08/E-09 und fachlicher Anweisungsreview; kein Widerspruch zwischen Normsatz, Plan und eingebetteter Anleitung. |
| **PP-08 – Gesamtregression und Release-Nachweis** | Finale Installationsartefakte und finale PYZ auf unterstützten Plattformen prüfen; Last-/Fault-Fälle, Bestands-Watcher-/Result-Publikationsregression und tatsächliche CIFS-Nachweise getrennt erfassen; Architekturreview und Bericht. | PP-00 bis PP-07 | Gesamte Definition of Done erfüllt; Nachweise an konkrete Commits und Artefakthashes gebunden, offene native/CIFS-Abnahmen nicht durch lokale Tests ersetzt. |

PP-04 und PP-05 können vorbereitet werden, während `pack` entsteht. Der Writer darf jedoch erst in einem auslieferbaren Stand umgestellt werden, wenn Reader, Provider, eingebettete Anweisung und PYZ die gemeinsam deklarierten Fähigkeiten tatsächlich besitzen. Insbesondere darf `pack_patch` nicht in Capability-Daten angekündigt werden, obwohl der ausgelieferte Code die Operation noch nicht enthält.

Das Bootstrap-/Writer-Gate ist eine **funktionale Abhängigkeit**, kein zusätzlicher Nutzerarbeitsschritt und keine zwingend zusätzliche Commit- oder Bundle-Grenze. Eng gekoppelte Vorbereitung und Writerwechsel dürfen gemeinsam umgesetzt werden, wenn kein kaputter Zwischenstand ausgeliefert wird und der Durchstich vor der Freigabe besteht.

### 18.3 Wahrscheinliche Änderungsstellen im gelieferten Stand

Diese Zuordnung ist eine Bestandsorientierung, keine Pflicht zum Beibehalten privater Modulnamen bei sinnvoller kleiner Refaktorierung:

| Bereich | Vorhandene Ansatzpunkte |
|---|---|
| Öffentliche API/Typen/CLI | `src/patchharbor/api.py`, `api_types.py`, `cli.py`, `application.py`, JSON-Adapter. |
| Neue Pack-Orchestrierung | Neues eng begrenztes internes Pack-Modul; Wiederverwendung von `patch_manifest.py`, `patch_package.py`, `patch_inspection.py`, `bundle_handoff.py`. |
| Quellinventar/Modi/Dateien | `bundle_paths.py`, `payload_modes.py`, `resource_policy.py`, `platform/filesystem.py` und passende Plattform-Publikationsadapter. |
| Referenzen und neue Formate | `result_reader.py`, `result_runtime.py`, `result_verification.py`, Result-/Exchange-/Archiv-/Recovery-Aufrufpfade. |
| PYZ-Build und Profil | `build_backend.py`, `scripts/build_release.py`, neues PYZ-Profilmodul; bestehender `runtime_wheel.py` für Legacy-Lesen erhalten. |
| Runtime-Erzeugerbindung | `runtime_artifact.py`, `result_resources.py`, request-lokale Vorbereitung. |
| Result-Publikation und Politiktrennung | `result_bundle_writer.py`, `result_bundle.py`, eigene temporäre Verifikation/Sync/Hashbindung, sichere Plattformadapter; Bestandsvertrag in `docs/result-publication-cifs.md` erhalten, Pack-Politik getrennt. |
| Vorlagen/Bootstrap | `chat_instructions.py`, kanonische Ressourcen, `scripts/runtime_bootstrap.py`, `CHAT_INSTRUCTIONS.md`. |
| Bestandstests | Inspect-/Reference-, Runtime-/Packaging-, Result-/Recovery-, CLI/API-/Mode-Tests; neue Pack-/PYZ-Funktionsmodule. |

**PLAN-03.** Alte und neue Runtime-Identitäten und Rezeptprofile dürfen während des Übergangs nicht durcheinandergeraten. Ein vorübergehend zusätzlich vorbereitetes Profil ist nur ein Implementierungszwischenstand, kein dauerhaftes Doppelartefakt im Result. Falls eine sichere atomare Umstellung eng gekoppelte Änderungen erfordert, werden deren Commit-/Paketgrenzen entsprechend angepasst, statt einen absichtlich kaputten Zwischenstand auszuliefern.

### 18.4 Dokumentation und Tests pro Schritt

**PLAN-04.** Jeder Schritt enthält die zu ihm gehörenden Tests und Dokumentationsänderungen. PP-07 ist ein übergreifender Abschlussabgleich, kein Aufschub der für PP-06 erforderlichen Bootstrap-Funktion oder eingebetteten Startanweisung. PP-08 ist der finale Integrationsnachweis, kein Ersatz für fehlende frühere Sicherheits-/Funktionstests. Der erste neue Writerstand wird bereits nach `MIG-02`/`E-10` geprüft.

Commit-, Push- und CI-Aktionen erfolgen ausschließlich nach dem bestehenden beauftragten Entwicklungs-/Apply-Ablauf. `pack` selbst kennt diese Planung nicht und führt keine solchen Aktionen aus. Eine bloße Spezifikationsübernahme ist kein abgeschlossener Umsetzungsschritt und kein Release.

## 19. Abnahme und Definition of Done

### 19.1 Zentrales Abnahmeszenario

> Eine unveränderte, regulär installierte PatchHarbor-Version erzeugt ohne zusätzliche manuelle Vorbereitung ein vollständiges Result mit einer passenden PYZ. Diese PYZ wird in einer frischen gewöhnlichen Python-Laufzeit ohne PatchHarbor-Installation verwendet. Sie erzeugt mit `pack` aus vorbereiteten Inhalten ein Patchformat-1-Paket, validiert die geschriebenen Bytes gegen genau dieses Result und veröffentlicht genau diese Bytes. Das Paket lässt sich anschließend über den regulären Apply-Weg in einer passenden isolierten Repositoryinstanz verarbeiten. Ein durch die PYZ erzeugtes weiteres Result enthält wiederum dieselbe kanonische PYZ. Der Watcher ist nicht in der PYZ enthalten.

### 19.2 Verbindliche Freigabebedingungen

**DONE-01.** Die Erweiterung ist erst vollständig umgesetzt, wenn alle folgenden Bedingungen nachweislich erfüllt sind:

- Normale Installation bleibt funktionsfähig, einschließlich separat installiertem Watcher; neue Results enthalten standardmäßig nur die PYZ-Runtime.
- PYZ-CLI und öffentliche API besitzen den vorgesehenen Core-Funktionsumfang mit denselben Sicherheitsregeln; keine zweite KI-Implementierung.
- `pack` erfüllt Eingabe-, Bindungs-, Modus-, Handoff-, phasenunabhängigen Fehler- und No-replace-Vertrag; liefert nach bestätigter Publikation auch bei Cleanup-Warnung vollständige Erfolgsdaten und führt weder Entrypoint noch externe Werkzeuge aus.
- Leser für alte und neue Results, konservative Altbehandlung, Diagnosepriorität und gemeinsame Resultwege sind geprüft. Der unveränderte Result-/CIFS-Sync-/Retry-/Hashvertrag ist auch für Format 3 nachgewiesen; Pack verwendet dagegen die ausdrücklich getrennte Erstfassung ohne Stabilitäts-Retries.
- Die Writerfreigabe erfolgte mit funktionsfähigem eingebettetem Bootstrap; das erste neue Result bestand den an seine eigene Anleitung gebundenen Durchstich (`E-10`).
- Reproduzierbarkeit, request-lokale Herkunft, Selbstupdate und mindestens drei Result-/PYZ-Generationen sind mit konkreten Artefakten nachgewiesen.
- Die relevanten Z-, F-, P-, S- und E-Tests sowie die fortgeltenden funktionalen Regressionen bestehen in den vorgeschriebenen Lanes; nicht ausgeführte native Nachweise werden nicht durch lokale Annahmen ersetzt.
- Hauptspezifikation und Ergänzung sind als gemeinsamer Satz mit den ausdrücklich begrenzten Ausnahmen eingeordnet; Commitplan, README, API-/Format-/Runtime-/Pack-Dokumentation und generierte Chat-Anweisungen widersprechen diesem Satz nicht. Die Auswahl beider Dateien und echte Konkurrenzfälle sind fachlich reviewed.
- Der finale Bericht nennt geprüften Commit, Interpreter/Plattform, Installationsweg, Testauswahl, relevante Skips, PYZ-Hash/Content-ID und tatsächliche Resultate. Offene Blocker sind ausdrücklich genannt.

Ein erfolgreiches `inspect`, ein Hashvergleich, ein einzelner Linux-Durchlauf oder eine grüne Source-Unit-Test-Suite allein erfüllen diese Definition nicht. Eine Release-Veröffentlichung oder ein Tag bleibt eine gesonderte autorisierte Handlung.

### 19.3 Nicht durch diese Datei erledigt

Diese Dokumentauslieferung implementiert keine neue Funktion, installiert keine Runtime auf dem Zielrechner, verändert keine Repositorykonfiguration und startet weder Commit, Push, Watcher noch CI. Die beschriebenen Tests sind Anforderungen an die spätere Umsetzung, keine behaupteten heutigen Produkttestergebnisse.

## 20. Nachweise, Quellen und Änderungsprotokoll

### 20.1 Repositoryquellen

Die folgenden Referenzen beziehen sich ausschließlich auf die in Abschnitt 1.2 gebundene Upload-Basis. Pfade sind relativ zu deren `base/`:

| Kürzel | Quelle | Relevanz |
|---|---|---|
| **B1** | `spec/SPECIFICATION.md`, insbesondere §§ 1, 2.2, 5, 15–19.6a, 21, 23, 26.3/26.6/26.8 und 32–41 | Bestehender Produkt-, API-, Runtime-, Result-, Chat- und Testvertrag; präzise begrenzte Ablösung durch diese Ergänzung. |
| **B2** | `CHAT_INSTRUCTIONS.md`, insbesondere §§ 3–4 und 7–8; `src/patchharbor/bundle_handoff.py` | Bootstrap-/Spezifikationsauswahl, Dateinamen/Suffix, Manifest, passive Begleitdateien und Bedeutung der Paketpfade. |
| **B3** | `src/patchharbor/apply_mutation.py`, `apply_preflight.py`, `patch_package.py`, `payload_modes.py`, `bundle_paths.py` | Vor-Entrypoint-Nutzdateien, Moduspolitik und sichere Paketgrenzen. |
| **B4** | `build_backend.py`, `src/patchharbor/runtime_wheel.py`, `runtime_artifact.py`, `result_resources.py`, `chat_instructions.py` | Bestehende kanonische Erzeugung, Identität, request-lokale Ressourcen und anzupassende Verzeichniszugriffe. |
| **B5** | `src/patchharbor/result_reader.py`, `result_runtime.py`, `inspection_output.py`, `api.py`, `api_types.py`, `cli.py`, `errors.py`, `exit_status.py`, `resource_policy.py` | Referenzschema, geschlossene Wheel-Capabilities, bestehende Ergebnisse, Fehlercodes und Budgets. |
| **B6** | `.github/workflows/acceptance-tests.yml`, `docs/test-parallelism.md`, Hauptspezifikation § 33 | Vorhandene Plattform-/Python-Lanes, manueller Workflow und Acceptance-Timeout. |
| **B7** | Hauptspezifikation §18.5; `docs/result-publication-cifs.md`; Result-Publikations-/Verifikations- und Plattformmodule | Bestehende Eigentums-/Sync-/Retry-/Hash-/Diagnosepolitik für eigene Result-Ausgaben; unverändert auch bei Format 3, keine implizite Übertragung auf Pack-Eingaben. |
| **B8** | `planning/watcher-events/commit-plan.md` und `planning/result-publication/commit-plan.md` | Gebundener Planstatus: Watcher abgeschlossen; im nachfolgenden CIFS-Plan dokumentierte noch offene Apply-/Windows-/CIFS-Nachweise vor Umsetzung aktuell abgleichen. |

Die frühere Gesprächserklärung, nach der der Entrypoint grundsätzlich erst alle vollständigen Dateien ins Ziel kopiere, ist **keine Grundlage** dieses Dokuments. Maßgeblich ist der kontrollierte Core-Payload-Schritt vor dem Entrypoint gemäß Abschnitt 3.2. Ebenso wird die frühere pauschale Aufnahme des Watchers in den PYZ-Umfang ausdrücklich nicht übernommen.

### 20.2 Technische Primärquellen

Die technischen Primärquellen aus Revision 1 werden für Revision 2 unverändert als Referenzen weitergeführt; diese Korrektur umfasst keine erneute externe Recherche. Die Python-Quellen erklären technische Möglichkeiten und Grenzen. Die hier festgelegten Profile, Metadatenschemata, Hashableitungen, Limits, Publikationsregeln und Arbeitspakete sind **eigene PatchHarbor-Produktentscheidungen**, keine automatisch durch Python erfüllten Garantien.

| Kürzel | Primärquelle | Bezug |
|---|---|---|
| **Q1** | Python 3.12, `zipapp`: `https://docs.python.org/3.12/library/zipapp.html` | Direkt ausführbare ZIP mit `__main__.py`, vorhandener Interpreter, ZIP-Anwendungsformat. |
| **Q2** | Python 3.12, `zipimport`: `https://docs.python.org/3.12/library/zipimport.html` | Modulimport aus ZIP-Archiven und dessen Grenzen. |
| **Q3** | Python 3.12, Kommandozeile: `https://docs.python.org/3.12/using/cmdline.html` | Interpreterargumente und Schalter `-I`, `-S`, `-B`; keine Sicherheits-Sandbox. |
| **Q4** | Python 3.12, `importlib.resources`: `https://docs.python.org/3.12/library/importlib.resources.html` | Verankerte Ressourcen ohne vorausgesetzten realen Paketverzeichnispfad. |
| **Q5** | Python 3.12, `zipfile`: `https://docs.python.org/3.12/library/zipfile.html` | ZIP-Struktur, Metadaten und Kompressionsmethoden als technische Grundlage. |

### 20.3 Revisionen

| Revision | Datum | Änderung |
|---|---|---|
| 1 | 2026-10-07 | Erste vollständige separate Spezifikationserweiterung für Result-PYZ ohne Watcher und reguläres `pack`, einschließlich Formatübergang, CLI/API, Fehler-/Sicherheitsvertrag, Dokumentation, Testmatrix und Umsetzungsplan. |
| 2 | 2026-10-07 | Integrationsreview umgesetzt: gemeinsamer Spezifikationssatz und eng begrenzte Bestandsausnahmen; unveränderte Prüferkategorien; Bootstrap als Writer-Gate; Result-/CIFS-Bestandsschutz und ausdrücklich getrennte Pack-Publikationspolitik; vollständiger Erfolg trotz Cleanup-Warnung und getrennte CLI-Ausgabefehler; Paket-ID/Zeit für beide Ausgabearten und Abgrenzung zum Chat-Zähler. Testmatrix, Dokumentationspflichten, Plan und Abnahme entsprechend nachgeführt. Keine Implementierung oder Produktabnahme. |

### 20.4 Nachverfolgung der Korrekturen aus dem Integrationsreview

Die Review-Unterlagen `REVIEW_SPECIFICATION_EXTENSION_PYZ_PACK.md` und `PRUEFNACHWEISE_PYZ_PACK_REVIEW.json` beziehen sich auf Revision 1. Sie sind Arbeitsnachweise, **keine zusätzlichen normativen Spezifikationen** und keine für die Nutzung dieser Revision erforderlichen Laufzeitdateien. Die Anforderungen der korrigierten Revision stehen vollständig in diesem Dokument und seinem ausdrücklich benannten Basisdokument.

| Review-ID | Korrektur in Revision 2 | Zugeordneter späterer Nachweis |
|---|---|---|
| R-01 | `PACK-03/22`: bestehende Kategorien 3/4/5/9/10 phasenunabhängig erhalten; neue Argument-, Ausgabe- und Publikationsfälle getrennt. | P-04/P-08/P-11, S-15, Bestands-Inspect-/Validate-Regression. |
| R-02 | `GOV-03`, `CHAT-06`, `DOC-01`, `PLAN-01`: gemeinsamer Normsatz und expliziter Featureplan, keine künstliche Mehrdeutigkeit durch Ergänzung. | E-09 und Review des konkreten Commitplans. |
| R-03 | `MIG-02`, PP-04/PP-05/PP-06 und `PLAN-04`: nutzbarer Bootstrap samt eingebetteter Vorlage vor oder atomar mit Writerumschaltung. | F-10 und E-10 als PP-06-Freigabegate. |
| R-04 | §1.3/`GOV-04`: Ausnahmen zu Core-Paketerzeugung, rekursivem Inhaltsbaum, Handoff/Namen und Trennung Result-/Pack-Publikation ausdrücklich begrenzt. | P-09, F-14 und Bestands-Exchange-/Apply-Regression. |
| R-05 | `GOV-02`, `MIG-06`, `PACK-23`, `TEST-07`, PP-00/PP-01/PP-06/PP-08: tatsächlicher Planstatus, Result-CIFS-Vertrag erhalten, Pack zunächst ohne Stabilitäts-Retry. | F-13/F-14/S-17, getrennte tatsächliche Windows-/CIFS-Nachweise. |
| R-06 | `PACK-03/04/05/18/20/22`: bestätigter Publikationserfolg bleibt vollständig zugänglich; Cleanup-Warnung, CLI-Ausgabe und Unterbrechungen getrennt. | S-12/S-16/S-18, API ohne Observer und intakter/defekter CLI-Ausgabepfad. |
| K-01 | `PACK-04/15`: eine Paket-ID und Erzeugungszeit pro Auftrag bei beiden Ausgabearten. | P-17. |
| K-02 | `PACK-15`, `CHAT-05`: Chat-Bundle-Nummer unabhängig von Paket-ID und Referenz-Run-ID; kein neuer Zähler oder Entrypoint-Rewrite. | P-18 und fachlicher Chat-/Planreview. |

Die Überarbeitung schließt die genannten Vertrags- und Planungslücken **auf Dokumentebene**. Sämtliche in der Tabelle genannten Produkttests und Plattformnachweise sind weiterhin Aufgaben der späteren Implementierung. Das erfolgreiche Prüfen dieser Markdown-Datei ersetzt sie nicht.
