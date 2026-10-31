"""Shared, stdlib-only runtime recipe data; no Wheel or PYZ reader imports.

Canonical encodings and validators retain their existing byte/error contracts.
Format-specific namespaces, budgets, capabilities and materialization stay with
those profiles, including their independent validation boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re


RESOURCE_ROOT = "patchharbor/_runtime/"
CHAT_PATH = RESOURCE_ROOT + "CHAT_INSTRUCTIONS.md"
DOC_PATH = RESOURCE_ROOT + "python-api.md"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
VERSION_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?\Z")
PATH_SEGMENT_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")


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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_recipe(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeDataError(message)


def recipe_json(document: object) -> bytes:
    """The versioned recipe/producer encoding, shared with the build backend."""
    return (json.dumps(document, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def unique_recipe_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require_recipe(key not in result, "duplicate recipe key")
        result[key] = value
    return result


def reject_recipe_constant(value: str) -> object:
    raise RuntimeDataError("non-finite recipe value: " + value)
