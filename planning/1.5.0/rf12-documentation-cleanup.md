# RF-12: aktuelle Hinweise und nachprüfbare Bereinigung

Bundle 069 bereitet einen Dokumentationscommit vor. Basis ist der tatsächlich
angewendete und gepushte RF-11-Commit
`7294d77fde0598dd57a6fdc3c19f6925e5520bdb`; dessen vollständige parallele
Apply-Suite bestand mit 3281 Passed und 15 Skips. RF-12 selbst ist noch nicht
angewendet. Produktversion bleibt 1.4.0 bis RF-13; die Releaseabnahme ist offen.

## Aktuelle Hinweise und unveränderte Verträge

- README, API-, Result-, Runtime- und Installationshinweise beschreiben den
  bereits implementierten Stand: Result 3, unveränderte gültige 1.4.0-Artefakte,
  aktuelle Produzentencapabilities `[3]` und weiterhin lesbare originale `[1,2,3]`.
  Patchformat 1 ist weiterhin gültig; Produktversion und Formatnummer sind getrennt.
- Normale Distributions-Wheels und sdist installieren CLI und optionalen Watcher.
  Die Core-PYZ enthält keinen Watcher. Entfernte Runtime-Wheel-Reader/Provider
  und Installationskommandos werden nicht mehr als aktuelle Anleitung angeboten.
- Fehlende oder technisch unbrauchbare Runtime erlaubt weiterhin den dokumentierten
  bisherigen Übergabeweg für sonst unterstützte Referenzen. Ungültige Bindung,
  beschädigte Pflichtdaten und unbekannte Resultformate erhalten keine Freigabe.
- Die beiden bestehenden geschlossenen PYZ-Rezeptvarianten `>=3.10` und `>=3.12`
  bleiben Datenverträge des aktuellen Validators. Daraus folgt keine allgemeine
  Unterstützung alter Result-1/2-Produzenten. Es gibt keine Produktversionsheuristik.
- Hauptspec §33, PYZ/PACK TEST-05 und CPY-15/CT-16 werden an die bereits geltenden
  Nutzerentscheidungen angeglichen: ausgewählte parallele Development-Tests,
  volle parallele Apply-Suite vor jedem Commit, CI nur durch Christian manuell.
  Keine neue Normdatei, Zusammenführung oder Änderung der Sicherheits-/Paketverträge.
- Der ausführbare CHAT-Block bleibt bytegleich zur allein gepflegten Bootstrapquelle.
  Die drei Normdateien, historischen Pläne und tatsächlichen CI-/Apply-Nachweise
  behalten ihre eigenständigen Rollen. Frühere Ergebnisse werden nicht als heutige
  Releaseabnahme ausgegeben. RF-12 ändert keinen Produktcode, Test oder Workflow.

## Reproduzierbarer Vergleich

Verglichen werden die vollständigen Git-Bäume vor RF-00
(`caad28b84bdf9461c98cf8a218061e06ff894074`) und nach bestätigtem RF-11
(`7294d77fde0598dd57a6fdc3c19f6925e5520bdb`). Die Messung bezieht sich bewusst
auf bestätigte Commits, nicht auf einen erfundenen künftigen RF-12-Commit.
Der unveränderte Produktcode in RF-12 hat dieselben Maße.

In einem Repository mit beiden lokalen Git-Objekten:

```bash
python planning/1.5.0/measure_cleanup.py \
  --repository /absolute/path/to/repository \
  --before caad28b84bdf9461c98cf8a218061e06ff894074 \
  --after 7294d77fde0598dd57a6fdc3c19f6925e5520bdb > /tmp/cleanup-evidence.json
cmp planning/1.5.0/cleanup-evidence.json /tmp/cleanup-evidence.json
```

Das stdlib-Skript liest reguläre Git-Blobs mit `ls-tree`/`cat-file`. Es führt
keinen historischen Quellcode aus und verändert weder Index, Checkout noch
Git-Konfiguration. Fehlende Objekte sind ein Fehler, kein Anlass für einen Fetch.
Die [JSON-Daten](cleanup-evidence.json) enthalten vollständige Commits, pro
Produktmodul SHA-256, Bytes und physische Zeilen sowie alle statischen Importkanten.
Zeilen schließen Leerzeilen und Kommentare ein; sie messen keine Komplexität.
Gezählt werden die tatsächlich versionierten Bytes, keine installierten/build-
generierten Dateien. Testquellen schließen binäre und historische Fixturebäume aus.

| Messgröße | Vor RF-00 | Nach RF-11 |
| --- | ---: | ---: |
| Python-Produktquellen in `src/`, einschließlich Watcher: Dateien | 116 | 122 |
| Dieselben Quellen: physische Zeilen | 23.194 | 22.721 |
| Dieselben Quellen: Bytes | 886.435 | 859.297 |
| `application.py`: Zeilen | 1.497 | 269 |
| Gesamte Application-Familie: Zeilen / Dateien | 1.497 / 1 | 1.646 / 5 |
| `cli.py`: Zeilen | 1.513 | 150 |
| Gesamte Core-CLI-Familie: Zeilen / Dateien | 1.513 / 1 | 1.433 / 4 |
| Größtes Produktmodul: Zeilen | 1.513 (`cli.py`) | 1.024 (`run_report.py`) |
| Statische gerichtete Testmodul-zu-Testmodul-Importkanten | 82 | 0 |
| Testquellen ohne Fixtures: Zeilen / Dateien | 37.317 / 155 | 36.981 / 178 |
| Darin Hilfs-/Konfigurationsmodule ohne `test_*`: Zeilen / Dateien | 1.439 / 17 | 2.638 / 33 |
| Manuell gepflegte Bootstrap-Programmkopien | 2 | 1 |
| Generierte ausführbare Bootstrap-Kopien | 0 | 1 |

Netto entfallen 473 Produktzeilen bzw. 27.138 Bytes. Die Aufteilung der
Application ergänzt insgesamt 149 Zeilen; eine kleinere Fassadendatei ist keine
gleich große Codelöschung. Die CLI-Familie reduziert sich insgesamt um 80 Zeilen.
`run_report.py` blieb mit 1.024 Zeilen bytegleich und ist nun das größte Modul.
Diese Angaben versprechen keine Geschwindigkeit, Speicher- oder Tokenersparnis.

## Entfernte Pfade und erhaltene Datenprimitive

Gegen die Ausgangsbasis fehlen diese vollständigen Produktdateien:

| Datei | Frühere Zeilen | Entscheidung |
| --- | ---: | --- |
| `src/patchharbor/result_runtime.py` | 203 | Metadaten-/Lesepfad für das eingebettete Runtime-Wheel entfernt |
| `src/patchharbor/runtime_artifact.py` | 91 | Legacy-Wheel-Provider entfernt |
| `src/patchharbor/runtime_wheel.py` | 329 | Wheel-Rezeptvalidator und Runtime-Materializer entfernt; gemeinsam nötige Datenprimitive zuvor in RF-05 getrennt |
| `scripts/runtime_bootstrap.py` | 222 | Separaten Runtime-Wheel-Installationsbootstrap entfernt |

Diese 623 Produktzeilen und 222 Skriptzeilen sind Bruttoentfernungen, keine
zusätzliche Nettoersparnis. RF-05 hat benötigte kanonische JSON-, Inventar- und
begrenzte ZIP-Primitiven erhalten; RF-06 hat den tatsächlich überholten
Wheel-Vertrag einschließlich Zwischenhelfer `wheel_record.py` entfernt.
Der normale Wheel-Build erzeugt weiterhin sein RECORD im Buildbackend.
Result-1/2-Zweige und fehlende-Handoff-Erfindung wurden aus verbleibenden
Produktdateien entfernt. Der aktuelle Produktpfad verwendet PYZ oder den
bereits vorhandenen, begrenzten und am Quellbaum verankerten Source-Vertrag.

Die entfernten Implementierungen wurden nicht in Test-Supportmodule kopiert.
Die ausführbaren eingefrorenen Result-1/2-Modulbäume und positive 1.3.0-Reader-
Tests entfallen ebenfalls; alte ZIPs bleiben als negative Datenfixtures erhalten.
Der Zuwachs der Supportmodule stammt aus benannten gemeinsamen Testfixtures
(RF-03), Importgraph-Prüfung und Abnahmenachweisen. Er wird oben separat
ausgewiesen; die gesamten Testquellen ohne Fixtures sind dennoch kleiner.
Statische Kanten erfassen AST-Importanweisungen einschließlich relativer Imports,
keine behauptete vollständige Laufzeit- oder dynamische Importanalyse.

## Gepflegte und generierte Quellen

`scripts/pyz_bootstrap.py` und der CHAT-Programmblock waren vor RF-07 zwei
manuell zu synchronisierende Kopien. Heute pflegt man genau das Skript;
`scripts/render_chat_bootstrap.py` erzeugt und prüft dessen vollständige Kopie.
Der aktuelle Programm-SHA ist in beiden Orten
`043e5afd0e3ffee49f8bfeb6b226193dafd9b194dc257907a9054d750206b343`.
Die Kopie wurde nicht gelöscht; lediglich die doppelte manuelle Pflege entfällt.
Generatorcode ist weiter gepflegter Buildcode, kein zweiter Bootstrapalgorithmus.

Die Workflow-Matrizen sind seit RF-11 generierte Abschnitte aus
`tools/acceptance-catalog.json`; die Jobabläufe außerhalb dieser Abschnitte
bleiben gepflegte YAML. Buildgenerierte PYZ-Identitäten, Ressourcen und ZIPs
sind keine zusätzlich gepflegten Python-Produktquellen in dieser Messung.
Beide Generatoren besitzen explizite, lesende `--check`-Aufrufe.

## Zuordnung entfernter Tests und Grenzen der Abnahme

Die vollständigen fachlichen Zuordnungen bleiben unter
[RF-04](rf04-test-mapping.md) und [RF-06B](rf06-legacy-removal.md) erhalten:
reine Prosa-/Layout-/Quelltextprüfungen entfallen, echte Verhaltensgrenzen
bleiben geprüft; Wheel-spezifische Fälle entfallen mit ihrem Produktpfad.
Allgemeine Pfad-, Herkunfts-, Inhalts-, Budget-, Fallback- und Fehlerverträge
haben die dort ausdrücklich benannten PYZ-/Installations-/Referenznachweise.
RF-11 bindet Pflichtvarianten zusätzlich an explizite Nachweiskennungen.
Eine statische Funktionszahl ist kein pytest-Collectionvergleich; parametrisierte
Fälle und Skips werden in den tatsächlichen Berichten separat geprüft.
RF-12 entfernt oder verändert keine Testkennung und ergänzt keine Prosatests.

Development-Auswahl für Bundle 069 (parallel, 12 Worker):

- Bootstrapquelle/Generierung, stdlib-Start und eingebettete eigene Anleitung:
  `test_bootstrap_generation.py`, `test_pyz_bootstrap.py`, `test_result3_embedded_bootstrap.py`.
- Fortgeltende Artefakt-/Referenzverträge und Python-/Capabilityvarianten:
  `test_compatibility_140.py`, `test_python_variants.py`, `test_result_capabilities.py`.
- Ausführbare Pack-Beispiele, passive Handoff-Ressourcen und normale Installation:
  `test_pack_examples.py`, `test_chat_contract.py`, `test_bundle_handoff.py`,
  `test_release_audit.py`, `test_runtime_packaging.py`, `test_packaging_e2e.py`.
- Echte Commit-/Fehlergrenzen: `test_handoff_commit_sequence.py` und die
  23 privaten Verhaltenstests des exakt ausgelieferten Entrypoints.

Alle Produkt-Testdateien liegen unter `tests/`. Der lokale Bericht und die
Exitcode-Quittung werden in Exchange/reports als
`patchharbor-refactoring-069-selected.json` bzw. `.completion.json` dokumentiert;
die Paketprüfung bindet deren vollständige Hashes und tatsächliche Quelldateien.
Dies ist keine Development-Vollsuite. Apply führt vor dem einen Commit seine
vollständige parallele Suite aus und pusht erst danach genau einmal normal.
Nur Christian startet CI. Native Windows-/Interpreter-/CIFS-/Release-Nachweise
werden nicht aus diesem Dokumentationsschritt oder älteren grünen Läufen abgeleitet.
