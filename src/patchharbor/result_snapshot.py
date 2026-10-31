"""Public snapshot projection on the existing complete, once-captured Result reader."""
from __future__ import annotations

from pathlib import Path

from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.bundle_paths import BundlePathError
from patchharbor.json_document import parse_json_document
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, MAX_RESULT_FILES, ResourcePolicy, ResultSnapshotLimitError
from patchharbor.result_reader import capture_result_payloads
from patchharbor.runtime_profile import RuntimeLimitError
from patchharbor.snapshot_budget import SnapshotBudget
from patchharbor.snapshot_delta import apply_patch, file_value, layer
from patchharbor.snapshot_types import ResultSnapshot, ResultSnapshotError, SnapshotErrorCode, SnapshotRuntime
from patchharbor.zip_payloads import ZipResourceLimitError
from patchharbor.platform.filesystem import FileReadLimitExceeded


def read_result_snapshot(path: Path, *, expected_sha256: str | None = None,
                         resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY) -> ResultSnapshot:
    try:
        captured = capture_result_payloads(path, resource_policy=resource_policy)
    except PatchHarborError as exc:
        cause: BaseException | None = exc
        code = SnapshotErrorCode.INVALID_RESULT
        while cause is not None:
            if isinstance(cause, (ZipResourceLimitError, FileReadLimitExceeded, ResultSnapshotLimitError, RuntimeLimitError)):
                code = SnapshotErrorCode.RESOURCE_LIMIT
                break
            if isinstance(cause, BundlePathError) or (isinstance(cause, PatchHarborError)
                    and cause.reason is FailureReason.UNSUPPORTED_REPOSITORY_STATE):
                code = SnapshotErrorCode.PATH_COLLISION
                break
            cause = cause.__cause__
        raise ResultSnapshotError(code, str(exc)) from exc
    if expected_sha256 is not None and captured.sha256 != expected_sha256:
        raise ResultSnapshotError(SnapshotErrorCode.DIGEST_MISMATCH, 'Result SHA-256 does not match expected bytes')
    facts = captured.facts
    payloads = {p.relative_path: p.content for p in captured.payloads}
    # Already fully validated by the shared reader; this is projection only.
    manifest = parse_json_document(payloads['manifest.json'])
    budget = SnapshotBudget(resource_policy)
    algorithm = facts.context.base_commit.object_format
    base_files = {}
    untracked_files = {}
    for name, mode, _oid in facts.base_entries:
        raw = payloads['base/' + name]
        budget.take(len(raw))
        base_files[name] = file_value(name, mode, raw, algorithm)
    for item in manifest['untracked_entries']:
        name = item['path']
        raw = payloads['untracked/' + name]
        budget.take(len(raw))
        untracked_files[name] = file_value(name, item['mode'], raw, algorithm)
    base = layer('base', base_files)
    untracked = layer('untracked', untracked_files)
    try:
        index = apply_patch(base, payloads['changes/staged.patch'], 'index', algorithm, budget)
        worktree = apply_patch(index, payloads['changes/unstaged.patch'], 'worktree', algorithm, budget)
    except ResultSnapshotError:
        raise
    except (ValueError, OverflowError, UnicodeError) as exc:
        raise ResultSnapshotError(SnapshotErrorCode.INVALID_PATCH, 'invalid reconstruction syntax') from exc
    if untracked.files.keys() & (index.files.keys() | worktree.files.keys()):
        raise ResultSnapshotError(SnapshotErrorCode.PATH_COLLISION, 'untracked file collides with a tracked path')
    if len(worktree.files) + len(untracked.files) > MAX_RESULT_FILES:
        raise ResultSnapshotError(SnapshotErrorCode.RESOURCE_LIMIT, 'too many effective snapshot files')
    effective = layer('effective', {**worktree.files, **untracked.files})
    runtime = facts.runtime
    if runtime is None:
        raise RuntimeError('validated Result 3 lacks runtime facts')
    projection = SnapshotRuntime(runtime.status, runtime.reason, runtime.version, runtime.requires_python,
        runtime.profile, runtime.content_id,
        runtime.artifact.sha256 if runtime.artifact else None,
        runtime.artifact.size if runtime.artifact else None)
    return ResultSnapshot(captured.sha256, facts.format_version, facts.context, facts.run_id,
        facts.operation, facts.dry_run, facts.primary_result, facts.warnings, projection,
        base, index, worktree, untracked, effective)
