"""Finite, versioned data recipe for the canonical dependency-free runtime wheel.

Only standard-library data operations live here. The build backend uses this
same implementation; consuming a recipe never imports its described modules.
"""
from __future__ import annotations

import base64
from configparser import ConfigParser, Error as ConfigError
import csv
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
import hashlib
import io
import json
import re
from typing import Callable
from zipfile import ZIP_STORED, ZipFile, ZipInfo


RECIPE_PATH = "patchharbor/_runtime/recipe.json"
RESOURCE_ROOT = "patchharbor/_runtime/"
CONTENT_ALGORITHM = "patchharbor-runtime-content-v1"
PRODUCER_ALGORITHM = "patchharbor-runtime-producer-v1"
IDENTITY_PATH = "patchharbor/_runtime_identity.py"
MAX_RECIPE_BYTES = 1024 * 1024
MAX_WHEEL_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_CONTENT_BYTES = 32 * 1024 * 1024
CHAT_PATH = RESOURCE_ROOT + "CHAT_INSTRUCTIONS.md"
DOC_PATH = RESOURCE_ROOT + "python-api.md"
WHEEL_METADATA = (
    b"Wheel-Version: 1.0\nGenerator: patchharbor-canonical-v1\n"
    b"Root-Is-Purelib: true\nTag: py3-none-any\n\n"
)
_METADATA_FILES = {"METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "licenses/LICENSE"}
_RECIPE_FIELDS = {
    "marker", "format_version", "distribution", "version", "requires_python",
    "content_id_algorithm", "content_id", "source_commit", "entries",
}
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")
_DEV_REQUIREMENT = re.compile(r'[^;\r\n]+; extra == [\"\']dev[\"\']\Z')


class RuntimeDataError(ValueError):
    """Invalid prepared resources, distinct from missing local installation."""


class RuntimeLimitError(RuntimeDataError):
    """A fixed canonical-runtime product budget was exceeded."""


@dataclass(frozen=True, slots=True)
class RuntimeEntry:
    path: str
    source: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class RuntimeRecipe:
    version: str
    requires_python: str
    content_id: str
    source_commit: str | None
    entries: tuple[RuntimeEntry, ...]
    data: bytes

    @property
    def dist_info(self) -> str:
        return f"patchharbor-{self.version}.dist-info"

    @property
    def wheel_name(self) -> str:
        return f"patchharbor-{self.version}-py3-none-any.whl"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeDataError(message)


def _json(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate recipe key")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise RuntimeDataError("non-finite recipe value: " + value)


def _python_requirement(value: object) -> bool:
    if type(value) is not str or not 0 < len(value) <= 128:
        return False
    for constraint in value.split(","):
        match = re.fullmatch(r"\s*(~=|==|!=|<=|>=|<|>)\s*([0-9A-Za-z.*]+)\s*", constraint)
        if match is None:
            return False
        operator, version = match.groups()
        if version.endswith(".*"):
            if operator not in {"==", "!="} or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", version[:-2]):
                return False
        elif not _VERSION.fullmatch(version) or (operator == "~=" and not re.match(r"[0-9]+\.[0-9]+", version)):
            return False
    return True


def _path(name: object, dist_info: str) -> str:
    _require(type(name) is str and 0 < len(name) <= 512, "invalid wheel path")
    parts = name.split("/")
    for part in parts:
        _require(len(part) <= 128 and _SEGMENT.fullmatch(part) is not None
                 and not part.endswith("."), "unsafe wheel path")
        stem = part.split(".")[0].upper()
        _require(stem not in {"CON", "PRN", "AUX", "NUL"}
                 and not re.fullmatch(r"(?:COM|LPT)[1-9]", stem), "device wheel path")
    if parts[0] == dist_info:
        _require("/".join(parts[1:]) in _METADATA_FILES, "unexpected distribution data")
    elif parts[0] in {"patchharbor", "patchharbor_watcher"}:
        if name.startswith(RESOURCE_ROOT):
            _require(name in {CHAT_PATH, DOC_PATH}
                     or name.removeprefix(RESOURCE_ROOT + "metadata/") in _METADATA_FILES,
                     "unexpected runtime resource")
        else:
            _require((name.endswith(".py") and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p)
                     for p in [*parts[1:-1], parts[-1][:-3]]))
                     or name == "patchharbor/py.typed", "unexpected runtime module")
            _require(parts[-1] not in {"sitecustomize.py", "usercustomize.py"}
                     and "__pycache__" not in parts, "startup or bytecode resource")
    else:
        raise RuntimeDataError("foreign wheel namespace")
    return name


def _metadata(payloads: dict[str, bytes], recipe: RuntimeRecipe) -> None:
    prefix = recipe.dist_info + "/"
    message = BytesParser(policy=email_policy).parsebytes(payloads[prefix + "METADATA"])
    _require(not message.defects, "invalid core metadata")
    for key, expected in (("Name", "patchharbor"), ("Version", recipe.version),
                          ("Requires-Python", recipe.requires_python)):
        _require(message.get_all(key) == [expected], "inconsistent core metadata: " + key)
    # Dev extras remain transport metadata, never offline runtime dependencies.
    _require(all(_DEV_REQUIREMENT.fullmatch(str(value))
                 for value in message.get_all("Requires-Dist", [])), "runtime dependencies forbidden")
    _require(payloads[prefix + "WHEEL"] == WHEEL_METADATA, "noncanonical wheel metadata")
    parser = ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string(payloads[prefix + "entry_points.txt"].decode("utf-8"))
        scripts = dict(parser.items("console_scripts"))
    except (ConfigError, ValueError, UnicodeError) as exc:
        raise RuntimeDataError("invalid entry points") from exc
    _require(parser.sections() == ["console_scripts"] and scripts == {
        "patchharbor": "patchharbor.cli:main", "patchharbor-watcher": "patchharbor_watcher.cli:main",
    }, "unexpected console entry points")
    _require(set(payloads[prefix + "top_level.txt"].splitlines()) ==
             {b"patchharbor", b"patchharbor_watcher"}, "unexpected top-level packages")
    _require(bool(payloads[prefix + "licenses/LICENSE"]), "missing license")
    for path in (CHAT_PATH, DOC_PATH):
        raw = payloads[path]
        _require(0 < len(raw) <= 128 * 1024 and not raw.startswith(b"\xef\xbb\xbf"), "invalid documentation resource")
        try:
            raw.decode("utf-8")
        except UnicodeError as exc:
            raise RuntimeDataError("invalid resource encoding") from exc


def parse_recipe(raw: bytes) -> RuntimeRecipe:
    if len(raw) > MAX_RECIPE_BYTES:
        raise RuntimeLimitError("runtime recipe too large")
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise RuntimeDataError("invalid runtime recipe JSON") from exc
    _require(type(doc) is dict and set(doc) == _RECIPE_FIELDS, "invalid recipe schema")
    _require(doc["marker"] == "patch-harbor-runtime-recipe"
             and type(doc["format_version"]) is int and doc["format_version"] == 1
             and doc["distribution"] == "patchharbor"
             and doc["content_id_algorithm"] == CONTENT_ALGORITHM, "unsupported recipe")
    version = doc["version"]
    _require(type(version) is str and _VERSION.fullmatch(version) is not None, "invalid runtime version")
    requires = doc["requires_python"]
    _require(_python_requirement(requires), "invalid Python requirement")
    commit = doc["source_commit"]
    _require(commit is None or (type(commit) is str and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit)),
             "invalid source provenance")
    content_id = doc["content_id"]
    _require(type(content_id) is str and _HEX.fullmatch(content_id) is not None, "invalid content ID")
    _require(type(doc["entries"]) is list, "invalid inventory")
    if len(doc["entries"]) + 2 > MAX_ENTRIES:
        raise RuntimeLimitError("runtime inventory too large")
    entries = []
    names: set[str] = set()
    directories: dict[str, str] = {}
    total = len(raw)
    dist_info = f"patchharbor-{version}.dist-info"
    for item in doc["entries"]:
        _require(type(item) is dict and set(item) == {"path", "source", "size", "sha256"}, "invalid entry schema")
        name = _path(item["path"], dist_info)
        source = _path(item["source"], dist_info)
        expected_source = (RESOURCE_ROOT + "metadata/" + name.split("/", 1)[1]
                           if name.startswith(dist_info + "/") else name)
        _require(source == expected_source, "invalid resource mapping")
        _require(name.casefold() not in names, "duplicate wheel target")
        names.add(name.casefold())
        parts = name.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index])
            _require(directories.setdefault(parent.casefold(), parent) == parent,
                     "case-ambiguous wheel directory")
        size, digest = item["size"], item["sha256"]
        _require(type(size) is int and size >= 0 and type(digest) is str
                 and _HEX.fullmatch(digest) is not None, "invalid entry size or hash")
        total += size
        if total > MAX_CONTENT_BYTES:
            raise RuntimeLimitError("runtime content budget exceeded")
        entries.append(RuntimeEntry(name, source, size, digest))
    _require([e.path for e in entries] == sorted(e.path for e in entries), "noncanonical inventory order")
    inventory = {e.path: e for e in entries}
    required = {CHAT_PATH, DOC_PATH, "patchharbor/py.typed", "patchharbor/__init__.py",
                "patchharbor/api.py", "patchharbor/cli.py", "patchharbor_watcher/__init__.py",
                "patchharbor_watcher/cli.py", "patchharbor/runtime_wheel.py", "patchharbor/runtime_artifact.py"}
    required |= {dist_info + "/" + n for n in _METADATA_FILES}
    required |= {RESOURCE_ROOT + "metadata/" + n for n in _METADATA_FILES}
    _require(required <= inventory.keys(), "incomplete runtime inventory")
    for entry in entries:
        source = inventory.get(entry.source)
        _require(source is not None and (source.size, source.sha256) == (entry.size, entry.sha256),
                 "inconsistent passive metadata copy")
        for i in range(1, len(entry.path.split("/"))):
            _require("/".join(entry.path.split("/")[:i]).casefold() not in names, "file/directory collision")
    unsigned = {k: v for k, v in doc.items() if k != "content_id"}
    _require(sha256(_json(unsigned)) == content_id and _json(doc) == raw, "recipe content ID or encoding mismatch")
    return RuntimeRecipe(version, requires, content_id, commit, tuple(entries), raw)


def prepare_recipe(payloads: dict[str, bytes], *, version: str, requires_python: str) -> RuntimeRecipe:
    """Build-time only: derive the self-description, without an archive self-hash."""
    dist_info = f"patchharbor-{version}.dist-info/"
    doc = {
        "marker": "patch-harbor-runtime-recipe", "format_version": 1,
        "distribution": "patchharbor", "version": version, "requires_python": requires_python,
        "content_id_algorithm": CONTENT_ALGORITHM, "source_commit": None,
        "entries": [{"path": name,
                     "source": RESOURCE_ROOT + "metadata/" + name[len(dist_info):] if name.startswith(dist_info) else name,
                     "size": len(raw), "sha256": sha256(raw)} for name, raw in sorted(payloads.items())],
    }
    doc["content_id"] = sha256(_json(doc))
    return parse_recipe(_json(doc))


def producer_id(recipe: RuntimeRecipe) -> str:
    """Finite identity anchored in loaded code, before adding its own module.

    This deliberately differs from content_id: the final recipe also inventories
    the generated identity module. Neither digest contains itself.
    """
    return sha256(_json({
        "algorithm": PRODUCER_ALGORITHM, "version": recipe.version,
        "requires_python": recipe.requires_python, "source_commit": recipe.source_commit,
        "entries": [{"path": e.path, "source": e.source, "size": e.size, "sha256": e.sha256}
                    for e in recipe.entries if e.path != IDENTITY_PATH],
    }))


def identity_module(resource_id: str) -> bytes:
    _require(type(resource_id) is str and _HEX.fullmatch(resource_id) is not None,
             "invalid producer ID")
    return (f'# Generated at wheel build; no runtime work.\nRESOURCE_ID = "{resource_id}"\n').encode("ascii")


def _record(recipe: RuntimeRecipe) -> bytes:
    inventory = [(entry.path, entry.sha256, entry.size) for entry in recipe.entries]
    inventory.append((RECIPE_PATH, sha256(recipe.data), len(recipe.data)))
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, digest, size in sorted(inventory):
        encoded = base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode("ascii")
        writer.writerow((name, "sha256=" + encoded, size))
    writer.writerow((recipe.dist_info + "/RECORD", "", ""))
    return record.getvalue().encode("utf-8")


def materialize(recipe: RuntimeRecipe, read: Callable[[str, int], bytes]) -> bytes:
    """Validate prepared input and emit fixed ZIP_STORED bytes; no build/import/IO."""
    # RuntimeRecipe is an internal value, but callers must not bypass the parser
    # by constructing one with different paths, limits or provenance.
    _require(parse_recipe(recipe.data) == recipe, "recipe value differs from its bytes")
    record_path = recipe.dist_info + "/RECORD"
    record = _record(recipe)
    sizes = [(entry.path, entry.size) for entry in recipe.entries]
    sizes.extend(((RECIPE_PATH, len(recipe.data)), (record_path, len(record))))
    # Budget the complete archive, including derived data, before resource reads.
    total = 22 + sum(size + 76 + 2 * len(name.encode("ascii")) for name, size in sizes)
    if total > MAX_WHEEL_BYTES or sum(size for _, size in sizes) > MAX_CONTENT_BYTES:
        raise RuntimeLimitError("runtime archive budget exceeded")
    payloads: dict[str, bytes] = {}
    sources: dict[str, bytes] = {}
    for entry in recipe.entries:
        raw = sources.get(entry.source)
        if raw is None:
            raw = read(entry.source, entry.size)
            sources[entry.source] = raw
        _require(len(raw) == entry.size and sha256(raw) == entry.sha256, "runtime resource changed: " + entry.source)
        payloads[entry.path] = raw
    _metadata(payloads, recipe)
    if IDENTITY_PATH in payloads:
        _require(payloads[IDENTITY_PATH] == identity_module(producer_id(recipe)),
                 "inconsistent producer identity module")
    payloads[RECIPE_PATH] = recipe.data
    payloads[record_path] = record
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_STORED, allowZip64=False) as wheel:
        for name in sorted(payloads, key=lambda n: (n.startswith(recipe.dist_info + "/"), n)):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.create_version = info.extract_version = 20
            info.external_attr = 0o100644 << 16
            wheel.writestr(info, payloads[name])
    result = stream.getvalue()
    _require(len(result) == total, "unexpected archive serialization")
    return result
