"""Closed Result runtime descriptors shared by the Wheel and PYZ profiles."""
from __future__ import annotations

from dataclasses import dataclass

from .runtime_profile import SHA256_PATTERN, sha256


METADATA_PATH = "runtime/runtime.json"
MAX_METADATA_BYTES = 128 * 1024
UNAVAILABLE_REASONS = frozenset({
    "source_not_prepared", "source_changed", "artifact_missing", "artifact_mismatch",
    "artifact_corrupt", "artifact_unsupported", "resource_limit", "read_error",
})
@dataclass(frozen=True, slots=True)
class RuntimeFile:
    path: str
    size: int
    sha256: str

def require_metadata(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def read_descriptor(value: object, *, path: str, limit: int, files: dict[str, bytes]) -> RuntimeFile:
    require_metadata(type(value) is dict and set(value) == {"path", "size", "sha256"},
             "invalid runtime descriptor schema")
    require_metadata(value["path"] == path and type(value["size"]) is int
             and 0 <= value["size"] <= limit and type(value["sha256"]) is str
             and SHA256_PATTERN.fullmatch(value["sha256"]) is not None, "invalid runtime descriptor")
    raw = files[path]
    require_metadata(len(raw) == value["size"] and sha256(raw) == value["sha256"],
             "runtime descriptor size or hash mismatch")
    return RuntimeFile(path, value["size"], value["sha256"])
