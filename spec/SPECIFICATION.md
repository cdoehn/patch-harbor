# PatchHarbor – Spezifikation

**Dateiname:** `SPECIFICATION.md`<br>
**Produktversion:** `1.2.0`<br>
**Spezifikationsstand:** 2026-09-15<br>
**Status:** Verbindliche, freigegebene Produktspezifikation (fachlicher Vertrag) einschließlich repositorylokaler Konfiguration; keine Release-Freigabe des konkreten Commits ohne grüne Gates<br>
**Projektname:** `PatchHarbor`<br>
**Kommando:** `patchharbor`<br>
**Skriptmarker:** `# PATCHHARBOR`<br>
**Patch-Paketmarker:** `patch-harbor`

Der Umsetzungs- und Commit-Plan ist von dieser Produktspezifikation getrennt und liegt unter `planning/1.2.0/commit-plan.md`. Die abgeschlossenen Pläne für 1.0.0, 1.1.0 und 1.1.1 bleiben als historische Umsetzungsgrundlage erhalten. Änderungen am Produktziel werden in `spec/SPECIFICATION_CHANGELOG.md` dokumentiert.

---

## 1. Zweck, Gültigkeit und Verhältnis zu 1.1.1

Dieses Dokument beschreibt das vollständige verbindliche Produktziel von PatchHarbor 1.2.0.

Es übernimmt die Produktverträge des stabilen 1.1.1-Stands und ergänzt die
öffentliche synchrone Python-API. Haupt-CLI und Watcher verwenden dieselben
API-/Application-Pfade. Details stehen in Abschnitt 32 und
`planning/1.2.0/specification.md`. Die ausdrücklich beauftragte
Konfigurationsrevision ersetzt den bisherigen globalen Konfigurationsvertrag:

- alle Repository-Einstellungen ausschließlich in `.patchharbor/config.json`,
- eine globale Registry für lokale Identität und Pfad sowie globale technische
  Locks und Laufzeit-/Replay-Zustände, aber keine globale Einstellungsebene,
- pro Repository frei wählbare Exchange-Verzeichnisse; mehrere Repositorys dürfen
  denselben physischen Ordner als Übergabe für Patch-Pakete und Result Bundles nutzen,
- `patchharbor apply` ohne expliziten Dateipfad mit sicherer, nicht rekursiver und zustandsgebundener Paketauswahl,
- `patchharbor bundle` und automatische Apply-Result-Bundles mit dem Exchange-Ordner als Standardziel,
- eine gemeinsame Erkennungs- und Wiederverarbeitungsgrenze für Core und Watcher,
- die versionierte Datei `CHAT_INSTRUCTIONS.md` zur Initialisierung eines neuen Entwicklungs-Chats,
- eine verbindliche schmale Chat-Oberfläche für `PLAN`, `FIX`, `OFF-PLAN`, `WARNING`, `STOP` und fertige Patch-Pakete.

PatchHarbor 1.2.0 führt keine Netzwerk-, Chat-, Commit-Plan- oder Journalfunktion in den Core ein. `CHAT_INSTRUCTIONS.md` ist eine ausgelieferte Vorlage für passive Bundle-Begleitdokumentation und einen externen Chat; der Exchange-Ordner ist eine lokale Dateisystemgrenze.

Es gibt keinen Migrationscode für alte globale `config.json`, `watcher.json`,
`paths.json` oder frühere interne Pfaddokumente. Sie werden weder gelesen noch
übernommen. Die lokale Formatversion 1 ist ein neues geschlossenes Schema und
keine Fortsetzung des alten globalen Format-1/2/3-Lesers. Bestehende Registrierungen
werden manuell eingerichtet (Abschnitt 4.3). Keine automatische Reparatur und
kein stiller Fallback; Registry und technischer Replay-State bleiben erhalten.

Die historischen Commit-Pläne bleiben unter `planning/1.0.0/` und `planning/1.1.0/` erhalten, sind aber kein normativer Teil dieses Dokuments.

Bei einem Widerspruch zwischen diesem Dokument und einer älteren Produktspezifikation gilt dieses Dokument.

## 2. Produktzweck und Sicherheitsgrenze

PatchHarbor ist ein kontrollierter, plattformübergreifender Runner für von einem Chatbot erzeugte Skripte und ZIP-Patch-Pakete.

PatchHarbor unterstützt zwei öffentliche Ausführungswege:

1. den fortgeführten expliziten manuellen Runner `patchharbor fs run`,
2. den neuen sicheren Mehr-Repository-Pfad `patchharbor apply`.

Der sichere Mehr-Repository-Pfad ordnet ein Patch-Paket genau einer registrierten lokalen Repository-Instanz in genau einem erwarteten Zustand zu:

```text
Patch-Paket
    +
Repository-ID
    +
Base-Commit
    +
Zustands-Fingerprint
    =
genau eine lokale Repository-Instanz in genau einem erwarteten Zustand
```

PatchHarbor führt einen validierten Entrypoint aus, erfasst das Ergebnis und erzeugt einen vollständigen Snapshot des aktuellen Repository-Zustands ohne Git-Historie.

PatchHarbor ist kein Testmanager, kein Commit-Manager, kein Build-System, kein Chat-Transport und kein allgemeiner Workflow-Orchestrator.

### 2.1 PatchHarbor Core macht

- direkte Skripte und ZIP-Container kontrolliert verarbeiten,
- konkrete lokale Git-Repository-Instanzen registrieren,
- pro lokaler Instanz eine UUID v4 verwalten,
- Repository-Kontext und Zustands-Fingerprint bestimmen,
- sichere Patch-Pakete anhand einer verpflichtenden `patch.json` validieren,
- ein Patch-Paket eindeutig einem registrierten Ziel-Repository zuordnen,
- Base-Commit und Zustands-Fingerprint strikt prüfen,
- einen Dry-Run ohne Repository-Änderung durchführen,
- einen Entrypoint mit geprüfter Interpreterzuordnung ausführen,
- sichere reguläre ZIP-Nutzdateien bytegenau bereitstellen,
- Timeout, Abbruch und vollständigen Prozessbaum kontrollieren,
- stdout und stderr vollständig erfassen,
- Exit-Code, Laufzeit, Warnings und Tool-Fehler dokumentieren,
- ein vollständiges PatchHarbor Result Bundle erzeugen,
- repositorylokale Einstellungen aus `.patchharbor/config.json` identitätsgebunden lesen und sicher schreiben,
- den für das betroffene Repository konfigurierten Exchange-Ordner als Standardübergabe in beide Richtungen verwenden,
- bei manuellem parameterlosem `patchharbor apply` das aktuelle registrierte Repository bestimmen und ausschließlich dafür den neuesten zulässigen Kandidaten nach `mtime_ns` mit deterministischem Dateinamen-Tie-Breaker auswählen,
- Patch-Pakete, Result Bundles und sonstige Dateien im Exchange-Ordner sicher voneinander unterscheiden,
- einen maschinenlesbaren Ergebnisvertrag für Watcher, Repo Assist und einen späteren Orchestrator anbieten.

### 2.2 PatchHarbor Core macht ausdrücklich nicht

- keinen Ordner dauerhaft überwachen,
- keinen systemd-Dienst enthalten,
- keinen eigenen Managed- oder Standalone-Modus besitzen,
- keine Netzwerk- oder Chatverbindung betreiben,
- keine Dateien selbst zu einem Chat hochladen oder von ihm abrufen,
- keine Tests des Zielprojekts als fachlichen Workflow verwalten oder bewerten,
- keine Git-Commits, Branches, Tags oder Releases erzeugen,
- keinen Commit-Plan, kein Journal und keinen Entwicklungsfortschritt verwalten,
- keine Builds oder Linter als eigene Produktfunktion verwalten,
- keine Patches inhaltlich bewerten,
- keine interaktiven Kindskripte unterstützen,
- keine öffentliche Plugin-Schnittstelle anbieten,
- keine Clipboard- oder SSH-Quelle anbieten,
- keine Dateien aus kommentierten Skriptabschnitten erzeugen,
- keine textuelle Binärkodierung automatisch erkennen oder dekodieren,
- keine rekursive Ordnersuche durchführen,
- keine enthaltenen Archive rekursiv als weitere Patch-Pakete öffnen,
- keine vollständige Pakettransaktion oder automatische globale Rückabwicklung versprechen,
- keine dauerhafte zentrale Loghistorie oder Logrotation verwalten,
- keine beliebigen Diagnose-, Test- oder Build-Artefakte automatisch einsammeln,
- keine Dateien ohne vollständigen eigenen Entbehrlichkeitsnachweis archivieren oder beliebig sortieren und keine Bundles endgültig löschen.

Ein vertrauenswürdiger, vom Chat erzeugter Entrypoint darf im Auftrag des Benutzers Projekttests und Git-Kommandos ausführen. PatchHarbor Core behandelt deren Output und Exit-Code jedoch nur als Entrypoint-Ergebnis und übernimmt weder fachliche Testbewertung noch Commit-Verwaltung.

### 2.3 Keine Sandbox

PatchHarbor ist keine Sandbox. Ein ausgeführter Entrypoint besitzt grundsätzlich die Rechte des PatchHarbor-Benutzers. Repository-ID, Base-Commit und Fingerprint sichern Zuordnung und Zustand, authentifizieren aber nicht den Absender des Pakets. Nur vertrauenswürdige Patch-Pakete dürfen ausgeführt werden.

Die Pfadprüfung von ZIP-Nutzdateien schützt vor unbeabsichtigtem oder manipuliertem Entpacken außerhalb der erlaubten Ziele. Sie kann nicht verhindern, dass ein vertrauenswürdig gestartetes Skript mit den Rechten des Benutzers selbst beliebige erreichbare Dateien oder Programme verwendet.

---

## 3. Komponenten und Verantwortungsgrenzen

### 3.1 PatchHarbor Core

PatchHarbor Core ist ein normales CLI-Werkzeug und eine wiederverwendbare Runner-Engine. Jeder Aufruf verarbeitet genau einen klar abgegrenzten Auftrag und endet anschließend.

PatchHarbor Core besitzt keinen Hintergrundloop und keine Netzwerkverbindung.

### 3.2 PatchHarbor Watcher

Der PatchHarbor Watcher ist eine separate dünne Komponente im PatchHarbor-Projekt.

Er kann unter Linux als systemd-Service betrieben werden und:

- über Core die in den lokalen `.patchharbor/config.json` festgelegten Exchange-Verzeichnisse überwachen,
- vollständig abgeschlossene Downloads erkennen,
- offensichtliche temporäre Browserdateien ignorieren,
- stabile Dateien über die öffentliche PatchHarbor-Core-Grenze klassifizieren und anwenden lassen,
- Rückgabecode und strukturiertes Ergebnis protokollieren,
- die ungeplante erneute Verarbeitung derselben unveränderten Datei verhindern.

Der Watcher besitzt keine eigene Eingangsordner-Konfiguration. Startup prüft nur
die Registry über `api.repositories()`, nicht eine Konfiguration relativ zum
Service-Arbeitsverzeichnis. Jeder Poll ruft über einen privaten Worker
`api.apply_next()` auf; Core lädt die lokalen Konfigurationen frisch und scannt
jeden physisch eindeutigen Exchange-Ordner einmal. Paketklassifikation und
persistenter Dateidentitätsvertrag sind dieselben wie beim manuellen Apply.
Gültig registrierte Instanzen mit `exchange_directory: null` sowie fehlende
Repository-Pfade werden übersprungen. Eine fehlende oder ungültige Konfiguration
eines vorhandenen Repositorys, ein Identitätskonflikt oder ein nicht verfügbarer
konfigurierter Exchange führt zum Poll-Fehler vor Ausführung; keine Reparatur
und kein stilles Überspringen beschädigter Konfigurationen.

Der Watcher implementiert keine eigene Repository-, Git-, Manifest-, Fingerprint-, Lock-, Ausführungs- oder Result-Bundle-Logik. Er darf Prüfungen des Core weder nachbauen noch umgehen.

Der Watcher lässt die Exchange-Verzeichnisse ausschließlich flach scannen und implementiert keine eigene Archivierungslogik. Sein globaler Core-Scan darf nach Abschnitt 16.2.1 nachweislich überholte Bundles in den konfigurierten Archiv-Unterordner verschieben. Sonstige Dateien und unklare Zustände bleiben liegen; unveränderte Nichtkandidaten und bereits verarbeitete Dateien werden nicht fortlaufend neu delegiert.

### 3.3 Repo Assist

Repo Assist ist ein separates Werkzeug für den nachvollziehbaren Entwicklungsprozess eines Repositorys. Es ist nicht zwingend der oberste Orchestrator; über Repo Assist, PatchHarbor, PromptBridge und weitere Werkzeuge kann später ein zusätzlicher Orchestrator liegen.

Repo Assist kann insbesondere:

- Commit-Plan und Fortschritt verwalten,
- ein Entwicklungsjournal führen,
- Reproduzierbarkeit und Zuordnung von Aufgaben, Patches, Tests und Commits sichern,
- PatchHarbor Core aufrufen und PatchHarbor Result Bundles anfordern,
- Tests mit einer plattformgerechten Timeout-Strategie ausführen und Testresultate bewerten,
- nur bei erfolgreichem Workflow Commits erzeugen,
- Retry und Abort verwalten,
- eigene Repo-Assist-Journal-Bundles erzeugen,
- optional einen eigenen Automatikmodus anbieten.

Repo Assist erzeugt den technischen PatchHarbor-Repository-Snapshot nicht selbst. Benötigt Repo Assist den vollständigen Repository-Zustand, ruft es PatchHarbor auf.

PatchHarbor ruft Repo Assist nicht auf. Ein Patch darf Repo Assist nicht als versteckten inneren Workflow starten.

### 3.4 PromptBridge

PromptBridge besitzt die Chat- und Transportverantwortung.

Dazu können gehören:

- Chat-Interaktion,
- Netzwerktransport,
- Upload und Download,
- Übertragung von Nachrichten, Variablen und Dateien,
- spätere Automatisierung des Austauschs zwischen Chat und lokaler Umgebung.

PromptBridge ist kein internes PatchHarbor-Modul.

### 3.5 Keine konkurrierenden Automatikpfade

Für dieselben registrierten Repository-Instanzen gilt:

- Der PatchHarbor Watcher darf neue Exchange-Dateien autonom über PatchHarbor Core verarbeiten.
- Ein Repo-Assist-Automatikmodus oder ein späterer übergeordneter Orchestrator darf denselben Workflow alternativ steuern.
- Zwei autonome Auslöser dürfen nicht gleichzeitig dieselben Repository-Instanzen bearbeiten.

Manuelle Core-Aufrufe bleiben möglich. Die exklusive Repository-Sperre verhindert parallele PatchHarbor-Aufträge auf derselben lokalen Instanz, ersetzt aber keine fachliche Koordination mehrerer Automatiksysteme.

## 4. Installation, Plattformen und lokale Verzeichnisse

### 4.1 Installation

PatchHarbor wird für den Benutzer über pipx installiert:

```bash
pipx install patchharbor
```

Wheel und Source-Distribution werden aus derselben Version und denselben Release-Metadaten gebaut.

Der Konsolenbefehl lautet:

```bash
patchharbor
```

`patchharbor --version` zeigt die installierte Release-Version.

### 4.2 Python und Zielplattformen

PatchHarbor 1.1.1 verwendet die vollständig implementierte 1.1.0-Basis und benötigt Python 3.12 oder neuer.

Verbindliche Zielplattformen:

- Linux,
- Windows 11.

Verbindliche CI-Plattformen:

- Ubuntu 24.04,
- Ubuntu 26.04,
- ein echter GitHub-gehosteter Windows-Runner mit Windows PowerShell,
- zusätzlich PowerShell 7, soweit auf dem Runner vorhanden.

Ubuntu 24.04, Ubuntu 26.04 und der echte Windows-Runner sind normale blockierende Release-Gates. Eine Release-Freigabe ist nur zulässig, wenn alle verbindlichen Lanes grün sind. PowerShell 7 ist zusätzlich blockierend, sobald die entsprechende Lane im Release-Workflow aktiviert ist.

### 4.3 Repositorylokale Konfiguration und globale technische Zustände

Jede registrierte lokale Repository-Instanz besitzt ausschließlich:

```text
<Repository>/.patchharbor/id
<Repository>/.patchharbor/config.json
```

Alle Repository-Einstellungen liegen in dieser lokalen `config.json`, nicht im
Exchange-Verzeichnis und nicht in einem Benutzer-Config-Fallback. Die Bindung
entsteht durch Repository-Wurzel, lokale ID, lokale Git-Ausnahme und globale
Registry. Keine zusätzliche `repo_id` und kein Repository-Pfad im Config-Dokument.
Das vollständige `.patchharbor/` wird lokal über den von Git ermittelten
`info/exclude` ausgeblendet; die versionierte `.gitignore` bleibt unverändert.
Das Punktpräfix ist unter Linux versteckt; unter Windows wird kein Hidden-Attribut
gesetzt. Beide Dateien und das lokale Verzeichnis müssen regulär sein, keine
Symlinks/Junctions oder Sonderdateien.

#### 4.3.1 Geschlossenes lokales Format 1

Nur eine echte Erstregistrierung erzeugt diese Grundkonfiguration:

```json
{
  "format_version": 1,
  "exchange_directory": null,
  "bundle_suffix": "",
  "archive_directory": "PatchHarbor-Archive"
}
```

Verbindliche Regeln:

- exakt die vier genannten Felder; keine fehlenden, unbekannten oder doppelten
  Schlüssel, kein BOM, keine nachgestellten Daten und keine nichtendlichen Zahlen;
- `format_version` ist die Ganzzahl `1`, kein Boolean; andere Versionen werden
  abgelehnt, auch alle alten globalen Formate;
- `exchange_directory` ist `null` oder ein nichtleerer absoluter Pfadstring ohne
  NUL; `null` bedeutet korrekt registriert, aber noch nicht konfiguriert;
- `bundle_suffix` ist ein String, `""` deaktiviert das Suffix; ein gesetztes Suffix
  besteht aus höchstens 32 ASCII-Buchstaben, Ziffern, Punkten, Unterstrichen oder
  Bindestrichen und enthält mindestens einen Buchstaben oder eine Ziffer;
  `..`, abschließender Punkt, Pfade, Leerraum und Steuerzeichen sind unzulässig;
- `.crdownload`, `.download`, `.opdownload`, `.part`, `.partial` und `.tmp` sind
  als Suffix-Endungen case-insensitiv verboten;
- `archive_directory` ist ein portabler einzelner Ordnername direkt unter dem
  Exchange, Standard `PatchHarbor-Archive`; `""` deaktiviert nur die Archivierung
  dieses Repositorys. Keine absoluten Pfade, Trennzeichen, Traversal, Leerraum,
  abschließenden Punkte oder reservierten Windows-Gerätenamen; zulässig sind
  1–128 ASCII-Buchstaben, Ziffern, Punkte, Unterstriche und Bindestriche. Ein
  führender Punkt ist erlaubt;
- UTF-8 ohne BOM; Schreiber erzeugen abschließendes LF und ersetzen atomar im
  lokalen Verzeichnis. Direkte manuelle Bearbeitung ist erlaubt, ungültige
  Dokumente führen ohne Mutation zu einem Konfigurationsfehler.

Fehlende Konfiguration ist **nicht** gleich gültige Konfiguration mit `null`.
Keine lesende Operation, kein Setter und keine erneute Registrierung darf eine
fehlende oder beschädigte Konfiguration automatisch erzeugen/reparieren.
Nur eine Erstanmeldung ohne bestehende ID oder Registry-Bindung initialisiert
Defaults innerhalb ihrer Registrierungstransaktion.

#### 4.3.2 Auswahl, Setter und Verwendung

Normaler Einrichtungsablauf:

```bash
cd /pfad/zum/repository
patchharbor register
patchharbor configure exchange-directory VERZEICHNIS
patchharbor configure bundle-suffix .txt
patchharbor configure bundle-suffix --clear
patchharbor configure archive-dir PatchHarbor-Archive
patchharbor configure archive-dir --clear
patchharbor configure show
```

`VERZEICHNIS` muss absolut sein. Jeder `configure`-Aufruf ermittelt aus seinem
aktuellen Arbeitsverzeichnis einschließlich Unterverzeichnissen die Git-Wurzel
und prüft eine eindeutige Registrierung sowie gültige lokale Metadaten. Außerhalb
eines Git-Repositorys oder ohne passende Registrierung wird abgebrochen, bevor
ein Verzeichnis oder eine Config angelegt wird. Die Python-API kann das Repository
explizit wählen (Abschnitt 32); eine CLI-Option für globale Einstellungen gibt es
nicht.

Setter halten zuerst den globalen Registry-Lock und danach den Repository-Lock.
Sie validieren Identität, bisherige Konfiguration, Registry und Verzeichnis vor
der atomaren Veröffentlichung erneut und erhalten die jeweils anderen Werte.
`configure exchange-directory` erzeugt bei Bedarf den ausdrücklich gewählten
Ordner und persistiert dessen physisch kanonischen absoluten Pfad. Ein nicht mehr
verfügbarer alter Exchange kann ausdrücklich ersetzt werden; eine beschädigte
JSON-Datei wird dadurch nicht repariert. Suffix/Archiv können schon bei `null`
konfiguriert werden. Ist ein Exchange gesetzt, muss er bei diesen Settern weiter
verfügbar und pfadpolitisch zulässig sein. Fehlendes Argument oder Argument plus
`--clear` sind CLI-Fehler.

`configure show` und normales `api.configuration()` prüfen Identität und Schema,
zeigen aber auch `null` oder einen derzeit nicht verfügbaren gespeicherten Pfad.
Sie erzeugen keine Verzeichnisse. `api.configuration(..., revalidate=True)`
fordert zusätzlich einen verfügbaren physischen Exchange und dessen Trennung
von registrierten Repositorys. Jede tatsächliche Verwendung prüft den Pfad erneut.

`context` benötigt gültige lokale Konfiguration, aber keinen gesetzten Exchange.
`registry list`, `unregister` und der unabhängige `fs run` benötigen keinen Exchange.
Default-`bundle`, parameterloses Apply und Default-Result-Publikation benötigen
hingegen einen verfügbaren Exchange des Zielrepositorys. Ein explizites
`PATCH_ZIP` bestimmt das Repository ausschließlich per Manifest-ID. Ein explizites
`--output-dir` übersteuert nur das Ausgabeziel: Es erlaubt einen nicht gesetzten
oder nicht verfügbaren Exchange, niemals fehlende oder ungültige lokale Config.
Der lokale Suffix bleibt wirksam; Identität, Exchange-Wert und Suffix werden vor
Result-Veröffentlichung revalidiert.

Das Suffix wird bei neuen Bundles des betreffenden Repositorys unverändert direkt
hinter `.zip` angehängt. Es benennt keine Bestandsdatei um und ändert weder
ZIP-Inhalt noch `patch.json`, Fingerprint oder Replay. Kein Suffix-Schalter auf
`apply`/`bundle`. Bundle-Begleitdaten beschreiben das konkrete Zielrepository.

Mehrere Repositorys dürfen denselben physischen Exchange verwenden; separate
Ordner sind ebenso zulässig. Es gibt keine Eindeutigkeitsanforderung an diesen
Pfad. Eigene Suffix-/Archivwerte bleiben unabhängig, auch im gemeinsamen Ordner.
Für jeden Exchange gilt weiterhin: weder identisch mit noch innerhalb noch
oberhalb irgendeiner registrierten Repository-Wurzel. Neu konfigurierte Pfade
und spätere Registrierungen werden gegen diese Grenzen geprüft. Symlinks,
Junctions und Elternpfade werden zum tatsächlichen Ziel aufgelöst. Patch-Pakete,
Result Bundles und sonstige Dateien dürfen in derselben flachen Übergabe liegen.

Ein expliziter `--output-dir` darf weder identisch mit noch innerhalb einer
registrierten Repository-Wurzel liegen. Er darf dem Exchange entsprechen oder
außerhalb davon liegen. Vor der ersten Repository-Änderung wird er sicher
angelegt und auf Schreibbarkeit geprüft; temporäre Result-ZIPs entstehen direkt
im endgültigen Ausgabeordner für dateisystemgleiche atomare Veröffentlichung.

#### 4.3.3 Globale Registry, Locks und Replay bleiben erhalten

Unter Linux gelten standardmäßig:

```text
Registry:            ${XDG_CONFIG_HOME:-$HOME/.config}/patchharbor/registry.json
Zustand:             ${XDG_STATE_HOME:-$HOME/.local/state}/patchharbor/
Exchange-Dateistatus:${XDG_STATE_HOME:-$HOME/.local/state}/patchharbor/exchange/
Locks:               ${XDG_STATE_HOME:-$HOME/.local/state}/patchharbor/locks/
```

Unter Windows gelten standardmäßig:

```text
Registry:            %APPDATA%\PatchHarbor\registry.json
Zustand:             %LOCALAPPDATA%\PatchHarbor\
Exchange-Dateistatus: %LOCALAPPDATA%\PatchHarbor\exchange\
Locks:               %LOCALAPPDATA%\PatchHarbor\locks\
```

Die Registry verwaltet Identität und lokalen Pfad, keine Exchange-/Suffix-/
Archiveinstellungen. Der gemeinsame Exchange-State verwaltet technische
Dateiidentitäten und Replay-Belege über alle Ordner hinweg; er ist weder
Konfiguration, Archiv, Journal noch Download-Sortierung. Bestehende Format-4-
Replay-Verträge und lesbare alte Replay-Belege bleiben von der neuen lokalen
Config-Formatversion unberührt. Keine Config-Reparatur bedeutet nicht, dass die
bestehende beweisgebundene Attempt-Recovery aus 16.4.1 entfernt wird.

#### 4.3.4 Bewusster manueller Versionswechsel

Die alte globale `config.json` wird vollständig ignoriert, weder importiert,
gelöscht noch verändert. Kein automatischer oder optionaler Migrationspfad,
keine Übernahme alter Formatschemata, kein Lesen als Fallback. Dasselbe gilt für
`watcher.json` und `paths.json`.

Bestehende Registrierungen ohne lokale Konfiguration benötigen eine bewusste
manuelle Anlage des vollständigen Dokuments aus 4.3.1. Anschließend wird im
jeweiligen Repository `configure exchange-directory` ausgeführt; Suffix und
Archivpräferenz werden ausdrücklich gewählt. Die bisherige ID, Registry, lokale
Git-Ausnahme und Replay-Belege bleiben erhalten. Bereits gültige lokale Dateien
werden nicht überschrieben. `register --new-id` ist keine Reparaturfunktion.
Vor Installation/Handänderung aktive Applies abschließen und Watcher stoppen;
CLI und Watcher gemeinsam auf denselben Stand bringen. Der README beschreibt
diesen einmaligen Handablauf, keinen vom Programm ausgeführten Migrationscode.

### 4.4 Dokumentation und Chat-Initialisierung

- Die Installations- und Betriebsanleitung steht kurz und handlungsorientiert im README.
- Das README beschreibt neues und bestehendes Repository, neuen Chat, manuellen Modus und Watcher-Modus vollständig.
- Die vollständige CLI-Bedienung steht in den argparse-Help-Screens.
- Die Produktspezifikation beschreibt verbindliches Verhalten und die Verantwortungsgrenzen.
- Die versionierte Root-Datei `CHAT_INSTRUCTIONS.md` beschreibt den vollständigen Vertrag für einen externen Entwicklungs-Chat.
- Ein neuer Chat erhält die frisch generierten `CHAT_INSTRUCTIONS.md` und `environment.json` im aktuellen Result Bundle. Lokale Pfade dienen nur passenden Zielrechner-Beispielen, nie der Bindung; maßgeblich bleibt `context.json`.
- Nicht implementierte Funktionen werden weder im README noch im Help-Screen oder in `CHAT_INSTRUCTIONS.md` als verfügbar dargestellt.

Die standardisierten Chat-Statuszeilen aus `CHAT_INSTRUCTIONS.md` sind eine bewusst maschinenlesbare UI-Grenze und dürfen im Unterschied zu sonstigen Human-Texten exakt getestet werden.

## 5. Öffentliche CLI

### 5.1 Sicherer Mehr-Repository-Pfad und lokale Konfiguration

```bash
patchharbor configure exchange-directory VERZEICHNIS
patchharbor configure show
patchharbor register [REPOSITORY]
patchharbor register --new-id [REPOSITORY]
patchharbor registry list
patchharbor unregister [REPOSITORY_OR_REPO_ID]
patchharbor context [REPOSITORY]
patchharbor bundle [REPOSITORY]
patchharbor apply [PATCH_ZIP]
patchharbor apply --dry-run [PATCH_ZIP]
```

Die Optionen sind pro Befehl verbindlich begrenzt:

| Befehl | Unterstützte zusätzliche Optionen |
|---|---|
| `patchharbor configure exchange-directory` | keine fachliche Zusatzoption |
| `patchharbor configure show` | keine fachliche Zusatzoption |
| `patchharbor configure bundle-suffix` | `--clear` statt Suffix |
| `patchharbor configure archive-dir` | `--clear` statt Name |
| `patchharbor register` | `--new-id` |
| `patchharbor registry list` | `--json` |
| `patchharbor unregister` | keine fachliche Zusatzoption |
| `patchharbor context` | `--json` |
| `patchharbor bundle` | `--json`, `--output-dir VERZEICHNIS` |
| `patchharbor apply` | `--dry-run`, `--timeout SEKUNDEN`, `--plain`, `--no-color`, `--json`, `--output-dir VERZEICHNIS` |

Für `patchharbor apply` beträgt der Standard-Timeout 10.800 Sekunden (drei Stunden).

Ist `PATCH_ZIP` angegeben, wird ausschließlich diese Datei verarbeitet. Das Paket bestimmt über seine vollständige `repo_id` das registrierte Ziel-Repository; das aktuelle Arbeitsverzeichnis schränkt diesen expliziten Auftrag nicht ein. Ist `PATCH_ZIP` nicht angegeben, löst ein manueller Aufruf zuerst das aktuelle Arbeitsverzeichnis einschließlich Unterverzeichnissen zu genau einer registrierten Repository-Instanz auf. Danach betrachtet PatchHarbor im konfigurierten Exchange-Ordner ausschließlich Pakete für diese `repo_id`, filtert vollständige State-Bindung und Replay-Eignung und wählt nach Abschnitt 16.2 den höchsten `mtime_ns` mit deterministischem Dateinamen-Tie-Breaker. Ist das aktuelle Repository nicht eindeutig registriert, gibt es keinen repositoryübergreifenden Fallback. Ein bewusster manueller Aufruf darf einen weiterhin exakt gebundenen fehlgeschlagenen Patch erneut versuchen. Der Watcher verwendet einen internen automatischen Ursprung, bleibt repositoryübergreifend und wiederholt fehlgeschlagene Identitäten nicht. Ein öffentlicher Schalter `--retry-failed` ist nicht erforderlich.

Ohne `--output-dir` veröffentlicht `bundle` sein Result Bundle im Exchange-Ordner. Dasselbe gilt für den Result-Bundle-Versuch von `apply`. Ein explizites `--output-dir` überschreibt nur das Ausgabeziel, nicht die Paketauswahl.

Der separate Watcher besitzt ab 1.1.1 keinen eigenen Eingangsordnerparameter und keine eigene `--configure`-Option. Seine öffentlichen Betriebsaufrufe lauten:

```bash
patchharbor-watcher
patchharbor-watcher --install-systemd-user-unit
patchharbor-watcher --poll-interval SEKUNDEN
```

Er bezieht die Exchange-Verzeichnisse über Core ausschließlich aus den lokalen
`.patchharbor/config.json` der registrierten Repositorys; kein globales Config-Lesen.

`--json` und eine interaktive Terminaldarstellung schließen sich aus. Im JSON-Modus werden weder TUI-Sequenzen noch Farbcodes auf stdout ausgegeben. Nicht für einen Befehl aufgeführte Optionen werden von argparse abgelehnt.

Alle Befehle unterstützen die üblichen argparse-Hilfen wie `--help`.

### 5.2 Gemeinsamer JSON-Ausgabevertrag

Die Befehle `registry list --json`, `context --json`, `bundle --json` und `apply --json` verwenden einen gemeinsamen versionierten Abschlussvertrag.

Nach erfolgreicher CLI-Argumentanalyse gilt:

- stdout enthält genau ein UTF-8-JSON-Objekt und einen abschließenden LF-Zeilenumbruch,
- stdout enthält weder TUI-Sequenzen noch Farbcodes noch rohen Kindprozessoutput,
- menschliche Zusatz- oder Notfallmeldungen erscheinen ausschließlich auf stderr,
- alle UUIDs werden in kanonischer kleingeschriebener Schreibweise ausgegeben,
- alle Objekt-IDs und Fingerprints werden kleingeschrieben ausgegeben,
- Zeitstempel sind UTC-Zeitstempel nach RFC 3339 mit `Z`,
- Pfade sind physisch kanonisierte absolute Pfadstrings,
- nicht endliche Zahlenwerte kommen nicht vor,
- JSON-Ausgabeformat 1 enthält nur die nachfolgend festgelegten Felder; Erweiterungen erfordern eine höhere `output_version`.

Jedes Abschlussobjekt besitzt exakt diese Top-Level-Felder:

| Feld | Typ | Bedeutung |
|---|---|---|
| `output_version` | Integer | Exakt `1`. |
| `command` | String | `registry.list`, `context`, `bundle` oder `apply`. |
| `success` | Boolean | `true` genau dann, wenn der Prozess-Exit-Code `0` ist. |
| `result` | Objekt oder `null` | Befehlsspezifisches Ergebnis, soweit vorhanden. |
| `error` | Objekt oder `null` | Strukturierter PatchHarbor-Tool-Fehler, soweit vorhanden. |
| `process_exit_code` | Integer | Tatsächlich zurückgegebener Prozess-Exit-Code. |

Ein nicht-null `error`-Objekt besitzt exakt:

| Feld | Typ | Bedeutung |
|---|---|---|
| `kind` | String | Stabile Fehlerkategorie aus dem jeweiligen Befehl. |
| `message` | String | Menschenlesbare, nicht geheime Kurzbeschreibung. |
| `patchharbor_error_code` | Integer | Zugehöriger PatchHarbor-Tool-Exit-Code. |
| `emergency_diagnostics_path` | String oder `null` | Physisch kanonischer Notfallpfad, falls vorhanden. |

Ein normal beendeter Entrypoint mit einem von null verschiedenen Exit-Code ist kein PatchHarbor-Tool-Fehler. In diesem Fall ist `success` gleich `false`, `error` bleibt `null`, und das Resultat beschreibt den Entrypoint-Exit eindeutig.

#### `patchharbor registry list --json`

Das `result`-Objekt besitzt exakt ein Feld `repositories`. Die Einträge sind nach den ASCII-Bytes der `repo_id` sortiert und besitzen exakt `repo_id`, `repository_path` und `status`. Zulässige Statuswerte sind `ok`, `missing` und `conflict`.

```json
{
  "output_version": 1,
  "command": "registry.list",
  "success": true,
  "result": {
    "repositories": [
      {
        "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
        "repository_path": "/home/user/src/patchharbor",
        "status": "ok"
      }
    ]
  },
  "error": null,
  "process_exit_code": 0
}
```

#### `patchharbor context --json`

Das erfolgreiche `result`-Objekt besitzt exakt:

- `repo_id`,
- `repository_path`,
- `base_commit`,
- `dirty`,
- `state_fingerprint`,
- `fingerprint_algorithm`.

```json
{
  "output_version": 1,
  "command": "context",
  "success": true,
  "result": {
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "repository_path": "/home/user/src/patchharbor",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "dirty": true,
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": "patchharbor-state-v1"
  },
  "error": null,
  "process_exit_code": 0
}
```

#### `patchharbor bundle --json`

Das erfolgreiche `result`-Objekt besitzt exakt:

- `run_id`,
- `repo_id`,
- `repository_path`,
- `base_commit`,
- `state_fingerprint`,
- `fingerprint_algorithm`,
- `result_bundle_status`,
- `result_bundle_path`,
- `emergency_diagnostics_path`.

`result_bundle_status` ist bei einem erfolgreichen manuellen Bundle exakt `created`; `emergency_diagnostics_path` ist dann `null`.

```json
{
  "output_version": 1,
  "command": "bundle",
  "success": true,
  "result": {
    "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "repository_path": "/home/user/src/patchharbor",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": "patchharbor-state-v1",
    "result_bundle_status": "created",
    "result_bundle_path": "/home/user/Downloads/patchharbor_Result_093000_0825_b592be.zip",
    "emergency_diagnostics_path": null
  },
  "error": null,
  "process_exit_code": 0
}
```

#### `patchharbor apply --json`

Das erfolgreiche oder fachlich fehlgeschlagene `result`-Objekt besitzt exakt:

- `run_id`,
- `repository_resolved`,
- `repo_id`,
- `repository_path`,
- `primary_result`,
- `result_bundle`.

`repo_id` und `repository_path` sind `null`, solange kein Repository sicher aufgelöst wurde.

`primary_result` besitzt exakt:

- `kind`,
- `entrypoint_started`,
- `entrypoint_exit_code`,
- `timed_out`,
- `interrupted`,
- `patchharbor_error_code`.

`result_bundle` besitzt exakt:

- `attempted`,
- `status`,
- `path`,
- `emergency_diagnostics_path`.

Zulässige Bundle-Statuswerte sind `created`, `failed` und `not_attempted`. `not_attempted` ist nur zulässig, wenn `repository_resolved` gleich `false` ist.

```json
{
  "output_version": 1,
  "command": "apply",
  "success": false,
  "result": {
    "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
    "repository_resolved": true,
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "repository_path": "/home/user/src/patchharbor",
    "primary_result": {
      "kind": "entrypoint_exit",
      "entrypoint_started": true,
      "entrypoint_exit_code": 7,
      "timed_out": false,
      "interrupted": false,
      "patchharbor_error_code": null
    },
    "result_bundle": {
      "attempted": true,
      "status": "created",
      "path": "/home/user/Downloads/patchharbor_Result_093000_0825_b592be.zip",
      "emergency_diagnostics_path": null
    }
  },
  "error": null,
  "process_exit_code": 7
}
```

### 5.3 Fortgeführter manueller Runner

Der vorhandene öffentliche Hauptaufruf bleibt:

```bash
patchharbor fs run [PFAD]
```

Unterstützte Optionen:

- `--timeout SEKUNDEN` mit Standardwert 10.800 (drei Stunden),
- `--log` für eine vollständige temporäre Logdatei,
- `--plain` für einfache fortlaufende Textausgabe,
- `--no-color`,
- die üblichen argparse-Hilfen.

`patchharbor fs run` ist ein expliziter lokaler Runner. Er besitzt keine automatische Repository-Zuordnung und prüft weder Repository-ID noch Base-Commit oder Fingerprint.

## 6. Gemeinsamer Runner-Lebenszyklus

Ein Runner-Auftrag verarbeitet genau ein Eingabeartefakt oder ein sicheres Patch-Paket und endet anschließend.

Der allgemeine Lebenszyklus lautet:

```text
Start
→ Eingabe übernehmen
→ vollständige Struktur und Ressourcen prüfen
→ ausführbare Einträge vorbereiten und Pflichtmarker prüfen
→ angeforderte Interpreter bestimmen und ihre Verfügbarkeit prüfen
→ Nutzdateien vollständig vorbereiten und sicher schreiben
→ Kindprozess nicht interaktiv ausführen
→ Output und Ergebnis erfassen
→ gegebenenfalls Result Bundle erzeugen
→ temporäre Ressourcen über einen gemeinsamen Cleanup-Pfad entfernen
→ Auftrag beenden
```

Beim sicheren Apply werden sämtliche rein lesenden Prüfungen einschließlich Entrypoint-, Marker-, Interpreter- und Result-Zielprüfung vor der ersten Änderung einer Repository-Datei abgeschlossen.

Kein Skript startet, bevor das zugehörige Eingabepaket vollständig validiert wurde und alle vorab bereitzustellenden Nutzdateien erfolgreich geschrieben wurden.

### 6.1 Arbeitsverzeichnis

Beim manuellen Runner läuft jedes Skript im ursprünglichen aktuellen Arbeitsverzeichnis des Aufrufs.

Beim sicheren Apply läuft der Entrypoint im Wurzelverzeichnis des anhand der Repository-ID aufgelösten Ziel-Repositorys.

Der Speicherort der Eingabedatei, des ZIP-Pakets oder der temporären Entrypoint-Datei ändert das Arbeitsverzeichnis nicht.

Relative Pfade im Skript beziehen sich immer auf dieses Arbeitsverzeichnis.

### 6.2 Temporäre Eingabe- und Skriptdateien

Direkte Skriptinhalte, aus STDIN erzeugte Eingabeartefakte und ausführbare ZIP-Einträge werden bei Bedarf in einem privaten System-Temp-Verzeichnis bereitgestellt.

Eine temporäre Datei:

- wird nicht als Nutzdatei in das Zielverzeichnis kopiert,
- erhält nur die für ihren Zweck notwendigen Benutzerrechte,
- wird nach Erfolg, Fehler, Timeout oder Strg+C über genau einen gemeinsamen Cleanup-Pfad entfernt,
- darf vom Skript nicht als dauerhaft im Projekt vorhandene Datei vorausgesetzt werden.

Nur wenn die in Abschnitt 18 definierte Notfallrettung benötigt wird, dürfen `execution.log` und `run.json` nach einem Bundle-Fehler im ausdrücklich gemeldeten Notfallverzeichnis verbleiben.

## 7. Manueller Runner: Quellen und Eingabeartefakte

### 7.1 Quellengrenze

Eine Quelle ist ausschließlich dafür verantwortlich, Daten zu empfangen und als neutrales `InputArtifact` bereitzustellen.

Ein `InputArtifact` enthält nur:

- einen sicher lesbaren lokalen Pfad,
- einen Anzeigenamen für Status und Fehler.

Die Quelle interpretiert den Inhalt nicht. Sie kennt weder Skriptmarker noch ZIP-Regeln, Nutzdateien, Interpreter oder Execution.

### 7.2 Einzelne Datei

Eine einzelne reguläre Datei wird als Eingabeartefakt übernommen.

Dateiname und Dateiendung sind für die Skript- und ZIP-Erkennung unerheblich.

Symbolische Links werden als direkte Eingabe nicht stillschweigend dereferenziert. Kann eine Datei nicht sicher als reguläre Datei geöffnet werden, endet der Auftrag mit einem Tool-Fehler.

### 7.3 Einmaliger Ordnerscan

Ein an `patchharbor fs run` übergebener Ordner wird genau einmal gescannt. Er wird nicht überwacht.

Regeln:

- nicht rekursiv,
- nur reguläre Dateien,
- symbolische Links werden ignoriert,
- ein Kandidat ist eine Datei, deren Auflösung mindestens ein gültiges PatchHarbor-Skript liefert,
- Sortierung nach Änderungszeit, neueste zuerst,
- bei gleicher Änderungszeit Dateiname als stabiler zweiter Sortierschlüssel,
- Auswahl mit einer ab eins gezählten Zahl aus ASCII-Ziffern,
- bei genau einem Kandidaten automatische Auswahl,
- bei mehreren Kandidaten muss der Benutzer genau einen Eintrag wählen,
- leere Eingabe bricht ohne automatische Auswahl ab,
- ungültige Eingabe wird erneut abgefragt, solange die Eingabe interaktiv möglich ist.

### 7.4 STDIN und Pipe

Ist kein Pfad angegeben und STDIN eine Pipe, wird der vollständige Byte-Strom einmalig und unter Einhaltung des Eingabebudgets in ein sicheres temporäres Eingabeartefakt geschrieben.

STDIN kann übertragen:

- ein direktes UTF-8-Skript,
- ein binäres ZIP-PatchBundle.

Es gibt keinen Streaming-Befehlsdialog und kein interaktives Protokoll.

Ist kein Pfad angegeben und STDIN ein normales Terminal, endet PatchHarbor mit einem klaren Usage-Fehler wegen fehlender Eingabe.

Das aus STDIN erzeugte temporäre Eingabeartefakt unterliegt demselben zentralen Cleanup-Vertrag wie temporäre Skriptdateien und wird bei Erfolg, Fehler, Timeout und Strg+C entfernt.

Die Standardeingabe des ausgeführten Kindprozesses ist geschlossen.

## 8. Skripterkennung, Metadaten und Messages

### 8.1 Pflichtmarker

Ein Skript ist nur gültig, wenn es mindestens eine vollständige Zeile enthält, die exakt lautet:

```text
# PATCHHARBOR
```

Regeln:

- Die Zeile beginnt am ersten Zeichen der Zeile.
- Es gibt keine führenden Leerzeichen.
- Groß- und Kleinschreibung sind fest.
- Die Zeile enthält keinen Zusatz und keine Version.
- Eine META- oder MESSAGE-Zeile ersetzt den Pflichtmarker nicht.
- Zeilenenden von Linux und Windows werden beim Prüfen normalisiert.

Fehlt der Pflichtmarker, wird das Skript nicht ausgeführt.

### 8.2 Optionale Metadaten

Kleine Informationen können als optionale META-Zeilen übertragen werden:

```text
# PATCHHARBOR META name=wert
```

Metadaten sind rein informativ. Sie verändern weder Timeout noch Interpreter, Umgebungsvariablen, Repository-Zuordnung, Fingerprint oder anderes Ausführungsverhalten.

Fehlerhafte META-Zeilen führen höchstens zu einer Warning und werden ansonsten ignoriert.

### 8.3 Optionale Messages

Es dürfen mehrere benannte Message-Blöcke enthalten sein.

Ein Message-Name besteht aus Großbuchstaben, Kleinbuchstaben, Zahlen und Punkten und enthält keine Leerzeichen.

Anfang und Ende eines Blocks enthalten denselben Namen. Der Text dazwischen besteht aus kommentierten UTF-8-Zeilen. Beim Lesen wird das definierte Kommentarpräfix entfernt.

Messages sind ausschließlich Informationen für Menschen oder äußere Orchestratoren. Sie steuern PatchHarbor nicht.

Ein unvollständiger, falsch benannter oder beschädigter Message-Block wird vollständig verworfen. PatchHarbor zeigt eine Warning und führt ein ansonsten gültiges Skript trotzdem aus.

---

## 9. Manueller Runner: PatchBundle-Auflösung

### 9.1 Begriff

Jedes Eingabeartefakt des manuellen Runners wird genau einmal zu einem `PatchBundle` aufgelöst.

Ein PatchBundle enthält:

- mindestens ein PatchHarbor-Skript in definierter Reihenfolge,
- null oder mehr geordnete reguläre Nutzdateien mit relativem Zielpfad und bytegenauem Inhalt.

Ein einzelnes direktes Skript ist fachlich ein PatchBundle mit genau einem Skript und ohne Nutzdateien.

### 9.2 Auflösungsreihenfolge

- Ein vollständig als UTF-8 lesbares direktes Skript mit exaktem Pflichtmarker ergibt ein PatchBundle mit genau einem Skript.
- Ist das Artefakt kein gültiges direktes Skript, wird es als ZIP-basiertes PatchBundle geprüft.
- Ist es weder ein gültiges direktes Skript noch ein gültiges ZIP-Bundle mit mindestens einem PatchHarbor-Skript, endet der Auftrag mit einem klaren Tool-Fehler.
- Quelle, Dateiname und Dateiendung bestimmen weder Skripttyp noch Bundletyp.

### 9.3 ZIP-PatchBundle

ZIP ist die Codierung für mehrere geordnete Skripte und zusätzliche Text- oder Binärdateien. Es ist kein eigener Ausführungsmodus.

Regeln:

- Das Archiv wird vor der ersten Dateischreibung vollständig auf Struktur, Eintragstypen, Zielpfade, Duplikate, Lesbarkeit und Ressourcenbudgets geprüft.
- Verzeichniseinträge beschreiben nur die sichere relative Zielstruktur.
- Symbolische Links, Hardlinks und andere besondere oder mehrdeutige Einträge machen das gesamte Bundle ungültig.
- Jeder reguläre Dateieintrag wird in Archiv-Reihenfolge klassifiziert.
- Ist ein Eintrag vollständig als UTF-8 lesbar und enthält er den exakten Pflichtmarker, ist er ein ausführbares PatchHarbor-Skript.
- Jeder andere sichere reguläre Eintrag ist eine Nutzdatei und wird bytegenau übertragen. Das gilt auch für markerlose Shell- oder PowerShell-Dateien.
- Binärdateien werden niemals als Text verändert und niemals automatisch ausgeführt.
- Ein enthaltenes Archiv ohne PatchHarbor-Marker wird nicht rekursiv geöffnet, sondern wie jede andere Binärdatei als Nutzdatei behandelt.
- Skripteinträge werden in der im Archiv gespeicherten Reihenfolge ausgeführt.
- Alle Nutzdateien werden vollständig vorbereitet und vor dem ersten Skript bereitgestellt.
- Jedes Skript erhält sein eigenes Timeout.
- Beim ersten nicht erfolgreichen Skript wird abgebrochen.
- Der Exit-Code des zuletzt ausgeführten Skripts wird zurückgegeben.
- Enthält das Archiv kein gültiges PatchHarbor-Skript, endet PatchHarbor mit einem Tool-Fehler.
- Das Archiv wird möglichst streamend verarbeitet und nicht pauschal vollständig in das Arbeitsverzeichnis entpackt.

---

## 10. Sichere ZIP-Nutzdateien

Die Regeln dieses Abschnitts gelten sowohl für den manuellen ZIP-PatchBundle-Pfad als auch für sichere `patchharbor apply`-Pakete.

### 10.1 Erlaubte relative Pfade

Für jeden Nutzdateipfad gelten:

- ausschließlich relative Pfade mit dem ZIP-Trennzeichen `/`,
- keine absoluten Pfade,
- keine Laufwerks- oder UNC-Angaben,
- keine Backslashes,
- kein leeres Segment,
- kein `.`- oder `..`-Segment,
- jedes Segment besteht ausschließlich aus ASCII-Buchstaben, Ziffern, Punkt, Unterstrich und Bindestrich,
- jedes Segment ist höchstens 128 Zeichen lang,
- der vollständige relative Pfad ist höchstens 512 Zeichen lang,
- kein Segment endet mit Punkt oder Leerzeichen,
- kein Segment ist ein reservierter Windows-Gerätename wie `CON`, `PRN`, `AUX`, `NUL`, `COM1` bis `COM9` oder `LPT1` bis `LPT9`, auch nicht mit Dateiendung,
- symbolische Links, Hardlinks, Geräte, FIFOs, Sockets und andere besondere Archivtypen sind unzulässig,
- vorhandene symbolische Links oder andere nicht reguläre Ziel- oder Elternpfade werden nicht überschrieben,
- doppelte normalisierte Zielpfade werden abgelehnt,
- Groß-/Kleinschreibungs-Kollisionen werden plattformübergreifend als mehrdeutig abgelehnt.

### 10.2 Verbotene interne Pfade

Kein Paket darf einen Pfad enthalten, bei dem irgendein normalisiertes Segment ohne Beachtung der Groß-/Kleinschreibung exakt einem der folgenden Namen entspricht:

```text
.git
.patchharbor
```

Das Verbot gilt für:

- reguläre Nutzdateien,
- Verzeichniseinträge,
- den Entrypoint-Pfad,
- alle Elternsegmente eines Eintrags.

Dadurch kann ein ZIP-Paket weder Git-Metadaten noch die lokale PatchHarbor-Identität direkt als Paketinhalt überschreiben.

Diese Regel ist eine Entpack- und Bereitstellungsgrenze, keine Sandbox für das anschließend gestartete Skript.

### 10.3 Vollständige Vorabvalidierung

Das gesamte Paket wird einschließlich aller Eintragstypen, Zielpfade, Duplikate, Kollisionen und Ressourcenbudgets validiert, bevor eine Zieldatei geschrieben wird.

Beim sicheren Apply werden zusätzlich vor der ersten Repository-Änderung:

- der Entrypoint privat temporär bereitgestellt,
- sein Pflichtmarker geprüft,
- der angeforderte Interpreter eindeutig bestimmt,
- die Verfügbarkeit des Interpreters geprüft,
- der endgültige Ausgabeordner aus `--output-dir` oder `exchange_directory` validiert und dort ein temporärer Ausgabepfad reserviert.

Ein unsicherer, beschädigter oder mehrdeutiger Eintrag oder ein fehlender Interpreter macht das gesamte Paket ungültig. Kein Skript wird gestartet und keine endgültige Nutzdatei wird geschrieben.

### 10.4 Schreiben und Atomizität

- Nutzdateien werden bytegenau vorbereitet.
- Vorhandene reguläre Dateien werden ohne Nachfrage überschrieben.
- Jede Zieldatei wird zuerst vollständig in eine sichere temporäre Datei im selben Zielverzeichnis geschrieben und danach atomar ersetzt.
- Benötigte sichere Unterverzeichnisse werden angelegt.
- PatchHarbor legt keine dauerhaften Backups an.
- Jeder einzelne Dateiaustausch ist atomar.
- Das Gesamtpaket besitzt in 1.1.1 keine vollständige Transaktion und keine automatische globale Rückabwicklung.
- Scheitert die vollständige Vorbereitung oder ein tatsächlicher Schreibvorgang, startet kein Skript.

### 10.5 Ressourcenbudget

Ein Auftrag verwendet genau eine kleine unveränderliche `ResourcePolicy`.

Verbindliche Anfangswerte:

- Warning ab 10 MiB für einen einzelnen Skript- oder Nutzdateiinhalt,
- höchstens 256 MiB pro Eingabeartefakt oder ZIP-Eintrag,
- höchstens 512 MiB unkomprimierte Gesamtdaten eines Eingabe-ZIP-Archivs einschließlich Skripten, Manifest und Nutzdateien,
- höchstens 1.000 ZIP-Einträge einschließlich Verzeichnis-, Skript-, Manifest- und Nutzdateieinträgen.

Eine Pipe setzt das harte Eingabebudget bereits während des Empfangs durch.

Die ZIP-Auflösung prüft deklarierte Größen und Eintragszahlen vorab und die tatsächlich gelesenen Bytes erneut während des Lesens. Die Vorabprüfung stoppt offensichtlich zu große Archive früh; die laufende Prüfung schützt vor falschen oder manipulierten Größenangaben.

Eine Überschreitung eines harten Budgets führt vor der Ausführung zu einem Tool-Fehler. Die Warning-Schwelle allein verhindert die Verarbeitung nicht.

---

## 11. Interpreter und Ausführung

### 11.1 Unterstützte Interpreter

PatchHarbor 1.1.1 unterstützt bewusst Bash und PowerShell.

- Linux ohne Shebang: Bash.
- Windows ohne Shebang: Windows PowerShell.
- Ein bekannter unterstützter Shebang in der ersten Skriptzeile hat Vorrang.
- Bash: `#!/bin/bash`, `#!/usr/bin/bash`, `#!/usr/bin/env bash`.
- Windows PowerShell: `#!powershell`, `#!powershell.exe`, `#!/usr/bin/env powershell`, `#!/usr/bin/env powershell.exe`.
- PowerShell 7: `#!pwsh`, `#!pwsh.exe`, `#!/usr/bin/pwsh`, `#!/usr/bin/env pwsh`, `#!/usr/bin/env pwsh.exe`.
- Unbekannte, erweiterte oder beliebige Shebang-Kommandos werden nicht ausgeführt.
- Ein angeforderter Interpreter wird vor Prozessstart über den Systempfad gesucht.
- Fehlt er, endet PatchHarbor mit einem klaren Tool-Fehler.
- Die Dateiendung entscheidet nicht über den Interpreter.
- Eine temporäre Skriptdatei erhält lediglich eine technisch passende Endung.
- Weitere Interpreter dürfen später nur über eine kleine geprüfte Zuordnung ergänzt werden, nicht über freie Kommandoausführung.

### 11.2 PowerShell auf Windows

- PowerShell wird ohne Benutzerprofil und nicht interaktiv gestartet.
- Die festen Prozessargumente enthalten weder `-ExecutionPolicy` noch `Bypass`.
- PatchHarbor umgeht oder verändert keine lokale oder zentrale Execution Policy.
- Verhindert die Richtlinie die Ausführung, bleibt die native PowerShell-Fehlermeldung sichtbar und der PowerShell-Exit-Code wird unverändert zurückgegeben.

### 11.3 Nicht interaktive Ausführung

Die Standardeingabe des Kindprozesses ist geschlossen.

Nicht unterstützt sind insbesondere:

- Eingabeaufforderungen,
- Ja/Nein-Rückfragen,
- Warten auf Enter,
- interaktive Programmsitzungen,
- während der Ausführung erforderliche Benutzereingaben.

### 11.4 Timeout und Prozessende

- Standard-Timeout: 10.800 Sekunden (drei Stunden) pro Skript beziehungsweise Entrypoint.
- Der Wert ist über `--timeout` änderbar.
- Bei normalem Ende wird der Skript-Exit-Code übernommen.
- Bei Timeout versucht PatchHarbor zunächst eine geordnete Beendigung.
- Nach einer Frist von zwei Sekunden wird der vollständige Prozessbaum hart beendet.
- Unter Linux wird eine eigene Prozesssitzung beziehungsweise Prozessgruppe verwendet.
- Unter Windows wird eine echte Prozessbaum-Lösung verwendet, vorzugsweise ein Windows Job Object.
- Strg+C beendet Skript und Kindprozesse und liefert Exit-Code 130.
- Timeout liefert Exit-Code 124.

### 11.5 Reihenfolge im manuellen PatchBundle

1. Eingabeartefakt vollständig auflösen.
2. Gesamtes Bundle validieren.
3. Alle Skripteinträge vollständig parsen und Pflichtmarker prüfen.
4. Beschädigte optionale META- oder MESSAGE-Inhalte als Warning verwerfen.
5. Für alle auszuführenden Skripte den Interpreter bestimmen und seine Verfügbarkeit prüfen.
6. Alle Nutzdateien vollständig vorbereiten und sicher schreiben.
7. Skripte in der Archiv-Reihenfolge im ursprünglichen Arbeitsverzeichnis starten.
8. Output erfassen und Status darstellen.
9. Bei Erfolg mit dem nächsten Skript fortfahren oder beim ersten Fehler abbrechen.
10. Exit-Code des zuletzt ausgeführten Skripts zurückgeben.

Damit führt auch im manuellen ZIP-Pfad ein vorhersehbar fehlender Interpreter nicht erst nach dem Schreiben von Nutzdateien zum Abbruch.

## 12. Output, Terminaldarstellung und manuelles Logging

### 12.1 Output-Erfassung

stdout und stderr des Kindprozesses werden unverändert zu einem gemeinsamen
zeitlich beobachteten Bytestrom zusammengeführt. PatchHarbor liest verfügbare
Chunks laufend, ohne auf einen Zeilenumbruch zu warten. Auch Testpunkte und eine
letzte unvollständige Zeile gelangen damit unmittelbar zur sichtbaren Ausgabe.
Die Erfassung kann den Kindprozess nicht zum Flush seiner eigenen Puffer zwingen.

Der vorhandene begrenzte Rolling Buffer bleibt für aufrufende Bibliotheksnutzer
erhalten; er begrenzt weder Live-Ausgabe noch das bytegenaue Ausführungslog.
Terminal-Steuersequenzen aus fremden Texten werden ausschließlich für die
sichtbare Darstellung entschärft. Der rohe Logstrom bleibt unverändert.

### 12.2 Farbige fortlaufende Konsole

Die bisherige feste Oberfläche entfällt. Normale Apply-, Bundle- und manuelle
Run-Aufträge erhalten eine ausführliche, chronologisch nach unten wachsende
Ausgabe. Keine Bildschirm-Löschung, kein Cursor-Verstecken, keine Neuzeichnung,
keine festen Fensterhöhen, keine Zeilen- oder Breitenkürzung von Meldungen.
Farben, Symbole, Zeitstempel und klare Phasenüberschriften sorgen für Übersicht.
`--no-color`, `NO_COLOR` und `TERM=dumb` deaktivieren Farben; `--plain` verwendet
einfache farblose Kennzeichnungen. Technische IDs bleiben nach Abschnitt 14.1
zentral auf sechs Zeichen plus `…` gekürzt, niemals in Maschinenverträgen.

Die Beobachtung beginnt bereits vor der Paketauswahl. Sie beschreibt die
wirklich stattfindenden Datei-, Inhalts-, SHA-, Bindungs-, Replay-, Recovery-,
Archivierungs-, Preflight-, Schreib-, Prozess- und Result-Schritte. Jeder
untersuchte Exchange-Eintrag und jeder Ausschluss erhält seinen tatsächlichen
Grund; eine aus identischem Inhalt wiederverwendete Klassifizierung wird als
solche benannt. Ordner, Links und unfertige Downloads werden nicht zur Anzeige
geöffnet. Es entstehen keine zusätzlichen Dateizugriffe oder Sicherheitsprüfungen
allein für die Darstellung. Beobachter dürfen keine Berechtigung erteilen oder
fachliche Entscheidungen beeinflussen.

Alle bereits geparsten MESSAGE-Blöcke erscheinen vollständig vor dem zugehörigen
Skript, ohne Zeilenbegrenzung. Es handelt sich um deklarative Kommentarblöcke,
nicht um zur Laufzeit ausgeführte Meldungsanweisungen. Laufende Skriptausgaben
werden unabhängig davon sofort weitergereicht. Dateimeldungen zeigen Pfade,
Rollen, Größen und Ergebnisse, niemals Nutzdateiinhalte.

### 12.3 Umleitung, JSON und Logs

Bei umgeleitetem stdout und bei `--plain` bleiben die sichtbaren Skriptdaten auf
stdout; die zusätzlichen menschlichen Ablaufmeldungen gehen auf stderr. Im
interaktiven Normalmodus erscheinen beide in der gemeinsamen Konsole. Es werden
keine Farben in Pipes geschrieben. Bereits vorhandene Abschlussangaben für
nicht interaktive Aufrufe bleiben verfügbar. JSON-Befehle verwenden weiterhin
exakt ihr geschlossenes Schema und mischen keine Ablaufmeldungen oder
Skriptausgaben in stdout.

Das zusätzliche interne Ablaufprotokoll ist Konsolenausgabe. Es wird nicht in
das bytegenaue `logs/execution.log` eines Apply-Result-Bundles eingemischt und
fügt keine neuen ZIP-Einträge zum bestehenden Result- oder Recovery-Vertrag
hinzu. Dieser Log bleibt der vollständige rohe Entrypoint-Strom; strukturierte
Run-Metadaten und die bisherigen manuellen Log-Metadaten bleiben erhalten.

### 12.4 `--log` des manuellen Runners

Mit `patchharbor fs run --log` wird der vollständige zusammengeführte Output zusätzlich in eine sichere eindeutig benannte Datei im System-Temp-Verzeichnis geschrieben.

Das Log enthält:

- Startzeit,
- Quelle,
- Arbeitsverzeichnis,
- gewählten Interpreter,
- PatchHarbor-Warnings,
- vollständigen rohen Skriptoutput,
- Endzeit,
- Exit-Code oder Tool-Fehler.

Ohne `--log` erzeugt der manuelle Runner keine vollständige separate Ausgabedatei.

Der sichere Apply-Pfad verwendet unabhängig davon den vollständigen Run-Log für sein Result Bundle.

---

## 13. Registrierung lokaler Repository-Instanzen

### 13.1 Identitätsmodell

Ein entferntes Git-Repository kann mehrfach geklont, kopiert oder als zusätzlicher Worktree vorhanden sein. Jede lokale Instanz kann einen anderen Commit, Index und Working Tree besitzen.

Die PatchHarbor-ID gehört deshalb zu genau einer lokalen Repository-Instanz und nicht zum abstrakten Remote-Repository.

### 13.2 Globaler Registry-Lock und Persistenz

Alle lesenden und schreibenden Registry-Operationen verwenden einen eigenen globalen Registry-Lock. Dieser Lock ist von den Repository-Locks getrennt.

Verbindliche Lock-Reihenfolge:

1. globaler Registry-Lock,
2. danach gegebenenfalls der betroffene Repository-Lock.

Kein Codepfad darf diese Reihenfolge umkehren.

Die zentrale Registry wird:

- vollständig in eine temporäre Datei im selben Konfigurationsverzeichnis geschrieben,
- vor Veröffentlichung geschlossen und syntaktisch geprüft,
- anschließend über einen atomaren Austausch ersetzt,
- niemals durch stückweises direktes Überschreiben aktualisiert.

Eine Operation meldet erst Erfolg, wenn lokale ID-Datei, lokale Konfiguration, Git-Ausnahme und zentrale Registry konsistent sind. Scheitert eine Teiloperation, versucht PatchHarbor den vorherigen Zustand wiederherzustellen und meldet bei verbleibender Inkonsistenz einen ausdrücklichen Registry-Fehler. Es wird kein scheinbarer Erfolg ausgegeben.

### 13.3 Registrierung

```bash
patchharbor register
patchharbor register /pfad/zum/repository
```

PatchHarbor führt unter dem globalen Registry-Lock mindestens aus:

1. kanonischen Repository-Wurzelpfad bestimmen,
2. prüfen, dass `HEAD` auf einen Commit auflösbar ist,
3. prüfen, dass weder der Base-Baum von `HEAD` noch der Index einen Pfad mit dem reservierten Segment `.patchharbor` in beliebiger Groß-/Kleinschreibung enthält,
4. prüfen, dass die neue Repository-Wurzel keinen Exchange eines gültig auflösbaren registrierten Repositorys enthält, darin liegt oder damit identisch ist,
5. prüfen, dass ein vorhandener Pfad `.patchharbor` ein echtes reguläres Verzeichnis und weder Symlink noch Junction noch Datei ist,
6. das lokale interne Verzeichnis andernfalls sicher anlegen,
7. vorhandene lokale ID und Konfiguration validieren; nur bei echter Erstanmeldung eine UUID v4 erzeugen,
8. den vollständigen lokalen Pfad `.patchharbor/` über den von `git rev-parse --git-path info/exclude` gelieferten Exclude-Pfad aus der normalen Git-Statusanzeige ausnehmen,
9. veraltete zentrale Zuordnungen desselben kanonischen Pfads entfernen,
10. bei echter Erstanmeldung die lokale Format-1-Grundkonfiguration ohne Exchange anlegen; ID, Konfiguration, Git-Ausnahme und Registry konsistent veröffentlichen,
11. eine gekürzte menschenlesbare Kontextzusammenfassung mit eindeutigem Verweis auf `patchharbor context --json` für vollständige Werte ausgeben.

PatchHarbor verändert nicht ungefragt die gemeinsam versionierte `.gitignore`.
Fehlende/ungültige lokale Metadaten einer bereits bekannten Instanz werden nicht
repariert. Die Fehler-Rücknahme einer noch nicht abgeschlossenen frischen
Registrierung erhält dagegen ihren bisherigen Transaktionsvertrag; sie ist keine
Migration, kein Reparaturmodus und keine Rückabwicklung eines Apply.

### 13.4 Repository-ID

Die Repository-ID ist eine UUID v4.

Beispiel:

```text
a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d
```

Eigenschaften:

- 36 Zeichen einschließlich Bindestrichen,
- automatisch erzeugt,
- praktisch eindeutig,
- unabhängig von Name, Remote-URL, Branch und Pfad,
- stabil für genau diese lokale Instanz,
- intern, persistent und maschinenlesbar nicht zu kürzen; nur die menschenlesbare UI darf einen klar gekennzeichneten Sechs-Zeichen-Präfix anzeigen,
- nicht fachlich zu interpretieren.

Jeder lokale Klon oder Worktree erhält eine eigene UUID.

### 13.5 Reserviertes lokales Verzeichnis

Das vollständige Verzeichnis:

```text
.patchharbor/
```

ist für lokale PatchHarbor-Daten reserviert.

Für diesen 1.2.0-Stand enthält es mindestens:

```text
.patchharbor/id
.patchharbor/config.json
```

Der Inhalt von `id` besteht ausschließlich aus der UUID und einem abschließenden Zeilenumbruch.

Verbindliche Regeln:

- Kein Pfad unter `.patchharbor/` darf von Git getrackt sein.
- `.patchharbor` selbst darf kein Symlink, keine Junction und kein anderer besonderer Dateityp sein.
- ID und Konfiguration müssen reguläre Dateien sein und werden atomar geschrieben. Eine fehlende/ungültige Config bleibt bis zur manuellen Korrektur ein Fehler.
- Das gesamte Verzeichnis wird lokal ausgeschlossen und nicht in Result Bundles aufgenommen.
- Die Repository-ID selbst steht in den maschinenlesbaren Kontextdateien.

### 13.6 Idempotente Registrierung und Pfadänderungen

Ist derselbe kanonische Pfad bereits mit derselben gültigen ID und gültiger lokaler Konfiguration/Exclude registriert, ist `patchharbor register` idempotent und gibt den bestehenden Kontext zurück, ohne die Einstellungen zurückzusetzen.

Ist eine ID einem anderen weiterhin vorhandenen Pfad zugeordnet, wird nicht geraten. Die Registrierung wird als Konflikt abgelehnt.

Ist das Repository einschließlich ID, Konfiguration und Git-Ausnahme an einen neuen Pfad verschoben worden und der bisher registrierte Pfad existiert nicht mehr, darf `patchharbor register` die Zuordnung auf den neuen kanonischen Pfad aktualisieren; die Einstellungen bleiben erhalten.

Fehlt die lokale ID-Datei, obwohl eine lokale Konfiguration oder Registry-Bindung
für diesen Pfad besteht, wird ohne automatische Neuerzeugung abgebrochen. Nur eine
wirklich neue lokale Instanz erhält eine neue UUID und Defaults. Ein normaler
Git-Clone übernimmt die ignorierten lokalen Dateien nicht und benötigt Register
plus Configure. Es bleiben niemals zwei IDs für denselben kanonischen Pfad als
erfolgreicher Zustand bestehen.

### 13.7 Minimale Registry-Verwaltung

```bash
patchharbor registry list
```

liest unter dem globalen Registry-Lock einen konsistenten Snapshot und zeigt mindestens:

- `repo_id`,
- kanonischen Pfad,
- Status `ok`, `missing` oder `conflict`.

Die menschenlesbare Liste kürzt `repo_id` auf sechs Zeichen plus `…`. Vollständige
UUIDs liefert `patchharbor registry list --json`. Ein gekürzter Präfix ist reine
Präsentation und kein gültiger Selektor für `unregister`; dort ist die
vollständige kanonische UUID oder der exakte Repository-Pfad zu verwenden.

```bash
patchharbor unregister REPOSITORY_OR_REPO_ID
```

entfernt unter dem globalen Registry-Lock die zentrale Zuordnung. Soweit ein vorhandenes Repository betroffen ist, wird zusätzlich dessen Repository-Lock beachtet. Die lokale `.patchharbor/id`, `.patchharbor/config.json` und Git-Ausnahme bleiben bestehen, damit ein verschobenes oder später erneut registriertes Repository Identität und Einstellungen behält.

```bash
patchharbor register --new-id [REPOSITORY]
```

- erzeugt bewusst eine neue UUID,
- ersetzt die lokale ID-Datei atomar, erhält aber eine vorhandene gültige lokale Konfiguration; keine Reparatur fehlender oder beschädigter Metadaten,
- entfernt alte Zuordnungen genau dieses kanonischen Pfads,
- verändert nicht die gültige Zuordnung eines anderen Pfads mit einer kopierten alten ID,
- registriert die neue ID,
- ist der vorgesehene Minimalweg zur Auflösung einer kopierten ID.

Registry-Mutationen, die eine aktuell gesperrte Repository-Instanz verändern würden, warten kontrolliert oder schlagen mit einer eindeutigen Busy-Meldung fehl; sie umgehen den Repository-Lock nicht.

## 14. Repository-Kontext und Zustandsmodell

### 14.1 Kontextbefehl

```bash
patchharbor context
patchharbor context /pfad/zum/repository
patchharbor context --json
patchharbor context --json /pfad/zum/repository
```

Der Kontextbefehl verwendet den Repository-Lock für die Dauer seiner Zustandsaufnahme.

Beispiel:

```text
PATCH_HARBOR_CONTEXT

repo_id: a3f9c2…
base_commit: f4e9c2…
dirty: true
state_fingerprint: a1b2c3…
fingerprint_algorithm: patchharbor-state-v1

INSTRUCTIONS:
- Kurzansicht nicht in patch.json oder als Chat-/Maschineninput verwenden.
- Vollständige Werte mit patchharbor context --json [REPOSITORY] ausgeben.
- Erzeuge bei geändertem Repository-Zustand einen neuen Kontext.
```

Menschenlesbare Terminalausgaben kürzen lange technische Kennungen zentral auf die ersten sechs Zeichen plus das einzelne Zeichen `…`. Das betrifft insbesondere Repository-IDs, Run-IDs, Base-Commits und Zustands-Fingerprints. Dateinamen verwenden denselben Sechs-Zeichen-Präfix ohne `…`. Maschinenlesbare JSON-Ausgaben, Manifeste, persistenter Zustand, Logs und alle Sicherheitsvergleiche behalten stets den vollständigen Wert.

Der Block `PATCH_HARBOR_CONTEXT` ist daher ausschließlich eine Kurzansicht zur menschlichen Kontrolle und keine kopierbare Maschinenrepräsentation. `patchharbor register` gibt denselben Block aus und besitzt bewusst keine `--json`-Option. Vollständige eigenständige Kontextwerte werden mit `patchharbor context --json [REPOSITORY]` ausgegeben.

Der Chat darf Repository-ID, Base-Commit oder Fingerprint nicht erraten und verwendet für `patch.json` die vollständigen Werte aus `context.json` des aktuellen Result Bundles. Wird ausnahmsweise ein separater Kontext als JSON übergeben, muss er aus `patchharbor context --json` stammen; die verkürzte Standardausgabe ist kein zulässiger Ersatz.

### 14.2 Base-Commit

`base_commit` ist die vollständige Ausgabe von:

```bash
git rev-parse HEAD
```

Der Wert wird nicht künstlich auf 40 Zeichen begrenzt und unterstützt damit unterschiedliche Git-Objektformate.

Der Base-Commit beschreibt den committed Basiszustand und wird getrennt vom Fingerprint geprüft.

### 14.3 Dirty State

Der Dirty State beschreibt alle nicht in `HEAD` enthaltenen unterstützten Git-Zustände:

- staged Änderungen im Index,
- unstaged Änderungen zwischen Index und Working Tree,
- nicht ignorierte untracked reguläre Dateien.

Dazu gehören Hinzufügungen, Änderungen, Löschungen und unterstützte Dateimodusänderungen. Umbenennungen werden kanonisch als Löschung plus Hinzufügung dargestellt.

Ignorierte Dateien werden nicht aufgenommen.

### 14.4 Algorithmuskennung

Der verbindliche Algorithmus heißt:

```text
patchharbor-state-v1
```

Jeder Kontext und jedes Manifest nennt diese Kennung. Ein unbekannter Algorithmus wird abgelehnt.

Der endgültige Fingerprint ist:

```text
SHA-256 über den kanonischen Eingabestrom
→ erste 16 kleingeschriebene Hex-Zeichen
```

### 14.5 Unterstützte Repository-Grenzen

Der sichere 1.1.1-Pfad unterstützt ausschließlich Repository-Zustände, die auf Linux und Windows eindeutig, sicher und vollständig darstellbar sind.

Die Pfadprüfung umfasst die Vereinigungsmenge aus:

- allen Pfaden des Base-Baums von `HEAD`,
- allen Pfaden des Index,
- allen von Git als unstaged betroffen gemeldeten getrackten Pfaden,
- allen nicht ignorierten untracked Pfaden.

Damit wird ein im Base-Baum noch vorhandener, aber im Index bereits zur Löschung vorgesehener verbotener Pfad ebenfalls abgelehnt.

Alle von Git gelieferten Repository-Pfade müssen gültiges UTF-8 sein. PatchHarbor decodiert streng, führt keine Unicode-Normalisierung aus und verwendet für Hashing und Manifest wieder exakt die ursprünglichen UTF-8-Bytes. Ein nicht streng als UTF-8 darstellbarer Pfad führt zu einem klaren Fehler wegen nicht unterstützten Repository-Zustands.

Jeder Repository-Pfad ist ein relativer POSIX-Pfad mit `/` als Segmenttrenner. Für jedes Segment gelten verbindlich:

- nicht leer,
- weder `.` noch `..`,
- kein NUL-Byte,
- keine ASCII-Steuerzeichen `U+0001` bis `U+001F` und kein `U+007F`,
- keines der Zeichen `<`, `>`, `:`, `"`, `\`, `|`, `?` oder `*`,
- kein abschließender Punkt und kein abschließendes ASCII-Leerzeichen,
- weder `.git` noch `.patchharbor` nach Unicode-`casefold()`,
- kein reservierter Windows-Gerätename nach Unicode-`casefold()`.

Als reservierte Windows-Gerätenamen gelten der Segmentteil vor dem ersten Punkt mit den Werten:

```text
con
prn
aux
nul
com1 bis com9
lpt1 bis lpt9
conin$
conout$
clock$
```

Für die Kollisionsprüfung bildet PatchHarbor aus jedem vollständig decodierten Pfad einen Vergleichsschlüssel mit Unicode-`casefold()`, ohne die gespeicherten Pfadbytes zu verändern. Zwei verschiedene Repository-Pfade mit demselben Vergleichsschlüssel werden als Groß-/Kleinschreibungs-Kollision abgelehnt.

Die gleichen Portabilitätsregeln gelten für Pfade, die in `base/`, `untracked/`, Rekonstruktions-Patches oder JSON-Manifeste aufgenommen werden. Ein nicht sicher als regulärer UTF-8-ZIP-Pfad darstellbarer Repository-Pfad wird vor Kontextausgabe, Apply oder Bundle-Erzeugung abgelehnt.

Vor Kontext, Apply und Bundle werden außerdem folgende Zustände abgelehnt:

- nicht aufgelöste Merge-Stages,
- Indexeinträge mit `assume-unchanged`,
- Indexeinträge mit `skip-worktree`,
- Intent-to-add-Einträge,
- aktiviertes Sparse-Checkout,
- Sparse-Index,
- Gitlink-Einträge beziehungsweise Submodule,
- getrackte symbolische Links in `HEAD` oder Index,
- ein symbolischer Link oder anderer besonderer Dateityp an einem getrackten Working-Tree-Pfad,
- andere getrackte Modi als `100644` und `100755`,
- nicht reguläre untracked Einträge.

Der manuelle Befehl `patchharbor fs run` ist von diesen Repository-Grenzen nicht betroffen.

### 14.6 Kanonische Git-Umgebung und Abfragen

Alle Git-Befehle laufen:

- im kanonischen Repository-Wurzelverzeichnis,
- mit `LC_ALL=C` und `LANG=C`,
- mit `GIT_OPTIONAL_LOCKS=0`,
- mit deaktiviertem externem Diff-Programm,
- ohne Textkonvertierung,
- ohne Rename-Erkennung,
- ohne Farbausgabe,
- mit NUL-getrennter Pfadausgabe, wo Git sie anbietet.

Verbindliche Abfragen umfassen mindestens:

```text
git rev-parse HEAD
git ls-tree -r -z --full-tree <base_commit>
git ls-files --stage -z
git ls-files --unmerged -z
git ls-files -v -z
git diff-files --raw -z --no-renames --no-ext-diff --
git ls-files --others --exclude-standard -z --
git config --bool --get core.fileMode
git config --bool --get core.sparseCheckout
git config --bool --get index.sparse
```

Fehlende boolesche Konfigurationswerte gelten als `false`, soweit Git keinen repositoryspezifischen Standardwert liefert.

Sonderzustände werden wie folgt erkannt:

- Eine nicht leere Ausgabe von `git ls-files --unmerged -z` wird abgelehnt.
- Bei `git ls-files -v -z` kennzeichnet ein führendes `S` einen Skip-Worktree-Eintrag; ein kleingeschriebener führender Statusbuchstabe kennzeichnet Assume-Unchanged. Beide werden abgelehnt.
- Ein `A`-Datensatz in `git diff-files --raw -z` wird als Intent-to-add-Sonderzustand abgelehnt.
- `core.sparseCheckout=true` oder `index.sparse=true` wird abgelehnt.
- Baum- oder Indexmodi `120000` und `160000` sowie alle nicht ausdrücklich unterstützten Modi werden abgelehnt.

PatchHarbor liest die Ausgaben als Bytes und normalisiert keine Zeilenenden oder Pfadbytes.

### 14.7 Kanonischer staged Zustand

PatchHarbor bildet aus `git ls-tree -r -z --full-tree <base_commit>` den Base-Baum und aus `git ls-files --stage -z` den Index ab.

Für jeden Pfad, dessen `(mode, object-id)` zwischen Base-Commit und Index abweicht, wird genau ein staged Datensatz erzeugt.

Ein Datensatz enthält in dieser Reihenfolge:

1. Pfadbytes,
2. Base-Modus oder leeres Feld,
3. vollständige Base-Objekt-ID oder leeres Feld,
4. Indexmodus oder leeres Feld,
5. vollständige Indexobjekt-ID oder leeres Feld.

Die Datensätze werden byteweise nach Pfad sortiert.

Damit sind Hinzufügungen, Änderungen, Löschungen und Modusänderungen eindeutig beschrieben, ohne von einer konfigurierbaren Patch-Darstellung abhängig zu sein.

### 14.8 Kanonischer unstaged Zustand

`git diff-files --raw -z --no-renames --no-ext-diff --` bestimmt die getrackten Pfade, die Git gegenüber dem Index als unstaged verändert betrachtet.

Ein Intent-to-add-Datensatz wird vor der Fingerprint-Bildung abgelehnt.

Für jeden übrigen betroffenen Pfad wird genau ein Datensatz erzeugt. Er enthält:

1. Pfadbytes,
2. Git-Statusbyte,
3. Indexmodus,
4. vollständige Indexobjekt-ID,
5. Working-Tree-Art `missing` oder `regular`,
6. kanonischen Working-Tree-Modus,
7. vollständigen aktuellen Inhalt als rohe Bytes; bei `missing` ein leeres Feld.

Die Datensätze werden byteweise nach Pfad sortiert.

Der Working-Tree-Modus lautet:

- `100755`, wenn `core.fileMode=true` gilt und mindestens ein Ausführungsbit der regulären Datei gesetzt ist,
- sonst `100644` für reguläre Dateien,
- leer für fehlende Einträge.

PatchHarbor verwendet `lstat` und folgt keinem symbolischen Link. Trifft es an einem getrackten Pfad auf einen Symlink, ein Verzeichnis oder einen anderen besonderen Dateityp, wird der sichere Auftrag abgelehnt.

### 14.9 Kanonischer untracked Zustand

Die Ausgabe von `git ls-files --others --exclude-standard -z --` liefert die nicht ignorierten untracked Pfade.

Die Pfade werden byteweise sortiert.

Für jeden Pfad werden einbezogen:

1. Pfadbytes,
2. kanonischer Modus,
3. Dateigröße,
4. vollständiger Dateiinhalt als rohe Bytes.

Der kanonische Modus lautet:

- `100755`, wenn `core.fileMode=true` gilt und mindestens ein Ausführungsbit gesetzt ist,
- sonst `100644`.

Nur reguläre Dateien sind zulässig. Symlinks, Junctions, Geräte, FIFOs, Sockets, Verzeichnisse oder andere besondere Einträge führen zu einem klaren Kontextfehler und werden niemals dereferenziert.

### 14.10 Kanonische Payloadcodierung und Byte-Rahmung

Der Hash-Eingabestrom beginnt exakt mit diesen Bytes:

```text
PATCHHARBOR_STATE_FINGERPRINT\0
1\0
```

Feldnamen sind exakt die in diesem Abschnitt genannten ASCII-Bytes ohne Groß-/Kleinschreibungsvariation.

Jedes Feld wird codiert als:

```text
ASCII-Feldname
+ NUL-Byte
+ 8-Byte-Länge des Payloads, unsigned big-endian
+ Payloadbytes
```

Für alle Payloads gelten verbindlich:

| Fachlicher Wert | Exakte Payloadcodierung |
|---|---|
| Repository-Pfad | Die ursprünglichen streng validierten UTF-8-Pfadbytes, ohne Normalisierung und ohne abschließendes NUL. |
| Git-Modus | ASCII `100644` oder ASCII `100755`; ein fachlich fehlender Modus ist ein Payload der Länge null. |
| Git-Objekt-ID | Vollständiger kleingeschriebener ASCII-Hex-String des Repository-Objektformats; 40 Zeichen bei SHA-1 und 64 Zeichen bei SHA-256. Keine Abkürzung und keine rohen Objekt-ID-Bytes. |
| Unstaged-Status | Genau ein großgeschriebenes ASCII-Byte. Im unterstützten 1.1.1-Zustand sind ausschließlich `M` und `D` zulässig. |
| Working-Tree-Art | Exakt ASCII `regular` oder ASCII `missing`. |
| Dateiinhalt | Unveränderte rohe Bytes, einschließlich vorhandener NUL-Bytes und Zeilenenden. |
| Zähler und Dateigröße | Genau acht Bytes, unsigned big-endian. |
| Fachlich leerer Wert | Payloadlänge null; das Feld selbst bleibt vorhanden. |

Es werden keine impliziten Zeilenumbrüche, Terminatoren, Textcodierungen oder Trennzeichen ergänzt.

Die Payload jedes Zählerfelds ist eine 8-Byte-Zahl, unsigned big-endian.

Abschnittsreihenfolge und exakte Feldnamen:

1. `staged-count`,
2. je staged Datensatz: `staged-path`, `staged-head-mode`, `staged-head-object`, `staged-index-mode`, `staged-index-object`,
3. `unstaged-count`,
4. je unstaged Datensatz: `unstaged-path`, `unstaged-status`, `unstaged-index-mode`, `unstaged-index-object`, `unstaged-worktree-kind`, `unstaged-worktree-mode`, `unstaged-worktree-content`,
5. `untracked-count`,
6. je untracked Datensatz: `untracked-path`, `untracked-mode`, `untracked-size`, `untracked-content`.

Die Payload von `untracked-size` ist eine 8-Byte-Zahl, unsigned big-endian. Leere fachliche Werte werden als Feld mit Payloadlänge null codiert; das Feld selbst wird nicht ausgelassen.

Jeder Datensatz besteht damit ausschließlich aus einzeln längencodierten Feldern. Es gibt keine Trennzeichenverkettung ohne Längenfeld.

Der Base-Commit wird nicht in diesen Eingabestrom aufgenommen.

### 14.11 Clean-Zustand

Auch ein sauberes Repository besitzt einen deterministischen Fingerprint. Alle drei Zähler sind null; das zusätzliche Feld `dirty: false` dient nur der Lesbarkeit.

### 14.12 Referenz-Testvektoren

Die Implementierung muss mindestens die folgenden reinen Encoder-Testvektoren erfüllen. Die Zeichenfolgen in den Vektoren werden nach den Codierungsregeln aus Abschnitt 14.10 in Payloadbytes überführt.

#### Leerer Zustand

Für einen leeren Zustand mit null staged, null unstaged und null untracked Datensätzen:

```text
vollständiger SHA-256:
7c9d2a24e397e0e58d8caf4c14abf8f76879b256ef7f843655981fb751c7b309

16-stelliger Fingerprint:
7c9d2a24e397e0e5
```

#### Genau eine untracked Datei

```text
Pfad:    note.txt
Modus:   100644
Inhalt:  hello\n
```

Alle staged- und unstaged-Zähler sind null; `untracked-count` ist eins.

```text
vollständiger SHA-256:
05fe268b93ee2ea113d23b0dfc1becd7bfe881f8992e91b7e2ea8bdea2745310

16-stelliger Fingerprint:
05fe268b93ee2ea1
```

#### Genau eine staged Hinzufügung

```text
staged-path:          app.txt
staged-head-mode:     <leer>
staged-head-object:   <leer>
staged-index-mode:    100644
staged-index-object:  0123456789abcdef0123456789abcdef01234567
```

`staged-count` ist eins; alle unstaged- und untracked-Zähler sind null.

```text
vollständiger SHA-256:
b56f3f6610db992f53139dc53d1decdccb9fd510260dafa1a29473c47a257008

16-stelliger Fingerprint:
b56f3f6610db992f
```

#### Genau eine unstaged Änderung

```text
unstaged-path:              app.txt
unstaged-status:            M
unstaged-index-mode:        100644
unstaged-index-object:      0123456789abcdef0123456789abcdef01234567
unstaged-worktree-kind:     regular
unstaged-worktree-mode:     100644
unstaged-worktree-content:  hello\n
```

Alle staged- und untracked-Zähler sind null; `unstaged-count` ist eins.

```text
vollständiger SHA-256:
fa106451ef080706f5f24269d0dc2192bd50ef6f5ac69215485771137a8d3010

16-stelliger Fingerprint:
fa106451ef080706
```

Die vier Testvektoren prüfen Feldcodierung, Abschnittsreihenfolge und Byte-Rahmung. Repository-basierte Tests prüfen zusätzlich die kanonische Erzeugung aller staged-, unstaged- und untracked Datensätze auf Linux und Windows.

### 14.13 Kontextänderung

Ändert sich nach der Kontexterzeugung einer der folgenden Zustände, ist ein alter Patch nicht mehr gültig:

- `HEAD`,
- Index,
- getrackter Working Tree,
- Pfad, Modus oder Inhalt einer nicht ignorierten untracked Datei.

PatchHarbor lehnt den Patch ab. Der Benutzer erzeugt einen neuen Kontext oder ein neues Result Bundle.

## 15. Sicheres Patch-Paket

### 15.1 Container

Ein über `patchharbor apply` verarbeiteter Patch ist immer ein ZIP-Paket.

Der äußere Dateiname und die Dateiendung sind keine Sicherheits- oder Zuordnungsinformation. PatchHarbor prüft die tatsächlichen ZIP-Bytes.

### 15.2 Verpflichtende Wurzeldatei

Im Wurzelverzeichnis des ZIP-Pakets liegt genau eine Datei mit dem Namen:

```text
patch.json
```

Weitere sichere Dateien und Unterverzeichnisse sind zulässig.

Beispiel:

```text
patch.zip
├── patch.json
├── run.sh
└── files/
    └── configuration.bin
```

### 15.3 `patch.json`

`patch.json` ist UTF-8 ohne Byte-Order-Mark und enthält genau ein JSON-Objekt. Doppelte Schlüssel, Kommentare, nachgestellte Daten und nicht endliche Zahlenwerte sind ungültig.

Für Paketformat 1 sind ausschließlich die folgenden sieben Schlüssel zulässig; unbekannte oder zusätzliche Schlüssel werden abgelehnt:

```json
{
  "marker": "patch-harbor",
  "format_version": 1,
  "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
  "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
  "state_fingerprint": "a1b2c3d4e5f67890",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "entrypoint": "run.sh"
}
```

Der Vertrag lautet exakt:

| Feld | Typ und Validierung |
|---|---|
| `marker` | JSON-String, exakt `patch-harbor`. |
| `format_version` | JSON-Integer, exakt `1`; ein Boolean oder Gleitkommawert ist ungültig. |
| `repo_id` | JSON-String in kanonischer kleingeschriebener UUID-v4-Schreibweise nach dem Muster `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`, wobei `y` eines von `8`, `9`, `a`, `b` ist. |
| `base_commit` | JSON-String mit der vollständigen kleingeschriebenen Hex-Objekt-ID; exakt 40 Zeichen für ein SHA-1-Repository oder 64 Zeichen für ein SHA-256-Repository. Abgekürzte Objekt-IDs sind verboten. |
| `state_fingerprint` | JSON-String aus exakt 16 kleingeschriebenen Hex-Zeichen. |
| `fingerprint_algorithm` | JSON-String, exakt `patchharbor-state-v1`. |
| `entrypoint` | Nicht leerer JSON-String, der nach Abschnitt 10 einen sicheren relativen ZIP-Pfad bezeichnet, nicht `patch.json` ist und exakt einen vorhandenen regulären ZIP-Eintrag referenziert. |

Die exakte Objekt-ID-Länge wird nach Auflösung von `repo_id` gegen das Objektformat des Ziel-Repositorys geprüft. Der angegebene Commit muss zusätzlich exakt dem aktuellen `HEAD` entsprechen.

Eine Verletzung dieses Schemas, eine nicht unterstützte Formatversion oder eine unbekannte Semantik führt vor der Repository-Änderung zur Ablehnung. Erweiterungen des Paketvertrags erfordern eine neue `format_version`.

### 15.4 Entrypoint-Lebenszyklus

Der Entrypoint:

- ist genau ein regulärer ZIP-Eintrag,
- liegt nicht unter einem verbotenen Pfad,
- wird nicht als Nutzdatei in das Repository geschrieben,
- wird in ein privates temporäres Auftragsverzeichnis extrahiert,
- wird dort vollständig gelesen und anhand des exakten Skriptmarkers validiert,
- wird mit der bestehenden Interpreter-Whitelist gestartet,
- läuft mit dem Ziel-Repository als aktuellem Arbeitsverzeichnis,
- erhält geschlossene Standardeingabe,
- wird nach dem Auftrag entfernt.

Der temporäre Speicherort ist kein Teil der öffentlichen Patch-Schnittstelle.

### 15.5 Weitere Paketdateien

Jeder andere sichere reguläre ZIP-Eintrag außer `patch.json` und dem Entrypoint ist eine Nutzdatei.

Nutzdateien können Text, Binärdaten, Unterverzeichnisse oder nicht automatisch ausgeführte Hilfsskripte enthalten. Sie werden bytegenau in den entsprechenden relativen Repository-Pfad geschrieben.

Nur der in `patch.json` benannte Entrypoint wird automatisch gestartet. Ein Marker in einer anderen Paketdatei macht diese Datei nicht zu einem weiteren Entrypoint.

### 15.6 Keine rekursive Paketauflösung

Ein enthaltenes ZIP oder anderes Archiv wird nicht als weiteres Patch-Paket geöffnet. Ist es ein sicherer regulärer Nutzdateieintrag, wird es ausschließlich bytegenau als Datei behandelt.

---

## 16. Exklusive Repository-Sperre, Exchange-Auswahl und Apply-Ablauf

### 16.1 Sperrmodell

Für jede `repo_id` existiert genau eine betriebssystemübergreifende exklusive Sperre im benutzerspezifischen Lock-Verzeichnis.

Die Sperre:

- wird von `context`, `apply`, `apply --dry-run` und `bundle` verwendet,
- gilt pro `repo_id`, nicht pro Exchange-Dateiname,
- wird vor der ersten vollständigen Zustandsaufnahme des ausgewählten Repositorys erworben,
- bleibt bei `apply`, Dry-Run und Bundle bis zum Abschluss oder Fehlschlag der Result-Bundle-Erzeugung gehalten,
- wird bei `context` unmittelbar nach der konsistenten Zustandsaufnahme freigegeben,
- wird über einen sicheren Cleanup-Pfad freigegeben,
- darf durch Prozessabsturz nicht dauerhaft unauflösbar werden.

Kann die Sperre nicht erworben werden, startet kein weiterer Auftrag für dieses Repository. PatchHarbor liefert den Tool-Fehler „Repository beschäftigt“.

Die Sperre koordiniert PatchHarbor-Aufträge. Fremde Editoren oder andere Git-Prozesse werden dadurch nicht blockiert.

Bei einer Auflösung über die zentrale Registry gilt die Lock-Reihenfolge aus Abschnitt 13: zuerst globaler Registry-Lock, danach Repository-Lock. Nach erfolgreicher Revalidierung wird der Registry-Lock freigegeben, während der Repository-Lock bis zum Auftragsende gehalten bleibt.

### 16.2 Parameterlose Paketauswahl im Exchange-Ordner

Wird `patchharbor apply` ohne `PATCH_ZIP` aufgerufen, verwendet PatchHarbor ausschließlich den konfigurierten Exchange-Ordner. Der Aufruf besitzt intern entweder den Ursprung `manual` oder `automatic`; der normale CLI-Aufruf ist manuell, der Watcher delegiert mit automatischem Ursprung.

Beim manuellen Ursprung wird vor dem Exchange-Scan zuerst der Auswahlkontext bestimmt:

1. Das aktuelle Arbeitsverzeichnis wird zu seiner kanonischen Git-Repository-Wurzel aufgelöst; ein Aufruf aus einem beliebigen Unterverzeichnis gehört zur selben Wurzel.
2. Lokale Repository-ID und zentrale Registry müssen diese konkrete Repository-Instanz eindeutig und widerspruchsfrei registrieren.
3. Unter der verbindlichen Lock-Reihenfolge werden `repo_id`, Base-Commit, Fingerprint und Fingerprint-Algorithmus konsistent aufgenommen.

Kann das aktuelle Arbeitsverzeichnis nicht genau einer registrierten Repository-Instanz zugeordnet werden, endet der manuelle Auftrag kontrolliert vor der Exchange-Auswahl. PatchHarbor darf dann kein Paket eines anderen registrierten Repositorys als Ersatz auswählen.

Beim automatischen Ursprung wird kein Repository aus dem Arbeitsverzeichnis
vorgegeben. Dieser Ursprung bleibt für den Watcher global. Unter dem Registry-Lock
werden alle auflösbaren lokalen Konfigurationen gelesen. Physisch kanonisierte
Exchange-Pfade werden zusammengefasst: ein flacher Scan pro eindeutigem Ordner,
nicht pro Registry-Eintrag. Gültige `null`-Einstellungen und fehlende Repository-
Pfade werden übersprungen; beschädigte Konfigurationen vorhandener Instanzen,
Konflikte oder nicht verfügbare gesetzte Exchange-Verzeichnisse brechen den Poll
vor Ausführung ab. Geänderte Einstellungen werden beim nächsten Poll neu geladen.

Die anschließende gemeinsame Kandidatenklassifikation:

1. lädt und validiert die lokalen `.patchharbor/config.json` des jeweiligen manuellen oder automatischen Repository-Scopes,
2. scannt pro physisch eindeutigem Exchange genau die oberste Verzeichnisebene und niemals rekursiv,
3. berücksichtigt nur reguläre Dateien und folgt keinen Symlinks oder Junctions,
4. ignoriert bekannte temporäre Browser-Downloads,
5. ermittelt eine stabile Dateiaufnahme mit physisch kanonischem Pfad, vollständigem SHA-256-Inhalt und `mtime_ns`,
6. verwendet für eine unveränderte Identität eine bereits sicher gespeicherte Inhaltsklassifikation, statt dieselbe Nichtkandidaten-Datei fortlaufend neu zu analysieren,
7. unterscheidet anhand des tatsächlichen ZIP-Inhalts und nicht anhand von Dateiname oder Endung zwischen Patch-Paket, Result Bundle und sonstiger Datei,
8. liest bei Patch-Kandidaten die Root-`patch.json` streng genug, um `repo_id`, Base-Commit und Fingerprint zu bestimmen,
9. verwirft beim manuellen Ursprung fremde `repo_id`; beim automatischen Ursprung löst sie die Manifest-ID über die Registry auf und akzeptiert das Paket nur, wenn dessen physischer Elternordner dem konfigurierten Exchange genau dieses Ziels entspricht,
10. prüft unter der verbindlichen Registry-/Repository-Lock-Reihenfolge, ob Base-Commit, Fingerprint und Fingerprint-Algorithmus zum jeweiligen Repository-Kontext passen,
11. berücksichtigt beim manuellen Ursprung sowohl noch nie gestartete als auch mit `failed` abgeschlossene Identitäten; beim automatischen Ursprung ausschließlich noch nie gestartete Identitäten; `attempted` und `succeeded` sind in beiden Fällen ausgeschlossen,
12. bildet erst danach die Menge der vollständig passenden, repositoryzulässigen und replayzulässigen Kandidaten und wählt den höchsten `mtime_ns`.

Der persistente Exchange-Dateistatus darf für unveränderte Dateien die Inhaltsklasse und bei Patch-Kandidaten die geprüften Manifest-Auswahldaten zwischenspeichern. Ein gültiger Patch-Kandidat, der lediglich zum derzeitigen Repository-Zustand nicht passt, wird bei einem späteren Scan erneut gegen den dann aktuellen Zustand geprüft. Dauerhaft inhaltsbedingt ungültige Pakete, Result Bundles und sonstige Nichtkandidaten müssen dagegen nicht erneut vollständig analysiert werden.

`mtime_ns` ist ausschließlich die Rangfolge unter bereits vollständig validierten, repositoryzulässigen, state-kompatiblen und replayzulässigen Kandidaten. Ein neueres fremdes, state-inkompatibles oder bereits erfolgreich verarbeitetes Paket blockiert deshalb keinen älteren zulässigen Kandidaten. Teilen mehrere zulässige Kandidaten exakt denselben höchsten `mtime_ns`, entscheidet der lexikografisch kleinste Unicode-NFC-normalisierte Dateiname; sind auch die normalisierten Namen gleich, entscheidet der unveränderte Dateiname; bei gleichem Namen in unterschiedlichen Exchange-Verzeichnissen entscheidet zuletzt der vollständige Pfadstring deterministisch. Die Auswahl hängt niemals von der Reihenfolge von `os.scandir()` ab. Der Dateiname ist keine Repository- oder State-Bindung und wird ausschließlich für diesen Gleichstand verwendet.

Kann eine einzelne reguläre Exchange-Datei während eines Scans nicht stabil oder nicht sicher gelesen werden, wird ausschließlich dieser Eintrag für den aktuellen Scan ignoriert. Ein solcher Einzelfehler darf die Klassifikation anderer Dateien und eines unabhängig lesbaren passenden Patch-Pakets nicht verhindern. Der Fehler „cannot scan exchange directory“ bleibt einem tatsächlichen Fehler beim Auflisten des konfigurierten Verzeichnisses vorbehalten.

Auf virtuellen oder gemeinsam eingebundenen Dateisystemen dürfen Pfad- und Deskriptoransicht trotz unveränderter Datei keine vergleichbare Inode-Identität liefern. Ausschließlich für Exchange-Dateien darf die stabile Aufnahme in diesem Fall auf übereinstimmenden regulären Dateityp, Größe und Änderungszeit zurückfallen. Der vollständige SHA-256 bleibt Bestandteil der Identität; ein ausgewähltes Paket wird vor Materialisierung und unmittelbar vor der ersten Mutation erneut geöffnet und gegen denselben vollständigen Hash geprüft. Andere PatchHarbor-Vertrauensgrenzen verwenden weiterhin die strikte physische Dateidentität.

Die Zustandsprüfung während der Auswahl verwendet dieselbe gesperrte und konsistente Kontextaufnahme wie `patchharbor context`. Beim manuellen Ursprung wird nur das aktuelle Repository aufgenommen. Beim automatischen Ursprung dürfen Repositorys nur lesend und nacheinander gesperrt werden. Nach der Kandidatenentscheidung wird für den eigentlichen Apply-Auftrag die vollständige Sperr-, Preflight- und Revalidierungsfolge erneut durchlaufen.

Result Bundles werden an ihrem eigenen Marker erkannt und niemals als Patch ausgeführt. Andere ZIP-Dateien, direkte Skripte, alte Shell-Patch-ZIPs und beliebige sonstige Dateien sind keine Kandidaten für den sicheren Apply-Pfad.

Gibt es keinen passenden Kandidaten, endet der Auftrag ohne Mutation mit einem klaren Fehler. Ein manueller parameterloser Apply darf eine Identität im Zustand `failed` nur dann erneut öffnen, wenn Repository-ID, Base-Commit, Zustands-Fingerprint, Paketvalidierung und Revalidierung weiterhin vollständig passen. Unmittelbar vor der ersten Mutation wechselt diese Identität atomar zurück auf `attempted`; nach dem tatsächlichen Ausführungsergebnis wird sie als `failed` oder `succeeded` abgeschlossen.

Erfolgreiche Patch-Pakete sind gegen Replay geschützt. Ein fehlgeschlagener Patch kann durch einen bewussten manuellen Apply erneut versucht werden, solange Repository-Bindung und Patch-Zustand weiterhin exakt passen. Der Watcher wiederholt fehlgeschlagene Pakete nicht automatisch in einer Endlosschleife.

Ein explizites `patchharbor apply PATCH_ZIP` übersteuert die parameterlose Auswahl. Es darf unabhängig vom aktuellen Arbeitsverzeichnis das über seine `repo_id` bestimmte registrierte Repository auflösen und behält sämtliche Paket-, State-, Pfad- und Revalidierungsprüfungen. Es ist kein öffentlicher `--retry-failed`-Schalter erforderlich, weil der normale parameterlose manuelle Aufruf bereits die bewusste Benutzeraktion darstellt. Ein Dry-Run verändert keinen Replay-Status.

Die explizit ausgewählte Datei wird vor ihrer Ausführung nicht archiviert. Die optionale vorgeschaltete Exchange-Archivierung darf ausschließlich nachgewiesen überholte Bundles aus dem jeweiligen Repository-Scope verschieben; sie löscht keine Bundles. Wird unter demselben Pfad später anderer Inhalt abgelegt, entsteht wegen des neuen SHA-256 eine neue Dateidentität.

### 16.2.1 Nachweisbasierte Exchange-Archivierung

Bei gemeinsamen Exchange-Verzeichnissen wird jedes validierte Bundle seinem
Repository zugeordnet. Dessen `archive_directory` entscheidet, ob und in welchen
direkten Unterordner es verschoben werden darf. Ein deaktiviertes Archiv eines
Repositorys deaktiviert nicht andere; der Archivname eines anderen Repositorys
darf nicht übernommen werden. Geteilte oder unterschiedliche Archivnamen sind
zulässig. Frische Config-/Identitätsprüfung unmittelbar vor dem Verschieben
bleibt Pflicht; kein Scan-Cache ersetzt diese Prüfung.


Der Standardordner `PatchHarbor-Archive` ist ein direktes Kind des konfigurierten
Exchange-Ordners und wird beim normalen Scan bei Bedarf angelegt. Es gibt keinen
zweiten frei wählbaren Archivpfad. Ein führender Punkt im konfigurierten Namen
verwendet normale Linux-Semantik; unter Windows wird kein Hidden-Attribut gesetzt.
Ein leerer `archive_directory`-Wert deaktiviert die gesamte Wartung einschließlich
Verzeichniserzeugung. Bereits archivierte Dateien bleiben erhalten.

Die Archivierung ist rein nachweisbasiert. Alter, Dateiname, `mtime_ns`, `ctime`
und eine bloße Zustandsabweichung sind keine Entbehrlichkeitsbeweise. Nur vollständig
validierte PatchHarbor-Bundles mit eindeutiger registrierter Repository-ID dürfen
betrachtet werden. Ein Fehler, eine fehlende Historie, inkonsistente Metadaten oder
ein konkurrierender Zustandswechsel bedeutet immer: Datei unverändert liegen lassen.

Der vorhandene Exchange-State verwendet Format 4 (Formate 1–3 bleiben lesbar): Ein `succeeded`-Eintrag
kann zusätzlich einen vollständigen `completed_commit` enthalten. Dieser wird nach
dem tatsächlichen erfolgreichen Entrypoint unter dem Repository-Lock ermittelt,
aber nur bei einem neuen, sauberen und nachgewiesen vom Base-Commit abstammenden
HEAD gespeichert. Fehlt der Beweis, bleibt der Wert `null`; Erfolg allein ist kein
Commit-Beleg. Alte Formate 1/2 bleiben lesbar, liefern keinen nachträglich erfundenen
Abschlusscommit und migrieren erst beim Schreiben. Ein neuer Versuch löscht einen
alten Abschlussbeleg. Es wird kein zweites Consumption-Journal angelegt.

Für ein Patch-Paket müssen exakter Pfad und vollständiger SHA-256, validiertes
Manifest und Replay-Eintrag übereinstimmen. Der Status muss `succeeded` sein,
der Base-Commit ein echter Vorfahr des bestätigten Abschlusscommits und dieser
Abschlusscommit gleich dem aktuellen sauberen HEAD oder dessen Vorfahr. Der
Nachweis bezieht sich ausschließlich auf dieselbe registrierte Repository-Instanz.
Auch explizite Pakete direkt im Exchange-Ordner können nach ihrer Ausführung einen
solchen Eintrag erzeugen; die explizite Retry-Semantik bleibt unverändert.

Für Result Bundles sind vollständige, geschlossene Manifest-/Kontext-/Run-Schemas,
ein erfolgreicher abgeschlossener Lauf, konsistente vollständige Bindungen, leerer
staged-/unstaged-Diff und keine untracked Dateien erforderlich. Alle enthaltenen
Base-Dateien werden nach Größe, Git-Blob-Hash und Modus geprüft; die vollständige
Inventarliste muss exakt dem tatsächlichen Git-Baum entsprechen. Unerwartete
ZIP-Inhalte, widersprüchliche Begleitdaten oder fehlende Dateien verhindern eine
Archivierung. Der gespeicherte Commit muss echter Vorfahr des aktuellen sauberen
HEAD sein. Aktuelle, dirty, fehlgeschlagene oder unklare Result Bundles bleiben.

Git-Prüfungen verwenden vollständige Objekt-IDs und unveränderte Originalhistorie;
Shallow-Repositories, Grafts und Replacement-Refs werden konservativ abgelehnt.
Fehlende Git-Objekte oder Git-Fehler erlauben niemals einen Fallback auf Vermutungen.

Beim manuellen parameterlosen Apply und beim manuellen Bundle-Bau gilt der Scope
des aktuellen registrierten Repositorys. Bei explizitem Apply gilt die Paket-ID,
wobei die ausgewählte Datei von der Wartung ausgeschlossen ist. Der Watcher bleibt
repositoryübergreifend. Dry-Run archiviert nichts. Der vorhandene flache Scan
betrachtet den Archiv-Unterordner nicht rekursiv als aktive Paketquelle.

Die Zielverzeichnisse werden physisch geprüft, gegen Symlinks/Junctions geschützt,
mit Dateisystem-Handles gepinnt und unmittelbar vor Mutation revalidiert. Unter
den vorhandenen Repository-/Registry-Locks werden Konfiguration, Zuordnung,
aktueller Zustand und Consumption-Beleg erneut geprüft; nach dem letzten vollen
Dateihash folgt eine weitere Prüfung. Belegte/beschädigte/beschäftigte Zustände
bleiben unangetastet. Der Move nutzt ausschließlich No-Replace-Rename (Linux:
`renameat2(RENAME_NOREPLACE)`, Windows: nicht überschreibendes Rename). Bei
Namenskollisionen wird ein eindeutiger Alternativname verwendet. Ist eine sichere
Operation nicht verfügbar oder schlägt sie fehl, bleibt die Quelle erhalten.
Es gibt keinen Copy-/Unlink-Fallback, keine überschriebenen Zieldateien und keine
endgültig gelöschten Bundles. Replay-Belege werden durch Archivierung nicht gelöscht.

Die Wartung gruppiert vollständig validierte Kandidaten innerhalb eines Scans
nach Repository-ID. Ein konsistenter Anfangssnapshot wird je Repository geteilt;
rein negative Entscheidungen (aktuelles Result oder fehlender Abschlussbeleg)
benötigen keine Historienabfrage. Vor **jedem** Verschieben wird nach dem letzten
Datei-Hash unter den bestehenden Locks ein frischer vollständiger konsistenter
Repository-Snapshot erfasst. Registrierung, Konfiguration, Replay-Beleg und
Originalhistorie werden dabei erneut geprüft. Diese endgültige Freigabe darf
weder aus dem Anfangssnapshot noch aus einem Cache übernommen werden. Es gibt
keinen scanübergreifenden Cache für Archivierungsentscheidungen.

Funktionale CLI-Testhelfer haben standardmäßig keine interne
`subprocess.run`-Zeitgrenze. Ein expliziter Test einer Prozess-/Timeout-Semantik
kann weiterhin eine Grenze angeben; solche Produkttests bleiben unverändert.
Das Abschalten von pytest-timeout allein deaktiviert keine separate
Subprozess-Zeitgrenze. Termux-Entrypoints verwenden weder künstliche Einzeltest-
noch Gesamtsuite-Timeouts; Core-Standard 10.800 Sekunden und CI-/Release-Grenzen
bleiben unverändert.

### 16.3 Sicher aufgelöstes Repository

Ein Repository gilt erst dann als sicher aufgelöst, wenn:

1. `patch.json` soweit gültig gelesen wurde, dass `repo_id` verfügbar ist,
2. unter dem globalen Registry-Lock genau eine Zuordnung gefunden wurde,
3. der kanonische Pfad existiert,
4. der Pfad weiterhin ein gültiges Git-Repository ist,
5. `.patchharbor` ein reguläres lokales Verzeichnis ist,
6. `.patchharbor/id` exakt dieselbe ID enthält,
7. kein Pfad unter `.patchharbor/` getrackt ist,
8. die exklusive Repository-Sperre in der verbindlichen Lock-Reihenfolge erworben wurde,
9. Registry-Zuordnung, Pfad und lokale ID unter beiden Locks erneut übereinstimmen.

Ab diesem Zeitpunkt versucht PatchHarbor am Ende des Auftrags stets, ein Result Bundle zu erzeugen.

Kann das Repository vorher nicht sicher aufgelöst werden, entsteht kein Repository-Snapshot.

### 16.4 Validierungs- und Ausführungsreihenfolge

`patchharbor apply [PATCH_ZIP]` führt mindestens aus:

1. Bei fehlendem `PATCH_ZIP` den manuellen oder automatischen Auswahlkontext bestimmen und den neuesten zulässigen Kandidaten nach Abschnitt 16.2 auswählen; andernfalls ausschließlich den expliziten Pfad verwenden.
2. Eingabedatei stabil und vollständig lesbar öffnen.
3. Tatsächliches ZIP-Format prüfen.
4. Archivstruktur, Eintragstypen, Pfade und Ressourcenlimits vollständig prüfen.
5. `patch.json` im ZIP-Wurzelverzeichnis finden.
6. Striktes JSON-Schema, Paketmarker, Fingerprint-Algorithmus und Formatversion prüfen.
7. `repo_id` unter dem globalen Registry-Lock eindeutig auflösen.
8. Ausgabeordner bestimmen: explizites `--output-dir`, andernfalls den Exchange-Ordner; gegen alle registrierten Repository-Pfade prüfen und dort einen temporären Ausgabepfad reservieren.
9. Zielpfad, Git-Repository, reserviertes lokales Verzeichnis und ID-Datei prüfen.
10. Exklusive Repository-Sperre erwerben, Zuordnung unter beiden Locks erneut validieren und danach den Registry-Lock freigeben.
11. Unterstützte Repository- und Pfadgrenzen aus Abschnitt 14 prüfen.
12. Aktuellen vollständigen Base-Commit bestimmen und mit dem Manifest vergleichen.
13. Aktuellen Fingerprint bestimmen und mit dem Manifest vergleichen.
14. Entrypoint und alle Nutzdateipfade vollständig prüfen.
15. Entrypoint in einem privaten Temp-Verzeichnis bereitstellen und den Pflichtmarker prüfen.
16. Interpreter bestimmen und seine Verfügbarkeit prüfen.
17. Alle Nutzdateiinhalte vollständig in Speicher oder ein privates auftragsbezogenes Temp-Verzeichnis außerhalb des Repositorys aufnehmen.
18. Vor der ersten Repository-Schreiboperation Base-Commit, Fingerprint, Registry-Zuordnung, lokale ID, alle Zielpfade und deren relevante Eltern erneut prüfen.
19. Beim Dry-Run keine Dateidentität konsumieren, keine Nutzdatei schreiben und keinen Entrypoint starten.
20. Bei einem im Exchange verfolgten Nicht-Dry-Run-Auftrag die Identität mit vollständiger `attempt_run_id` atomar auf `attempted` setzen; nur ein manueller Ursprung darf dabei `failed` erneut öffnen; bei Fehler ohne Mutation abbrechen.
21. Beim echten Apply Nutzdateien einzeln atomar schreiben oder ersetzen.
22. Entrypoint mit Repository-Wurzel als CWD ausführen.
23. stdout und stderr vollständig in den Run-Log aufnehmen.
24. Exit-Code, Timeout, Strg+C oder Tool-Fehler als primäres Ergebnis bestimmen; den terminalen Replay-Status noch nicht vor der Result-Veröffentlichung abschließen.
25. Konsistenten aktuellen Repository-Snapshot aufnehmen.
26. Result Bundle in der reservierten temporären Datei im endgültigen Ausgabeordner erstellen und prüfen; bei beweisbarem Erfolg die vollständige Result-SHA im zugehörigen lokalen Attempt verankern, danach das Bundle atomar veröffentlichen.
27. Den Replay-Status atomar aus dem tatsächlichen Ausführungsergebnis als `failed` oder `succeeded` abschließen und Ergebnisse nach Abschnitt 18 zusammenführen. Scheitert nur die terminale Persistenz, bleibt ein bereits veröffentlichtes Erfolgs-Result unverändert erhalten; der CLI-Auftrag meldet diesen Persistenzfehler.
28. Repository-Sperre und alle temporären Ressourcen freigeben.

### 16.4.1 Nachweisbasierte Recovery eines unterbrochenen Attempts

Die bestehende Replay-Persistenz Format 4 ergänzt `attempt_run_id` (vollständige
UUID des Runs oder `null`) und `result_sha256` (vollständige kleingeschriebene
SHA-256 des bestätigten Result-ZIPs oder `null`). Formate 1, 2 und 3 bleiben strikt
lesbar; Lesen schreibt nicht. Der nächste Schreibvorgang migriert atomar. Fehlende
Legacy-Beweise werden niemals ergänzt, geraten oder aus Dateinamen hergeleitet.
Die neue repositorylokale Konfiguration verwendet unabhängig davon ihr geschlossenes Format 1; Replay-Formatversionen sind kein Config-Migrationspfad.

Die Patch-SHA entsteht aus denselben stabil eingelesenen ZIP-Bytes wie Parser,
Entrypoint und Nutzdaten, nicht aus einem später separat geöffneten Download.
Neue Apply-Result-Manifeste enthalten bei bekannter Paket-SHA das optionale Paar
`patch_sha256` und `completed_commit`. `completed_commit` ist nur bei tatsächlich
erfolgreichem Entrypoint, sauberem konsistentem Result-Snapshot und bestätigtem
Vorwärts-Commit gesetzt, sonst `null`. Die vorhandenen `run_id`, `repo_id`,
`expected_*`- und `actual_*`-Felder vervollständigen die Bindung. Reine manuelle
Bundles erfinden keine Paketzuordnung. `patch.json` bleibt unverändert.

Der Publisher schreibt und prüft zuerst das temporäre Result-ZIP. Vor dessen
atomarer Veröffentlichung wird die komplette Result-SHA unter dem vorhandenen
Exchange-State-Lock im exakt passenden aktiven Attempt gespeichert. Er prüft die
Datei danach erneut. Erst nach dem Veröffentlichungsversuch wird der terminale
Replay-Status geschrieben. Bei einem Fehler nur dieses letzten Schreibschritts
bleibt das erfolgreiche ZIP bytegleich erhalten. Keine zweite fehlerhafte Ausgabe
überschreibt den bereits veröffentlichten Erfolgsbeleg. Synchronisierung bleibt
plattformabhängig best-effort; es gibt keine absolute Stromausfallsicherheitszusage.

Recovery erfolgt vor Archivierung bei nicht-trockenen Exchange-Scans. Manuelles
Apply und `bundle` bleiben auf ihr Repository begrenzt, explizites Apply auf das
Paket-Repository, der Watcher bleibt global. Die Funktion ist unabhängig vom
Archivierungs-Schalter. Dry-Run repariert keine Einträge. Es gibt keinen neuen
CLI-Schalter, kein zweites Journal und keinen parallelen Auswahlalgorithmus.

Eine Reparatur `attempted -> succeeded + completed_commit` erfordert gleichzeitig:

- die ursprüngliche verfolgte Patch-Dateiidentität (Pfad und vollständige SHA),
- eine im aktiven Exchange liegende gültige Result-Datei mit exakt der vorher
  lokal gespeicherten Result-SHA; Umbenennen bei identischen Bytes ist zulässig,
- exakt übereinstimmende Patch-SHA, Attempt-/Run-ID, `repo_id`, erwarteten Base-Commit,
  ursprünglichen State-Fingerprint und Fingerprint-Algorithmus,
- konsistente erfolgreiche Manifest-/Run-/Context-Daten ohne Dry-Run oder Fehler,
- vollständige unveränderte Snapshot-Blobs des echten `completed_commit`,
- sauberen aktuellen Repository-Zustand, vollständige Originalhistorie ohne
  shallow/graft/replace und `base -> completed_commit -> HEAD` mit `base != completed_commit`,
- den tatsächlich erworbenen exklusiven Repository-Lock, erneute Registry-,
  Konfigurations-, Datei-, Git- und State-Prüfung und atomaren Compare-and-swap
  unter dem vorhandenen Replay-State-Lock; bei Änderung keine Reparatur.

Eine Hash-Korrelation ersetzt keine digitale Signatur. Die Vertrauensbasis ist
wie bisher die lokale Registry/State-Datei; ein Angreifer mit Schreibzugriff auf
alle Belege einschließlich dieser Persistenz ist dadurch nicht authentifiziert.
Im Exchange abgelegte fremde oder editierte ZIPs allein genügen niemals als Beweis.

Ein lebender Lock-Halter wird nicht als Crash interpretiert. Ein fehlender
Screen-Socket, geringe CPU-Last oder Dateialter sind keine Recovery-Auslöser.
PatchHarbor löscht keinen Lock und setzt niemals automatisch Working-Tree- oder
Index-Inhalte zurück. Bei Dirty-Zustand, fehlendem Result oder unklaren Beweisen
bleiben Dateien und `attempted` erhalten, auch wenn bereits ein Commit existiert.
Ein Abbruch zwischen gepinnter Result-SHA und Veröffentlichung reicht nicht zur
Reparatur. Ein erfolgreich veröffentlichtes, aber noch nicht terminal gespeichertes
Result kann dagegen beim nächsten freien Scan rekonstruiert werden.

Result-Belege für noch offene Attempts bleiben vor Archivierung geschützt. Erst
nach nachgewiesener Reparatur greifen die normalen Archivierungsregeln. Die Suche
ist flach: keine rekursive Suche im Archiv, keine beliebigen externen Result-Pfade.
Ein Result aus einem expliziten anderen Ausgabeordner muss für diesen Scan wieder
bytegleich im aktiven Exchange liegen. Ohne ursprüngliche Patch-Dateiidentität
oder bei alten Runs ohne lokal verankerte Hashes bleibt die Reparatur aus.

### 16.5 Harte Ablehnung

PatchHarbor lehnt vor der ersten Repository-Änderung unter anderem ab:

- fehlende oder ungültige lokale Konfiguration auch bei explizitem Patch-/Ausgabeauftrag; ein explizites Ausgabeziel übergeht nur einen unset/unavailable Exchange-Pfad,
- beim manuellen parameterlosen Apply ein nicht eindeutig registriertes aktuelles Repository,
- keinen passenden Kandidaten im jeweiligen manuellen oder automatischen Repository-Scope,
- unbekannte oder widersprüchliche Repository-ID,
- fehlende oder kopierte lokale ID,
- ungültige Registry-Zuordnung,
- Base-Commit-Mismatch,
- Fingerprint-Mismatch,
- geänderten Zustand zwischen erster Prüfung und Mutationsgrenze,
- nicht unterstützten Git- oder Pfadzustand,
- ungültige `patch.json`,
- unsichere ZIP-Einträge,
- ungültigen oder fehlenden Entrypoint,
- fehlenden Pflichtmarker,
- nicht unterstützten oder fehlenden Interpreter,
- unzulässigen Exchange- oder Result-Bundle-Ausgabeordner,
- nicht sicher vorbereitbare Nutzdatei.

Nach sicherer Repository-Auflösung versucht PatchHarbor auch bei einer solchen späteren Ablehnung ein Result Bundle des unveränderten Repository-Zustands zu erzeugen.

### 16.6 Konsistenter Snapshot trotz äußerer Änderungen

Vor der Snapshot-Aufnahme wird der aktuelle Kontext bestimmt. Während der Aufnahme werden genau die Daten gelesen, die in das Result Bundle geschrieben werden.

Nach der Aufnahme wird der aktuelle Kontext erneut bestimmt.

Nur wenn Vorzustand, aufgenommene Daten und Nachzustand konsistent sind, wird das temporäre Result Bundle veröffentlicht.

Ändert ein fremder Prozess das Repository während der Aufnahme, wird die temporäre Bundle-Datei entfernt und die Bundle-Erzeugung schlägt klar fehl.

Da die temporäre Bundle-Datei außerhalb aller registrierten Repositories liegt, verändert die Snapshot-Erzeugung den aufzunehmenden Repository-Zustand nicht.

## 17. Dry-Run

```bash
patchharbor apply --dry-run PATCH_ZIP
```

### 17.1 Der Dry-Run führt aus

- vollständige ZIP- und Ressourcenvalidierung,
- `patch.json`-Validierung,
- Repository-Auflösung,
- lokale ID-Prüfung,
- exklusive Sperre,
- Base-Commit-Vergleich,
- Fingerprint-Berechnung und Vergleich,
- Entrypoint- und Nutzdateipfadprüfung,
- Interpreter-Verfügbarkeitsprüfung, soweit ohne Prozessstart möglich,
- Erzeugung eines Result Bundles des unveränderten Repository-Zustands.

### 17.2 Der Dry-Run führt nicht aus

- keine Nutzdatei wird geschrieben,
- kein Entrypoint wird gestartet,
- kein Kindprozess wird erzeugt,
- keine Repository-Datei wird verändert,
- kein Test wird gestartet,
- kein Commit wird erzeugt,
- keine Exchange-Datei wird als verarbeitet markiert.

Das Result Bundle kennzeichnet:

```json
{
  "dry_run": true,
  "entrypoint_started": false,
  "execution_present": false
}
```

---

## 18. Auftragsergebnis und Result-Bundle-Fehler

PatchHarbor behandelt zwei getrennte Ergebnisse:

1. das primäre Auftragsergebnis,
2. das Ergebnis der Result-Bundle-Erzeugung.

### 18.1 Grundregel

Ein Fehler bei der Result-Bundle-Erzeugung überschreibt einen bereits vorhandenen primären Fehler nicht. Er überschreibt nur einen ansonsten erfolgreichen Auftrag.

| Primärer Auftrag | Result Bundle | Prozess-Exit-Code |
|---|---|---:|
| erfolgreich | erfolgreich | `0` |
| erfolgreich | fehlgeschlagen | `11` |
| fehlgeschlagen | erfolgreich | primärer Fehlercode |
| fehlgeschlagen | ebenfalls fehlgeschlagen | primärer Fehlercode |

Beispiele:

- Entrypoint Exit `0`, Bundle fehlgeschlagen: PatchHarbor Exit `11`.
- Entrypoint Exit `7`, Bundle erfolgreich: PatchHarbor Exit `7`.
- Entrypoint Exit `7`, Bundle ebenfalls fehlgeschlagen: PatchHarbor Exit `7`, Bundle-Fehler zusätzlich dokumentiert.
- Timeout plus Bundle-Fehler: PatchHarbor Exit `124`.
- Strg+C plus Bundle-Fehler: PatchHarbor Exit `130`.

### 18.2 Priorität des primären Ergebnisses

1. Benutzerabbruch: `130`.
2. Timeout: `124`.
3. normal beendeter Entrypoint: dessen exakter Exit-Code.
4. Tool-Fehler vor Entrypoint-Start: zugehöriger Tool-Exit-Code.
5. interner PatchHarbor-Fehler während der Prozesssteuerung: zugehöriger Tool-Exit-Code.

### 18.3 Strukturierter Run-Bericht

Jeder Auftrag besitzt eine UUID-v4-`run_id`.

Soweit ein Result Bundle erzeugt werden kann, liegt der Bericht unter:

```text
logs/run.json
```

Beispiel:

```json
{
  "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
  "operation": "apply",
  "dry_run": false,
  "repository_resolved": true,
  "primary_result": {
    "kind": "entrypoint_exit",
    "success": false,
    "patchharbor_error_code": null,
    "entrypoint_started": true,
    "entrypoint_exit_code": 7,
    "timed_out": false,
    "interrupted": false
  },
  "result_bundle": {
    "attempted": true,
    "status": "created",
    "error": null
  },
  "process_exit_code": 7
}
```

Mögliche `primary_result.kind`-Werte:

```text
success
dry_run_success
validation_error
repository_error
state_mismatch
repository_busy
entrypoint_exit
timeout
interrupted
execution_error
```

Mögliche `result_bundle.status`-Werte:

```text
created
failed
not_attempted
```

`not_attempted` ist nur zulässig, wenn kein Repository sicher aufgelöst werden konnte.

### 18.4 Maschinenlesbare Apply-Ausgabe

```bash
patchharbor apply --json PATCH_ZIP
```

Die Ausgabe folgt exakt dem gemeinsamen Vertrag aus Abschnitt 5.2.

Insbesondere:

- enthält stdout genau ein Abschlussobjekt,
- enthält `result.primary_result` die primäre Ergebnisart und den Entrypoint-Zustand,
- enthält `result.result_bundle` Versuch, Status, Pfad und gegebenenfalls Notfalldiagnose,
- bleibt `error` bei einem normalen von null verschiedenen Entrypoint-Exit `null`,
- enthält `error` bei einem PatchHarbor-Tool-Fehler den zugehörigen Tool-Code,
- entspricht `process_exit_code` exakt dem tatsächlich zurückgegebenen Exit-Code.

`logs/run.json` ist der ausführliche persistierte Bericht. Das stdout-Abschlussobjekt ist die kompakte maschinenlesbare Aufrufantwort und darf nicht aus TUI-Text rekonstruiert werden.

### 18.5 Atomare Bundle-Veröffentlichung und Notfallrettung

Ein Result Bundle wird in einem vorab reservierten endgültigen Ausgabeordner erzeugt. Ohne `--output-dir` ist das der konfigurierte Exchange-Ordner; mit `--output-dir` ist es der explizit validierte Zielordner.

Die temporäre ZIP-Datei des Result Bundles wird ausdrücklich nicht im System-Temp-Verzeichnis erzeugt. Sie wird unter einem nicht endgültigen Namen direkt im kanonischen endgültigen Ausgabeordner angelegt, beispielsweise:

```text
.<finaler-name>.tmp-<zufall>
```

Verbindlicher Ablauf:

1. Ausgabeordner physisch kanonisieren und gegen alle registrierten Repository-Pfade prüfen.
2. Temporären Dateinamen im selben Ausgabeordner reservieren.
3. Bundle vollständig schreiben und schließen.
4. ZIP-Struktur und Pflichtdateien prüfen.
5. Temporäre Datei flushen und, soweit plattformgerecht möglich, synchronisieren.
6. Zielpfad unmittelbar vor Veröffentlichung revalidieren.
7. Über `os.replace()` atomar auf den endgültigen Namen veröffentlichen.

Bei fehlgeschlagener Bundle-Erzeugung:

- wird die temporäre Bundle-Datei bestmöglich entfernt,
- bleibt keine unvollständige Datei unter dem endgültigen Bundle-Namen liegen,
- werden `execution.log` und `run.json` soweit möglich in einem privaten Notfallverzeichnis unter dem PatchHarbor-Zustandsverzeichnis gesichert,
- wird der Notfallpfad auf stderr und im äußeren strukturierten Ergebnis ausgegeben,
- wird dieser Rettungspfad niemals selbst als erfolgreiches Result Bundle bezeichnet.

### 18.6 Manueller Bundle-Auftrag

Bei:

```bash
patchharbor bundle [REPOSITORY]
```

ist die Bundle-Erzeugung selbst der primäre Auftrag.

Ohne `--output-dir` wird im konfigurierten Exchange-Ordner veröffentlicht. Fehlt der benötigte Exchange oder ist die lokale Konfiguration ungültig, endet der Bundle-Auftrag klar mit Exit `11`. Ein explizites `--output-dir` übersteuert das Standardziel und erlaubt unset/unavailable Exchange, benötigt aber weiterhin gültige lokale Konfiguration.

Ein Fehler führt zu Exit `11`. Es gibt keinen getrennten vorherigen Skript-Exit-Code.

## 19. PatchHarbor Result Bundle

### 19.1 Zweck

Das PatchHarbor Result Bundle ist die vollständige portable Darstellung des aktuellen lokalen Repository-Zustands ohne `.git`-Historie.

Es dient:

- dem Upload in einen Chat,
- der Erzeugung des nächsten Patches,
- der Diagnose eines erfolgreichen oder fehlgeschlagenen Auftrags,
- der Übergabe an Repo Assist,
- der unabhängigen Betrachtung des Repository-Zustands.

Ein bloßer Commit-Hash reicht nicht aus, weil der Empfänger den Commit möglicherweise nicht besitzt.

### 19.2 Automatische und manuelle Erzeugung

Manuell:

```bash
patchharbor bundle [REPOSITORY]
```

Ohne `--output-dir` wird das Result Bundle in `exchange_directory` veröffentlicht.

Automatisch versucht `patchharbor apply` nach jedem Auftrag ein Result Bundle zu erzeugen, sobald das Ziel-Repository sicher aufgelöst und gesperrt wurde. Ohne `--output-dir` verwendet auch dieser Versuch `exchange_directory`.

Das gilt auch bei:

- Base-Commit-Mismatch,
- Fingerprint-Mismatch,
- ungültigem Entrypoint nach sicherer Auflösung,
- Entrypoint-Fehler,
- fehlgeschlagenen Projekttests im Entrypoint,
- Timeout,
- Strg+C,
- internem Fehler nach sicherer Auflösung.

PatchHarbor verarbeitet ein von ihm veröffentlichtes Result Bundle im selben Exchange-Ordner niemals als Patch-Paket.

### 19.3 Vollständigkeitsregel

Das Result Bundle enthält immer:

- den vollständigen aktuellen Base-Commit als Dateien,
- staged Änderungen,
- unstaged Änderungen,
- alle nicht ignorierten untracked regulären Dateien,
- Repository-Kontext und Fingerprint,
- Run-Metadaten,
- vollständigen Entrypoint-Output, sofern eine Ausführung stattgefunden hat,
- Warnings und Tool-Fehler.

Es gibt keinen reduzierten Standardmodus, der nur den Commit-Hash enthält.

### 19.4 Struktur

```text
<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip
├── manifest.json
├── context.json
├── CHAT_INSTRUCTIONS.md
├── environment.json
├── base/
│   └── ... alle regulären Dateien des aktuellen Base-Commits ...
├── changes/
│   ├── staged.patch
│   └── unstaged.patch
├── untracked/
│   └── ... nicht ignorierte untracked reguläre Dateien ...
└── logs/
    ├── execution.log
    └── run.json
```

Der Dateiname beginnt mit dem Namen des Repository-Wurzelverzeichnisses, verwendet danach das Schlüsselwort `Result`, die UTC-Uhrzeit `HHMMSS`, Monat und Tag `MMDD` ohne Jahr sowie die ersten sechs Zeichen der vollständigen Run-ID ohne `…`. Das entsprechende Chat-Patch-Schema verwendet an derselben Position `Patch` und eine Paket-UUID. Der Dateiname ist keine Sicherheits- oder Klassifikationsinformation. An beide Basisschemata wird das konfigurierte `bundle_suffix` angehängt, beispielsweise `.zip.txt`; dies gilt auch für automatische Fehler-, Dry-Run- und Watcher-Resultate sowie explizite Ausgabeziele. Die Konfigurations- und Ausgabeschichten lesen den Wert einmal bei der Zielvorbereitung und verwenden denselben Wert für Dateiname und Kontextmetadaten.

`execution.log` fehlt bei einem manuellen Bundle oder Dry-Run ohne Entrypoint-Ausführung.

### 19.5 `manifest.json`

Verkürztes Beispiel:

```json
{
  "marker": "patch-harbor-result-bundle",
  "format_version": 1,
  "created_at": "2026-08-25T06:00:00Z",
  "run_id": "b592be12-55f2-49d7-9699-2435bbcd7935",
  "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
  "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
  "state_fingerprint": "a1b2c3d4e5f67890",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "dirty": true,
  "dry_run": false,
  "execution_present": true,
  "primary_result": "entrypoint_exit",
  "result_bundle_status": "created"
}
```

Das vollständige Manifest enthält zusätzlich zwei nach UTF-8-Pfadbytes sortierte Arrays:

- `base_entries` mit `path`, `git_mode`, `object_id` und `size`,
- `untracked_entries` mit `path`, `mode`, `size` und `sha256`.

Diese Metadaten sind die plattformunabhängige Quelle für Dateimodi. Die ZIP-Einträge tragen zusätzlich passende reguläre Dateirechte, soweit das ZIP-Format sie abbilden kann.

Bei `apply` enthält das Manifest außerdem die aus `patch.json` erwarteten und die tatsächlich ermittelten Zustandswerte, sodass ein Mismatch eindeutig nachvollziehbar bleibt. Neue Apply-Resultate mit bekannter Paket-SHA ergänzen gemeinsam `patch_sha256` und `completed_commit` gemäß Abschnitt 16.4.1. Der Abschlusscommit darf `null` sein; beide Felder fehlen in alten Resultaten und manuellen Bundles. Bestehende Resultate ohne diese optionalen Felder bleiben lesbar, liefern aber keinen neuen Recovery-Beleg.

### 19.6 `context.json`

`context.json` enthält den aktuellen Zustand zum Zeitpunkt der konsistenten Snapshot-Aufnahme:

```json
{
  "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
  "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
  "dirty": true,
  "state_fingerprint": "a1b2c3d4e5f67890",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "created_at": "2026-08-25T06:00:00Z",
  "bundle_suffix": ".txt"
}
```

`bundle_suffix` ist zusätzliche optionale Dateinamen-Präsentationsmetadaten,
kein Teil des Repository-Zustands. Ältere Result Bundles ohne dieses Feld gelten
als suffixlos. Der externe Entwicklungs-Chat übernimmt den Wert unverändert für
seinen nächsten Patch-Dateinamen. Er fügt ihn niemals in `patch.json` ein und
verwendet ihn nicht für Fingerprint, Repository-Zuordnung oder Replay. Die
vollständigen Bindungswerte, Result-Marker und Formatversion 1 bleiben erhalten.
Die geschlossene CLI-Antwort von `context --json` bleibt unverändert; bei einer
separaten Kontextübergabe muss die Dateinamenpräferenz zusätzlich genannt werden.

### 19.6a Frische Chat-Anweisungen und Umgebungsdaten

Jede neue Result-Bundle-Veröffentlichung enthält genau eine Root-Datei
`CHAT_INSTRUCTIONS.md` und `environment.json`: manuelles Bundle, Apply-Erfolg,
Fehler, Dry Run, Watcher und explizites Ausgabeziel. Sie werden gemeinsam mit
Snapshot und Logs geschrieben, CRC-geprüft und atomar veröffentlicht. Kein
zusätzlicher CLI-Befehl, keine Sidecar-Datei, kein nachträgliches Umschreiben
alter Bundles. Der tatsächlich aufgelöste Repository-Kontext ist maßgeblich,
nicht CWD eines Watchers oder eines explizit anders gerichteten Apply.

`exchange_directory` und `bundle_suffix` in `environment.json` stammen aus der
lokalen Konfiguration genau dieses Zielrepositorys; `output_directory` ist das
tatsächliche Ausgabeziel und kann davon abweichen. Es sind keine globalen
Benutzereinstellungen. Die ignorierte `.patchharbor/config.json` wird nicht als
Snapshotdatei mitgeliefert. Die Begleitdaten bilden nicht zwingend sämtliche
lokalen Einstellungen ab, insbesondere keinen vollständigen Archivvertrag.

Die statische Root-`CHAT_INSTRUCTIONS.md` des PatchHarbor-Quellprojekts bleibt
fachliche Vorlage. Bei Installation wird genau diese Version aus dem bestehenden
`share/patchharbor`-Datenartefakt geladen, bei Quellbetrieb nur relativ zum
laufenden Core-Modul. Niemals eine gleichnamige Datei aus einem fremden
Zielrepository oder vorherige dynamische Instructions verwenden. Die Vorlage
wird bei jedem Bundle neu gelesen; keine lokale Datei wird dabei überschrieben.
Fehlt sie, schlägt die Bundle-Publikation kontrolliert fehl; bestehende
Primärergebnis-/Notfalldiagnostikregeln gelten unverändert.

Die generierte Anleitung verwendet plattformübergreifend LF-Zeilenenden.
Der Vorlagenloader normalisiert nach strenger UTF-8-Decodierung CRLF und
alleinstehendes CR zu LF. Derselbe zentrale Helfer gilt für explizite
Vorlagen des reinen Renderers `render_chat_handoff`, insbesondere bei externen
Patch-Autoren. Alle übrigen Zeichen, Leerzeilen sowie vorhandene oder fehlende
abschließende Zeilenumbrüche bleiben erhalten. Größe, leere Eingabe und BOM
werden beim Dateiladen weiterhin anhand der ursprünglichen Bytes geprüft;
Normalisierung darf keine zu große Vorlage nachträglich zulässig machen.
Weder Quelldatei noch `base/`-Snapshot, empfangene Patch-Nutzdateien oder
JSON-Feldwerte werden umgeschrieben. Bestehende Bundles und Metadatenformate
bleiben kompatibel; Repository-Bindung und Fingerprint bleiben unverändert.

`environment.json` hat Marker `patch-harbor-environment`, `format_version: 1`
und enthält `captured_at`, `bundle_type`, `bundle_filename`, volle `run_id`,
`repository_name`, `repository_path`, vollständigen `repository_context`,
`exchange_directory`, `output_directory`, `bundle_suffix`, `filename_schemas`,
`filename_timezone: UTC` sowie `runtime`. Die Suffix- und Exchange-Angaben
stammen aus derselben Zielvorbereitung wie der Dateiname und werden revalidiert.
Ein explizites Ausgabeziel bleibt vom konfigurierten Exchange-Pfad getrennt;
fehlende/defekte lokale Konfigurationen werden auch damit nicht umgangen.
Ein gültig nicht gesetzter Exchange und unbekannte Laufzeitangaben sind `null`. `context.json` und `context --json` bleiben
hinsichtlich ihres bisherigen Vertrags unverändert.

`runtime` enthält ausschließlich System, Distributions-ID/-Name/-Version,
Kernel-Release, Architektur, Python-Version/-Implementierung, uv-Version,
konfigurierte Shell mit Quelle und PatchHarbor-Version. Die Probe ist lokal,
ohne Netzwerk, ohne Ausführen einer Shell und ohne vollständige Umgebungs- oder
OS-Dateidumps. Eine optionale `uv --version`-Probe hat zwei Sekunden Timeout;
Fehler/Fehlen erzeugen `null` statt eines Bundle-Fehlers. Diese Probe verändert
nicht den 10.800-Sekunden-Entrypoint-Timeout. OS-Distribution bezeichnet das
laufende Userland (beispielsweise Ubuntu in proot), Kernel gegebenenfalls den
Host. `SHELL`/`COMSPEC` beschreibt nur die konfigurierte Präferenz.
Hostnamen, IP-Adressen, separate Benutzernamen und Seriennummern werden nicht
gesammelt; erforderliche absolute Pfade können einen Benutzernamen enthalten.

Die erzeugte Anleitung enthält alle Umgebungswerte als abgegrenzte JSON-Daten,
passend gequotete lokale POSIX-/PowerShell-Befehle und den vollständigen statischen
Vertrag. Unbekannte Systeme oder unsicher darstellbare Pfade erhalten keine
scheinbar ausführbaren Beispiele. Umgebungswerte sind niemals Sicherheitsinput,
Anweisungen, Repository-Auswahl oder Teil des Fingerprints.

Neue externe Patch-Pakete enthalten dieselben beiden Dokumente im reservierten
Namensraum `PATCHHARBOR_META/`. Für jedes Paket rendert der Chat die statische
Vorlage neu mit dem letzten Zielrechner-Snapshot; er erhält dessen Erfassungszeit,
setzt Paketart und Dateiname passend und erfindet keine Zielrechnerdaten aus
seiner eigenen Laufzeit. Der Core erzeugt keine Patch-Pakete. Alte Pakete ohne
Metadatenpaar bleiben gültig; das geschlossene `patch.json` bleibt Format 1 mit
sieben Feldern. Andere/incomplete reservierte Dateien, reservierte Entrypoints,
BOM, Nicht-UTF-8, mehr als 128 KiB je Datei, ungültiges JSON, doppelte Schlüssel,
Nicht-Objekte, nicht endliche Zahlen und von `patch.json` abweichende Bindungen
werden abgelehnt. Normale ZIP-, Pfad- und Ressourcengrenzen gelten zusätzlich.
Begleitdateien werden weder als Nutzdateien geschrieben noch als Code ausgeführt.
Eine echte Root-`CHAT_INSTRUCTIONS.md` in einem Patch bleibt eine Nutzdatei.
Beim erstmaligen Upgrade eines älteren Runners darf ein nachweislich
kollisionsfreier zustandsgebundener Bootstrap-Patch ausschließlich seine beiden
bytegeprüften, vom alten Runner noch als Nutzdateien materialisierten
Metadateien vor Tests/Commit entfernen. Bestandsdateien sind dabei tabu.

### 19.7 `base/`

`base/` wird unabhängig von Exportattributen direkt aus dem unveränderlichen Git-Baum materialisiert.

Verbindliches Verfahren:

```text
git ls-tree -r -z --full-tree <base_commit>
git cat-file --batch
```

PatchHarbor:

1. liest alle Baumdatensätze als Bytes,
2. akzeptiert ausschließlich reguläre Blob-Einträge mit Modus `100644` oder `100755`,
3. fordert die vollständigen Blob-Inhalte über `git cat-file --batch` an,
4. prüft zurückgegebenen Objekttyp und Größe,
5. schreibt exakt diese unveränderten Blob-Bytes unter `base/<repository-path>`,
6. dokumentiert Pfad, Modus, Objekt-ID und Größe in `manifest.json`.

Dieses Verfahren wertet insbesondere keine Exportattribute oder Ersetzungsanweisungen aus. Eine committed Datei wird nicht aufgrund einer Exportregel ausgelassen oder inhaltlich verändert.

Enthalten sind alle unterstützten, im Base-Commit verwalteten regulären Dateien.

Nicht enthalten sind:

- `.git`,
- frühere Commits,
- Branch- und Tag-Historie,
- lokale Git-Konfiguration,
- das reservierte lokale PatchHarbor-Verzeichnis.

Externe Git-LFS-Objekte werden nicht nachgeladen. Das Bundle enthält den tatsächlich im Git-Commit gespeicherten Blob, beispielsweise gegebenenfalls eine LFS-Zeigerdatei.

### 19.8 `changes/staged.patch`

Die staged Patch-Datei wird unter derselben kontrollierten Git-Umgebung wie der Fingerprint erzeugt:

```bash
git -c color.ui=false -c diff.renames=false diff \
  --cached --binary --full-index --no-renames \
  --no-ext-diff --no-textconv --no-color \
  <base_commit> --
```

Zusätzlich gelten `LC_ALL=C`, `LANG=C`, `GIT_OPTIONAL_LOCKS=0` und ein deaktiviertes externes Diff-Programm.

Die Datei beschreibt die staged Änderungen gegenüber dem festgehaltenen Base-Commit einschließlich binärer Änderungen und Modusänderungen.

### 19.9 `changes/unstaged.patch`

Die unstaged Patch-Datei wird ebenfalls unter der kontrollierten Git-Umgebung erzeugt:

```bash
git -c color.ui=false -c diff.renames=false diff \
  --binary --full-index --no-renames \
  --no-ext-diff --no-textconv --no-color --
```

Die Datei beschreibt die unstaged Änderungen zwischen Index und Working Tree.

Zur Rekonstruktion wird zuerst `staged.patch` und anschließend `unstaged.patch` auf `base/` angewendet.

Die Patch-Dateien dienen der Rekonstruktion und Ansicht. Der Sicherheits-Fingerprint wird ausschließlich nach Abschnitt 14 berechnet.

### 19.10 `untracked/`

`untracked/` enthält alle nicht ignorierten untracked regulären Dateien:

- vollständiger UTF-8-Repository-Pfad,
- vollständiger bytegenauer Inhalt,
- erhaltene Verzeichnisstruktur,
- kanonischer Modus `100644` oder `100755` gemäß Abschnitt 14,
- SHA-256 des Inhalts im Manifest.

Ignorierte Dateien werden nicht aufgenommen. Nicht reguläre Einträge werden nicht dereferenziert und führen zu einem klaren Fehler.

### 19.11 Vollständiger aktueller Snapshot

Die Kombination:

```text
base/
+ changes/staged.patch
+ changes/unstaged.patch
+ untracked/
```

ist der vollständige aktuelle Snapshot innerhalb der definierten Git- und Dateigrenzen.

Ein zweites materialisiertes `snapshot/`-Verzeichnis ist nicht erforderlich und würde dieselben Daten unnötig verdoppeln.

### 19.12 Logs

`logs/execution.log` enthält den vollständigen während der Ausführung beobachteten stdout-/stderr-Strom.

`logs/run.json` enthält mindestens:

- Startzeit,
- Endzeit,
- Laufzeit,
- Operation,
- Patch-Paket-Anzeigename,
- Repository-ID und Pfad,
- erwartete und tatsächliche Zustandswerte,
- Dry-Run-Status,
- Entrypoint,
- Interpreter,
- Timeout,
- Warnings,
- Entrypoint-Exit-Code,
- Tool-Fehler,
- Result-Bundle-Status,
- endgültigen Prozess-Exit-Code.

Zusätzliche Diagnose-, Test- oder Build-Dateien des Zielprojekts werden nicht automatisch gesucht oder eingesammelt. Sie können manuell übertragen oder durch Repo Assist verwaltet werden.

### 19.13 Datenschutz und Secrets

Ein Result Bundle kann vollständigen Quellcode und nicht ignorierte untracked Dateien enthalten.

PatchHarbor:

- nimmt `.git` nicht auf,
- nimmt standardmäßig ignorierte Dateien nicht auf,
- schreibt bekannte sensible Umgebungswerte nicht unkontrolliert in strukturierte Logs,
- weist im Help-Screen klar auf den vollständigen Snapshot-Inhalt hin.

Eine allgemeine automatische Secret-Erkennung ist nicht Bestandteil von 1.1.1.

---

## 20. Exit-Codes

Wenn ein Entrypoint oder manuelles Skript gestartet wurde, bestimmt grundsätzlich dessen Exit-Code das primäre Ergebnis. PatchHarbor-Tool-Fehler müssen in der sichtbaren und strukturierten Ausgabe klar von Skript-Exit-Codes unterscheidbar sein.

| Code | Bedeutung |
|---:|---|
| `2` | ungültige CLI-Verwendung oder fehlende Eingabe |
| `3` | kein gültiges PatchHarbor-Skript beziehungsweise kein gültiger Entrypoint |
| `4` | Eingabe oder ZIP nicht lesbar, unsicher oder Ressourcenbudget überschritten |
| `5` | Interpreter fehlt oder kann nicht gestartet werden |
| `6` | sichere Bereitstellung einer Nutzdatei fehlgeschlagen |
| `7` | sonstiger interner Ausführungsfehler vor Prozessstart |
| `8` | Repository nicht registriert, nicht mehr gültig oder Registrierung mehrdeutig |
| `9` | Base-Commit, Fingerprint oder Fingerprint-Algorithmus stimmt nicht überein |
| `10` | `patch.json` oder Paketformat ungültig |
| `11` | Result Bundle ist der primäre oder einzige fehlgeschlagene Auftrag |
| `12` | Repository ist bereits exklusiv gesperrt |
| `13` | Repository-Zustand wird im sicheren 1.1.1-Pfad nicht unterstützt |
| `124` | Timeout |
| `130` | Abbruch durch Strg+C |

Bei mehreren Skripten im manuellen ZIP-PatchBundle gilt:

- alle erfolgreich: Exit-Code des letzten Skripts, normalerweise 0,
- erstes fehlerhaftes Skript: dessen Exit-Code,
- spätere Skripte werden nicht gestartet.

Da ein Skript dieselben numerischen Werte zurückgeben kann, nennt `run.json` immer getrennt:

- `entrypoint_exit_code`,
- `patchharbor_error_code`,
- `process_exit_code`.

---

## 21. Architektur und Modulgrenzen

Das Python-Paket bleibt so flach wie sinnvoll.

Empfohlene Verantwortlichkeiten:

- `cli.py` – argparse, Aufrufe der öffentlichen API und Darstellung,
- `api.py` – unterstützte synchrone Bibliotheksgrenze zur Application,
- `api_types.py` – wiederverwendete öffentliche Ergebnis-, Stream- und Ereignistypen,
- `application.py` – Orchestrierung genau eines Auftrags einschließlich manueller beziehungsweise automatischer Repository-Scope-Wahl und deterministischer Kandidatenauswahl,
- `sources.py` – Datei, Ordner und STDIN als neutrales `InputArtifact`,
- `bundles.py` – manuelle direkte Skripte und ZIP-Container zu `PatchBundle`s auflösen,
- `bundle_paths.py` – gemeinsame sichere ZIP-Pfadregeln,
- `payload_files.py` – sichere ZIP-Nutzdateien und atomisches Schreiben,
- `parser.py` – Pflichtmarker, META und MESSAGE,
- `resource_policy.py` – unveränderliche Ressourcenbudgets,
- `interpreters.py` – Interpreter-Whitelist und feste Prozessargumente,
- `execution.py` – temporäre Skriptdatei, Prozessstart, Timeout und Ergebnis,
- `run_log.py` – vollständiger Run-Log und strukturierter Run-Bericht,
- `presentation.py` – kompakte/ausführliche Konsole und CLI-Adapter für neutrale Ereignisse,
- `identifier_presentation.py` – zentrale Sechs-Zeichen-Darstellung technischer Kennungen,
- `exchange.py` und `exchange_state.py` – stabile Inhaltsklassifikation, Exchange-Dateiidentität und persistenter Replay-Status einschließlich Run-ID, gepinnter Result-SHA und optionalem Abschlusscommit,
- `exchange_recovery.py` – koordinierte Beweisprüfung unter Repository-/Registry-/State-Locks vor normaler Archivierung; keine PID-Heuristik und kein Rollback,
- `archive_policy.py` – reine Validierung des direkten Archivordnernamens,
- `archive_evidence.py` und `archive_git.py` – passive Bundle-Validierung und lesende Originalhistorien-Beweise,
- `exchange_archive.py` – konservative Wartung des von `application` bestimmten Repository-Scopes,
- `archive_files.py` und `platform/archive.py` – Kollisionsnamen und gepinnte No-Replace-Dateioperationen,
- `registry.py` – zentrale Repository-Registrierung ohne Repository-Einstellungen,
- `configuration_context.py` – Auflösung einer registrierten lokalen Config anhand Pfad oder ID,
- `configuration.py` – geschlossenes lokales Format 1, Identitätsprüfung und atomare Persistenz,
- `repository_state.py` – Base-Commit, kanonischer Fingerprint und Snapshot-Zustand,
- `locks.py` – globale Registry-Sperre und exklusive Sperre pro Repository-ID,
- `patch_manifest.py` – `patch.json` und Schema,
- `result_bundle.py` – vollständiges Result Bundle und atomare Veröffentlichung,
- `models.py` – kleine unveränderliche Datenträger,
- `errors.py` – fachliche Tool-Fehler und semantische Fehlergründe,
- `exit_status.py` – gemeinsame Abbildung in kompatible CLI-/JSON-Statuszahlen,
- `platform/` – notwendige Linux- und Windows-Grenzen,
- separater Watcher-Einstiegspunkt – Registry-Prüfung über API, Poll-Lebenszyklus und privater API-Worker mit frischer Core-Konfiguration in einem eigenen Prozess.

Abhängigkeitsregeln:

- `cli` ruft für Fachoperationen ausschließlich `api` auf; `api` delegiert an `application`.
- `application` ist der einzige fachliche Orchestrator eines Auftrags.
- `sources` kennt weder ZIP-Regeln noch Parser, Git oder Execution.
- `bundles` klassifiziert und beschreibt Inhalte, schreibt aber keine Nutzdateien.
- `parser` ist rein und kennt keine Dateischreib- oder Prozesslogik.
- `payload_files` schreibt Dateien, steuert aber keine Execution.
- `patch_manifest` kennt weder Git noch Execution.
- `registry` kennt weder TUI noch ZIP-Inhalte.
- `configuration` verwaltet ausschließlich repositorylokales Format 1 und prüft die zugehörige lokale Identität, aber steuert weder Git-Zustandsaufnahme noch Execution. `configuration_context` löst gegen einen konsistenten Registry-Snapshot auf; kein globaler Config-Leser und kein Migrationspfad.
- `bundle_names` enthält reine Validierung und Anfügen des Suffixes sowie die gemeinsame Erkennung temporärer Download-Namen; es liest keine Konfiguration und keine Dateien.
- `platform.environment` erfasst ausschließlich freigegebene lokale Laufzeitfelder; `chat_instructions` lädt die installierte statische Vorlage und rendert passive Dokumentation. `bundle_handoff` modelliert und validiert optionale Patch-Begleitdaten; `result_bundle_handoff` komponiert Result-Begleitdaten. Keine dieser Schichten führt Chat-, Plan- oder Commit-Anweisungen aus.
- `result_bundle_target` bindet das konfigurierte Suffix an das Ausgabeziel und revalidiert es; `result_bundle` übergibt denselben Wert als optionale Kontextmetadaten. Der Chat bleibt für die Benennung externer Patch-Pakete verantwortlich.
- `exchange` klassifiziert flache Dateikandidaten und persistiert Dateidentitäten, führt aber keinen Entrypoint aus.
- `archive_evidence` liest nur geprüfte Bundle-Bytes; `archive_git` prüft nur Git und bestehende Statusbelege. `exchange_archive` erhält den Scope von `application`, wählt keine auszuführenden Patches und importiert weder CLI noch Execution. `archive_files` kennt keine Git-Semantik; native Rename-/Handle-Details liegen ausschließlich unter `platform/`.
- `repository_state` kennt weder TUI noch Watcher.
- `locks` kennt keine Ausführungs- oder Bundle-Semantik.
- `interpreters` kennt nur den kleinen Interpretervertrag.
- `execution` kennt weder Registry, Git-Zustand, Result-Bundle-Struktur noch TUI.
- `result_bundle` verwendet Repository-State- und Run-Log-Daten, führt aber keinen Patch aus.
- `presentation` steuert keine fachliche Logik.
- Der Watcher kennt nur die öffentliche PatchHarbor-Aufrufsgrenze sowie den gemeinsamen Exchange-Dateivertrag.
- Repo Assist und PromptBridge sind keine internen Module.
- Es gibt keine Sammelpakete namens `utils`, `helpers` oder `common`.
- Es gibt keine Plugin-Registry und keine asynchrone Kernarchitektur.

---

## 22. Teststrategie und Freigabe

### 22.1 Grundsatz

PatchHarbor wird pragmatisch verhaltensorientiert entwickelt.

- Schwerpunkt auf End-to-End- und Integrationstests,
- wenige gezielte Unit-Tests für isolierte kritische Logik,
- echte Dateien, echte Git-Repositories und echte Prozesse,
- Verhalten statt interner Implementierungsdetails,
- keine dogmatische Forderung nach vollständiger Testabdeckung,
- automatisierte CI- und Release-Testläufe besitzen einen ausreichend bemessenen äußeren Timeout; der native Acceptance-Matrix-Job erhält 120 Minuten, die gesonderten PowerShell- und Docker-Grenzen bleiben unverändert,
- interaktive Commit-Skripte im dokumentierten Pixel-/Termux-Workflow dürfen ohne künstlichen Einzeltest- oder Gesamtsuite-Timeout laufen,
- menschliche Konsolenausgabe wird nicht automatisiert getestet: weder Texte, Farben, Symbole, Reihenfolge, Kürzungen noch Fenster- oder Streaming-Darstellung,
- geschlossene JSON-Verträge, rohe Ausführungslogs, Dateiinhalte, Parserdaten, Zustandsübergänge und Exit-Codes bleiben funktional geprüft; die Chat-Paketverträge bleiben ebenfalls verbindlich.

### 22.2 Beizubehaltende 1.0.0-Verträge

Mindestens zu erhalten und weiter zu testen sind:

- direkter Datei-Run,
- exakter Pflichtmarker,
- META- und MESSAGE-Warnings,
- STDIN und Pipe mit direktem Skript,
- STDIN und Pipe mit binärem ZIP-PatchBundle,
- einmaliger nicht rekursiver Ordnerscan und Auswahl,
- mehrere ZIP-Skripte in Archiv-Reihenfolge,
- Binärdateien einschließlich Nullbytes,
- bytegenaue Erhaltung von Nutzdateien,
- Nutzdateien vor dem ersten Skript verfügbar,
- markerlose Shell- oder PowerShell-Dateien werden nicht automatisch ausgeführt,
- enthaltenes Archiv wird nicht rekursiv geöffnet,
- reines Datei-ZIP ohne Skript wird im manuellen Pfad abgelehnt,
- unsichere, besondere, doppelte oder mehrdeutige ZIP-Einträge,
- tatsächlicher Schreibfehler verhindert Ausführung,
- Abbruch beim ersten fehlerhaften Skript,
- Exit-Code des letzten ausgeführten Skripts,
- atomisches Überschreiben,
- Timeout pro Skript,
- Strg+C und vollständiger Prozessbaum,
- fehlender Interpreter,
- verlustfreie Prozesserfassung bei viel Output und begrenzter interner Rolling Buffer,
- lange beziehungsweise unvollständige Zeilen sowie beliebige Bytes bleiben im Rohlog erhalten,
- temporäre Logdatei bei `--log`,
- ursprüngliches Arbeitsverzeichnis,
- Ressourcenlimits und ZIP-Bomben-Schutz,
- Wheel- und pipx-Installation.

### 22.3 Fortgeltende Pflichtszenarien aus 1.1.0

- Registrierung und UUID-v4-Format,
- globaler Registry-Lock und atomarer Registry-Austausch,
- vollständiges lokales Exclude von `.patchharbor/`,
- Ablehnung einer getrackten oder besonderen `.patchharbor`-Struktur,
- zwei Klone desselben Remotes erhalten verschiedene IDs,
- idempotente Registrierung,
- verlorene ID entfernt alte Pfadzuordnungen vor der Neuregistrierung,
- `registry list`, `unregister` und `register --new-id`,
- verschobener Pfad bei nicht mehr vorhandenem Altpfad,
- kopierte ID wird abgelehnt,
- partielle Registry-Aktualisierung wird zurückgerollt oder als Inkonsistenz gemeldet,
- Kontextausgabe für clean und dirty unter Repository-Lock,
- vier feste Encoder-Testvektoren für `patchharbor-state-v1`, darunter staged und unstaged,
- exakte ASCII-, UTF-8-, Objekt-ID-, Status-, Inhalts-, Zähler- und Größen-Payloadcodierung,
- staged Hinzufügung, Änderung, Löschung und Modusänderung,
- unstaged Änderung und Löschung regulärer Dateien,
- untracked Pfad, Modus und vollständiger Inhalt,
- Binärdatei im Fingerprint,
- Base-Commit ist nicht Teil des Fingerprints,
- nicht aufgelöster Index wird klar abgelehnt,
- Assume-Unchanged und Skip-Worktree werden klar abgelehnt,
- Intent-to-add wird klar abgelehnt,
- Sparse-Checkout und Sparse-Index werden klar abgelehnt,
- Submodule und getrackte Symlinks werden klar abgelehnt,
- nicht reguläre Working-Tree- und untracked Einträge werden klar abgelehnt,
- nicht als UTF-8 darstellbare Repository-Pfade werden klar abgelehnt,
- Windows-reservierte, steuerzeichenhaltige, mit Punkt oder Leerzeichen endende und anderweitig nicht portable Repository-Pfade werden klar abgelehnt,
- Groß-/Kleinschreibungs-Kollisionen werden über den festgelegten `casefold()`-Vergleichsschlüssel abgelehnt,
- verbotene `.git`- und `.patchharbor`-Segmente werden in Base-Baum und Index ohne Beachtung der Groß-/Kleinschreibung erkannt,
- `core.fileMode` bestimmt den kanonischen Modus eindeutig,
- Kontextänderung führt zur Ablehnung,
- eine Zustandsänderung zwischen erster Prüfung und unmittelbar vor der ersten Repository-Schreiboperation führt ohne Repository-Schreibzugriff zur Ablehnung,
- genau eine Root-`patch.json` bei weiteren erlaubten Paketdateien,
- ungültiger Paketmarker, Algorithmus oder Formatversion,
- striktes `patch.json`-Schema mit verbotenen unbekannten Feldern, kanonischer UUID, vollständiger Objekt-ID und exakt 16-stelligem Fingerprint,
- unbekannte Repository-ID,
- Base-Commit- und Fingerprint-Mismatch,
- `.git` und `.patchharbor` in jedem Eingabepfadsegment werden abgelehnt,
- Entrypoint bleibt temporär und CWD ist das Ziel-Repository,
- Entrypoint-Marker und Interpreter werden vor der ersten Repository-Änderung geprüft,
- nur der manifestierte Entrypoint wird automatisch ausgeführt,
- Dry-Run schreibt und startet nichts,
- exklusive Sperre verhindert parallele Aufträge,
- feste Lock-Reihenfolge verhindert Deadlocks zwischen Registry und Repository,
- äußerer Zustandswechsel während Snapshot-Erzeugung verwirft das Bundle,
- Result-Bundle-Ausgabeordner innerhalb irgendeines registrierten Repositorys wird abgelehnt,
- temporäre und endgültige Bundle-Datei liegen im selben endgültigen Ausgabeordner,
- dateisystemgleiche atomare Veröffentlichung über `os.replace()`,
- vollständiges Result Bundle ohne `.git`,
- Base-Commit wird vollständig über Baumabfrage und Blob-Lesen materialisiert,
- Exportattribute dürfen keine committed Datei auslassen oder verändern,
- Base-Dateimodi und Objekt-IDs stehen im Manifest,
- staged und unstaged Patch werden unter kontrollierter Git-Umgebung erzeugt,
- untracked Dateien werden bytegenau samt Modus und Inhalts-Hash aufgenommen,
- vollständiger Run-Log,
- automatische Bundle-Erzeugung nach sicherer Repository-Auflösung,
- Fehlerpriorität bei primärem Fehler plus Bundle-Fehler,
- Exit `11` bei ausschließlich fehlgeschlagener Bundle-Erzeugung,
- Notfallrettung ohne halbfertige endgültige ZIP-Datei,
- JSON-Modus mit genau einem Objekt auf stdout,
- exakte JSON-Verträge für `registry list`, `context`, `bundle` und `apply` einschließlich Fehlerobjekten,
- temporäre STDIN-Artefakte werden über den zentralen Cleanup-Pfad entfernt,
- Watcher delegiert stabile Exchange-Dateien ohne duplizierte Core-Logik,
- konkurrierende autonome Watcher-, Repo-Assist- oder Orchestrator-Pfade werden für dieselben Repositories nicht gleichzeitig aktiviert.

### 22.4 Exchange-Pflichtszenarien einschließlich repositorylokaler Revision

Mindestens zusätzlich zu prüfen sind:

- exaktes geschlossenes lokales Format 1 mit `null`-Exchange nach Erstanmeldung und atomarer Veröffentlichung,
- Konfiguration nur im registrierten Repository, einschließlich CLI-/API-Aufruf aus Unterverzeichnissen,
- getrennte und gemeinsam genutzte Exchange-Verzeichnisse mit unabhängigen Suffix-/Archivwerten,
- automatischer Poll scannt physisch gleiche Ordner einmal, akzeptiert keine falsch abgelegten Pakete und lädt geänderte Konfigurationen frisch,
- lokale Einstellungen bleiben bei Unregister, Wiederanmeldung und echtem Verschieben erhalten; Git-Clone beginnt neu,
- alte globale Konfigurationen bleiben wirkungslos und unverändert; fehlende/ungültige lokale Dateien werden weder angelegt noch repariert,
- explizite Ausgabe bei unset/unavailable Exchange bleibt zulässig, aber nicht bei beschädigter Config; Zielrepository bestimmt Begleitdaten,
- konkrete Workflow-/Verhaltenstests statt neuer Dokumentations-, Help- oder Darstellungstests,
- direkte gültige und ungültige Bearbeitung der Konfigurationsdatei,
- Linux-, Termux-kompatible Linux- und Windows-Benutzerpfade,
- `configure exchange-directory` und `configure show`,
- Exchange-Ordner innerhalb, außerhalb und oberhalb registrierter Repositories,
- spätere Registrierung mit Konflikt zum Exchange-Ordner,
- fehlende Konfiguration bei Befehlen mit und ohne explizite Overrides,
- `bundle` ohne `--output-dir` veröffentlicht im Exchange-Ordner,
- automatisches Apply-Result-Bundle veröffentlicht im Exchange-Ordner,
- explizites `--output-dir` übersteuert das Standardziel,
- nicht rekursiver Exchange-Scan ohne Abhängigkeit von Dateiname oder Endung,
- Result Bundles, direkte Skripte, alte Patch-ZIPs, Browser-Temporärdateien und sonstige Dateien werden nicht als sichere Patch-Kandidaten ausgeführt,
- manueller parameterloser Apply löst das aktuelle registrierte Repository einschließlich Unterverzeichnisaufrufen zuerst auf und betrachtet keine Pakete fremder Repositorys,
- ein nicht registriertes oder nicht eindeutig auflösbares aktuelles Repository führt ohne repositoryübergreifenden Fallback zum kontrollierten Fehler,
- vollständig passende Kandidaten werden vor jeder Zeitrangfolge anhand von Repository-Scope, `repo_id`, Base-Commit, Fingerprint und Replay-Eignung gefiltert,
- bei mehreren zulässigen Kandidaten wird der höchste `mtime_ns` gewählt; ein exakter Zeitgleichstand wird deterministisch über Unicode-NFC-normalisierten Dateinamen und unveränderten Dateinamen aufgelöst,
- ein neuerer unzulässiger Kandidat blockiert keinen älteren zulässigen Kandidaten,
- explizites `PATCH_ZIP` übersteuert die parameterlose CWD-Auswahl und darf ein anderes registriertes Repository über `repo_id` bestimmen,
- Dry-Run verändert keinen Replay-Status,
- `attempted`, `failed` und `succeeded` bleiben über Prozessneustarts unterscheidbar,
- ein fehlgeschlagener parameterloser manueller Apply kann bei unveränderter vollständiger State-Bindung dasselbe Paket erneut ausführen,
- ein Watcher-Poll wiederholt dasselbe fehlgeschlagene Paket nicht unmittelbar erneut,
- ein erfolgreiches Paket bleibt für manuelle parameterlose und automatische Auswahl Replay-geschützt,
- Base-Commit- oder Fingerprint-Mismatch verhindert den manuellen Retry eines fehlgeschlagenen Pakets,
- mehrere Pakete für verschiedene Repositorys oder Zustände führen beim manuellen Apply nicht zur Auswahl eines falschen Kandidaten; der Watcher bleibt global,
- geänderter Inhalt unter demselben Namen ist eine neue Identität,
- Patch- und Result-Dateinamen folgen dem Repository-/Typ-/Uhrzeit-/Datum-/ID6-Vertrag,
- menschenlesbare technische IDs erscheinen zentral als sechs Zeichen plus `…`, während JSON und Sicherheitsdaten vollständig bleiben,
- Exchange-Dateien bleiben nach Verarbeitung unverändert am Ort,
- Core und Watcher teilen Konfiguration, Klassifikation und Dateidentitätsvertrag,
- Watcher-Neustart führt nicht zur erneuten Verarbeitung unveränderter Dateien,
- Watcher verarbeitet ein neu erzeugtes Result Bundle im Exchange-Ordner nicht,
- `CHAT_INSTRUCTIONS.md` ist vorhanden, versionsgebunden und widerspruchsfrei zu Spezifikation, README und CLI,
- Chat-Initialisierung verwendet die frisch eingebettete `CHAT_INSTRUCTIONS.md` und `environment.json` im aktuellen Result Bundle; Pfade dienen nur lokalen Befehlen,
- Plan- und Spezifikationssuche folgt der festgelegten Priorität und stoppt bei Mehrdeutigkeit,
- `PLAN`, `FIX` und `OFF-PLAN` besitzen die festgelegte Kennungs- und Zählersemantik,
- Fix-Kennungen verwenden `<PLAN-ID>-FIX<n>` und erhöhen den Plan-Zähler nicht,
- Off-Plan-Kennung und Commit-Message dürfen sinnvoll frei gewählt werden und sind sichtbar als `OFF-PLAN` markiert,
- Spezifikation ist fachlicher Vertrag, Commit-Plan ist die geplante Zerlegung; Scope-Erweiterungen werden nicht stillschweigend vorgenommen,
- blockierende Widersprüche erzeugen die standardisierte STOP-Ausgabe und kein Patch-Paket,
- nicht blockierende Auffälligkeiten erzeugen die standardisierte WARNING-Ausgabe,
- pro Patch-Auftrag gibt es eine finale Auslieferung mit genau einer grünen Bereitschaftszeile und einer kanonischen ZIP,
- `PATCH BEREIT` erscheint erst, wenn genau ein herunterladbares Patch-Paket tatsächlich erzeugt wurde,
- vor lokaler Ausführung werden geplante Tests nicht fälschlich als erfolgreich dargestellt,
- zurückgegebene `logs/run.json` und `logs/execution.log` werden für Erfolg oder Reparatur ausgewertet,
- README deckt neues und bestehendes Repository, neuen Chat, manuellen Betrieb und Watcher-Betrieb ab.

### 22.5 Release-Audit

Der finale 1.1.1-Release-Audit prüft mindestens die Existenz und Konsistenz von:

```text
README.md
CHAT_INSTRUCTIONS.md
spec/SPECIFICATION.md
spec/SPECIFICATION_CHANGELOG.md
planning/1.0.0/commit-plan.md
planning/1.1.0/commit-plan-cleanup.md
planning/1.1.0/commit-plan.md
planning/1.1.1/commit-plan.md
```

Der vorbereitende 1.1.1-Dokumentationscommit erweitert den bestehenden Audit zunächst um `planning/1.1.1/commit-plan.md`, ohne Produktionscode zu verändern. Der Implementierungscommit, der `CHAT_INSTRUCTIONS.md` einführt, erweitert den Audit anschließend um diese Datei. So bleibt jeder Zwischencommit grün, während der finale Vertrag vollständig erzwungen wird.

### 22.6 Freigaberegel

- Jeder Implementierungscommit hat eine erkennbare Absicht.
- Feature und zugehöriger Verhaltenstest gehören zusammen.
- Nach jedem Commit ist die bis dahin geltende Testsuite mit einer plattformgerechten Timeout-Strategie grün.
- Ausgelieferte Commit-Skripte für den dokumentierten Pixel-/Termux-Workflow verwenden keinen künstlichen Einzeltest- oder Gesamtsuite-Timeout.
- Bei fehlgeschlagenen Tests entsteht kein Commit.
- Plattform- und Akzeptanztests werden vor Release vollständig ausgeführt.
- Ubuntu 24.04, Ubuntu 26.04 und der echte Windows-Runner sind blockierende Release-Gates; eine rote verbindliche Lane verhindert die Freigabe.

---

## 23. Bewusst ausgeschlossene Funktionen

Folgende Funktionen gehören nicht zu PatchHarbor 1.1.1:

- Netzwerk- oder Chatquelle im Core,
- Clipboard- oder SSH-Quelle,
- öffentliches Plugin-System,
- Save-Modus mit chmod,
- Zielprojekt-Testmanagement,
- Git-Commit-, Branch-, Tag- oder Release-Management,
- interaktive Kindskripte,
- aus Skriptkommentaren erzeugte Nutzdateien,
- automatische Dekodierung textuell transportierter Binärdaten,
- rekursive Ordnersuche,
- rekursive Auflösung enthaltener Archive,
- universelle Pakettransaktion und automatische globale Rückabwicklung,
- dauerhafte Logverwaltung und Logrotation im Core,
- automatisches Einsammeln beliebiger zusätzlicher Diagnoseartefakte,
- Netzwerk-, Chat-, Upload- oder Downloadlogik im Core,
- unbelegte oder altersbasierte Archivierung und beliebige Sortierung von Exchange-Dateien sowie jede endgültige Bundle-Löschung,
- automatische Migration früherer `watcher.json`- oder `paths.json`-Dateien,
- Submodule im sicheren 1.1.1-Kontext und Result Bundle.

Commit-Plan, Journal, Reproduzierbarkeit sowie die fachliche Verwaltung von Tests und Commits gehören zu Repo Assist oder bis zu dessen Einsatz zum ausdrücklich angewiesenen externen Entwicklungs-Chat. Dauerhafte Ordnerüberwachung gehört zum separaten PatchHarbor Watcher. Chat- und Transportfunktionen gehören zu PromptBridge beziehungsweise einem späteren übergeordneten Orchestrator.

---

## 24. Unterschiedliche Bundle-Arten

### 24.1 PatchHarbor Result Bundle

Beantwortet:

> Wie sieht die konkrete lokale Repository-Instanz technisch jetzt aus, und was hat der PatchHarbor-Auftrag ausgegeben?

Es enthält Snapshot, Kontext, Fingerprint und PatchHarbor-Run-Logs.

### 24.2 Repo-Assist-Journal-Bundle

Beantwortet:

> Welche Aufgabe und welcher Entwicklungsworkflow wurden durchgeführt, warum wurden Entscheidungen getroffen, und welches Gesamtergebnis entstand?

Es kann enthalten:

- Aufgabe,
- Prompts,
- Patch-Pakete,
- Testergebnisse,
- Commit-Ergebnis,
- Retry- und Abort-Informationen,
- Journal,
- ein eingebettetes oder referenziertes PatchHarbor Result Bundle.

Repo Assist dupliziert nicht die technische Snapshot-Logik von PatchHarbor.

---

## 25. Versionswechsel und abgeschlossene Entwicklungspläne

### 25.1 Historie ist kein Konfigurations-Fallback

Die abgeschlossenen Pläne unter `planning/1.1.1/` und der API-Plan unter
`planning/1.2.0/commit-plan.md` dokumentieren ihre jeweiligen Implementierungsschritte.
Sie werden durch die repositorylokale Revision nicht neu nummeriert oder als
unerledigt markiert. Frühere Konfigurationsmodelle sind ausschließlich im
`SPECIFICATION_CHANGELOG.md` als Historie beschrieben, nicht als parallel
unterstützte Einstellungen. Für aktuelle Aufrufe gilt Abschnitt 4.3.

### 25.2 Keine Konfigurationsmigration

Es gibt keinen automatischen oder optionalen Migrationscode für alte globale
`config.json`, `watcher.json` oder `paths.json`, kein duales Lesen und keinen
stillen Fallback auf einen früheren Standard-Result-Ordner. Die einzige Quelle
für Repository-Einstellungen ist dessen `.patchharbor/config.json` im neuen
lokalen Format 1. Registry und technische Replay-Zustände bleiben erhalten.

Die Umstellung vorhandener Registrierungen erfolgt ausdrücklich von Hand nach
4.3.4. Fehlende oder beschädigte lokale Dateien werden nicht repariert;
`register`, `register --new-id` und `configure` sind keine Reparaturbefehle.
Eine normale frische Registrierung erzeugt dagegen ihre Grundkonfiguration.

### 25.3 Repositorylokale Revision in zwei OFF-PLAN-Aufträgen

REPO-CONFIG-1 stellt Persistenz, Registrierung, Configure, Bundle/Apply,
Archivierung und Watcher technisch um. REPO-CONFIG-2 gleicht Spezifikation,
README, Python-API-Vertrag, Planungsspezifikation und Chat-Anweisungen ab und
sichert die vollständigen Benutzerabläufe mit Verhaltenstests.

Der abgeschlossene API-Plan bleibt bei 4/4. Die Konfigurationsrevision erzeugt
weder automatisch einen Release-Tag noch eine Publikation. Der konkrete
Apply-/Commit-Erfolg und externe CI benötigen eigene Nachweise; die
Dokumentationsfortschreibung ist kein grünes Testergebnis.

## 26. Verbindlicher Chat-Initialisierungsvertrag

### 26.1 Initialisierung eines neuen Chats

Die ausgelieferte Root-Datei `CHAT_INSTRUCTIONS.md` ist die versionsgebundene Handlungsanweisung für einen externen Entwicklungs-Chat.

Ein neuer Chat erhält mindestens:

1. die im Bundle frisch eingebettete `CHAT_INSTRUCTIONS.md` (bei alten Bundles separat),
2. das aktuelle PatchHarbor Result Bundle der zu bearbeitenden registrierten Repository-Instanz,
3. die konkrete Benutzeraufgabe oder die Anweisung, den nächsten Plan-Commit vorzubereiten.

Der Chat erhält lokale Repository- und Exchange-Pfade aus `environment.json` für passende Kommandozeilen auf dem Entwicklungsrechner. Diese Pfade dienen niemals der Repository-Zuordnung und gehören nicht in `patch.json`. Dafür verwendet er weiterhin ausschließlich `repo_id`, Base-Commit und Fingerprint aus dem Result Bundle unverändert.

Der Chat darf nicht aus Gesprächserinnerung behaupten, den Repository-Zustand zu kennen, wenn kein aktuelles Result Bundle vorliegt. Reichen die hochgeladenen Daten nicht für einen sicheren Patch aus, verwendet er eine STOP-Ausgabe nach Abschnitt 26.7.

### 26.2 Result-Bundle-Auswertung

Vor jeder Änderung prüft der Chat mindestens:

- `manifest.json` und `context.json`,
- den vollständigen Base-Snapshot,
- staged und unstaged Patches,
- nicht ignorierte untracked Dateien,
- bei einem vorherigen Apply zuerst `logs/run.json`,
- bei Fehler, Warning oder unklarer Ausführung zusätzlich `logs/execution.log`.

Ein fehlgeschlagener Patch kann Dateien verändert oder neu erzeugt haben. Der Chat arbeitet deshalb immer auf dem tatsächlich zurückgegebenen Snapshot weiter und unterstellt keine globale Rückabwicklung.

Ignorierte Dateien sind nicht Teil des Result Bundles. Benötigt die Aufgabe zwingend einen solchen Inhalt, darf der Chat ihn nicht erfinden.

### 26.3 Commit-Plan- und Spezifikationssuche

Der Chat bestimmt zunächst die aktuelle Zielversion aus eindeutigen Repository-Quellen wie Paketmetadaten, Versionsdatei, aktiver Spezifikation und versionsbezogenem Planning-Verzeichnis. Widersprechen sich plausible aktuelle Versionsquellen, stoppt er.

Für den Commit-Plan gilt diese Reihenfolge:

1. `planning/<version>/commit-plan.md`,
2. `planning/<version>/implementation-plan.md`,
3. ein eindeutig als Commit- oder Implementation-Plan erkennbarer Markdown-Kandidat direkt unter `planning/<version>/`,
4. genau ein eindeutig aktueller repositoryweiter Commit- oder Implementation-Plan.

Historische Pläne anderer Versionen dürfen nicht allein wegen eines ähnlichen Namens ausgewählt werden. Gibt es mehrere plausible aktuelle Kandidaten, gilt `PLAN_AMBIGUOUS`. Gibt es keinen Plan und verlangt der Benutzer ausdrücklich den „nächsten“ Plan-Commit, gilt `PLAN_NOT_FOUND`. Für eine bewusst planlose Aufgabe darf der Chat stattdessen `OFF-PLAN` verwenden.

Für die Spezifikation gilt diese Reihenfolge:

1. ein vom ausgewählten Commit-Plan ausdrücklich referenziertes Dokument,
2. `planning/<version>/specification.md` oder ein dort eindeutig als Spezifikation erkennbarer Markdown-Kandidat,
3. `spec/SPECIFICATION.md`,
4. genau eine eindeutig aktuelle repositoryweite Spezifikation.

Ist keine Spezifikation vorhanden, zeigt die UI `Spec: nicht vorhanden` und arbeitet anhand von Plan, realem Repository und Benutzerauftrag. Gibt es mehrere plausible aktuelle Spezifikationen, gilt `SPEC_AMBIGUOUS`.

Der verwendete Plan- und Spezifikationspfad wird in jeder Patch-Bereit-Ausgabe angezeigt. Kann die bereits erreichte Planposition nicht eindeutig bestimmt werden, gilt `PLAN_POSITION_UNKNOWN`; der Chat rät nicht.

### 26.4 Verhältnis von Spezifikation, Plan und Repository

Die Spezifikation ist der fachliche Vertrag. Der Commit-Plan ist die vorgesehene Zerlegung dieses Vertrags. Der reale Repository-Zustand entscheidet, welche Voraussetzungen bereits tatsächlich vorhanden sind.

Vor der Patch-Erstellung gleicht der Chat die konkrete Commit-Beschreibung mit den zugehörigen Spezifikationsabschnitten und dem Code ab.

- Eine kleine, eindeutig zum Commit gehörende und für dessen Korrektheit notwendige Lücke darf im selben Commit geschlossen werden. Sie wird als Warning sichtbar gemacht.
- Eine merkliche Scope-Erweiterung, ein vorgezogener späterer Planpunkt, eine neue Architekturentscheidung oder ein fachlicher Widerspruch wird nicht stillschweigend umgesetzt.
- Erscheint eine Vorgabe technisch falsch, unlogisch, unsicher oder unmöglich, stoppt der Chat mit einem passenden Code und einer kurzen konkreten Frage.

### 26.5 Commit-Arten und Zähler

Es gibt genau drei sichtbare Commit-Arten:

`PLAN`

- Kennung, Commitposition und Commit-Message werden exakt aus dem ausgewählten Plan übernommen.
- Der Plan-Zähler zeigt `aktuelle Position / Gesamtzahl`.

`FIX`

- Ein Fix gehört zu genau einem Plan-Commit.
- Seine Kennung lautet `<PLAN-ID>-FIX<n>`, beginnend mit `FIX1`.
- Seine Commit-Message beginnt mit `Fix:` und beschreibt die konkrete Reparatur.
- Ein Fix erhöht weder Gesamtzahl noch erreichte Position der Plan-Commits.

`OFF-PLAN`

- Der Chat darf eine kurze sinnvolle Kennung und Commit-Message frei wählen.
- `OFF-PLAN` muss unübersehbar angezeigt werden.
- Ein Off-Plan-Commit verändert den Plan-Zähler nicht.
- Existiert ein Plan, zeigt die UI `-- / <Gesamtzahl>`; existiert keiner, zeigt sie `-- / --`.

Ein Chat-Patch erzeugt nach grünen Tests genau einen Git-Commit der angezeigten Art, sofern der Benutzer nicht ausdrücklich einen nicht committenden Diagnoseauftrag verlangt. Bei roten Tests entsteht kein Commit.

### 26.6 Patch-Paket- und Testvertrag des Chats

Der Chat erzeugt genau eine herunterladbare ZIP-Datei im sicheren PatchHarbor-Paketformat. Er liefert keine parallele Shell-Datei, keinen zweiten Patch und keine alternative manuelle Änderungsanleitung. Der Dateiname folgt `<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip` mit UTC-Uhrzeit, Monat/Tag ohne Jahr und den ersten sechs Zeichen einer Paket-UUID ohne `…`.

Das Paket:

- enthält genau eine Root-`patch.json`,
- verwendet unverändert `repo_id`, Base-Commit, Fingerprint und Algorithmus aus dem aktuellen Result Bundle,
- enthält genau einen manifestierten Entrypoint mit dem Pflichtmarker `# PATCHHARBOR`,
- enthält nur die für den Auftrag notwendigen sicheren Nutzdateien,
- führt die zur Änderung passenden Tests mit einer plattformgerechten Timeout-Strategie aus,
- verwendet im dokumentierten Pixel-/Termux-Workflow keinen künstlichen Einzeltest- oder Gesamtsuite-Timeout; fachlich notwendige interne Prozess- und Timeout-Tests bleiben bestehen,
- verwendet bei breitem oder riskantem Scope die vollständige Testsuite,
- erzeugt den vorgesehenen Git-Commit erst nach grünen Tests,
- ruft nicht selbst `patchharbor bundle` auf.

Vor dem lokalen Apply darf die UI nur die im Patch vorgesehenen Tests nennen. Sie darf diese Tests nicht als erfolgreich darstellen. Erst ein zurückgegebenes Result Bundle mit erfolgreichem Run-Bericht erlaubt eine Erfolgsaussage.

Die kanonische Patch-ZIP erhält bei ihrer finalen Festlegung eine dreistellige `PATCHHARBOR-BUNDLE-NR`. Der Entrypoint verwendet exakt dieselbe Nummer und gibt erst nach allen Änderungen, Tests, Commits und der Prüfung des sauberen Zielzustands als seine letzte eigene Erfolgszeile `PATCHHARBOR-BUNDLE-NR: <NNN> | APPLIED SUCCESSFULLY` aus. Bei einem fehlgeschlagenen Apply darf diese Zeile nicht erscheinen; nach ihr darf PatchHarbor selbst noch Snapshot- und Result-Bundle-Meldungen ausgeben.

### 26.7 Standardisierte Warning- und Stop-Ausgaben

Eine nicht blockierende Auffälligkeit beginnt exakt mit:

```text
🟨🟨 PATCHHARBOR WARNUNG 🟨🟨
CODE: <WARNING_CODE>
```

Zulässige Warning-Codes sind mindestens:

- `PLAN_SPEC_MINOR_DEVIATION` – eine kleine eindeutig commitbezogene Planlücke wird innerhalb des Scopes geschlossen,
- `NON_BLOCKING_ASSUMPTION` – eine ausdrücklich benannte, sichere und nicht designprägende Annahme wird verwendet,
- `REDUCED_TEST_SCOPE` – aus einem klar genannten Grund kann nur ein kleinerer als der normalerweise erforderliche Testumfang in den Patch aufgenommen werden.

Eine blockierende Situation beginnt exakt mit:

```text
🟥🟥 PATCHHARBOR STOP 🟥🟥
CODE: <STOP_CODE>
```

Zulässige Stop-Codes sind mindestens:

- `PLAN_NOT_FOUND`,
- `PLAN_AMBIGUOUS`,
- `PLAN_POSITION_UNKNOWN`,
- `SPEC_AMBIGUOUS`,
- `PLAN_SPEC_CONFLICT`,
- `REPOSITORY_STATE_INCOMPLETE`,
- `REQUIREMENT_AMBIGUOUS`,
- `UNSAFE_OR_IMPOSSIBLE`,
- `PATCH_CREATION_FAILED`.

Nach der Codezeile folgen höchstens eine kurze Erklärung und eine konkrete benötigte Entscheidung. Bei `STOP` wird kein Patch-Paket erzeugt und keine grüne `PATCH BEREIT`-Zeile ausgegeben.

### 26.8 Verbindliche schmale Patch-Bereit-UI

Pro Patch-Auftrag gibt es genau eine finale Auslieferung und genau eine kanonische ZIP. Eine erfolgreiche Antwort beginnt mit `🟩🟩 PATCH BEREIT 🟩🟩` und wiederholt diesen Balken im Abschlussblock; die Wiederholung ist keine zweite Auslieferung.

Jede neue kanonische ZIP erhält eine repositorybezogene, dreistellige `PATCHHARBOR-BUNDLE-NR`. Sie zählt Bundles, nicht Commits. Der externe Chat verwendet die nächste aus dem bekannten Verlauf ableitbare Nummer; ohne verlässliche Historie beginnt er bei `001`. Die Nummer wird erst mit der kanonischen ZIP vergeben, bleibt bei erneutem Link, Backup oder Versand derselben ZIP unverändert und wird bei einem STOP ohne Bundle nicht vergeben. Sie ist Handoff-Metadatum, keine Sicherheits- oder State-Bindung.

Vor der finalen Antwort gilt: ZIP vollständig erstellen, öffnen und validieren; danach Dateiname, Größe, Bundle-Nummer und SHA-256 festlegen und nicht mehr neu packen. Der Chat-Link verweist auf exakt diese Datei. Wenn autorisierte Drive-Werkzeuge verfügbar sind, wird dieselbe byteidentische ZIP privat unter `PatchHarbor-Backups/Patches` gesichert; keine öffentliche Freigabe. Upload-Erfolg darf nur nach Tool-Bestätigung, Bytegleichheit nur nach SHA-256-Rückprüfung oder geeigneter Anbieter-Prüfsumme behauptet werden. Die eigene Gmail-Adresse wird aus dem verbundenen Konto ermittelt; dieselbe ZIP wird dorthin gesendet, oder bei Anhangsgrenzen der bestätigte private Drive-Link mit Dateiname und SHA-256. Eine reine Statusmail ist kein Backup. Backupfehler sind Best Effort und machen einen ansonsten gültigen Patch nicht ungültig; unklaren Status prüfen und keine doppelten Uploads oder Mails erzeugen.

`Chat-Link`, `Drive-Backup`, `E-Mail` und `SHA-256` stehen unmittelbar vor dem Abschlussblock. Chat-Link, Drive-Link und E-Mail beziehen sich auf dieselbe kanonische Datei. Die Sicherung erfolgt im externen Chat, nicht im Core, Watcher oder Entrypoint, und ist keine CI-Freigabe oder Release-Markierung.

Beispiel (Platzhalter nie als echte Nachweise ausgeben):

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

Verbindlich gelten die vorhandenen `FIX`-/`OFF-PLAN`-Detailzeilen, Commit-/Plan-/Spec-Angaben und die Beschränkung auf tatsächlich vorgesehene Tests. Der Erfolgsabschluss besteht exakt aus Bereitschaftsbalken, Bundle-Nummer und Patch-Link; der Patch-Link ist die allerletzte Zeile der gesamten Antwort. `PATCH BEREIT` darf erst nach Existenz der verlinkten Datei erscheinen.

### 26.9 Auswertung nach lokalem Apply

Nach Rückgabe eines Result Bundles unterscheidet der Chat mindestens:

- erfolgreicher Apply und erfolgreicher Commit,
- fehlgeschlagener Entrypoint oder Test,
- PatchHarbor-Toolfehler,
- erfolgreicher Primärauftrag mit fehlgeschlagenem Result Bundle,
- Mismatch oder andere Ablehnung vor Mutation.

Ein Erfolg darf erst nach Prüfung von `run.json`, Git-Zustand und erwartetem Commit bestätigt werden. Bei einem Fehler beschreibt der Chat knapp die Ursache, den tatsächlich zurückgebliebenen Zustand und den nächsten sinnvollen `FIX`- oder `OFF-PLAN`-Schritt.

---

## 27. Zusammenfassung der verbindlichen Entscheidungen

- PatchHarbor Core ist ein kontrollierter Runner ohne Hintergrunddienst oder Netzwerk.
- Der PatchHarbor Watcher ist eine separate dünne systemd-fähige Komponente.
- Repo Assist verwaltet Commit-Plan, Journal, Reproduzierbarkeit sowie die fachliche Test- und Commit-Steuerung; ein weiterer Orchestrator kann darüber liegen.
- PromptBridge besitzt Chat- und Transportfunktionen.
- Jede lokale Repository-Instanz erhält eine eigene UUID v4 im reservierten, nicht committeten Verzeichnis `.patchharbor/`.
- Registry-Mutationen sind global gesperrt, atomar und folgen vor Repository-Locks einer festen Lock-Reihenfolge.
- `patchharbor context` liefert Base-Commit und Fingerprint; lokale Pfade sind kein Bestandteil des Patch-Vertrags.
- Der Fingerprint `patchharbor-state-v1` umfasst staged, unstaged und untracked Pfad, Modus und vollständigen Inhalt.
- Nicht eindeutige oder nicht portable Git-, Datei- und Pfadzustände werden im sicheren Pfad abgelehnt.
- Das sichere Patch-Paket ist ZIP-basiert, besitzt genau eine Root-`patch.json` und startet genau einen privat temporär bereitgestellten Entrypoint.
- Base-Commit und Fingerprint werden vor der ersten Repository-Mutation erneut geprüft.
- Pro Repository-ID gilt eine exklusive Sperre.
- Dry-Run validiert vollständig, schreibt und startet aber nichts und konsumiert keine Exchange-Dateiidentität.
- Primäres Auftragsergebnis und Result-Bundle-Ergebnis bleiben getrennt.
- Result Bundles enthalten den vollständigen Base-Commit, staged und unstaged Patches, nicht ignorierte untracked Dateien, Kontext und Run-Logs, aber keine Git-Historie.
- Result Bundles werden im endgültigen Ausgabeordner atomar veröffentlicht.
- `.patchharbor/config.json` ist die einzige Quelle aller Repository-Einstellungen: geschlossenes lokales Format 1, kein globaler Fallback, keine Migration, keine automatische Reparatur.
- Jedes Repository wählt seinen Exchange; getrennte oder gemeinsam genutzte flache Übergaben sind zulässig, Suffix und Archivregeln bleiben repositorylokal.
- Exchange-Ordner und registrierte Repositorys dürfen sich in keiner Richtung überlappen.
- `bundle` und Apply-Result-Bundles verwenden ohne explizites `--output-dir` den Exchange-Ordner.
- Ein manueller `apply` ohne `PATCH_ZIP` ist an das registrierte Repository des aktuellen Arbeitsverzeichnisses gebunden; Unterverzeichnisse werden zur Repository-Wurzel aufgelöst und fremde Repository-Pakete sind keine Kandidaten.
- Der Watcher bleibt mit internem automatischem Ursprung repositoryübergreifend.
- Erst nach Repository-, State- und Replay-Filterung gewinnt der höchste `mtime_ns`; bei Zeitgleichstand entscheidet deterministisch der Unicode-NFC-normalisierte und danach der unveränderte Dateiname.
- Result Bundles und sonstige Dateien werden nie als sichere Patch-Pakete ausgeführt.
- Erfolgreiche Identitäten bleiben Replay-geschützt; fehlgeschlagene Identitäten sind nur für einen bewussten manuellen parameterlosen Retry erneut zulässig, nicht für den Watcher.
- Patch- und Result-Dateinamen beginnen mit dem Repository-Namen, danach folgen `Patch` oder `Result`, UTC-Uhrzeit, Monat/Tag ohne Jahr und ID6.
- Menschenlesbare technische Kennungen verwenden sechs Zeichen plus `…`; JSON, Manifeste, Logs, Persistenz und Sicherheitsvergleiche bleiben vollständig.
- Die optionale Core-Archivierung verschiebt ausschließlich nachgewiesen überholte eigene Bundles in einen direkten Exchange-Unterordner; weder beliebige Ablageverwaltung noch endgültiges Löschen gehören dazu.
- Der Watcher verwendet über Core dieselben lokalen Konfigurationen, Paketklassifikation und Dateidentität; ein Scan je physischem Exchange pro Poll.
- Das aktuelle Result Bundle enthält frisch erzeugte `CHAT_INSTRUCTIONS.md` und `environment.json` zur Initialisierung eines neuen Entwicklungs-Chats.
- Repository-Pfad und Exchange-Pfad dienen nur Kommandozeilenbeispielen; sie ersetzen niemals die Repository-Bindung.
- Die Spezifikation ist der fachliche Vertrag; der Commit-Plan ist die geplante Zerlegung.
- Der Chat prüft Plan, Spezifikation und realen Repository-Zustand gegeneinander und fragt bei blockierenden Widersprüchen nach.
- `PLAN`, `FIX` und `OFF-PLAN` sind feste Commit-Arten; Fixes verwenden `<ID>-FIX<n>` und verändern den Plan-Zähler nicht.
- Blockierende Situationen verwenden eine standardisierte rote STOP-Ausgabe, nicht blockierende Auffälligkeiten eine gelbe WARNING-Ausgabe.
- Ein fertiges Patch-Paket wird genau einmal mit einer grünen Bereitschaftszeile ausgeliefert; es gibt keine Wiederholung am Antwortende.
- Der externe Chat versucht zusätzlich private Drive- und E-Mail-Backups derselben ZIP, bestätigt nur nachgewiesene Ergebnisse und nennt die vollständige SHA-256; der Core bleibt netzwerkfrei.
- `PATCH BEREIT` darf erst erscheinen, wenn genau eine herunterladbare Patch-Datei tatsächlich vorhanden ist.
- Ein Chat-Patch soll die zur Änderung passenden Projekttests mit einer plattformgerechten Timeout-Strategie ausführen und bei Testfehler ohne Commit enden; im dokumentierten Pixel-/Termux-Workflow verwendet das Commit-Skript keinen künstlichen Einzeltest- oder Gesamtsuite-Timeout. PatchHarbor selbst bewertet die Tests nicht und führt keinen Rollback durch.
- Nach Erfolg oder Fehler erzeugt PatchHarbor soweit möglich ein Result Bundle mit realem Repository-Zustand sowie `run.json` und `execution.log`.
- `watcher.json` und `paths.json` werden nicht migriert oder als Fallback gelesen.
- Der fortgeführte manuelle Runner behält seine Datei-, Ordner-, Pipe-, ZIP-, Interpreter-, Prozess-, TUI-, Logging- und Ressourcenverträge.
- PatchHarbor ist keine Sandbox; nur vertrauenswürdige Pakete dürfen ausgeführt werden.
- Ubuntu 24.04, Ubuntu 26.04 und echte Windows-Runner bleiben blockierende Release-Gates.


## 29. Kompakte Standardkonsole (OFF-PLAN COMPACT-CORE)

Diese Ergänzung ersetzt ausschließlich ältere Vorgaben zur standardmäßig
vollständigen Detailausgabe. Alle realen Sicherheitsprüfungen bleiben gleich.
Die normale Ausgabe von Apply, fs run und Bundle zeigt zusammengefasste
Arbeitsschritte und Ergebnisse. Die zentrale Präsentationspolitik unterdrückt
Einzelmeldungen von Git, ZIP, SHA, Payload-Dateien und Result-ZIP-Dateien.
`--verbose`/`-v` zeigt die vollständige Detailspur; Emittern ist der Modus unbekannt.

Bei laufenden internen Arbeiten werden Punkte angehängt, frühestens alle
0,8 Sekunden, ohne nachholende Punktserie, Carriage Return, Cursorsteuerung oder
Neuzeichnen. Der Präsentationsgeber untersucht keine Dateien und entscheidet
keine Core-Aktion. Warnungen, Fehler und Phasenwechsel beenden offene Punktzeilen.
MESSAGE-Blöcke und Skriptausgaben bleiben vollständig; Punkte werden niemals in
Skriptausgabe oder Rohlogs eingefügt. JSON bleibt ohne menschliche Zusatzdaten.
Farben, kurze menschliche Kennungen und vorhandene Exitcode-Verträge bleiben.
Kleine bisher kompakte Konfigurations-/Kontextbefehle erhalten Detailbeobachtung
nur bei --verbose. Es werden keine automatisierten Konsolenausgabetests ergänzt.


## 30. Neutrale Application-Beobachtung (OFF-PLAN COMPACT-CORE)

Application kennt keine ConsolePresentation, PresentedFile oder Konsolenparameter.
RequestStarted, RepositoryResolved und ScriptPrepared sind unveränderliche
interne Fakten. Repository-Kennungen bleiben vollständig. Aktivitätsereignisse
markieren Identifikatoren für die optionale Kürzung ausschließlich im UI-Adapter.
Die CLI bindet den Beobachter an den Request; verschachtelte und parallele
Aufrufe dürfen keinen Beobachterzustand verlieren oder teilen.

Ein fehlender Beobachter ist still. Ein optionaler Beobachterfehler verändert
keine Entscheidung; KeyboardInterrupt bleibt ausdrücklich nicht unterdrückt.
Skriptausgabe erfordert ein explizites Ausgabeziel und wird unabhängig erfasst.
Interaktive Dateiauswahl gehört zur CLI; Application akzeptiert nur eine explizite
Auswahlfunktion und prüft deren Ergebnis gegen die angebotenen Kandidaten.
Mehrere Kandidaten ohne Auswahlfunktion ergeben einen Fehler statt eines Prompts.
Dieser Vorbereitungsstand führte noch keine öffentliche Python-API oder neue
Versionsnummer ein; die additive Weiterentwicklung folgt in Abschnitt 32.


## 31. Fachliche Fehler und kompatible Statuscodes (OFF-PLAN COMPACT-CORE)

PatchHarborError enthält einen FailureReason statt eines CLI-Exitcodes.
PrimaryResult und RunToolError speichern ebenfalls fachliche Fehlergründe;
Application trifft keine Entscheidungen anhand von process_exit_code.

Die zentrale reine Abbildung in exit_status.py bedient CLI und die bestehenden
JSON-/Result-Serializer. Die Zahlen bleiben in allen bisherigen maschinenlesbaren
Formaten erhalten, auch bei Aufrufen ohne CLI. Diese Serialisierungsgrenze ist
kein zweiter fachlicher Kontrollfluss. Die bestehende Abschlusspriorität bleibt:
Primärfehler behalten Vorrang; ausschließlich eine erfolgreiche Primäraktion mit
fehlgeschlagenem Result ergibt den bisherigen Result-Bundle-Fehlerstatus.
Native Skript-Exitcodes sind Prozessdaten, keine PatchHarbor-Fehlerkategorien.
Insbesondere darf ein Skript-Exit 124 oder 130 nicht als Tool-Timeout bzw.
Tool-Unterbrechung umgedeutet werden. Version und öffentliche CLI bleiben gleich.


## 32. Öffentliche Python-API 1.2.0

Der additive Vertrag steht in `planning/1.2.0/specification.md`; der Ablauf in
`planning/1.2.0/commit-plan.md`, die Imports und Anwendungsbeispiele in
`docs/python-api.md`. Die öffentliche synchrone API, die Haupt-CLI und der Watcher
verwenden dieselbe Application. Die Paketversion ist 1.2.0; alle bestehenden
Wire-Verträge, CLI-Exitcodes, Paketmarker und Fingerprints bleiben unverändert.
API-Ergebnisse verwenden vollständige Kennungen; keine Konsolentexte werden geparst.

`patchharbor.api` ist der unterstützte Import-Namensraum. Die dokumentierten
Operationen, Rückgabefakten und Fehlersemantik bleiben grundsätzlich innerhalb
1.x kompatibel. Die ausdrücklich beauftragte repositorylokale Revision dieser
1.2.0-Entwicklung ersetzt jedoch die frühere globale Konfigurationssemantik ohne
Fallback. Private Module und diagnostische Texte sind kein öffentlicher
Erweiterungsvertrag.
Standardaufrufe sind still. Fachliche Resultate und Exceptions werden wiederverwendet;
explizite OutputStreams und request-lokale Beobachter sind unabhängig von der CLI.

`configuration(repository=".", *, revalidate=False)` liest die ausgewählte
registrierte lokale Konfiguration. Die drei `configure_*`-Setter besitzen
keyword-only `repository="."`. `ConfigurationResult.exchange_directory` ist
`Path | None`; gewöhnliches Lesen prüft Schema/Identität, `revalidate=True`
zusätzlich den verfügbaren physischen Exchange und die Registry-Pfadpolitik.
Keine API-Funktion erzeugt fehlende lokale Metadaten außer echter Erstregistrierung.

Der Watcher prüft beim Start `api.repositories()` und startet pro Poll weiterhin
einen separaten Prozess, der `api.apply_next()` direkt aufruft. Core lädt lokale
Konfigurationen frisch, fasst physisch gleiche Exchange-Pfade zusammen und
wendet die Repository-/Verzeichnisbindung an. Signal-/Stop-Verhalten,
automatische Nichtwiederholung fehlgeschlagener Identitäten, Replay und
beweisgebundene Recovery bleiben unverändert.

Wheel und sdist enthalten die API, ihren Typing-Marker und API-Dokumentation.
Release-Gates prüfen API-Verträge, installierte Artefakte, CLI, Watcher und bestehende
Sicherheits-/Plattformfunktionen. Konsolendarstellung wird nicht neu getestet.
Tags oder Veröffentlichungen folgen nicht automatisch aus der Versionsanhebung;
der neue Commit benötigt weiterhin die vollständige lokale und externe CI-Freigabe.


## 33. Parallele Entwicklungstests (TEST-PARALLEL)

Der Entwicklungsvertrag in `planning/test-parallel/specification.md` und der
zugehörige W/R/C-Plan ergänzen diese Spezifikation, ohne den Produktvertrag 1.2.0
zu verändern. pytest und pytest-xdist bleiben reine Entwicklungsabhängigkeiten.
`tools/run_tests.py` verwendet standardmäßig xdist `auto`, unterstützt explizite
Workerzahlen und `--serial`. `scripts/test.sh`, native CI und Docker verwenden
seine gemeinsame Policy. Das Produkt führt keinen Testscheduler ein.

Der Launcher prüft vollständige maschinenlesbare Ergebnisse im Controller,
auch ohne persistierte Berichte. Ein optionaler JSON-Nachweis wird ausschließlich
vom Controller atomar geschrieben. Sammlungen, Worker-Abschlussbelege und
Testphasen werden vollständig geprüft; fehlende Ergebnisse, unterschiedliche
Sammlungen, Worker-Abstürze und Setup-/Teardown-/Untertestfehler verhindern
Erfolg. Skips bleiben explizit und werden bei Referenzvergleichen berücksichtigt.
Collection-only ist kein bestandener Laufzeitnachweis.

Der Vollvergleich führt seriell/2/4/auto und zusätzliche Hash-Seeds mit stabiler
Quellen-/Interpreterbindung aus. Kein Ergebnisvergleich von Reihenfolge, Farbe,
Layout, Dauer, Zeitstempel oder Worker-Zuteilung. Prozess- und Dateisolation ist
Teil der Verhaltenstests. Keine neuen Darstellungs- oder Dokumentationstests.
Eine zusätzliche blockierende serielle CI-Lane bleibt erhalten; die bisherigen
OS-/Python-/PowerShell-Matrizen werden nicht reduziert.

Keine zusätzlichen künstlichen Test-/Suite-Timeouts. Das äußere Apply-Limit,
CI-Joblimits und fachliche Timeouttests bleiben eigenständige Verträge.
Eine W/R/C-Patchfolge wendet jeden Zwischenstand einzeln an und committet ihn
nur nach erfolgreichen Prüfungen. Bei Fehler bleiben vorherige Commits stehen.
Weder ein erzeugtes Paket noch lokale Tests allein bedeuten externe CI-Freigabe.


## 34. POSIX-Dateirechte bei Core-Payloads (POSIX-MODE)

Verbindliche Details: `planning/posix-mode/specification.md`.
`BundlePayload.unix_mode` transportiert optionale Unix-Berechtigungen aus
ZIP-Metadaten (`create_system == 3`, High-Word von `external_attr`). Fehlende
Unix-Metadaten ergeben bei neuen regulären Dateien 0644; sichere explizite Modi
werden unverändert übernommen (0755 für ausführbare Dateien). Ein High-Word von
0 bedeutet fehlende Metadaten; eine explizit typisierte reguläre Datei mit 0000
ist davon verschieden. Explizite 0600-Werte sind gültig, kein Default-Indikator.

Bei bestehenden POSIX-Dateien bleibt der aktuelle rwx-Modus erhalten, auch
0664/0666/0777. Dies respektiert lokale Rechte, ohne sie als allgemein sicher
zu bewerten. Bestandsmodi verbieten Sonderbits (07000); ZIP/API-Anfragen verbieten
zusätzlich Gruppen-/Andere-Schreibrechte (07022), auch bei bestehenden Zielen.
Beide prüfen Typ und Bitbereich. Keine automatische Reparatur, kein chmod-Sweep. Alle bekannten
Ziel-/Modefehler werden vor der ersten Payload-Mutation geprüft, auch im Dry-Run;
bei Mutation und vor Veröffentlichung wird frisch geprüft. Beobachtete Änderungen
während des Stagings führen zum Abbruch. Der Lock schützt kooperierende Prozesse,
nicht vor jeder denkbaren feindlichen Dateisystem-Race.

Der Filesystem-Adapter schreibt privat neben dem Ziel, flush/fchmod/fsync erfolgen
vor `os.replace`. Ein Mode-/Sync-/Replace-Fehler lässt diese Zieldatei unverändert;
Staging-Reste werden aufgeräumt, soweit das Betriebssystem dies zulässt. Bereits
erfolgreiche frühere Ersetzungen bleiben bei späterem Fehler erhalten. Keine
paketweite Rollback-Garantie. Symlinks, Junctions, Sondertypen und unsichere Pfade
bleiben verboten. Verzeichnis-Metadaten werden nicht als Dateipayload angewendet.

Ohne expliziten Modus behält der atomare Writer seine private Rechtepolitik für
Registry, Konfiguration und Laufzeitzustand. Windows validiert Paketmodi, bildet
sie aber nicht auf native ACLs oder Read-only-Flags ab. Eigentümer, ACLs und
Extended Attributes sind nicht Teil dieses Vertrags. Paketformat, Fingerprint
und globale Locks bleiben unverändert. Git speichert nicht alle POSIX-Modi;
bereits bestehendes 0600 wird deshalb nicht rückwirkend auf 0644 erweitert.

Entrypoints prüfen und nutzen vorhandene Core-Funktionen für Payloads,
Dateiersetzung, Pfadvalidierung, Registry/Zustand und Archive, statt diese selbst
nachzubauen. Fehlende wiederverwendbare Infrastruktur wird im Core ergänzt;
Tests/Commits und ihre Reihenfolge bleiben auftragsspezifische Orchestrierung.
Beim Selbstupgrade nutzt das erste W ausschließlich eine private Kopie desselben
W-Cores für seine Schreiboperationen, keine zweite Writer-Implementierung.

Für nachfolgende lokale Entwicklungs-/Patchläufe läuft die Vollsuite nur parallel.
Der vollständige serielle Referenzlauf gehört in CI. Die ausdrücklich bestätigte
Ausnahme bleibt dieses bereits geplante POSIX-W/R/C-Bundle; der Launcher behält
seine Referenzfunktion, CI-Workflows werden hierfür nicht geändert.
