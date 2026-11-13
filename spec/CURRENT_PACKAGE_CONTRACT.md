# Aktueller Paketvertrag: genau eine Version, keine Migration

Dieser Vertrag ersetzt alle früheren Zusagen zur Paket-, Handoff- und
Replay-Kompatibilität. Historische Spezifikationen und Nachweise bleiben
Dokumentation ihrer damaligen Stände und aktivieren keine alten Leser.

## Versionsbindung

PatchHarbor verarbeitet TaskBundles und ResultBundles ausschließlich für die
eigene Produktversion und im jeweils aktuellen Format. `patchharbor_version`
ist ein verpflichtendes Zeichenkettenfeld in `task.json` und `manifest.json`.
Es muss exakt der Version des ausführenden Werkzeugs entsprechen, einschließlich
Patch- und Entwicklungsversionsbestandteilen. Maßgeblich ist das laufende
Werkzeug, nicht GitHub, der Dateiname oder die Version des bearbeiteten Projekts.

Fehlende, ältere, neuere oder typfalsche Versionsangaben werden abgelehnt.
Produkt- und Formatversion werden unabhängig geprüft. Gleiche Formatnummern
heben eine abweichende Produktversion nicht auf. Dieselbe Produktversion
berechtigt nicht zur Verwendung eines abgelösten Formats.

Task-Erkennung, Inspect, Validate, Pack mit Referenz, Execute, automatische
Watcher-Auswahl, Result-/Snapshot-Leser und Starthelfer dürfen die Grenze nicht
umgehen. Eine unpassende Version wird vor Entrypoint-Start und Veränderungen
am Zielrepository abgelehnt. Der Monitor zeigt den Versionskonflikt an.
Bloße Dateityperkennung ist kein Validierungs- oder Ausführungsnachweis.

## Aktuelle Formate

| Bestandteil | Einziger unterstützter Vertrag |
| --- | --- |
| TaskBundle | Format 3, acht Pflichtfelder einschließlich `patchharbor_version` |
| ResultBundle | Format 5, verpflichtende `patchharbor_version` |
| Environment | Format 3, separater Helfer mit Pfad, Größe und SHA-256 |
| Runtime-Metadaten | Format 3; `task_formats: [3]`, `result_formats: [5]` |
| Pack / Inspect / Validate JSON | Ausgabeversion 4 |
| Execute JSON | Ausgabeversion 2 |
| Replay-Ablage | Schema 5; keine Leser für Schema 1–4 |
| Core-PYZ | Ein aktuelles Profil mit Python-Untergrenze 3.10 und Pflichthelfer |

Runtime-Metadaten und eingebettete PYZ müssen dieselbe Produktversion wie das
Result und das verarbeitende Werkzeug tragen. Auch `runtime unavailable` hat
eine bekannte Produktversion; fehlende Runtime-Bytes verhindern diesen
Versionsvergleich nicht. Der eigenständig verteilte Starthelfer trägt seine
Version als beim Build geprüfte Konstante. Seine Vorprüfung führt keine
beschriebene Runtime aus und ersetzt keine vollständige native Resultprüfung.

## Keine Migration

Es gibt keine Konverter, Lesemigration, Feldübersetzung, stillschweigende
Umetikettierung oder automatische Reparatur abgelöster Formate. Unpassende
Pakete werden weder ausgeführt noch als erfolgreiche Archiv-/Recovery-Belege
verwendet. Ihre Dateien bleiben erhalten.

Ein nicht unterstütztes Replay-Schema wird unverändert abgelehnt. Es darf nicht
automatisch durch einen leeren Zustand ersetzt werden. Ein unverändertes
aktuelles Registry-, Konfigurations- oder Zustandsschema kann weiterverwendet
werden; das ist keine Migration. Lockidentitäten und vollständige
Repository-Bindungen bleiben unverändert.

Nach einem Werkzeugwechsel wird für weitere Tasks ein neues Result direkt aus
dem tatsächlichen Repository erzeugt: `patchharbor bundle REPOSITORY`. Alte
Resultdateien werden dafür nicht konvertiert. Eine erforderliche frische
Entwicklungsumgebung wird ausdrücklich initialisiert; Replay-Nachweise werden
nicht automatisch gelöscht.

## Erhaltene Oberflächen und Bezeichnungen

Öffentliche CLI-Aliase bleiben erhalten. `patchharbor apply` delegiert an
denselben aktuellen Execute-Pfad und akzeptiert keine alten Pakete.
`api.run_scripts`, `patchharbor fs run` und ScriptBundle bleiben als eigenständiger,
deprecated Skriptweg erhalten. Dieser ausdrücklich ausgenommene Weg ist nicht
produktversionsgebunden und ist kein alternativer Task-/Result-Leser.

Interne Namen für Task-Ausführung, Starter, Worker, Testhelfer und Testfälle
verwenden `execute`. Fachliche Git-Operationen wie `git apply` behalten ihren
Namen. Python 3.10/3.11 und native Windows-Unterstützung bleiben erhalten.

## Nachweise

Historische erfolgreiche Ausführungsmatrizen und eingefrorene alte PYZs sind
keine Release-Anforderung. Aktuelle Tests prüfen dagegen fehlende, ältere und
neuere Versionen, Versionswidersprüche, alte Formate und unveränderte Dateien
bei Ablehnung. Integrität, Pfad-/ZIP-Grenzen, Replay, Locks, Bindung und aktuelle
Script-Runner-/Alias-Funktionen werden weiterhin geprüft.
