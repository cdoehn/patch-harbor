# Pack-Beispiele und Grenzen der Prüfung

Diese Beispiele gelten nach der geprüften Bereitstellung der Runtime aus dem
[ursprünglichen Result](runtime-bootstrap.md). Sie verwenden dieselbe vollständige
Referenz für `pack` und `validate`. Der Inhaltsordner enthält nur die bewusst
gewählten Dateien; der Ausgabeordner liegt daneben und existiert bereits.
Die Bindung stammt vollständig aus dem Result. Ein nummeriertes Chat-Bundle und
die neue Paket-UUID sind verschiedene Kennungen.

## Drei gleichwertige Aufrufe

Für einen Bash-Entrypoint `run.sh`:

```text
patchharbor pack /work/contents --reference-bundle /work/result.zip --entrypoint run.sh --output-dir /work/output --json
python -I -S -B /private/patchharbor-VERSION.pyz pack /work/contents --reference-bundle /work/result.zip --entrypoint run.sh --output-dir /work/output --json
```

Die API einer vorhandenen passenden Installation lautet:

```python
from patchharbor import api

packed = api.pack_patch(
    "/work/contents", reference_bundle="/work/result.zip",
    entrypoint="run.sh", output_directory="/work/output",
)
checked = api.validate_patch(packed.path, reference_bundle="/work/result.zip")
assert checked.scope == "reference" and checked.binding_matches
print(packed.path, packed.package_sha256)
```

Für Python-only ohne Installation liefert der geprüfte Bootstrap nach `assess`
und `prepare` über `api = bootstrap.import_api(prepared)` genau dieselbe API.
Ein bereits geladenes fremdes `patchharbor` erfordert einen frischen Prozess.
Für ein Windows-Ziel heißen Entrypoint und Option stattdessen `run.ps1`; die
Datei enthält PowerShell-Code. Die lokalen Pack-Aufrufe starten keine Ziel-Shell.

## Vollständige Dateien

`contents` enthält `tracked.txt` mit den gewünschten endgültigen Bytes und einen
Entrypoint. Apply schreibt `tracked.txt` bereits **vor** dem Entrypoint an seinen
relativen Zielpfad. Der Entrypoint muss sie daher nicht aus einem angenommenen
ZIP-Stagingordner kopieren. Ein einfaches Bash-Beispiel ist:

```bash
# PATCHHARBOR
set -eu
test "$(cat tracked.txt)" = changed
```

Für PowerShell:

```powershell
# PATCHHARBOR
if ([System.IO.File]::ReadAllText('tracked.txt').TrimEnd() -ne 'changed') { exit 31 }
exit 0
```

## Diff und gemischte Inhalte

Ein Diff ist eine normale Nutzdatei, beispielsweise `change.patch`. Apply schreibt
sie zuerst ins Repository; erst der Entrypoint führt sie ausdrücklich aus:

```bash
# PATCHHARBOR
set -eu
git apply -- change.patch
```

```powershell
# PATCHHARBOR
git apply -- change.patch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Bei gemischten Paketen kommen vollständige Nutzdateien hinzu. Sie liegen ebenfalls
schon vor dem Entrypoint im Repository. Der Inhaltsersteller sorgt dafür, dass
Diff und vollständige Dateien miteinander und mit dem tatsächlichen Resultzustand
übereinstimmen. Pack wählt keine Änderungen selbst und untersucht keine fachlichen
Wechselwirkungen. Nutzdateien wie `change.patch` bleiben bis zu einer ausdrücklich
vorgesehenen Bereinigung vorhanden; der Entrypoint und `PATCHHARBOR_META` werden
nicht als Projektdateien übernommen.

## Diagnose ohne Commit

Der Inhaltsordner darf ausschließlich einen Entrypoint enthalten. Er kann zum
Beispiel `git status --porcelain=v1` ausgeben. Die Ausgabe landet im Ausführungslog
des tatsächlichen Apply-Results. Keine Nutzdatei, kein Commit und kein Push sind
für eine solche Diagnose nötig. Auch eine Diagnose braucht die vollständige
Repositorybindung; `fs run` ersetzt diese nicht.

## Erfolgreiches Pack ist kein erfolgreicher Skriptlauf

Diese Bash-Datei trägt den richtigen Pflichtmarker, enthält aber falsche Syntax:

```bash
# PATCHHARBOR
if deliberately broken (
```

Pack und statische Referenzvalidierung dürfen hier erfolgreich sein. Sie führen
die Datei nicht aus und behaupten weder Shellsyntax noch Projekt-Test-Erfolg.
Erst der tatsächliche Apply meldet den Entrypointfehler. Sein Result und Log sind
maßgeblich; bereits geschriebene Nutzdateien werden nicht global zurückgerollt.
Fachliche Validatorfehler, ungültige Referenzen oder falsche Bindung bleiben dagegen
blockierend und dürfen nicht als technischer Startfallback umgangen werden.

Nach Pack die endgültige ZIP, Payloads, Größe und vollständige SHA-256 prüfen.
Eine Ausgabestörung nach erfolgreicher Veröffentlichung erzeugt kein zweites
Paket. Cleanup-Warnungen können zu einem vollständigen Erfolg gehören; sie nennen
eigene temporäre Reste. Es gibt keinen automatischen Versand oder Watcherstart.
Der Benutzer bestimmt die eine kanonische finale ZIP und ihren Übergabeort.

`tests/test_pack_examples.py` führt diese fünf Verhaltensfälle mit installierter
CLI, PYZ-CLI und PYZ-API sowie tatsächlichem Apply aus. Die Tests prüfen Dateien,
Bindung, Ausführungslog und Commitzustand, keine Dokumentformulierungen. Die
zusätzliche Erstnutzung aus der eigenen eingebetteten Anleitung und die drei
identischen PYZ-Generationen bleiben in der vollständigen Suite enthalten.
