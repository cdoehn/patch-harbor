"""Closed Core-only PYZ recipe and deterministic data materialization.

No described Python code is imported or executed by these profile validators.
Relative imports allow the build backend to load these same anchored data helpers
in a private package namespace, without importing an installed PatchHarbor.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import re
from typing import Callable, Mapping
from zipfile import BadZipFile, ZIP_STORED, ZipFile, ZipInfo

from .runtime_wheel import (
    RuntimeDataError, RuntimeLimitError, RuntimeEntry, recipe_json, sha256,
    _require, _unique, _constant, _HEX, _VERSION, _SEGMENT, CHAT_PATH, DOC_PATH,
)
from .runtime_zip import bounded_directory


PROFILE = 'patchharbor-core-no-watcher-v1'
CONTENT_ALGORITHM = 'patchharbor-pyz-content-v1'
PRODUCER_ALGORITHM = 'patchharbor-pyz-producer-v1'
RECIPE_PATH = 'patchharbor/_runtime/pyz-recipe.json'
IDENTITY_PATH = 'patchharbor/_pyz_identity.py'
RESOURCE_ROOT = 'patchharbor/_runtime/'
LICENSE_PATH = RESOURCE_ROOT + 'LICENSE'
MAIN_PATH = RESOURCE_ROOT + 'pyz-main.py'
MAX_RECIPE_BYTES = 1024 * 1024
MAX_PYZ_BYTES = 16 * 1024 * 1024
MAX_CONTENT_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 1000
RESOURCES = frozenset({CHAT_PATH, DOC_PATH, LICENSE_PATH, MAIN_PATH})
FIELDS = frozenset({'marker', 'format_version', 'distribution', 'version', 'requires_python',
                   'profile', 'content_id_algorithm', 'content_id', 'source_commit', 'entries'})
REQUIRED = RESOURCES | {IDENTITY_PATH, '__main__.py', 'patchharbor/__init__.py',
                       'patchharbor/api.py', 'patchharbor/cli.py', 'patchharbor/py.typed'}
MAIN_BYTES = b'''"""PatchHarbor Core ZIP application; no Watcher launcher."""
import sys

if sys.version_info < (3, 12):
    sys.stderr.write("PatchHarbor requires Python 3.12 or newer.\\n")
    raise SystemExit(2)

from patchharbor.cli import main
raise SystemExit(main())
'''


@dataclass(frozen=True, slots=True)
class PyzRecipe:
    version: str
    requires_python: str
    content_id: str
    source_commit: str | None
    entries: tuple[RuntimeEntry, ...]
    data: bytes

    @property
    def pyz_name(self) -> str:
        return f'patchharbor-{self.version}.pyz'


def _path(value: object) -> str:
    _require(type(value) is str and 0 < len(value) <= 512, 'invalid PYZ path')
    parts = value.split('/')
    for part in parts:
        _require(len(part) <= 128 and _SEGMENT.fullmatch(part) is not None and not part.endswith('.'),
                 'unsafe PYZ path segment')
        stem = part.split('.')[0].upper()
        _require(stem not in {'CON', 'PRN', 'AUX', 'NUL'}
                 and not re.fullmatch(r'(?:COM|LPT)[1-9]', stem), 'device PYZ path')
    if value == '__main__.py':
        return value
    _require(parts[0] == 'patchharbor' and len(parts) > 1, 'foreign PYZ namespace')
    if value.startswith(RESOURCE_ROOT):
        _require(value in RESOURCES, 'unlisted PYZ resource')
    else:
        _require(value != 'patchharbor/_runtime_identity.py', 'legacy generated identity in PYZ')
        _require(value == 'patchharbor/py.typed' or (value.endswith('.py')
                 and all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', p)
                         for p in [*parts[1:-1], parts[-1][:-3]])), 'unsupported PYZ member')
        _require('__pycache__' not in parts and parts[-1] not in {'sitecustomize.py', 'usercustomize.py'},
                 'startup hook or bytecode in PYZ')
    return value


def parse_recipe(raw: bytes) -> PyzRecipe:
    if len(raw) > MAX_RECIPE_BYTES:
        raise RuntimeLimitError('PYZ recipe exceeds budget')
    try:
        doc = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise RuntimeDataError('invalid PYZ recipe JSON') from exc
    _require(type(doc) is dict and set(doc) == FIELDS, 'invalid PYZ recipe schema')
    _require(doc['marker'] == 'patch-harbor-pyz-recipe' and type(doc['format_version']) is int
             and doc['format_version'] == 1 and doc['distribution'] == 'patchharbor'
             and doc['profile'] == PROFILE and doc['content_id_algorithm'] == CONTENT_ALGORITHM,
             'unsupported PYZ recipe')
    version, requires, commit = doc['version'], doc['requires_python'], doc['source_commit']
    _require(type(version) is str and _VERSION.fullmatch(version) is not None, 'invalid PYZ version')
    _require(requires == '>=3.12', 'unsupported PYZ Python requirement')
    _require(commit is None or (type(commit) is str and re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit)),
             'invalid PYZ source provenance')
    _require(type(doc['content_id']) is str and _HEX.fullmatch(doc['content_id']) is not None, 'invalid PYZ content ID')
    _require(type(doc['entries']) is list, 'invalid PYZ inventory')
    if len(doc['entries']) + 1 > MAX_ENTRIES:
        raise RuntimeLimitError('PYZ inventory exceeds budget')
    entries, names, directories = [], set(), {}
    total = len(raw)
    for item in doc['entries']:
        _require(type(item) is dict and set(item) == {'path', 'source', 'size', 'sha256'}, 'invalid PYZ entry schema')
        name, source = _path(item['path']), _path(item['source'])
        _require(source == (MAIN_PATH if name == '__main__.py' else name), 'invalid PYZ source mapping')
        _require(name.casefold() not in names, 'duplicate PYZ path')
        names.add(name.casefold())
        parts = name.split('/')
        for i in range(1, len(parts)):
            parent = '/'.join(parts[:i])
            _require(directories.setdefault(parent.casefold(), parent) == parent, 'case-ambiguous PYZ directory')
        size, digest = item['size'], item['sha256']
        _require(type(size) is int and size >= 0 and type(digest) is str and _HEX.fullmatch(digest) is not None,
                 'invalid PYZ size or digest')
        total += size
        if total > MAX_CONTENT_BYTES:
            raise RuntimeLimitError('PYZ content exceeds budget')
        entries.append(RuntimeEntry(name, source, size, digest))
    _require([e.path for e in entries] == sorted(e.path for e in entries), 'noncanonical PYZ inventory order')
    inventory = {e.path: e for e in entries}
    _require(REQUIRED <= inventory.keys(), 'incomplete PYZ inventory')
    for entry in entries:
        source = inventory.get(entry.source)
        _require(source is not None and (source.size, source.sha256) == (entry.size, entry.sha256),
                 'inconsistent PYZ entrypoint resource')
        for i in range(1, len(entry.path.split('/'))):
            _require('/'.join(entry.path.split('/')[:i]).casefold() not in names, 'PYZ file/directory collision')
    unsigned = {k: v for k, v in doc.items() if k != 'content_id'}
    _require(sha256(recipe_json(unsigned)) == doc['content_id'] and recipe_json(doc) == raw,
             'PYZ content ID or canonical encoding mismatch')
    return PyzRecipe(version, requires, doc['content_id'], commit, tuple(entries), raw)


def producer_id(recipe: PyzRecipe) -> str:
    return sha256(recipe_json({
        'algorithm': PRODUCER_ALGORITHM, 'version': recipe.version,
        'requires_python': recipe.requires_python, 'profile': PROFILE,
        'source_commit': recipe.source_commit,
        'entries': [dict(path=e.path, source=e.source, size=e.size, sha256=e.sha256)
                    for e in recipe.entries if e.path != IDENTITY_PATH],
    }))


def identity_module(resource_id: str) -> bytes:
    _require(type(resource_id) is str and _HEX.fullmatch(resource_id) is not None, 'invalid PYZ producer ID')
    return ('# Generated for the PatchHarbor PYZ profile.\nRESOURCE_ID = "' + resource_id + '"\n').encode('ascii')


def create_recipe(payloads: Mapping[str, bytes], *, version: str, requires_python: str,
                  source_commit: str | None = None) -> tuple[PyzRecipe, bytes]:
    """Build helper: derive the identity without a self-hash cycle."""
    _require(IDENTITY_PATH not in payloads and RECIPE_PATH not in payloads, 'generated PYZ input supplied')
    entries = [dict(path=name, source=MAIN_PATH if name == '__main__.py' else name,
                    size=len(raw), sha256=sha256(raw)) for name, raw in sorted(payloads.items())]
    producer = sha256(recipe_json(dict(algorithm=PRODUCER_ALGORITHM, version=version,
                                      requires_python=requires_python, profile=PROFILE,
                                      source_commit=source_commit, entries=entries)))
    identity = identity_module(producer)
    entries.append(dict(path=IDENTITY_PATH, source=IDENTITY_PATH, size=len(identity), sha256=sha256(identity)))
    entries.sort(key=lambda e:e['path'])
    doc = dict(marker='patch-harbor-pyz-recipe', format_version=1, distribution='patchharbor', version=version,
               requires_python=requires_python, profile=PROFILE, content_id_algorithm=CONTENT_ALGORITHM,
               source_commit=source_commit, entries=entries)
    doc['content_id'] = sha256(recipe_json(doc))
    recipe = parse_recipe(recipe_json(doc))
    _require(producer_id(recipe) == producer, 'inconsistent generated PYZ identity')
    return recipe, identity


def materialize(recipe: PyzRecipe, read: Callable[[str, int], bytes]) -> bytes:
    _require(parse_recipe(recipe.data) == recipe, 'PYZ recipe value differs from bytes')
    sizes = [(e.path, e.size) for e in recipe.entries] + [(RECIPE_PATH, len(recipe.data))]
    total = 22 + sum(size + 76 + 2 * len(name) for name, size in sizes)
    if total > MAX_PYZ_BYTES or sum(size for _, size in sizes) > MAX_CONTENT_BYTES:
        raise RuntimeLimitError('PYZ artifact budget exceeded')
    payloads, sources = {}, {}
    for entry in recipe.entries:
        raw = sources.get(entry.source)
        if raw is None:
            raw = read(entry.source, entry.size)
            sources[entry.source] = raw
        _require(type(raw) is bytes and len(raw) == entry.size and sha256(raw) == entry.sha256,
                 'PYZ resource size or hash mismatch')
        payloads[entry.path] = raw
    _require(payloads[IDENTITY_PATH] == identity_module(producer_id(recipe)), 'PYZ producer identity mismatch')
    _require(payloads['__main__.py'] == payloads[MAIN_PATH], 'PYZ entrypoint/resource mismatch')
    for name in (CHAT_PATH, DOC_PATH, LICENSE_PATH):
        raw = payloads[name]
        _require(0 < len(raw) <= 128 * 1024 and not raw.startswith(b'\xef\xbb\xbf'), 'invalid PYZ document resource')
        try: raw.decode('utf-8')
        except UnicodeError as exc: raise RuntimeDataError('invalid PYZ resource encoding') from exc
    payloads[RECIPE_PATH] = recipe.data
    stream = BytesIO()
    with ZipFile(stream, 'w', compression=ZIP_STORED, allowZip64=False) as archive:
        for name, raw in sorted(payloads.items()):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.create_version = info.extract_version = 20
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    result = stream.getvalue()
    _require(len(result) == total, 'unexpected canonical PYZ serialization')
    return result


def read_pyz(raw: bytes, *, policy, remaining_bytes: int) -> PyzRecipe:
    """Validate a bounded archive as data, including its complete canonical bytes."""
    if len(raw) > MAX_PYZ_BYTES:
        raise RuntimeLimitError('PYZ artifact exceeds budget')
    count = bounded_directory(raw, policy, max_entries=MAX_ENTRIES)
    try:
        with ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            _require(len(infos) == count and len({i.filename for i in infos}) == count, 'invalid PYZ directory')
            if (sum(i.file_size for i in infos) > min(MAX_CONTENT_BYTES, remaining_bytes)
                    or any(i.file_size > policy.max_content_bytes for i in infos)):
                raise RuntimeLimitError('shared PYZ content budget exceeded')
            offset = 0
            for info in infos:
                _require(info.filename == info.orig_filename and info.filename.isascii()
                         and not info.is_dir() and info.compress_type == ZIP_STORED
                         and info.file_size == info.compress_size and info.header_offset == offset
                         and info.date_time == (1980, 1, 1, 0, 0, 0)
                         and info.create_system == 3 and info.create_version == info.extract_version == 20
                         and info.external_attr == 0o100644 << 16
                         and info.internal_attr == info.flag_bits == info.volume == info.reserved == 0
                         and not info.extra and not info.comment, 'noncanonical PYZ ZIP member')
                header = info.FileHeader(zip64=False)
                _require(raw[offset:offset + len(header)] == header, 'inconsistent PYZ local header')
                offset += len(header) + info.file_size
            recipe_info = archive.getinfo(RECIPE_PATH)
            if recipe_info.file_size > MAX_RECIPE_BYTES:
                raise RuntimeLimitError('PYZ recipe exceeds budget')
            recipe = parse_recipe(archive.read(recipe_info))
            expected = {e.path: e.size for e in recipe.entries}
            expected[RECIPE_PATH] = len(recipe.data)
            _require({i.filename: i.file_size for i in infos} == expected, 'PYZ inventory/size mismatch')
            canonical = materialize(recipe, lambda name, size: archive.read(name))
            _require(canonical == raw, 'noncanonical or changed PYZ archive')
            return recipe
    except (BadZipFile, KeyError, UnicodeError, OSError, NotImplementedError) as exc:
        raise RuntimeDataError('invalid PYZ archive') from exc
