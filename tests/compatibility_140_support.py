"""Byte-pinned historical artifacts and independent stdlib-only test helpers."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile


FIXTURES = Path(__file__).parent / 'fixtures' / 'compatibility_140'
PROVENANCE_SHA256 = '6cd32c3a06b978179b331a8f1c63001da47c08ac1db6784a15151e3a962993c8'
PYZ_SHA256 = '4e0d26997bffe9476e79d98211cef2d93be7899063a0eb3480bea2ffa3d8f594'
RESULT_CASES = ('clean', 'diagnostic', 'single', 'multi', 'dry-run', 'partial-failure', 'dirty', 'unavailable')
PATCH_CASES = ('diagnostic', 'single', 'multi', 'dry-run', 'partial-failure')
BINDING_FIELDS = ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def provenance():
    raw = (FIXTURES / 'provenance.json').read_bytes()
    assert sha256(raw) == PROVENANCE_SHA256, 'frozen provenance changed'
    return json.loads(raw)


def artifact(kind, case):
    assert kind in ('result', 'patch')
    facts = provenance()['results' if kind == 'result' else 'patches'][case]
    path = FIXTURES / (kind + '-' + case + '.zip')
    raw = path.read_bytes()
    assert len(raw) == facts['bytes'] and sha256(raw) == facts['sha256'], path
    return path, facts


def prepared_pyz(directory):
    # Execute only the exact, reviewed original, never a modified negative fixture.
    source, _ = artifact('result', 'clean')
    with ZipFile(source) as archive:
        raw = archive.read('runtime/patchharbor-1.4.0.pyz')
    assert sha256(raw) == PYZ_SHA256
    directory.mkdir()
    path = directory / 'patchharbor-1.4.0.pyz'
    path.write_bytes(raw)
    return path


def rewrite_zip(original, destination, changes):
    """Produce a deliberately altered copy; original fixture bytes stay untouched."""
    with ZipFile(original) as archive:
        records = [(entry, archive.read(entry)) for entry in archive.infolist()]
    with ZipFile(destination, 'w') as archive:
        for entry, raw in records:
            archive.writestr(entry, changes.get(entry.filename, raw))


def json_bytes(document):
    return (json.dumps(document, sort_keys=True, separators=(',', ':')) + '\n').encode()


def corrupt_reference(original, destination, fault):
    with ZipFile(original) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        runtime = json.loads(archive.read('runtime/runtime.json'))
        changes = {}
        if fault == 'snapshot':
            changes['base/tracked.txt'] = archive.read('base/tracked.txt') + b'changed'
        elif fault == 'future_result':
            manifest['format_version'] = 99
        elif fault == 'future_runtime':
            runtime['format_version'] = 99
        elif fault == 'capabilities':
            runtime['capabilities']['result_formats'] = [1, 2, 3, 99]
        elif fault == 'runtime_bytes':
            changes[runtime['artifact']['path']] = b'not a PYZ'
        else:
            raise AssertionError(fault)
        if fault in ('future_runtime', 'capabilities'):
            raw = json_bytes(runtime)
            changes['runtime/runtime.json'] = raw
            manifest['runtime']['metadata'].update(size=len(raw), sha256=sha256(raw))
        changes['manifest.json'] = json_bytes(manifest)
    rewrite_zip(original, destination, changes)


def result_members(case):
    path, _ = artifact('result', case)
    with ZipFile(BytesIO(path.read_bytes())) as archive:
        return {name: archive.read(name) for name in archive.namelist()}
