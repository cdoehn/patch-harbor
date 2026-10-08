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
MAX_ENTRIES = 250_010  # 250,000 snapshot files plus at most ten auxiliary members.
MAX_PYZ = 16 * 1024 * 1024
MAX_METADATA = 128 * 1024
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


def _state(info):
    # Windows path stat exposes creation time as ctime, while fstat exposes
    # change time. Compare birth time across views and ctime within the handle.
    timestamp = info.st_birthtime_ns if _WINDOWS else info.st_ctime_ns
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, timestamp


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
        _require(_state(initial) == _state(before), 'input changed before capture')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        _require(len(raw) <= maximum and before.st_ctime_ns == after.st_ctime_ns
                 and _state(initial) == _state(before) == _state(after) == _state(path.lstat()),
                 'input changed during capture')
    return raw


def _directory_budget(raw):
    """Bound ZipFile's metadata allocation before opening the supplied archive."""
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
    _require(disk_count == count and 0 < count <= MAX_ENTRIES,
             f'ZIP entry limit exceeded: actual={count}, limit={MAX_ENTRIES}')
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
