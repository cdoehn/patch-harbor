"""Strict, read-only bundle evidence for conservative Exchange maintenance.

Discovery's result marker is deliberately not an archival proof. All snapshot
bytes, metadata and optional handoff documents must agree before Git is queried.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from uuid import UUID

from patchharbor.bundle_handoff import (
    CHAT_INSTRUCTIONS_NAME, ENVIRONMENT_MARKER, MAX_HANDOFF_ENTRY_BYTES,
)
from patchharbor.bundle_names import validate_bundle_suffix
from patchharbor.exchange_state import ExchangePatchSelection
from patchharbor.models import GitObjectFormat, GitObjectId, RepositoryId
from patchharbor.patch_package import resolve_patch_payloads
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.state_fingerprint import state_fingerprint_digest
from patchharbor.zip_payloads import read_zip_payload_bytes


CLEAN_FINGERPRINT = state_fingerprint_digest(
    staged_records=(), unstaged_records=(), untracked_records=(),
)[:16]
_BINDING_FIELDS = {"repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm"}
_MANIFEST_FIELDS = _BINDING_FIELDS | {
    "marker", "format_version", "created_at", "run_id", "dirty", "dry_run",
    "entrypoint_started", "execution_present", "primary_result",
    "result_bundle_status", "base_entries", "untracked_entries",
}
_APPLY_FIELDS = {
    prefix + name for prefix in ("expected_", "actual_")
    for name in ("base_commit", "state_fingerprint", "fingerprint_algorithm")
}
_RECEIPT_FIELDS = {"patch_sha256", "completed_commit"}
_RUN_FIELDS = _BINDING_FIELDS | {
    "run_id", "operation", "dry_run", "started_at", "ended_at", "duration_seconds",
    "repository_resolved", "repository_path", "warnings", "execution_present",
    "primary_result", "result_bundle", "process_exit_code",
}


@dataclass(frozen=True)
class ApplyReceipt:
    """An executed patch's full binding; trust also requires the local ZIP digest."""

    patch_sha256: str
    run_id: str
    expected: ExchangePatchSelection
    completed_commit: GitObjectId


@dataclass(frozen=True)
class ArchiveEvidence:
    """Validated manifest binding and, for clean results, the full blob inventory."""

    kind: str
    selection: ExchangePatchSelection
    base_entries: tuple[tuple[str, str, str], ...] = ()  # path, mode, object ID
    receipt: ApplyReceipt | None = None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate bundle JSON key")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> object:
    raise ValueError("non-finite bundle JSON value")


def _document(content: bytes) -> dict[str, object]:
    if content.startswith(b"\xef\xbb\xbf"):
        raise ValueError("bundle JSON has a BOM")
    result = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object,
                        parse_constant=_invalid_constant)
    if type(result) is not dict:
        raise ValueError("bundle JSON is not an object")
    return result


def _selection(document: dict[str, object]) -> ExchangePatchSelection:
    if any(type(document.get(key)) is not str for key in _BINDING_FIELDS):
        raise ValueError("incomplete bundle binding")
    base = document["base_commit"]
    return ExchangePatchSelection(
        repo_id=RepositoryId(document["repo_id"]),
        base_commit=GitObjectId(base, GitObjectFormat.for_hex_length(len(base))),
        state_fingerprint=document["state_fingerprint"],
        fingerprint_algorithm=document["fingerprint_algorithm"],
    )


def _timestamp(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("invalid bundle timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("bundle timestamp has no timezone")
    return stamp


def _result_evidence(files: dict[str, bytes]) -> ArchiveEvidence:
    manifest = _document(files["manifest.json"])
    context = _document(files["context.json"])
    run = _document(files["logs/run.json"])
    if (
        manifest.get("marker") != "patch-harbor-result-bundle"
        or type(manifest.get("format_version")) is not int
        or manifest["format_version"] != 1
        or set(manifest) not in (_MANIFEST_FIELDS, _MANIFEST_FIELDS | _APPLY_FIELDS,
                                        _MANIFEST_FIELDS | _APPLY_FIELDS | _RECEIPT_FIELDS)
        or set(context) not in (_BINDING_FIELDS | {"dirty", "created_at"},
                                _BINDING_FIELDS | {"dirty", "created_at", "bundle_suffix"})
        or set(run) != _RUN_FIELDS
    ):
        raise ValueError("unsupported or incomplete result schema")
    binding = _selection(manifest)
    if _selection(context) != binding or _selection(run) != binding:
        raise ValueError("inconsistent result binding")
    if (
        manifest["dirty"] is not False or context["dirty"] is not False
        or binding.state_fingerprint != CLEAN_FINGERPRINT
        or files["changes/staged.patch"] != b""
        or files["changes/unstaged.patch"] != b""
        or manifest["untracked_entries"] != []
        or manifest["dry_run"] is not False or run["dry_run"] is not False
        or manifest["primary_result"] != "success"
        or manifest["result_bundle_status"] != "created"
        or run["repository_resolved"] is not True
        or type(run["process_exit_code"]) is not int or run["process_exit_code"] != 0
        or type(run["warnings"]) is not list or run["warnings"]
        or type(run["repository_path"]) is not str
        or not run["repository_path"]
        or run["operation"] not in {"bundle", "apply"}
    ):
        raise ValueError("result is not a clean, completed success")
    validate_bundle_suffix(context.get("bundle_suffix", ""))
    if (context["created_at"] != manifest["created_at"]
        or run["started_at"] != manifest["created_at"]
        or run["run_id"] != manifest["run_id"]):
        raise ValueError("inconsistent result run metadata")
    parsed_id = UUID(manifest["run_id"])
    if parsed_id.version != 4 or str(parsed_id) != manifest["run_id"]:
        raise ValueError("invalid result run ID")
    if _timestamp(run["ended_at"]) < _timestamp(run["started_at"]):
        raise ValueError("invalid run interval")
    if (type(run["duration_seconds"]) not in {int, float}
        or run["duration_seconds"] < 0):
        raise ValueError("invalid run duration")
    execution = run["operation"] == "apply"
    if (
        manifest["entrypoint_started"] is not execution
        or manifest["execution_present"] is not execution
        or run["execution_present"] is not execution
        or ("logs/execution.log" in files) is not execution
        or run["primary_result"] != {
            "kind": "success", "success": True, "patchharbor_error_code": None,
            "entrypoint_started": execution, "entrypoint_exit_code": 0 if execution else None,
            "timed_out": False, "interrupted": False,
        }
        or run["result_bundle"] != {"attempted": True, "status": "created", "error": None}
    ):
        raise ValueError("inconsistent successful execution metadata")
    if (any(type(run["primary_result"][key]) is not bool
            for key in ("success", "entrypoint_started", "timed_out", "interrupted"))
        or type(run["result_bundle"]["attempted"]) is not bool):
        raise ValueError("invalid boolean execution metadata")
    # Reject bool-as-integer aliases in the nested execution record too.
    exit_code = run["primary_result"]["entrypoint_exit_code"]
    if execution and type(exit_code) is not int:
        raise ValueError("invalid entrypoint exit code")
    if execution != (_APPLY_FIELDS <= set(manifest)):
        raise ValueError("inconsistent apply binding fields")
    if execution:
        expected = _selection({
            "repo_id": manifest["repo_id"],
            **{key: manifest["expected_" + key]
               for key in _BINDING_FIELDS - {"repo_id"}},
        })
        if expected.base_commit.object_format != binding.base_commit.object_format:
            raise ValueError("inconsistent expected object format")
        if any(manifest["actual_" + key] != manifest[key]
               for key in _BINDING_FIELDS - {"repo_id"}):
            raise ValueError("inconsistent actual result state")

    receipt = None
    if _RECEIPT_FIELDS <= set(manifest):
        digest = manifest["patch_sha256"]
        if (type(digest) is not str or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("invalid patch package SHA-256")
        completed = manifest["completed_commit"]
        if completed is not None:
            if (type(completed) is not str or not execution
                or completed != str(binding.base_commit)
                or completed == str(expected.base_commit)):
                raise ValueError("inconsistent completion commit")
            receipt = ApplyReceipt(digest, run["run_id"], expected, binding.base_commit)

    expected_files = {"manifest.json", "context.json", "logs/run.json",
                      "changes/staged.patch", "changes/unstaged.patch"}
    if execution:
        expected_files.add("logs/execution.log")
    if "environment.json" in files or CHAT_INSTRUCTIONS_NAME in files:
        for name in ("environment.json", CHAT_INSTRUCTIONS_NAME):
            raw = files[name]
            if not raw or len(raw) > MAX_HANDOFF_ENTRY_BYTES or raw.startswith(b"\xef\xbb\xbf"):
                raise ValueError("invalid result handoff")
            raw.decode("utf-8")
        environment = _document(files["environment.json"])
        if (
            environment.get("marker") != ENVIRONMENT_MARKER
            or type(environment.get("format_version")) is not int
            or environment["format_version"] != 1
            or environment.get("bundle_type") != "Result"
            or environment.get("repository_context") != {
                key: context[key] for key in _BINDING_FIELDS
            }
            or environment.get("run_id") != run["run_id"]
            or environment.get("bundle_suffix") != context.get("bundle_suffix", "")
        ):
            raise ValueError("inconsistent result handoff")
        expected_files.update(("environment.json", CHAT_INSTRUCTIONS_NAME))

    entries = manifest["base_entries"]
    if type(entries) is not list:
        raise ValueError("invalid base inventory")
    inventory: list[tuple[str, str, str]] = []
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"path", "git_mode", "object_id", "size"}:
            raise ValueError("invalid base entry")
        path, mode, object_id = entry["path"], entry["git_mode"], entry["object_id"]
        if type(path) is not str or mode not in {"100644", "100755"}:
            raise ValueError("invalid base path or mode")
        name = "base/" + path
        if name in expected_files:
            raise ValueError("duplicate base entry")
        raw = files[name]
        if type(entry["size"]) is not int or entry["size"] != len(raw):
            raise ValueError("base entry size mismatch")
        GitObjectId(object_id, binding.base_commit.object_format)
        digest = hashlib.new(binding.base_commit.object_format.value)
        digest.update(b"blob " + str(len(raw)).encode("ascii") + b"\0")
        digest.update(raw)
        if digest.hexdigest() != object_id:
            raise ValueError("base blob hash mismatch")
        expected_files.add(name)
        inventory.append((path, mode, object_id))
    if set(files) != expected_files:
        raise ValueError("unaccounted bundle contents")
    return ArchiveEvidence("result_bundle", binding, tuple(sorted(inventory)), receipt)


def parse_archive_evidence(content: bytes, path: Path) -> ArchiveEvidence:
    """Validate complete bytes; errors mean 'keep', never an archival decision."""
    payloads = read_zip_payload_bytes(content)
    files = {item.relative_path: item.content for item in payloads}
    if "manifest.json" in files and "patch.json" in files:
        raise ValueError("ambiguous bundle kind")
    if "manifest.json" in files:
        return _result_evidence(files)
    package = resolve_patch_payloads(payloads, package_path=path, resource_policy=DEFAULT_RESOURCE_POLICY)
    return ArchiveEvidence("patch_package", ExchangePatchSelection.from_manifest(package.manifest))
