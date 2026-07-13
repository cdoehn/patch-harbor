# PatchHarbor – Spezifikation und Commit-Plan

**Empfohlener Dokumentname:** PatchHarbor – Spezifikation und Commit-Plan  
**Empfohlener Dateiname:** `patchharbor-spezifikation-und-commit-plan.md`  
**Status:** verbindliche Planungsbasis für Version 1  
**Projektname, Kommando und Marker:** `PatchHarbor`, `patchharbor`, `# PATCHHARBOR`

Der Name **Commit-Plan** allein wäre zu eng, weil dieses Dokument zuerst die Produktspezifikation und danach den Umsetzungsplan enthält. Der Titel **Spezifikation und Commit-Plan** beschreibt den Inhalt eindeutig.

---

## 1. Zweck dieses Dokuments

Dieses Dokument ist die gemeinsame Arbeitsgrundlage für Architektur, Implementierung, Tests und Review. Es enthält:

1. die bereinigte Spezifikation von PatchHarbor,
2. die verbindlichen Architekturgrenzen,
3. die Teststrategie,
4. vier nummerierte Meilensteine mit Definition of Done,
5. alle Steps innerhalb der Meilensteine,
6. für jeden Step genau drei Commits in den Phasen **work**, **right** und **clean**.

Nach jedem Meilenstein wird der verbleibende Plan geprüft. Notwendige Anpassungen werden klein und gezielt vorgenommen. Der Plan wird nicht vollständig neu geschrieben.

---

## 2. Nummerierungs- und Commit-Konvention

### 2.1 Hierarchie

- Meilensteine werden mit normalen Zahlen nummeriert: `1`, `2`, `3`, `4`.
- Steps werden innerhalb des Meilensteins mit kleinen Buchstaben nummeriert: `a`, `b`, `c` und so weiter.
- Commits bilden die unterste Ebene und erhalten den Phasenbuchstaben `W`, `R` oder `C`.

Beispiele:

- `1.a.W`
- `1.a.R`
- `1.a.C`
- `1.b.W`
- `1.b.R`
- `1.b.C`

### 2.2 Bedeutung der Phasen

| Kürzel | Phase | Zweck |
|---|---|---|
| `W` | work | Das Verhalten vertikal und minimal zum Laufen bringen. Der passende Test gehört in denselben Commit. |
| `R` | right | Verantwortlichkeiten, Fehlerbehandlung, Datenmodelle und Abhängigkeiten fachlich richtig schneiden. |
| `C` | clean | Vereinfachen, Doppeltes entfernen, Namen verbessern und unnötigen Ballast löschen. |

`R` steht für **right**, nicht für write.

### 2.3 Regeln für jeden Commit

- Jeder Commit hat genau eine erkennbare Absicht.
- Nach jedem Commit ist das Repository lauffähig und die bis dahin geltende Testsuite grün.
- Ein `W`-Commit enthält Feature und passenden Verhaltenstest gemeinsam.
- Ein `R`-Commit darf strukturieren und Fehler korrigieren, aber keinen verdeckten Feature-Sprung enthalten.
- Ein `C`-Commit vereinfacht und entfernt Komplexität. Er führt grundsätzlich kein neues Produktverhalten ein.
- Es gibt keine leeren Pflicht-Commits. Die Steps sind so geschnitten, dass jede Phase eine sinnvolle Änderung enthält.
- Commit-Nachrichten beginnen mit der Kennung, zum Beispiel `2.c.W ZIP-Fallback und Archiv-Reihenfolge implementieren`.

---

# Teil A – Produktspezifikation

## 3. Produktzweck

PatchHarbor ist ausschließlich ein kontrollierter Runner für von einer KI erzeugte Skripte.

PatchHarbor übernimmt ein Skript, erkennt das PatchHarbor-Format, liest optionale Informationen und übertragene Dateien, bereitet diese vor und führt das Skript aus.

PatchHarbor ist kein Testwerkzeug, kein Git-Werkzeug und kein Build-System.

### 3.1 PatchHarbor macht

- Skripte aus unterstützten Quellen übernehmen,
- den exakten PatchHarbor-Marker prüfen,
- optionale Metadaten und Messages best effort erkennen,
- optionale FILE-Blöcke sicher vorbereiten,
- Skripte mit Timeout ausführen,
- Prozess und Kindprozesse bei Timeout oder Abbruch beenden,
- Status, Messages, Dateien und begrenzte Skriptausgabe anzeigen,
- optional den vollständigen Output in eine temporäre Logdatei schreiben,
- den festgelegten Exit-Code an die aufrufende Umgebung zurückgeben.

### 3.2 PatchHarbor macht ausdrücklich nicht

- keine Tests des Zielprojekts ausführen,
- keine Git-Commits, Branches oder sonstigen Git-Operationen durchführen,
- keine Builds oder Linter starten,
- keine Patches inhaltlich bewerten,
- keine interaktiven Skripte unterstützen,
- keinen Ordner dauerhaft überwachen,
- keinen Hintergrunddienst oder Daemon betreiben,
- keine KI-Anleitung im Programm verwalten,
- in Version 1 keinen Save-Modus anbieten,
- in Version 1 keine Clipboard- oder WebSocket-Schnittstelle öffentlich anbieten.

---

## 4. Lebenszyklus und Arbeitsverzeichnis

Ein Aufruf verarbeitet genau eine Quelle und endet anschließend.

Der Ablauf lautet:

**Start → Quelle übernehmen → Skriptformat prüfen → optionale Nutzdaten vorbereiten → ausführen → Ergebnis anzeigen → Prozess beenden**

Das Skript wird immer im aktuellen Arbeitsverzeichnis ausgeführt, in dem der Nutzer PatchHarbor gestartet hat. Der Speicherort der Eingabedatei, eines ZIP-Archivs oder einer temporären Skriptdatei ändert das Arbeitsverzeichnis nicht.

Relative Pfade im Skript beziehen sich deshalb immer auf dieses aktuelle Arbeitsverzeichnis.

Skripte aus Pipe oder ZIP werden bei Bedarf sicher im System-Temp-Verzeichnis zwischengespeichert und anschließend gelöscht. Ein Skript darf sich nicht darauf verlassen, dass sein eigener Dateipfad im Projektverzeichnis liegt.

---

## 5. Kommandozeile, Installation und Dokumentation

### 5.1 Öffentliche CLI von Version 1

Der öffentliche Hauptaufruf lautet:

`patchharbor fs run [PFAD]`

Unterstützte Optionen:

- `--timeout SEKUNDEN` mit dem Standardwert 300,
- `--log` für die vollständige temporäre Logdatei,
- `--plain` für einfache fortlaufende Textausgabe,
- `--no-color` für Ausgabe ohne Farben,
- die üblichen argparse-Hilfen wie `--help`.

Ist kein Pfad angegeben und die Standardeingabe enthält eine Pipe, wird das Skript vollständig aus der Standardeingabe gelesen.

Ist kein Pfad angegeben und die Standardeingabe ist ein normales Terminal, endet PatchHarbor mit einem klaren Fehler wegen fehlender Eingabe.

### 5.2 Noch nicht öffentliche Quellen

Clipboard und WebSocket werden als zukünftige Eingabequellen in der Architektur berücksichtigt, aber nicht implementiert und nicht im Help-Screen angezeigt.

Die Vorbereitung besteht nur aus einer klaren internen Quellengrenze. Es gibt in Version 1 kein Plugin-System und keine dynamische Modulregistrierung.

### 5.3 Installation

Ziel ist die globale Installation über pipx, ohne dass der Nutzer eine virtuelle Umgebung selbst verwalten muss.

Nach Veröffentlichung des Pakets lautet der Zielbefehl `pipx install patchharbor`.

Der Konsolenbefehl ist anschließend überall als `patchharbor` verfügbar.

### 5.4 Dokumentation

- Die Installationsanleitung steht kurz im README.
- Die komplette Bedienungsdokumentation steht in den argparse-Help-Screens.
- Es gibt in Version 1 kein zusätzliches Benutzerhandbuch, Wiki oder Tutorial.
- Nicht implementierte Funktionen werden nicht dokumentiert und nicht im Help-Screen angeboten.

---

## 6. Skripterkennung und Format

### 6.1 Pflichtmarker

Ein Skript ist nur gültig, wenn es mindestens eine vollständige Zeile enthält, die exakt lautet:

`# PATCHHARBOR`

Regeln:

- Die Zeile beginnt am ersten Zeichen der Zeile.
- Es gibt keine führenden Leerzeichen.
- Groß- und Kleinschreibung sind fest.
- Die Zeile enthält keinen Zusatz und keine Version.
- Eine MESSAGE-, FILE- oder META-Zeile gilt nicht als Pflichtmarker.
- Zeilenenden von Linux und Windows werden beim Prüfen normalisiert.

Fehlt der Pflichtmarker, wird das Skript nicht ausgeführt.

### 6.2 Optionale Metadaten

Kleine Informationen können als optionale META-Zeilen übertragen werden.

Das Format lautet sinngemäß:

`# PATCHHARBOR META name=wert`

Metadaten sind rein informativ. Sie verändern weder Timeout noch Interpreter noch Umgebungsvariablen oder anderes Ausführungsverhalten.

Fehlerhafte META-Zeilen führen höchstens zu einer Warning und werden ansonsten ignoriert.

### 6.3 Optionale Messages

Es dürfen mehrere benannte Message-Blöcke enthalten sein.

Ein Message-Name besteht aus Großbuchstaben, Kleinbuchstaben, Zahlen und Punkten. Er enthält keine Leerzeichen.

Anfang und Ende eines Blocks enthalten denselben Namen. Der Text dazwischen besteht aus kommentierten UTF-8-Zeilen. Beim Lesen wird das definierte Kommentarpräfix entfernt.

Messages sind ausschließlich Informationen für den Menschen oder eine spätere externe Weiterverarbeitung. Sie steuern PatchHarbor nicht.

Ein unvollständiger, falsch benannter oder anderweitig beschädigter Message-Block wird vollständig verworfen. PatchHarbor zeigt eine Warning und führt das Skript trotzdem aus.

### 6.4 Optionale FILE-Blöcke

Es dürfen mehrere benannte FILE-Blöcke enthalten sein.

Anfang und Ende eines Blocks enthalten denselben Dateinamen. Der Inhalt besteht in Version 1 ausschließlich aus kommentiertem UTF-8-Text. PatchHarbor entfernt das definierte Kommentarpräfix und schreibt den verbleibenden Text als Datei.

Binärdaten oder bytegenau zu übertragende Inhalte werden vorher außerhalb von PatchHarbor als Base64-Text codiert. PatchHarbor erkennt oder decodiert Base64 nicht automatisch.

Ein beschädigter FILE-Block wird vollständig verworfen und als Warning angezeigt. Das Skript darf weiterlaufen, sofern kein formal gültiger FILE-Block beim tatsächlichen Schreiben scheitert.

Scheitert das Schreiben eines formal gültigen FILE-Blocks, wird das Skript nicht gestartet.

---

## 7. Sichere Verarbeitung übertragener Dateien

### 7.1 Erlaubte Dateinamen

FILE-Blöcke dürfen nur einfache Dateinamen enthalten, keine Pfade.

Erlaubt sind ausschließlich:

- Buchstaben von A bis Z und a bis z,
- Ziffern von 0 bis 9,
- Punkt,
- Unterstrich,
- Bindestrich.

Zusätzliche Regeln:

- Länge zwischen 1 und 128 Zeichen,
- nicht nur Punkt oder zwei Punkte,
- kein Schrägstrich und kein Backslash,
- kein absoluter oder relativer Pfad,
- kein abschließender Punkt oder abschließendes Leerzeichen,
- keine reservierten Windows-Gerätenamen wie CON, PRN, AUX, NUL, COM1 bis COM9 und LPT1 bis LPT9, auch nicht mit Dateiendung,
- vorhandene symbolische Links und andere nicht reguläre Ziele werden nicht überschrieben.

Ein unzulässiger Name macht den gesamten FILE-Block ungültig. Der Block wird verworfen und als Warning angezeigt.

### 7.2 Schreiben und Überschreiben

- FILE-Blöcke werden vor der jeweiligen Skriptausführung geschrieben.
- Vorhandene reguläre Dateien werden ohne Nachfrage überschrieben.
- Jede Datei wird zunächst vollständig in eine sichere temporäre Datei im selben Verzeichnis geschrieben.
- Erst danach wird die Zieldatei atomar ersetzt.
- PatchHarbor legt keine Backups an.
- Version 1 bietet keine vollständige Transaktion über mehrere FILE-Blöcke. Jeder einzelne Dateiaustausch ist atomar.
- Scheitert ein tatsächlicher Schreibvorgang, startet das Skript nicht.

### 7.3 Größen- und Ressourcenbudget

Unbegrenzte Eingaben werden nicht unterstützt. Die Anfangswerte sind zentrale Konstanten und können nach echten Nutzungserfahrungen angepasst werden.

Empfohlene Anfangswerte:

- Warning ab 10 MiB für einen einzelnen Skript- oder FILE-Inhalt,
- höchstens 256 MiB pro direkter Eingabe oder ZIP-Eintrag,
- höchstens 512 MiB unkomprimierte Gesamtdaten eines ZIP-Archivs,
- höchstens 1.000 ZIP-Einträge.

Eine Überschreitung eines harten Budgets führt zu einem klaren Tool-Fehler vor der Ausführung. Die Warning-Schwelle allein verhindert die Verarbeitung nicht.

---

## 8. Dateisystemquelle

### 8.1 Einzelne Datei

Eine einzelne Datei wird zuerst als direktes UTF-8-Skript geprüft.

Wird kein gültiger Pflichtmarker gefunden oder ist die Datei nicht als Text lesbar, versucht PatchHarbor die Datei als ZIP-Archiv zu öffnen.

Ist die Datei weder ein gültiges PatchHarbor-Skript noch ein verarbeitbares ZIP mit gültigen Skripten, endet der Aufruf mit einem klaren Fehler.

Der Dateiname und die Dateiendung sind für die Skripterkennung unerheblich.

### 8.2 Ordner

Ein Ordner wird genau einmal gescannt. Er wird nicht überwacht.

Regeln:

- nicht rekursiv,
- nur reguläre Dateien,
- symbolische Links werden ignoriert,
- Kandidaten werden nach Änderungszeit sortiert, neueste zuerst,
- bei identischer Änderungszeit dient der Dateiname als stabiler zweiter Sortierschlüssel,
- die Auswahl erfolgt mit einer ab eins gezählten Zahl aus ASCII-Ziffern,
- bei genau einem Kandidaten wird dieser automatisch gewählt,
- bei mehreren Kandidaten muss der Nutzer genau einen Eintrag wählen,
- leere Eingabe bricht ohne automatische Auswahl ab,
- ungültige Eingabe wird erneut abgefragt, solange die Eingabe interaktiv möglich ist.

Nach Einführung des ZIP-Fallbacks gelten sowohl direkte PatchHarbor-Skripte als auch ZIP-Dateien mit mindestens einem gültigen PatchHarbor-Skript als Kandidaten.

### 8.3 ZIP-Datei

ZIP ist ein Transportformat, kein eigener Ausführungsmodus.

Regeln:

- Verzeichniseinträge, Links und andere nicht reguläre Einträge werden ignoriert.
- Verschachtelte ZIP-Archive werden in Version 1 nicht geöffnet.
- Alle regulären Dateieinträge werden in der im Archiv gespeicherten Reihenfolge geprüft.
- Nur Einträge mit dem exakten Pflichtmarker werden ausgeführt.
- Die Aussage alle Dateien probieren bedeutet alle Dateien prüfen, nicht markerlose Dateien blind ausführen.
- Mehrere gültige Skripte werden sequenziell in Archiv-Reihenfolge ausgeführt.
- Jedes Skript erhält sein eigenes Timeout.
- Beim ersten nicht erfolgreichen Skript wird abgebrochen.
- Der Exit-Code des zuletzt ausgeführten Skripts wird zurückgegeben.
- Enthält das Archiv kein gültiges Skript, endet PatchHarbor mit einem Tool-Fehler.
- Das Archiv wird möglichst streamend verarbeitet und nicht vollständig in das Projektverzeichnis entpackt.

### 8.4 Pipe und STDIN

Ist kein Pfad angegeben und STDIN ist eine Pipe, liest PatchHarbor den vollständigen Input einmalig ein.

Es gibt keinen Streaming-Befehlsdialog und kein interaktives Protokoll. Nach dem Einlesen durchläuft der Inhalt dieselbe Pipeline wie ein direktes Skript.

Die Standardeingabe des ausgeführten Kindprozesses bleibt geschlossen. Version 1 unterstützt ausschließlich nicht interaktive Skripte.

---

## 9. Interpreter und Ausführung

### 9.1 Unterstützte Interpreter

Version 1 unterstützt bewusst nur Bash und PowerShell.

- Linux ohne Shebang: Bash.
- Windows ohne Shebang: Windows PowerShell.
- Ein bekannter, unterstützter Shebang hat Vorrang.
- Unbekannte oder beliebige Shebang-Kommandos werden nicht ausgeführt.
- Ein angeforderter Interpreter muss vorhanden sein, sonst endet PatchHarbor mit einem klaren Fehler.
- PowerShell 7 kann durch einen ausdrücklich unterstützten Shebang gewählt werden, wenn `pwsh` installiert ist.
- Weitere Interpreter können später über eine kleine geprüfte Zuordnung ergänzt werden, nicht über freie Kommandoausführung.

### 9.2 PowerShell auf Windows

- PowerShell wird ohne Benutzerprofil und nicht interaktiv gestartet.
- PatchHarbor umgeht die Execution Policy standardmäßig nicht.
- Verhindert die lokale oder zentrale Richtlinie die Ausführung, zeigt PatchHarbor einen klaren Fehler.
- Ein späterer expliziter Bypass-Schalter ist möglich, gehört aber nicht zu Version 1.

### 9.3 Timeout und Prozessende

- Standard-Timeout: 300 Sekunden pro Skript.
- Der Wert ist über `--timeout` änderbar.
- Bei normalem Ende wird der Skript-Exit-Code übernommen.
- Bei Timeout versucht PatchHarbor zunächst eine geordnete Beendigung.
- Nach einer kurzen Frist von zwei Sekunden wird der gesamte Prozessbaum hart beendet.
- Unter Linux wird eine eigene Prozesssitzung beziehungsweise Prozessgruppe verwendet.
- Unter Windows wird eine echte Prozessbaum-Lösung verwendet, vorzugsweise ein Windows Job Object.
- Strg+C beendet das Skript und seine Kindprozesse und liefert Exit-Code 130.
- Timeout liefert Exit-Code 124.

### 9.4 Ausführungsreihenfolge je Skript

1. Pflichtmarker prüfen.
2. optionale META-, MESSAGE- und FILE-Blöcke vollständig analysieren.
3. beschädigte optionale Blöcke als Warning verwerfen.
4. gültige FILE-Blöcke sicher schreiben.
5. Interpreter bestimmen.
6. Kindprozess im ursprünglichen Arbeitsverzeichnis starten.
7. Output erfassen und Status darstellen.
8. Exit-Code zurückgeben oder beim ersten Fehler abbrechen.

---

## 10. Ausgabe, TUI und Logging

### 10.1 Output-Erfassung

- STDOUT und STDERR werden zu einem gemeinsamen zeitlichen Strom zusammengeführt.
- PatchHarbor liest den Output fortlaufend, damit der Kindprozess nicht an vollen Pipes blockiert.
- Intern werden nur die letzten zehn vollständigen oder angefangenen Ausgabezeilen im Rolling Buffer gehalten.
- Im Execution-Bereich werden die letzten fünf Zeilen angezeigt.
- Sehr lange Zeilen werden auf die verfügbare Breite gekürzt.
- Eine letzte Zeile ohne Zeilenumbruch wird trotzdem angezeigt.
- Für die TUI werden ANSI- und andere Terminal-Steuersequenzen entfernt oder entschärft.

### 10.2 Feste Terminaloberfläche

Im interaktiven Terminal verwendet PatchHarbor eine feste, neu gezeichnete Oberfläche.

Regeln:

- maximale Breite 80 Zeichen,
- ist das Terminal schmaler, wird die tatsächliche Breite verwendet,
- ist das Terminal für das Layout zu schmal, wird automatisch in den einfachen Textmodus gewechselt,
- kein horizontaler Umbruch innerhalb fester Bereiche; Text wird rechts gekürzt,
- feste Höhen für die Informationsbereiche,
- vertikaler Überlauf wird durch einen Hinweis auf weitere Elemente dargestellt,
- Redraw alle 0,2 Sekunden während der Ausführung,
- sofortiger finaler Redraw nach Prozessende,
- sehr schnelle Skripte zeigen direkt den finalen Zustand,
- keine künstliche Pause nach Ende,
- keine zeitgesteuerten Informationen verschwinden aus der Anzeige.

Vorgesehene Bereiche:

- Source,
- Messages,
- Files,
- Execution,
- Result.

Der Source-Bereich zeigt dauerhaft die gewählte Eingabe und bei ZIP zusätzlich den aktuellen Skripteintrag.

Der Message-Bereich zeigt so viele Messages, wie in den festen Bereich passen. Weitere Messages werden gezählt, aber nicht vollständig dargestellt.

Der Files-Bereich zeigt Dateiname, Größe und Status, aber niemals den Dateiinhalt.

### 10.3 Nicht interaktive Ausgabe

Ist die Ausgabe kein echtes Terminal, verwendet PatchHarbor automatisch einfache fortlaufende Textausgabe ohne Cursorsteuerung und ohne Farben.

Das gilt insbesondere für:

- umgeleitete Ausgabe,
- CI-Systeme,
- Logsammler,
- Tests ohne Pseudo-Terminal.

`--plain` erzwingt diesen Modus auch im Terminal.

### 10.4 Vollständiges Logging

Mit `--log` wird der vollständige zusammengeführte Output zusätzlich in eine sichere, eindeutig benannte Datei im System-Temp-Verzeichnis geschrieben.

Das Log enthält:

- Startzeit,
- Quelle,
- Arbeitsverzeichnis,
- gewählten Interpreter,
- PatchHarbor-Warnings,
- den vollständigen rohen Skriptoutput,
- Endzeit,
- Exit-Code oder Tool-Fehler.

Der Pfad zur Logdatei wird im Ergebnis angezeigt.

Ohne `--log` wird keine vollständige Ausgabedatei erzeugt.

---

## 11. Exit-Codes

Wenn ein Skript gestartet wurde, bestimmt grundsätzlich dessen Exit-Code das Ergebnis.

Bei mehreren ZIP-Skripten gilt:

- alle erfolgreich: Exit-Code des letzten Skripts, normalerweise 0,
- erstes fehlerhaftes Skript: dessen Exit-Code,
- spätere Skripte werden nicht mehr gestartet.

Empfohlene Tool-Exit-Codes:

| Code | Bedeutung |
|---:|---|
| `2` | ungültige CLI-Verwendung oder keine Eingabe |
| `3` | kein gültiges PatchHarbor-Skript gefunden |
| `4` | Quelle oder ZIP nicht lesbar beziehungsweise Ressourcenbudget überschritten |
| `5` | Interpreter fehlt oder kann nicht gestartet werden |
| `6` | Vorbereitung eines gültigen FILE-Blocks fehlgeschlagen |
| `7` | sonstiger interner Ausführungsfehler vor Prozessstart |
| `124` | Timeout |
| `130` | Abbruch durch Strg+C |

Da ein Skript theoretisch dieselben numerischen Werte zurückgeben kann, muss die sichtbare Fehlermeldung immer erkennen lassen, ob der Code vom Skript oder von PatchHarbor stammt.

---

## 12. Architektur und Verantwortungsgrenzen

### 12.1 Datenfluss und Importabhängigkeiten sind nicht dasselbe

Der fachliche Datenfluss lautet:

**Quelle → Skriptformat → FILE-Vorbereitung → Execution → Darstellung**

Die Importabhängigkeiten werden jedoch über einen kleinen Orchestrator gesteuert. Execution darf nicht die TUI kennen und der Parser darf nicht die Prozesssteuerung kennen.

### 12.2 Empfohlene Modulgrenzen

Zu Beginn bleibt das Python-Paket flach. Unterordner entstehen erst bei echter Größe oder plattformspezifischer Notwendigkeit.

Empfohlene Module:

- `cli.py` – argparse und Umwandlung der CLI-Eingabe in einen Anwendungsaufruf,
- `application.py` – einziger Orchestrator des vollständigen Ablaufs,
- `sources.py` – Datei, Ordner, ZIP und STDIN übernehmen,
- `script_format.py` – Marker, META, MESSAGE und FILE-Blöcke analysieren,
- `payload_files.py` – Dateinamen prüfen und Dateien atomar schreiben,
- `execution.py` – Interpreter, Prozessstart, Timeout und Ergebnis,
- `presentation.py` – Plain-Ausgabe, TUI, Farben und Rolling-Buffer-Darstellung,
- `models.py` – kleine unveränderliche Datenträger,
- `errors.py` – eindeutige Tool-Fehler und Exit-Codes,
- `platform/` – nur die tatsächlich notwendige Linux- und Windows-Prozesssteuerung.

### 12.3 Abhängigkeitsregel

- `cli` kennt `application`.
- `application` orchestriert die fachlichen Module.
- Fachmodule kennen sich nicht gegenseitig, sofern eine Übergabe über Modelle genügt.
- `models` und `errors` kennen keine höherliegenden Module.
- `execution` kennt weder TUI noch argparse.
- `presentation` erhält Zustandsmodelle und steuert keine Ausführung.
- Es gibt keine Pakete namens `utils`, `helpers` oder `common` als Sammelstellen.
- Zukünftige Quellen liefern denselben neutralen Quellenausgang, ohne die Verarbeitungspipeline zu verändern.

---

## 13. Teststrategie

### 13.1 Grundsatz

PatchHarbor wird pragmatisch verhaltensorientiert entwickelt.

- Schwerpunkt auf End-to-End-Integrationstests,
- wenige gezielte Unit-Tests für isolierte, kritische Logik,
- echte Dateien und echte Prozesse statt umfangreicher Mocks,
- Verhalten statt interner Implementierungsdetails prüfen,
- keine dogmatische Forderung nach vollständiger Testabdeckung.

### 13.2 Vertikale Entwicklung

Für jeden Step gilt:

1. erwartetes Verhalten festlegen,
2. im `W`-Commit Feature und passenden Test gemeinsam implementieren,
3. im `R`-Commit fachliche Struktur verbessern und Tests grün halten,
4. im `C`-Commit vereinfachen und doppelte oder fragile Tests entfernen,
5. erst dann mit dem nächsten Step beginnen.

### 13.3 Unbedingt abzudeckende Verhaltenstests

- direkter Datei-Run,
- exakter Pflichtmarker,
- MESSAGE-Zeile ohne eigenständigen Marker ist kein gültiges Skript,
- fehlender Marker,
- STDIN und Pipe,
- Ordnerscan und Auswahl,
- ZIP mit mehreren Skripten in Archiv-Reihenfolge,
- Abbruch beim ersten fehlerhaften ZIP-Skript,
- Exit-Code des letzten ausgeführten Skripts,
- gültige und beschädigte Message-Blöcke,
- gültige und beschädigte FILE-Blöcke,
- tatsächlicher FILE-Schreibfehler verhindert Execution,
- sichere Dateinamen, Windows-Reservierungen und symbolische Links,
- atomisches Überschreiben,
- Timeout pro Skript,
- Strg+C und vollständiger Prozessbaum,
- fehlender Interpreter,
- viel Output und Rolling Buffer zehn beziehungsweise Anzeige fünf,
- sehr lange Zeile und letzte Zeile ohne Zeilenumbruch,
- ANSI-Ausgabe zerstört die TUI nicht,
- schneller Prozess zeigt finalen Zustand,
- Plain-Modus ohne Cursorsequenzen,
- Logdatei im System-Temp-Verzeichnis,
- korrektes ursprüngliches Arbeitsverzeichnis,
- Ressourcenlimits und ZIP-Bomben-Schutz.

### 13.4 Plattformen und CI

Pflichtplattformen:

- Ubuntu 24.04,
- Ubuntu 26.04,
- Windows GitHub-Runner mit Windows PowerShell,
- zusätzlich PowerShell 7, soweit auf dem Runner vorhanden.

Ubuntu 26.04 wird anfangs als zusätzliche, gegebenenfalls nicht blockierende CI-Lane behandelt, solange das Runner-Image noch Preview-Status besitzt. Die stabile Release-Freigabe stützt sich mindestens auf Ubuntu 24.04 und Windows.

Windows-Tests laufen auf einem echten GitHub-gehosteten Windows-Runner, nicht in einem Linux-Docker-Container.

Die CI prüft außerdem die Installation eines gebauten Wheels mit pipx in einer sauberen Umgebung.

---

## 14. Bewusst verschobene Funktionen

Folgende Funktionen gehören nicht zu Version 1:

- WebSocket-Quelle,
- Clipboard-Quelle,
- SSH-Quelle,
- öffentliches Plugin-System,
- Save-Modus mit chmod,
- Tests des Zielprojekts,
- Git-Commits,
- interaktive Kindskripte,
- automatische Base64-Decodierung,
- rekursive Ordnersuche,
- verschachtelte ZIP-Archive,
- vollständige Transaktion über mehrere FILE-Blöcke,
- dauerhafte Logverwaltung oder Logrotation.

Diese Liste verhindert, dass die erste Version wieder zu groß wird.

---

# Teil B – Meilenstein- und Commit-Plan

## 15. Übersicht der Meilensteine

| Meilenstein | Name | Ergebnis |
|---:|---|---|
| 1 | Minimal lauffähig | Eine direkte Datei kann ohne TUI kontrolliert ausgeführt werden. |
| 2 | Robuste Inputs und Nutzdaten | Datei, Ordner, ZIP, Pipe, Messages und FILE-Blöcke funktionieren. |
| 3 | Kontrollierte Execution und Ausgabe | Prozessbaum, Output, Logging und feste TUI sind stabil. |
| 4 | Plattform und Release-Qualität | Linux und Windows sind automatisiert getestet und pipx-fähig veröffentlicht. |

Am Ende jedes Meilensteins werden Architektur, Risiken und der verbleibende Commit-Plan geprüft. Notwendige Korrekturen werden im `C`-Commit des letzten Steps dieses Meilensteins dokumentiert, damit kein zusätzlicher künstlicher Planungscommit entsteht.

---

# Meilenstein 1 – Minimal lauffähig

## Ziel

Der kleinste vertikale Durchlauf funktioniert: Eine einzelne Datei wird über die CLI eingelesen und ohne TUI mit minimalen Fehlermeldungen ausgeführt.

## Scope

- Python-Paketgrundlage,
- direkter Datei-Input,
- minimaler Prozessstart,
- exakter Pflichtmarker,
- aktuelles Arbeitsverzeichnis,
- Timeout und Exit-Code,
- argparse-Help,
- pipx-fähiger Einstiegspunkt.

Nicht enthalten sind ZIP, Ordnerauswahl, Pipe, Messages, FILE-Blöcke, Logging und TUI.

## Definition of Done

- `patchharbor fs run PFAD` funktioniert als vertikaler Pfad.
- Ein Skript mit exaktem Marker läuft.
- Ein Skript ohne exakten Marker läuft nicht.
- Das Skript läuft im ursprünglichen Arbeitsverzeichnis.
- Timeout und Exit-Code sind nachvollziehbar.
- Die CLI hat einen klaren Help-Screen.
- Das gebaute Paket lässt sich lokal mit pipx aus einem Wheel installieren.
- Die E2E-Basistests sind grün.
- Der verbleibende Plan wurde geprüft.

---

## Step 1.a – Direkte Datei minimal einlesen und ausführen

**Ergebnis:** Der erste vertikale Durchlauf existiert bewusst noch ohne TUI und ohne weitere Quellen.

### 1.a.W – Minimalen Datei-Run vertikal implementieren

- minimales `pyproject.toml` und Paketgerüst anlegen,
- argparse-Aufruf für `fs run PFAD` einführen,
- Datei als UTF-8 einlesen,
- Skript mit dem plattformüblichen Standardinterpreter starten,
- Skript-Exit-Code zurückgeben,
- minimalen E2E-Happy-Path-Test mit echter Datei und echtem Prozess hinzufügen.

### 1.a.R – Vertikalen Pfad in klare Verantwortlichkeiten schneiden

- CLI, Anwendungsorchestrierung und Prozessstart voneinander trennen,
- kleine Ergebnis- und Fehlerdatenträger einführen,
- direkte Abhängigkeiten von argparse in der Execution entfernen,
- vorhandenen E2E-Test unverändert grün halten.

### 1.a.C – Ersten Pfad radikal vereinfachen

- unnötige Klassen und Zukunftsabstraktionen entfernen,
- Namen auf Datei, Skript und Ausführung vereinheitlichen,
- tote Optionen und doppelte Fehlertexte löschen,
- sicherstellen, dass noch kein Plugin- oder Source-Framework entstanden ist.

---

## Step 1.b – Exakten Pflichtmarker validieren

**Ergebnis:** Nur ein Skript mit der vollständigen eigenständigen Markerzeile darf laufen.

### 1.b.W – Exakte Markerregel und Fehlerverhalten ergänzen

- vollständige Zeile `# PATCHHARBOR` prüfen,
- führende Leerzeichen, Zusätze und falsche Schreibweise ablehnen,
- fehlenden Marker mit Tool-Fehler beenden,
- E2E-Tests für gültigen und fehlenden Marker hinzufügen,
- positiven Test ergänzen, dass eine reine MESSAGE-Zeile den Pflichtmarker nicht ersetzt.

### 1.b.R – Markerprüfung als kleine Parserfunktion strukturieren

- Zeilenenden vor der Prüfung normalisieren,
- Markerprüfung aus Source- und Execution-Code lösen,
- gezielte Unit-Tests für Randfälle ergänzen,
- Tool-Fehler und sichtbare Meldung eindeutig machen.

### 1.b.C – Markerlogik und Tests entschlacken

- Mehrfachscans vermeiden,
- unnötige reguläre Ausdrücke entfernen, falls einfache Zeilenprüfung genügt,
- Testfälle auf fachlich unterschiedliche Fälle reduzieren,
- Benennung des Pflichtmarkers zentralisieren.

---

## Step 1.c – Minimalen Ausführungsvertrag festlegen

**Ergebnis:** Arbeitsverzeichnis, Timeout, Kind-STDIN, temporäre Skriptdatei und Exit-Codes verhalten sich vorhersagbar.

### 1.c.W – CWD, Timeout und temporäre Skriptdatei implementieren

- ursprüngliches Arbeitsverzeichnis unverändert an den Kindprozess geben,
- Kind-STDIN schließen,
- Standard-Timeout 300 Sekunden und `--timeout` einführen,
- temporäre Skriptdatei sicher im System-Temp-Verzeichnis anlegen und entfernen,
- Skript-Exit-Code übernehmen,
- E2E-Tests für CWD, Timeout und einen nicht null Exit-Code ergänzen.

### 1.c.R – Cleanup und interne Exit-Codes richtig strukturieren

- Lebenszyklus der temporären Datei in einen sicheren Kontext kapseln,
- Tool-Fehler vor Prozessstart von Skriptfehlern trennen,
- interne Exit-Codes zentral abbilden,
- Fehlerpfade auf zuverlässiges Cleanup prüfen.

### 1.c.C – Ausführungspfad vereinfachen

- verschachtelte Fehlerbehandlung reduzieren,
- Timeout-Validierung und Standardwert an einer Stelle halten,
- unnötige Zwischenobjekte entfernen,
- klare und kurze Fehlermeldungen herstellen.

---

## Step 1.d – CLI, Help und pipx-Installation abschließen

**Ergebnis:** Der minimale Runner ist als echtes Kommando installierbar und über Help verständlich.

### 1.d.W – Konsolenbefehl und pipx-Installierbarkeit herstellen

- Konsolen-Entry-Point `patchharbor` definieren,
- Wheel bauen,
- Installation mit pipx aus dem lokalen Wheel testen,
- Smoke-Test für `patchharbor --help` und einen echten Run nach pipx-Installation hinzufügen.

### 1.d.R – argparse-Struktur und Usage-Fehler ordnen

- Unterbefehle `fs` und `run` klar modellieren,
- fehlenden Pfad ohne Pipe als Usage-Fehler behandeln,
- Help-Texte auf Zweck, Parameter und Standardwerte begrenzen,
- Parsing und fachlichen Aufruf sauber trennen.

### 1.d.C – Öffentliche Oberfläche und Dokumentation minimieren

- README auf Installation und Verweis auf `--help` begrenzen,
- unfertige Commands und Optionen aus Help und Code entfernen,
- Paketmetadaten und Namen vereinheitlichen,
- Meilenstein 1 reviewen und den verbleibenden Plan nur bei echtem Bedarf aktualisieren.

---

# Meilenstein 2 – Robuste Inputs und Nutzdaten

## Ziel

Alle für Version 1 vorgesehenen Eingabewege und optionalen Skriptnutzdaten funktionieren über dieselbe Verarbeitungspipeline.

## Scope

- STDIN und Pipe,
- einmaliger Ordnerscan und Auswahl,
- ZIP-Fallback,
- mehrere Skripte im ZIP,
- Metadaten und Messages,
- FILE-Blöcke,
- sichere Dateinamen,
- atomisches Schreiben,
- erste Ressourcenbudgets.

## Definition of Done

- Datei, Ordner, ZIP und Pipe funktionieren.
- Ordner werden nicht überwacht und nicht rekursiv gelesen.
- ZIP-Skripte laufen in Archiv-Reihenfolge und stoppen beim ersten Fehler.
- Messages und Metadaten sind rein informativ und fail soft.
- FILE-Blöcke werden vor Execution sicher geschrieben.
- Beschädigte optionale Blöcke erzeugen nur Warnings.
- Ein tatsächlicher FILE-Schreibfehler verhindert Execution.
- Sicherheits- und Ressourcenfälle sind getestet.
- Der verbleibende Plan wurde geprüft.

---

## Step 2.a – STDIN und Pipe als zweite Quelle ergänzen

**Ergebnis:** Ein vollständiges Skript kann ohne Datei über STDIN übernommen werden.

### 2.a.W – Pipe-Verhalten vertikal implementieren

- ohne Pfad zwischen TTY und gepipetem STDIN unterscheiden,
- vollständigen Pipe-Inhalt einmalig lesen,
- denselben Marker- und Execution-Pfad wie bei Dateien verwenden,
- Fehler bei leerem oder fehlendem Input ausgeben,
- E2E-Test für Pipe-Happy-Path und fehlenden Input hinzufügen.

### 2.a.R – Kleine gemeinsame Quellengrenze einführen

- Datei und STDIN auf ein neutrales Source-Ergebnis abbilden,
- Source-Code von Parser und Execution trennen,
- Schnittstelle so klein halten, dass später Clipboard oder WebSocket denselben Ausgang liefern könnten,
- keine dynamische Registrierung und kein Plugin-System einführen.

### 2.a.C – Source-Abstraktion auf das notwendige Maß reduzieren

- nur tatsächlich von Datei und STDIN gemeinsam genutzte Teile behalten,
- spekulative Methoden für zukünftige Quellen entfernen,
- Source-Fehlertexte vereinheitlichen,
- Tests auf Verhalten statt Klassennamen ausrichten.

---

## Step 2.b – Ordner einmalig scannen und Auswahl anbieten

**Ergebnis:** Der Nutzer kann aus sortierten Kandidaten genau eine Datei wählen.

### 2.b.W – Ordnerscan und Indexauswahl implementieren

- Ordner nicht rekursiv scannen,
- nur reguläre Dateien berücksichtigen und Symlinks ignorieren,
- direkte PatchHarbor-Skripte als Kandidaten erkennen,
- nach Änderungszeit absteigend und Dateiname als Tie-Breaker sortieren,
- Auswahl ab eins mit ASCII-Ziffern einführen,
- genau einen Kandidaten automatisch wählen,
- E2E-Tests für Sortierung, Auswahl, leere Auswahl und keinen Kandidaten hinzufügen.

### 2.b.R – Discovery und Benutzerwahl trennen

- Kandidatenermittlung als reine, testbare Funktion strukturieren,
- interaktive Auswahl von Dateisystemscan trennen,
- stabile Anzeigeinformationen als Datenmodell definieren,
- Randfälle bei verschwundenen Dateien sauber behandeln.

### 2.b.C – Ordner-UX und Tests vereinfachen

- unnötige Wiederholungen im Prompt entfernen,
- Auswahlfehler kurz und eindeutig formulieren,
- Testfixtures zusammenfassen, ohne Verhalten zu verstecken,
- sicherstellen, dass kein Watcher oder Hintergrundloop existiert.

---

## Step 2.c – ZIP-Fallback und sequenzielle Skripte implementieren

**Ergebnis:** Eine Datei ohne direkten Marker kann als ZIP geprüft werden; gültige Einträge laufen in Archiv-Reihenfolge.

### 2.c.W – ZIP-Fallback und Archiv-Reihenfolge ergänzen

- direkte Datei zuerst als Skript prüfen,
- anschließend best effort als ZIP öffnen,
- reguläre Einträge in gespeicherter Reihenfolge prüfen,
- nur Einträge mit exaktem Pflichtmarker ausführen,
- mehrere gültige Skripte sequenziell ausführen,
- beim ersten nicht null Exit-Code stoppen,
- letzten ausgeführten Exit-Code zurückgeben,
- E2E-Tests für mehrere Skripte, Reihenfolge, Stop-on-failure und leeres ZIP ergänzen.

### 2.c.R – ZIP-Verarbeitung streamend und begrenzt strukturieren

- Verzeichnisse, Links und verschachtelte ZIPs explizit ignorieren,
- Eintragszahl, Einzelgröße und unkomprimierte Gesamtgröße vor und während des Lesens prüfen,
- pro Skript eigenes Timeout sicherstellen,
- ZIP-Fehler von fehlendem Marker unterscheiden,
- Ordnerkandidaten um ZIP-Dateien mit gültigen Skripten erweitern.

### 2.c.C – ZIP-Pfad entschlacken

- unnötiges vollständiges Entpacken vermeiden,
- gemeinsame Skriptpipeline für direkte Datei und ZIP-Eintrag herstellen,
- doppelte Markerprüfungen reduzieren,
- Warnungen und Fehler auf wenige klare Kategorien begrenzen.

---

## Step 2.d – Optionale Metadaten und benannte Messages parsen

**Ergebnis:** Informative Zusatzdaten werden erkannt, ohne Execution zu steuern oder bei Fehlern abzubrechen.

### 2.d.W – META- und MESSAGE-Format positiv implementieren

- optionale META-Zeilen erkennen,
- mehrere benannte Message-Blöcke erkennen,
- Groß- und Kleinbuchstaben, Zahlen und Punkte im Message-Namen erlauben,
- kommentierte UTF-8-Inhaltszeilen entkommentieren,
- positive Unit- und E2E-Tests für mehrere Messages und Metadaten ergänzen.

### 2.d.R – Best-Effort-Fehlerbehandlung und Namensabgleich ergänzen

- identischen Namen in START und END verlangen,
- unvollständigen oder ungültigen Block vollständig verwerfen,
- Warnings sammeln statt Exceptions bis zur Execution durchzureichen,
- sicherstellen, dass Metadaten keine Umgebung, keinen Timeout und keinen Interpreter verändern,
- Tests für beschädigte Blöcke ohne Skriptabbruch ergänzen.

### 2.d.C – Informationsmodelle vereinfachen

- unnötige Metadatenhierarchien entfernen,
- Messages als einfache geordnete Liste modellieren,
- Parsing in einen linearen Durchlauf bringen,
- doppelte Warnungen vermeiden und Formulierungen vereinheitlichen.

---

## Step 2.e – FILE-Blöcke sicher vor Execution schreiben

**Ergebnis:** Textdateien können übertragen, validiert und atomar in das aktuelle Arbeitsverzeichnis geschrieben werden.

### 2.e.W – FILE-Blöcke und Überschreiben implementieren

- mehrere benannte FILE-Blöcke erkennen,
- identischen Dateinamen in START und END verwenden,
- kommentierten UTF-8-Text entkommentieren,
- Inhalte vor Execution in das aktuelle Arbeitsverzeichnis schreiben,
- vorhandene reguläre Dateien ohne Nachfrage überschreiben,
- Base64 als gewöhnlichen Text unverändert transportieren,
- E2E-Tests für neue Datei, Überschreiben und mehrere Dateien ergänzen.

### 2.e.R – Dateinamen, atomisches Schreiben und Fehlerklassen härten

- nur das vereinbarte plattformübergreifende Namensformat erlauben,
- Punkt, zwei Punkte, Pfade, Windows-Reservierungen und abschließende Punkte oder Leerzeichen ablehnen,
- vorhandene Symlinks und nicht reguläre Ziele ablehnen,
- jede Datei im selben Verzeichnis vorab schreiben und atomar ersetzen,
- beschädigten Block nur warnen und verwerfen,
- tatsächlichen Schreibfehler als fatal vor Execution behandeln,
- Größenwarnung und harte Budgets testen.

### 2.e.C – FILE-Pipeline auf geringe Komplexität reduzieren

- mehrfaches Kopieren großer Inhalte vermeiden,
- Validierung, Staging und atomaren Replace klar, aber kompakt halten,
- Fehlertexte nach Warning und fatalem Schreibfehler trennen,
- unnötige Backup- oder Rollback-Logik aus Version 1 entfernen,
- Meilenstein 2 reviewen und den verbleibenden Plan gezielt aktualisieren.

---

## Review nach Meilenstein 2

- Der gerichtete Ablauf bleibt `CLI → Input → Parser → Files → Execution → Output`; neue Rückabhängigkeiten sind nicht notwendig.
- Das flache Paket genügt weiterhin. Ein zusätzlicher Application-Layer entsteht erst, wenn die Orchestrierung in Meilenstein 3 tatsächlich wächst.
- Die vollständige Vereinheitlichung der Ressourcenbudgets für alle Quellen bleibt gezielt in Step 4.b; FILE- und ZIP-Grenzen sind bereits zentral definiert und getestet.

---

# Meilenstein 3 – Kontrollierte Execution und Ausgabe

## Ziel

Prozesse werden auf Linux und Windows zuverlässig gesteuert. Output, Logging und die feste Terminaloberfläche funktionieren ohne Scroll-Effekt oder Prozesslecks.

## Scope

- unterstützte Interpreter,
- PowerShell-Startregeln,
- Prozessbaum und Signale,
- Timeout und Strg+C,
- zusammengeführter Output,
- Rolling Buffer zehn und Anzeige fünf,
- Plain-Modus,
- temporäres Voll-Log,
- feste TUI mit 0,2 Sekunden Redraw.

## Definition of Done

- Bash und PowerShell werden deterministisch gewählt.
- Unbekannte Interpreter werden klar abgelehnt.
- Timeout und Strg+C beenden auch Kindprozesse.
- Output blockiert den Kindprozess nicht.
- Plain-Modus enthält keine ANSI-Cursorsteuerung.
- TUI bleibt fest, passt sich schmalen Terminals an und wird von Skript-ANSI nicht zerstört.
- Rolling Buffer und Logdatei funktionieren wie spezifiziert.
- Der verbleibende Plan wurde geprüft.

---

## Step 3.a – Interpreterauswahl und PowerShell-Vertrag härten

**Ergebnis:** Der Interpreter wird aus einer kleinen Whitelist deterministisch gewählt.

### 3.a.W – Bash- und PowerShell-Auswahl implementieren

- Linux ohne Shebang auf Bash abbilden,
- Windows ohne Shebang auf Windows PowerShell abbilden,
- bekannte Bash-, Windows-PowerShell- und PowerShell-7-Shebangs erkennen,
- unbekannte Shebangs ablehnen,
- Interpreterverfügbarkeit vor Prozessstart prüfen,
- PowerShell ohne Profil und nicht interaktiv starten,
- E2E-Tests für Defaults, bekannte Shebangs und fehlenden Interpreter ergänzen.

### 3.a.R – Interpreterresolver plattformneutral strukturieren

- Shebang-Auswertung, Verfügbarkeitsprüfung und Prozessargumente trennen,
- freie Shebang-Kommandoausführung verhindern,
- temporäre Dateiendung nur als technische Hilfe, nicht als Typentscheidung nutzen,
- PowerShell Execution Policy nicht umgehen und Policy-Fehler verständlich abbilden.

### 3.a.C – Interpreterlogik vereinfachen

- Mapping auf tatsächlich unterstützte Varianten begrenzen,
- doppelte OS-Abfragen entfernen,
- Fehlermeldungen auf Interpretername und Ursache reduzieren,
- nicht benötigte Python- oder Shell-Autodetektion entfernen.

---

## Step 3.b – Prozessbaum, Timeout und Strg+C zuverlässig steuern

**Ergebnis:** PatchHarbor hinterlässt nach Ende, Timeout oder Abbruch keine Kindprozesse.

### 3.b.W – Plattformgerechte Prozessgruppen implementieren

- unter Linux eine eigene Prozesssitzung beziehungsweise Gruppe starten,
- unter Windows den Prozess in einem Job Object verwalten,
- Timeout zunächst geordnet und nach zwei Sekunden hart beenden,
- Strg+C auf den gesamten Prozessbaum anwenden,
- Exit-Codes 124 und 130 liefern,
- echte E2E-Tests mit einem Kindprozess auf beiden Plattformen ergänzen.

### 3.b.R – Plattformcode hinter kleinem Lifecycle-Vertrag isolieren

- Linux- und Windows-Details in `platform/` trennen,
- Execution nur eine kleine Start-, Stop- und Kill-Schnittstelle kennen lassen,
- Race Conditions zwischen natürlichem Ende, Timeout und Strg+C behandeln,
- Cleanup auch bei Exceptions garantieren.

### 3.b.C – Prozesssteuerung vereinfachen und härten

- redundante Signalpfade entfernen,
- genau eine Zustandsmaschine für läuft, beendet, Timeout und Abbruch verwenden,
- Wartezeiten und Polling zentralisieren,
- Tests auf tatsächliches Prozessende statt interne Funktionsaufrufe ausrichten.

---

## Step 3.c – Output fortlaufend erfassen und begrenzen

**Ergebnis:** STDOUT und STDERR erscheinen gemeinsam, ohne Deadlock und ohne unbegrenzten RAM-Verbrauch.

### 3.c.W – Zusammengeführten Output und Rolling Buffer implementieren

- STDOUT und STDERR in einen gemeinsamen Stream führen,
- Output während des Laufs fortlaufend lesen,
- letzte zehn Zeilen im Rolling Buffer halten,
- zunächst die letzten fünf Zeilen in einfacher Textdarstellung ausgeben,
- lange Zeile und letzte Zeile ohne Zeilenumbruch unterstützen,
- E2E-Tests für viel Output, gemischte Streams und schnellen Prozess ergänzen.

### 3.c.R – Streaming und Decodierung robust strukturieren

- Byte-Lesen von Textdecodierung und Zeilenbildung trennen,
- fehlerhafte Zeichen mit Ersatzdarstellung statt Crash behandeln,
- Thread- oder Async-Lösung so kapseln, dass der Prozess nie wegen voller Pipe blockiert,
- Zähler für verworfene ältere Zeilen bereitstellen.

### 3.c.C – Buffer und Reader vereinfachen

- geeignete begrenzte Datenstruktur verwenden,
- unnötige vollständige Outputkopien entfernen,
- Zeilen- und Chunklogik zusammenführen, wo sie fachlich identisch ist,
- Performance nur anhand realer Tests optimieren.

---

## Step 3.d – Plain-Ausgabe und vollständiges Temp-Log ergänzen

**Ergebnis:** Automation erhält saubere Textausgabe; Debugging kann den vollständigen Output sichern.

### 3.d.W – Plain-Modus und `--log` implementieren

- bei Nicht-TTY automatisch einfache fortlaufende Ausgabe verwenden,
- `--plain` und `--no-color` ergänzen,
- mit `--log` eine sichere eindeutige Datei im System-Temp-Verzeichnis erzeugen,
- vollständigen zusammengeführten Output und Run-Metadaten schreiben,
- Logpfad am Ende anzeigen,
- E2E-Tests für Plain-Ausgabe und Loginhalt ergänzen.

### 3.d.R – Ausgabeziele und Log-Lebenszyklus trennen

- Terminaldarstellung, Plain-Sink und Log-Sink sauber koordinieren,
- Logging vom Rolling Buffer unabhängig machen,
- rohe Skriptausgabe im Log und bereinigte Ausgabe im UI unterscheiden,
- sichere Tempdateierzeugung und korrektes Schließen auf allen Fehlerpfaden sicherstellen.

### 3.d.C – Output-Pipeline entschlacken

- unnötiges allgemeines Logging-Framework vermeiden,
- Ausgabeziele über kleine Funktionen oder einen schmalen Vertrag anbinden,
- doppelte Präfixe und Statuszeilen entfernen,
- Logformat auf die tatsächlich nützlichen Informationen begrenzen.

---

## Step 3.e – Feste TUI mit Redraw alle 0,2 Sekunden bauen

**Ergebnis:** Im interaktiven Terminal bleibt eine kompakte feste Oberfläche ohne Scroll-Effekt sichtbar.

### 3.e.W – Dashboard und periodischen Redraw implementieren

- Bereiche Source, Messages, Files, Execution und Result darstellen,
- maximale Breite 80 und tatsächliche Terminalbreite berücksichtigen,
- alle 0,2 Sekunden während der Execution neu zeichnen,
- nach Ende sofort final rendern,
- letzte fünf Outputzeilen anzeigen,
- feste Bereichshöhen und Überlaufhinweise implementieren,
- Renderer-Tests und einen interaktiven Smoke-Test ergänzen.

### 3.e.R – Terminalschutz und Fallbacks ergänzen

- ANSI-Steuersequenzen aus sichtbarem Skriptoutput entfernen,
- Cursorzustand und Farben auch bei Exception oder Strg+C wiederherstellen,
- bei zu schmalem Terminal automatisch in Plain wechseln,
- horizontales Kürzen ohne unbeabsichtigte Zeilenumbrüche sicherstellen,
- TUI-Zustandsmodell von Execution entkoppeln.

### 3.e.C – TUI beruhigen und vereinfachen

- nur bei verändertem Zustand oder fälligem 0,2-Sekunden-Tick rendern,
- Flackern und unnötige Vollausgaben reduzieren,
- Darstellung auf die vereinbarten Informationen begrenzen,
- keine Scroll-, Auswahl- oder Framework-Funktionen hinzufügen,
- Meilenstein 3 reviewen und den verbleibenden Plan gezielt aktualisieren.

---

# Meilenstein 4 – Plattform und Release-Qualität

## Ziel

PatchHarbor ist auf den Zielplattformen reproduzierbar getestet, sicher paketiert und als Version 1 über pipx nutzbar.

## Scope

- Ubuntu 24.04,
- Ubuntu 26.04,
- Windows GitHub-Runner,
- Windows PowerShell und PowerShell 7,
- Ressourcen- und Sicherheits-Härtung,
- vollständige Akzeptanztests,
- GitHub Actions,
- Wheel und pipx-Installation,
- finale Help- und Installationsdokumentation.

## Definition of Done

- alle blockierenden CI-Jobs sind grün,
- Ubuntu 24.04 und Windows sind Release-Gates,
- Ubuntu 26.04 läuft mindestens als zusätzliche Lane,
- Prozessbaumtests sind auf Linux und Windows grün,
- ZIP- und FILE-Sicherheitsfälle sind grün,
- pipx-Installation aus dem gebauten Wheel ist grün,
- Help-Screens beschreiben alle und nur die implementierten Funktionen,
- keine offenen kritischen Architekturfragen bestehen,
- kein unnötiger Code für verschobene Features ist enthalten,
- der finale Restplan und die Release-Kriterien wurden geprüft.

---

## Step 4.a – Plattformkonformität und Sicherheitsfälle härten

**Ergebnis:** Linux- und Windows-Sonderfälle sind explizit und verhaltensgleich behandelt.

### 4.a.W – Plattformübergreifende Sicherheitsfälle vervollständigen

- Windows-reservierte Dateinamen und Pfadsonderfälle testen,
- Symlink- und nicht reguläre Zieltests unter Linux ergänzen,
- Tempverzeichnis und CWD auf beiden Systemen prüfen,
- Windows PowerShell als Default und PowerShell 7 per Shebang testen,
- Bash-Verhalten auf Ubuntu 24.04 und 26.04 prüfen,
- Plattform-E2E-Tests für FILE, ZIP, Timeout und Logging hinzufügen.

### 4.a.R – OS-spezifische Logik an klare Grenzen verschieben

- plattformspezifische Prozess- und Dateisystemteile aus allgemeinen Modulen entfernen,
- gemeinsame fachliche Regeln in plattformneutralen Funktionen halten,
- Skip-Bedingungen in Tests begründen und zentralisieren,
- Fehlertexte auf beiden Systemen semantisch angleichen.

### 4.a.C – Plattformcode und Fixtures vereinfachen

- doppelte Linux- und Windows-Testdaten zusammenführen,
- nur echte Unterschiede separat halten,
- unnötige OS-Heuristiken entfernen,
- Abhängigkeiten und Paketgröße prüfen und möglichst bei Standardbibliothek bleiben.

---

## Step 4.b – Ressourcenbudgets und Missbrauchsschutz abschließen

**Ergebnis:** Große oder manipulierte Eingaben führen kontrolliert zu Warning oder Tool-Fehler statt Ressourcenerschöpfung.

### 4.b.W – Harte Budgets und Angriffsfälle testen

- Grenzen für direkte Eingabe, ZIP-Eintrag, ZIP-Gesamtdaten und Eintragszahl implementieren,
- Warning-Schwelle für große Inhalte anzeigen,
- ZIP-Bomben-ähnliche Fälle kontrolliert ablehnen,
- ANSI- und Kontrollzeichenfälle testen,
- sichere temporäre Dateinamen und atomaren Replace unter Fehlerbedingungen testen.

### 4.b.R – Ressourcenrichtlinie zentral und nachvollziehbar machen

- Grenzwerte als wenige zentrale Konstanten oder unveränderliche Policy modellieren,
- Vorabprüfung und laufende Prüfung großer ZIPs koordinieren,
- Fehler vor Execution garantieren,
- Metriken für gelesene und verworfene Daten nur dort halten, wo sie für Warning oder Fehler nötig sind.

### 4.b.C – Schutzlogik auf gutes Kosten-Nutzen-Verhältnis reduzieren

- doppelte Größenprüfungen entfernen,
- keine allgemeine Quota- oder Policy-Engine bauen,
- Grenzwerte und Fehlermeldungen im Help nur soweit nötig erklären,
- Tests auf echte Grenzen und nicht auf interne Zähler ausrichten.

---

## Step 4.c – Akzeptanzsuite und GitHub Actions etablieren

**Ergebnis:** Der reale Nutzerworkflow wird automatisiert auf Linux und Windows geprüft.

### 4.c.W – E2E-Akzeptanzsuite und CI-Matrix einführen

- vollständige E2E-Szenarien für Datei, Ordner, ZIP, Pipe, Messages, FILE, Timeout, Logging und Exit-Codes bündeln,
- GitHub Actions für Ubuntu 24.04, Ubuntu 26.04 und Windows einrichten,
- Windows PowerShell und PowerShell 7 abdecken,
- Wheel bauen und mit pipx in sauberer Umgebung installieren,
- Windows-Tests auf echtem Windows-Runner statt Docker ausführen.

### 4.c.R – Stabile und Preview-CI sauber trennen

- Ubuntu 24.04 und Windows als blockierende Release-Gates festlegen,
- Ubuntu 26.04 solange nötig als zusätzliche nicht blockierende Preview-Lane markieren,
- Unit-, E2E- und plattformspezifische Tests sinnvoll gruppieren,
- fehlerhafte Tests nach Ursache statt durch pauschale Retries stabilisieren.

### 4.c.C – Testbestand pragmatisch bereinigen

- doppelte E2E-Fälle entfernen,
- fragile pixelgenaue TUI-Assertions durch Zustands- und Renderer-Tests ersetzen,
- Mocks auf unvermeidbare OS-Grenzen beschränken,
- Testlaufzeit und Diagnoseausgaben optimieren, ohne Testaussage zu schwächen.

---

## Step 4.d – Version 1 paketieren und final freigeben

**Ergebnis:** Das veröffentlichbare Paket enthält nur den vereinbarten Scope und ist über pipx nutzbar.

### 4.d.W – Release-Paket und finale Bedienoberfläche herstellen

- Paketversion und Release-Metadaten setzen,
- Wheel und Source-Distribution bauen,
- Installation mit `pipx install patchharbor` für die Veröffentlichung vorbereiten,
- Help-Screens auf alle implementierten Optionen prüfen,
- kurze Installationsanleitung finalisieren,
- Release-Smoke-Test aus einem leeren Arbeitsverzeichnis ergänzen.

### 4.d.R – Architektur- und Release-Audit durchführen

- Importabhängigkeiten gegen die vereinbarte Richtung prüfen,
- CLI, Source, Parser, FILE, Execution und Presentation auf klare Grenzen prüfen,
- interne Exit-Codes, Warnings und Fehlermeldungen konsolidieren,
- sicherstellen, dass Clipboard, WebSocket, SSH, Save, Tests und Git nicht öffentlich enthalten sind,
- Lizenz, Paketinhalt und veröffentlichte Dateien prüfen.

### 4.d.C – Finalen Ballast entfernen und Plan abschließen

- tote Module, ungenutzte Optionen und spekulative Abstraktionen löschen,
- Namen und Help-Texte final vereinheitlichen,
- alle Tests auf beiden Release-Gates ausführen,
- verbleibenden Commit-Plan und Risiken abschließend reviewen,
- Version 1 nur freigeben, wenn die Definition of Done vollständig erfüllt ist.

---

# Teil C – Arbeitsregeln während der Umsetzung

## 16. Vertikal statt horizontal

Ein Step liefert immer einen benutzbaren schmalen Durchlauf. Es wird nicht zuerst der gesamte Parser, danach die gesamte Execution und erst später die CLI gebaut.

Das Repository bleibt nach jedem Commit ausführbar.

## 17. Tests begleiten das Feature

Der Verhaltenstest gehört in den `W`-Commit. Es gibt keinen späteren Sammelcommit, der Tests nachholt.

Unit-Tests werden nur ergänzt, wenn sie die Fehlersuche an einer kritischen, isolierbaren Regel deutlich verbessern.

## 18. Right und Clean sind getrennte Aufgaben

- **right** macht Verantwortlichkeiten und Fehlerverhalten fachlich korrekt.
- **clean** nimmt Code, Abstraktionen und doppelte Tests wieder weg.

Die KI darf in einer Phase nur das Ziel dieser Phase bearbeiten. Architekturentscheidungen werden nicht nebenbei geändert.

## 19. Meilensteinreview

Nach jedem Meilenstein werden fünf Fragen beantwortet:

1. Erfüllt das reale Verhalten die Definition of Done?
2. Welche Annahmen haben sich als falsch erwiesen?
3. Welche geplanten Steps sind jetzt unnötig?
4. Welche Risiken müssen in den nächsten Meilenstein verschoben werden?
5. Bleibt PatchHarbor ein Script-Runner oder ist Scope hinzugekommen?

Änderungen am Restplan werden klein gehalten und im letzten `C`-Commit des Meilensteins dokumentiert.

## 20. Freigaberegel

Ein Meilenstein ist erst abgeschlossen, wenn:

- alle vorgesehenen Steps mit `W`, `R` und `C` abgeschlossen sind,
- die Definition of Done erfüllt ist,
- alle bis dahin relevanten Tests grün sind,
- Help und Installation den tatsächlichen Stand wiedergeben,
- keine halbfertige öffentliche Funktion sichtbar ist,
- der verbleibende Plan geprüft wurde.

---

# Teil D – Zusammenfassung

Der Plan besteht aus:

- **4 Meilensteinen**,
- **18 Steps**,
- **54 geplanten Commits**,
- pro Step genau einem `W`-, einem `R`- und einem `C`-Commit.

Die Reihenfolge ist bewusst vertikal:

**Meilenstein → Step → work → right → clean**

Der erste Step liefert den kleinsten ausführbaren Datei-Run ohne TUI. Danach werden Eingaben und Nutzdaten, kontrollierte Execution und Ausgabe sowie zuletzt Plattform- und Release-Qualität ergänzt.

Die Leitlinie bleibt über den gesamten Plan gleich:

**minimal implementieren, fachlich richtig schneiden, anschließend konsequent vereinfachen.**

---

## Quellenhinweis zur CI-Planung

Die CI-Zielauswahl orientiert sich am aktuellen Stand der offiziellen GitHub-Dokumentation und des offiziellen `actions/runner-images`-Repositories. Ubuntu 26.04 ist zum Zeitpunkt dieses Plans als GitHub-Actions-Runner verfügbar, wird aber zunächst vorsichtig als zusätzliche Lane behandelt. GitHub-gehostete Runner stellen Linux- und Windows-Umgebungen bereit; auf GitHub-gehosteten Runnern ist PowerShell 7 verfügbar.
