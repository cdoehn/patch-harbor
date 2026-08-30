"""Persistent content identity and processing state for Exchange files."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
import json
import os
from pathlib import Path

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
_FORMAT_VERSION = 2
_DOCUMENT_FIELDS = frozenset({"entries", "format_version"})
_LEGACY_ENTRY_FIELDS = frozenset(
    {"attempted", "kind", "manifest", "path", "sha256"}
)
_ENTRY_FIELDS = frozenset(
    {"apply_status", "kind", "manifest", "path", "sha256"}
)
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
        else _ENTRY_FIELDS
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
    path = Path(path_text)
    try:
        return ExchangeStateRecord(
            identity=ExchangeFileIdentity(path=path, sha256=sha256),
            kind=kind,
            manifest=_parse_selection(value["manifest"]),
            apply_status=apply_status,
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
) -> None:
    """Verify and atomically record the start of one automatic apply."""
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
        if record.apply_status is not None:
            raise _error("selected exchange patch was already attempted")
        next_records = tuple(
            replace(candidate, apply_status=ExchangeApplyStatus.ATTEMPTED)
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
        if record.apply_status is not ExchangeApplyStatus.ATTEMPTED:
            raise _error("selected exchange patch has no active attempt")
        next_records = tuple(
            replace(candidate, apply_status=status)
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
