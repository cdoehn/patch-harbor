"""Read the closed Result-2 runtime namespace; never import described code."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import struct
from zipfile import BadZipFile, ZIP_STORED, ZipFile

from patchharbor.json_document import parse_json_document
from patchharbor.resource_policy import ResourcePolicy
from patchharbor import runtime_wheel as wheel


METADATA_PATH = "runtime/runtime.json"
MAX_METADATA_BYTES = 128 * 1024
UNAVAILABLE_REASONS = frozenset({
    "source_not_prepared", "source_changed", "artifact_missing", "artifact_mismatch",
    "artifact_corrupt", "artifact_unsupported", "resource_limit", "read_error",
})
_FIELDS = {
    "marker", "format_version", "status", "reason", "distribution", "version",
    "requires_python", "content_id", "content_id_algorithm", "wheel", "tags",
    "runtime_dependencies", "provenance", "capabilities",
}


@dataclass(frozen=True, slots=True)
class RuntimeFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ResultRuntime:
    status: str
    reason: str | None
    metadata: RuntimeFile
    wheel: RuntimeFile | None
    version: str | None
    requires_python: str | None
    content_id: str | None
    source_commit: str | None
    operations: tuple[str, ...]
    patch_formats: tuple[int, ...]
    result_formats: tuple[int, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _descriptor(value: object, *, path: str, limit: int, files: dict[str, bytes]) -> RuntimeFile:
    _require(type(value) is dict and set(value) == {"path", "size", "sha256"},
             "invalid runtime descriptor schema")
    _require(value["path"] == path and type(value["size"]) is int
             and 0 <= value["size"] <= limit and type(value["sha256"]) is str
             and wheel._HEX.fullmatch(value["sha256"]) is not None, "invalid runtime descriptor")
    raw = files[path]
    _require(len(raw) == value["size"] and wheel.sha256(raw) == value["sha256"],
             "runtime descriptor size or hash mismatch")
    return RuntimeFile(path, value["size"], value["sha256"])


def _capabilities(value: object) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...]]:
    _require(type(value) is dict and set(value) == {"operations", "patch_formats", "result_formats"},
             "invalid runtime capabilities schema")
    _require(value["operations"] == ["inspect_patch", "validate_patch"], "unsupported runtime operations")
    for key, choices in (("patch_formats", ([1],)), ("result_formats", ([1], [1, 2]))):
        versions = value[key]
        _require(type(versions) is list and all(type(v) is int for v in versions)
                 and versions in choices, "unsupported runtime read versions")
    return tuple(value["operations"]), tuple(value["patch_formats"]), tuple(value["result_formats"])


def _read_wheel(raw: bytes, *, policy: ResourcePolicy, remaining_bytes: int) -> wheel.RuntimeRecipe:
    """Validate one canonical archive, retaining only recipe and small metadata.

    Each member is read once and released before the next; the already captured
    outer wheel bytes are neither extracted nor materialized into another wheel.
    """
    _require(len(raw) <= wheel.MAX_WHEEL_BYTES, "runtime wheel budget exceeded")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            _require(len(infos) <= min(wheel.MAX_ENTRIES, policy.max_zip_entries),
                     "inner runtime entry budget exceeded")
            _require(sum(i.file_size for i in infos) <= min(wheel.MAX_CONTENT_BYTES, remaining_bytes),
                     "shared runtime byte budget exceeded")
            _require(all(i.file_size <= policy.max_content_bytes for i in infos),
                     "inner runtime member budget exceeded")
            names = [i.filename for i in infos]
            _require(len(names) == len(set(names)) and not archive.comment, "duplicate or noncanonical runtime ZIP")
            offset = 0
            for info in infos:
                _require(bool(info.filename) and info.orig_filename == info.filename and info.filename.isascii()
                         and not info.is_dir() and info.compress_type == ZIP_STORED
                         and info.file_size == info.compress_size
                         and info.date_time == (1980, 1, 1, 0, 0, 0)
                         and info.create_system == 3 and info.create_version == info.extract_version == 20
                         and info.external_attr == 0o100644 << 16
                         and info.internal_attr == info.flag_bits == info.volume == info.reserved == 0
                         and not info.extra and not info.comment and info.header_offset == offset,
                         "noncanonical runtime ZIP member")
                header = info.FileHeader(zip64=False)
                _require(raw[offset:offset + len(header)] == header, "inconsistent runtime local ZIP header")
                offset += len(header) + info.file_size
            directory_size = sum(46 + len(name) for name in names)
            end = struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, len(infos), len(infos), directory_size, offset, 0)
            _require(len(raw) == offset + directory_size + len(end) and raw[-len(end):] == end,
                     "noncanonical runtime ZIP boundary")
            members = dict(zip(names, infos, strict=True))
            recipe_info = members[wheel.RECIPE_PATH]
            _require(recipe_info.file_size <= wheel.MAX_RECIPE_BYTES, "runtime recipe budget exceeded")
            recipe = wheel.parse_recipe(archive.read(recipe_info))
            record_path = recipe.dist_info + "/RECORD"
            inventory = {e.path: e for e in recipe.entries}
            expected = set(inventory) | {wheel.RECIPE_PATH, record_path}
            _require(set(names) == expected and wheel.IDENTITY_PATH in inventory,
                     "incomplete or unexpected runtime wheel inventory")
            _require(names == sorted(expected, key=lambda n: (n.startswith(recipe.dist_info + "/"), n)),
                     "noncanonical runtime wheel order")
            for name, entry in inventory.items():
                _require(members[name].file_size == entry.size, "runtime inventory size mismatch")
            record_entries = [(e.path, e.sha256, e.size) for e in recipe.entries]
            record_entries.append((wheel.RECIPE_PATH, wheel.sha256(recipe.data), len(recipe.data)))
            record = wheel.wheel_record(record_entries, record_path)
            _require(members[record_path].file_size == len(record), "runtime RECORD size mismatch")
            metadata_names = {recipe.dist_info + "/" + n for n in wheel._METADATA_FILES}
            metadata_names.update((wheel.CHAT_PATH, wheel.DOC_PATH))
            metadata = {}
            for info in infos:
                if info.filename == wheel.RECIPE_PATH:
                    continue
                content = archive.read(info)
                if info.filename == record_path:
                    _require(content == record, "runtime RECORD mismatch")
                else:
                    entry = inventory[info.filename]
                    _require(len(content) == entry.size and wheel.sha256(content) == entry.sha256,
                             "runtime wheel member hash mismatch")
                    if info.filename == wheel.IDENTITY_PATH:
                        _require(content == wheel.identity_module(wheel.producer_id(recipe)),
                                 "runtime producer identity mismatch")
                    if info.filename in metadata_names:
                        metadata[info.filename] = content
                del content
            wheel._metadata(metadata, recipe)
            return recipe
    except (BadZipFile, OSError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("invalid runtime wheel archive") from exc


def read_result_runtime(value: object, files: dict[str, bytes], *,
                        resource_policy: ResourcePolicy) -> ResultRuntime:
    """Verify the complete finite runtime namespace and return immutable facts."""
    _require(type(value) is dict and set(value) == {"status", "reason", "metadata", "wheel"},
             "invalid Result runtime schema")
    metadata = _descriptor(value["metadata"], path=METADATA_PATH, limit=MAX_METADATA_BYTES, files=files)
    doc = parse_json_document(files[METADATA_PATH])
    _require(set(doc) == _FIELDS and doc["marker"] == "patch-harbor-runtime"
             and type(doc["format_version"]) is int and doc["format_version"] == 1
             and doc["distribution"] == "patchharbor", "unsupported runtime metadata schema")
    _require(doc["status"] == value["status"] and doc["reason"] == value["reason"]
             and doc["wheel"] == value["wheel"], "inconsistent runtime metadata")
    actual = {name for name in files if name.startswith("runtime/")}
    version, requires = doc["version"], doc["requires_python"]
    _require(version is None or (type(version) is str and wheel._VERSION.fullmatch(version) is not None),
             "invalid runtime version")
    _require(requires is None or wheel._python_requirement(requires), "invalid runtime Python requirement")
    if doc["status"] == "unavailable":
        _require(type(doc["reason"]) is str and doc["reason"] in UNAVAILABLE_REASONS,
                 "invalid unavailable runtime reason")
        _require(actual == {METADATA_PATH} and all(doc[key] is None for key in (
            "content_id", "content_id_algorithm", "wheel", "tags", "runtime_dependencies", "provenance", "capabilities")),
            "unavailable runtime contains artifact claims")
        return ResultRuntime("unavailable", doc["reason"], metadata, None, version, requires, None, None, (), (), ())
    _require(doc["status"] == "embedded" and doc["reason"] is None
             and version is not None and requires is not None, "invalid embedded runtime status")
    descriptor = _descriptor(value["wheel"], path=f"runtime/patchharbor-{version}-py3-none-any.whl",
                             limit=wheel.MAX_WHEEL_BYTES, files=files)
    _require(_descriptor(doc["wheel"], path=descriptor.path, limit=wheel.MAX_WHEEL_BYTES, files=files) == descriptor,
             "runtime wheel descriptors differ")
    _require(actual == {METADATA_PATH, descriptor.path}, "unexpected Result runtime files")
    _require(doc["tags"] == ["py3-none-any"] and doc["runtime_dependencies"] == []
             and doc["content_id_algorithm"] == wheel.CONTENT_ALGORITHM, "unsupported runtime profile")
    capabilities = _capabilities(doc["capabilities"])
    provenance = doc["provenance"]
    _require(type(provenance) is dict and set(provenance) == {"mode", "source_commit", "recipe_format_version"}
             and provenance["mode"] == "canonical_resources"
             and type(provenance["recipe_format_version"]) is int and provenance["recipe_format_version"] == 1,
             "invalid runtime provenance schema")
    remaining = resource_policy.max_zip_total_bytes - sum(len(raw) for raw in files.values())
    recipe = _read_wheel(files[descriptor.path], policy=resource_policy, remaining_bytes=remaining)
    _require((version, requires, doc["content_id"], provenance["source_commit"]) ==
             (recipe.version, recipe.requires_python, recipe.content_id, recipe.source_commit),
             "runtime metadata differs from wheel recipe")
    return ResultRuntime("embedded", None, metadata, descriptor, version, requires,
                         recipe.content_id, recipe.source_commit, *capabilities)
