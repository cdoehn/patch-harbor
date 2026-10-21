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
