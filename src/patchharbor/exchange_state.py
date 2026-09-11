"""Persistent content identity and processing state for Exchange files."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
import json
import os
from pathlib import Path
from uuid import UUID

from patchharbor.errors import PatchHarborError, patch_package_error
from patchharbor.json_document import serialize_json_document
from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryContext,
    RepositoryId,
)
from patchharbor.patch_manifest import PatchManifest
from patchharbor.platform.errors import describe_os_error
from patchharbor.platform.filesystem import (
    FileChangedDuringRead,
    FileSystemOperationError,
    PathKind,
    UnsupportedFileTypeError,
    atomic_replace_bytes,
    path_kind,
    read_stable_regular_file,
)
from patchharbor.platform.locking import (
    LockOperationError,
    LockUnavailable,
    exclusive_file_lock,
)
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor.user_paths import RegistrationUserPaths


_LEGACY_FORMAT_VERSION = 1
_FORMAT_VERSION = 4
_DOCUMENT_FIELDS = frozenset({"entries", "format_version"})
_LEGACY_ENTRY_FIELDS = frozenset(
    {"attempted", "kind", "manifest", "path", "sha256"}
)
_VERSION_2_ENTRY_FIELDS = frozenset(
    {"apply_status", "kind", "manifest", "path", "sha256"}
)
_VERSION_3_ENTRY_FIELDS = _VERSION_2_ENTRY_FIELDS | {"completed_commit"}
_ENTRY_FIELDS = _VERSION_3_ENTRY_FIELDS | {"attempt_run_id", "result_sha256"}
_MANIFEST_FIELDS = frozenset(
    {
        "base_commit",
        "fingerprint_algorithm",
        "repo_id",
        "state_fingerprint",
    }
)
_ALLOWED_KINDS = frozenset({"other", "patch_package", "result_bundle"})


class ExchangeApplyStatus(str, Enum):
    """Persisted lifecycle state for one automatically selected package."""

    ATTEMPTED = "attempted"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


@dataclass(frozen=True, slots=True, order=True)
class ExchangeFileIdentity:
    """One physical Exchange path plus the complete SHA-256 of its bytes."""

    path: Path
    sha256: str

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("exchange file path must be absolute")
        if not _is_sha256(self.sha256):
            raise ValueError("exchange file identity requires a full SHA-256")


@dataclass(frozen=True, slots=True)
class ExchangePatchSelection:
    """Manifest fields needed to match one package to a repository state."""

    repo_id: RepositoryId
    base_commit: GitObjectId
    state_fingerprint: str
    fingerprint_algorithm: str

    def __post_init__(self) -> None:
        if (
            len(self.state_fingerprint) != 16
            or self.state_fingerprint != self.state_fingerprint.lower()
            or any(
                character not in "0123456789abcdef"
                for character in self.state_fingerprint
            )
        ):
            raise ValueError("exchange selection fingerprint is invalid")
        if self.fingerprint_algorithm != FINGERPRINT_ALGORITHM:
            raise ValueError("exchange selection algorithm is invalid")

    @classmethod
    def from_manifest(cls, manifest: PatchManifest) -> ExchangePatchSelection:
        return cls(
            repo_id=manifest.repo_id,
            base_commit=manifest.base_commit,
            state_fingerprint=manifest.state_fingerprint,
            fingerprint_algorithm=manifest.fingerprint_algorithm,
        )

    def matches_context(self, context: RepositoryContext) -> bool:
        return (
            self.repo_id == context.repo_id
            and self.base_commit == context.base_commit
            and self.state_fingerprint == context.state_fingerprint
            and self.fingerprint_algorithm == context.fingerprint_algorithm
        )


@dataclass(frozen=True, slots=True)
class ExchangeStateRecord:
    """Cached classification and apply lifecycle for one Exchange identity."""

    identity: ExchangeFileIdentity
    kind: str
    manifest: ExchangePatchSelection | None
    apply_status: ExchangeApplyStatus | None = None
    completed_commit: GitObjectId | None = None
    attempt_run_id: str | None = None
    result_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED_KINDS:
            raise ValueError("exchange state kind is invalid")
        if self.apply_status is not None and not isinstance(
            self.apply_status,
            ExchangeApplyStatus,
        ):
            raise ValueError("exchange apply status is invalid")
        if (self.manifest is not None) != (self.kind == "patch_package"):
            raise ValueError("only patch-package state may contain a manifest")
        if self.apply_status is not None and self.kind != "patch_package":
            raise ValueError("only patch-package state may have an apply status")

        if self.attempt_run_id is not None:
            if (self.apply_status is None or type(self.attempt_run_id) is not str
                or not _is_run_id(self.attempt_run_id)):
                raise ValueError("attempt run ID is invalid")
        if self.result_sha256 is not None and (
            not _is_sha256(self.result_sha256) or self.attempt_run_id is None
            or self.apply_status not in {ExchangeApplyStatus.ATTEMPTED, ExchangeApplyStatus.SUCCEEDED}
        ):
            raise ValueError("result digest requires an identified successful or pending attempt")
        if self.completed_commit is not None and (
            self.apply_status is not ExchangeApplyStatus.SUCCEEDED
            or self.manifest is None
            or self.completed_commit.object_format != self.manifest.base_commit.object_format
            or self.completed_commit == self.manifest.base_commit
        ):
            raise ValueError("completion commit requires a successful changed-HEAD apply")

    @property
    def attempted(self) -> bool:
        """Return whether this identity has crossed the apply-start boundary."""
        return self.apply_status is not None

    def same_classification(self, other: ExchangeStateRecord) -> bool:
        return (
            self.identity == other.identity
            and self.kind == other.kind
            and self.manifest == other.manifest
        )


@dataclass(frozen=True, slots=True)
class ExchangeStateSnapshot:
    """One immutable complete Exchange status document."""

    records: tuple[ExchangeStateRecord, ...] = ()

    def __post_init__(self) -> None:
        identities = [record.identity for record in self.records]
        if len(set(identities)) != len(identities):
            raise ValueError("exchange state contains duplicate identities")

    def record_for(
        self,
        identity: ExchangeFileIdentity,
    ) -> ExchangeStateRecord | None:
        return next(
            (
                record
                for record in self.records
                if record.identity == identity
            ),
            None,
        )


class _DuplicateJsonKey(ValueError):
    pass


def _error(message: str) -> PatchHarborError:
    return patch_package_error(message)


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_run_id(value: str) -> bool:
    try:
        parsed = UUID(value)
        return parsed.version == 4 and str(parsed) == value
    except (ValueError, AttributeError):
        return False


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _reject_non_finite_number(value: str) -> object:
    raise ValueError(f"non-finite JSON number: {value}")


def _require_string(document: dict[str, object], field: str) -> str:
    value = document[field]
    if type(value) is not str:
        raise ValueError(f"exchange state {field} is invalid")
    return value


def _parse_selection(value: object) -> ExchangePatchSelection | None:
    if value is None:
        return None
    if type(value) is not dict or set(value) != _MANIFEST_FIELDS:
        raise ValueError("exchange state manifest is invalid")

    repo_id_text = _require_string(value, "repo_id")
    base_commit_text = _require_string(value, "base_commit")
    state_fingerprint = _require_string(value, "state_fingerprint")
    fingerprint_algorithm = _require_string(value, "fingerprint_algorithm")
    try:
        repo_id = RepositoryId(repo_id_text)
        object_format = GitObjectFormat.for_hex_length(len(base_commit_text))
        base_commit = GitObjectId(base_commit_text, object_format)
        return ExchangePatchSelection(
            repo_id=repo_id,
            base_commit=base_commit,
            state_fingerprint=state_fingerprint,
            fingerprint_algorithm=fingerprint_algorithm,
        )
    except ValueError as exc:
        raise ValueError("exchange state manifest is invalid") from exc


def _parse_apply_status(value: object) -> ExchangeApplyStatus | None:
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError("exchange state apply status is invalid")
    try:
        return ExchangeApplyStatus(value)
    except ValueError as exc:
        raise ValueError("exchange state apply status is invalid") from exc


def _parse_record(value: object, *, format_version: int) -> ExchangeStateRecord:
    expected_fields = (
        _LEGACY_ENTRY_FIELDS
        if format_version == _LEGACY_FORMAT_VERSION
        else _VERSION_2_ENTRY_FIELDS if format_version == 2
        else _VERSION_3_ENTRY_FIELDS if format_version == 3 else _ENTRY_FIELDS
    )
    if type(value) is not dict or set(value) != expected_fields:
        raise ValueError("exchange state entry is invalid")
    path_text = _require_string(value, "path")
    sha256 = _require_string(value, "sha256")
    kind = _require_string(value, "kind")
    if format_version == _LEGACY_FORMAT_VERSION:
        attempted = value["attempted"]
        if type(attempted) is not bool:
            raise ValueError("exchange state attempted flag is invalid")
        apply_status = ExchangeApplyStatus.ATTEMPTED if attempted else None
    else:
        apply_status = _parse_apply_status(value["apply_status"])
    if value.get("completed_commit") is not None and type(value["completed_commit"]) is not str:
        raise ValueError("exchange completed commit is invalid")
    path = Path(path_text)
    try:
        return ExchangeStateRecord(
            identity=ExchangeFileIdentity(path=path, sha256=sha256),
            kind=kind,
            manifest=_parse_selection(value["manifest"]),
            apply_status=apply_status,
            attempt_run_id=value.get("attempt_run_id"),
            result_sha256=value.get("result_sha256"),
            completed_commit=(
                GitObjectId(value["completed_commit"],
                            GitObjectFormat.for_hex_length(len(value["completed_commit"])))
                if type(value.get("completed_commit")) is str else None
            ),
        )
    except ValueError as exc:
        raise ValueError("exchange state entry is invalid") from exc


def _parse_state(content: bytes) -> ExchangeStateSnapshot:
    if content.startswith(b"\xef\xbb\xbf"):
        raise _error("exchange processing state must be UTF-8 without a BOM")
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _error("exchange processing state is not valid UTF-8") from exc
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_number,
        )
    except (json.JSONDecodeError, _DuplicateJsonKey, ValueError) as exc:
        raise _error("exchange processing state is not one valid JSON object") from exc
    if type(document) is not dict or set(document) != _DOCUMENT_FIELDS:
        raise _error("exchange processing state has an invalid schema")
    format_version = document["format_version"]
    if type(format_version) is not int or format_version not in {
        _LEGACY_FORMAT_VERSION,
        2,
        3,
        _FORMAT_VERSION,
    }:
        raise _error("exchange processing state format_version is invalid")
    entries = document["entries"]
    if type(entries) is not list:
        raise _error("exchange processing state entries are invalid")
    try:
        return ExchangeStateSnapshot(
            records=tuple(
                _parse_record(entry, format_version=format_version)
                for entry in entries
            )
        )
    except ValueError as exc:
        raise _error(f"exchange processing state is invalid: {exc}") from exc


def _selection_document(
    selection: ExchangePatchSelection | None,
) -> dict[str, object] | None:
    if selection is None:
        return None
    return {
        "base_commit": str(selection.base_commit),
        "fingerprint_algorithm": selection.fingerprint_algorithm,
        "repo_id": str(selection.repo_id),
        "state_fingerprint": selection.state_fingerprint,
    }


def _encoded_state(snapshot: ExchangeStateSnapshot) -> bytes:
    records = sorted(
        snapshot.records,
        key=lambda record: (
            os.fsencode(os.fspath(record.identity.path)),
            record.identity.sha256.encode("ascii"),
        ),
    )
    return serialize_json_document(
        {
            "entries": [
                {
                    "apply_status": (
                        record.apply_status.value
                        if record.apply_status is not None
                        else None
                    ),
                    "attempt_run_id": record.attempt_run_id,
                    "result_sha256": record.result_sha256,
                    "completed_commit": (str(record.completed_commit)
                                         if record.completed_commit is not None else None),
                    "kind": record.kind,
                    "manifest": _selection_document(record.manifest),
                    "path": os.fspath(record.identity.path),
                    "sha256": record.identity.sha256,
                }
                for record in records
            ],
            "format_version": _FORMAT_VERSION,
        }
    ).encode("utf-8")


def _state_file_kind(path: Path) -> PathKind:
    try:
        kind = path_kind(path)
    except FileSystemOperationError as exc:
        raise _error(
            "cannot inspect exchange processing state: "
            f"{describe_os_error(exc.cause)}"
        ) from exc
    if kind not in {PathKind.MISSING, PathKind.REGULAR_FILE}:
        raise _error("exchange processing state must be a regular file")
    return kind


def _prepare_state_directory(paths: RegistrationUserPaths) -> None:
    directory = paths.exchange_state_directory
    try:
        kind = path_kind(directory)
        if kind is PathKind.MISSING:
            directory.mkdir()
            kind = path_kind(directory)
    except (FileSystemOperationError, OSError) as exc:
        cause = exc.cause if isinstance(exc, FileSystemOperationError) else exc
        raise _error(
            "cannot create exchange processing state directory: "
            f"{describe_os_error(cause)}"
        ) from exc
    if kind is not PathKind.DIRECTORY:
        raise _error("exchange processing state directory is not a directory")


def _load_unlocked(paths: RegistrationUserPaths) -> ExchangeStateSnapshot:
    _prepare_state_directory(paths)
    if _state_file_kind(paths.exchange_state_path) is PathKind.MISSING:
        return ExchangeStateSnapshot()
    try:
        content = read_stable_regular_file(paths.exchange_state_path).content
    except UnsupportedFileTypeError as exc:
        raise _error("exchange processing state must be a regular file") from exc
    except FileChangedDuringRead as exc:
        raise _error(
            "exchange processing state changed while it was being read"
        ) from exc
    except FileSystemOperationError as exc:
        raise _error(
            "cannot read exchange processing state: "
            f"{describe_os_error(exc.cause)}"
        ) from exc
    return _parse_state(content)


def _write_unlocked(
    paths: RegistrationUserPaths,
    snapshot: ExchangeStateSnapshot,
) -> None:
    _prepare_state_directory(paths)
    _state_file_kind(paths.exchange_state_path)
    try:
        atomic_replace_bytes(paths.exchange_state_path, _encoded_state(snapshot))
    except FileSystemOperationError as exc:
        raise _error(
            "cannot write exchange processing state: "
            f"{describe_os_error(exc.cause)}"
        ) from exc


@contextmanager
def _state_lock(paths: RegistrationUserPaths) -> Iterator[None]:
    lock = exclusive_file_lock(paths.exchange_state_lock_path)
    try:
        lock.__enter__()
    except LockUnavailable as exc:
        raise _error("exchange processing state is busy") from exc
    except LockOperationError as exc:
        raise _error(
            f"{exc.operation}: {describe_os_error(exc.cause)}"
        ) from exc
    try:
        yield
    finally:
        lock.__exit__(None, None, None)


def load_exchange_state(
    paths: RegistrationUserPaths,
) -> ExchangeStateSnapshot:
    """Load one complete persistent status snapshot under its own lock."""
    with _state_lock(paths):
        return _load_unlocked(paths)


def merge_exchange_classifications(
    paths: RegistrationUserPaths,
    records: Iterable[ExchangeStateRecord],
) -> ExchangeStateSnapshot:
    """Atomically add classifications without losing apply lifecycle state."""
    pending = tuple(records)
    with _state_lock(paths):
        current = _load_unlocked(paths)
        by_identity = {record.identity: record for record in current.records}
        changed = False
        for candidate in pending:
            existing = by_identity.get(candidate.identity)
            if existing is None:
                by_identity[candidate.identity] = candidate
                changed = True
                continue
            if not existing.same_classification(candidate):
                raise _error(
                    "exchange processing state conflicts with file classification"
                )
        next_snapshot = ExchangeStateSnapshot(tuple(by_identity.values()))
        if changed:
            _write_unlocked(paths, next_snapshot)
        return next_snapshot


def mark_exchange_apply_started(
    paths: RegistrationUserPaths,
    identity: ExchangeFileIdentity,
    selection: ExchangePatchSelection,
    *,
    verify_identity: Callable[[], None],
    retry_failed: bool = False,
    explicitly_selected: bool = False,
    run_id: str | None = None,
) -> None:
    """Verify and atomically record a fresh or deliberate failed retry."""
    with _state_lock(paths):
        verify_identity()
        current = _load_unlocked(paths)
        record = current.record_for(identity)
        if (
            record is None
            or record.kind != "patch_package"
            or record.manifest != selection
        ):
            raise _error(
                "selected exchange patch has no matching processing state"
            )
        retrying_failed = (
            retry_failed
            and record.apply_status is ExchangeApplyStatus.FAILED
        )
        if record.apply_status is not None and not retrying_failed and not explicitly_selected:
            raise _error("selected exchange patch was already attempted")
        next_records = tuple(
            replace(candidate, apply_status=ExchangeApplyStatus.ATTEMPTED, completed_commit=None,
                    attempt_run_id=run_id, result_sha256=None)
            if candidate.identity == identity
            else candidate
            for candidate in current.records
        )
        _write_unlocked(paths, ExchangeStateSnapshot(next_records))


def mark_exchange_apply_finished(
    paths: RegistrationUserPaths,
    identity: ExchangeFileIdentity,
    selection: ExchangePatchSelection,
    status: ExchangeApplyStatus,
    *,
    completed_commit: GitObjectId | None = None,
    run_id: str | None = None,
) -> None:
    """Atomically record the known failed or successful primary apply result."""
    if status not in {
        ExchangeApplyStatus.FAILED,
        ExchangeApplyStatus.SUCCEEDED,
    }:
        raise ValueError("finished exchange apply requires a terminal status")
    with _state_lock(paths):
        current = _load_unlocked(paths)
        record = current.record_for(identity)
        if (
            record is None
            or record.kind != "patch_package"
            or record.manifest != selection
        ):
            raise _error(
                "selected exchange patch has no matching processing state"
            )
        if record.apply_status is not ExchangeApplyStatus.ATTEMPTED or record.attempt_run_id != run_id:
            raise _error("selected exchange patch has no active attempt")
        next_records = tuple(
            replace(candidate, apply_status=status, completed_commit=completed_commit,
                    result_sha256=(candidate.result_sha256 if status is ExchangeApplyStatus.SUCCEEDED else None))
            if candidate.identity == identity
            else candidate
            for candidate in current.records
        )
        _write_unlocked(paths, ExchangeStateSnapshot(next_records))


def mark_exchange_attempted(
    paths: RegistrationUserPaths,
    identity: ExchangeFileIdentity,
    selection: ExchangePatchSelection,
    *,
    verify_identity: Callable[[], None],
) -> None:
    """Compatibility alias for the explicit apply-start transition."""
    mark_exchange_apply_started(
        paths,
        identity,
        selection,
        verify_identity=verify_identity,
    )


def record_exchange_result_digest(
    paths: RegistrationUserPaths,
    identity: ExchangeFileIdentity,
    selection: ExchangePatchSelection,
    *,
    run_id: str,
    result_sha256: str,
) -> None:
    """Pin the exact successful result bytes BEFORE publication in the same ledger.

    A crash cannot make a later downloaded/edited bundle into an execution proof.
    This is not a terminal status; recovery still needs the published ZIP and Git.
    """
    if not _is_sha256(result_sha256) or not _is_run_id(run_id):
        raise ValueError("invalid result receipt")
    with _state_lock(paths):
        current = _load_unlocked(paths)
        record = current.record_for(identity)
        if (record is None or record.manifest != selection
            or record.apply_status is not ExchangeApplyStatus.ATTEMPTED
            or record.attempt_run_id != run_id
            or record.result_sha256 not in {None, result_sha256}):
            raise _error("successful result does not belong to the active attempt")
        _write_unlocked(paths, ExchangeStateSnapshot(tuple(
            replace(item, result_sha256=result_sha256) if item == record else item
            for item in current.records
        )))


def recover_exchange_apply_finished(
    paths: RegistrationUserPaths,
    expected: ExchangeStateRecord,
    completed_commit: GitObjectId,
    *,
    verify_evidence: Callable[[], None],
) -> None:
    """Compare-and-swap a proven orphan while the caller owns the repository lock.

    The callback revalidates files, repository and Git while this state lock is
    held; it must NOT load the ledger recursively. No reset/rollback is performed.
    """
    if (expected.apply_status is not ExchangeApplyStatus.ATTEMPTED
        or expected.attempt_run_id is None or expected.result_sha256 is None):
        raise _error("recovery requires a pinned result for an identified attempt")
    with _state_lock(paths):
        current = _load_unlocked(paths)
        if current.record_for(expected.identity) != expected:
            raise _error("attempt changed before recovery")
        verify_evidence()
        if _load_unlocked(paths) != current:
            raise _error("exchange state changed during recovery proof")
        recovered = replace(expected, apply_status=ExchangeApplyStatus.SUCCEEDED,
                            completed_commit=completed_commit)
        _write_unlocked(paths, ExchangeStateSnapshot(tuple(
            recovered if item == expected else item for item in current.records
        )))
