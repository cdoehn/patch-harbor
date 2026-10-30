# PatchHarbor 1.5.0 – Refactoring- und Commitplan

**Plan-ID:** `REFACTOR-1.5.0`
**Revision:** 10 · 30. Oktober 2026
**Zielversion:** 1.5.0; die Produktversion bleibt bis RF-13 bei 1.4.0.
**Status:** RF-00 bis RF-07 bestätigt; RF-08 als Bundle 065 vorbereitet, Apply offen.
**Fortschritt:** 8 / 14 Planpositionen und 9 / 15 vorgesehene Commits bestätigt.
**Aktueller Auftrag:** genau das nächste Arbeitspaket RF-08 erstellen; keine übernommene Automatik aus älteren Plänen.
**Gemeinsame normative Grundlage:** [Hauptspezifikation](../../spec/SPECIFICATION.md),
[PYZ/PACK-Erweiterung](../../spec/SPECIFICATION_EXTENSION_PYZ_PACK.md) und
[CPython-3.10/3.11-Erweiterung](../../spec/SPECIFICATION_EXTENSION_CPYTHON_310_311.md),
mit den ausdrücklichen Nutzerentscheidungen in Abschnitt 2.

## 1. Zweck, bestätigte Ausgangsbasis und Arbeitsgrenze

Dieser Plan reduziert überholten Produktcode, mehrfach gepflegte ausführbare
Inhalte und unnötige Kopplung zwischen Tests und Implementierung. Er umfasst die
Empfehlungen zur Altformatbereinigung, Testorganisation, Bootstrap-Erzeugung,
CLI-/Application-Aufteilung und CI-Nachweispflege. Die Spezifikation wird
ausdrücklich **nicht zusammengeführt, neu aufgeteilt oder grundlegend umgeschrieben**.
Ihre bestehenden Dateien und Zuständigkeiten bleiben erhalten. Nur konkrete
grobe Fehler und widersprüchliche aktuelle Anforderungen werden gezielt korrigiert.

| Technische Basis von Bundle 056 | Vollständiger Wert |
| --- | --- |
| Repository-ID | `e7a93d72-62dc-4759-97e8-6bf6cdf10e90` |
| Zielbranch | `dev` |
| Apply-Commit | `caad28b84bdf9461c98cf8a218061e06ff894074` |
| Result | `patchharbor-apply_Result_102601_1029_f051fd.zip` |
| Result-SHA-256 | `3a073753032fa7f3218b76b1e3ebd6d8365e13f760a4811ab8585474097ed19b` |
| State-Fingerprint | `7c9d2a24e397e0e5` |
| Fingerprint-Algorithmus | `patchharbor-state-v1` |
| Snapshot | 354 Dateien; sauber; Resultformat 3; eingebettete Core-PYZ 1.4.0 |
| Herkunft dieses Results | tatsächlicher `bundle`-Aufruf, kein Dry-Run, kein Apply-/Commitnachweis |

Integrität, Inventar und Binding dieser Ausgangsbasis wurden gegen das aktuell
saubere Apply-Repository gelesen geprüft. Das Result bestätigt den Startzustand,
nicht den Abschluss älterer offener Abnahmen. Insbesondere werden offene
CPython-Abnahmen nicht allein durch den neuen Plan als bestanden erklärt.
Der vorhandene Versionscommit und das Tag 1.4.0 ersetzen keine fehlenden
CI-/Praxisnachweise. Deren Historie bleibt im bisherigen Plan erhalten.

Jedes Folgebundle benötigt sein eigenes aktuelles maßgebliches Result. Die Werte
oben sind Provenienz dieses Starts, keine wiederzuverwendende globale Bindung.
Development arbeitet ausschließlich in `patchharbor-codex`, bei Bedarf in einem
aus dem Result rekonstruierten Arbeitsverzeichnis unter `build/`. Die alten
uncommitteten Dateien im Development-Root werden nicht überschrieben.
Nur eine fertig geprüfte ZIP wird atomar im Exchange veröffentlicht. Der bestehende
Watcher übernimmt Apply, Tests, autorisierte Commits und den abschließenden Push.

RF-00 liefert nur diesen Plan und seine aktiven Verweise in README und
Chat-Anleitung. Quellcode, Tests, Paketversion, ausführbarer Bootstrap,
Abhängigkeiten, CI-YAML und die drei Spezifikationsdateien bleiben in RF-00 gleich.

## 2. Autorisierte Zielverträge und ausdrücklich erhaltenes Verhalten

### 2.1 Kompatibilitätsbasis ab 1.4.0

Christians Entscheidungen vom 29. Oktober 2026 ersetzen die bisherige Pflicht,
Result- und Patch-Artefakte aller Versionen vor 1.4.0 weiterhin zu bearbeiten.
**Spätere Versionen müssen gültige Artefakte aus 1.4.0 und den danach unterstützten
Vertragsständen weiterhin lesen und bestimmungsgemäß verarbeiten können.**
Das ist Abwärtskompatibilität des neuen Lesers. Ein alter 1.4.0-Leser muss nicht
unbekannte zukünftige Formate verstehen. Unbekannte Formate werden konservativ
behandelt; es gibt keinen permissiven Universalparser.

| Vertrag der 1.4.0-Basis | Bleibt unterstützt |
| --- | --- |
| Patchmanifest | Patchformat 1, derselbe Marker und dieselben sieben Felder |
| Resultmanifest | Resultformat 3 einschließlich sauberer/dirty Zustände und Fehler-/Dry-Run-Daten |
| Runtime-Metadaten | Format 2; vorhandene eingebettete und `unavailable`-Formen |
| Core-PYZ | Rezeptformat 1, bestehende IDs/Hashes und Profil `patchharbor-core-no-watcher-v1`; kein Watcher |
| Python | CPython 3.10/3.11 sowie vorhandene 3.12-/3.14-Nachweise |
| Begleitdaten und API | vorhandene Environment-/Handoff-Formate, öffentliche Signaturen, Ergebnisfelder und Fehlerkategorien |

Produktversion und Formatnummer sind unterschiedliche Angaben. Patchformat 1
ist **kein** zu entfernendes Altformat. Das Patchmanifest enthält keine
Produzenten-Versionsnummer: Eine künstliche Versionssperre, neue Pflichtfelder
oder ein Erraten der Produktversion aus Dateinamen sind nicht Teil dieses Plans.
Ein älteres Paket mit identischem weiterhin gültigem Vertrag kann weiterhin
lesbar sein, ohne dass daraus eine allgemeine Altkompatibilitätszusage folgt.

Unveränderte 1.4.0-Results enthalten die Runtime-Capabilities
`result_formats: [1, 2, 3]`. Neue Leser müssen diese Originaldaten weiter
akzeptieren. Das Feld beschreibt den eingebetteten Produzenten, nicht die
Supportpflicht des aktuell lesenden Programms. Neue bereinigte Produzenten
deklarieren ihre tatsächlich unterstützten Resultformate wahrheitsgemäß.
RF-01/RF-06 definieren und testen die geschlossenen zulässigen Varianten
`[1, 2, 3]` für Bestandsartefakte und `[3]` für den bereinigten Produzenten.
Vorhandene Bytes, Profil-/Rezeptidentitäten und Hashes werden nie umgeschrieben.
Neue Schemas dürfen nur mit ausdrücklich versioniertem Vertrag hinzukommen;
für diese reine Capability-Einschränkung werden keine Felder umgedeutet.

Entfallen dürfen die eigenständigen Result-1-/Result-2-Lesepfade, das alte
eingebettete Runtime-Wheel und dessen Installations-Bootstrap sowie ausschließlich
für vor-1.4.0-Produzenten notwendige PYZ-Varianten und positive Kompatibilitätstests.
Einige alte/malformed/future Eingaben bleiben als negative Sicherheitsfixtures
erhalten. Abgelehnte oder nicht unterstützte Results sind niemals Erfolgs-,
Replay-, Recovery- oder Archivierungsnachweise und lösen keine Ersatz-Ausführung aus.

### 2.2 Unveränderte Sicherheits- und Betriebsgrenzen

- Keine neue Produktfunktion, kein Transportdienst, Plugin-System oder eigener
  Test-/Commitmanager im Core. Öffentliche API, CLI und Watcher nutzen dieselbe Fachlogik.
- Das normale Installations-Wheel, sdist, pip-/pipx-Installationswege und der
  separat installierte Watcher bleiben erhalten. Nur das **alte Result-Runtime-Wheel** entfällt.
- Die CPython-3.10/3.11-Adapter unter Windows bleiben erforderlich. Creation-/Change-Time,
  Handle-Identität, DACLs, Junctions/Reparse-Points und No-follow werden nicht vereinfacht.
- Vollständige Repositorybindung, Locks, sichere Pfade, Rechte, Symlink-Ablehnung,
  Ressourcenlimits, atomare Veröffentlichung und Prüfung tatsächlicher Bytes bleiben bestehen.
  250.000 Snapshot-Dateien, 250.010 äußere ZIP-Einträge und getrennte innere Limits bleiben erhalten.
- Result-Publikation behält ihre endlichen CIFS-Retries, Sync-Regeln, Diagnose und
  gemeinsame Zeitgrenze. `pack` behält No-replace und seinen separaten No-retry-Vertrag.
  Prüfungen an verschiedenen zeitlichen Sicherheitsgrenzen werden nicht zusammengelegt.
- Fehlgeschlagene Applies samt Teilfortschritten, Unterbrechung, Prozessbaum-Cleanup,
  numerische Exitcodes und maschinenlesbare Fehler bleiben unterscheidbar.
- Der Watcher bleibt ereignisgesteuert mit fünf Sekunden Quiet-Time, ohne periodischen
  Exchange-Poller. Seine Zustandsmaschine, Prozessgrenze und Deduplizierung bleiben erhalten.
- Core und PYZ bleiben ohne externe Runtime-Abhängigkeiten. Pack/Inspect/Referenz-Validate
  benötigen weiterhin weder Git, Netzwerk, Installer noch Shell.

### 2.3 Umfang der Spezifikationspflege

RF-01 bearbeitet die widersprüchlichen Altformatpflichten gezielt an ihren
bestehenden Stellen, insbesondere Hauptspec §§35–41, PYZ/PACK §§7–8/MIG und
CPython CPY-10–13. Ein kleiner aktueller Geltungshinweis ist zulässig; bloß ein
weiterer Hinweis bei unverändert widersprüchlicher aktueller Muss-Regel genügt nicht.
Historische Aussagen werden als Historie erkennbar erhalten, aktuelle Muss-Regeln
werden präzisiert. Die bereits autorisierte Nutzerentscheidung hat bis dahin Vorrang.

Keine vierte normative Ergänzung, keine große redaktionelle Konsolidierung, keine
Verschiebung der vorhandenen Normdateien. Das Changelog hält die punktuellen
Vertragsänderungen nachvollziehbar fest. Alte Commitpläne und Nachweise bleiben
historische Dokumente; ihre Formulierungen werden nicht nachträglich passend gemacht.

## 3. Reihenfolge und Commitübersicht

Jeder Schritt baut auf dem vorherigen **tatsächlich bestätigten** Zustand auf.
Die Reihenfolge schützt besonders die 1.4.0-Basis, bevor Kompatibilitätscode
entfernt wird. Mehrere fachlich abgegrenzte Schritte dürfen in einem Bundle liegen,
wenn jeder als echter Dateizustand mit eigenem vollständigen parallelen Apply-Gate
und anschließendem Commit entsteht. Es gibt keine künstliche W/R/C-Dreiteilung;
falls weitere Aufteilung nötig wird, wird der Plan vorher nachvollziehbar angepasst.

| Position | ID | Aktueller Status | Vorgesehener Commit |
| --- | --- | --- | --- |
| 1 / 14 | RF-00 | CONFIRMED – Bundle 056 | `docs(plan): define 1.5.0 refactoring sequence [RF-00]` |
| 2 / 14 | RF-01 | CONFIRMED – Bundle 057 | `docs(spec): establish compatibility baseline from 1.4.0 [RF-01]` |
| 3 / 14 | RF-02 | CONFIRMED – Bundle 058 | `test(compat): freeze supported 1.4.0 artifact contracts [RF-02]` |
| 4 / 14 | RF-03 | CONFIRMED – Bundle 059 | `refactor(tests): isolate shared fixtures from test modules [RF-03]` |
| 5 / 14 | RF-04 | CONFIRMED – Bundle 060 | `test(architecture): assert behavior and dependency boundaries [RF-04]` |
| 6 / 14 | RF-05 | CONFIRMED – Bundle 061 | `refactor(runtime): separate shared profile primitives from wheel support [RF-05]` |
| 7 / 14 | RF-06 | CONFIRMED – Bundles 062/063 | zwei aufeinanderfolgende Commits, siehe RF-06A/B unten |
| 8 / 14 | RF-07 | CONFIRMED – Bundle 064 | `refactor(bootstrap): generate embedded program from one source [RF-07]` |
| 9 / 14 | RF-08 | NEXT – Bundle 065 vorbereitet | `refactor(application): isolate configuration and exchange discovery [RF-08]` |
| 10 / 14 | RF-09 | OPEN | `refactor(application): clarify apply and result orchestration [RF-09]` |
| 11 / 14 | RF-10 | OPEN | `refactor(cli): share command plumbing and separate parser setup [RF-10]` |
| 12 / 14 | RF-11 | OPEN | `refactor(ci): centralize acceptance matrix and proof identities [RF-11]` |
| 13 / 14 | RF-12 | OPEN | `docs(refactor): align current guidance and record cleanup evidence [RF-12]` |
| 14 / 14 | RF-13 | OPEN | `chore(release): prepare PatchHarbor 1.5.0 acceptance [RF-13]` |

Die 14 Positionen schließen den Startcommit ein. RF-06 wird in zwei echte
aufeinanderfolgende Commits aufgeteilt; damit sind derzeit 15 Commits vorgesehen.
RF-06 gilt erst nach bestätigtem RF-06B als abgeschlossene Planposition. Korrekturen sind eigene
`RF-xx-FIXn` mit belegtem Fehler und erhöhen diesen Zähler nicht. Ein reines
Diagnosebundle darf null Commits enthalten. Korrekturen sind zahlenmäßig nicht
begrenzt; Sicherheitsgrenzen und belastbare Resultbindung bleiben Stop-Bedingungen.
RF-13 ist erst mit den Abschlussnachweisen aus Abschnitt 6 vollständig abgenommen.

### RF-00 – Planungsbootstrap

- **Voraussetzung:** oben vollständig geprüfte frische Referenz und autorisierter Auftrag.
- **Dateien:** dieser Plan, aktiver Verweis in `README.md`, projektbezogene aktive
  Planauswahl in `CHAT_INSTRUCTIONS.md`; kein ausführbarer Code in diesem Schritt.
- **Ergebnis:** Ziel 1.5.0, klare Reihenfolge, Kompatibilitätsbasis und begrenzte
  Spezifikationspflege sind auffindbar. Alte Tagging-/Fortsetzungsaufträge werden
  nicht auf diesen Plan übertragen; historische Abnahmen bleiben ehrlich offen.
- **Gate:** Dokumentinhalt fachlich prüfen, Links und enger Diff prüfen,
  vollständige parallele Suite in Development und Apply. Genau ein Commit und ein
  normaler abschließender Push durch den Entrypoint, keine CI-Auslösung.

### RF-01 – Widersprüchliche Vertragsanforderungen korrigieren

- **Voraussetzung:** RF-00 bestätigt. **Dateien:** die bestehenden drei Normdateien,
  `SPECIFICATION_CHANGELOG.md`, nötige korrespondierende Hinweise im Chat-/Runtime-Vertrag.
- Die früheren Pflichten für Result 1/2, alte Runtime-Wheels und eingefrorene
  1.3.0-Laufzeiten durch die explizite Basis ab 1.4.0 ersetzen; Produkt- und
  Formatversionen getrennt beschreiben. Runtime-Ausfall bleibt ein gültiger Diagnosefall.
- Die Capability-Varianten und Zukunftsregel aus Abschnitt 2 festhalten. Die sieben
  Patchfelder, aktuelle Resultfelder, Fehlercodes und öffentliche API bleiben gleich.
- Aktuelle Supportaussagen und historische Tatsachen trennen. Keine Spezifikations-
  Konsolidierung und keine Änderung der Interpreter-Untergrenze.
- **Abnahme:** alle betroffenen Muss-Regeln widerspruchsfrei zugeordnet; kein
  Produktpfad schon entfernt. Bestehende Texttests dürfen durch Verhaltenstests
  ersetzt werden, soweit sie genau die autorisierte Vertragskorrektur blockieren.

### RF-02 – Unveränderliche 1.4.0-Basis und Kompatibilitätstests sichern

- **Voraussetzung:** RF-01. **Dateien:** neue versionierte Fixtures unter
  `tests/fixtures/compatibility_140/`, Provenienz und gemeinsame Result-/Patch-Testhilfen.
- Repräsentative Originalartefakte mit dem unveränderten, vertrauenswürdig gebundenen
  1.4.0-Produzenten erzeugen bzw. übernehmen. Commit, Produzent, Format, Größe,
  vollständige SHA-256 und fachliche Herkunft festhalten; keine nachträglich umetikettierten Fixtures.
- Eingebettete PYZ und `unavailable`, Clean-/Dirty-Snapshot, staged/unstaged/untracked,
  tatsächlicher Erfolg/Fehler mit Teilfortschritt, Dry-Run und Diagnose abdecken.
  Kleine öffentliche Testrepositories statt persönlicher vollständiger Repository-Dumps verwenden.
- Patchformat 1, alle vier Bindungswerte, Datei-/Modusverhalten sowie 0/1/mehrere
  Entrypoint-Commits anhand der vorhandenen Durchstiche erhalten. Baseline-PYZ nur
  aus geprüfter Herkunft und isoliert ausführen; Importfreiheit statischer Leser belegen.
- **Abnahme:** zukünftiger Leser/Pack/Validate und Exchange-Entscheidungen werden
  gegen unveränderte 1.4.0-Daten geprüft; aktuelle Produzenten werden ebenfalls
  durch Ende-zu-Ende-Tests geprüft. Nicht unterstützte/future Daten liefern keine Erfolgsbeweise.

**Bestätigt durch Bundle 058:** Acht echte Result-3- und fünf Patch-1-Archive
mit vollständig gepinnter Provenienz. Originale Core-PYZ 1.4.0 aus dem geprüften
Result 057; alle 102 enthaltenen Core-Module gegen den Release-Tag-Commit
`282db1ef5c0af8e2a3ecf41f431f80006487dde4` verglichen. Das unveränderte
`source_commit: null` im Artefakt bleibt ehrlich erhalten. `unavailable` stammt
aus einem echten, unvorbereiteten Original-Quellbaum desselben Commits.

Neue gemeinsame Testhilfe und Verhaltenstests prüfen unveränderte Referenzen,
statische APIs ohne Prozess-/Netzzugriff, alle vier Bindungswerte, Modi,
0/1/2 Commits, Fehler-Teilfortschritte, unbekannte/manipulierte Daten und
konservative Exchange-Entscheidungen. Die Original-PYZ läuft ausschließlich
gepinnt in frischen isolierten Prozessen. Bestehende Produzenten-/Ende-zu-Ende-
Tests bleiben erhalten. Der einmalige Capture-Code und seine Grenzen sind
[bei den Fixtures](../../tests/fixtures/compatibility_140/README.md) dokumentiert.
Kein Produktcode oder Artefaktformat wurde in RF-02 geändert; Apply bestätigt (siehe Abschnitt 4).

### RF-03 – Gemeinsame Testdaten aus Testmodulen herauslösen

- **Voraussetzung:** RF-02. **Dateien:** `tests/test_*.py`, vorhandene Supportmodule
  und kleine fachliche Ergänzungen unter `tests/`; Produktcode bleibt unverändert.
- Die im Ausgangsstand gefundenen 88 direkten Importstellen aus `tests.test_*`
  einzeln zuordnen. Gemeinsame Builder, Fixtures und Prozesshilfen in fachliche
  Supportmodule verschieben; keine zweite Testsuite und kein universelles Hilfsframework.
- Session-Ressourcen, Worker-Isolation, `tmp_path`, Environment-/CWD- und
  Handle-Cleanup unverändert respektieren. Testmodule besitzen ihre eigenen Testfälle.
- **Abnahme:** keine Test-zu-Test-Importabhängigkeit mehr für wiederverwendete
  Hilfen. Unveränderte Fallauswahl und Verhaltensergebnisse nachweisen; Änderungen
  an Node-IDs nur mit vollständiger Zuordnung, nicht als stiller Testverlust.

**Bestätigt durch Bundle 059:** 88 direkte Hilfsimporte und ein Modulalias
werden vollständig auf fachliche Supportmodule umgestellt. 66 Definitionen
ziehen in 14 neue und zwei bestehende Module; Testnamen, Parameter, Marker und
Fixture-Scopes bleiben erhalten. Die gemeinsame Windows-ACL-Prüflogik erhält
einen expliziten Core-/Bootstrap-Adapter, beide bisherigen Testfälle bleiben.
Alle übrigen Testfunktionskörper bleiben strukturell gleich, abgesehen von den
Importzielen. Die [vollständige Zuordnung](rf03-test-support.md) hält jede
ursprüngliche Importstelle und ihre neue Zuständigkeit fest. Keine neuen
Test-zu-Test-Abhängigkeiten oder Importzyklen, keine Änderung an Produktcode,
CI oder eingefrorenen Fixtures. Apply-/Commit-Nachweis siehe Abschnitt 4.

### RF-04 – Verhalten und Architekturgrenzen statt Quelltextlayout prüfen

- **Voraussetzung:** RF-03. **Dateien:** besonders `test_chat_contract.py`,
  `test_release_audit.py`, `test_architecture.py` und die entsprechenden Verhaltenstests.
- Tests auf historische Planprosa, Überschriften, README-Wortlaut und exakte
  Quellcodezeichenketten entfernen. Funktionale Checks auf installierte Ressourcen,
  ausführbare Beispiele, Paketdaten, API-/JSON-Verträge und Grenzen bleiben erhalten.
- Die Forderung nach einem einzigen konkreten `application.py`-Orchestrator durch
  nachvollziehbare erlaubte Schichtabhängigkeiten ersetzen. Azyklische Importe,
  importfreie Prüfpfade, Core/Watcher-Trennung und fehlende Runtime-Fremdabhängigkeiten weiter prüfen.
- Für jeden entfernten nicht rein redaktionellen Check seinen Verhaltensersatz
  oder die ausdrücklich weggefallene Anforderung dokumentieren. Kein allgemeines
  Skip/Xfail, kein bloßes Löschen roter Sicherheitsprüfungen.
- **Abnahme:** gleiches Verhalten kann intern umorganisiert werden, tatsächliche
  Grenzverletzungen werden weiter erkannt; keine neuen Layout-/Prosa-Tests.

**Bestätigt durch Bundle 060:** Prosa- und Quelltextformprüfungen in Chat-/Release-
Tests entfallen zugunsten vorhandener Verhaltenstests und eines tatsächlich
validierten Manifest-Beispiels. Der AST-Importgraph erkennt Aliase und relative
Importe und erlaubt eine aufgeteilte Application-/CLI-Schicht ohne Rückabhängigkeiten.
22 adversarielle Architekturfälle sichern erlaubte und verbotene Abhängigkeiten.
Die [vollständige Check- und Collection-Zuordnung](rf04-test-mapping.md) erklärt
jede Entfernung; Produktcode, Normverträge, CI und Originalfixtures bleiben gleich.
Apply und vollständiges paralleles Gate bestätigt; Nachweis in Abschnitt 4.

### RF-05 – Gemeinsame Runtime-Primitiven von Wheel-Code trennen

- **Voraussetzung:** RF-04. **Dateien:** `runtime_wheel.py`, `result_runtime.py`,
  `runtime_pyz.py`, `result_pyz.py`, `runtime_sources.py`, `result_resources.py`,
  `build_backend.py` sowie betroffene Tests.
- Gemeinsam benötigte Rezeptdaten, Descriptor-Prüfungen, kanonische JSON-/Hash-
  Regeln, Ressourcenpfade und Fehlertypen an klar benannte fachliche Stellen verschieben.
  PYZ darf dafür nicht mehr private Details eines alten Wheel-Lesers importieren.
- Build-only Wheel-RECORD-/Transportaufgaben vom Runtime-Profil abgrenzen. Der
  PEP-517-Build bleibt an den eigenen Quellbaum gebunden und importiert keine fremde Installation.
- **Abnahme:** zunächst weiterhin gleiches Lese-/Buildverhalten; Golden-Daten,
  Inhalts-/Produzenten-IDs und unabhängige Installer-Routen unverändert. Azyklische
  Importe und stdlib-only PYZ bleiben nachgewiesen. Noch kein Legacy-Code vorschnell löschen.

**Bestätigt durch Bundle 061:** `runtime_profile.py` besitzt gemeinsame Rezept-
Daten, kanonische JSON-/Hashregeln, Fehler und Ressourcenpfade.
`result_runtime_metadata.py` besitzt die gemeinsamen Result-Deskriptoren;
`wheel_record.py` hält ausschließlich die Wheel-RECORD-Kodierung.
PYZ-Datenpfade und der aktuelle Buildpfad laden keine alten Wheel-Reader mehr.
Der PEP-517-Builder lädt Datenhelfer aus seinem eigenen Quellbaum in einem
kurzlebigen privaten Paketnamensraum. Bestehende Profile, Limits, Fehler,
Identitätsalgorithmen und Legacy-Lesepfade bleiben in diesem Schritt erhalten.
Die [Zuordnung und Testauswahl](rf05-runtime-primitives.md) dokumentiert die
Verlagerung, Originalbyte-Prüfung und verbleibende RF-06-Arbeit.
Development prüft gemäß Nutzerentscheidung vom 29. Oktober eine gezielte
parallele Auswahl; Apply prüft vor dem Commit die vollständige parallele Suite.
Apply-/Commit-Nachweis bestätigt; siehe Abschnitt 4.

### RF-06 – Überholte Unterstützung und ihre ausschließlichen Tests entfernen

- **Voraussetzung:** RF-05 und grüne RF-02-Baseline. **Dateien:** Result-Leser,
  Runtime-Provider, Buildbackend, `patch_pack.py`, alte Bootstrap-Hilfen und Legacy-Fixtures/Tests.
- Result-1-/Result-2-Unterstützung, Runtime-Wheel-Provider und ausschließlich
  historische Build-Rezepte abbauen. `_prepare_transport`/`_prepare_recipe` werden
  entfernt, sobald keine aktuelle Produktionsfunktion sie mehr benötigt.
- `RuntimeProvider`-Fallback im Pack-Templatepfad durch die eindeutigen heutigen
  PYZ-/Source-Wege ersetzen. Source-/Editable-Diagnose und sicherer Fallback bei
  fehlender nutzbarer PYZ bleiben erhalten; beschädigte Ressourcen dürfen keine fremde Installation wählen.
- Originale 1.4.0-Metadaten `[1, 2, 3]` weiter validieren. Den Leser zuerst für
  die genau definierte aktuelle Capability `[3]` vervollständigen, danach den
  Writer umstellen. Keine unbegrenzte Capability-Liste und keine Formatumdeutung.
- Alte positive Kompatibilitätstests entfallen erst mit der Supportpflicht;
  ihre weiterhin relevanten Angriffsszenarien auf aktuelle Formate übertragen.
  Die installierbaren Wheel-/sdist-/Watcher-Wege bleiben vollständig geprüft.
- **Abnahme:** neues Result → eigene PYZ → Pack/Validate → tatsächlicher Apply →
  nächstes Result; zusätzlich unveränderte 1.4.0-Eingaben, Fehler und Runtime-Ausfälle.
  Altformate in gemischtem Exchange werden nicht als Erfolg oder Archivierungsfreigabe gewertet.

#### RF-06A – Geschlossene Capability-Profile zuerst lesen

- **Voraussetzung:** RF-05 tatsächlich bestätigt; unveränderte RF-02-Fixtures.
- **Commit:** `refactor(compat): prepare closed capability readers [RF-06A]`.
- Core-Reader, Bootstrap-Skript und dessen ausführbare Kopie im Handoff akzeptieren
  genau `[1, 2, 3]` und `[3]`. Patchformate bleiben genau `[1]`; boolesche Werte,
  andere Typen, Teilmengen, Duplikate und unbekannte Versionen bleiben ungültig.
- Writer und bisherige Lese-/Buildpfade bleiben in diesem Zwischenschritt bestehen;
  der aktuelle Produzent deklariert daher weiterhin wahrheitsgemäß `[1, 2, 3]`.
- **Abnahme:** statischer Reader/Pack/Validate für beide Profile ohne Codeausführung;
  Bootstrap bleibt Vorprüfung, die native Referenzprüfung weiterhin verpflichtend.
  Eigene gebaute PYZ und eingebetteter Bootstrap müssen beide Profile in frischen
  isolierten Prozessen verarbeiten und beschädigte Snapshots weiter ablehnen.
- **Bestätigt durch Bundle 062:** [Änderungs- und Testzuordnung](rf06-capability-reader.md).
  Ein Commit tatsächlich angewendet und gepusht; Nachweis in Abschnitt 4.
  Diese Vorbereitung allein schließt RF-06 nicht ab.

#### RF-06B – Writer umstellen und überholte Pfade abbauen

- **Voraussetzung:** RF-06A durch tatsächlichen Apply und vollständiges paralleles
  Gate bestätigt; dessen neues Result ist die Bindungsbasis.
- **Commit:** `refactor(compat): remove pre-1.4 result and runtime paths [RF-06B]`.
- Die oben genannten Legacy-Reader/-Provider/-Buildrezepte abbauen und aktuelle
  Writer auf `[3]` umstellen. Originale 1.4.0-Results bleiben bytegleich lesbar.
- Vor dem Entfernen alter Tests weiterhin relevante Angriffe auf aktuelle Formate
  übertragen und jeden entfallenden Fall zuordnen. Installations-Wheels, sdist,
  Watcher, Runtime-unavailable und technischer Fallback bleiben unterstützt.
- **Abnahme:** sämtliche RF-06-Nachweise oben einschließlich tatsächlicher Übergabe,
  Folge-Result und konservativer Behandlung alter Results im gemischten Exchange.

**Bestätigt durch Bundle 063:** Der native Reader unterstützt ausschließlich
Result 3; Original-1.4.0-Capabilities `[1, 2, 3]` bleiben gültig. Der aktuelle
Writer deklariert `[3]`. Result-Wheel-Reader, Provider, alter Installations-
Bootstrap, Wheel-Rezeptgenerator und deren ausschließliche Fixtures entfallen.
Der nur noch beim Build benötigte RECORD-Serializer liegt im Buildbackend.
Der Pack-Templatepfad verwendet den eigenen PYZ-Provider oder den begrenzten
Source-Pfad. Normales Installations-Wheel, sdist, pipx, uv und Watcher bleiben.
Die [Abbau- und Testzuordnung](rf06-legacy-removal.md) ordnet jeden entfernten
Test zu; relevante Grenzen sind auf aktuelle Formate übertragen. Development
prüfte nur die dokumentierte parallele Auswahl. Vollständiges Apply-Gate,
Commit und Push sind durch das Result in Abschnitt 4 bestätigt.

### RF-07 – Einen gepflegten ausführbaren Bootstrap bereitstellen

- **Voraussetzung:** RF-06. **Dateien:** `scripts/pyz_bootstrap.py`,
  `CHAT_INSTRUCTIONS.md`, enges Generierungs-/Prüfwerkzeug und Build-/Bootstrap-Tests.
- Das geprüfte Python-Skript wird die einzige manuell gepflegte Programmquelle.
  Sein markierter Codeblock in der Chat-Anleitung wird deterministisch erzeugt.
  Die außerhalb dieses Blocks gepflegte Dokumentation bleibt unabhängig editierbar.
- Der veröffentlichte Chat-Vertrag bleibt vollständig und offline verwendbar;
  Source-Checkout, Wheel, sdist und PYZ liefern die passende eigene Anleitung.
  Ein Build-Check erkennt veraltete erzeugte Bytes, ohne den Quellbaum still zu reparieren.
- Keine Laufzeit-Installation, kein Netzwerk und keine Core-Abhängigkeit vor der
  Vertrauensprüfung. Separate Vorprüfung und vollständige native Result-Prüfung bleiben getrennt.
- **Abnahme:** identische erzeugte Programmbytes, reproduzierbare Ressourcen,
  eigener Bootstrap im frischen stdlib-Prozess; Beschädigung, Shadowing,
  Rechte-/Handle-Fehler und technische Nichtverfügbarkeit bleiben korrekt behandelt.

**Bestätigt durch Bundle 064:** Das unveränderte Skript ist die einzige gepflegte
Programmquelle. `scripts/render_chat_bootstrap.py` erzeugt ausschließlich den
markierten ausführbaren Block und bietet einen rein lesenden Check. Wheel-,
sdist- und Editable-Builds verweigern fehlende, mehrdeutige oder veraltete
Generierung, ohne den Quellbaum automatisch zu reparieren. Der sdist enthält
gezielt die zwei benötigten Buildskripte; Wheel/PYZ enthalten keine zusätzlichen
Buildwerkzeuge. [Arbeitsweise und Nachweiszuordnung](rf07-bootstrap-source.md).
Development prüfte die dort dokumentierte parallele Auswahl; vollständiges
Apply-Gate, Commit und Push sind durch das Result in Abschnitt 4 bestätigt.

### RF-08 – Konfiguration und Exchange-Ermittlung fachlich isolieren

- **Voraussetzung:** RF-07. **Dateien:** `application.py` und klar begrenzte
  Application-Module für Konfiguration, registrierte Ziele und Exchange-Ermittlung.
- Bestehende Orchestrierung verschieben und gemeinsame Konfigurationsabläufe
  nutzen. `api.py` bleibt stabile öffentliche Grenze; keine zweite Fachimplementierung im Watcher.
- Reihenfolge und Lebensdauer von Registry-/Repository-Locks, erneute
  Identitäts-/Konfigurationsprüfungen und die Auswahl genau eines Kandidaten erhalten.
- **Abnahme:** Konfiguration aus Unterverzeichnissen, geteilter Exchange,
  Registry-/Konfigurationsfehler, mehrdeutige Kandidaten und Locks liefern gleiches
  Verhalten. Watcher-Targets und automatische Auswahl bleiben unverändert gebunden.

**Vorbereitet in Bundle 065:** `application_configuration.py` übernimmt
Registrierungs-/Konfigurationsabläufe einschließlich des gemeinsamen geschützten
Schreibablaufs. `application_exchange.py` besitzt Zielermittlung, Scope,
Kandidatenauswahl, erneute Validierung, Wartung und Attempt-Receipts.
`application.py` bleibt die Fassade für die unveränderte öffentliche API;
Apply-/Result- und Script-Orchestrierung bleiben bis RF-09 dort.
Alle bisherigen Funktions-/Klassenkörper bleiben unverändert; Fehlersimulationen
folgen ihren neuen Lookup-Orten. Kein bestehender Testfall entfällt.
[Modulgrenzen und Nachweiszuordnung](rf08-application-discovery.md).
Development führt nur die dokumentierte parallele Auswahl aus. Vollständiges
Apply-Gate, Commit und Push von RF-08 sind noch offen.

### RF-09 – Apply- und Result-Orchestrierung übersichtlich trennen

- **Voraussetzung:** RF-08. **Dateien:** verbleibende `application.py`-Abläufe,
  fachliche Apply-/Bundle-Orchestrierung und vorhandene Result-/Run-Modelle.
- Preflight, Mutation, Entrypoint, Ergebnisaufnahme und Veröffentlichung behalten
  erkennbare Zustandsübergänge. Wiederholte gleichartige Abschlusslogik gemeinsam
  ausdrücken, ohne Fehler- und Teilerfolgspfade gleichzusetzen.
- Bestehende Domain-Fehler und Statusadapter verwenden; keine neue Hierarchie,
  kein Plugin-System und kein allgemeines Workflow-Framework.
- **Abnahme:** erfolgreiche/fehlgeschlagene/unterbrochene Applies, null/mehrere
  Commits, Dry-Run, Result-Veröffentlichungsfehler, Recovery und Wiederanlauf
  liefern weiterhin die richtigen Exitcodes, Logs und Nachweise. CIFS-Prüfreihenfolge erhalten.

### RF-10 – CLI-Parser und wiederholte Befehlsrahmen bereinigen

- **Voraussetzung:** RF-09. **Dateien:** `cli.py`, fachliche Parser-/Handler-Module
  und API-/CLI-Verhaltenstests; öffentliche Befehle und Optionen bleiben bestehen.
- Parser nach Befehlsgruppen strukturieren; Ausgabe-/Observer-/Fehlerrahmen für
  gleichartige Konfigurations- und Inspektionsbefehle teilen. Wiederholte Parameter-
  Weitergabe vereinfachen, ohne einen neuen Command-Framework-Layer einzuführen.
- Shellfreie API-Pfadbehandlung, strikte Argumentprüfung, JSON-Ausgabeversionen,
  stdout/stderr-Zuordnung, UTF-8 und Exitcode-Abbildung erhalten.
- **Abnahme:** CLI und API für dieselben Eingaben verhalten sich fachlich gleich;
  ungültige Kombinationen bleiben abgelehnt. Installierte Entrypoints und PYZ
  funktionieren außerhalb des Checkouts unter den unterstützten Interpretern.

### RF-11 – CI-Matrix und fachliche Nachweise zentral pflegen

- **Voraussetzung:** RF-10. **Dateien:** manuelle Workflow-YAML, `tools/test_policy.py`,
  Evidence-/Reviewwerkzeuge, `scripts/run_handoff_ci.py` und ihre Verhaltenstests.
- Einen kleinen gemeinsamen maschinenlesbaren Prüfkatalog für Plattform-/Python-
  Kombinationen, Artefaktrollen und stabile fachliche Nachweiskennungen einführen.
  Workflow und lesender Auswerter verwenden denselben Katalog bzw. nachweisbar
  deterministisch daraus erzeugte Definitionen; keine neue Laufzeitabhängigkeit im Produkt.
- Nachweise von Funktions-/Datei-/Anzeigenamen entkoppeln. Erforderliche
  parametrische Varianten explizit erhalten; eine Kennung auf einem beliebigen
  einzelnen Test darf keine fehlenden übrigen Nachweise verdecken.
- Aktuelle zwölf native/Docker-Jobs samt PowerShell-Varianten und vollen parallelen
  Suites erhalten. Keine Abdeckungskürzung allein zur Laufzeit- oder Tokenersparnis.
  Änderungen an internen Reportschemas sind versioniert, historische Nachweise bleiben einordenbar.
- **Abnahme:** fehlende/doppelte/übersprungene Pflichtnachweise und falscher Commit,
  Interpreter oder Plattform bleiben Fehler. CI nur `workflow_dispatch`; ausschließlich
  Christian startet sie. Auswerter und Entrypoints können sie weder auslösen noch wiederholen.

### RF-12 – Aktuelle Hinweise angleichen und Bereinigung belegen

- **Voraussetzung:** RF-11. **Dateien:** README, betroffene Runtime-/Installations-/
  Testdokumentation, Chat-Anleitung, Changelog und Fortschritt dieses Plans.
- Veraltete aktuelle Supportversprechen und nicht mehr verwendbare Anleitungen
  entfernen oder als historische Informationen kennzeichnen. Installations-Wheel,
  Runtime-PYZ, fehlende Runtime und die 1.4.0-Basis verständlich auseinanderhalten.
- In den drei Normdateien nur verbliebene konkrete Fehler/Widersprüche korrigieren;
  keine Zusammenführung, neue Spezifikationsstruktur oder allgemeine Textpolitur.
- Gegen den Basisstand nachprüfbar erfassen: entfernte Produktionspfade/Dateien,
  Größen der großen Module, Test-zu-Test-Importe, Anzahl gepflegter Bootstrapquellen
  und Zuordnung entfallener Tests. Generierte Dateien getrennt von gepflegten Quellen zählen.
- **Abnahme:** weniger tatsächlich gepflegter Altcode, keine bloße Verlagerung in
  Tests oder generische Helfer. Keine versprochene Prozent-/Laufzeitersparnis ohne Messung;
  alte CI-/Apply-Nachweise bleiben unverändert zugänglich.

### RF-13 – Version 1.5.0 und Abschlussabnahme vorbereiten

- **Voraussetzung:** RF-12; alle vorherigen Schritte tatsächlich angewendet und
  ihre vollständigen parallelen Gates bestätigt. **Dateien:** zentrale Version,
  notwendige Releasehinweise und bestehende Versions-/Packaging-Verträge.
- Produktversion konsistent auf 1.5.0 setzen; den Stand wieder vollständig
  im Apply parallel prüfen. Wheel, sdist und Core-PYZ mit übereinstimmenden Versionen,
  IDs, Inventaren und Mindest-Python-Angaben bauen und prüfen.
- Der Watcher führt den realen Versionscommit aus und pusht genau einmal normal.
  Tag, GitHub Release, Upload auf einen Paketindex, Installation und Dienstneustart
  bleiben gesonderte Nutzerentscheidungen; dieser Plan autorisiert sie nicht automatisch.
- **Abnahme:** Abschnitt 6 auf genau dem finalen Versionsstand erfüllen. Eine
  ältere grüne CI oder ein erfolgreicher Build ist kein Ersatz. Bei fehlenden
  externen Nachweisen bleibt der Plan offen, ohne weitere spekulative Patches.

## 4. Verbindliche Test- und Übergaberegeln

**Aktuelle Nutzerentscheidung vom 29. Oktober 2026:** Development führt nur
ausgewählte, änderungsbezogene Tests parallel aus, keine vollständige Suite.
Auswahl und Ergebnisse müssen nachvollziehbar dokumentiert und dürfen nicht
als Volltest-Nachweis bezeichnet werden. Diese Entscheidung ersetzt ältere
Development-Volltestpflichten, auch in bereits bestätigten Planabschnitten.

Apply führt für **jeden** tatsächlichen Commitstand die vollständige parallele
Testsuite aus, auch am Bundle-Ende:

```text
python tools/run_tests.py --suite all --report <lokaler-ergebnisnachweis.json>
```

Eine explizite positive Workerzahl ist erlaubt. Keine seriellen Gates, keine
verkürzte Auswahl als Ersatz für das Apply-Gate. Zusätzliche Verhaltenstests
werden in die passende Development-Auswahl und die vollständige Apply-Suite aufgenommen. Tests auf Prosa, Farben, ANSI, Spinner,
Tabellenlayout und Konsolenwortlaut werden nicht neu eingeführt.

Exitcode, vollständige Worker-Collection, Worker-Enden, Pflichtfälle, Fehler,
Skips und Bindung an tatsächliche Quelldateien auswerten. Bloßer Prozessstart,
Dry-Run, Reportdatei oder ausschließlich grüne Konsolenausgabe genügen nicht.
Bei Entfernung alter Tests wird die Anforderungszuordnung dokumentiert.
Niedrigere Testzahlen sind allein weder Erfolg noch Fehler.

Tests laufen als eigene Prozesse mit Log und Ergebnisnachweis. Planmäßige
Modellkontrollen frühestens nach 300 Sekunden, danach im selben Mindestabstand;
ein zuverlässig gemeldetes Ende darf sofort ausgewertet werden. Die Wartezeit
übernimmt ein gewöhnlicher Prozess. Keine erneuten Starts durch Zwischenkontrollen.

Die vollständige Apply-Suite ersetzt keine native Windows-/Interpreter-/CIFS-Abnahme.
CI bleibt ausschließlich manuell (`workflow_dispatch`), gestartet von Christian.
Codex/Entrypoints werten verfügbare CI aus, starten aber keinen Lauf und keinen
Fünfertakt. Ein fehlender CI-Lauf auf einem Zwischencommit blockiert allein
kein weiteres autorisiertes lokales Refactoring.

Jedes Paket enthält die vollständige aus seinem Result übernommene Repository-ID,
Base-SHA, Fingerprint und Algorithmus. Pack nutzt die öffentliche API bzw. die
verifizierte nutzbare Result-PYZ; finale ZIP öffnen, Paketstruktur, Payloads,
Modi, Hashes, Bindung, Größe und vollständige SHA-256 prüfen. Erst danach atomar
in Exchange veröffentlichen. Genau eine kanonische ZIP; ein Result gilt erst
nach erfolgreicher Folgebundle-Auslieferung als verbraucht.

Der Entrypoint prüft Zielbranch, erwartete Dateizustände und Commitumfang,
führt die lokalen Gates aus und erzeugt tatsächliche Commits ausschließlich im
Apply-Repository. Nach allen erfolgreichen Commits genau ein normaler Push.
Bei Fehlern keine Erfolgsmeldung und keinen nachgelagerten Push; bereits
erreichte Teilfortschritte werden im tatsächlichen Result ausgewertet.

### Bestätigter Fortschritt: RF-00 / Bundle 056

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `05cceef59891a68a3e0fdd2115fa79e718db1347`, normaler Push auf `dev`,
  sauberer Snapshot mit 355 Dateien; genau die drei geplanten Dokumentänderungen.
- Result `patchharbor-apply_Result_111022_1029_d93260.zip`, SHA-256
  `126547f6af58edf66323ac1b98711c32c882978f7a08cd3965833dbb590ffd23`.
- Vollständiges paralleles Apply-Gate: 3299 passed, 15 skipped, 12 Worker.
- Keine CI ausgelöst. RF-01 verwendet dieses Result als neue Bindungsbasis;
  der eigene künftige Apply-/Commit-Erfolg wird hier nicht vorweggenommen.

### Bestätigter Fortschritt: RF-01 / Bundle 057

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `37e2c88c5afd41be2abb83a394b22748a5256ef9`, normaler Push auf `dev`;
  sauberer Snapshot mit 355 Dateien und den geplanten 16 Änderungen.
- Result `patchharbor-apply_Result_121920_1029_43a1e8.zip`, SHA-256
  `09301a80390bd41410d37a6485d5377071af1d5e96b7946f0b05b7c108d91de1`.
- Vollständiges paralleles Apply-Gate: 3299 passed, 15 skipped, 12 Worker.
- Report-SHA-256: `90290174a372825cb77bb6425ad7bfb4551df4751a513412910c358f3f703c2a`.
- Keine CI ausgelöst. RF-02 bindet sich an dieses Result; sein eigener
  zukünftiger Apply-/Commit-Erfolg wird nicht vorweggenommen.

### Bestätigter Fortschritt: RF-02 / Bundle 058

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `f959ea054c37977650be43db690909c2d510f29d`, normaler Push auf `dev`;
  sauberer Snapshot mit 373 Dateien und genau den 21 geplanten Änderungen.
- Result `patchharbor-apply_Result_132604_1029_b044e1.zip`, SHA-256
  `056327a1edd6f7ba4ffccfe0edec56f51be10ede9b59c8dfa71a27142e7323e6`.
- Vollständiges paralleles Apply-Gate: 3342 passed, 15 skipped, 12 Worker;
  alle 43 neuen Kompatibilitätsfälle bestanden.
- Report-SHA-256: `e7c505fb6a4eeb7857ced5d0e9dfa974821b11b30067ad48c5989770fa2080fd`.
- Keine CI ausgelöst. RF-03 verwendet dieses Result als neue Bindungsbasis.

### Bestätigter Fortschritt: RF-03 / Bundle 059

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `ab1d6d5dae0d6f013c91775e9308dfe86ef6d848`, normaler Push auf `dev`;
  sauberer Snapshot mit 388 Dateien und genau den 78 geplanten Änderungen.
- Result `patchharbor-apply_Result_173904_1029_2cadb0.zip`, SHA-256
  `10fae621c678ad78ac0dca9b28977c2bfcf872fe7eea719ef90a9a12bd28db6d`.
- Vollständiges paralleles Apply-Gate: 3342 passed, 15 skipped, 12 Worker;
  unveränderte Collection gegenüber RF-02.
- Report-SHA-256: `2b9363578408ba6b3d75375df059f31aaa7b4190c1de28fb780fc6b5dacb1d11`.
- Keine CI ausgelöst. RF-04 bindet sich an dieses Result; sein eigener
  zukünftiger Apply-/Commit-Erfolg wird nicht vorweggenommen.

### Bestätigter Fortschritt: RF-04 / Bundle 060

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `afce2628e9c1d85baa7726ec29a308de3d4d5ad2`, normaler Push auf `dev`;
  sauberer Snapshot mit 391 Dateien und genau den 11 geplanten Änderungen.
- Result `patchharbor-apply_Result_183436_1029_f5cbe0.zip`, SHA-256
  `80c24575edb99eed9bbef3173332fdbc87455c4b50a58207cf1804b9e0326c47`.
- Vollständiges paralleles Apply-Gate: 3343 passed, 15 skipped, 12 Worker.
- Report-SHA-256: `00b41ce7dbef2e97114e953ce0e9686d84b3edba50ff080507f830fd5e68f7e3`.
- Keine CI ausgelöst. RF-05 verwendet dieses Result als neue Bindungsbasis.

### Bestätigter Fortschritt: RF-05 / Bundle 061

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `5ee194153d1338777cb6b77a60b7854e7b009388`, normaler Push auf `dev`;
  sauberer Snapshot mit 396 Dateien und genau den 19 geplanten Änderungen.
- Result `patchharbor-apply_Result_190808_1029_5527f4.zip`, SHA-256
  `3c287fbaede17019a5a1e51d00ad066bda23371843aa076374a421d8453802b3`.
- Vollständiges paralleles Apply-Gate: 3351 passed, 15 skipped, 12 Worker.
- Report-SHA-256: `bda4980d16f801a4493631a059eacc4940a2c7ef4df2d3a431fecc8dfe0d097b`.
- Development hatte nur seine ausgewählte parallele Prüfung ausgeführt.
  Keine CI ausgelöst. RF-06A verwendet dieses Result als neue Bindungsbasis.

### Bestätigter Teilschritt: RF-06A / Bundle 062

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `220c0af2189cebe29ae2c991c4a6afb65dc3cc1f`, normaler Push auf `dev`;
  sauberer Snapshot mit 398 Dateien und genau den acht geplanten Änderungen.
- Result `patchharbor-apply_Result_203434_1029_8a726e.zip`, SHA-256
  `88a35eba58b85477e0768333e89b70ff16f775f63a1d176d4e1209884ca56700`.
- Vollständiges paralleles Apply-Gate: 3386 passed, 15 skipped, 12 Worker.
- Report-SHA-256: `2ece84af0a0360c5ae6984a7d382148e8136d1fbaadfb3fe04326a9fa4d166ed`.
- RF-06A ist bestätigt, die Planposition RF-06 bleibt bis RF-06B offen.
  Keine CI ausgelöst. RF-06B ist an dieses neue Result gebunden.

### Bestätigter Fortschritt: RF-06B / Bundle 063

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `3afcc56b00ccdc9818b2436ecde999b46176b1ea`, normaler Push auf `dev`;
  sauberer Snapshot mit 383 Dateien und genau den 56 geplanten Änderungen.
- Result `patchharbor-apply_Result_030914_1030_5ee031.zip`, SHA-256
  `80ad3c1a2830b888b18b3c3153c6381f029cc5093cdf69f4dcc0587b2be0f7e3`.
- Vollständiges paralleles Apply-Gate: 3171 passed, 15 skipped, 12 Worker.
- Report-SHA-256: `937f22f358781c8b8bdc5eb5c25407618035e47089a43835d9b6b224212e9602`.
- Collection-Änderungen entsprechen vollständig der geprüften Testzuordnung.
  RF-06A und RF-06B schließen zusammen die siebte Planposition ab.
  Development hatte nur ausgewählte parallele Tests ausgeführt. Keine CI gestartet.
  RF-07 band sich an dieses Result; sein eigener Apply ist unten bestätigt.

### Bestätigter Fortschritt: RF-07 / Bundle 064

- Tatsächlicher Apply, Entrypoint- und Prozess-Exitcode 0; kein Dry-Run.
- Commit `d4210e7a2ae85fc85b50aedddecd1ce24bb414d1`, normaler Push auf `dev`;
  sauberer Snapshot mit 386 Dateien und genau den zehn geplanten Änderungen.
- Result `patchharbor-apply_Result_061002_1030_8bfd9f.zip`, SHA-256
  `367aa89d86ca085ef8a63c2c99d1faf4cccb89b151752176c4b27b0c7556a8a8`.
- Vollständiges paralleles Apply-Gate: 3204 passed, 15 skipped, 12 Worker.
- Report-SHA-256: `99c6dac8838515c7f6c0e50882d921a7675185b2b61af4e66eb58902bf4547dc`.
- Die 33 zusätzlichen Testfälle und alle bisherigen Fälle sind nachgewiesen.
  Damit sind acht Planpositionen und neun Plancommits bestätigt.
  Development hatte nur ausgewählte parallele Tests ausgeführt. Keine CI gestartet.
  RF-08 bindet sich an dieses Result; sein eigener Apply-Erfolg steht noch aus.

## 5. Pflichtnachweise über die Schritte hinweg

| Bereich | Erforderlicher Nachweis | Hauptschritte |
| --- | --- | --- |
| 1.4.0-Basis | unveränderte Artefaktbytes/Provenienz, Reader/Pack/Validate, Erfolg/Fehler/Dirty/Dry-Run | RF-02, RF-06, RF-13 |
| Aktueller Produzent | eigenes Result, eigene Anleitung/PYZ, Pack, Apply, Folge-Result | RF-06, RF-07, RF-13 |
| Paket- und Dateisicherheit | vollständige Bindung, Pfade/Modi, Duplikate, Limits/ZIP64, unbekannte Daten | RF-02, RF-05, RF-06, RF-09 |
| Runtime-Ausfall | gültiges `unavailable`, technischer Fallback, keine falsche Validierungszusage | RF-02, RF-06, RF-07 |
| Windows/Python | reale 3.10/3.11/3.12-Handles, DACLs, Reparse/Junction, beide PowerShell-Wege | RF-07 bis RF-11, RF-13 |
| Installation/Portabilität | Wheel/sdist/source, pipx und bestehender uv-Nachweis, Core-PYZ ohne Installation/Watcher | RF-05 bis RF-07, RF-10, RF-13 |
| Apply/Recovery | Fehler-Teilfortschritte, Replay, Locks, Abbruch, 0/1/mehrere Commits | RF-08, RF-09 |
| Watcher | native Ereignisse, fünf Sekunden Ruhe, keine verlorenen Änderungen während Apply, kein doppelter Worker | RF-08, RF-09, RF-13 |
| Result-Publikation | No-follow/Ownership, atomare Publikation, CIFS-Retrybudget und Diagnosen | RF-06, RF-09, RF-13 |
| Nachweiswerkzeuge | vollständige parallele Berichte, stabile fachliche Kennungen, falsche/fehlende Belege abgelehnt | RF-03, RF-04, RF-11 |

Die Matrix beschreibt Verhalten, keine Pflicht zu mehrfach identischen teuren
Aufbauten. Gemeinsame vertrauenswürdige Fixtures dürfen innerhalb ihrer bisherigen
Isolation wiederverwendet werden. Eigenständige Angriffstests und unabhängige
Paketprüfungen werden nicht mit dem Code des getesteten Writers tautologisch ersetzt.

## 6. Fortschritt, Abschluss und Stop-Regeln

Ein Schritt wird erst mit tatsächlichem Apply, Commit-SHA, vollständigem
parallelen Gate und überprüftem Result als bestätigt geführt. Die Planfassung
in einem vorbereiteten Paket darf ihre eigene künftige Commit-SHA und ihren
eigenen Erfolg nicht vorwegnehmen. Der externe Result-Review ist dafür maßgeblich;
ein Folgecommit kann den zuvor bestätigten Stand nachtragen.

Für den vollständigen Abschluss von 1.5.0 werden gemeinsam benötigt:

1. Alle 14 Planpositionen tatsächlich angewendet; kein ungeklärter Teilfortschritt,
   sauberer Endstand und bestätigter abschließender Push.
2. Dokumentierte ausgewählte parallele Development-Nachweise, vollständige
   parallele Apply-Nachweise und unveränderte 1.4.0-Kompatibilitätsfixtures auf
   dem finalen Stand.
3. Von Christian gestartete manuelle native CI einschließlich Windows, der
   unterstützten Python-Versionen und Docker; passende Run-ID, vollständiger
   Commit, Jobs, Artefakthashes und fachliche Pflichtnachweise geprüft.
4. Repräsentativer echter CIFS-Praxisnachweis für die resultrelevanten Umbauten
   oder eindeutig zugeordneter bereits vorhandener Nachweis für unveränderte
   geprüfte Pfade; ältere Versionsnachweise nicht pauschal als neu ausgeben.
5. Nachprüfbare aktuelle Wheel-/sdist-/PYZ-Artefakte, dokumentierte Bereinigungen
   und konsistente aktuelle Anleitungen bei unveränderter Spec-Aufteilung.

Abschlussnachweise werden in einem lesenden Review dokumentiert. Falls nach der
finalen CI noch Dateien geändert werden müssen, ist der geänderte Endstand neu
zu prüfen; nicht die vorherige CI auf einen anderen Commit übertragen. Es braucht
keinen zusätzlichen Commit allein, um ein bereits belegtes Ende zu behaupten.
Bei fehlender externer Abnahme konkret berichten und keine CI eigenmächtig starten.

Beim bestätigten Abschluss endet der aktive Plan. Kein weiteres Bundle und kein
neuer Plan ohne Nutzerauftrag. Die bisherige S-Schleife, alte Releasefreigaben,
einzelne Tag-Aufträge und frühere offene Pläne werden nicht automatisch reaktiviert.
