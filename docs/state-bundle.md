# State, Task und Result

Diese Begriffe beschreiben die aktuelle Weiterentwicklung auf `dev` nach 2.0.1.
Die Änderung ist noch kein neues Release.

| Paket | Entsteht durch | Zweck |
| --- | --- | --- |
| **State Bundle** | `patchharbor bundle` | Aktuellen Repository-Arbeitsstand an den Chat übergeben. |
| **Task Bundle** | `patchharbor pack` | Änderungen und Entrypoint an diesen geprüften Zustand binden. |
| **Result Bundle** | `patchharbor execute` | Tatsächlichen Zustand und Ausführungsergebnis zurückgeben. |

## Einstieg und erneute Zustandsübernahme

```sh
patchharbor bundle /absoluter/pfad/zum/repository
```

Der Befehl bleibt `bundle`. Er meldet `State Bundle created: ...` und erzeugt
`<Repository>_State_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip`, gegebenenfalls mit dem
konfigurierten Suffix nach `.zip`. Zeitpunkt und Datum sind UTC. Bei `--json`
stehen Pfad und Status unter `result.state_bundle_path` und
`result.state_bundle_status` im Ausgabeformat 2.

Das State enthält Base-Dateien, staged/unstaged Änderungen, nicht ignorierte
untracked Dateien, die vollständige Repository-Bindung, Chat Instructions und
Umgebungsdaten. Soweit verfügbar kommt die passende Core-PYZ mit Starthelfer dazu.
Ignorierte Dateien und Git-Historie gehören nicht zum Snapshot.

Das ist sowohl der Einstieg für einen neuen Chat als auch die erneute Grundlage
nach verlorenen Dateien oder einem neu gestarteten Chat-Arbeitsverzeichnis.
Es rekonstruiert keine Gesprächserinnerung, virtuelle Umgebung oder verlorene
Ausführungsprotokolle. Der Auftrag muss weiterhin bekannt sein.

## Weiterarbeiten

State und Result heißen gemeinsam **Referenzbundles**. Beide können bei
`pack` und `validate` als `--reference-bundle` verwendet werden. Nach Execute
zuerst das tatsächliche Result und dessen Logs prüfen; ein Fehler kann Änderungen
oder Commits hinterlassen haben. Der nächste Task bindet an diesen tatsächlichen
Stand. Ein frisches State ist sinnvoll, wenn dieser Übergabestand fehlt oder
das Repository inzwischen anderweitig verändert wurde.

Ein State bescheinigt nur seine eigene Zustandserfassung. Es beweist keinen
früheren Execute, keine Tests und keinen Commit. Auch ein Result nach Fehler oder
Dry-Run bleibt ein Result; es wird nicht zum State umetikettiert.

## Große Zustandsaufnahmen

`patchharbor bundle --force` hebt die Ressourcenbudgets dieses Aufrufs auf.
Das Lesen und Verarbeiten großer Referenzen benötigt jeweils erneut `--force`;
siehe [Größenfreigabe](bundle-size-limits.md).

## Technischer Vertrag

State und Result verwenden Snapshotformat 5 mit unterschiedlichen Markern:
`patch-harbor-state-bundle` und `patch-harbor-result-bundle`. Sie müssen zu
`logs/run.json.operation` (`bundle` oder `execute`) und dem Begleittyp passen.
Dateinamen sind frei transportierbare Namen und keine Typnachweise. Nur aktuelle,
vollständig validierte Pakete der eigenen Produktversion werden verarbeitet;
es gibt keine Migration alter Pakete durch Umbenennen oder Konvertierung.

Die Python-API liest beide Arten mit `api.read_reference_snapshot(...)`.
Der zurückgegebene `ReferenceSnapshot` enthält `bundle_kind` und denselben
geprüften Dateizustand. Die gemeinsame Verarbeitung wird nicht dupliziert.
Der deprecated CLI-Alias `apply` bleibt erhalten.
