"""Passive bundle handoff documents and optional format-2 Task metadata roles."""

from __future__ import annotations

from dataclasses import dataclass
import json
from hashlib import sha256

from patchharbor.errors import task_bundle_error
from patchharbor.json_document import serialize_json_document
from patchharbor.models import BundlePayload
from patchharbor.task_manifest import TaskManifest


CHAT_INSTRUCTIONS_NAME = "CHAT_INSTRUCTIONS.md"
ENVIRONMENT_NAME = "environment.json"
TASK_HANDOFF_DIRECTORY = "PATCHHARBOR_META"
ENVIRONMENT_MARKER = "patch-harbor-environment"
ENVIRONMENT_FORMAT_VERSION = 3
BOOTSTRAP_NAME = "tools/pyz_bootstrap.py"
MAX_HANDOFF_ENTRY_BYTES = 128 * 1024
TASK_FILENAME_SCHEMA = "<Repository>_Task_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip<bundle_suffix>"
RESULT_FILENAME_SCHEMA = "<Repository>_Result_Bundle_<HHMMSS>_<MMDD>_<ID6>.zip<bundle_suffix>"


@dataclass(frozen=True)
class BundleHandoff:
    """Documentation only; never a source of execution or repository identity."""

    instructions: bytes
    environment: bytes
    bootstrap: bytes | None = None

    def entries(self, *, task: bool = False) -> tuple[tuple[str, bytes], ...]:
        prefix = f"{TASK_HANDOFF_DIRECTORY}/" if task else ""
        entries = (
            (prefix + CHAT_INSTRUCTIONS_NAME, self.instructions),
            (prefix + ENVIRONMENT_NAME, self.environment),
        )
        return entries if self.bootstrap is None else entries + ((prefix + BOOTSTRAP_NAME, self.bootstrap),)


def handoff_names(document: dict) -> set[str]:
    version = document.get("format_version")
    if type(version) is not int or version not in (2, 3):
        raise ValueError("unsupported handoff version")
    return {CHAT_INSTRUCTIONS_NAME, ENVIRONMENT_NAME} | ({BOOTSTRAP_NAME} if version == 3 else set())


def validate_bootstrap(document: dict, raw: bytes | None) -> None:
    """Check passive helper integrity; this does not authenticate its author."""
    if document["format_version"] == 2:
        if raw is not None or "bootstrap" in document:
            raise ValueError("unexpected helper in handoff 2")
        return
    descriptor = document.get("bootstrap")
    if (raw is None or not raw or len(raw) > MAX_HANDOFF_ENTRY_BYTES
            or raw.startswith(b"\xef\xbb\xbf") or type(descriptor) is not dict
            or set(descriptor) != {"path", "size", "sha256"}
            or descriptor.get("path") != BOOTSTRAP_NAME
            or type(descriptor.get("size")) is not int or descriptor["size"] != len(raw)
            or descriptor.get("sha256") != sha256(raw).hexdigest()):
        raise ValueError("invalid handoff helper descriptor or content")
    raw.decode("utf-8")


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
        return payloads, None  # Handoff remains optional; Task binding is always mandatory.
    if manifest.entrypoint in {item.relative_path for item in metadata}:
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
            or environment["format_version"] not in (2, 3)
            or environment.get("bundle_type") != "Task"
        ):
            raise ValueError("invalid environment document")
        expected = {prefix + name for name in handoff_names(environment)}
        if set(content) != expected or len(metadata) != len(expected):
            raise ValueError("handoff inventory differs from its version")
        validate_bootstrap(environment, content.get(prefix + BOOTSTRAP_NAME))
        # Supplementary metadata must agree, but cannot replace the manifest.
        if environment.get("repository_context") != {
            "repo_id": str(manifest.repo_id),
            "base_commit": str(manifest.base_commit),
            "state_fingerprint": manifest.state_fingerprint,
            "fingerprint_algorithm": manifest.fingerprint_algorithm,
        }:
            raise ValueError("handoff does not match task.json")
    except (UnicodeError, ValueError, RecursionError, KeyError) as exc:
        raise task_bundle_error("invalid patch handoff metadata") from exc
    return (
        tuple(payload for payload in payloads if payload not in metadata),
        BundleHandoff(content[prefix + CHAT_INSTRUCTIONS_NAME], content[prefix + ENVIRONMENT_NAME],
                      content.get(prefix + BOOTSTRAP_NAME)),
    )
