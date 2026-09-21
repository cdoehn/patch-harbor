# PatchHarbor 1.2.0 – Chat-Initialisierung

**Vertragsversion:** 1.2.0<br>
**Patch-Paketmarker:** `patch-harbor`<br>
**Patch-Paketformat:** `1`<br>
**Result-Bundle-Marker:** `patch-harbor-result-bundle`<br>
**Fingerprint-Algorithmus:** `patchharbor-state-v1`<br>
**Entrypoint-Pflichtmarker:** `# PATCHHARBOR`

Diese Datei ist die verbindliche Handlungsanweisung für einen externen
Entwicklungs-Chat. Halte dich an diesen Vertrag, wenn du aus einem PatchHarbor
Result Bundle ein Patch-Paket für ein registriertes Repository erzeugst.

## 1. Deine Aufgabe und die Sicherheitsgrenze

Der Chat entwickelt; der lokale Runner bindet jedes Patch-Paket an genau eine
registrierte Repository-Instanz und ihren geprüften Zustand.

PatchHarbor registriert lokale Git-Instanzen per UUID v4, prüft Base-Commit und
vollständigen Fingerprint, validiert sichere ZIP-Pakete, ordnet sie per repo_id
zu und schreibt geprüfte Payloads vor genau einem Bash-/PowerShell-Entrypoint.
Es erfasst stdout/stderr, Exit-Code, Laufzeit, Abbruch und Toolfehler, erzeugt
Result Bundles und unterscheidet diese von Patch-Paketen. Exchange-Auswahl und
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
patchharbor apply [PATCH_ZIP]
patchharbor apply --dry-run [PATCH_ZIP]
patchharbor fs run QUELLE
patchharbor-watcher
```

### Vorhandenen Core nutzen

Prüfe vor Entrypoint-Code die tatsächlich vorhandenen Core-/API-Funktionen.
Nutze sie für Payload-Ausbringung, atomare Ersetzung, Pfad-/Sicherheitsprüfung,
Repository-Zuordnung, Zustand und Archivierung statt eigener Nachbauten.
Fehlende allgemeine Infrastruktur gehört bevorzugt als eigener geprüfter
Schritt in den Core. Keine erfundene API, rekursiven apply/bundle-Aufrufe oder
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
Ordner wählen. Der Watcher lädt pro Poll ihre lokalen Einstellungen über Core,
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

### Apply, Watcher und Archivierung

`bundle` veröffentlicht ohne explizites Ausgabeziel im konfigurierten
Exchange-Ordner. Ein manueller parameterloser `apply` löst zuerst das aktuelle
Arbeitsverzeichnis einschließlich Repository-Unterverzeichnissen auf und
betrachtet ausschließlich Pakete für genau diese registrierte Repository-Instanz.
Unter den vollständig state- und replay-kompatiblen Kandidaten gewinnt der
Kandidat mit dem höchsten `mtime_ns`; bei Gleichstand entscheidet der Unicode-NFC-normalisierte
Dateiname deterministisch. Einen weiterhin passenden fehlgeschlagenen Patch darf
der manuelle Aufruf bewusst erneut versuchen. Der Watcher bleibt dagegen global
für alle registrierten Repositorys und verwendet einen automatischen Ursprung,
der fehlgeschlagene Pakete nicht erneut pollt. Erfolgreiche Pakete bleiben in
beiden Fällen Replay-geschützt. Ein expliziter `PATCH_ZIP` darf weiterhin über
seine `repo_id` ein anderes registriertes Repository als das aktuelle auswählen.
`fs run` ist der ältere explizite Runner.

Der normale Exchange-Scan kann ausschließlich nachweislich überholte, vollständig
geprüfte eigene Bundles in `PatchHarbor-Archive` direkt unter dem Exchange-Ordner
verschieben. Ein leerer Archivname (`configure archive-dir --clear`) deaktiviert
dies. Es werden keine Bundles gelöscht. Alter und Dateiname sind keine Beweise.
Patch-Pakete benötigen einen erfolgreichen Replay-Beleg mit bestätigtem
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
Verwende sie niemals als Repository-Zuordnung oder in `patch.json`. Dafür gelten
weiterhin ausschließlich die vollständigen Bindungswerte aus `context.json`.

### Unterbrochene Attempts und Erfolgsnachweis

Neue Apply-Result-Manifeste verknüpfen `patch_sha256`, `run_id`, `repo_id`, die
vollständige erwartete Bindung und optional `completed_commit`. Replay-Format 4
speichert außerdem `attempt_run_id` und eine vor Veröffentlichung lokal verankerte
`result_sha256`. Nur ein vollständig passendes erfolgreiches Result und sauberer
Git-Nachweis unter dem echten freien Repository-Lock erlauben eine automatische
Reparatur `attempted -> succeeded`. Ältere Einträge ohne Beweise bleiben unverändert.

`screen -ls` ohne Socket beweist keinen Prozessabbruch. Ein `attempted`, ein dirty
Working Tree oder ein fehlendes Result kann zu einem noch laufenden Apply gehören.
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
für `patch.json` dienen. Das aktuelle Result Bundle ist im normalen
Entwicklungsworkflow die Quelle der vollständigen Bindungswerte. Wird
ausnahmsweise ein separater Kontext übergeben, muss er aus
`patchharbor context --json` stammen. Rekonstruiere niemals vollständige
Kennungen aus verkürzten Präfixen.

Behaupte nicht aus Gesprächserinnerung, den aktuellen Repository-Zustand zu
kennen. Fehlt ein aktuelles oder ausreichend vollständiges Result Bundle,
verwende `REPOSITORY_STATE_INCOMPLETE` nach Abschnitt 10 und erzeuge kein
Patch-Paket.

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
- bei einem vorherigen Apply zuerst `logs/run.json`,
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

## 4. Zielversion, Commit-Plan und Spezifikation finden

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

## 5. Spezifikation, Plan, Code und Auftrag abgleichen

Die Spec definiert den Vertrag, der Plan seine Zerlegung; der Snapshot zeigt
die tatsächlich vorhandenen Voraussetzungen.

Prüfe vor der Patch-Erstellung:

- ob Kennung, Commit-Message und Scope zum nächsten Plan-Schritt passen,
- ob die Commit-Beschreibung die zugehörigen Spec-Anforderungen abdeckt,
- ob der Code die vorausgesetzten früheren Schritte tatsächlich enthält,
- ob die Benutzeraufgabe eindeutig und technisch sinnvoll ist,
- ob die Änderung innerhalb eines einzelnen fachlich geschlossenen Commits
  bleibt.

Kleine notwendige Lücken im selben Commit-Scope schließen und als
`PLAN_SPEC_MINOR_DEVIATION` melden.

Scope-Erweiterungen, vorgezogene Planpunkte, neue Architekturentscheidungen
oder Widersprüche nicht still umsetzen. Bei falschen, unsicheren oder unmöglichen
Vorgaben mit passendem Code stoppen und konkret nachfragen.

## 6. Commit-Art und Zähler

Es gibt genau drei sichtbare Commit-Arten.

### `PLAN`

- Übernimm Kennung, Commitposition und Commit-Message exakt aus dem Plan.
- Zeige den Zähler als `aktuelle Position / Gesamtzahl`.
- Aktualisiere den Planfortschritt im selben Commit, falls der Plan dies
  vorsieht.

### `FIX`

- Ein Fix gehört zu genau einem Plan-Commit.
- Verwende `<PLAN-ID>-FIX<n>`, beginnend mit `FIX1`.
- Die Commit-Message beginnt mit `Fix:` und beschreibt die konkrete Reparatur.
- Ein Fix erhöht weder Gesamtzahl noch erreichte Position der Plan-Commits.
- Zeige in der UI die unveränderte Planposition.

### `OFF-PLAN`

- Wähle eine kurze sinnvolle Kennung und Commit-Message.
- Zeige `OFF-PLAN` unübersehbar.
- Verändere den Plan-Zähler nicht.
- Existiert ein Plan, zeige `-- / <Gesamtzahl>`; andernfalls `-- / --`.

Ein normaler Chat-Patch erzeugt nach grünen Tests genau einen Git-Commit der
angezeigten Art. Bei roten Tests darf kein Commit entstehen. Eine Ausnahme ist
ein ausdrücklich verlangter Diagnoseauftrag oder eine beauftragte W/R/C-Folge
nach Abschnitt 8.

## 7. Genau ein sicheres Patch-Paket erzeugen

Erzeuge genau eine herunterladbare ZIP-Datei im sicheren PatchHarbor-Format.
Liefere keine parallele Shell-Datei, keinen zweiten Patch und keine alternative
manuelle Änderungsanleitung. Der Dateiname folgt exakt
`<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip`: Repository-Name zuerst,
dann `Patch`, UTC-Uhrzeit, Monat/Tag ohne Jahr und die ersten sechs Zeichen
einer Paket-UUID ohne `…`. Für Result Bundles gilt exakt
`<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip`; dessen ID6 stammt aus der
vollständigen Run-ID.

Hänge das optionale `bundle_suffix` aus der Result-`context.json` unverändert
an den Basisdateinamen an: `.txt` ergibt beispielsweise
`patch-harbor_Patch_181530_0908_abcdef.zip.txt`. Fehlendes Feld in älteren Bundles
oder leerer String bedeutet kein Suffix. Maßgeblich sind diese Metadaten,
nicht die Endung einer möglicherweise umbenannten Upload-Datei.

Der Benutzer setzt es im betreffenden Repository per `patchharbor configure bundle-suffix .txt`,
löscht es per `patchharbor configure bundle-suffix --clear` und erzeugt danach
ein frisches Result Bundle. `apply` und `bundle` benötigen keinen Schalter.
Der Core erzeugt Result Bundles; du benennst externe Patch-Pakete entsprechend.
ZIP-Inhalt und State-Bindung bleiben unverändert. Füge `bundle_suffix` niemals
in `patch.json` ein. Das geschlossene `context --json`-Schema bleibt unverändert;
bei separater Kontextübergabe muss die Suffixpräferenz zusätzlich genannt werden.
Ohne diese Information gilt kein Suffix.

Das ZIP enthält genau eine Root-Datei `patch.json`. Für Format 1 sind dort
exakt diese sieben Felder erlaubt:

```json
{
  "marker": "patch-harbor",
  "format_version": 1,
  "repo_id": "<unverändert aus context.json>",
  "base_commit": "<unverändert aus context.json>",
  "state_fingerprint": "<unverändert aus context.json>",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "entrypoint": "run.sh"
}
```

`patch.json` ist UTF-8 ohne BOM und enthält genau ein JSON-Objekt. Doppelte
Schlüssel, Kommentare, nachgestellte Daten und nicht endliche Zahlen sind
ungültig. Verwende `repo_id`, `base_commit`, `state_fingerprint` und
`fingerprint_algorithm` unverändert und vollständig aus dem aktuellen Result
Bundle. Die Terminal-UI darf diese Werte als sechs Zeichen plus `…` darstellen;
für `patch.json` gelten ausschließlich die vollständigen JSON-Werte. Ergänze
keine unbekannten Felder.

Beachte zusätzlich:

- `repo_id` ist eine kanonische kleingeschriebene UUID v4,
- `base_commit` ist die vollständige kleingeschriebene 40- oder
  64-stellige Git-Objekt-ID,
- `state_fingerprint` besteht aus exakt 16 kleingeschriebenen Hex-Zeichen,
- `entrypoint` bezeichnet genau einen vorhandenen regulären ZIP-Eintrag und ist
  nicht `patch.json`.

Das Paket enthält genau einen in `patch.json` referenzierten Entrypoint. Dieser:

- ist eine sichere relative Paketdatei,
- enthält als exakten Skriptmarker `# PATCHHARBOR`,
- wird von PatchHarbor außerhalb des Repositorys privat bereitgestellt,
- läuft mit dem Ziel-Repository als aktuellem Arbeitsverzeichnis,
- führt die vorgesehenen Prüfungen und den Git-Commit aus,
- beendet sich bei einem Fehler mit einem von null verschiedenen Exit-Code,
- ruft nicht selbst `patchharbor bundle` auf.

Neue Chat-Patches enthalten zusätzlich genau diese beiden passiven Begleitdateien:
`PATCHHARBOR_META/CHAT_INSTRUCTIONS.md` und `PATCHHARBOR_META/environment.json`.
Erzeuge die Anleitung für jedes Paket neu aus der statischen Vorlage plus dem
Umgebungssnapshot des jüngsten Result Bundles, nicht aus deiner Chat-Laufzeit.
Übernimm die bekannten Zielrechnerdaten und deren `captured_at`, setze
`bundle_type` auf `Patch` und `bundle_filename` auf den neuen Namen. Die vier
Werte in `repository_context` müssen exakt zu `patch.json` passen. Unbekannte
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
Enthaltene Archive werden nicht rekursiv als weitere Patch-Pakete geöffnet.

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
ZIP-Gesamtdaten und höchstens 1.000 ZIP-Einträge.

Nimm nur Dateien auf, die für den Auftrag notwendig sind. Prüfe im Entrypoint
vor dem Commit, dass keine unerwarteten Repository-Dateien verändert wurden.

## 8. Tests, Commit und lokale Ausführung

Der Entrypoint führt die zur Änderung passenden Tests aus. Bei breitem,
riskantem oder schichtenübergreifendem Scope führt er zusätzlich die vollständige
Projektsuite aus.

Für den dokumentierten Pixel-/Termux-Workflow gilt:

- keine künstlichen Einzeltest-Timeouts,
- kein künstlicher Gesamtsuite-Timeout,
- fachlich notwendige interne Prozess- und Timeout-Tests bleiben unverändert.

Für dieses PatchHarbor-Repository darf ohne vorhandene `uv.lock` kein
`uv run --frozen` verwendet werden. Entwicklungsabhängigkeiten werden aus
`.[dev]` in der lokalen `.venv` vorbereitet, ohne die produktive pipx-Installation
zu verändern. Den vollständigen Lauf z. B. mit
`.venv/bin/python tools/run_tests.py` starten: xdist `auto`, Controller-Prüfung,
kein pytest-timeout. Lokal/Bundles: Vollsuite nur parallel (`--workers 2/4`
optional); `--serial`-Vollreferenz nur in CI.
`--session-timeout=0` ist kein Abschalten der Frist und darf dafür nicht verwendet
werden. Keine Tests zur Geschwindigkeit erzwingen; alle fachlichen Gates bleiben.
Neue Tests prüfen Verhalten und maschinenlesbare Datenverträge, nicht
README-/Spezifikationstexte, Help-Wortlaut, Farben oder Konsolenlayout.

Erzeuge den Git-Commit erst, nachdem alle vorgesehenen Tests grün sind. Stage
nur die beabsichtigten Pfade, prüfe den Commit-Inhalt und verwende exakt die in
der UI angezeigte Commit-Message. Erhalte bereits vorhandene, nicht zum Auftrag
gehörende staged, unstaged und untracked Änderungen. Verwende kein pauschales
`git reset --hard` oder `git clean`, das Benutzeränderungen verlieren könnte.
Bei einem Fehler entsteht für den scheiternden Schritt kein Commit.

Bei beauftragten W/R/C-Folgen entsteht jeder Zwischenstand einzeln:
Änderung → Gate → Commit → nächster Schritt. Nicht zuerst den Endzustand
installieren; Fehler erhalten frühere Commits. Plan und Spec stehen unter
`planning/test-parallel/`. Der Scheduler ist ausschließlich pytest-xdist.

Der Vollvergleich `tools/verify_test_modes.py --outdir NEUER_PFAD` enthält
seriell/2/4/auto mit Hash-Seeds und gehört daher in CI, nicht in lokale Bundles.
Berichte liegen außerhalb der Quellen; Quelländerungen brauchen neue Referenzen.
Vertrag: `docs/test-parallelism.md`.

Die kanonische Patch-ZIP erhält bei ihrer finalen Festlegung eine dreistellige
`PATCHHARBOR-BUNDLE-NR`. Der Entrypoint verwendet exakt dieselbe Nummer und gibt
erst nach allen vorgesehenen Änderungen, Tests, Commits und einer abschließenden
Prüfung des sauberen Zielzustands als seine letzte eigene Erfolgszeile aus:

```text
PATCHHARBOR-BUNDLE-NR: <NNN> | APPLIED SUCCESSFULLY
```

Bei einem Fehler darf diese Zeile niemals erscheinen. Danach darf PatchHarbor
selbst noch Snapshot- und Result-Bundle-Meldungen ausgeben.

PatchHarbor führt anschließend automatisch den Result-Bundle-Versuch durch,
sobald das Ziel-Repository sicher aufgelöst wurde. Deshalb darf der Entrypoint
`patchharbor bundle` nicht rekursiv aufrufen.

Vor dem lokalen Apply darfst du nur nennen, welche Tests im Paket vorgesehen
sind. Behaupte nicht, sie seien bereits erfolgreich. Erst ein zurückgegebenes
Result Bundle mit erfolgreichem `logs/run.json`, passendem Git-Zustand und dem
erwarteten Commit erlaubt eine Erfolgsaussage.

## 9. Result Bundle nach Apply auswerten

Unterscheide nach Rückgabe eines Result Bundles mindestens:

- erfolgreicher Apply und erfolgreicher Commit,
- fehlgeschlagener Entrypoint oder Test,
- PatchHarbor-Toolfehler,
- erfolgreicher Primärauftrag mit fehlgeschlagenem Result Bundle,
- Mismatch oder andere Ablehnung vor Mutation.

Prüfe insbesondere `logs/run.json`, `logs/execution.log`, `context.json`, den
aktuellen Snapshot und den erwarteten Commit. Bei einem Fehler beschreibe kurz:

- die konkrete Ursache,
- den tatsächlich zurückgebliebenen Repository-Zustand,
- ob ein Commit entstanden ist,
- den nächsten sinnvollen `FIX`- oder `OFF-PLAN`-Schritt.

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
Patch-Bundle: keine neue Bundle-Nummer, kein Patch-Link und kein `PATCH BEREIT`.
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
4. Eigene Gmail-Adresse aus dem verbundenen Konto auflösen und dieselbe ZIP
   senden; bei Anhangsgrenzen bestätigten privaten Drive-Link plus Dateiname und
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

Commit: <Message>
Plan: <Pfad>
Spec: <Pfad>
Änderungen: <5–10 kurze Zeilen>
Tests: <vorgesehene Gates>
Noch offen: 11 Plan-Commits

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
Commit, Plan und Spec; `Änderungen` fünf bis zehn kurze Zeilen, `Tests` nur
vorgesehene Gates, `Noch offen` verbleibende Plan-Commits. Erfolgsabschluss:
genau Bereitschaftsbalken, Bundle-Nummer, Patch-Link. Der Patch-Link ist die
allerletzte Zeile der gesamten Antwort; danach folgt nichts. `PATCH BEREIT` erst
nach Existenz der Datei; vor Apply keine vorgesehenen Tests als grün behaupten.

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
