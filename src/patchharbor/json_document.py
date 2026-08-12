"""Serialize closed PatchHarbor JSON documents through one boundary."""

from __future__ import annotations

from collections.abc import Mapping
import json


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
