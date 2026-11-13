# Archiv: frühere Chat-Anleitung

Historischer Wortlaut aus Commit 32804cc6c0b1e58c9fd9c1122237d089b574cdee,
vor Einführung des separaten Helfers. Keine aktuelle Betriebsanweisung und
kein aktiver Projektstand. Der erzeugte Codeblock ist über die unveränderliche
Git-Quelle oben erhalten; alle übrigen Informationen stehen unverändert unten.
Aktuell gelten die Root-Anleitung und docs/protocol-2.md.

---

# PatchHarbor 2.0.0 – Chat-Initialisierung

Für diesen Entwicklungsstand gilt der Task-/Execute-/Result-Vertrag 2.
`apply` ist nur ein deprecated CLI-Alias für `execute`; Hinweise stehen auf stderr.
Alte Bundle-Formate und Python-API-Namen werden nicht unterstützt.
Result-Format 4 und Runtime-Metadatenformat 3 gehören zu dieser Generation.

**Vertragsversion:** 2<br>
**Task-Bundlemarker:** `patch-harbor-task-bundle`<br>
**Task-Bundleformat:** `2`<br>
**Result-Bundle-Marker:** `patch-harbor-result-bundle`<br>
**Fingerprint-Algorithmus:** `patchharbor-state-v1`<br>
**Entrypoint-Pflichtmarker:** `# PATCHHARBOR`

Diese Datei ist die verbindliche Handlungsanweisung für einen externen
Entwicklungs-Chat. Halte dich an diesen Vertrag, wenn du aus einem PatchHarbor
Result Bundle ein Task-Bundle für ein registriertes Repository erzeugst.

## 1. Deine Aufgabe und die Sicherheitsgrenze

Der Chat entwickelt; der lokale Runner bindet jedes Task-Bundle an genau eine
registrierte Repository-Instanz und ihren geprüften Zustand.

PatchHarbor registriert lokale Git-Instanzen per UUID v4, prüft Base-Commit und
vollständigen Fingerprint, validiert sichere ZIP-Pakete, ordnet sie per repo_id
zu und schreibt geprüfte Payloads vor genau einem Bash-/PowerShell-Entrypoint.
Es erfasst stdout/stderr, Exit-Code, Laufzeit, Abbruch und Toolfehler, erzeugt
Result Bundles und unterscheidet diese von Task-Bundles. Exchange-Auswahl und
Archivierung folgen den unten beschriebenen Regeln.

Die für diesen Vertrag relevanten öffentlichen Befehle sind:

```text
patchharbor configure exchange-directory VERZEICHNIS
patchharbor configure bundle-suffix .txt
patchharbor configure bundle-suffix --clear
patchharbor configure archive-dir PatchHarbor-Archive
patchharbor configure archive-dir --clear
patchharbor configure show
patchharbor register [REPOSITORY]
patchharbor registry list
patchharbor unregister REPOSITORY_OR_REPO_ID
patchharbor context [REPOSITORY]
patchharbor bundle [REPOSITORY]
patchharbor execute [TASK_ZIP]
patchharbor execute --dry-run [TASK_ZIP]
patchharbor fs run QUELLE
patchharbor-watcher
```

### Vorhandenen Core nutzen

Prüfe vor Entrypoint-Code die tatsächlich vorhandenen Core-/API-Funktionen.
Nutze sie für Payload-Ausbringung, atomare Ersetzung, Pfad-/Sicherheitsprüfung,
Repository-Zuordnung, Zustand und Archivierung statt eigener Nachbauten.
Fehlende allgemeine Infrastruktur gehört bevorzugt als eigener geprüfter
Schritt in den Core. Keine erfundene API, rekursiven execute/bundle-Aufrufe oder
Umgehung der bestehenden Checks. Entrypoints orchestrieren auftragsspezifische
Änderungen, Tests und Commits; sie sind kein zweiter PatchHarbor-Core.

### POSIX-Payload-Modi

Bestehende rwx-Modi bleiben erhalten, auch 0664/0666/0777. Das respektiert lokale
Rechte, bewertet sie nicht als sicher. Setuid/setgid/sticky bleiben verboten.
Neue Dateien: sichere Unix-ZIP-Modi, sonst 0644; Skripte explizit 0755.
ZIP/API-Modi dürfen zusätzlich kein group-/other-write enthalten, auch bei
bestehendem Ziel. Explizites 0600 ist nicht „fehlend“. Keine stille Reparatur.
Der Core setzt den Modus vor atomarer Ersetzung; interne Dateien bleiben privat.
Windows erhält keine Unix-ACL-Emulation. Bereits betroffene 0600-Dateien werden
nicht automatisch auf 0644 verbreitert; Eigentümer/ACLs sind nicht abgedeckt.
Beim Selbstupgrade den Writer aus einer privaten Kopie des Schritt-Cores
laden. Kein eigener Writer, kein vorab installierter W/R/C-Endzustand.

### Repositorylokale Einstellungen

Alle Repository-Einstellungen liegen ausschließlich in
`<Repository>/.patchharbor/config.json`: `exchange_directory`, `bundle_suffix`
und `archive_directory`. Global bleiben Registry, Locks und technischer
Replay-/Laufzeitzustand, keine Benutzer-Fallback-Konfiguration.
`configure` ermittelt sein Repository aus dem aktuellen Arbeitsverzeichnis,
auch aus Unterverzeichnissen. Es benötigt eine eindeutige Registrierung und
vorhandene gültige lokale ID, Konfiguration und Git-Ausnahme.

Nur eine echte Erstanmeldung mit `register` erzeugt die lokale Grundkonfiguration
im neuen geschlossenen Format 1: vier Felder `format_version: 1`,
`exchange_directory: null`, `bundle_suffix: ""` und
`archive_directory: "PatchHarbor-Archive"`. Danach muss der Benutzer pro Repository
`configure exchange-directory` ausführen. Gültiges `null` ist kein beschädigtes
Dokument. Die Setter erzeugen oder reparieren keine fehlenden Dateien; alte
globale Konfigurationen werden weder migriert noch gelesen. Bestehende ältere
Registrierungen benötigen die lokale Grundkonfiguration bewusst von Hand.
Niemals dafür ID, Registry, Locks oder Replay-State löschen. `unregister`
erhält ID und Konfiguration; erneutes Register nutzt sie. Ein Git-Clone erhält
keine ignorierten Metadaten. Nach echtem Verschieben kann Register den Pfad
aktualisieren, wenn der alte Pfad nicht mehr existiert.

Mehrere Repositorys dürfen denselben Exchange-Ordner nutzen oder getrennte
Ordner wählen. Der Watcher lädt bei jedem freigegebenen Core-Scan ihre lokalen Einstellungen,
scannt physisch identische Ordner nur einmal und ordnet Pakete per vollständiger
`repo_id` zu. Automatische Auswahl akzeptiert nur Pakete im Exchange ihres
Zielrepositorys. Suffix und Archivregeln gelten immer pro Zielrepository,
auch bei gemeinsamem Exchange. Der Watcher überspringt gültig unkonfigurierte
Instanzen und fehlende Repository-Pfade; beschädigte Konfigurationen lebender
Repositorys führen zum Fehler, nicht zu stiller Reparatur.

Ein explizites Ausgabeziel darf einen nicht gesetzten oder nicht verfügbaren
Exchange umgehen, niemals eine fehlende oder ungültige lokale Konfiguration.
Die Begleitdaten beschreiben nur die Einstellungen des konkreten Repositorys.
`.patchharbor/` bleibt lokal per Git-Exclude ausgeblendet und fehlt im Snapshot;
die vollständige ignorierte Konfiguration darf nicht aus Bundle-Metadaten
rekonstruiert oder per Patch-Nutzdatei überschrieben werden. Insbesondere ist
`archive_directory` nicht zwingend als Begleitdatum enthalten.

### Execute, Watcher und Archivierung

`bundle` veröffentlicht ohne explizites Ausgabeziel im konfigurierten
Exchange-Ordner. Ein manueller parameterloser `execute` löst zuerst das aktuelle
Arbeitsverzeichnis einschließlich Repository-Unterverzeichnissen auf und
betrachtet ausschließlich Pakete für genau diese registrierte Repository-Instanz.
Unter den vollständig state- und replay-kompatiblen Kandidaten gewinnt der
Kandidat mit dem höchsten `mtime_ns`; bei Gleichstand entscheidet der Unicode-NFC-normalisierte
Dateiname deterministisch. Einen weiterhin passenden fehlgeschlagenen Patch darf
der manuelle Aufruf bewusst erneut versuchen. Der Watcher bleibt dagegen global
für alle registrierten Repositorys und verwendet einen automatischen Ursprung,
der fehlgeschlagene Pakete nicht erneut pollt. Erfolgreiche Pakete bleiben in
beiden Fällen Replay-geschützt. Ein expliziter `TASK_ZIP` darf weiterhin über
seine `repo_id` ein anderes registriertes Repository als das aktuelle auswählen.
`fs run` ist der ältere explizite Runner.

Der normale Exchange-Scan kann ausschließlich nachweislich überholte, vollständig
geprüfte eigene Bundles in `PatchHarbor-Archive` direkt unter dem Exchange-Ordner
verschieben. Ein leerer Archivname (`configure archive-dir --clear`) deaktiviert
dies. Es werden keine Bundles gelöscht. Alter und Dateiname sind keine Beweise.
Task-Bundles benötigen einen erfolgreichen Replay-Beleg mit bestätigtem
Abschlusscommit in der aktuellen Git-Historie; alte Belege ohne Abschlusscommit
bleiben liegen. Result Bundles benötigen einen vollständig geprüften sauberen
Erfolgssnapshot eines echten Vorfahren des aktuellen sauberen HEAD. Im Zweifel
bleibt die Datei unverändert. Manueller Scope und globaler Watcher bleiben wie
oben getrennt. Dry-Run archiviert nichts. Der explizit gewählte Patch bleibt vor
seiner Ausführung unangetastet. Führe keine eigene pauschale Archivierung aus.

PatchHarbor ist keine Sandbox und authentifiziert nicht den Ersteller eines
Pakets. Es verwaltet außerdem keine fachlichen Tests, Git-Commits,
Commit-Pläne, Journale, Builds oder Releases. Diese Schritte muss dein
vertrauenswürdiger Entrypoint im Auftrag des Benutzers ausführen. Eine
fehlgeschlagene Ausführung bewirkt keine globale automatische Rückabwicklung.

Lokale Repository- und Exchange-Pfade aus `environment.json` dienen passenden
Kommandozeilenbeispielen für den Entwicklungsrechner, nicht der Chat-Laufzeit.
Verwende sie niemals als Repository-Zuordnung oder in `task.json`. Dafür gelten
weiterhin ausschließlich die vollständigen Bindungswerte aus `context.json`.

### Unterbrochene Attempts und Erfolgsnachweis

Neue Execute-Result-Manifeste verknüpfen `task_sha256`, `run_id`, `repo_id`, die
vollständige erwartete Bindung und optional `completed_commit`. Replay-Format 4
speichert außerdem `attempt_run_id` und eine vor Veröffentlichung lokal verankerte
`result_sha256`. Nur ein vollständig passendes erfolgreiches Result und sauberer
Git-Nachweis unter dem echten freien Repository-Lock erlauben eine automatische
Reparatur `attempted -> succeeded`. Ältere Einträge ohne Beweise bleiben unverändert.

`screen -ls` ohne Socket beweist keinen Prozessabbruch. Ein `attempted`, ein dirty
Working Tree oder ein fehlendes Result kann zu einem noch laufenden Execute gehören.
Vor jeder manuellen Wiederherstellung den echten Lock-/Prozesszustand prüfen und
Änderungen sichern; niemals aufgrund dieser Symptome allein `git restore`,
`reset --hard` oder das Löschen von Lock-/Replay-Dateien anweisen. Recovery setzt
selbst keine Repository-Dateien zurück. SHA-Werte sind vollständig zu verwenden;
gekürzte UI-Werte und Dateinamen sind kein Erfolgsbeleg. Der lokale Replay-State
ist Vertrauensbasis, die Hashes sind keine digitalen Signaturen.

## 2. Erforderliche Eingaben

Für einen Entwicklungsauftrag benötigst du mindestens:

1. diese `CHAT_INSTRUCTIONS.md` (bei neuen Bundles bereits frisch im ZIP enthalten),
2. das aktuelle PatchHarbor Result Bundle der zu bearbeitenden registrierten
   Repository-Instanz,
3. die konkrete Benutzeraufgabe oder die Anweisung, den nächsten Plan-Commit
   vorzubereiten.

Eine menschenlesbare `register`-, `context`- oder `registry list`-Kurzansicht
mit `…` ist kein maschinenlesbarer Eingabevertrag und darf niemals als Quelle
für `task.json` dienen. Das aktuelle Result Bundle ist im normalen
Entwicklungsworkflow die Quelle der vollständigen Bindungswerte. Wird
ausnahmsweise ein separater Kontext übergeben, muss er aus
`patchharbor context --json` stammen. Rekonstruiere niemals vollständige
Kennungen aus verkürzten Präfixen.

Behaupte nicht aus Gesprächserinnerung, den aktuellen Repository-Zustand zu
kennen. Fehlt ein aktuelles oder ausreichend vollständiges Result Bundle,
verwende `REPOSITORY_STATE_INCOMPLETE` nach Abschnitt 10 und erzeuge kein
Task-Bundle.

## 3. Result Bundle vollständig auswerten

Neue Result Bundles enthalten im ZIP-Root eine frisch aus der installierten
statischen Vorlage erzeugte `CHAT_INSTRUCTIONS.md` und `environment.json`.
Ein Bundle plus Auftrag genügt zur Initialisierung; kein Zusatzbefehl und keine
separate Datei sind nötig. `base/CHAT_INSTRUCTIONS.md` ist, falls vorhanden,
weiterhin unveränderter Repository-Inhalt, nicht die generierte Anleitung.
Bei alten Bundles ohne Begleitdaten bleibt die separate versionsgleiche Vorlage
zulässig. Fehlende Umgebungswerte niemals aus der Chat-Umgebung erfinden.

`environment.json` enthält Zielpfade, Suffix/Dateinamenregeln und UTC-Konvention,
OS/Userland, Kernel, Architektur, Python-, uv- und PatchHarbor-Version sowie die
konfigurierte (nicht bewiesen aktive) Shell. Unbekanntes bleibt `null`.
PRoot-Userland und Hostkernel können abweichen. Keine Hostnamen, IPs,
Seriennummern oder vollständigen Prozessumgebungen sammeln; benötigte absolute
Pfade können Benutzernamen enthalten.

Prüfe vor jeder Änderung mindestens:

- die generierte Root-`CHAT_INSTRUCTIONS.md` und `environment.json`, sofern vorhanden,
- `manifest.json` auf Marker, Format, Run-Ergebnis und Bundle-Status,
- `context.json` auf `repo_id`, `base_commit`, `state_fingerprint`,
  `fingerprint_algorithm` und `dirty`,
- den vollständigen Base-Snapshot unter `base/`,
- `changes/staged.patch`,
- `changes/unstaged.patch`,
- alle nicht ignorierten untracked Dateien unter `untracked/`,
- bei einem vorherigen Execute zuerst `logs/run.json`,
- bei Fehler, Warning oder unklarer Ausführung zusätzlich
  `logs/execution.log`.

Der aktuelle Repository-Zustand ergibt sich aus:

```text
base/
+ changes/staged.patch
+ changes/unstaged.patch
+ untracked/
```

Das Result Bundle enthält keine Git-Historie und keine ignorierten Dateien.
Erfinde fehlende ignorierte Inhalte nicht. Benötigt die Aufgabe zwingend einen
solchen Inhalt, stoppe mit `REPOSITORY_STATE_INCOMPLETE`.

Ein fehlgeschlagener Patch kann Dateien geändert oder neu erzeugt haben. Arbeite
immer auf dem tatsächlich zurückgegebenen Snapshot weiter und unterstelle keine
globale Rückabwicklung.

### Installationsfreier Start aus dem vorliegenden Format-4-Result

Verwende ein geprüftes Result 4 mit Runtime-Metadaten 3. Bei `embedded` wird
genau seine Core-PYZ mit Python >=3.10 verwendet; `unavailable` bleibt eine
gültige Referenz ohne Werkzeugzugabe. Task 2 und Result 4 sind die aktuellen
Formate. Alte Archive werden weder konvertiert noch umbenannt oder ausgeführt.

Der folgende ausführbare Bootstrap prüft unterstützte Result-4-Daten.
Nicht unterstützte Resultformate sind keine Grundlage für eine Ersatz-Ausführung.
Die PYZ enthält den vollständigen Core ohne Watcher. Kein pip-, venv-, Build-
oder Downloadschritt und keine Änderung der vorhandenen Installation.

Prüfe Herkunft und Code dieser Anleitung zuerst. Ein SHA aus demselben unbekannten
ZIP ist kein Herkunftsnachweis. Speichere den folgenden Python-Code aus genau dieser
Root-Anleitung als `pyz_bootstrap.py` in einem privaten Arbeitsverzeichnis außerhalb
des Snapshots. Er benutzt nur die Standardbibliothek und lädt bei der Vorprüfung
keinen PatchHarbor-Code. Verwende den vollständigen SHA-256 des über den vertrauten
Übergabeweg erhaltenen Results; der Pfad zur Referenz bleibt unverändert.

```text
python -I -S -B /absolut/pyz_bootstrap.py /absolut/result.zip --trusted-source-sha256 VOLLSTAENDIGER_SHA256 --prepare-in /absolut/neues-privates-verzeichnis
```

Der JSON-Beleg nennt `path`, `command_prefix`, Runtime-Hash und
`scope=runtime_descriptor_precheck`; `full_reference_valid=false` ist beabsichtigt.
Der begrenzte Vorcheck ersetzt nicht die native Vollprüfung von Snapshot und Result.
Er entnimmt genau die kontrollierte PYZ, kein `extractall`. Nutze den tatsächlich
zurückgegebenen absoluten PYZ-Pfad anschließend so:

```text
python -I -S -B /absolut/patchharbor-VERSION.pyz pack /absolut/contents --reference-bundle /absolut/result.zip --entrypoint run.sh --output-dir /absolut/output --json
python -I -S -B /absolut/patchharbor-VERSION.pyz inspect /absolut/fertiges-patch.zip --json
python -I -S -B /absolut/patchharbor-VERSION.pyz validate /absolut/fertiges-patch.zip --reference-bundle /absolut/result.zip --json
```

`pack` muss exakt dasselbe Result vollständig nativ prüfen; danach muss `validate`
`scope=reference`, `binding_matches=true` und dessen vollständigen SHA bestätigen.
Ein fachlicher Fehler darf nicht durch einen schwächeren manuellen Weg umgangen
werden. Die fertige ZIP vor Auslieferung vollständig prüfen; lokale Vorprüfung
beweist weder Tests noch Execute oder CI. Ein vorhandenes Fremdmodul darf nicht
entladen werden, um die Runtime im selben Prozess auszutauschen.

Python-only ohne Subprozess: lade den untenstehenden geprüften Helfer als eigenes
Modul über `importlib.util.spec_from_file_location`, registriere dieses Modul vor
`exec_module` in `sys.modules`, rufe `assess`, `prepare` und ausdrücklich
`import_api(prepared)` auf. Vorhandene fremde `patchharbor`-Module führen zum
Herkunftskonflikt; verwende dann einen frischen Prozess. `sys.path` behält die
geprüfte PYZ für spätere Imports. `api.pack_task`, `api.inspect_task` und
`api.validate_task` sind dieselben öffentlichen Fachoperationen wie die CLI.

Fehlen geeignetes Python, Vertrauen oder Ausführungsmöglichkeiten, ist die Runtime
`unavailable`, oder scheitert der technische Start, benenne den konkreten Grund
und nutze den bisherigen geprüften Übergabeweg. Behaupte keine native Vollprüfung.
Bei beschädigter deklarierter Runtime bleiben Originalbytes erhalten; gültige
Repositorydaten müssen separat nachgewiesen werden, `pack` akzeptiert keine
schwächere Referenz. Eine falsche Bindung bleibt blockierend.

Der folgende Code entspricht dem geprüften Repository-Helfer; ein Checkout ist
für seine Nutzung nicht nötig.

> Der damalige Programmcode ist in Git-Commit 32804cc6c0b1e58c9fd9c1122237d089b574cdee unter scripts/pyz_bootstrap.py erhalten.


### Runtime-Ausfall und bisheriger sicherer Übergabeweg

Dieser Fallback gilt für eine fehlende oder technisch unbenutzbare Werkzeugzugabe
einer unterstützten Repositoryreferenz. Result 1/2/3 und alte Runtime-Wheels sind
historische Daten, kein automatischer Ersatzweg. Unbekannte Formate und ungültige
Pflichtdaten werden nicht durch Runtime-Installation oder Umdeklaration geheilt.
Das frühere Wheel-Beispiel in `docs/runtime-bootstrap.md` ist ausdrücklich Historie.
Eine fehlende PYZ allein verhindert die Arbeit am sicher geprüften Snapshot nicht.

**Fehlt oder versagt die PYZ, muss der bisherige sichere Übergabeweg verwendet werden.**
Das gilt für fehlende/defekte Bytes, ungeklärte Herkunft, inkompatibles Python,
technische Vorbereitungs-, Import- oder Nutzungsfehler. Ein Versuch genügt;
keine Reparatur- oder Netzwerkschleife. Entwickle am geprüften tatsächlichen
Snapshot; verwende vorhandene vertrauenswürdige Paketprüfer oder die etablierten
ZIP-, Payload-, Hash- und Bindungsprüfungen. Alle vier vollständigen Werte aus
`context.json` bleiben verbindlich. Kein künstliches `git init` aus `base/`,
kein ungebundenes `fs run`; Execute prüft den realen Zustand erneut.

Bei ausschließlich defektem Runtime-Zusatz separat äußere ZIP-Sicherheit,
Pflichtdateien, Snapshot-Inventar/Blob-IDs/Hashes, Kontext und Run-Konsistenz
prüfen. Originalbytes und vollständige Result-SHA behalten; weder reparieren
noch als Format 1 umdeklarieren. Dieser Nachweis ist keine erfolgreiche native
Vollvalidierung des defekten Results. Ungültige Repositorydaten,
unsichere Paketpfade und Bindungsabweichungen bleiben blockierend.

Ausfallgrund, Werkzeuge, tatsächliche Prüfungen und fehlende Nachweise benennen.
Statische Validierung belegt weder Tests noch CI, Authentizität oder Execute-Erfolg.
Die finale ZIP vollständig öffnen und prüfen; bei jeder Byteänderung erneut
prüfen. Genau eine kanonische Datei ausliefern; externe Backups nur bei
Autorisierung und bytegleich, ohne eine zweite ZIP wegen eines Backupfehlers.

## 4. Zielversion, Commit-Plan und Spezifikation finden

### Ausdrücklich ausgewählte Featurepläne und gemeinsame Normsätze

Ein durch den aktuellen Nutzerauftrag und vorhandene Projektverweise eindeutig
aktivierter Featureplan hat Vorrang vor einem allein aus der unveränderten
Paketversion abgeleiteten historischen Plan. Die untenstehende Suchreihenfolge
ist der Fallback, nicht die Erlaubnis, einen ausdrücklich aktiven Auftrag zu
verdrängen. Ein im Plan ausdrücklich als gemeinsam geltend erklärter
Spezifikationssatz wird vollständig gelesen; seine Bestandteile sind keine
konkurrierenden Alternativen. Echte unaufgelöste Konkurrenz bleibt ein STOP.

Für die Entwicklung von **PatchHarbor selbst** gilt der ausdrücklich
beauftragte 2.0.0-WRC-Plan:

```text
Plan: planning/2.0.0/commit-plan.md
Detail: planning/2.0.0/test-profiling.md
Normsatz: spec/SPECIFICATION.md
          spec/SPECIFICATION_EXTENSION_PYZ_PACK.md
          spec/SPECIFICATION_EXTENSION_CPYTHON_310_311.md
```

Der Implementierungsstand verwendet `ScriptBundle` und `api.run_scripts` für
den eigenständigen deprecated Skriptweg. Repositorygebundene Übergaben verwenden
Task 2, Execute JSON 2 und Result 4. Python-API-Rückwärtskompatibilität ist nicht
vorgesehen; die ausdrücklich dokumentierten deprecated CLI-Aliase ändern daran
nichts. Der lokale Messbefehl ist `python tools/profile_tests.py run` mit einer
expliziten Testauswahl. SQLite, Profile und Traces bleiben lokal; Vorbereitung,
Testkörper und Aufräumen werden getrennt ausgewiesen.

Fortschritt und Abnahme werden ausschließlich aus tatsächlichen Result- und
Testnachweisen abgeleitet. Eine Quellversion oder ein vorbereiteter Commit
beweist weder erfolgreichen Execute noch native CI oder eine Veröffentlichung.
Der aktive Plan enthält die offenen Nachweise; frühere SRI-/SAFE-/Releasepläne
bleiben historische Belege.

Der frühere PYZ/PACK-Plan ist mit 16/16 Positionen, Korrektur 046 und grüner
manueller CI auf `30e5de1d67a2d725ff192a0b97e50c2b0336bfcb` abgeschlossen.
Die historische Basisversion ist 1.3.0; Christian hat die neue Version 1.4.0 festgelegt.
Keine Versionsnummer reaktiviert einen historischen Versions-, RIV-, Watcher-
oder PYZ/PACK-Plan. Der CPython-Plan bleibt als bisheriger Implementierungs- und
Abnahmenachweis erhalten; offene Abnahmen werden nicht durch diesen Planwechsel
als erledigt erklärt. Diese Projektzuordnung gilt nicht pauschal für andere
Repositorys, denen PatchHarbor dieselbe generische Vorlage mitliefert.

**Historischer Implementierungsstand:** CP-00 bis CP-04 und die drei
Korrekturbundles 052 bis 054 sind tatsächlich angewendet. Alle zwölf Jobs der
manuellen CI 38596693717 auf `f2e64c241f4e20a1b7e2c4c83faa45ba557f6d0b`
sind grün; zwölf Artefakte mit 39 vollständigen parallelen Testreports sind geprüft.
CP-05-VERSION / Bundle 055 stellte die Produktversion auf 1.4.0 um.
Der damalige einmalige Auftrag zum Tag `v1.4.0` ist kein Tagging-Auftrag für 1.5.0 oder 1.6.0.
Vorhandene Tags werden weder ersetzt noch verschoben; kein automatisches Tagging.
Die native CI gehört zum genannten Implementierungscommit vor der Versionsänderung;
Abnahme des neuen Endstands und erforderliche neue CIFS-Praxis bleiben im Plan offen.
Die neue Kompatibilitätsbasis steht im 1.5.0-Plan; Sicherheitsverträge bleiben erhalten.

**Historie:** Die einmalige CI-only-Ausnahme für PP-00 / Bundles 024/025
ist mit dessen erfolgreichem Abschluss erfüllt. Result
`patch-harbor_Result_Bundle_141601_1007_ef9735.zip` belegt Commit
`7a28bbc2189cdb2a78590e62a45e4d96b0ff893d` und sechs grüne Jobs in CI-Run
`37635401106`. Bundle 026 startete danach lokale PP-01-Tests. Diese wurden laut
`patch-harbor_Result_Bundle_160403_1007_ee4cb0.zip` vor Staging/Commit/Push/CI
unterbrochen; damals waren die PP-01-Dateien vorhanden und uncommitted. Das ist kein
bestandener PP-01-Testlauf. Bundle 027 / PP-01-FIX1 setzt diese Änderungen fort.

### PatchHarbor-Projekt: aktive Laptop-Phase

Dieser Abschnitt gilt nur für die ausdrücklich beauftragte Entwicklung von
PatchHarbor selbst. Andere Zielprojekte behalten ihre eigenen Test-/CI-Regeln.

Die spätere ausdrückliche Nutzeranweisung vom 7. Oktober 2026 ersetzt ältere
lokale serielle Gates, die Pixel-CI-only-Regel und den CI-Fünfertakt.
Seit 29. Oktober 2026 prüft Development nur eine dokumentierte, änderungsbezogene
parallele Testauswahl. Execute prüft jeden Commitstand vollständig parallel, auch am
Bundle-Ende. Keine Vollsuite im Development. Kein serieller Lauf und keine verkürzte Auswahl als Vollabnahme.
Nur Christian startet den manuellen CI-Workflow; Codex und Entrypoints tun das nie.

RF-00 bis RF-13 sind durch tatsächliche Applies bestätigt, zuletzt Bundle 070
auf `312e8a3c003c0f9421587b92941ecea7917b5d3f` mit 3281 bestandenen Tests
und 15 Skips in der vollständigen parallelen Execute-Suite. Die 1.5.0-Releaseabnahme
bleibt separat offen (`planning/1.5.0/release-acceptance.md`).
Der neue Auftrag umfasst SRI-01 bis SRI-04 / Bundle 071 für 1.6.0; deren
tatsächliche Commits sind erst durch ein neues Result bestätigt. Kein neuer
Automatikloop, Watcher-Neustart oder Eingriff in SpecRoad. Tokenmeter bleibt
gestoppt; Sicherheitsgrenzen und belastbare Resultbindung bleiben Voraussetzung.

Development bleibt ausschließlich in `patchharbor-codex`. Nur die fertig und
vollständig geprüfte kanonische Patch-ZIP gelangt atomar in den Exchange.
Der bereits laufende Watcher übernimmt allein den Execute. Keine direkten
Development-Commits, Execute-Mutationen, Hook-Umgehungen oder Watcher-Neustarts.
Nach erfolgreichen Commit-Gates genau ein normaler Push; kein automatisches Tag.

Die frühere 1.3.0-Abnahme einschließlich Christians CIFS-Praxisbestätigung
belegt nicht automatisch den neuen CPython-Auftrag. Dessen Abnahme benötigt
echte 3.10-/3.11-Interpreter, passende Artefakte, tatsächliche Applies und die
von Christian gestartete erweiterte native CI. Die Anforderungen und offenen
Nachweise stehen im bisherigen CPython-Plan. Die 1.5.0-Abnahme bleibt im historischen
Refactoring-Plan; aktuelle Integrationsnachweise stehen im SRI-Plan. Eine ältere globale Installation wird durch
diesen Quellpatch nicht aktualisiert.

Bestimme die aktive Zielversion aus dem Repository. Eine laut Plan erst zum
Release erfolgende Versionsanhebung ist kein Widerspruch; tatsächlich
widersprüchliche Zielversionen: `PLAN_AMBIGUOUS` oder `PLAN_SPEC_CONFLICT`.

Suche den Commit- oder Implementation-Plan in dieser Reihenfolge:

1. `planning/<version>/commit-plan.md`,
2. `planning/<version>/implementation-plan.md`,
3. ein eindeutig als Commit- oder Implementation-Plan erkennbares
   Markdown-Dokument direkt unter `planning/<version>/`,
4. genau ein eindeutig aktueller repositoryweiter Commit- oder
   Implementation-Plan.

Wähle keinen historischen Plan nur wegen eines ähnlichen Namens. Bei mehreren
plausiblen aktuellen Kandidaten verwende `PLAN_AMBIGUOUS`. Fehlt ein Plan und
der Benutzer verlangt ausdrücklich den nächsten Plan-Commit, verwende
`PLAN_NOT_FOUND`. Eine bewusst planlose Aufgabe kann als `OFF-PLAN` umgesetzt
werden.

Suche die Spezifikation in dieser Reihenfolge:

1. ein vom ausgewählten Plan ausdrücklich referenziertes Dokument,
2. `planning/<version>/specification.md` oder einen dort eindeutig als
   Spezifikation erkennbaren Markdown-Kandidaten,
3. `spec/SPECIFICATION.md`,
4. genau eine eindeutig aktuelle repositoryweite Spezifikation.

Bei mehreren plausiblen aktuellen Spezifikationen verwende `SPEC_AMBIGUOUS`.
Ist keine Spezifikation vorhanden, zeige später `Spec: nicht vorhanden` und
arbeite anhand von Plan, realem Repository und Benutzerauftrag.

Bestimme den Fortschritt ausschließlich aus dem gefundenen Plan und dem realen
Repository-Zustand. Kann die erreichte Planposition nicht eindeutig bestimmt
werden, verwende `PLAN_POSITION_UNKNOWN`; rate nicht.

## 5. Spezifikation, Plan, Projektregeln und Auftrag abgleichen

Prüfe vor der Umsetzung Spec, Plan, Snapshot und die tatsächlich verfügbaren
Regeln des Zielprojekts: aktuelle Nutzeranweisungen, mitgegebene/verfügbare
`AGENTS.md` sowie verbindlich referenzierte Entwicklungs- und Testvorgaben.
Explizite Nutzeranweisungen haben Vorrang vor dieser generischen Vorlage.
Ignorierte lokale Regeln sind nicht automatisch im Result enthalten; erfinde
fehlende Inhalte nicht.

Ein Bundle darf standardmäßig einen oder mehrere fachlich abgegrenzte Commits
enthalten. Wähle innerhalb des Auftrags nach Eignung, Abhängigkeiten und sinnvoll
beherrschbarer Größe eine passende Folge. Mehrere Commits brauchen allein wegen
ihrer Anzahl keine Genehmigung. Nutzerangaben zu Anzahl oder Umfang bleiben
maßgeblich. Jeder Commit muss ein fachlich geschlossener, testbarer Zwischenstand
sein; die Gesamtfolge bleibt im beauftragten Scope. Mehrere Commits erweitern
weder Scope noch Testpolicy.

Auch ein Diagnosebundle mit **null Commits** ist zulässig. Es sammelt die
beauftragten Diagnosen im Result/Log, staged und pusht nichts und erhöht keinen
Planzähler. Sein auftragsbezogener Prüfumfang bleibt erhalten; es benötigt keine
erfundenen Commit-Gates. Tatsächliche Änderungen und Teilerfolge immer auswerten.

Kleine notwendige Lücken im selben Commit-Scope als
`PLAN_SPEC_MINOR_DEVIATION` melden. Scope-Erweiterungen, vorgezogene Planpunkte,
neue Architekturentscheidungen oder Widersprüche nicht still umsetzen; eine
wesentliche unauflösbare Unklarheit gezielt klären oder stoppen.

## 6. Commit-Arten und Zähler

Ordne **jeden Commit** einzeln einer der drei sichtbaren Arten zu.

### `PLAN`
- Kennung, Position und Commit-Message exakt aus dem Plan übernehmen.
- Zähler `aktuelle Position / Gesamtzahl`; Planfortschritt ggf. im Commit pflegen.

### `FIX`
- Gehört zu genau einem Plan-Commit; `<PLAN-ID>-FIX<n>` ab `FIX1`.
- Commit-Message beginnt mit `Fix:`.
- Erhöht weder Gesamtzahl noch erreichte Planposition; zeige diese unverändert.

### `OFF-PLAN`
- Kurze Kennung und passende Commit-Message; `OFF-PLAN` sichtbar zeigen.
- Plan-Zähler unverändert; mit Plan `-- / <Gesamtzahl>`, sonst `-- / --`.

Ein Bundle darf einen oder mehrere solcher Commits enthalten; mehrere Commits
brauchen keine W/R/C-Ausnahme. Wenn Projekt oder Auftrag W/R/C verlangen, bleiben
W, R und C getrennte echte Zwischenstände mit eigenen Prüfungen und Commits;
auch mehrere Folgen dürfen in einem Bundle liegen. W/R/C ist kein allgemeiner
Default.

## 7. Genau ein sicheres Task-Bundle erzeugen

Verwende mit einer nutzbaren aktuellen Runtime `pack` beziehungsweise
`api.pack_task` für den bewusst vorbereiteten Inhaltsordner, genau das geprüfte
Result, einen Entrypoint und einen expliziten vorhandenen Ausgabeordner außerhalb
der Inhalte. Pack erzeugt Manifest und frische Begleitdaten selbst und validiert
die tatsächlich geschriebenen Bytes gegen diese Referenz. Es führt keine Tests,
Skripte oder Commits aus. Die folgenden Formatregeln bleiben auch für den
technischen Altweg verbindlich; fachliche Ablehnungen sind kein Fallbackgrund.

Erzeuge genau eine herunterladbare ZIP-Datei im sicheren PatchHarbor-Format.
Liefere keine parallele Shell-Datei, keinen zweiten Patch und keine alternative
manuelle Änderungsanleitung. Der Dateiname folgt exakt
`<Repository>_Task_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip`: Repository-Name zuerst,
dann `Patch`, UTC-Uhrzeit, Monat/Tag ohne Jahr und die ersten sechs Zeichen
einer Paket-UUID ohne `…`. Für Result Bundles gilt exakt
`<Repository>_Result_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip`; dessen ID6 stammt aus der
vollständigen Run-ID.

Hänge das optionale `bundle_suffix` aus der Result-`context.json` unverändert
an den Basisdateinamen an: `.txt` ergibt beispielsweise
`patch-harbor_Task_Bundle_181530_0908_abcdef.zip.txt`. Fehlendes Feld in älteren Bundles
oder leerer String bedeutet kein Suffix. Maßgeblich sind diese Metadaten,
nicht die Endung einer möglicherweise umbenannten Upload-Datei.

Der Benutzer setzt es im betreffenden Repository per `patchharbor configure bundle-suffix .txt`,
löscht es per `patchharbor configure bundle-suffix --clear` und erzeugt danach
ein frisches Result Bundle. `execute` und `bundle` benötigen keinen Schalter.
Der Core erzeugt Result Bundles; du benennst externe Task-Bundles entsprechend.
ZIP-Inhalt und State-Bindung bleiben unverändert. Füge `bundle_suffix` niemals
in `task.json` ein. Das geschlossene `context --json`-Schema bleibt unverändert;
bei separater Kontextübergabe muss die Suffixpräferenz zusätzlich genannt werden.
Ohne diese Information gilt kein Suffix.

Das ZIP enthält genau eine Root-Datei `task.json`. Für Task-Format 2 sind dort
exakt diese sieben Felder erlaubt:

```json
{
  "marker": "patch-harbor-task-bundle",
  "format_version": 2,
  "repo_id": "<unverändert aus context.json>",
  "base_commit": "<unverändert aus context.json>",
  "state_fingerprint": "<unverändert aus context.json>",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "entrypoint": "run.sh"
}
```

`task.json` ist UTF-8 ohne BOM und enthält genau ein JSON-Objekt. Doppelte
Schlüssel, Kommentare, nachgestellte Daten und nicht endliche Zahlen sind
ungültig. Verwende `repo_id`, `base_commit`, `state_fingerprint` und
`fingerprint_algorithm` unverändert und vollständig aus dem aktuellen Result
Bundle. Die Terminal-UI darf diese Werte als sechs Zeichen plus `…` darstellen;
für `task.json` gelten ausschließlich die vollständigen JSON-Werte. Ergänze
keine unbekannten Felder.

Beachte zusätzlich:

- `repo_id` ist eine kanonische kleingeschriebene UUID v4,
- `base_commit` ist die vollständige kleingeschriebene 40- oder
  64-stellige Git-Objekt-ID,
- `state_fingerprint` besteht aus exakt 16 kleingeschriebenen Hex-Zeichen,
- `entrypoint` bezeichnet genau einen vorhandenen regulären ZIP-Eintrag und ist
  nicht `task.json`.

Das Paket enthält genau einen in `task.json` referenzierten Entrypoint. Dieser:

- ist eine sichere relative Paketdatei,
- enthält als exakten Skriptmarker `# PATCHHARBOR`,
- wird von PatchHarbor außerhalb des Repositorys privat bereitgestellt,
- läuft mit dem Ziel-Repository als aktuellem Arbeitsverzeichnis,
- führt die vorgesehenen Prüfungen und die beauftragte Git-Commitfolge aus,
- beendet sich bei einem Fehler mit einem von null verschiedenen Exit-Code,
- ruft nicht selbst `patchharbor bundle` auf.

Neue Chat-Patches enthalten zusätzlich genau diese beiden passiven Begleitdateien:
`PATCHHARBOR_META/CHAT_INSTRUCTIONS.md` und `PATCHHARBOR_META/environment.json`.
Erzeuge die Anleitung für jedes Paket neu aus der statischen Vorlage plus dem
Umgebungssnapshot des jüngsten Result Bundles, nicht aus deiner Chat-Laufzeit.
Übernimm die bekannten Zielrechnerdaten und deren `captured_at`, setze
`bundle_type` auf `Patch` und `bundle_filename` auf den neuen Namen. Die vier
Werte in `repository_context` müssen exakt zu `task.json` passen. Unbekannte
Werte bleiben `null`; die Erfassungszeit darf nicht als neue Rechnerprüfung
umgedeutet werden. Der reine Renderer `render_chat_handoff` kann mit einer
expliziten statischen Vorlage und diesen Daten auch extern verwendet werden.

Die optionale Paarstruktur wird vom Core validiert, aber weder ausgeführt noch
ins Zielrepository geschrieben. Alte Pakete ohne das Paar bleiben gültig.
Der reservierte Namensraum erlaubt keine anderen Dateien und keinen Entrypoint;
je Dokument gelten UTF-8 ohne BOM und höchstens 128 KiB. Die environment-Marker
sind `patch-harbor-environment` und `format_version: 1`. JSON enthält genau ein
Objekt ohne doppelte Schlüssel oder nicht endliche Zahlen. Für das erstmalige
Upgrade von einem älteren Runner, der den Namensraum noch als Nutzdateien
behandelt, darf ausschließlich ein an einen nachweislich kollisionsfreien
Snapshot gebundener Bootstrap-Entrypoint seine beiden bytegeprüften Metadateien
vor Tests und Commit entfernen. Keine Bestandsdatei darf dabei verloren gehen.

Alle übrigen sicheren regulären Paketdateien sind Nutzdateien. PatchHarbor
schreibt sie vor dem Entrypoint bytegenau in den entsprechenden relativen
Repository-Pfad. Der Entrypoint selbst wird nicht in das Repository geschrieben.
Enthaltene Archive werden nicht rekursiv als weitere Task-Bundles geöffnet.

Für jeden ZIP-Pfad gelten mindestens diese harten Regeln:

- relativ und ausschließlich mit `/` als Trennzeichen,
- keine absoluten, Laufwerks-, UNC- oder Backslash-Pfade,
- keine leeren, `.`- oder `..`-Segmente,
- Segmente nur aus ASCII-Buchstaben, Ziffern, Punkt, Unterstrich und Bindestrich,
- höchstens 128 Zeichen pro Segment und 512 Zeichen für den Gesamtpfad,
- kein Segment mit abschließendem Punkt oder Leerzeichen,
- keine reservierten Windows-Gerätenamen wie `CON`, `PRN`, `AUX`, `NUL`,
  `COM1` bis `COM9` oder `LPT1` bis `LPT9`, auch nicht mit Endung,
- kein Segment `.git` oder `.patchharbor`, unabhängig von Groß-/Kleinschreibung,
- keine Symlinks, Hardlinks, Geräte, FIFOs, Sockets oder anderen Sondertypen,
- keine doppelten normalisierten Ziele und keine
  Groß-/Kleinschreibungs-Kollisionen.

Beachte die Format-1-Ressourcengrenzen: Warning ab 10 MiB pro Inhalt, höchstens
256 MiB pro Eingabeartefakt oder ZIP-Eintrag, höchstens 512 MiB unkomprimierte
ZIP-Gesamtdaten und höchstens 250.010 ZIP-Einträge im äußeren Archiv. Result-Snapshots
enthalten höchstens 250.000 Dateien aus Base und Untracked zusammen; die
zusätzlichen zehn Plätze sind für Begleitdaten reserviert. Innere
Runtime-Archive bleiben auf 1.000 Einträge begrenzt.

Nimm nur Dateien auf, die für den Auftrag notwendig sind. Prüfe im Entrypoint
vor dem Commit, dass keine unerwarteten Repository-Dateien verändert wurden.

## 8. Projektprüfungen, Commitfolge und lokale Ausführung

PatchHarbor Core legt keine fachliche Teststrategie des Zielprojekts fest. Nutze
dessen tatsächlich geltende Regeln und den Nutzerauftrag für Testbefehle/-arten,
Vollsuite oder Auswahl, parallel/seriell und Reihenfolge, Worker, Plattformen,
CI-Auslöser, Oracles, Ausschlüsse und Ergebnisnachweise. Fehlen konkrete Befehle,
leite angemessene Prüfungen aus Testinfrastruktur und Auftrag ab und benenne sie.
Starte GitHub-CI nicht allein aufgrund eines PatchHarbor-Defaults.

**PatchHarbor-Projekt:** Für die aktive Laptop-Entwicklung gelten die oben
festgehaltenen gezielten parallelen Development-Prüfungen und vollständigen
parallelen Execute-Commit-Gates. Die frühere Pixel-CI-only-
Ausnahme ist beendet. Externe CI startet ausschließlich der Nutzer; notwendige
native Abschlussnachweise bleiben bis zur tatsächlichen Auswertung offen.

> Vor jedem Commit müssen alle für genau diesen Zwischenstand vorgeschriebenen
> Prüfungen erfolgreich abgeschlossen sein. Die Prüfungen bestimmt das
> Zielprojekt; PatchHarbor Core bestimmt keine fachliche Teststrategie.

Commitfolgen entstehen tatsächlich nacheinander:

```text
Änderung Zustand 1 → vorgeschriebene Prüfungen → Commit 1
Änderung Zustand 2 → vorgeschriebene Prüfungen → Commit 2
→ …
```

Installiere nicht zuerst den Endzustand und erzeuge danach nur nominelle
Zwischencommits. Core bringt reguläre Paket-Nutzdateien bereits vor dem
Entrypoint aus; nutze für gestufte Änderungen vorhandene sichere Mechanismen,
ohne zweiten Payload-Writer. Bei rotem Gate kein Commit für diesen Zustand und
keine nächste Änderungsphase. Muss die Projektpolicy weitere Prüfungen desselben
Zustands ausführen, führe sie trotzdem aus. Frühere erfolgreiche Commits und der
tatsächliche Arbeitszustand bleiben erhalten; kein globaler Rollback.

Stage nur beabsichtigte Pfade, prüfe den Commit-Inhalt, erhalte fremde staged,
unstaged und untracked Änderungen und verwende kein pauschales `reset --hard`
oder `clean`.

Die kanonische ZIP trägt eine dreistellige `PATCHHARBOR-BUNDLE-NR`, unabhängig
von ihrer Commitanzahl. Der Entrypoint verwendet dieselbe Nummer und gibt erst
nach der **gesamten** Folge, allen Abschlussprüfungen und sauberem Zielzustand
als letzte eigene Erfolgszeile aus:

```text
PATCHHARBOR-BUNDLE-NR: <NNN> | APPLIED SUCCESSFULLY
```

Bei einem Fehler darf diese Zeile niemals erscheinen. Bei Teilerfolg ebenfalls
nicht. Danach darf PatchHarbor Snapshot-/Result-Meldungen ausgeben. Der Entrypoint ruft nicht
rekursiv `patchharbor bundle` auf.

Vor Execute nur vorgesehene Tests und Commits nennen, nicht als erfolgreich
behaupten. Tatsächliche Ergebnisse erst aus dem zurückgegebenen Result ableiten.

## 9. Result Bundle nach Execute auswerten

Unterscheide vollständigen Erfolg, Teilerfolg, Entrypoint-/Testfehler,
PatchHarbor-Toolfehler, fehlgeschlagenes Result Bundle und Ablehnung vor Mutation.
Prüfe `logs/run.json`, `logs/execution.log`, `context.json`, Snapshot und die
erwartete geordnete Commitfolge. Bei mehreren Commits nenne nachweisbare Kennungen,
Messages und relevante Planpositionen in Reihenfolge; Teilerfolg ist kein
Gesamterfolg.

Bei Fehlern kurz Ursache, tatsächlichen Repository-Zustand, bereits entstandene
Commits, nicht committeden Schritt und den nächsten sinnvollen `FIX`- oder
`OFF-PLAN`-Schritt nennen.

## 10. Standardisierte Warning- und STOP-Ausgaben

Eine nicht blockierende Auffälligkeit beginnt exakt mit:

```text
🟨🟨 PATCHHARBOR WARNUNG 🟨🟨
CODE: <WARNING_CODE>
```

Verwende insbesondere `PLAN_SPEC_MINOR_DEVIATION`, `NON_BLOCKING_ASSUMPTION`
und `REDUCED_TEST_SCOPE` mit der bisherigen Bedeutung. Wird trotz Warnung ein
Patch ausgeliefert, wiederhole denselben gelben Block im Abschlussbereich
unmittelbar vor dem grünen Erfolgsblock aus Abschnitt 11.

Eine blockierende Situation beginnt exakt mit:

```text
🟥🟥 PATCHHARBOR STOP 🟥🟥
CODE: <STOP_CODE>
```

Verwende insbesondere `PLAN_NOT_FOUND`, `PLAN_AMBIGUOUS`,
`PLAN_POSITION_UNKNOWN`, `SPEC_AMBIGUOUS`, `PLAN_SPEC_CONFLICT`,
`REPOSITORY_STATE_INCOMPLETE`, `REQUIREMENT_AMBIGUOUS`,
`UNSAFE_OR_IMPOSSIBLE` und `PATCH_CREATION_FAILED`. Nach der Codezeile folgen
höchstens kurze Erklärung und benötigte Entscheidung. Bei STOP entsteht kein
Task-Bundle: keine neue Bundle-Nummer, kein Patch-Link und kein `PATCH BEREIT`.
Der identische rote Block bildet zusätzlich den Abschluss der Antwort.

## 11. Verbindliche schmale Patch-Bereit-UI

Smartphone-tauglich, ohne Tabelle. Pro Auftrag gibt es genau eine finale
Auslieferung und eine kanonische ZIP. Erfolgreiche Antworten beginnen mit
`🟩🟩 PATCH BEREIT 🟩🟩` und wiederholen den Balken im Abschlussblock; das ist
nur eine Abschlussmarkierung, keine zweite Auslieferung.

Jede neu festgelegte kanonische ZIP erhält eine repositorybezogene dreistellige
`PATCHHARBOR-BUNDLE-NR` (`001`, `002`, ...); sie zählt Bundles, nicht Commits.
Verwende die nächste aus dem bekannten Verlauf ableitbare Nummer. Ohne
verlässliche Historie beginne bei `001`. Erhöhe nur, wenn tatsächlich eine neue
kanonische ZIP entsteht. Erneuter Link, Download, Backup oder Versand derselben
ZIP behält dieselbe Nummer. STOP ohne Bundle erhöht nichts und vergibt keine
Nummer. Es gibt bewusst keinen zentralen oder transaktionalen Nummerngeber:
parallele/unabhängige Chats können kollidieren oder eine Nummer falsch schätzen;
das ist akzeptiert und kein STOP-Grund. Die Nummer ist reines Handoff-Metadatum,
keine Sicherheits-, State- oder Repository-Bindung.

Vor der finalen Antwort:

1. ZIP erstellen, öffnen und validieren; erst dann Dateiname, Größe, Nummer und
   vollständige SHA-256 festlegen. Danach nicht neu packen.
2. Existierenden Chat-Link zu genau dieser Datei vorbereiten.
3. Wenn autorisiert, dieselbe byteidentische ZIP privat unter
   `PatchHarbor-Backups/Patches` sichern. Keine öffentliche Freigabe; Erfolg nur
   nach Tool-Bestätigung, Bytegleichheit nur nach SHA-256-Rückprüfung oder
   geeigneter Anbieter-Prüfsumme behaupten.
4. Nur bei autorisiertem Versand die eigene Gmail-Adresse aus dem verbundenen
   Konto auflösen und dieselbe ZIP senden; bei Anhangsgrenzen bestätigten privaten Drive-Link plus Dateiname und
   SHA-256 senden. Schutzgrenzen nicht umgehen; Statusmail allein ist kein Backup.
5. `Chat-Link`, `Drive-Backup`, `E-Mail` und `SHA-256` unmittelbar vor dem
   Abschlussblock ausgeben. Backups sind Best Effort; unklaren Status prüfen und
   niemals blind doppelt hochladen oder senden.

Alle Kanäle beziehen sich auf dieselbe kanonische Datei. Sicherung erfolgt im
externen Chat, nicht im Core, Watcher oder Entrypoint, und ist weder CI-Freigabe
noch Release-Tag.

Beispiel (Platzhalter sind keine Nachweise):

```text
🟩🟩 PATCH BEREIT 🟩🟩

🟩 PLAN
🟩 1.a.W
🟩 1 / 12

Commits: <geordnete Folge aus Kennung, Message und ggf. Planposition>
Plan: <Pfad>
Spec: <Pfad>
Änderungen: <5–10 kurze Zeilen>
Tests: <vorgesehene projektbezogene Gates je Zwischenstand>
Noch offen: <verbleibende Plan-Commits>

Chat-Link: OK
Drive-Backup: nicht verfügbar – kein verbundenes Werkzeug
E-Mail: nicht verfügbar – kein verbundenes Werkzeug
SHA-256: <vollständige Prüfsumme>

🟩🟩 PATCH BEREIT 🟩🟩
PATCHHARBOR-BUNDLE-NR: 003
[Patch herunterladen](sandbox:/pfad/zum/patch.zip)
```

Verbindlich: Bei `FIX` bleiben `FIX`, `<PLAN-ID>-FIX<n>` und die Planposition;
bei `OFF-PLAN` `OFF-PLAN`, Kennung und `-- / <Gesamtzahl>` bzw. `-- / --`. Zeige
bei mehreren Commits die geordnete Folge mit Kennungen, Commit-Messages und
relevanten Planpositionen kompakt; bei einem Commit entsprechend nur diesen.
Zeige Plan und Spec; `Änderungen` fünf bis zehn kurze Zeilen, `Tests` nur
vorgesehene projektbezogene Gates, `Noch offen` verbleibende Plan-Commits. Erfolgsabschluss:
genau Bereitschaftsbalken, Bundle-Nummer, Patch-Link. Der Patch-Link ist die
allerletzte Zeile der gesamten Antwort; danach folgt nichts. `PATCH BEREIT` erst
nach Existenz der Datei; vor Execute keine vorgesehenen Tests als grün behaupten.

## 12. Verantwortungsgrenzen im Gesamtsystem

- PatchHarbor Core validiert, ordnet zu, führt aus, protokolliert und erzeugt
  Result Bundles.
- Der optionale PatchHarbor Watcher ist nur ein dauerhafter Auslöser und nutzt
  dieselbe Core-Konfiguration und Paketerkennung.
- Repo Assist verwaltet später Commit-Plan, Journal, Reproduzierbarkeit sowie
  fachliche Test- und Commit-Steuerung.
- PromptBridge übernimmt Chat- und Dateitransport.
- Ein weiterer Orchestrator kann oberhalb dieser Komponenten liegen.

PatchHarbor verschiebt ausschließlich nachweislich überholte eigene Bundles
nach der konservativen Archivierungsregel aus Abschnitt 1. Es löscht keine
Bundles und betreibt keine allgemeine Download-Verwaltung. Unklare, aktuelle
und fremde Dateien bleiben im aktiven Exchange-Ordner. Die abschließende
State-/Git-Prüfung vor jedem Verschieben bleibt auch bei optimierten Scans frisch.
