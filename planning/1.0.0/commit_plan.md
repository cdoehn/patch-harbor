# Commit-Plan

## Ziel

PatchHarbor soll sich einfach und vollständig über `pipx` installieren und verwenden lassen.

Die Installation muss ein isoliertes Python-Environment automatisch erstellen und verwalten. Benutzer dürfen weder selbst ein virtuelles Environment anlegen noch eines aktivieren müssen. Nach der Installation soll der PatchHarbor-CLI-Befehl unmittelbar in einer normalen Shell verfügbar sein.

Dieser Commit umfasst die vollständige pipx-Unterstützung einschließlich Paketkonfiguration, CLI-Bereitstellung, Dokumentation und automatisierter Tests.

---

## Commit 1: pipx-Unterstützung vollständig bereitstellen

### Commit-Betreff

```text
feat(packaging): add complete pipx installation support
```

### Ziel des Commits

Der Commit stellt sicher, dass PatchHarbor über `pipx` installiert, aktualisiert, ausgeführt und deinstalliert werden kann.

Der typische Installationsablauf soll einfach sein:

```bash
pipx install .
patchharbor --help
```

Nach einer Veröffentlichung in einem unterstützten Python-Paketindex soll außerdem folgende Installation möglich sein:

```bash
pipx install patch-harbor
```

Eine manuelle Aktivierung des von pipx verwalteten Python-Environments darf zu keinem Zeitpunkt erforderlich sein.

### Benutzererlebnis

Benutzer sollen lediglich `pipx` installieren und anschließend den Installationsbefehl für PatchHarbor ausführen müssen.

`pipx` übernimmt automatisch:

* das Erstellen eines isolierten Python-Environments;
* die Installation von PatchHarbor und seinen Laufzeitabhängigkeiten;
* die Bereitstellung des ausführbaren CLI-Befehls;
* die Verwaltung des Environments;
* spätere Aktualisierungen;
* die vollständige Deinstallation.

Nach erfolgreicher Installation muss der CLI-Befehl direkt in einer neuen oder bestehenden Shell aufrufbar sein, sofern das pipx-Bin-Verzeichnis bereits im `PATH` liegt.

Es darf nicht erforderlich sein:

* ein eigenes `venv` anzulegen;
* ein Environment mit `source .../bin/activate` zu aktivieren;
* Python-Pfade manuell zu konfigurieren;
* Module mit `python -m ...` aufzurufen;
* interne Installationsverzeichnisse von pipx zu kennen;
* zusätzliche projektspezifische Installationsskripte auszuführen.

### Umfang

Der Commit umfasst alle Änderungen, die für eine zuverlässige pipx-Installation notwendig sind.

#### 1. Paketmetadaten prüfen und ergänzen

Die vorhandene Python-Paketkonfiguration wird geprüft und so angepasst, dass das Repository als installierbares Python-Paket verwendet werden kann.

Dabei sind insbesondere zu prüfen:

* Paketname;
* Paketversion;
* unterstützte Python-Versionen;
* Laufzeitabhängigkeiten;
* Build-System;
* Paketquellen und Package-Discovery;
* Einbindung erforderlicher Paketdaten;
* CLI-Einstiegspunkt;
* Verhalten bei Installation aus einem lokalen Checkout;
* Verhalten beim Bau eines Wheels.

Die vorhandene Packaging-Struktur und die bestehenden Projektkonventionen sind beizubehalten. Es soll kein zweites konkurrierendes Packaging-System eingeführt werden.

#### 2. CLI-Einstiegspunkt bereitstellen

Die Paketmetadaten müssen einen stabilen Konsolen-Einstiegspunkt bereitstellen.

Nach der Installation muss mindestens folgender Befehl funktionieren:

```bash
patchharbor --help
```

Der Einstiegspunkt soll die bereits vorhandene CLI-Implementierung verwenden. Es darf keine zweite, von der bestehenden CLI getrennte Befehlsimplementierung entstehen.

Der CLI-Einstiegspunkt muss:

* ohne aktiviertes Environment ausführbar sein;
* bei erfolgreichem Aufruf den korrekten Exit-Code liefern;
* die vorhandene Hilfeausgabe verwenden;
* die bestehende Argumentverarbeitung respektieren;
* installierte Ressourcen und Module korrekt finden;
* unabhängig vom aktuellen Arbeitsverzeichnis funktionieren.

#### 3. Lokale pipx-Installation unterstützen

Die Installation aus dem Repository muss unterstützt werden:

```bash
pipx install .
```

Für Entwicklungs- oder Testzwecke darf zusätzlich dokumentiert werden:

```bash
pipx install --force .
```

Eine vorhandene Installation soll über die normalen pipx-Funktionen verwaltet werden können.

Beispiele:

```bash
pipx list
pipx upgrade patch-harbor
pipx reinstall patch-harbor
pipx uninstall patch-harbor
```

Es dürfen keine projektspezifischen Sonderbefehle erforderlich sein, wenn die entsprechenden Standardfunktionen von pipx ausreichen.

#### 4. Installation aus einem Paketindex vorbereiten

Die Paketmetadaten müssen so gestaltet sein, dass nach einer Veröffentlichung eine Installation über den Paketnamen möglich ist:

```bash
pipx install patch-harbor
```

Die Veröffentlichung selbst ist nicht Bestandteil dieses Commits.

Der Commit darf insbesondere nicht behaupten, dass das Paket bereits auf PyPI oder einem anderen Paketindex verfügbar ist, solange dies nicht tatsächlich der Fall ist.

#### 5. Dokumentation aktualisieren

Die Hauptdokumentation erhält einen klar sichtbaren Abschnitt zur empfohlenen Installation mit pipx.

Die Dokumentation soll mindestens folgende Punkte enthalten:

##### Voraussetzungen

* unterstützte Python-Version;
* installierbares beziehungsweise vorhandenes `pipx`;
* gegebenenfalls einmalige Einrichtung des pipx-Bin-Verzeichnisses.

Beispiel:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Dabei muss darauf hingewiesen werden, dass nach `ensurepath` je nach Shell eine neue Sitzung erforderlich sein kann.

##### Installation aus dem Repository

```bash
git clone <repository-url>
cd <repository-directory>
pipx install .
```

Repository-URL und Verzeichnisname dürfen nur dann konkret eingetragen werden, wenn sie aus dem Repository eindeutig hervorgehen.

##### Verwendung

```bash
patchharbor --help
```

Die Dokumentation muss ausdrücklich erklären, dass kein Python-Environment aktiviert werden muss.

##### Aktualisierung

Für eine veröffentlichte Paketversion:

```bash
pipx upgrade patch-harbor
```

Für eine erneute Installation aus einem lokalen Checkout kann ein passender pipx-Befehl dokumentiert werden, beispielsweise:

```bash
pipx install --force .
```

Die tatsächlich empfohlenen Befehle müssen mit dem Paketnamen und dem unterstützten Installationsweg übereinstimmen.

##### Deinstallation

```bash
pipx uninstall patch-harbor
```

##### Fehlerbehebung

Die Dokumentation soll eine kurze, einfache Hilfestellung enthalten, falls der Befehl nach der Installation nicht gefunden wird.

Beispiel:

```bash
pipx ensurepath
```

Danach soll eine neue Shell geöffnet oder die Shell-Konfiguration neu geladen werden.

Die Fehlerbehebung darf nicht in eine komplizierte manuelle Aktivierung oder Manipulation des pipx-Environments ausweichen.

#### 6. Automatisierten pipx-Smoke-Test ergänzen

Es wird ein fokussierter automatisierter Test ergänzt, der die Installation in einer isolierten Umgebung prüft.

Der Test muss nach Möglichkeit:

1. ein temporäres pipx-Home-Verzeichnis verwenden;
2. ein temporäres pipx-Bin-Verzeichnis verwenden;
3. das aktuelle Repository beziehungsweise ein daraus gebautes Paket installieren;
4. den erzeugten CLI-Befehl direkt ausführen;
5. `patchharbor --help` prüfen;
6. den Exit-Code prüfen;
7. relevante Bestandteile der Hilfeausgabe prüfen;
8. sicherstellen, dass keine Aktivierung eines Environments erfolgt;
9. außerhalb des Repository-Arbeitsverzeichnisses ausführbar sein;
10. keine dauerhaften Änderungen am Benutzerprofil oder am realen pipx-Verzeichnis vornehmen.

Geeignete isolierte Umgebungsvariablen sind abhängig von der vorhandenen Teststruktur zu verwenden, beispielsweise:

```bash
PIPX_HOME=<temporäres-verzeichnis>
PIPX_BIN_DIR=<temporäres-bin-verzeichnis>
```

Der Test darf keine reale Benutzerinstallation überschreiben.

Falls `pipx` im Testsystem nicht verfügbar ist, muss der Test entsprechend den bestehenden Projektregeln entweder:

* mit einer klaren Begründung übersprungen werden; oder
* als gesonderter Packaging- beziehungsweise Integrationstest ausgeführt werden.

Ein fehlendes `pipx` darf nicht fälschlich als bestandener Installationstest gemeldet werden.

#### 7. Packaging- und CLI-Tests ausführen

Zusätzlich zum pipx-Smoke-Test sind die vorhandenen relevanten Tests auszuführen.

Mindestens zu prüfen sind, soweit im Repository verfügbar:

* bestehende CLI-Tests;
* Packaging-Tests;
* Installation aus einem gebauten Wheel;
* Aufruf des installierten Konsolenbefehls;
* Hilfeausgabe;
* Paketimport;
* Test der erforderlichen Paketdaten;
* Build des Source-Archivs;
* Build des Wheels.

Mögliche Prüfungen sind:

```bash
python -m build
python -m pytest <fokussierte-tests>
pipx install <gebautes-wheel>
patchharbor --help
```

Die endgültigen Befehle müssen aus der tatsächlichen Repository-Struktur, den vorhandenen Werkzeugen und den Projektregeln abgeleitet werden.

### Nicht-Ziele

Dieser Commit umfasst ausdrücklich nicht:

* Veröffentlichung auf PyPI oder einem anderen Paketindex;
* Einrichtung von Zugangsdaten für Paketveröffentlichungen;
* automatisierte Release-Pipelines, sofern sie nicht bereits zwingend für die vorhandenen Tests benötigt werden;
* Einführung eines neuen Versionsschemas;
* allgemeine Umstrukturierung des Quellcodes;
* Neuentwicklung der CLI;
* Umbenennung vorhandener öffentlicher Befehle;
* Migration auf ein anderes Build-System ohne technische Notwendigkeit;
* Unterstützung zusätzlicher Betriebssysteme außerhalb des bestehenden Projektumfangs;
* Änderungen an nicht betroffenen PatchHarbor-Funktionen;
* allgemeine Bereinigung oder Formatierung nicht betroffener Dateien.

### Betroffene Komponenten

Die konkreten Pfade werden nach der Repository-Inspektion festgelegt.

Voraussichtlich betroffen sind:

* Python-Paketmetadaten, beispielsweise `pyproject.toml`;
* vorhandene CLI-Einstiegspunkte;
* Installationsabschnitt der README;
* gegebenenfalls eine separate Installationsdokumentation;
* Packaging- oder Integrationstests;
* CI-Konfiguration, sofern der pipx-Smoke-Test dort eingebunden werden muss;
* Commit-Plan beziehungsweise zugehörige Planungsdokumentation.

Es dürfen nur Dateien geändert werden, die für diesen Commit erforderlich sind.

### Kompatibilitätsanforderungen

Die Änderung muss:

* die bestehende CLI-Schnittstelle erhalten;
* bestehende Installationswege möglichst nicht beschädigen;
* die im Projekt unterstützten Python-Versionen respektieren;
* unter Linux funktionieren;
* nicht von einem aktivierten virtuellen Environment abhängen;
* nicht von einem bestimmten Benutzerpfad abhängen;
* nicht vom aktuellen Arbeitsverzeichnis abhängen;
* keine interaktive Eingabe während automatisierter Tests erfordern;
* mit der vorhandenen Build- und Paketstruktur kompatibel bleiben.

### Akzeptanzkriterien

Der Commit gilt als abgeschlossen, wenn alle folgenden Kriterien erfüllt sind:

1. Das Repository kann als Python-Paket gebaut werden.
2. Eine lokale Installation über `pipx install .` ist möglich.
3. pipx erstellt und verwaltet das isolierte Python-Environment automatisch.
4. Es muss kein Environment manuell aktiviert werden.
5. Nach der Installation ist `patchharbor` als Konsolenbefehl verfügbar.
6. `patchharbor --help` wird erfolgreich ausgeführt.
7. Der CLI-Aufruf funktioniert außerhalb des Repository-Verzeichnisses.
8. Die erforderlichen Laufzeitabhängigkeiten werden automatisch installiert.
9. Erforderliche Paketdaten sind in der Installation enthalten.
10. Die Dokumentation beschreibt Installation, Verwendung, Aktualisierung und Deinstallation.
11. Die Dokumentation erklärt ausdrücklich, dass keine Environment-Aktivierung erforderlich ist.
12. Ein isolierter automatisierter pipx-Smoke-Test deckt den Installationsweg ab.
13. Bestehende relevante Tests bleiben erfolgreich.
14. Der Build von Wheel und gegebenenfalls Source-Archiv ist erfolgreich.
15. Der Commit enthält keine unabhängigen Refactorings oder späteren Aufgaben.
16. Der Commit erzeugt genau den vorgesehenen Git-Commit.

### Validierung

Nach der Implementierung sollen mindestens folgende Prüfungen durchgeführt werden, sofern die benötigten Werkzeuge verfügbar sind:

```bash
python -m build
python -m pytest <relevante-tests>
```

Zusätzlich wird die pipx-Installation in isolierten temporären Verzeichnissen geprüft.

Sinngemäß:

```bash
tmp_dir="$(mktemp -d)"
export PIPX_HOME="$tmp_dir/pipx-home"
export PIPX_BIN_DIR="$tmp_dir/bin"

pipx install .
"$PIPX_BIN_DIR/patchharbor" --help
```

Danach soll zusätzlich geprüft werden, dass der Befehl aus einem anderen Arbeitsverzeichnis funktioniert.

Sinngemäß:

```bash
cd /
"$PIPX_BIN_DIR/patchharbor" --help
```

Die temporären Testdaten müssen nach dem Test entfernt werden.

Die tatsächlich ausgeführten Befehle und Ergebnisse werden bei der Übergabe vollständig und wahrheitsgemäß dokumentiert.

### Risiken

#### Unvollständige Paketdaten

PatchHarbor kann lokal aus dem Quellverzeichnis funktionieren, aber nach der Installation erforderliche Vorlagen, Schemas oder andere Ressourcen nicht finden.

Deshalb müssen Paketdaten und Ressourcenpfade ausdrücklich geprüft werden.

#### Abweichender Paket- und CLI-Name

Der Distributionsname kann beispielsweise `patch-harbor` lauten, während der Konsolenbefehl `patchharbor` heißt.

Dokumentation, Metadaten und Tests müssen diese Unterscheidung konsistent behandeln.

#### Installation funktioniert nur im Repository-Verzeichnis

Relative Pfade können dazu führen, dass die CLI nur aus dem Checkout heraus funktioniert.

Der Smoke-Test muss den Aufruf deshalb außerhalb des Repository-Verzeichnisses prüfen.

#### Versehentliche Nutzung des Benutzer-pipx-Verzeichnisses

Tests dürfen keine vorhandenen Benutzerinstallationen verändern.

Alle pipx-Testpfade müssen isoliert und temporär sein.

#### Nicht veröffentlichtes Paket

Eine lokale pipx-Installation kann bereits funktionieren, obwohl `pipx install patch-harbor` noch nicht verfügbar ist.

Die Dokumentation muss klar zwischen lokaler Installation und Installation einer veröffentlichten Version unterscheiden.

#### Verschmutzter Arbeitsbaum

Vor der Änderung muss sichergestellt werden, dass keine fremden oder bereits vorhandenen Änderungen versehentlich in den Commit aufgenommen werden.

Der Commit darf ausschließlich die pipx-Unterstützung enthalten.

### Geplantes Ergebnis

Nach diesem Commit steht ein einfacher, dokumentierter Installationsweg zur Verfügung:

```bash
pipx install .
patchharbor --help
```

Das von pipx verwaltete Python-Environment bleibt für den Benutzer vollständig transparent. Eine Aktivierung mit `source`, `activate` oder einem vergleichbaren Befehl ist nicht erforderlich.

Der Commit liefert die Paketkonfiguration, den CLI-Zugriff, die Dokumentation und die automatisierte Absicherung dieses Installationswegs als eine zusammenhängende Änderung.
---

## Commit 2: Entwicklungsbefehle gegen Hänger absichern

### Commit-Betreff

    feat(tooling): add timeout guard for development commands

### Ziel des Commits

Dieser Commit nimmt `scripts/run_with_timeout.sh` als generisches Linux-Werkzeug
auf, dokumentiert seine Verwendung in der README und ergänzt eine verbindliche
Workflow-Regel für potenziell lang laufende Entwicklungsbefehle.

### Umfang

- Timeout-Werkzeug mit begrenzten Wiederholungen aufnehmen;
- README mit Optionen, Beispielen und Timeout-Eskalation ergänzen;
- Workflow-Regel für Tests, Builds, Linting, Packaging, Installation und
  Smoke-Tests ergänzen;
- fokussierte Tests für Erfolg, normale Fehler, Timeouts, Dokumentation und
  Regeldefinition ergänzen.

### Nicht-Ziele

- keine Änderung am PatchHarbor-Runner;
- keine unbegrenzten Wiederholungen oder automatische Endlosschleifen;
- keine Wiederholung normaler Programmfehler;
- keine Änderungen an Packaging- oder CLI-Verträgen.

### Akzeptanzkriterien

1. `scripts/run_with_timeout.sh` ist ausführbar und besteht `bash -n`.
2. Erfolgreiche Befehle werden einmal ausgeführt und liefern Exit-Code 0.
3. Normale Fehler werden unverändert und ohne Neustart zurückgegeben.
4. Timeout-Fälle werden höchstens entsprechend `--attempts` neu gestartet.
5. Die README beschreibt Parameterwahl und einen erneuten Lauf mit größerem,
   weiterhin begrenztem Timeout.
6. Die aktivierte Workflow-Regel verlangt das Werkzeug für potenziell lang
   laufende Befehle und verbietet unbegrenzte Neustarts.
7. Die fokussierten Tests werden selbst über `run_with_timeout.sh` ausgeführt.
8. Der Commit enthält keine unabhängigen Refactorings.

