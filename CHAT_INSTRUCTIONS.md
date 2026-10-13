# PatchHarbor 1.3.0 – Chat-Initialisierung

**Vertragsversion:** 1.3.0<br>
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
Ordner wählen. Der Watcher lädt bei jedem freigegebenen Core-Scan ihre lokalen Einstellungen,
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
Format bis zu einem gesonderten Upgrade. Der Bootstrap prüft die genaue
Anforderung der ausgewählten PYZ: unveränderte historische Artefakte benötigen
Python >=3.12; die neue geschlossene Variante verlangt >=3.10. Unbekannte oder
widersprüchliche Varianten sind Fehler. Der aktuelle Produktionswriter bleibt
bis zum gesonderten CP-03-Schritt bei >=3.12.
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
from contextlib import ExitStack
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
MAX_ENTRIES = 250_010  # 250,000 snapshot files plus at most ten auxiliary members.
MAX_PYZ = 16 * 1024 * 1024
MAX_METADATA = 128 * 1024
MAX_RECIPE = 1024 * 1024
MAX_INNER_TOTAL = 32 * 1024 * 1024
MAX_INNER_ENTRIES = 1000
RECIPE_PATH = 'patchharbor/_runtime/pyz-recipe.json'
MAIN_PATH = 'patchharbor/_runtime/pyz-main.py'
IDENTITY_PATH = 'patchharbor/_pyz_identity.py'
PYTHON_MINIMA = {'>=3.12': (3, 12), '>=3.10': (3, 10)}
RESOURCES = {'patchharbor/_runtime/CHAT_INSTRUCTIONS.md',
             'patchharbor/_runtime/python-api.md', 'patchharbor/_runtime/LICENSE', MAIN_PATH}
RECIPE_FIELDS = {'marker','format_version','distribution','version','requires_python','profile',
                 'content_id_algorithm','content_id','source_commit','entries'}
_WINDOWS = sys.platform == 'win32'
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


def _legacy_windows():
    return _WINDOWS and sys.version_info < (3, 12)


def _creation_time(info):
    birth = getattr(info, 'st_birthtime_ns', None)
    if birth is not None:
        return birth
    _require(_legacy_windows(), 'Windows creation-time metadata is unavailable')
    return info.st_ctime_ns


def _state(info):
    # Old Windows fstat's ctime is creation time, never a change-time proof.
    timestamp = _creation_time(info) if _WINDOWS else info.st_ctime_ns
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, timestamp


def _windows_times(descriptor):
    import ctypes
    from ctypes import wintypes
    import msvcrt
    class BasicInfo(ctypes.Structure):
        _fields_ = [('creation', ctypes.c_longlong), ('access', ctypes.c_longlong),
                    ('write', ctypes.c_longlong), ('change', ctypes.c_longlong),
                    ('attributes', wintypes.DWORD)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel.GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    query.restype = wintypes.BOOL
    info = BasicInfo()
    if not query(msvcrt.get_osfhandle(descriptor), 0, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    epoch = 11644473600 * 1_000_000_000
    return info.creation * 100 - epoch, info.write * 100 - epoch, info.change * 100 - epoch, info.attributes


@dataclass(frozen=True)
class _WindowsMetadata:
    original: object
    st_birthtime_ns: int
    st_ctime_ns: int

    def __getattr__(self, name):
        return getattr(self.original, name)


def _descriptor_info(descriptor):
    if not _legacy_windows():
        return os.fstat(descriptor)
    before = _windows_times(descriptor)
    info = os.fstat(descriptor)
    after = _windows_times(descriptor)
    _require(before == after and _creation_time(info) == after[0]
             and info.st_mtime_ns == after[1] and getattr(info, 'st_file_attributes', 0) == after[3],
             'Windows handle metadata changed during capture')
    return _WindowsMetadata(info, after[0], after[2])


def _regular(info):
    return stat.S_ISREG(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400


def _parent_states(path):
    parents = []
    for parent in reversed(Path(os.fspath(path)).absolute().parents):
        info = parent.lstat()
        _require(stat.S_ISDIR(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'linked or special parent directory')
        parents.append((parent, info.st_dev, info.st_ino))
    return parents


def _windows_open(path):
    import ctypes
    from ctypes import wintypes
    import msvcrt
    class AttributeTag(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    query = kernel.GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    query.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes, close.restype = [wintypes.HANDLE], wintypes.BOOL
    # READ, share READ/WRITE/DELETE, OPEN_EXISTING, OPEN_REPARSE_POINT.
    handle = create(os.fspath(path), 0x80000000, 7, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = AttributeTag()
        if not query(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        _require(not attributes.attributes & (0x400 | 0x10), 'opened reparse point or directory')
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handle = None  # CRT now owns the handle.
        return descriptor
    finally:
        if handle is not None:
            close(handle)


def _capture(path, maximum):
    """One stable, bounded, no-follow regular-file capture, with no retry."""
    parents = _parent_states(path)
    initial = path.lstat()
    _require(_regular(initial), 'linked or special input')
    descriptor = (_windows_open(path) if os.name == 'nt' else
                  os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)))
    try:
        os.set_inheritable(descriptor, False)
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            before = _descriptor_info(stream.fileno())
            _require(_regular(before) and before.st_size <= maximum, 'file type or size limit')
            _require(_state(initial) == _state(before), 'input changed before capture')
            raw = stream.read(maximum + 1)
            after = _descriptor_info(stream.fileno())
            final = path.lstat()
            _require(_regular(after) and _regular(final) and len(raw) <= maximum
                     and before.st_ctime_ns == after.st_ctime_ns
                     and _state(initial) == _state(before) == _state(after) == _state(final),
                     'input changed during capture')
        _require(_parent_states(path) == parents, 'input parent changed during capture')
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return raw


def _directory_budget(raw, *, maximum=None):
    """Bound ZipFile's metadata allocation before opening the supplied archive."""
    maximum = MAX_ENTRIES if maximum is None else maximum
    start = max(0, len(raw)-65557)
    position = raw.rfind(b'PK\x05\x06', start)
    _require(position >= 0 and position + 22 <= len(raw), 'missing ZIP boundary')
    _, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from('<4s4H2IH', raw, position)
    _require(disk == directory_disk == 0 and position + 22 + comment == len(raw),
             'ZIP boundary or unsupported multipart archive')
    directory_end = position
    if position >= 20 and raw[position-20:position-16] == b'PK\x06\x07':
        _, record_disk, record_offset, disks = struct.unpack_from('<4sLQL', raw, position-20)
        _require(record_disk == 0 and disks == 1 and 0 <= record_offset <= position-76,
                 'invalid ZIP64 locator')
        # Match the fixed ZIP64 record read by all supported Python versions.
        # PatchHarbor does not emit an extensible data sector.
        signature, record_size, made, needed, z_disk, z_directory_disk, z_disk_count, z_count, z_size, z_offset = struct.unpack_from('<4sQ2H2L4Q', raw, record_offset)
        _require(signature == b'PK\x06\x06' and record_size == 44
                 and record_offset + 12 + record_size == position-20
                 and z_disk == z_directory_disk == 0 and z_disk_count == z_count,
                 'invalid ZIP64 end record')
        _require(disk_count in (0xffff, z_disk_count) and count in (0xffff, z_count)
                 and size in (0xffffffff, z_size) and offset in (0xffffffff, z_offset),
                 'inconsistent ZIP64 directory facts')
        count, disk_count, size, offset = z_count, z_disk_count, z_size, z_offset
        directory_end = record_offset
    _require(disk_count == count and 0 < count <= maximum,
             f'ZIP entry limit exceeded: actual={count}, limit={maximum}')
    _require(offset + size == directory_end,
             'ZIP directory boundary mismatch')
    cursor = offset
    for _ in range(count):
        _require(cursor + 46 <= directory_end and raw[cursor:cursor+4] == b'PK\x01\x02', 'ZIP directory mismatch')
        name, extra, note = struct.unpack_from('<3H', raw, cursor+28)
        _require(0 < name <= 4096, 'ZIP member name budget')
        cursor += 46 + name + extra + note
    _require(cursor == directory_end, 'ZIP directory count mismatch')


def _members(archive):
    infos = archive.infolist()
    _require(len(infos) <= MAX_ENTRIES,
             f'ZIP entry limit exceeded: actual={len(infos)}, limit={MAX_ENTRIES}')
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


def _minimum(requires):
    _require(type(requires) is str and requires in PYTHON_MINIMA, 'unsupported PYZ Python requirement')
    return PYTHON_MINIMA[requires]


def _main_bytes(requires):
    major, minor = _minimum(requires)
    return ('''"""PatchHarbor Core ZIP application; no Watcher launcher."""
import sys

if sys.version_info < (%d, %d):
    sys.stderr.write("PatchHarbor requires Python %d.%d or newer.\\n")
    raise SystemExit(2)

from patchharbor.cli import main
raise SystemExit(main())
''' % (major, minor, major, minor)).encode('ascii')


def _canonical(document):
    return (json.dumps(document, sort_keys=True, ensure_ascii=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')


def _pyz_path(name):
    _require(type(name) is str and 0 < len(name) <= 512, 'invalid PYZ path')
    parts = name.split('/')
    for part in parts:
        _require(0 < len(part) <= 128 and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', part)
                 and part not in {'.', '..'} and not part.endswith('.'), 'unsafe PYZ path segment')
        stem = part.split('.')[0].upper()
        _require(stem not in {'CON','PRN','AUX','NUL'} and not re.fullmatch(r'(COM|LPT)[1-9]', stem),
                 'device PYZ path')
    if name == '__main__.py':
        return name
    _require(parts[0] == 'patchharbor' and len(parts) > 1, 'foreign PYZ namespace')
    if name.startswith('patchharbor/_runtime/'):
        _require(name in RESOURCES, 'unlisted PYZ resource')
    else:
        _require(name != 'patchharbor/_runtime_identity.py' and '__pycache__' not in parts
                 and parts[-1] not in {'sitecustomize.py','usercustomize.py'}, 'unsupported PYZ startup member')
        _require(name == 'patchharbor/py.typed' or (name.endswith('.py') and all(
            re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', p) for p in [*parts[1:-1], parts[-1][:-3]])),
            'unsupported PYZ member')
    return name


def _pyz_precheck(raw, expected, remaining=MAX_INNER_TOTAL):
    """Check the inner inventory and closed start variant without importing it.

    This is still not native validation of the surrounding repository Result.
    Its separate outer and inner budgets must both hold before code can run.
    """
    _require(0 < len(raw) <= MAX_PYZ, 'PYZ artifact byte budget')
    _directory_budget(raw, maximum=MAX_INNER_ENTRIES)
    with ZipFile(BytesIO(raw)) as archive:
        names = _members(archive)
        infos = archive.infolist()
        _require(sum(i.file_size for i in infos) <= min(MAX_INNER_TOTAL, remaining), 'shared PYZ byte budget')
        _require(not archive.comment and [i.filename for i in infos] == sorted(names), 'noncanonical PYZ order')
        offset = 0
        for info in infos:
            _require(info.filename.isascii() and info.compress_type == ZIP_STORED and info.file_size == info.compress_size
                     and info.create_system == 3 and info.create_version == info.extract_version == 20
                     and info.date_time == (1980,1,1,0,0,0) and info.external_attr == 0o100644 << 16
                     and info.internal_attr == info.flag_bits == info.volume == info.reserved == 0
                     and not info.extra and not info.comment and info.header_offset == offset,
                     'noncanonical PYZ ZIP member')
            header = info.FileHeader(zip64=False)
            _require(raw[offset:offset+len(header)] == header, 'inconsistent PYZ local header')
            offset += len(header) + info.file_size
        _require(len(raw) == offset + sum(46 + len(i.filename) for i in infos) + 22,
                 'noncanonical PYZ directory size')
        recipe_raw = _read(archive, RECIPE_PATH, MAX_RECIPE)
        recipe = _json(recipe_raw)
        _require(set(recipe) == RECIPE_FIELDS and recipe['marker'] == 'patch-harbor-pyz-recipe'
                 and type(recipe['format_version']) is int and recipe['format_version'] == 1
                 and recipe['distribution'] == 'patchharbor' and recipe['profile'] == 'patchharbor-core-no-watcher-v1'
                 and recipe['content_id_algorithm'] == 'patchharbor-pyz-content-v1', 'unsupported PYZ recipe')
        _require(type(recipe['version']) is str and VERSION.fullmatch(recipe['version']), 'invalid PYZ version')
        main = _main_bytes(recipe['requires_python'])
        commit = recipe['source_commit']
        _require(commit is None or (type(commit) is str and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit)),
                 'invalid PYZ source commit')
        _require(all(recipe[key] == value for key, value in expected.items()), 'runtime/recipe disagreement')
        _require(type(recipe['content_id']) is str and HEX.fullmatch(recipe['content_id'])
                 and sha256(_canonical({k:v for k,v in recipe.items() if k != 'content_id'})).hexdigest() == recipe['content_id']
                 and _canonical(recipe) == recipe_raw, 'PYZ content identity or encoding mismatch')
        entries = recipe['entries']
        _require(type(entries) is list and len(entries)+1 == len(infos), 'PYZ inventory count')
        inventory, folded, directories = {}, set(), {}
        for entry in entries:
            _require(type(entry) is dict and set(entry) == {'path','source','size','sha256'}, 'PYZ entry schema')
            name, source = _pyz_path(entry['path']), _pyz_path(entry['source'])
            _require(source == (MAIN_PATH if name == '__main__.py' else name), 'PYZ source mapping')
            _require(name.casefold() not in folded, 'duplicate PYZ path')
            folded.add(name.casefold())
            _require(type(entry['size']) is int and entry['size'] >= 0 and type(entry['sha256']) is str
                     and HEX.fullmatch(entry['sha256']), 'PYZ entry size/hash')
            data = _read(archive, name, min(entry['size'], MAX_INNER_TOTAL))
            _require(len(data) == entry['size'] and sha256(data).hexdigest() == entry['sha256'], 'PYZ entry bytes/hash')
            inventory[name] = entry
            parts = name.split('/')
            for index in range(1, len(parts)):
                parent = '/'.join(parts[:index])
                _require(directories.setdefault(parent.casefold(), parent) == parent, 'case-ambiguous PYZ directory')
        _require(list(inventory) == sorted(inventory) and set(inventory) | {RECIPE_PATH} == names,
                 'PYZ inventory differs from archive')
        _require(not (folded & set(directories)), 'PYZ file/directory collision')
        required = RESOURCES | {IDENTITY_PATH,'__main__.py','patchharbor/__init__.py',
                                'patchharbor/api.py','patchharbor/cli.py','patchharbor/py.typed'}
        _require(required <= inventory.keys(), 'incomplete PYZ inventory')
        for name in ('__main__.py', MAIN_PATH):
            _require(_read(archive, name, len(main)) == main, 'PYZ start bytes disagree with Python requirement')
        producer = dict(algorithm='patchharbor-pyz-producer-v1', version=recipe['version'],
                        requires_python=recipe['requires_python'], profile=recipe['profile'],
                        source_commit=commit, entries=[e for e in entries if e['path'] != IDENTITY_PATH])
        identity = ('# Generated for the PatchHarbor PYZ profile.\nRESOURCE_ID = "' +
                    sha256(_canonical(producer)).hexdigest() + '"\n').encode('ascii')
        _require(_read(archive, IDENTITY_PATH, len(identity)) == identity, 'PYZ producer identity mismatch')
        for name in RESOURCES - {MAIN_PATH}:
            data = _read(archive, name, MAX_METADATA)
            _require(data and not data.startswith(b'\xef\xbb\xbf'), 'invalid PYZ document resource')
            data.decode('utf-8')
    return recipe


@dataclass(frozen=True)
class PyzAssessment:
    reference: Path
    reference_sha256: str
    artifact_name: str
    artifact_sha256: str
    version: str
    requires_python: str
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
        version, requires = metadata.get('version'), metadata.get('requires_python')
        _require(version is None or (type(version) is str and VERSION.fullmatch(version)), 'runtime version profile')
        if requires is not None:
            _minimum(requires)
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
        _require(type(version) is str and VERSION.fullmatch(version), 'runtime version profile')
        _minimum(requires)
        name = 'patchharbor-' + version + '.pyz'
        _require(artifact['path'] == 'runtime/' + name
                 and runtime_names == {'runtime/runtime.json', artifact['path']}, 'runtime member selection')
        _require(metadata.get('profile') == 'patchharbor-core-no-watcher-v1'
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
        _pyz_precheck(artifact_bytes, dict(version=version, requires_python=requires,
                      content_id=metadata['content_id'], source_commit=commit),
                      MAX_TOTAL - sum(i.file_size for i in archive.infolist()))
    return PyzAssessment(path, digest, name, artifact['sha256'], version, requires, artifact_bytes,
                         trusted_source_sha256 is not None)


@dataclass(frozen=True)
class PreparedPyz:
    assessment: PyzAssessment
    path: Path


# Same reviewed atomic DACL creation as the Core; bootstrap cannot import it.
def _windows_create_private_directory(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", ctypes.c_void_p),
                    ("inherit", wintypes.BOOL)]

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [("sid", ctypes.c_void_p), ("attributes", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)

    def function(library, name, result, args):
        fn = getattr(library, name)
        fn.restype, fn.argtypes = result, args
        return fn

    close = function(kernel, "CloseHandle", wintypes.BOOL, [wintypes.HANDLE])
    free = function(kernel, "LocalFree", ctypes.c_void_p, [ctypes.c_void_p])
    thread = function(kernel, "GetCurrentThread", wintypes.HANDLE, [])
    process = function(kernel, "GetCurrentProcess", wintypes.HANDLE, [])
    open_thread = function(security, "OpenThreadToken", wintypes.BOOL,
                           [wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER(wintypes.HANDLE)])
    open_process = function(security, "OpenProcessToken", wintypes.BOOL,
                            [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)])
    token_info = function(security, "GetTokenInformation", wintypes.BOOL,
                          [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                           ctypes.POINTER(wintypes.DWORD)])
    sid_text = function(security, "ConvertSidToStringSidW", wintypes.BOOL,
                        [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)])
    convert = function(security, "ConvertStringSecurityDescriptorToSecurityDescriptorW", wintypes.BOOL,
                       [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
                        ctypes.POINTER(wintypes.DWORD)])
    create = function(kernel, "CreateDirectoryW", wintypes.BOOL,
                      [wintypes.LPCWSTR, ctypes.POINTER(SecurityAttributes)])
    with ExitStack() as stack:
        token = wintypes.HANDLE()
        if not open_thread(thread(), 0x8, True, ctypes.byref(token)):  # TOKEN_QUERY
            if ctypes.get_last_error() != 1008:  # ERROR_NO_TOKEN only
                raise ctypes.WinError(ctypes.get_last_error())
            if not open_process(process(), 0x8, ctypes.byref(token)):
                raise ctypes.WinError(ctypes.get_last_error())
        stack.callback(close, token)
        size = wintypes.DWORD()
        if token_info(token, 1, None, 0, ctypes.byref(size)) or ctypes.get_last_error() != 122:
            raise ctypes.WinError(ctypes.get_last_error())  # ERROR_INSUFFICIENT_BUFFER
        buffer = ctypes.create_string_buffer(size.value)
        if not token_info(token, 1, buffer, size, ctypes.byref(size)):  # TokenUser
            raise ctypes.WinError(ctypes.get_last_error())
        user = SidAndAttributes.from_buffer(buffer)
        sid = wintypes.LPWSTR()
        if not sid_text(user.sid, ctypes.byref(sid)):
            raise ctypes.WinError(ctypes.get_last_error())
        stack.callback(free, sid)
        # Protected DACL; only this effective user and administrators, inherited
        # by files/subdirectories. No permissive-create / later chmod interval.
        sddl = "D:P(A;OICI;FA;;;" + sid.value + ")(A;OICI;FA;;;BA)"
        descriptor = ctypes.c_void_p()
        if not convert(sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        stack.callback(free, descriptor)
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        if not create(str(path), ctypes.byref(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())


def prepare(assessment, workspace):
    """Copy exactly one verified artifact into a new private directory; no install."""
    if not assessment.source_trusted:
        raise BootstrapUnavailable('runtime source is not trusted')
    minimum = _minimum(assessment.requires_python)
    if sys.version_info < minimum:
        raise BootstrapUnavailable('Python %d.%d or newer is required by this artifact' % minimum)
    _require(sha256(assessment.pyz_bytes).hexdigest() == assessment.artifact_sha256
             and 0 < len(assessment.pyz_bytes) <= MAX_PYZ, 'captured PYZ bytes changed')
    _require(assessment.artifact_name == 'patchharbor-' + assessment.version + '.pyz'
             and VERSION.fullmatch(assessment.version), 'artifact name changed')
    _pyz_precheck(assessment.pyz_bytes, dict(version=assessment.version, requires_python=assessment.requires_python))
    workspace = Path(workspace).absolute()
    parents = _parent_states(workspace)
    if os.name == 'nt':
        _windows_create_private_directory(workspace)
    else:
        workspace.mkdir(mode=0o700)  # existing destinations and symlinks are refused
    _require(_parent_states(workspace) == parents, 'workspace parent changed during creation')
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
    assessment, path = prepared.assessment, prepared.path
    minimum = _minimum(assessment.requires_python)
    if sys.version_info < minimum:
        raise BootstrapUnavailable('Python %d.%d or newer is required by this artifact' % minimum)
    if not assessment.source_trusted:
        raise BootstrapUnavailable('runtime source is not trusted')
    _require(sha256(_capture(path, MAX_PYZ)).hexdigest() == assessment.artifact_sha256,
             'prepared PYZ changed before import')
    _pyz_precheck(assessment.pyz_bytes, dict(version=assessment.version, requires_python=assessment.requires_python))
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
                  artifact_sha256=assessment.artifact_sha256, version=assessment.version,
                  requires_python=assessment.requires_python)
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

### Legacy-Result 2: geprüftes Wheel und bisheriger Übergabeweg

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

Für die Entwicklung von **PatchHarbor selbst** gilt für den ausdrücklich
beauftragten CPython-3.10/3.11-Auftrag konkret:

```text
Plan: planning/python-compatibility/commit-plan.md
Normsatz: spec/SPECIFICATION.md
          spec/SPECIFICATION_EXTENSION_PYZ_PACK.md (Revision 4)
          spec/SPECIFICATION_EXTENSION_CPYTHON_310_311.md (Revision 1)
```

Der frühere PYZ/PACK-Plan ist mit 16/16 Positionen, Korrektur 046 und grüner
manueller CI auf `30e5de1d67a2d725ff192a0b97e50c2b0336bfcb` abgeschlossen.
Die Basisversion bleibt 1.3.0; die neue Releaseversion wird gesondert festgelegt.
Keine Versionsnummer reaktiviert einen historischen Versions-, RIV-, Watcher-
oder PYZ/PACK-Plan. Der neue Normsatz ändert nur seine ausdrücklich benannten
Python-Anforderungen. Diese Projektzuordnung gilt nicht pauschal für andere
Repositorys, denen PatchHarbor dieselbe generische Vorlage mitliefert.

**Aktueller Implementierungsschritt:** CP-00 und CP-01 sind durch tatsächliche
Applies bestätigt. CP-02 erweitert Datenleser und das ausführbare Bootstrapprogramm
oben auf beide geschlossenen PYZ-Varianten. Der normale Writer, Paketversion und
Python-Metadaten bleiben bis CP-03 bei der bisherigen 3.12-Anforderung.
Python 3.10/3.11 sind weiterhin Ziele, noch kein vollständig bestätigter Support.
Prüfe stets den gelieferten Resultstand: Eine alte globale Installation wird
durch eine Quelländerung nicht automatisch ersetzt.

**Historie:** Die einmalige CI-only-Ausnahme für PP-00 / Bundles 024/025
ist mit dessen erfolgreichem Abschluss erfüllt. Result
`patch-harbor_Result_141601_1007_ef9735.zip` belegt Commit
`7a28bbc2189cdb2a78590e62a45e4d96b0ff893d` und sechs grüne Jobs in CI-Run
`37635401106`. Bundle 026 startete danach lokale PP-01-Tests. Diese wurden laut
`patch-harbor_Result_160403_1007_ee4cb0.zip` vor Staging/Commit/Push/CI
unterbrochen; damals waren die PP-01-Dateien vorhanden und uncommitted. Das ist kein
bestandener PP-01-Testlauf. Bundle 027 / PP-01-FIX1 setzt diese Änderungen fort.

### PatchHarbor-Projekt: aktive Laptop-Phase

Dieser Abschnitt gilt nur für die ausdrücklich beauftragte Entwicklung von
PatchHarbor selbst. Andere Zielprojekte behalten ihre eigenen Test-/CI-Regeln.

Die spätere ausdrückliche Nutzeranweisung vom 7. Oktober 2026 ersetzt ältere
lokale serielle Gates, die Pixel-CI-only-Regel und den CI-Fünfertakt.
Development und Apply prüfen jeden Commitstand vollständig parallel, auch am
Bundle-Ende. Kein serieller Lauf und keine verkürzte Auswahl als Vollabnahme.
Nur Christian startet den manuellen CI-Workflow; Codex und Entrypoints tun das nie.

Der aktuelle Folgeauftrag umfasst genau das Reader-/Bootstrap-Bundle CP-02.
Er startet keine dauerhafte Schleife und autorisiert keine sofortige Umsetzung
von CP-03 bis CP-05. Eine später ausdrücklich beauftragte Fortsetzung wertet vollständige
Watcher-Results samt Teilfortschritten aus. Sicherheitsgrenzen und belastbare
Resultbindung bleiben Voraussetzung; Tokenmeter bleibt gestoppt.

Development bleibt ausschließlich in `patchharbor-codex`. Nur die fertig und
vollständig geprüfte kanonische Patch-ZIP gelangt atomar in den Exchange.
Der bereits laufende Watcher übernimmt allein den Apply. Keine direkten
Development-Commits, Apply-Mutationen, Hook-Umgehungen oder Watcher-Neustarts.
Nach erfolgreichen Commit-Gates genau ein normaler Push; kein automatisches Tag.

Die frühere 1.3.0-Abnahme einschließlich Christians CIFS-Praxisbestätigung
belegt nicht automatisch den neuen CPython-Auftrag. Dessen Abnahme benötigt
echte 3.10-/3.11-Interpreter, passende Artefakte, tatsächliche Applies und die
von Christian gestartete erweiterte native CI. Die Anforderungen und offenen
Nachweise stehen im neuen Plan. Eine ältere globale Installation wird durch
diesen Quellpatch nicht aktualisiert.

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

Verwende mit einer nutzbaren aktuellen Runtime `pack` beziehungsweise
`api.pack_patch` für den bewusst vorbereiteten Inhaltsordner, genau das geprüfte
Result, einen Entrypoint und einen expliziten vorhandenen Ausgabeordner außerhalb
der Inhalte. Pack erzeugt Manifest und frische Begleitdaten selbst und validiert
die tatsächlich geschriebenen Bytes gegen diese Referenz. Es führt keine Tests,
Skripte oder Commits aus. Die folgenden Formatregeln bleiben auch für den
technischen Altweg verbindlich; fachliche Ablehnungen sind kein Fallbackgrund.

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
ZIP-Gesamtdaten und höchstens 250.010 ZIP-Einträge im äußeren Archiv. Result-Snapshots
enthalten höchstens 250.000 Dateien aus Base und Untracked zusammen; die
zusätzlichen zehn Plätze sind für Begleitdaten reserviert. Innere
Runtime-Archive bleiben auf 1.000 Einträge begrenzt.

Nimm nur Dateien auf, die für den Auftrag notwendig sind. Prüfe im Entrypoint
vor dem Commit, dass keine unerwarteten Repository-Dateien verändert wurden.

## 8. Projektprüfungen, Commitfolge und lokale Ausführung

PatchHarbor Core legt keine fachliche Teststrategie des Zielprojekts fest. Nutze
dessen tatsächlich geltende Regeln und den Nutzerauftrag für Testbefehle/-arten,
Vollsuite oder Auswahl, parallel/seriell und Reihenfolge, Worker, Plattformen,
CI-Auslöser, Oracles, Ausschlüsse und Ergebnisnachweise. Fehlen konkrete Befehle,
leite angemessene Prüfungen aus Testinfrastruktur und Auftrag ab und benenne sie.
Starte GitHub-CI nicht allein aufgrund eines PatchHarbor-Defaults.

**PatchHarbor-Projekt:** Für die aktive Laptop-Entwicklung gelten die oben
festgehaltenen vollständigen parallelen Commit-Gates. Die frühere Pixel-CI-only-
Ausnahme ist beendet. Externe CI startet ausschließlich der Nutzer; notwendige
native Abschlussnachweise bleiben bis zur tatsächlichen Auswertung offen.

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
4. Nur bei autorisiertem Versand die eigene Gmail-Adresse aus dem verbundenen
   Konto auflösen und dieselbe ZIP senden; bei Anhangsgrenzen bestätigten privaten Drive-Link plus Dateiname und
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
