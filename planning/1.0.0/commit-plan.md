# Teil B – Meilenstein- und Commit-Plan

## 15. Übersicht der Meilensteine

| Meilenstein | Name | Ergebnis |
|---:|---|---|
| 1 | Minimal lauffähig | Eine direkte Datei kann ohne TUI kontrolliert ausgeführt werden. |
| 2 | Robuste Inputs und Nutzdaten | Datei, Ordner, ZIP, Pipe, Messages und FILE-Blöcke funktionieren. |
| 3 | PatchBundle, Execution und Ausgabe | Bundle-Nutzdateien, Prozessbaum, Output, Logging und feste TUI sind stabil. |
| 4 | Plattform und Release-Qualität | Linux und Windows sind automatisiert getestet und pipx-fähig veröffentlicht. |
| 5 | WebSocket-Transport, nach Version 1 | Direkte Textskripte und unveränderte ZIP-PatchBundles mit mehreren Skripten und Binärdateien können über einen sicheren äußeren Host übernommen werden. |

Die Meilensteine 1 bis 4 bilden den verbindlichen Version-1-Commit-Plan. Meilenstein 5 ist ein nachgelagertes Ziel und wird erst nach dem Review von Meilenstein 4 in konkrete Steps und W-R-C-Commits zerlegt.

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

- Datei, Ordner, Pipe, ZIP-Skriptfolgen, Messages und inline FILE-Blöcke funktionieren fachlich; ein Neustart ist nicht erforderlich.
- Die bisherige Eingabelogik bündelt jedoch Quellenzugriff, ZIP-Erkennung, Parsing, FILE-Vorbereitung und Ausführungsreihenfolge zu stark in einem Pfad.
- Vor der weiteren Execution-Arbeit trennt Step 3.a deshalb Quelle, neutrales `InputArtifact`, PatchBundle-Auflösung und Anwendungsorchestrierung.
- Die nachträgliche Produktentscheidung, ZIP-PatchBundles zusätzlich für bytegenaue Text- und Binärdateien zu verwenden, wird anschließend als eigener vertikaler Step 3.b umgesetzt.
- Diese Korrekturen bereiten WebSocket und weitere Quellen vor, ohne WebSocket-Code, Plugin-System oder asynchrone Kernarchitektur in Version 1 einzuführen.
- Die vollständige Vereinheitlichung der Ressourcenbudgets für alle Quellen, Skripte und Bundle-Nutzdateien bleibt gezielt in Step 4.b.

---

# Meilenstein 3 – PatchBundle, Execution und Ausgabe

## Ziel

Der transportneutrale PatchBundle-Kern unterstützt mehrere Skripte und bytegenaue Text- oder Binärdateien. Prozesse werden anschließend auf Linux und Windows zuverlässig gesteuert; Output, Logging und die feste Terminaloberfläche funktionieren ohne Scroll-Effekt oder Prozesslecks.

## Scope

- transportneutrale Quellengrenze mit `InputArtifact`,
- direkte Skripte und ZIP-Container als `PatchBundle`s,
- mehrere geordnete Skripte und bytegenaue Bundle-Nutzdateien,
- sichere relative Nutzdateipfade, vollständige Vorbereitung und atomisches Schreiben vor dem ersten Skript,
- kleiner Application-Orchestrator ohne Plugin-System,
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

- Datei und STDIN durchlaufen denselben Artefakt-zu-PatchBundle-Pfad.
- Ein direktes Skript und ein ZIP-basiertes PatchBundle werden quellenunabhängig aufgelöst.
- Ein ZIP-PatchBundle kann mehrere Skripte und echte Binärdateien bytegenau übertragen.
- Alle Bundle-Nutzdateien werden vor dem ersten Skript sicher bereitgestellt.
- Ein ungültiger oder nicht vollständig vorbereitbarer Bundle-Inhalt verhindert jede Skriptausführung.
- Quellen, PatchBundle-Auflösung, Nutzdateiverarbeitung, Parser, inline FILE-Verarbeitung und Execution haben eine gerichtete, zyklusfreie Abhängigkeitsrichtung.
- Bash und PowerShell werden deterministisch gewählt.
- Unbekannte Interpreter werden klar abgelehnt.
- Timeout und Strg+C beenden auch Kindprozesse.
- Output blockiert den Kindprozess nicht.
- Plain-Modus enthält keine ANSI-Cursorsteuerung.
- TUI bleibt fest, passt sich schmalen Terminals an und wird von Skript-ANSI nicht zerstört.
- Rolling Buffer und Logdatei funktionieren wie spezifiziert.
- Der verbleibende Plan wurde geprüft.

---

## Step 3.a – Transportneutrale Artefakt- und PatchBundle-Grenze einführen

**Ergebnis:** Datei und Pipe liefern denselben neutralen Eingang; direkte Skripte und ZIPs werden unabhängig von ihrer Quelle zu einem `PatchBundle` aufgelöst.

### 3.a.W – Einheitlichen Artefakt-zu-PatchBundle-Durchlauf implementieren

- kleine unveränderliche Modelle `InputArtifact` und `PatchBundle` einführen,
- vorhandene Datei direkt als Artefakt referenzieren,
- STDIN als Byte-Strom sicher in ein temporäres Artefakt schreiben,
- direktes Skript als PatchBundle mit einem Skript abbilden,
- ZIP als PatchBundle mit geordneten Skripten auflösen,
- Datei-, Pipe- und ZIP-Verhalten über denselben Anwendungsweg ausführen,
- E2E-Tests ergänzen, die gleiche Semantik und Archiv-Reihenfolge prüfen.

### 3.a.R – Quellen, PatchBundle-Auflösung und Anwendung fachlich trennen

- Quellenzugriff nach `sources.py` verschieben,
- direkte Skript- und ZIP-Auflösung nach `bundles.py` verschieben,
- sequenzielle Auftragssteuerung in einem kleinen `application.py` bündeln,
- Parser reine Skript- und inline FILE-Beschreibungen liefern lassen,
- Dateinamenprüfung und Schreiben ausschließlich in der Nutzdateiverarbeitung halten,
- Execution von Quelle, ZIP und Parser entkoppeln,
- Importtests oder Architekturtests für die gerichtete Abhängigkeit ergänzen.

### 3.a.C – Übergabegrenze vereinfachen und Altpfade entfernen

- alte quellenspezifische Ausführungszweige und doppelte ZIP-Behandlung entfernen,
- temporäre Artefaktverwaltung auf genau einen Cleanup-Pfad reduzieren,
- Modelle auf tatsächlich benötigte Felder begrenzen,
- keine Plugin-Basisklasse, Registry, WebSocket-Bibliothek oder Async-Kernarchitektur hinzufügen,
- vorhandene Verhaltenstests grün halten und fragile Implementierungsassertions entfernen.

---

## Step 3.b – Binäre Bundle-Nutzdateien sicher bereitstellen

**Ergebnis:** Ein ZIP-basiertes PatchBundle kann mehrere Skripte und beliebige Text- oder Binärdateien übertragen; alle Nutzdateien stehen bytegenau vor dem ersten Skript bereit.

### 3.b.W – Bundle-Nutzdateien vertikal implementieren

- `PatchBundle` um geordnete `BundlePayload`-Beschreibungen erweitern,
- reguläre ZIP-Einträge mit Pflichtmarker als Skripte und alle anderen regulären Einträge als Nutzdateien klassifizieren,
- Binärdaten ohne UTF-8-Konvertierung bytegenau lesen und schreiben,
- sichere relative Unterordner aus dem ZIP übernehmen,
- alle Bundle-Nutzdateien vor dem ersten Skript bereitstellen,
- Skripte weiterhin in Archiv-Reihenfolge ausführen,
- E2E-Test mit mehreren Skripten und einer Binärdatei einschließlich Nullbytes ergänzen,
- im Test nachweisen, dass die Binärdatei bereits für das erste Skript verfügbar und bytegenau ist.

### 3.b.R – Bundle vollständig validieren und fatal absichern

- gesamte Archivstruktur vor dem ersten Zielschreibvorgang validieren,
- absolute Pfade, Zwei-Punkte-Segmente, Backslashes, reservierte Windows-Namen und überlange Pfade ablehnen,
- Links, besondere Eintragstypen, doppelte normalisierte Ziele und Groß-/Kleinschreibungs-Kollisionen ablehnen,
- Bundle-Nutzdateien vollständig im aufgelösten PatchBundle vorbereiten,
- tatsächliche Schreibfehler fatal behandeln und jede Skriptausführung verhindern,
- ZIP ohne gültiges PatchHarbor-Skript weiterhin ablehnen,
- markerlose Skriptdateien nur übertragen und niemals ausführen,
- Tests für beschädigte, unsichere, doppelte und reine Datei-Bundles ergänzen.

### 3.b.C – Bundle-Payload-Pipeline vereinfachen

- gemeinsame atomare Schreibprimitive für Bundle-Nutzdateien und inline FILE-Inhalte nutzen, ohne ihre unterschiedlichen Namensregeln zu vermischen,
- vollständiges Entpacken in das Projektverzeichnis und unnötige Bytekopien vermeiden,
- Skripteinträge, Nutzdateien und Verzeichniseinträge mit wenigen klaren Modellen darstellen,
- Fehlertexte auf ungültiges Bundle, Ressourcenfehler und tatsächlichen Schreibfehler begrenzen,
- Tests auf sichtbares Verhalten und Bytegleichheit statt interne ZIP-Objekte ausrichten.

---

## Step 3.c – Interpreterauswahl und PowerShell-Vertrag härten

**Ergebnis:** Der Interpreter wird aus einer kleinen Whitelist deterministisch gewählt.

### 3.c.W – Bash- und PowerShell-Auswahl implementieren

- Linux ohne Shebang auf Bash abbilden,
- Windows ohne Shebang auf Windows PowerShell abbilden,
- bekannte Bash-, Windows-PowerShell- und PowerShell-7-Shebangs erkennen,
- unbekannte Shebangs ablehnen,
- Interpreterverfügbarkeit vor Prozessstart prüfen,
- PowerShell ohne Profil und nicht interaktiv starten,
- E2E-Tests für Defaults, bekannte Shebangs und fehlenden Interpreter ergänzen.

### 3.c.R – Interpreterresolver plattformneutral strukturieren

- Shebang-Auswertung, Plattformdefault, Verfügbarkeitsprüfung und Prozessargumente in `interpreters.py` trennen,
- freie oder um Argumente erweiterte Shebang-Kommandos vor jeder Interpretersuche ablehnen,
- temporäre Dateiendung nur aus dem bereits gewählten Interpreter ableiten und nie als Typentscheidung verwenden,
- PowerShell ohne `-ExecutionPolicy` oder `Bypass` starten,
- native PowerShell-Policyfehler sichtbar lassen und den Prozess-Exit-Code unverändert zurückgeben,
- Unit- und Architekturtests auf die neue gerichtete Grenze ausrichten.

### 3.c.C – Interpreterlogik vereinfachen

- `BundleScript` und Execution nicht mehr mit bedeutungslosen Quelldateiendungen belasten,
- die technische temporäre Dateiendung ausschließlich aus dem gewählten Interpreter ableiten,
- Interpretermodelle auf die tatsächlich zur Ausführung benötigten Felder reduzieren,
- gemeinsame feste PowerShell-Argumente nur einmal definieren,
- die exakte Whitelist und die knappen Interpreterfehler unverändert beibehalten,
- Tests auf öffentlich sichtbares Auswahl- und Ausführungsverhalten statt auf Quelldateiendungen ausrichten.

---

## Step 3.d – Prozessbaum, Timeout und Strg+C zuverlässig steuern

**Ergebnis:** PatchHarbor hinterlässt nach Ende, Timeout oder Abbruch keine Kindprozesse.

### 3.d.W – Plattformgerechte Prozessgruppen implementieren

- unter Linux eine eigene Prozesssitzung beziehungsweise Gruppe starten,
- unter Windows den Prozess in einem Job Object verwalten,
- Timeout zunächst geordnet und nach zwei Sekunden hart beenden,
- Strg+C auf den gesamten Prozessbaum anwenden,
- Exit-Codes 124 und 130 liefern,
- echte E2E-Tests mit einem Kindprozess auf beiden Plattformen ergänzen.

### 3.d.R – Plattformcode hinter kleinem Lifecycle-Vertrag isolieren

- Linux- und Windows-Details in `platform/` trennen,
- Execution nur eine kleine Start-, Stop- und Kill-Schnittstelle kennen lassen,
- Race Conditions zwischen natürlichem Ende, Timeout und Strg+C behandeln,
- Cleanup auch bei Exceptions garantieren.

### 3.d.C – Prozesssteuerung vereinfachen und härten

- redundante Signalpfade entfernen,
- genau eine Zustandsmaschine für läuft, beendet, Timeout und Abbruch verwenden,
- Wartezeiten und Polling zentralisieren,
- Tests auf tatsächliches Prozessende statt interne Funktionsaufrufe ausrichten.

---

## Step 3.e – Output fortlaufend erfassen und begrenzen

**Ergebnis:** STDOUT und STDERR erscheinen gemeinsam, ohne Deadlock und ohne unbegrenzten RAM-Verbrauch.

### 3.e.W – Zusammengeführten Output und Rolling Buffer implementieren

- STDOUT und STDERR in einen gemeinsamen Stream führen,
- Output während des Laufs fortlaufend lesen,
- letzte zehn Zeilen im Rolling Buffer halten,
- zunächst die letzten fünf Zeilen in einfacher Textdarstellung ausgeben,
- lange Zeile und letzte Zeile ohne Zeilenumbruch unterstützen,
- E2E-Tests für viel Output, gemischte Streams und schnellen Prozess ergänzen.

### 3.e.R – Streaming und Decodierung robust strukturieren

- Byte-Lesen von Textdecodierung und Zeilenbildung trennen,
- fehlerhafte Zeichen mit Ersatzdarstellung statt Crash behandeln,
- Thread- oder Async-Lösung so kapseln, dass der Prozess nie wegen voller Pipe blockiert,
- Zähler für verworfene ältere Zeilen bereitstellen.

### 3.e.C – Buffer und Reader vereinfachen

- geeignete begrenzte Datenstruktur verwenden,
- unnötige vollständige Outputkopien entfernen,
- Zeilen- und Chunklogik zusammenführen, wo sie fachlich identisch ist,
- Performance nur anhand realer Tests optimieren.

---

## Step 3.f – Plain-Ausgabe und vollständiges Temp-Log ergänzen

**Ergebnis:** Automation erhält saubere Textausgabe; Debugging kann den vollständigen Output sichern.

### 3.f.W – Plain-Modus und `--log` implementieren

- bei Nicht-TTY automatisch einfache fortlaufende Ausgabe verwenden,
- `--plain` und `--no-color` ergänzen,
- mit `--log` eine sichere eindeutige Datei im System-Temp-Verzeichnis erzeugen,
- vollständigen zusammengeführten Output und Run-Metadaten schreiben,
- Logpfad am Ende anzeigen,
- E2E-Tests für Plain-Ausgabe und Loginhalt ergänzen.

### 3.f.R – Ausgabeziele und Log-Lebenszyklus trennen

- Terminaldarstellung, Plain-Sink und Log-Sink sauber koordinieren,
- Logging vom Rolling Buffer unabhängig machen,
- rohe Skriptausgabe im Log und bereinigte Ausgabe im UI unterscheiden,
- sichere Tempdateierzeugung und korrektes Schließen auf allen Fehlerpfaden sicherstellen.

### 3.f.C – Output-Pipeline entschlacken

- unnötiges allgemeines Logging-Framework vermeiden,
- Ausgabeziele über kleine Funktionen oder einen schmalen Vertrag anbinden,
- doppelte Präfixe und Statuszeilen entfernen,
- Logformat auf die tatsächlich nützlichen Informationen begrenzen.

---

## Step 3.g – Feste TUI mit Redraw alle 0,2 Sekunden bauen

**Ergebnis:** Im interaktiven Terminal bleibt eine kompakte feste Oberfläche ohne Scroll-Effekt sichtbar.

### 3.g.W – Dashboard und periodischen Redraw implementieren

- Bereiche Source, Messages, Files, Execution und Result darstellen,
- maximale Breite 80 und tatsächliche Terminalbreite berücksichtigen,
- alle 0,2 Sekunden während der Execution neu zeichnen,
- nach Ende sofort final rendern,
- letzte fünf Outputzeilen anzeigen,
- feste Bereichshöhen und Überlaufhinweise implementieren,
- Renderer-Tests und einen interaktiven Smoke-Test ergänzen.

### 3.g.R – Terminalschutz und Fallbacks ergänzen

- ANSI-Steuersequenzen aus sichtbarem Skriptoutput entfernen,
- Cursorzustand und Farben auch bei Exception oder Strg+C wiederherstellen,
- bei zu schmalem Terminal automatisch in Plain wechseln,
- horizontales Kürzen ohne unbeabsichtigte Zeilenumbrüche sicherstellen,
- TUI-Zustandsmodell von Execution entkoppeln.

### 3.g.C – TUI beruhigen und vereinfachen

- Zustandsänderungen sammeln und höchstens beim nächsten 0,2-Sekunden-Tick darstellen,
- identische Frames nicht erneut in das Terminal schreiben,
- bei geänderter Terminalbreite neu rendern und den finalen Zustand sofort ausgeben,
- Darstellung auf Source, Messages, Files, Execution und Result begrenzen,
- keine Scroll-, Auswahl- oder Framework-Funktionen hinzufügen,
- Meilenstein 3 reviewen und den verbleibenden Plan gezielt aktualisieren.

---

## Review nach Meilenstein 3

- Der transportneutrale Pfad von Quelle über `InputArtifact` und `PatchBundle` bis zur Execution ist umgesetzt; ein Neustart ist nicht erforderlich.
- ZIP-PatchBundles tragen mehrere geordnete Skripte sowie bytegenaue Text- und Binärdateien. WebSocket kann später denselben Artefakt- und Bundlepfad verwenden, ohne den Runner-Kern zu verändern.
- Interpreterwahl, Prozessbaum-Lifecycle, Timeout, Strg+C, Output-Capture, Plain-Modus, Temp-Log und feste TUI sind fachlich getrennt und durch Verhaltens- sowie Architekturtests abgesichert.
- Das Dashboard schreibt identische Frames nicht erneut, bleibt auf die vereinbarten fünf Bereiche begrenzt und verwendet weiterhin nur ANSI-Cursorsteuerung ohne TUI-Framework.
- Der plattformübergreifende Release-Nachweis, insbesondere auf echtem Windows, bleibt bewusst Aufgabe von Meilenstein 4 und wird nicht durch weitere Architekturarbeit in Meilenstein 3 vorweggenommen.
- Der Restplan bleibt bei den vier Steps 4.a bis 4.d: Plattformfälle, Ressourcenbudgets, CI-Akzeptanzsuite und Release-Audit. Es ist kein zusätzlicher Version-1-Step nötig.
- WebSocket bleibt vollständig außerhalb von Version 1 und wird erst nach dem Review von Meilenstein 4 in eigene W-R-C-Commits zerlegt.

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
- ZIP-Bundle-, Binärdatei-, Pfad- und inline FILE-Sicherheitsfälle sind grün,
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
- Terminal-Fallback, Cursor-Wiederherstellung und `--no-color` auf Linux und Windows prüfen,
- Plattform-E2E-Tests für inline FILE, ZIP-PatchBundle mit Binärdatei, Timeout und Logging hinzufügen.

### 4.a.R – OS-spezifische Logik an klare Grenzen verschieben

- plattformspezifische Prozess- und Dateisystemteile aus allgemeinen Modulen entfernen,
- gemeinsame fachliche Regeln in plattformneutralen Funktionen halten,
- Skip-Bedingungen in Tests begründen und zentralisieren,
- Fehlertexte auf beiden Systemen semantisch angleichen.

### 4.a.C – Plattformcode und Fixtures vereinfachen

- den Plattformvertrag auf eine einfache Windows-Erkennung statt einer zusätzlichen Familien-Enumeration reduzieren,
- gemeinsame Linux- und Windows-Testwerte zentral auswählen und nur echte Skriptunterschiede getrennt halten,
- ungenutzten Dateisystem-Fehlerzustand entfernen,
- Docker-Testwerkzeuge nur einmal aus den Projekt-Testabhängigkeiten installieren,
- mit Packaging- und Architekturtests absichern, dass PatchHarbor zur Laufzeit bei der Python-Standardbibliothek bleibt und das Wheel kompakt bleibt.

## Review nach Step 4.a

- Linux-Verhalten ist lokal sowie in Docker auf Ubuntu 24.04 und Ubuntu 26.04 grün.
- Die Plattformgrenzen für Runtime, Dateisystem und Prozessbaum sind klein und gerichtet.
- PatchHarbor besitzt weiterhin keine Laufzeitabhängigkeiten außerhalb der Python-Standardbibliothek.
- Die echte Windows-Release-Lane bleibt bewusst Bestandteil von Step 4.c; ein Neustart oder weiterer Plattform-Abstraktionslayer ist nicht erforderlich.

---

## Step 4.b – Ressourcenbudgets und Missbrauchsschutz abschließen

**Ergebnis:** Große oder manipulierte Eingaben führen kontrolliert zu Warning oder Tool-Fehler statt Ressourcenerschöpfung.

### 4.b.W – Harte Budgets und Angriffsfälle testen

- Grenzen für direkte Eingabe, Skript- und Nutzdateieintrag, ZIP-Gesamtdaten und Eintragszahl implementieren,
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

- duplizierte Größen- und Warning-Zustände aus `InputArtifact` und Dateiquellen entfernen,
- vorhandene Dateien zentral im Resolver prüfen und STDIN nur während des Empfangs begrenzen,
- die Lese-Chunkgröße als I/O-Detail aus der `ResourcePolicy` entfernen,
- keine allgemeine Quota-, Registry- oder konfigurierbare Policy-Engine bauen,
- im Help nur erklären, dass übergroße oder unsichere Eingaben vor dem ersten Skript abgelehnt werden,
- Tests auf exakt akzeptierte und überschrittene Grenzen statt private Zähler oder Hilfsmethoden ausrichten.

## Review nach Step 4.b

- Die Version-1-Budgets bleiben zentral, unveränderlich und für alle Eingabewege konsistent.
- Vorhandene Dateien tragen keinen duplizierten Größen- oder Warning-Zustand mehr; der Resolver besitzt die fachliche Prüfung.
- STDIN bleibt während des Empfangs begrenzt, und ZIPs behalten bewusst sowohl die deklarierte Vorabprüfung als auch die Prüfung der tatsächlich gelesenen Bytes.
- Es gibt keine allgemeine Quota-Engine, keine öffentliche Policy-Konfiguration und keine neue Laufzeitabhängigkeit.
- Verhaltenstests decken die exakt erlaubte Grenze, die erste Überschreitung, ZIP-Gesamtbudgets und die Ausführungssperre vor dem ersten Skript ab.
- Der verbleibende Plan kann ohne zusätzlichen Step mit der plattformübergreifenden Akzeptanzsuite in 4.c fortgesetzt werden.

---

## Step 4.c – Akzeptanzsuite und GitHub Actions etablieren

**Ergebnis:** Der reale Nutzerworkflow wird automatisiert auf Linux und Windows geprüft.

### 4.c.W – E2E-Akzeptanzsuite und CI-Matrix einführen

- vollständige E2E-Szenarien für Datei, Ordner, ZIP-PatchBundle mit mehreren Skripten und Binärdateien, Pipe, Messages, inline FILE, Timeout, Logging und Exit-Codes bündeln,
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

- die Akzeptanzsuite als eindeutigen Besitzer der öffentlichen Happy Paths für Pipe, Timeout, Exit-Code, Ordnerwahl, ZIP-Bundle und Windows-Interpreter festlegen und identische ältere E2E-Fälle entfernen,
- gemeinsame echte CLI-Subprozesshelfer in `tests/platform_support.py` bündeln, statt sie in mehreren Testdateien zu duplizieren,
- TUI-Tests auf Abschnittsreihenfolge, Breitenbegrenzung, Zustandswechsel, Redraw und Terminal-Wiederherstellung ausrichten statt vollständige Frame-Bytes oder feste Zeilenzahlen zu vergleichen,
- Test-Doubles nur an der CLI-zu-Anwendung-Grenze und an unvermeidbaren Betriebssystemgrenzen verwenden,
- lokale und CI-Testläufe um eine kurze Liste der langsamsten Tests ergänzen, ohne Retries oder zusätzliche Laufzeitabhängigkeiten einzuführen.

## Review nach Step 4.c

- Die Akzeptanzsuite enthält je öffentlichen Hauptworkflow genau einen plattformübergreifenden Nachweis; granulare E2E-Tests bleiben für Fehler- und Sonderfälle zuständig.
- Doppelte Happy-Path-Subprozesse wurden entfernt, ohne die Aussagen zu Pipe, Timeout, Exit-Code, Ordnerwahl, ZIP-PatchBundle oder PowerShell zu verlieren.
- TUI-Verhalten wird über Rendererzustand, Begrenzung, Redraw und Terminal-Cleanup geprüft; private Bytefolgen und feste Framehöhen sind kein Testvertrag.
- Ubuntu 24.04 und Windows bleiben blockierende Release-Gates, Ubuntu 26.04 bleibt die nicht blockierende Preview-Lane.
- Diagnoseausgaben zeigen die langsamsten Tests; pauschale Retries, zusätzliche Mock-Schichten oder ein zweites Testframework wurden nicht eingeführt.
- Der verbleibende Version-1-Plan kann ohne neuen Step mit Packaging, Release-Audit und finaler Bereinigung in Step 4.d fortgesetzt werden.

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

- Importabhängigkeiten einschließlich des vollständigen `platform/`-Teilgraphen gegen die vereinbarte Richtung und auf Zyklen prüfen,
- CLI, Sources, PatchBundle-Auflösung, Bundle-Nutzdateien, Parser, inline FILE, Execution und Presentation auf klare Grenzen prüfen,
- internen Exit-Code 6 als allgemeinen Payload-Vorbereitungsfehler benennen und sichtbare Tool- sowie Warning-Präfixe zentralisieren,
- sicherstellen, dass Clipboard, WebSocket, SSH, Save, Tests und Git weder als öffentliche Befehle noch als Laufzeitmodule enthalten sind,
- Release-Artefakte aus einem sauberen, explizit gestagten Quellbaum bauen, damit gelöschte Altmodule nicht aus veralteten Build-Verzeichnissen in das Wheel gelangen,
- den exakten Laufzeitmodulbestand, den einzigen Konsolen-Entry-Point, fehlende Laufzeitabhängigkeiten, Lizenz und Source-Distribution prüfen,
- denselben sauberen Release-Build in Packaging-Test und Docker-Integration verwenden.

**Auditentscheidung:** Der Runner-Kern und die gerichtete Architektur bleiben erhalten. Das Audit darf keine neue Produktfunktion einführen; es schließt ausschließlich Release-, Namens- und Grenzfehler vor dem finalen Clean-Commit.

### 4.d.C – Finalen Ballast entfernen und Plan abschließen

- tote Module, ungenutzte Optionen und spekulative Abstraktionen löschen,
- Namen und Help-Texte final vereinheitlichen,
- alle lokal verfügbaren Prüfungen und beide Ubuntu-Docker-Läufe ausführen,
- verbleibenden Commit-Plan und Risiken abschließend reviewen,
- Version 1 nur veröffentlichen, wenn die stabilen CI-Gates auf dem exakten finalen Commit grün sind.

## Review nach Step 4.d und Meilenstein 4

- Der Version-1-Implementierungsplan ist mit 20 Steps und 60 W-R-C-Commits vollständig umgesetzt; ein Neustart oder zusätzlicher Version-1-Step ist nicht erforderlich.
- Wheel und Source-Distribution werden aus einem sauberen, expliziten Quellbestand gebaut. Das Wheel enthält nur die geprüften Laufzeitmodule; die Source-Distribution enthält keinen Testbestand und keine Release-Hilfsskripte.
- PatchHarbor besitzt genau einen öffentlichen Konsolenbefehl, keine Laufzeitabhängigkeit außerhalb der Python-Standardbibliothek und keine halbfertige öffentliche Funktion.
- Die lokale Testsuite sowie die Docker-Läufe auf Ubuntu 24.04 und Ubuntu 26.04 müssen im finalen Commit-Patch grün sein. Ubuntu 24.04 und Windows 2025 bleiben die stabilen Release-Gates; Ubuntu 26.04 bleibt eine nicht blockierende Preview-Lane.
- Release-Tag und Veröffentlichung bleiben bis zu grünen stabilen CI-Gates auf dem exakten Commit `4.d.C` gesperrt. Ein lokaler Linux- oder Docker-Lauf ersetzt den echten Windows-Runner nicht.
- Bekannte und akzeptierte Grenzen bleiben: keine Sandbox gegen das ausgeführte Skript, atomare Ersetzung je Datei statt Gesamttransaktion über ein Bundle, temporäre statt dauerhafte Logverwaltung und kein Umgehen der PowerShell Execution Policy.
- WebSocket bleibt außerhalb von Version 1. Vor einem detaillierten Meilenstein-5-Plan sind Antwortformat, Bindung, Authentifizierung, TLS, Limits, Warteschlange und Abbruchsemantik verbindlich zu entscheiden.

**Umsetzungsstand Version 1:** `60 / 60` geplante W-R-C-Commits abgeschlossen. Der Code ist ein Release Candidate; die Freigabe von `1.0.0` erfolgt erst nach den grünen stabilen CI-Gates.

---

# Meilenstein 5 – WebSocket-Transport, nach Version 1

## Ziel

Ein äußerer WebSocket-Host kann vollständige PatchHarbor-Skripte und unveränderte ZIP-basierte PatchBundles mit mehreren Skripten und echten Binärdateien entgegennehmen und sie ohne Sonderpfad als normale Runner-Aufträge verarbeiten lassen.

## Bereits festgelegte Grenze

- Textnachricht ergibt ein direktes Skript-Artefakt.
- Binärnachricht ergibt bytegenau ein vollständiges ZIP-basiertes PatchBundle.
- Dasselbe Bundleformat wird aus Datei, Pipe und WebSocket verarbeitet.
- Ein Bundle darf mehrere geordnete PatchHarbor-Skripte und beliebige sichere Text- oder Binärdateien enthalten.
- Eine vollständige Nachricht ergibt genau einen Runner-Auftrag.
- Der Runner bleibt zustandslos und verarbeitet weiterhin genau ein Artefakt pro Auftrag.
- Im selben Arbeitsverzeichnis werden Aufträge sequenziell ausgeführt.
- WebSocket darf die PatchBundle-, Nutzdatei-, Parser-, FILE-, Execution- und Presentation-Pipeline nicht umgehen.

## Entscheidungstor nach Meilenstein 4

Vor der Zerlegung in konkrete Steps und W-R-C-Commits werden verbindlich entschieden:

- Antwortformat und Zuordnung von Auftrag zu Ergebnis,
- lokale Standardbindung und Freigabe für Remote-Zugriff,
- Authentifizierung und Autorisierung,
- TLS beziehungsweise sicherer Transport,
- Größen-, Verbindungs- und Ratenlimits,
- Warteschlange, Backpressure und Abbruch bei Verbindungsverlust,
- Linux- und Windows-Akzeptanztests.

Meilenstein 5 gehört nicht zum Releaseumfang von Version 1. Sein detaillierter Commit-Plan entsteht erst nach dem Review von Meilenstein 4.

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

Der abgeschlossene Version-1-Implementierungsplan besteht aus:

- **4 Release-Meilensteinen**,
- **20 Steps**,
- **60 geplanten Commits**,
- pro Step genau einem `W`-, einem `R`- und einem `C`-Commit.

**Umsetzungsstand:** `60 / 60` geplante Commits sind abgeschlossen. Veröffentlichung und Release-Tag bleiben bis zum grünen Ubuntu-24.04- und Windows-Gate des finalen Commits gesperrt.

Zusätzlich ist **Meilenstein 5 – WebSocket-Transport** als nachgelagertes Ziel dokumentiert. Seine Steps und Commits werden bewusst erst nach dem Review von Meilenstein 4 festgelegt.

Die Reihenfolge ist bewusst vertikal:

**Meilenstein → Step → work → right → clean**

Der erste Step liefert den kleinsten ausführbaren Datei-Run ohne TUI. Danach folgen Eingaben und inline Nutzdaten. Vor der weiteren Execution-Arbeit trennt Step 3.a Quellen, Eingabeartefakte und PatchBundles. Step 3.b ergänzt darauf mehrere Skripte und bytegenaue Binärdateien im ZIP-Bundle. Anschließend werden kontrollierte Execution und Ausgabe sowie Plattform- und Release-Qualität ergänzt.

Die Leitlinie bleibt über den gesamten Plan gleich:

**minimal implementieren, fachlich richtig schneiden, anschließend konsequent vereinfachen.**

---

## Quellenhinweis zur CI-Planung

Die CI-Zielauswahl orientiert sich am aktuellen Stand der offiziellen GitHub-Dokumentation und des offiziellen `actions/runner-images`-Repositories. Ubuntu 26.04 ist zum Zeitpunkt dieses Plans als GitHub-Actions-Runner verfügbar, wird aber zunächst vorsichtig als zusätzliche Lane behandelt. GitHub-gehostete Runner stellen Linux- und Windows-Umgebungen bereit; auf GitHub-gehosteten Runnern ist PowerShell 7 verfügbar.
