# Große Bundles mit `--force`

`--force` hebt die Größen- und Mengengrenzen für **diesen einen manuellen Aufruf**
auf. Es setzt keine neue feste Obergrenze und wird weder gespeichert noch aus
Bundle-Inhalten, Umgebungsvariablen oder einem vorherigen Aufruf übernommen.

```sh
patchharbor bundle /pfad/zum/repository --force
patchharbor pack ./inhalt --reference-bundle ./state.zip --entrypoint run.sh --output-dir ./ausgabe --force
patchharbor inspect ./task.zip --force
patchharbor validate ./task.zip --reference-bundle ./state.zip --force
patchharbor execute ./task.zip --force
```

Ein großes Bundle benötigt die Freigabe auch beim späteren Lesen, Packen oder
Execute. Der Alias `apply` unterstützt denselben Schalter. Manuelles `execute`
ohne Dateiangabe kann damit auch große Kandidaten im eigenen Exchange auswählen.
Bei Execute gilt die Freigabe für den Task und die Veröffentlichung seines
Result Bundles. `--dry-run --force` hebt ebenfalls nur Ressourcengrenzen auf;
Dry-Run führt den Entrypoint weiterhin nicht aus.

| Ressource | Standardgrenze | Mit `--force` |
| --- | --- | --- |
| Eingabe-ZIP und erzeugtes Task-ZIP | 256 MiB | Keine Software-Größengrenze |
| Einzelner Inhalt | 256 MiB | Keine Software-Größengrenze |
| Entpackte Inhalte / Snapshot-Rekonstruktion | 512 MiB | Keine Software-Größengrenze |
| Äußere ZIP-Einträge | 250.011 | Keine Mengengrenze |
| Gespeicherte Repository-Dateien | 250.000 insgesamt | Keine Mengengrenze |
| Knoten beim Pack-Scan | 10.000, einschließlich Verzeichnissen und Wurzel | Keine Mengengrenze |
| Begleitdokument je Datei | 128 KiB | Keine Software-Größengrenze |
| Eingebettete Runtime | 16 MiB PYZ, 32 MiB Inhalt, 1.000 Einträge, 1 MiB Rezept | Ressourcenbudgets aufgehoben |

Task- und Referenz-ZIPs unterstützen ZIP64. Die kanonische Runtime behält ihren
eigenen geschlossenen ZIP-Profilvertrag. `--force` ändert keine Formatmerkmale,
Pfadlängen, zulässigen Dateitypen oder Namensräume.

CRC, vollständige Hashes, tatsächliche Größen gegen Deskriptoren, Dateizustand
während des Lesens, Marker und Produktversion werden weiter geprüft. Ebenso
gelten Repository-Bindung, Locks, Replay, No-overwrite und Entrypoint-Regeln.
`--force` repariert keine beschädigte Referenz und erteilt keine neue
Ausführungsberechtigung. Verfügbarer Speicher, Plattenplatz, Python und
Betriebssystem bleiben die praktischen Grenzen; Inhalte werden weiterhin zum
Teil vollständig im Speicher gehalten.

Watcher und `execute --automatic` haben keine Force-Freigabe. Ein solcher Task
wird bewusst mit dem manuellen Befehl ausgeführt. Die begrenzte Beobachtung im
Monitor und Profiling-Grenzen sind eigene Verträge und werden nicht verändert.

## Separater Starthelfer und Python-API

Auch der aus einer vertrauenswürdigen Referenz entnommene Starthelfer unterstützt
den Schalter. Die Herkunftsentscheidung und der externe Hash bleiben erforderlich:

```sh
python -I -S -B /trusted/tools/pyz_bootstrap.py ./state.zip --trusted-source-sha256 VOLLSTAENDIGER_SHA256 --prepare-in /privat/neue-runtime --force
```

Bei direkter Nutzung ist `force=True` jeweils separat an `assess`, `prepare`
und gegebenenfalls `import_api` zu übergeben. Die geladene Core-API übernimmt
diese Einstellung nicht automatisch. Dort unterstützen `bundle`, `pack_task`,
`inspect_task`, `validate_task`, `read_reference_snapshot`, `execute`,
`execute_guarded` und `dry_run` das boolesche Schlüsselwort `force=False`.
Beispiel: `api.pack_task(..., force=True)`.

Die Freigabe ist an den laufenden API-Aufruf gebunden und wird auch nach einem
Fehler oder Abbruch zurückgesetzt. Gleichzeitige Aufrufe teilen sie nicht.
Pakete und Maschinen-JSON benötigen dafür kein zusätzliches Force-Feld.
