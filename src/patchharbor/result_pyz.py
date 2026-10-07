"""Closed Result-3/PYZ metadata reader; described code is never imported."""
from __future__ import annotations

from dataclasses import dataclass, field

from patchharbor.json_document import parse_json_document
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.result_runtime import (
    METADATA_PATH, MAX_METADATA_BYTES, UNAVAILABLE_REASONS, RuntimeFile, _descriptor, _require,
)
from patchharbor import runtime_pyz as pyz
from patchharbor.runtime_wheel import _VERSION, _HEX, _python_requirement


_FIELDS = frozenset({
    'marker', 'format_version', 'status', 'reason', 'distribution', 'version',
    'requires_python', 'profile', 'content_id', 'content_id_algorithm', 'artifact',
    'runtime_dependencies', 'provenance', 'capabilities',
})


@dataclass(frozen=True, slots=True)
class RuntimePyzFile(RuntimeFile):
    type: str = field(default='pyz', init=False)


@dataclass(frozen=True, slots=True)
class ResultPyzRuntime:
    status: str
    reason: str | None
    metadata: RuntimeFile
    artifact: RuntimePyzFile | None
    version: str | None
    requires_python: str | None
    profile: str | None
    content_id: str | None
    source_commit: str | None
    operations: tuple[str, ...]
    patch_formats: tuple[int, ...]
    result_formats: tuple[int, ...]


def _artifact(value: object, *, version: str, files: dict[str, bytes]) -> RuntimePyzFile:
    _require(type(value) is dict and set(value) == {'type','path','size','sha256'}
             and value['type'] == 'pyz', 'invalid PYZ artifact descriptor schema')
    data = _descriptor({key:item for key,item in value.items() if key != 'type'},
                       path=f'runtime/patchharbor-{version}.pyz', limit=pyz.MAX_PYZ_BYTES, files=files)
    _require(data.size > 0, 'empty PYZ artifact')
    return RuntimePyzFile(data.path, data.size, data.sha256)


def _capabilities(value: object) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...]]:
    _require(type(value) is dict and set(value) == {'operations','patch_formats','result_formats'},
             'invalid PYZ capabilities schema')
    _require(value['operations'] == ['inspect_patch','validate_patch','pack_patch'],
             'unsupported PYZ operations')
    for key, expected in (('patch_formats',[1]), ('result_formats',[1,2,3])):
        versions = value[key]
        _require(type(versions) is list and all(type(v) is int for v in versions)
                 and versions == expected, 'unsupported PYZ read versions')
    return tuple(value['operations']), tuple(value['patch_formats']), tuple(value['result_formats'])


def read_result_pyz(value: object, files: dict[str, bytes], *, resource_policy: ResourcePolicy) -> ResultPyzRuntime:
    """Check exact namespaces, metadata, descriptors and shared outer/inner budget."""
    _require(type(value) is dict and set(value) == {'status','reason','metadata','artifact'},
             'invalid Result-3 runtime schema')
    metadata = _descriptor(value['metadata'], path=METADATA_PATH, limit=MAX_METADATA_BYTES, files=files)
    doc = parse_json_document(files[METADATA_PATH])
    _require(set(doc) == _FIELDS and doc['marker'] == 'patch-harbor-runtime'
             and type(doc['format_version']) is int and doc['format_version'] == 2
             and doc['distribution'] == 'patchharbor', 'unsupported PYZ runtime metadata schema')
    _require(doc['status'] == value['status'] and doc['reason'] == value['reason']
             and doc['artifact'] == value['artifact'], 'inconsistent PYZ runtime metadata')
    actual = {name for name in files if name.startswith('runtime/')}
    version, requires = doc['version'], doc['requires_python']
    _require(version is None or (type(version) is str and _VERSION.fullmatch(version) is not None),
             'invalid PYZ runtime version')
    _require(requires is None or _python_requirement(requires), 'invalid PYZ runtime Python requirement')
    if doc['status'] == 'unavailable':
        _require(type(doc['reason']) is str and doc['reason'] in UNAVAILABLE_REASONS,
                 'invalid unavailable PYZ reason')
        _require(actual == {METADATA_PATH} and all(doc[key] is None for key in (
            'artifact','profile','content_id','content_id_algorithm','runtime_dependencies','provenance','capabilities')),
            'unavailable PYZ contains artifact claims')
        return ResultPyzRuntime('unavailable',doc['reason'],metadata,None,version,requires,None,None,None,(),(),())
    _require(doc['status'] == 'embedded' and doc['reason'] is None
             and version is not None and requires is not None, 'invalid embedded PYZ status')
    descriptor = _artifact(value['artifact'], version=version, files=files)
    _require(_artifact(doc['artifact'], version=version, files=files) == descriptor,
             'PYZ artifact descriptors differ')
    _require(actual == {METADATA_PATH,descriptor.path}, 'unexpected PYZ runtime files')
    _require(doc['profile'] == pyz.PROFILE and doc['runtime_dependencies'] == []
             and doc['content_id_algorithm'] == pyz.CONTENT_ALGORITHM
             and type(doc['content_id']) is str and _HEX.fullmatch(doc['content_id']) is not None,
             'unsupported PYZ runtime profile')
    capabilities = _capabilities(doc['capabilities'])
    provenance = doc['provenance']
    _require(type(provenance) is dict and set(provenance) == {'mode','source_commit','recipe_format_version'}
             and provenance['mode'] == 'canonical_resources'
             and type(provenance['recipe_format_version']) is int and provenance['recipe_format_version'] == 1,
             'invalid PYZ provenance schema')
    remaining = resource_policy.max_zip_total_bytes - sum(len(raw) for raw in files.values())
    recipe = pyz.read_pyz(files[descriptor.path], policy=resource_policy, remaining_bytes=remaining)
    _require((version,requires,doc['content_id'],provenance['source_commit']) ==
             (recipe.version,recipe.requires_python,recipe.content_id,recipe.source_commit),
             'runtime metadata differs from PYZ recipe')
    return ResultPyzRuntime('embedded',None,metadata,descriptor,version,requires,pyz.PROFILE,
                            recipe.content_id,recipe.source_commit,*capabilities)
