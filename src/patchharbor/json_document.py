"""Strict data decoding and serialization of closed PatchHarbor JSON documents."""

from __future__ import annotations

from collections.abc import Mapping
import json


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate bundle JSON key")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> object:
    raise ValueError("non-finite bundle JSON value")


def parse_json_document(content: bytes) -> dict[str, object]:
    """Decode a UTF-8 object without BOM, duplicate keys or non-finite literals.

    Callers own resource limits, exact fields and semantic validation.
    """
    if content.startswith(b"\xef\xbb\xbf"):
        raise ValueError("bundle JSON has a BOM")
    result = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object,
                        parse_constant=_invalid_constant)
    if type(result) is not dict:
        raise ValueError("bundle JSON is not an object")
    return result


def serialize_json_document(document: Mapping[str, object]) -> str:
    """Return one JSON document terminated by a line feed."""
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    )
