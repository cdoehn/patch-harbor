"""Passive bundle handoff documents and optional format-1 patch metadata roles."""

from __future__ import annotations

from dataclasses import dataclass
import json

from patchharbor.errors import task_bundle_error
from patchharbor.json_document import serialize_json_document
from patchharbor.models import BundlePayload
from patchharbor.task_manifest import TaskManifest


CHAT_INSTRUCTIONS_NAME = "CHAT_INSTRUCTIONS.md"
ENVIRONMENT_NAME = "environment.json"
TASK_HANDOFF_DIRECTORY = "PATCHHARBOR_META"
ENVIRONMENT_MARKER = "patch-harbor-environment"
ENVIRONMENT_FORMAT_VERSION = 2
MAX_HANDOFF_ENTRY_BYTES = 128 * 1024
TASK_FILENAME_SCHEMA = "<Repository>_Task_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip<bundle_suffix>"
RESULT_FILENAME_SCHEMA = "<Repository>_Result_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip<bundle_suffix>"


@dataclass(frozen=True)
class BundleHandoff:
    """Documentation only; never a source of execution or repository identity."""

    instructions: bytes
    environment: bytes

    def entries(self, *, patch: bool = False) -> tuple[tuple[str, bytes], ...]:
        prefix = f"{TASK_HANDOFF_DIRECTORY}/" if patch else ""
        return (
            (prefix + CHAT_INSTRUCTIONS_NAME, self.instructions),
            (prefix + ENVIRONMENT_NAME, self.environment),
        )


def encode_environment(document: dict[str, object]) -> bytes:
    return serialize_json_document(document).encode("utf-8")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate handoff JSON key")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> object:
    raise ValueError("non-finite handoff JSON number")


def split_task_handoff(
    payloads: tuple[BundlePayload, ...],
    manifest: TaskManifest,
) -> tuple[tuple[BundlePayload, ...], BundleHandoff | None]:
    """Remove only a complete, validated reserved metadata pair, never execute it."""
    prefix = TASK_HANDOFF_DIRECTORY + "/"
    metadata = tuple(
        payload for payload in payloads
        if payload.relative_path.split("/", 1)[0].casefold() == TASK_HANDOFF_DIRECTORY.casefold()
    )
    if not metadata:
        return payloads, None  # Existing format-1 packages remain unchanged.
    expected = {prefix + CHAT_INSTRUCTIONS_NAME, prefix + ENVIRONMENT_NAME}
    if {item.relative_path for item in metadata} != expected or len(metadata) != 2:
        raise task_bundle_error("patch handoff must contain exactly the two reserved metadata files")
    if manifest.entrypoint in expected:
        raise task_bundle_error("patch handoff metadata cannot be an entrypoint")
    content = {item.relative_path: item.content for item in metadata}
    try:
        for raw in content.values():
            if not raw or len(raw) > MAX_HANDOFF_ENTRY_BYTES or raw.startswith(b"\xef\xbb\xbf"):
                raise ValueError("invalid handoff size or encoding")
            raw.decode("utf-8")
        environment = json.loads(
            content[prefix + ENVIRONMENT_NAME],
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
        if (
            type(environment) is not dict
            or environment.get("marker") != ENVIRONMENT_MARKER
            or type(environment.get("format_version")) is not int
            or environment["format_version"] != ENVIRONMENT_FORMAT_VERSION
            or environment.get("bundle_type") != "Task"
        ):
            raise ValueError("invalid environment document")
        # Supplementary metadata must agree, but cannot replace the manifest.
        if environment.get("repository_context") != {
            "repo_id": str(manifest.repo_id),
            "base_commit": str(manifest.base_commit),
            "state_fingerprint": manifest.state_fingerprint,
            "fingerprint_algorithm": manifest.fingerprint_algorithm,
        }:
            raise ValueError("handoff does not match task.json")
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise task_bundle_error("invalid patch handoff metadata") from exc
    return (
        tuple(payload for payload in payloads if payload not in metadata),
        BundleHandoff(content[prefix + CHAT_INSTRUCTIONS_NAME], content[prefix + ENVIRONMENT_NAME]),
    )
