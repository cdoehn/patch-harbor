# PatchHarbor 1.2.1 – Chat-Initialisierung

**Vertragsversion:** 1.2.1<br>
**Patch-Paketmarker:** `patch-harbor`<br>
**Patch-Paketformat:** `1`<br>
**Result-Bundle-Marker:** `patch-harbor-result-bundle`<br>
**Fingerprint-Algorithmus:** `patchharbor-state-v1`<br>
**Entrypoint-Pflichtmarker:** `# PATCHHARBOR`

Diese Datei ist die verbindliche Handlungsanweisung für einen externen
Entwicklungs-Chat. Halte dich an diesen Vertrag, wenn du aus einem PatchHarbor
Result Bundle ein Patch-Paket für ein registriertes Repository erzeugst.

## 1. Deine Aufgabe und die Sicherheitsgrenze

Der Chat entwickelt; der lokale Runner bindet jedes Patch-Paket an genau eine
registrierte Repository-Instanz und ihren geprüften Zustand.

PatchHarbor registriert lokale Git-Instanzen per UUID v4, prüft Base-Commit und
vollständigen Fingerprint, validiert sichere ZIP-Pakete, ordnet sie per repo_id
zu und schreibt geprüfte Payloads vor genau einem Bash-/PowerShell-Entrypoint.
Es erfasst stdout/stderr, Exit-Code, Laufzeit, Abbruch und Toolfehler, erzeugt
Result Bundles und unterscheidet diese von Patch-Paketen. Exchange-Auswahl und
Archivierung folgen den unten beschriebenen Regeln.

Die für diesen Vertrag relevanten öffentlichen Befehle sind:

```text
patchharbor configure exchange-directory VERZEICHNIS
patchharbor configure bundle-suffix .txt
patchharbor configure bundle-suffix --clear
patchharbor configure archive-dir PatchHarbor-Archive
patchharbor configure archive-dir --clear
patchharbor configure show
patchharbor register [REPOSITORY]
patchharbor registry list
patchharbor unregister REPOSITORY_OR_REPO_ID
patchharbor context [REPOSITORY]
patchharbor bundle [REPOSITORY]
patchharbor apply [PATCH_ZIP]
patchharbor apply --dry-run [PATCH_ZIP]
patchharbor fs run QUELLE
patchharbor-watcher
```

### Vorhandenen Core nutzen

Prüfe vor Entrypoint-Code die tatsächlich vorhandenen Core-/API-Funktionen.
Nutze sie für Payload-Ausbringung, atomare Ersetzung, Pfad-/Sicherheitsprüfung,
Repository-Zuordnung, Zustand und Archivierung statt eigener Nachbauten.
Fehlende allgemeine Infrastruktur gehört bevorzugt als eigener geprüfter
Schritt in den Core. Keine erfundene API, rekursiven apply/bundle-Aufrufe oder
Umgehung der bestehenden Checks. Entrypoints orchestrieren auftragsspezifische
Änderungen, Tests und Commits; sie sind kein zweiter PatchHarbor-Core.

### POSIX-Payload-Modi

Bestehende rwx-Modi bleiben erhalten, auch 0664/0666/0777. Das respektiert lokale
Rechte, bewertet sie nicht als sicher. Setuid/setgid/sticky bleiben verboten.
Neue Dateien: sichere Unix-ZIP-Modi, sonst 0644; Skripte explizit 0755.
ZIP/API-Modi dürfen zusätzlich kein group-/other-write enthalten, auch bei
bestehendem Ziel. Explizites 0600 ist nicht „fehlend“. Keine stille Reparatur.
Der Core setzt den Modus vor atomarer Ersetzung; interne Dateien bleiben privat.
Windows erhält keine Unix-ACL-Emulation. Bereits betroffene 0600-Dateien werden
nicht automatisch auf 0644 verbreitert; Eigentümer/ACLs sind nicht abgedeckt.
Beim Selbstupgrade den Writer aus einer privaten Kopie des Schritt-Cores
laden. Kein eigener Writer, kein vorab installierter W/R/C-Endzustand.

### Repositorylokale Einstellungen

Alle Repository-Einstellungen liegen ausschließlich in
`<Repository>/.patchharbor/config.json`: `exchange_directory`, `bundle_suffix`
und `archive_directory`. Global bleiben Registry, Locks und technischer
Replay-/Laufzeitzustand, keine Benutzer-Fallback-Konfiguration.
`configure` ermittelt sein Repository aus dem aktuellen Arbeitsverzeichnis,
auch aus Unterverzeichnissen. Es benötigt eine eindeutige Registrierung und
vorhandene gültige lokale ID, Konfiguration und Git-Ausnahme.

Nur eine echte Erstanmeldung mit `register` erzeugt die lokale Grundkonfiguration
im neuen geschlossenen Format 1: vier Felder `format_version: 1`,
`exchange_directory: null`, `bundle_suffix: ""` und
`archive_directory: "PatchHarbor-Archive"`. Danach muss der Benutzer pro Repository
`configure exchange-directory` ausführen. Gültiges `null` ist kein beschädigtes
Dokument. Die Setter erzeugen oder reparieren keine fehlenden Dateien; alte
globale Konfigurationen werden weder migriert noch gelesen. Bestehende ältere
Registrierungen benötigen die lokale Grundkonfiguration bewusst von Hand.
Niemals dafür ID, Registry, Locks oder Replay-State löschen. `unregister`
erhält ID und Konfiguration; erneutes Register nutzt sie. Ein Git-Clone erhält
keine ignorierten Metadaten. Nach echtem Verschieben kann Register den Pfad
aktualisieren, wenn der alte Pfad nicht mehr existiert.

Mehrere Repositorys dürfen denselben Exchange-Ordner nutzen oder getrennte
Ordner wählen. Der Watcher lädt pro Poll ihre lokalen Einstellungen über Core,
scannt physisch identische Ordner nur einmal und ordnet Pakete per vollständiger
`repo_id` zu. Automatische Auswahl akzeptiert nur Pakete im Exchange ihres
Zielrepositorys. Suffix und Archivregeln gelten immer pro Zielrepository,
auch bei gemeinsamem Exchange. Der Watcher überspringt gültig unkonfigurierte
Instanzen und fehlende Repository-Pfade; beschädigte Konfigurationen lebender
Repositorys führen zum Fehler, nicht zu stiller Reparatur.

Ein explizites Ausgabeziel darf einen nicht gesetzten oder nicht verfügbaren
Exchange umgehen, niemals eine fehlende oder ungültige lokale Konfiguration.
Die Begleitdaten beschreiben nur die Einstellungen des konkreten Repositorys.
`.patchharbor/` bleibt lokal per Git-Exclude ausgeblendet und fehlt im Snapshot;
die vollständige ignorierte Konfiguration darf nicht aus Bundle-Metadaten
rekonstruiert oder per Patch-Nutzdatei überschrieben werden. Insbesondere ist
`archive_directory` nicht zwingend als Begleitdatum enthalten.

### Apply, Watcher und Archivierung

`bundle` veröffentlicht ohne explizites Ausgabeziel im konfigurierten
Exchange-Ordner. Ein manueller parameterloser `apply` löst zuerst das aktuelle
Arbeitsverzeichnis einschließlich Repository-Unterverzeichnissen auf und
betrachtet ausschließlich Pakete für genau diese registrierte Repository-Instanz.
Unter den vollständig state- und replay-kompatiblen Kandidaten gewinnt der
Kandidat mit dem höchsten `mtime_ns`; bei Gleichstand entscheidet der Unicode-NFC-normalisierte
Dateiname deterministisch. Einen weiterhin passenden fehlgeschlagenen Patch darf
der manuelle Aufruf bewusst erneut versuchen. Der Watcher bleibt dagegen global
für alle registrierten Repositorys und verwendet einen automatischen Ursprung,
der fehlgeschlagene Pakete nicht erneut pollt. Erfolgreiche Pakete bleiben in
beiden Fällen Replay-geschützt. Ein expliziter `PATCH_ZIP` darf weiterhin über
seine `repo_id` ein anderes registriertes Repository als das aktuelle auswählen.
`fs run` ist der ältere explizite Runner.

Der normale Exchange-Scan kann ausschließlich nachweislich überholte, vollständig
geprüfte eigene Bundles in `PatchHarbor-Archive` direkt unter dem Exchange-Ordner
verschieben. Ein leerer Archivname (`configure archive-dir --clear`) deaktiviert
dies. Es werden keine Bundles gelöscht. Alter und Dateiname sind keine Beweise.
Patch-Pakete benötigen einen erfolgreichen Replay-Beleg mit bestätigtem
Abschlusscommit in der aktuellen Git-Historie; alte Belege ohne Abschlusscommit
bleiben liegen. Result Bundles benötigen einen vollständig geprüften sauberen
Erfolgssnapshot eines echten Vorfahren des aktuellen sauberen HEAD. Im Zweifel
bleibt die Datei unverändert. Manueller Scope und globaler Watcher bleiben wie
oben getrennt. Dry-Run archiviert nichts. Der explizit gewählte Patch bleibt vor
seiner Ausführung unangetastet. Führe keine eigene pauschale Archivierung aus.

PatchHarbor ist keine Sandbox und authentifiziert nicht den Ersteller eines
Pakets. Es verwaltet außerdem keine fachlichen Tests, Git-Commits,
Commit-Pläne, Journale, Builds oder Releases. Diese Schritte muss dein
vertrauenswürdiger Entrypoint im Auftrag des Benutzers ausführen. Eine
fehlgeschlagene Ausführung bewirkt keine globale automatische Rückabwicklung.

Lokale Repository- und Exchange-Pfade aus `environment.json` dienen passenden
Kommandozeilenbeispielen für den Entwicklungsrechner, nicht der Chat-Laufzeit.
Verwende sie niemals als Repository-Zuordnung oder in `patch.json`. Dafür gelten
weiterhin ausschließlich die vollständigen Bindungswerte aus `context.json`.

### Unterbrochene Attempts und Erfolgsnachweis

Neue Apply-Result-Manifeste verknüpfen `patch_sha256`, `run_id`, `repo_id`, die
vollständige erwartete Bindung und optional `completed_commit`. Replay-Format 4
speichert außerdem `attempt_run_id` und eine vor Veröffentlichung lokal verankerte
`result_sha256`. Nur ein vollständig passendes erfolgreiches Result und sauberer
Git-Nachweis unter dem echten freien Repository-Lock erlauben eine automatische
Reparatur `attempted -> succeeded`. Ältere Einträge ohne Beweise bleiben unverändert.

`screen -ls` ohne Socket beweist keinen Prozessabbruch. Ein `attempted`, ein dirty
Working Tree oder ein fehlendes Result kann zu einem noch laufenden Apply gehören.
Vor jeder manuellen Wiederherstellung den echten Lock-/Prozesszustand prüfen und
Änderungen sichern; niemals aufgrund dieser Symptome allein `git restore`,
`reset --hard` oder das Löschen von Lock-/Replay-Dateien anweisen. Recovery setzt
selbst keine Repository-Dateien zurück. SHA-Werte sind vollständig zu verwenden;
gekürzte UI-Werte und Dateinamen sind kein Erfolgsbeleg. Der lokale Replay-State
ist Vertrauensbasis, die Hashes sind keine digitalen Signaturen.

## 2. Erforderliche Eingaben

Für einen Entwicklungsauftrag benötigst du mindestens:

1. diese `CHAT_INSTRUCTIONS.md` (bei neuen Bundles bereits frisch im ZIP enthalten),
2. das aktuelle PatchHarbor Result Bundle der zu bearbeitenden registrierten
   Repository-Instanz,
3. die konkrete Benutzeraufgabe oder die Anweisung, den nächsten Plan-Commit
   vorzubereiten.

Eine menschenlesbare `register`-, `context`- oder `registry list`-Kurzansicht
mit `…` ist kein maschinenlesbarer Eingabevertrag und darf niemals als Quelle
für `patch.json` dienen. Das aktuelle Result Bundle ist im normalen
Entwicklungsworkflow die Quelle der vollständigen Bindungswerte. Wird
ausnahmsweise ein separater Kontext übergeben, muss er aus
`patchharbor context --json` stammen. Rekonstruiere niemals vollständige
Kennungen aus verkürzten Präfixen.

Behaupte nicht aus Gesprächserinnerung, den aktuellen Repository-Zustand zu
kennen. Fehlt ein aktuelles oder ausreichend vollständiges Result Bundle,
verwende `REPOSITORY_STATE_INCOMPLETE` nach Abschnitt 10 und erzeuge kein
Patch-Paket.

## 3. Result Bundle vollständig auswerten

Neue Result Bundles enthalten im ZIP-Root eine frisch aus der installierten
statischen Vorlage erzeugte `CHAT_INSTRUCTIONS.md` und `environment.json`.
Ein Bundle plus Auftrag genügt zur Initialisierung; kein Zusatzbefehl und keine
separate Datei sind nötig. `base/CHAT_INSTRUCTIONS.md` ist, falls vorhanden,
weiterhin unveränderter Repository-Inhalt, nicht die generierte Anleitung.
Bei alten Bundles ohne Begleitdaten bleibt die separate versionsgleiche Vorlage
zulässig. Fehlende Umgebungswerte niemals aus der Chat-Umgebung erfinden.

`environment.json` enthält Zielpfade, Suffix/Dateinamenregeln und UTC-Konvention,
OS/Userland, Kernel, Architektur, Python-, uv- und PatchHarbor-Version sowie die
konfigurierte (nicht bewiesen aktive) Shell. Unbekanntes bleibt `null`.
PRoot-Userland und Hostkernel können abweichen. Keine Hostnamen, IPs,
Seriennummern oder vollständigen Prozessumgebungen sammeln; benötigte absolute
Pfade können Benutzernamen enthalten.

Prüfe vor jeder Änderung mindestens:

- die generierte Root-`CHAT_INSTRUCTIONS.md` und `environment.json`, sofern vorhanden,
- `manifest.json` auf Marker, Format, Run-Ergebnis und Bundle-Status,
- `context.json` auf `repo_id`, `base_commit`, `state_fingerprint`,
  `fingerprint_algorithm` und `dirty`,
- den vollständigen Base-Snapshot unter `base/`,
- `changes/staged.patch`,
- `changes/unstaged.patch`,
- alle nicht ignorierten untracked Dateien unter `untracked/`,
- bei einem vorherigen Apply zuerst `logs/run.json`,
- bei Fehler, Warning oder unklarer Ausführung zusätzlich
  `logs/execution.log`.

Der aktuelle Repository-Zustand ergibt sich aus:

```text
base/
+ changes/staged.patch
+ changes/unstaged.patch
+ untracked/
```

Das Result Bundle enthält keine Git-Historie und keine ignorierten Dateien.
Erfinde fehlende ignorierte Inhalte nicht. Benötigt die Aufgabe zwingend einen
solchen Inhalt, stoppe mit `REPOSITORY_STATE_INCOMPLETE`.

Ein fehlgeschlagener Patch kann Dateien geändert oder neu erzeugt haben. Arbeite
immer auf dem tatsächlich zurückgegebenen Snapshot weiter und unterstelle keine
globale Rückabwicklung.

### Installationsfreier Start aus dem vorliegenden Format-3-Result

Das konkrete Resultformat entscheidet: Format 1/2 behält den unten beschriebenen
Legacyweg; Format 3 mit `embedded` verwendet genau seine PYZ. Der neue Writer
produziert Format 3. Bereits laufende alte Installationen behalten ihr bisheriges
Format bis zu einem gesonderten Upgrade. Python 3.12 oder neuer ist nötig.
Die PYZ enthält den vollständigen Core ohne Watcher. Es gibt keinen pip-, venv-,
Build- oder Downloadschritt und keine Änderung der vorhandenen Installation.

Prüfe Herkunft und Code dieser Anleitung zuerst. Ein SHA aus demselben unbekannten
ZIP ist kein Herkunftsnachweis. Speichere den folgenden Python-Code aus genau dieser
Root-Anleitung als `pyz_bootstrap.py` in einem privaten Arbeitsverzeichnis außerhalb
des Snapshots. Er benutzt nur die Standardbibliothek und lädt bei der Vorprüfung
keinen PatchHarbor-Code. Verwende den vollständigen SHA-256 des über den vertrauten
Übergabeweg erhaltenen Results; der Pfad zur Referenz bleibt unverändert.

```text
python -I -S -B /absolut/pyz_bootstrap.py /absolut/result.zip --trusted-source-sha256 VOLLSTAENDIGER_SHA256 --prepare-in /absolut/neues-privates-verzeichnis
```

Der JSON-Beleg nennt `path`, `command_prefix`, Runtime-Hash und
`scope=runtime_descriptor_precheck`; `full_reference_valid=false` ist beabsichtigt.
Der begrenzte Vorcheck ersetzt nicht die native Vollprüfung von Snapshot und Result.
Er entnimmt genau die kontrollierte PYZ, kein `extractall`. Nutze den tatsächlich
zurückgegebenen absoluten PYZ-Pfad anschließend so:

```text
python -I -S -B /absolut/patchharbor-VERSION.pyz pack /absolut/contents --reference-bundle /absolut/result.zip --entrypoint run.sh --output-dir /absolut/output --json
python -I -S -B /absolut/patchharbor-VERSION.pyz inspect /absolut/fertiges-patch.zip --json
python -I -S -B /absolut/patchharbor-VERSION.pyz validate /absolut/fertiges-patch.zip --reference-bundle /absolut/result.zip --json
```

`pack` muss exakt dasselbe Result vollständig nativ prüfen; danach muss `validate`
`scope=reference`, `binding_matches=true` und dessen vollständigen SHA bestätigen.
Ein fachlicher Fehler darf nicht durch einen schwächeren manuellen Weg umgangen
werden. Die fertige ZIP vor Auslieferung vollständig prüfen; lokale Vorprüfung
beweist weder Tests noch Apply oder CI. Ein vorhandenes Fremdmodul darf nicht
entladen werden, um die Runtime im selben Prozess auszutauschen.

Python-only ohne Subprozess: lade den untenstehenden geprüften Helfer als eigenes
Modul über `importlib.util.spec_from_file_location`, registriere dieses Modul vor
`exec_module` in `sys.modules`, rufe `assess`, `prepare` und ausdrücklich
`import_api(prepared)` auf. Vorhandene fremde `patchharbor`-Module führen zum
Herkunftskonflikt; verwende dann einen frischen Prozess. `sys.path` behält die
geprüfte PYZ für spätere Imports. `api.pack_patch`, `api.inspect_patch` und
`api.validate_patch` sind dieselben öffentlichen Fachoperationen wie die CLI.

Fehlen geeignetes Python, Vertrauen oder Ausführungsmöglichkeiten, ist die Runtime
`unavailable`, oder scheitert der technische Start, benenne den konkreten Grund
und nutze den bisherigen geprüften Übergabeweg. Behaupte keine native Vollprüfung.
Bei beschädigter deklarierter Runtime bleiben Originalbytes erhalten; gültige
Repositorydaten müssen separat nachgewiesen werden, `pack` akzeptiert keine
schwächere Referenz. Eine falsche Bindung bleibt blockierend.

Der folgende Code entspricht dem geprüften Repository-Helfer; ein Checkout ist
für seine Nutzung nicht nötig.

```python
# PATCHHARBOR-PYZ-BOOTSTRAP
"""Reviewed stdlib-only PYZ bootstrap; a precheck is not native Result validation.

Read this helper from a trusted source. A digest supplied by the same unknown
archive does not establish trust. No inspection here executes bundled code.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
from zipfile import BadZipFile, ZipFile, ZIP_STORED, ZIP_DEFLATED
from zipimport import zipimporter

MAX_INPUT = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_PYZ = 16 * 1024 * 1024
MAX_METADATA = 128 * 1024
HEX = re.compile(r'[0-9a-f]{64}')
METADATA_FIELDS = {'marker','format_version','status','reason','distribution','version',
                   'requires_python','profile','content_id','content_id_algorithm','artifact',
                   'runtime_dependencies','provenance','capabilities'}
VERSION = re.compile(r'[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?')


class BootstrapUnavailable(RuntimeError):
    """A technical/trust prerequisite is absent; no native success is claimed."""


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _json(raw):
    def constant(value): raise ValueError('non-finite JSON value')
    _require(not raw.startswith(b'\xef\xbb\xbf'), 'JSON BOM')
    result = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=constant)
    _require(type(result) is dict, 'JSON document must be an object')
    return result


def _state(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _capture(path, maximum):
    """One stable, bounded, no-follow regular-file capture, with no retry."""
    initial = path.lstat()
    _require(stat.S_ISREG(initial.st_mode) and not path.is_symlink()
             and not getattr(path, 'is_junction', lambda: False)(), 'linked or special input')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0)
                         | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum, 'file type or size limit')
        _require(not path.is_symlink() and not getattr(path, 'is_junction', lambda: False)(), 'linked input')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        _require(len(raw) <= maximum and _state(initial) == _state(before) == _state(after) == _state(path.lstat()),
                 'input changed during capture')
    return raw


def _directory_budget(raw):
    """Bound ZipFile's metadata allocation before opening the supplied archive."""
    start = max(0, len(raw)-65557)
    position = raw.rfind(b'PK\x05\x06', start)
    _require(position >= 0 and position + 22 <= len(raw), 'missing ZIP boundary')
    _, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from('<4s4H2IH', raw, position)
    _require(disk == directory_disk == 0 and disk_count == count and 0 < count <= MAX_ENTRIES,
             'ZIP entry budget or unsupported multipart/ZIP64 archive')
    _require(position + 22 + comment == len(raw) and offset + size == position,
             'ZIP directory boundary mismatch')
    cursor = offset
    for _ in range(count):
        _require(cursor + 46 <= position and raw[cursor:cursor+4] == b'PK\x01\x02', 'ZIP directory mismatch')
        name, extra, note = struct.unpack_from('<3H', raw, cursor+28)
        _require(0 < name <= 4096, 'ZIP member name budget')
        cursor += 46 + name + extra + note
    _require(cursor == position, 'ZIP directory count mismatch')


def _members(archive):
    infos = archive.infolist()
    _require(len(infos) <= MAX_ENTRIES, 'ZIP entry budget')
    names = set()
    for info in infos:
        name = info.filename
        _require(name == info.orig_filename and '\\' not in name and '\0' not in name,
                 'unsafe ZIP member name')
        path = PurePosixPath(name)
        _require(not path.is_absolute() and all(part and part not in {'.', '..'}
                 for part in name.split('/')) and ':' not in name and len(name) <= 4096,
                 'unsafe ZIP member path')
        _require(name not in names and not info.is_dir(), 'duplicate/directory ZIP member')
        names.add(name)
        _require(stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG)
                 and not info.external_attr & 0x10 and not info.flag_bits & 1,
                 'special/encrypted ZIP member')
        _require(info.compress_type in (ZIP_STORED, ZIP_DEFLATED)
                 and 0 <= info.file_size <= MAX_INPUT, 'unsupported ZIP compression or file size')
    _require(sum(info.file_size for info in infos) <= MAX_TOTAL, 'ZIP expanded byte budget')
    return names


def _read(archive, name, maximum):
    info = archive.getinfo(name)
    _require(info.file_size <= maximum, 'member exceeds byte budget')
    with archive.open(info) as stream:
        raw = stream.read(maximum+1)
    _require(len(raw) == info.file_size <= maximum, 'member size mismatch')
    return raw


def _descriptor(value, *, artifact=False):
    keys = {'path', 'size', 'sha256'} | ({'type'} if artifact else set())
    _require(type(value) is dict and set(value) == keys, 'descriptor schema')
    _require(type(value['path']) is str and type(value['size']) is int and value['size'] > 0
             and type(value['sha256']) is str and HEX.fullmatch(value['sha256']), 'descriptor values')
    if artifact: _require(value['type'] == 'pyz', 'unsupported artifact type')
    return value


def _checked(archive, descriptor, maximum):
    _require(descriptor['size'] <= maximum, 'descriptor byte budget')
    raw = _read(archive, descriptor['path'], maximum)
    _require(len(raw) == descriptor['size'] and sha256(raw).hexdigest() == descriptor['sha256'],
             'descriptor bytes/hash mismatch')
    return raw


@dataclass(frozen=True)
class PyzAssessment:
    reference: Path
    reference_sha256: str
    artifact_name: str
    artifact_sha256: str
    version: str
    pyz_bytes: bytes = field(repr=False)
    source_trusted: bool = False
    # This helper deliberately does not reimplement the full native reader.
    scope: str = 'runtime_descriptor_precheck'
    full_reference_valid: bool = False


def assess(reference, *, trusted_source_sha256=None):
    """Check the selected Result-3 runtime descriptors before any code import."""
    path = Path(reference).absolute()
    raw = _capture(path, MAX_INPUT)
    digest = sha256(raw).hexdigest()
    if trusted_source_sha256 is not None:
        _require(type(trusted_source_sha256) is str and HEX.fullmatch(trusted_source_sha256)
                 and digest == trusted_source_sha256, 'trusted Result digest mismatch')
    _directory_budget(raw)
    with ZipFile(BytesIO(raw)) as archive:
        names = _members(archive)
        manifest = _json(_read(archive, 'manifest.json', MAX_INPUT))
        _require(manifest.get('marker') == 'patch-harbor-result-bundle'
                 and type(manifest.get('format_version')) is int, 'not a supported Result')
        if manifest['format_version'] in (1,2):
            raise BootstrapUnavailable('legacy Result: use its documented wheel/previous handoff path')
        _require(manifest['format_version'] == 3, 'unsupported Result version')
        runtime = manifest.get('runtime')
        _require(type(runtime) is dict and set(runtime) == {'status','reason','metadata','artifact'},
                 'outer runtime schema')
        metadata_descriptor = _descriptor(runtime['metadata'])
        _require(metadata_descriptor['path'] == 'runtime/runtime.json', 'runtime metadata path')
        metadata = _json(_checked(archive, metadata_descriptor, MAX_METADATA))
        _require(set(metadata) == METADATA_FIELDS and metadata.get('marker') == 'patch-harbor-runtime'
                 and type(metadata.get('format_version')) is int and metadata['format_version'] == 2
                 and metadata.get('distribution') == 'patchharbor', 'runtime metadata identity')
        _require(metadata.get('status') == runtime['status'] and metadata.get('reason') == runtime['reason']
                 and metadata.get('artifact') == runtime['artifact'], 'runtime descriptor disagreement')
        runtime_names = {name for name in names if name.startswith('runtime/')}
        if runtime['status'] == 'unavailable':
            _require(runtime['artifact'] is None and type(runtime['reason']) is str
                     and runtime['reason'] in {'source_not_prepared','source_changed','artifact_missing',
                                               'artifact_mismatch','artifact_corrupt','artifact_unsupported',
                                               'resource_limit','read_error'}
                     and runtime_names == {'runtime/runtime.json'}
                     and all(metadata[key] is None for key in ('artifact','profile','content_id',
                         'content_id_algorithm','runtime_dependencies','provenance','capabilities')),
                     'invalid unavailable runtime')
            raise BootstrapUnavailable('runtime unavailable: ' + runtime['reason'])
        _require(runtime['status'] == 'embedded' and runtime['reason'] is None, 'runtime status')
        artifact = _descriptor(runtime['artifact'], artifact=True)
        _descriptor(metadata['artifact'], artifact=True)
        version = metadata.get('version')
        _require(type(version) is str and VERSION.fullmatch(version), 'runtime version profile')
        name = 'patchharbor-' + version + '.pyz'
        _require(artifact['path'] == 'runtime/' + name
                 and runtime_names == {'runtime/runtime.json', artifact['path']}, 'runtime member selection')
        _require(metadata.get('profile') == 'patchharbor-core-no-watcher-v1'
                 and metadata.get('requires_python') == '>=3.12'
                 and metadata.get('content_id_algorithm') == 'patchharbor-pyz-content-v1'
                 and type(metadata.get('content_id')) is str and HEX.fullmatch(metadata['content_id']),
                 'unsupported PYZ profile or Python requirement')
        capabilities = metadata['capabilities']
        _require(type(capabilities) is dict and set(capabilities) == {'operations','patch_formats','result_formats'}
                 and capabilities['operations'] == ['inspect_patch','validate_patch','pack_patch'],
                 'unsupported runtime capabilities')
        for key, expected in (('patch_formats',[1]), ('result_formats',[1,2,3])):
            values = capabilities[key]
            _require(type(values) is list and all(type(v) is int for v in values)
                     and values == expected, 'unsupported runtime read versions')
        provenance = metadata['provenance']
        _require(metadata['runtime_dependencies'] == [] and type(provenance) is dict
                 and set(provenance) == {'mode','source_commit','recipe_format_version'}
                 and provenance['mode'] == 'canonical_resources'
                 and type(provenance['recipe_format_version']) is int and provenance['recipe_format_version'] == 1,
                 'unsupported runtime provenance')
        commit = provenance['source_commit']
        _require(commit is None or (type(commit) is str and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',commit)),
                 'invalid runtime source commit')
        artifact_bytes = _checked(archive, artifact, MAX_PYZ)
    return PyzAssessment(path, digest, name, artifact['sha256'], version, artifact_bytes,
                         trusted_source_sha256 is not None)


@dataclass(frozen=True)
class PreparedPyz:
    assessment: PyzAssessment
    path: Path


def prepare(assessment, workspace):
    """Copy exactly one verified artifact into a new private directory; no install."""
    if not assessment.source_trusted:
        raise BootstrapUnavailable('runtime source is not trusted')
    if sys.version_info < (3, 12):
        raise BootstrapUnavailable('Python 3.12 or newer is required')
    _require(sha256(assessment.pyz_bytes).hexdigest() == assessment.artifact_sha256
             and 0 < len(assessment.pyz_bytes) <= MAX_PYZ, 'captured PYZ bytes changed')
    _require(assessment.artifact_name == 'patchharbor-' + assessment.version + '.pyz'
             and VERSION.fullmatch(assessment.version), 'artifact name changed')
    workspace = Path(workspace).absolute()
    workspace.mkdir(mode=0o700)  # existing destinations and symlinks are refused
    output = workspace/assessment.artifact_name
    with output.open('xb') as stream:
        stream.write(assessment.pyz_bytes); stream.flush(); os.fsync(stream.fileno())
    _require(sha256(_capture(output, MAX_PYZ)).hexdigest() == assessment.artifact_sha256,
             'prepared artifact changed')
    return PreparedPyz(assessment, output)


def _check_loaded_origin(path):
    for name, module in tuple(sys.modules.items()):
        if name == 'patchharbor' or name.startswith('patchharbor.'):
            spec = getattr(module, '__spec__', None)
            loader = getattr(spec, 'loader', None)
            if (not isinstance(loader, zipimporter) or Path(loader.archive) != path
                    or not str(getattr(spec, 'origin', '')).startswith(str(path) + os.sep)):
                raise BootstrapUnavailable('another PatchHarbor origin is already loaded; use a fresh process')


def import_api(prepared):
    """Explicit in-process use; retain the checked path for later lazy imports."""
    if sys.version_info < (3, 12):
        raise BootstrapUnavailable('Python 3.12 or newer is required')
    assessment, path = prepared.assessment, prepared.path
    if not assessment.source_trusted:
        raise BootstrapUnavailable('runtime source is not trusted')
    _require(sha256(_capture(path, MAX_PYZ)).hexdigest() == assessment.artifact_sha256,
             'prepared PYZ changed before import')
    _check_loaded_origin(path)
    if not sys.path or sys.path[0] != str(path):
        sys.path.insert(0, str(path))
    # Do not pop modules or remove this path on error: partial imports are not a
    # safe in-process version switch either. A failed import needs a fresh process.
    api = importlib.import_module('patchharbor.api')
    _check_loaded_origin(path)
    package = sys.modules['patchharbor']
    _require(package.__version__ == assessment.version, 'imported runtime version differs')
    _require(all(callable(getattr(api, name, None)) for name in
                 ('inspect_patch','validate_patch','pack_patch')), 'missing required public API')
    from patchharbor.pyz_artifact import PyzProvider
    # The imported Core now checks its complete canonical resources. This still
    # does not declare the original repository snapshot fully validated.
    captured = PyzProvider().capture()
    _require(captured.artifact is not None
             and captured.artifact.pyz_sha256 == assessment.artifact_sha256,
             'imported producer does not match the selected PYZ')
    return api


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('--trusted-source-sha256')
    parser.add_argument('--prepare-in', type=Path)
    args = parser.parse_args(argv)
    assessment = assess(args.reference, trusted_source_sha256=args.trusted_source_sha256)
    result = dict(scope=assessment.scope, full_reference_valid=False,
                  reference_sha256=assessment.reference_sha256, source_trusted=assessment.source_trusted,
                  artifact_sha256=assessment.artifact_sha256, version=assessment.version)
    if args.prepare_in is not None:
        prepared = prepare(assessment, args.prepare_in)
        result['path'] = str(prepared.path)
        result['command_prefix'] = [sys.executable, '-I', '-S', '-B', str(prepared.path)]
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BootstrapUnavailable as exc:
        print(json.dumps({'status':'fallback','reason':str(exc),'full_reference_valid':False}), file=sys.stderr)
        raise SystemExit(2)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, BadZipFile) as exc:
        print(json.dumps({'status':'invalid','reason':str(exc),'full_reference_valid':False}), file=sys.stderr)
        raise SystemExit(2)
```

### Geprüfte Runtime und verbindlicher bisheriger Übergabeweg

Result-Format 2 ergänzt `runtime/runtime.json` und gegebenenfalls ein kanonisches
Wheel. Format 1 sowie `unavailable` bleiben gültige Referenzen. `runtime/` ist
Werkzeugmaterial außerhalb des Repository-Snapshots; `base/runtime/` ist etwas
anderes. Das Finden eines Wheels erlaubt weder Installation noch Import.

Prüfe zuerst Herkunft und Berechtigung mit bereits vertrauenswürdigen Werkzeugen.
Ein Hash aus derselben unbekannten Quelle authentifiziert keinen Absender.
Prüfe äußere ZIP-Sicherheit, vollständiges Inventar, Größen, Hashes und das enge
Wheel-Profil einschließlich RECORD, Python-Anforderung, dependency-freier
Metadaten und Ausschluss von `.pth`, Fremdmodulen und Launchern **vor** Codeausführung.
Unbekannte Herkunft oder fehlender verlässlicher Prüfer führt zum bisherigen Weg.
Ein Skript aus dem ungeprüften Wheel darf nicht seine eigene Vertrauensbasis sein.

Erst danach explizit eine frische Umgebung außerhalb des Ziel-Snapshots anlegen.
Nur das geprüfte lokale Wheel offline installieren: kein Index, Nachladen,
Buildfallback, Interpreterdownload oder `--ignore-requires-python`. Ein vorhandener
Installer muss die vollständige `Requires-Python`-Bedingung vor Installation am
Zielinterpreter prüfen, etwa durch einen lokalen pip-Dry-Run. Eine venv ist keine
Sicherheits-Sandbox. Keine Session-Secrets weitergeben; `PYTHONPATH`/`PYTHONHOME`
bereinigen und einen fremden Arbeitsordner sowie den isolierten Interpreter nutzen.

Das separat reviewed Repository-Beispiel `scripts/runtime_bootstrap.py` und
`docs/runtime-bootstrap.md` konkretisieren den Ablauf. Der Helfer setzt eine
bereits vertrauenswürdige passende Core-Installation voraus; er ist keine neue
öffentliche API und wird nicht aus einer fremden Result-Runtime gestartet.
Fehlt er, bleibt die folgende bisherige Prüfung verbindlich.

Mit dem konkret geprüften venv-Interpreter (Windows: `Scripts/python.exe`,
POSIX: `bin/python`) prüfen:

```text
<venv-python> -I -m patchharbor.cli inspect /absolut/patch.zip --json
<venv-python> -I -m patchharbor.cli validate /absolut/patch.zip --reference-bundle /absolut/result.zip --json
```

**Fehlt oder versagt das Wheel, muss der bisherige Übergabeweg verwendet werden.**
Das gilt für fehlende/defekte Bytes, ungeklärte Herkunft, inkompatibles Python,
fehlenden Installer und technische Import-/Nutzungsfehler. Ein Versuch genügt;
keine Reparatur- oder Netzwerkschleife. Entwickle am geprüften tatsächlichen
Snapshot; verwende vorhandene vertrauenswürdige Paketprüfer oder die etablierten
ZIP-, Payload-, Hash- und Bindungsprüfungen. Alle vier vollständigen Werte aus
`context.json` bleiben verbindlich. Kein künstliches `git init` aus `base/`,
kein ungebundenes `fs run`; Apply prüft den realen Zustand erneut.

Bei ausschließlich defektem Runtime-Zusatz separat äußere ZIP-Sicherheit,
Pflichtdateien, Snapshot-Inventar/Blob-IDs/Hashes, Kontext und Run-Konsistenz
prüfen. Originalbytes und vollständige Result-SHA behalten; weder reparieren
noch als Format 1 umdeklarieren. Dieser Nachweis ist keine erfolgreiche native
Vollvalidierung des defekten Format-2-Results. Ungültige Repositorydaten,
unsichere Paketpfade und Bindungsabweichungen bleiben blockierend.

Ausfallgrund, Werkzeuge, tatsächliche Prüfungen und fehlende Nachweise benennen.
Statische Validierung belegt weder Tests noch CI, Authentizität oder Apply-Erfolg.
Die finale ZIP vollständig öffnen und prüfen; bei jeder Byteänderung erneut
prüfen. Genau eine kanonische Datei ausliefern; externe Backups nur bei
Autorisierung und bytegleich, ohne eine zweite ZIP wegen eines Backupfehlers.

## 4. Zielversion, Commit-Plan und Spezifikation finden

### Ausdrücklich ausgewählte Featurepläne und gemeinsame Normsätze

Ein durch den aktuellen Nutzerauftrag und vorhandene Projektverweise eindeutig
aktivierter Featureplan hat Vorrang vor einem allein aus der unveränderten
Paketversion abgeleiteten historischen Plan. Die untenstehende Suchreihenfolge
ist der Fallback, nicht die Erlaubnis, einen ausdrücklich aktiven Auftrag zu
verdrängen. Ein im Plan ausdrücklich als gemeinsam geltend erklärter
Spezifikationssatz wird vollständig gelesen; seine Bestandteile sind keine
konkurrierenden Alternativen. Echte unaufgelöste Konkurrenz bleibt ein STOP.

Für die Entwicklung von **PatchHarbor selbst**, solange der beauftragte
PYZ/PACK-Auftrag aktiv ist, gilt konkret:

```text
Plan: planning/pyz-pack/commit-plan.md
Normsatz: spec/SPECIFICATION.md
          spec/SPECIFICATION_EXTENSION_PYZ_PACK.md (Revision 2)
```

Die Paketversion bleibt vorerst 1.2.1; das reaktiviert keinen abgeschlossenen
Versions-, RIV- oder Watcher-Plan. Die gezielten Ausnahmen stehen in der
Erweiterung, unberührte Basisverträge gelten weiter. Der vorhandene CIFS-Plan
behält seine offenen Nachweise. Diese Projektzuordnung gilt nicht pauschal für
andere Repositorys, denen PatchHarbor dieselbe generische Vorlage mitliefert.

Der erste Schritt PP-00 / Bundle 024 integriert nur Dokumente und Verweise.
`pack` und die PYZ sind bis zu ihren nachgewiesenen Umsetzungsschritten
Zielzustand, keine bereits nutzbaren Befehle oder Artefakte. Die aktuellen
Wheel-/Result-2-Regeln und der etablierte Paketbau bleiben vorerst wirksam.

**Historie:** Die einmalige CI-only-Ausnahme für PP-00 / Bundles 024/025
ist mit dessen erfolgreichem Abschluss erfüllt. Result
`patch-harbor_Result_141601_1007_ef9735.zip` belegt Commit
`7a28bbc2189cdb2a78590e62a45e4d96b0ff893d` und sechs grüne Jobs in CI-Run
`37635401106`. Bundle 026 startete danach lokale PP-01-Tests. Diese wurden laut
`patch-harbor_Result_160403_1007_ee4cb0.zip` vor Staging/Commit/Push/CI
unterbrochen; damals waren die PP-01-Dateien vorhanden und uncommitted. Das ist kein
bestandener PP-01-Testlauf. Bundle 027 / PP-01-FIX1 setzt diese Änderungen fort.

### Aktive Laptop-Phase: volle parallele Tests, CI nur durch den Nutzer

Die spätere ausdrückliche Nutzeranweisung vom 7. Oktober 2026 ersetzt ältere
lokale serielle Gates, die Pixel-CI-only-Regel und den CI-Fünfertakt.
Development und Apply prüfen jeden Commitstand vollständig parallel, auch am
Bundle-Ende. Kein serieller Lauf und keine verkürzte Auswahl als Vollabnahme.
Nur Christian startet den manuellen CI-Workflow; Codex und Entrypoints tun das nie.

Die aktive Schleife setzt nach vollständig geprüften Watcher-Results den
PYZ/PACK-Plan fort, ohne feste Zahl erlaubter Korrekturen. Vorhandene Teilfortschritte
bleiben erhalten. Bei Planabschluss oder Nutzerstopp endet die Schleife.
Sicherheitsgrenzen und belastbare Resultbindung bleiben Voraussetzung.

Development bleibt ausschließlich in `patchharbor-codex`. Nur die fertig und
vollständig geprüfte kanonische Patch-ZIP gelangt atomar in den Exchange.
Der bereits laufende Watcher übernimmt allein den Apply. Keine direkten
Development-Commits, Apply-Mutationen, Hook-Umgehungen oder Watcher-Neustarts.
Nach erfolgreichen Commit-Gates genau ein normaler Push; kein automatisches Tag.

PP-00 bis PP-06A sind durch tatsächlich geprüfte Results bestätigt. Bundle 040
schaltet den gemeinsamen Writer auf Result 3 mit einer Core-PYZ um. Eigene
E-10-Erstnutzung, drei tatsächliche Generationen, normale Installation und
Core-Parität werden vor Übergabe vollständig parallel geprüft. Maßgeblich sind
Plan Abschnitt 1.20 und die aktuelle Testpolicy. Bereits laufende ältere globale
Installationen behalten ihren eigenen Stand; ein Quellpatch ersetzt sie nicht.
Ein älterer mitgelieferter Core kann `pack` oder Format 3 vermissen; dann bleibt
der geprüfte manuelle Paketvertrag nutzbar. Native Abnahme und Release bleiben offen.

Bestimme die aktive Zielversion aus dem Repository. Eine laut Plan erst zum
Release erfolgende Versionsanhebung ist kein Widerspruch; tatsächlich
widersprüchliche Zielversionen: `PLAN_AMBIGUOUS` oder `PLAN_SPEC_CONFLICT`.

Suche den Commit- oder Implementation-Plan in dieser Reihenfolge:

1. `planning/<version>/commit-plan.md`,
2. `planning/<version>/implementation-plan.md`,
3. ein eindeutig als Commit- oder Implementation-Plan erkennbares
   Markdown-Dokument direkt unter `planning/<version>/`,
4. genau ein eindeutig aktueller repositoryweiter Commit- oder
   Implementation-Plan.

Wähle keinen historischen Plan nur wegen eines ähnlichen Namens. Bei mehreren
plausiblen aktuellen Kandidaten verwende `PLAN_AMBIGUOUS`. Fehlt ein Plan und
der Benutzer verlangt ausdrücklich den nächsten Plan-Commit, verwende
`PLAN_NOT_FOUND`. Eine bewusst planlose Aufgabe kann als `OFF-PLAN` umgesetzt
werden.

Suche die Spezifikation in dieser Reihenfolge:

1. ein vom ausgewählten Plan ausdrücklich referenziertes Dokument,
2. `planning/<version>/specification.md` oder einen dort eindeutig als
   Spezifikation erkennbaren Markdown-Kandidaten,
3. `spec/SPECIFICATION.md`,
4. genau eine eindeutig aktuelle repositoryweite Spezifikation.

Bei mehreren plausiblen aktuellen Spezifikationen verwende `SPEC_AMBIGUOUS`.
Ist keine Spezifikation vorhanden, zeige später `Spec: nicht vorhanden` und
arbeite anhand von Plan, realem Repository und Benutzerauftrag.

Bestimme den Fortschritt ausschließlich aus dem gefundenen Plan und dem realen
Repository-Zustand. Kann die erreichte Planposition nicht eindeutig bestimmt
werden, verwende `PLAN_POSITION_UNKNOWN`; rate nicht.

## 5. Spezifikation, Plan, Projektregeln und Auftrag abgleichen

Prüfe vor der Umsetzung Spec, Plan, Snapshot und die tatsächlich verfügbaren
Regeln des Zielprojekts: aktuelle Nutzeranweisungen, mitgegebene/verfügbare
`AGENTS.md` sowie verbindlich referenzierte Entwicklungs- und Testvorgaben.
Explizite Nutzeranweisungen haben Vorrang vor dieser generischen Vorlage.
Ignorierte lokale Regeln sind nicht automatisch im Result enthalten; erfinde
fehlende Inhalte nicht.

Ein Bundle darf standardmäßig einen oder mehrere fachlich abgegrenzte Commits
enthalten. Wähle innerhalb des Auftrags nach Eignung, Abhängigkeiten und sinnvoll
beherrschbarer Größe eine passende Folge. Mehrere Commits brauchen allein wegen
ihrer Anzahl keine Genehmigung. Nutzerangaben zu Anzahl oder Umfang bleiben
maßgeblich. Jeder Commit muss ein fachlich geschlossener, testbarer Zwischenstand
sein; die Gesamtfolge bleibt im beauftragten Scope. Mehrere Commits erweitern
weder Scope noch Testpolicy.

Auch ein Diagnosebundle mit **null Commits** ist zulässig. Es sammelt die
beauftragten Diagnosen im Result/Log, staged und pusht nichts und erhöht keinen
Planzähler. Sein auftragsbezogener Prüfumfang bleibt erhalten; es benötigt keine
erfundenen Commit-Gates. Tatsächliche Änderungen und Teilerfolge immer auswerten.

Kleine notwendige Lücken im selben Commit-Scope als
`PLAN_SPEC_MINOR_DEVIATION` melden. Scope-Erweiterungen, vorgezogene Planpunkte,
neue Architekturentscheidungen oder Widersprüche nicht still umsetzen; eine
wesentliche unauflösbare Unklarheit gezielt klären oder stoppen.

## 6. Commit-Arten und Zähler

Ordne **jeden Commit** einzeln einer der drei sichtbaren Arten zu.

### `PLAN`
- Kennung, Position und Commit-Message exakt aus dem Plan übernehmen.
- Zähler `aktuelle Position / Gesamtzahl`; Planfortschritt ggf. im Commit pflegen.

### `FIX`
- Gehört zu genau einem Plan-Commit; `<PLAN-ID>-FIX<n>` ab `FIX1`.
- Commit-Message beginnt mit `Fix:`.
- Erhöht weder Gesamtzahl noch erreichte Planposition; zeige diese unverändert.

### `OFF-PLAN`
- Kurze Kennung und passende Commit-Message; `OFF-PLAN` sichtbar zeigen.
- Plan-Zähler unverändert; mit Plan `-- / <Gesamtzahl>`, sonst `-- / --`.

Ein Bundle darf einen oder mehrere solcher Commits enthalten; mehrere Commits
brauchen keine W/R/C-Ausnahme. Wenn Projekt oder Auftrag W/R/C verlangen, bleiben
W, R und C getrennte echte Zwischenstände mit eigenen Prüfungen und Commits;
auch mehrere Folgen dürfen in einem Bundle liegen. W/R/C ist kein allgemeiner
Default.

## 7. Genau ein sicheres Patch-Paket erzeugen

Erzeuge genau eine herunterladbare ZIP-Datei im sicheren PatchHarbor-Format.
Liefere keine parallele Shell-Datei, keinen zweiten Patch und keine alternative
manuelle Änderungsanleitung. Der Dateiname folgt exakt
`<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip`: Repository-Name zuerst,
dann `Patch`, UTC-Uhrzeit, Monat/Tag ohne Jahr und die ersten sechs Zeichen
einer Paket-UUID ohne `…`. Für Result Bundles gilt exakt
`<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip`; dessen ID6 stammt aus der
vollständigen Run-ID.

Hänge das optionale `bundle_suffix` aus der Result-`context.json` unverändert
an den Basisdateinamen an: `.txt` ergibt beispielsweise
`patch-harbor_Patch_181530_0908_abcdef.zip.txt`. Fehlendes Feld in älteren Bundles
oder leerer String bedeutet kein Suffix. Maßgeblich sind diese Metadaten,
nicht die Endung einer möglicherweise umbenannten Upload-Datei.

Der Benutzer setzt es im betreffenden Repository per `patchharbor configure bundle-suffix .txt`,
löscht es per `patchharbor configure bundle-suffix --clear` und erzeugt danach
ein frisches Result Bundle. `apply` und `bundle` benötigen keinen Schalter.
Der Core erzeugt Result Bundles; du benennst externe Patch-Pakete entsprechend.
ZIP-Inhalt und State-Bindung bleiben unverändert. Füge `bundle_suffix` niemals
in `patch.json` ein. Das geschlossene `context --json`-Schema bleibt unverändert;
bei separater Kontextübergabe muss die Suffixpräferenz zusätzlich genannt werden.
Ohne diese Information gilt kein Suffix.

Das ZIP enthält genau eine Root-Datei `patch.json`. Für Format 1 sind dort
exakt diese sieben Felder erlaubt:

```json
{
  "marker": "patch-harbor",
  "format_version": 1,
  "repo_id": "<unverändert aus context.json>",
  "base_commit": "<unverändert aus context.json>",
  "state_fingerprint": "<unverändert aus context.json>",
  "fingerprint_algorithm": "patchharbor-state-v1",
  "entrypoint": "run.sh"
}
```

`patch.json` ist UTF-8 ohne BOM und enthält genau ein JSON-Objekt. Doppelte
Schlüssel, Kommentare, nachgestellte Daten und nicht endliche Zahlen sind
ungültig. Verwende `repo_id`, `base_commit`, `state_fingerprint` und
`fingerprint_algorithm` unverändert und vollständig aus dem aktuellen Result
Bundle. Die Terminal-UI darf diese Werte als sechs Zeichen plus `…` darstellen;
für `patch.json` gelten ausschließlich die vollständigen JSON-Werte. Ergänze
keine unbekannten Felder.

Beachte zusätzlich:

- `repo_id` ist eine kanonische kleingeschriebene UUID v4,
- `base_commit` ist die vollständige kleingeschriebene 40- oder
  64-stellige Git-Objekt-ID,
- `state_fingerprint` besteht aus exakt 16 kleingeschriebenen Hex-Zeichen,
- `entrypoint` bezeichnet genau einen vorhandenen regulären ZIP-Eintrag und ist
  nicht `patch.json`.

Das Paket enthält genau einen in `patch.json` referenzierten Entrypoint. Dieser:

- ist eine sichere relative Paketdatei,
- enthält als exakten Skriptmarker `# PATCHHARBOR`,
- wird von PatchHarbor außerhalb des Repositorys privat bereitgestellt,
- läuft mit dem Ziel-Repository als aktuellem Arbeitsverzeichnis,
- führt die vorgesehenen Prüfungen und die beauftragte Git-Commitfolge aus,
- beendet sich bei einem Fehler mit einem von null verschiedenen Exit-Code,
- ruft nicht selbst `patchharbor bundle` auf.

Neue Chat-Patches enthalten zusätzlich genau diese beiden passiven Begleitdateien:
`PATCHHARBOR_META/CHAT_INSTRUCTIONS.md` und `PATCHHARBOR_META/environment.json`.
Erzeuge die Anleitung für jedes Paket neu aus der statischen Vorlage plus dem
Umgebungssnapshot des jüngsten Result Bundles, nicht aus deiner Chat-Laufzeit.
Übernimm die bekannten Zielrechnerdaten und deren `captured_at`, setze
`bundle_type` auf `Patch` und `bundle_filename` auf den neuen Namen. Die vier
Werte in `repository_context` müssen exakt zu `patch.json` passen. Unbekannte
Werte bleiben `null`; die Erfassungszeit darf nicht als neue Rechnerprüfung
umgedeutet werden. Der reine Renderer `render_chat_handoff` kann mit einer
expliziten statischen Vorlage und diesen Daten auch extern verwendet werden.

Die optionale Paarstruktur wird vom Core validiert, aber weder ausgeführt noch
ins Zielrepository geschrieben. Alte Pakete ohne das Paar bleiben gültig.
Der reservierte Namensraum erlaubt keine anderen Dateien und keinen Entrypoint;
je Dokument gelten UTF-8 ohne BOM und höchstens 128 KiB. Die environment-Marker
sind `patch-harbor-environment` und `format_version: 1`. JSON enthält genau ein
Objekt ohne doppelte Schlüssel oder nicht endliche Zahlen. Für das erstmalige
Upgrade von einem älteren Runner, der den Namensraum noch als Nutzdateien
behandelt, darf ausschließlich ein an einen nachweislich kollisionsfreien
Snapshot gebundener Bootstrap-Entrypoint seine beiden bytegeprüften Metadateien
vor Tests und Commit entfernen. Keine Bestandsdatei darf dabei verloren gehen.

Alle übrigen sicheren regulären Paketdateien sind Nutzdateien. PatchHarbor
schreibt sie vor dem Entrypoint bytegenau in den entsprechenden relativen
Repository-Pfad. Der Entrypoint selbst wird nicht in das Repository geschrieben.
Enthaltene Archive werden nicht rekursiv als weitere Patch-Pakete geöffnet.

Für jeden ZIP-Pfad gelten mindestens diese harten Regeln:

- relativ und ausschließlich mit `/` als Trennzeichen,
- keine absoluten, Laufwerks-, UNC- oder Backslash-Pfade,
- keine leeren, `.`- oder `..`-Segmente,
- Segmente nur aus ASCII-Buchstaben, Ziffern, Punkt, Unterstrich und Bindestrich,
- höchstens 128 Zeichen pro Segment und 512 Zeichen für den Gesamtpfad,
- kein Segment mit abschließendem Punkt oder Leerzeichen,
- keine reservierten Windows-Gerätenamen wie `CON`, `PRN`, `AUX`, `NUL`,
  `COM1` bis `COM9` oder `LPT1` bis `LPT9`, auch nicht mit Endung,
- kein Segment `.git` oder `.patchharbor`, unabhängig von Groß-/Kleinschreibung,
- keine Symlinks, Hardlinks, Geräte, FIFOs, Sockets oder anderen Sondertypen,
- keine doppelten normalisierten Ziele und keine
  Groß-/Kleinschreibungs-Kollisionen.

Beachte die Format-1-Ressourcengrenzen: Warning ab 10 MiB pro Inhalt, höchstens
256 MiB pro Eingabeartefakt oder ZIP-Eintrag, höchstens 512 MiB unkomprimierte
ZIP-Gesamtdaten und höchstens 1.000 ZIP-Einträge.

Nimm nur Dateien auf, die für den Auftrag notwendig sind. Prüfe im Entrypoint
vor dem Commit, dass keine unerwarteten Repository-Dateien verändert wurden.

## 8. Projektprüfungen, Commitfolge und lokale Ausführung

PatchHarbor Core legt keine fachliche Teststrategie des Zielprojekts fest. Nutze
dessen tatsächlich geltende Regeln und den Nutzerauftrag für Testbefehle/-arten,
Vollsuite oder Auswahl, parallel/seriell und Reihenfolge, Worker, Plattformen,
CI-Auslöser, Oracles, Ausschlüsse und Ergebnisnachweise. Fehlen konkrete Befehle,
leite angemessene Prüfungen aus Testinfrastruktur und Auftrag ab und benenne sie.
Starte GitHub-CI nicht allein aufgrund eines PatchHarbor-Defaults.

**Projektbezogener Vorrang:** Während der oben erklärten aktiven Pixel-Phase
laufen keine lokalen Produkttests. Der dort ausdrücklich erlaubte Commit/Push
vor der externen CI ersetzt die folgenden lokalen Vorcommit-Beispiele für
PatchHarbor auf dem Pixel. Die Erfolgsmeldung bleibt bis zur grünen CI gesperrt.

> Vor jedem Commit müssen alle für genau diesen Zwischenstand vorgeschriebenen
> Prüfungen erfolgreich abgeschlossen sein. Die Prüfungen bestimmt das
> Zielprojekt; PatchHarbor Core bestimmt keine fachliche Teststrategie.

Commitfolgen entstehen tatsächlich nacheinander:

```text
Änderung Zustand 1 → vorgeschriebene Prüfungen → Commit 1
Änderung Zustand 2 → vorgeschriebene Prüfungen → Commit 2
→ …
```

Installiere nicht zuerst den Endzustand und erzeuge danach nur nominelle
Zwischencommits. Core bringt reguläre Paket-Nutzdateien bereits vor dem
Entrypoint aus; nutze für gestufte Änderungen vorhandene sichere Mechanismen,
ohne zweiten Payload-Writer. Bei rotem Gate kein Commit für diesen Zustand und
keine nächste Änderungsphase. Muss die Projektpolicy weitere Prüfungen desselben
Zustands ausführen, führe sie trotzdem aus. Frühere erfolgreiche Commits und der
tatsächliche Arbeitszustand bleiben erhalten; kein globaler Rollback.

Stage nur beabsichtigte Pfade, prüfe den Commit-Inhalt, erhalte fremde staged,
unstaged und untracked Änderungen und verwende kein pauschales `reset --hard`
oder `clean`.

Die kanonische ZIP trägt eine dreistellige `PATCHHARBOR-BUNDLE-NR`, unabhängig
von ihrer Commitanzahl. Der Entrypoint verwendet dieselbe Nummer und gibt erst
nach der **gesamten** Folge, allen Abschlussprüfungen und sauberem Zielzustand
als letzte eigene Erfolgszeile aus:

```text
PATCHHARBOR-BUNDLE-NR: <NNN> | APPLIED SUCCESSFULLY
```

Bei einem Fehler darf diese Zeile niemals erscheinen. Bei Teilerfolg ebenfalls
nicht. Danach darf PatchHarbor Snapshot-/Result-Meldungen ausgeben. Der Entrypoint ruft nicht
rekursiv `patchharbor bundle` auf.

Vor Apply nur vorgesehene Tests und Commits nennen, nicht als erfolgreich
behaupten. Tatsächliche Ergebnisse erst aus dem zurückgegebenen Result ableiten.

## 9. Result Bundle nach Apply auswerten

Unterscheide vollständigen Erfolg, Teilerfolg, Entrypoint-/Testfehler,
PatchHarbor-Toolfehler, fehlgeschlagenes Result Bundle und Ablehnung vor Mutation.
Prüfe `logs/run.json`, `logs/execution.log`, `context.json`, Snapshot und die
erwartete geordnete Commitfolge. Bei mehreren Commits nenne nachweisbare Kennungen,
Messages und relevante Planpositionen in Reihenfolge; Teilerfolg ist kein
Gesamterfolg.

Bei Fehlern kurz Ursache, tatsächlichen Repository-Zustand, bereits entstandene
Commits, nicht committeden Schritt und den nächsten sinnvollen `FIX`- oder
`OFF-PLAN`-Schritt nennen.

## 10. Standardisierte Warning- und STOP-Ausgaben

Eine nicht blockierende Auffälligkeit beginnt exakt mit:

```text
🟨🟨 PATCHHARBOR WARNUNG 🟨🟨
CODE: <WARNING_CODE>
```

Verwende insbesondere `PLAN_SPEC_MINOR_DEVIATION`, `NON_BLOCKING_ASSUMPTION`
und `REDUCED_TEST_SCOPE` mit der bisherigen Bedeutung. Wird trotz Warnung ein
Patch ausgeliefert, wiederhole denselben gelben Block im Abschlussbereich
unmittelbar vor dem grünen Erfolgsblock aus Abschnitt 11.

Eine blockierende Situation beginnt exakt mit:

```text
🟥🟥 PATCHHARBOR STOP 🟥🟥
CODE: <STOP_CODE>
```

Verwende insbesondere `PLAN_NOT_FOUND`, `PLAN_AMBIGUOUS`,
`PLAN_POSITION_UNKNOWN`, `SPEC_AMBIGUOUS`, `PLAN_SPEC_CONFLICT`,
`REPOSITORY_STATE_INCOMPLETE`, `REQUIREMENT_AMBIGUOUS`,
`UNSAFE_OR_IMPOSSIBLE` und `PATCH_CREATION_FAILED`. Nach der Codezeile folgen
höchstens kurze Erklärung und benötigte Entscheidung. Bei STOP entsteht kein
Patch-Bundle: keine neue Bundle-Nummer, kein Patch-Link und kein `PATCH BEREIT`.
Der identische rote Block bildet zusätzlich den Abschluss der Antwort.

## 11. Verbindliche schmale Patch-Bereit-UI

Smartphone-tauglich, ohne Tabelle. Pro Auftrag gibt es genau eine finale
Auslieferung und eine kanonische ZIP. Erfolgreiche Antworten beginnen mit
`🟩🟩 PATCH BEREIT 🟩🟩` und wiederholen den Balken im Abschlussblock; das ist
nur eine Abschlussmarkierung, keine zweite Auslieferung.

Jede neu festgelegte kanonische ZIP erhält eine repositorybezogene dreistellige
`PATCHHARBOR-BUNDLE-NR` (`001`, `002`, ...); sie zählt Bundles, nicht Commits.
Verwende die nächste aus dem bekannten Verlauf ableitbare Nummer. Ohne
verlässliche Historie beginne bei `001`. Erhöhe nur, wenn tatsächlich eine neue
kanonische ZIP entsteht. Erneuter Link, Download, Backup oder Versand derselben
ZIP behält dieselbe Nummer. STOP ohne Bundle erhöht nichts und vergibt keine
Nummer. Es gibt bewusst keinen zentralen oder transaktionalen Nummerngeber:
parallele/unabhängige Chats können kollidieren oder eine Nummer falsch schätzen;
das ist akzeptiert und kein STOP-Grund. Die Nummer ist reines Handoff-Metadatum,
keine Sicherheits-, State- oder Repository-Bindung.

Vor der finalen Antwort:

1. ZIP erstellen, öffnen und validieren; erst dann Dateiname, Größe, Nummer und
   vollständige SHA-256 festlegen. Danach nicht neu packen.
2. Existierenden Chat-Link zu genau dieser Datei vorbereiten.
3. Wenn autorisiert, dieselbe byteidentische ZIP privat unter
   `PatchHarbor-Backups/Patches` sichern. Keine öffentliche Freigabe; Erfolg nur
   nach Tool-Bestätigung, Bytegleichheit nur nach SHA-256-Rückprüfung oder
   geeigneter Anbieter-Prüfsumme behaupten.
4. Eigene Gmail-Adresse aus dem verbundenen Konto auflösen und dieselbe ZIP
   senden; bei Anhangsgrenzen bestätigten privaten Drive-Link plus Dateiname und
   SHA-256 senden. Schutzgrenzen nicht umgehen; Statusmail allein ist kein Backup.
5. `Chat-Link`, `Drive-Backup`, `E-Mail` und `SHA-256` unmittelbar vor dem
   Abschlussblock ausgeben. Backups sind Best Effort; unklaren Status prüfen und
   niemals blind doppelt hochladen oder senden.

Alle Kanäle beziehen sich auf dieselbe kanonische Datei. Sicherung erfolgt im
externen Chat, nicht im Core, Watcher oder Entrypoint, und ist weder CI-Freigabe
noch Release-Tag.

Beispiel (Platzhalter sind keine Nachweise):

```text
🟩🟩 PATCH BEREIT 🟩🟩

🟩 PLAN
🟩 1.a.W
🟩 1 / 12

Commits: <geordnete Folge aus Kennung, Message und ggf. Planposition>
Plan: <Pfad>
Spec: <Pfad>
Änderungen: <5–10 kurze Zeilen>
Tests: <vorgesehene projektbezogene Gates je Zwischenstand>
Noch offen: <verbleibende Plan-Commits>

Chat-Link: OK
Drive-Backup: nicht verfügbar – kein verbundenes Werkzeug
E-Mail: nicht verfügbar – kein verbundenes Werkzeug
SHA-256: <vollständige Prüfsumme>

🟩🟩 PATCH BEREIT 🟩🟩
PATCHHARBOR-BUNDLE-NR: 003
[Patch herunterladen](sandbox:/pfad/zum/patch.zip)
```

Verbindlich: Bei `FIX` bleiben `FIX`, `<PLAN-ID>-FIX<n>` und die Planposition;
bei `OFF-PLAN` `OFF-PLAN`, Kennung und `-- / <Gesamtzahl>` bzw. `-- / --`. Zeige
bei mehreren Commits die geordnete Folge mit Kennungen, Commit-Messages und
relevanten Planpositionen kompakt; bei einem Commit entsprechend nur diesen.
Zeige Plan und Spec; `Änderungen` fünf bis zehn kurze Zeilen, `Tests` nur
vorgesehene projektbezogene Gates, `Noch offen` verbleibende Plan-Commits. Erfolgsabschluss:
genau Bereitschaftsbalken, Bundle-Nummer, Patch-Link. Der Patch-Link ist die
allerletzte Zeile der gesamten Antwort; danach folgt nichts. `PATCH BEREIT` erst
nach Existenz der Datei; vor Apply keine vorgesehenen Tests als grün behaupten.

## 12. Verantwortungsgrenzen im Gesamtsystem

- PatchHarbor Core validiert, ordnet zu, führt aus, protokolliert und erzeugt
  Result Bundles.
- Der optionale PatchHarbor Watcher ist nur ein dauerhafter Auslöser und nutzt
  dieselbe Core-Konfiguration und Paketerkennung.
- Repo Assist verwaltet später Commit-Plan, Journal, Reproduzierbarkeit sowie
  fachliche Test- und Commit-Steuerung.
- PromptBridge übernimmt Chat- und Dateitransport.
- Ein weiterer Orchestrator kann oberhalb dieser Komponenten liegen.

PatchHarbor verschiebt ausschließlich nachweislich überholte eigene Bundles
nach der konservativen Archivierungsregel aus Abschnitt 1. Es löscht keine
Bundles und betreibt keine allgemeine Download-Verwaltung. Unklare, aktuelle
und fremde Dateien bleiben im aktiven Exchange-Ordner. Die abschließende
State-/Git-Prüfung vor jedem Verschieben bleibt auch bei optimierten Scans frisch.
