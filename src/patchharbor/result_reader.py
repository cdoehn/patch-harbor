"""Read complete format-1 Result facts without imposing archival success policy."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import UUID

from patchharbor.archive_evidence import (
    CLEAN_FINGERPRINT, _APPLY_FIELDS, _BINDING_FIELDS, _MANIFEST_FIELDS,
    _RECEIPT_FIELDS, _RUN_FIELDS, _document, _selection, _timestamp,
)
from patchharbor.bundle_handoff import CHAT_INSTRUCTIONS_NAME, ENVIRONMENT_MARKER, MAX_HANDOFF_ENTRY_BYTES
from patchharbor.bundle_names import validate_bundle_suffix
from patchharbor.bundle_paths import BundlePathError, normalize_bundle_path
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.exchange_state import ExchangePatchSelection
from patchharbor.exit_status import reason_for_exit_code
from patchharbor.models import BundlePayload, GitObjectId, RepositoryId
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileSystemOperationError, UnsupportedFileTypeError,
    read_stable_regular_file_with_sha256,
)
from patchharbor.progress import activity
from patchharbor.repository_paths import RepositoryRelativePath, validate_repository_paths
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.run_report import PrimaryResult, PrimaryResultKind
from patchharbor.zip_payloads import NotZipArchiveError, ZipPayloadError, read_zip_payload_bytes


@dataclass(frozen=True, slots=True)
class ReferenceContext:
    """Recorded context; the foreign repository path is text, never resolved locally."""

    repo_id: RepositoryId
    repository_path: str
    base_commit: GitObjectId
    dirty: bool
    state_fingerprint: str
    fingerprint_algorithm: str


@dataclass(frozen=True, slots=True)
class ResultFacts:
    context: ReferenceContext
    run_id: str
    operation: str
    dry_run: bool
    primary_result: PrimaryResult
    warnings: tuple[str, ...]
    base_entries: tuple[tuple[str, str, str], ...]
    expected: ExchangePatchSelection | None
    patch_sha256: str | None
    completed_commit: GitObjectId | None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _primary(document: object) -> PrimaryResult:
    fields = {"kind", "success", "patchharbor_error_code", "entrypoint_started",
              "entrypoint_exit_code", "timed_out", "interrupted"}
    _require(type(document) is dict and set(document) == fields, "invalid primary result schema")
    kind = PrimaryResultKind(document["kind"])
    code = document["patchharbor_error_code"]
    reason = None if code is None else reason_for_exit_code(code)
    primary = PrimaryResult(kind, document["success"], reason,
                            document["entrypoint_started"], document["entrypoint_exit_code"],
                            document["timed_out"], document["interrupted"])
    _require(primary.success == (kind in (PrimaryResultKind.SUCCESS, PrimaryResultKind.DRY_RUN_SUCCESS)),
             "inconsistent primary success kind")
    if reason is not None:
        _require(PrimaryResultKind.for_tool_error(PatchHarborError("reference", reason)) is kind,
                 "inconsistent primary error kind")
    return primary


def _hex_digest(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def result_member_path(raw_path: str, *, is_directory: bool = False) -> str:
    """Snapshot paths follow repository rules; patch package paths remain unchanged."""
    prefix, separator, relative = raw_path.partition("/")
    if prefix not in ("base", "untracked") or not separator or not relative:
        return normalize_bundle_path(raw_path, is_directory=is_directory)
    if is_directory:
        _require(relative.endswith("/"), "invalid Result directory name")
        relative = relative[:-1]
    try:
        RepositoryRelativePath(relative.encode("utf-8"))
    except (PatchHarborError, UnicodeError) as exc:
        raise BundlePathError("invalid Result snapshot path") from exc
    return prefix + "/" + relative


def _handoff(files: dict[str, bytes], context: dict, run: dict) -> set[str]:
    names = {"environment.json", CHAT_INSTRUCTIONS_NAME}
    if not names.intersection(files):
        return set()
    for name in names:
        raw = files[name]
        _require(bool(raw) and len(raw) <= MAX_HANDOFF_ENTRY_BYTES and not raw.startswith(b"\xef\xbb\xbf"),
                 "invalid result handoff")
        raw.decode("utf-8")
    environment = _document(files["environment.json"])
    _require(environment.get("marker") == ENVIRONMENT_MARKER
             and type(environment.get("format_version")) is int and environment["format_version"] == 1
             and environment.get("bundle_type") == "Result"
             and environment.get("repository_context") == {k: context[k] for k in _BINDING_FIELDS}
             and environment.get("run_id") == run["run_id"]
             and environment.get("bundle_suffix") == context.get("bundle_suffix", ""),
             "inconsistent result handoff")
    if "repository_path" in environment:
        _require(environment["repository_path"] == run["repository_path"], "inconsistent handoff path")
    if "captured_at" in environment:
        _timestamp(environment["captured_at"])
    # Supplementary metadata is never used as a local path or execution input.
    pending = [environment]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
        elif type(value) is float:
            _require(math.isfinite(value), "non-finite handoff value")
    return names


def parse_result_payloads(payloads: tuple[BundlePayload, ...]) -> ResultFacts:
    """Validate ZIP-reader output; neither apply deltas nor infer a live fingerprint."""
    files = {entry.relative_path: entry.content for entry in payloads}
    modes = {entry.relative_path: entry.unix_mode for entry in payloads}
    _require(len(files) == len(payloads), "duplicate result members")
    manifest = _document(files["manifest.json"])
    context = _document(files["context.json"])
    run = _document(files["logs/run.json"])
    _require(manifest.get("marker") == "patch-harbor-result-bundle"
             and type(manifest.get("format_version")) is int and manifest["format_version"] == 1
             and set(manifest) in (_MANIFEST_FIELDS, _MANIFEST_FIELDS | _APPLY_FIELDS,
                                   _MANIFEST_FIELDS | _APPLY_FIELDS | _RECEIPT_FIELDS)
             and set(context) in (_BINDING_FIELDS | {"dirty", "created_at"},
                                  _BINDING_FIELDS | {"dirty", "created_at", "bundle_suffix"})
             and set(run) == _RUN_FIELDS, "unsupported or incomplete result schema")
    binding = _selection(manifest)
    _require(_selection(context) == binding == _selection(run), "inconsistent result binding")
    for doc, fields in ((manifest, ("dirty", "dry_run", "entrypoint_started", "execution_present")),
                        (context, ("dirty",)), (run, ("dry_run", "repository_resolved", "execution_present"))):
        _require(all(type(doc[key]) is bool for key in fields), "invalid result boolean")
    _require(context["dirty"] == manifest["dirty"] and run["dry_run"] == manifest["dry_run"]
             and run["repository_resolved"] and manifest["result_bundle_status"] == "created",
             "inconsistent result status")
    validate_bundle_suffix(context.get("bundle_suffix", ""))
    _require(type(manifest["run_id"]) is str, "invalid run ID")
    identity = UUID(manifest["run_id"])
    _require(identity.version == 4 and str(identity) == manifest["run_id"] == run["run_id"], "invalid run ID")
    _require(context["created_at"] == manifest["created_at"] == run["started_at"], "inconsistent run time")
    _require(_timestamp(run["ended_at"]) >= _timestamp(run["started_at"]), "invalid run interval")
    duration = run["duration_seconds"]
    _require(type(duration) in (int, float) and math.isfinite(duration) and duration >= 0, "invalid duration")
    path = run["repository_path"]
    _require(type(path) is str and "\x00" not in path
             and (PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute()),
             "invalid recorded repository path")
    _require(type(run["warnings"]) is list and all(type(w) is str for w in run["warnings"]), "invalid warnings")
    primary = _primary(run["primary_result"])
    _require(manifest["primary_result"] == primary.kind.value
             and manifest["entrypoint_started"] == manifest["execution_present"]
             == run["execution_present"] == primary.entrypoint_started
             and ("logs/execution.log" in files) == primary.entrypoint_started,
             "inconsistent execution metadata")
    result = run["result_bundle"]
    _require(type(result) is dict and set(result) == {"attempted", "status", "error"}
             and result["attempted"] is True and result["status"] == "created" and result["error"] is None,
             "incomplete publication")
    _require(type(run["process_exit_code"]) is int and run["process_exit_code"] == primary.process_exit_code,
             "inconsistent process status")
    operation = run["operation"]
    _require(operation in ("bundle", "apply"), "unsupported operation")
    if operation == "bundle":
        _require(not run["dry_run"] and not primary.entrypoint_started
                 and primary.kind is PrimaryResultKind.SUCCESS and not _APPLY_FIELDS.intersection(manifest),
                 "inconsistent manual bundle")
    else:
        _require(not run["dry_run"] or not primary.entrypoint_started, "dry-run executed an entrypoint")
        if primary.success:
            _require((run["dry_run"] and primary.kind is PrimaryResultKind.DRY_RUN_SUCCESS)
                     or (not run["dry_run"] and primary.kind is PrimaryResultKind.SUCCESS and primary.entrypoint_started),
                     "inconsistent apply success")

    expected = None
    if _APPLY_FIELDS <= set(manifest):
        expected = _selection({"repo_id": manifest["repo_id"],
                               **{key: manifest["expected_" + key] for key in _BINDING_FIELDS - {"repo_id"}}})
        _require(expected.base_commit.object_format == binding.base_commit.object_format,
                 "inconsistent expected object format")
        _require(all(manifest["actual_" + key] == manifest[key] for key in _BINDING_FIELDS - {"repo_id"}),
                 "inconsistent actual result context")
    completed = None
    digest = manifest.get("patch_sha256")
    if _RECEIPT_FIELDS <= set(manifest):
        _require(_hex_digest(digest), "invalid patch digest")
        if manifest["completed_commit"] is not None:
            _require(type(manifest["completed_commit"]) is str and primary.success and not run["dry_run"]
                     and primary.entrypoint_started and not context["dirty"]
                     and manifest["completed_commit"] == str(binding.base_commit)
                     and str(expected.base_commit) != manifest["completed_commit"], "inconsistent completion commit")
            completed = binding.base_commit

    expected_files = {"manifest.json", "context.json", "logs/run.json", "changes/staged.patch", "changes/unstaged.patch"}
    if primary.entrypoint_started:
        expected_files.add("logs/execution.log")
    expected_files.update(_handoff(files, context, run))
    inventory = []
    repository_paths = []
    for kind in ("base", "untracked"):
        entries = manifest[kind + "_entries"]
        _require(type(entries) is list, "invalid result inventory")
        fields = {"path", "size", "git_mode", "object_id"} if kind == "base" else {"path", "size", "mode", "sha256"}
        for entry in entries:
            _require(type(entry) is dict and set(entry) == fields, "invalid result entry schema")
            name = entry["path"]
            _require(type(name) is str and result_member_path(kind + "/" + name) == kind + "/" + name,
                     "invalid result path")
            repository_paths.append(name.encode("utf-8"))
            member = kind + "/" + name
            _require(member not in expected_files, "duplicate result inventory path")
            raw = files[member]
            _require(type(entry["size"]) is int and entry["size"] == len(raw), "result size mismatch")
            mode = entry["git_mode" if kind == "base" else "mode"]
            _require(type(mode) is str and mode in ("100644", "100755"), "invalid result mode")
            zip_mode = modes[member]
            _require(zip_mode is None or bool(zip_mode & 0o111) == (mode == "100755"), "result mode mismatch")
            if kind == "base":
                oid = GitObjectId(entry["object_id"], binding.base_commit.object_format)
                hashed = hashlib.new(oid.object_format.value, b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw)
                _require(hashed.hexdigest() == str(oid), "base blob hash mismatch")
                inventory.append((name, mode, str(oid)))
            else:
                _require(_hex_digest(entry["sha256"]) and hashlib.sha256(raw).hexdigest() == entry["sha256"],
                         "untracked hash mismatch")
            expected_files.add(member)
    validate_repository_paths(repository_paths)
    _require(set(files) == expected_files, "unaccounted result contents")
    has_changes = bool(files["changes/staged.patch"] or files["changes/unstaged.patch"] or manifest["untracked_entries"])
    _require(context["dirty"] == has_changes, "inconsistent dirty state")
    if not context["dirty"]:
        _require(binding.state_fingerprint == CLEAN_FINGERPRINT, "inconsistent clean fingerprint")
    return ResultFacts(ReferenceContext(binding.repo_id, path, binding.base_commit, context["dirty"],
                                        binding.state_fingerprint, binding.fingerprint_algorithm),
                       run["run_id"], operation, run["dry_run"], primary, tuple(run["warnings"]),
                       tuple(sorted(inventory)), expected, digest, completed)


def read_result_reference(path: Path, *, resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY) -> tuple[ResultFacts, str]:
    """Own one stable byte capture; all reference failures are input errors."""
    activity("REFERENCE", f"Read and validate explicit Result reference: {path}")
    try:
        try:
            target = path.resolve(strict=True)
        except RuntimeError as exc:  # pathlib symlink loops on Python 3.12/3.13
            raise ValueError("cannot resolve Result reference path") from exc
        _require(target.stat().st_size <= resource_policy.max_input_artifact_bytes, "reference exceeds resource limit")
        captured = read_stable_regular_file_with_sha256(
            target, retained_content_limit=resource_policy.max_input_artifact_bytes, allow_path_identity_fallback=True)
        _require(captured.content is not None, "reference exceeds resource limit")
        payloads = read_zip_payload_bytes(captured.content, policy=resource_policy, path_normalizer=result_member_path)
        return parse_result_payloads(payloads), captured.sha256
    except (FileChangedDuringRead, FileSystemOperationError, UnsupportedFileTypeError,
            NotZipArchiveError, ZipPayloadError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, RecursionError, OverflowError, PatchHarborError) as exc:
        raise PatchHarborError(f"invalid Result reference {path}: {exc}", FailureReason.SOURCE_ERROR) from exc
