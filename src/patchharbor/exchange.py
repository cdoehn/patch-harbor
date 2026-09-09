"""Classify files from the shared flat PatchHarbor Exchange directory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import stat

from patchharbor.bundle_names import is_browser_temporary_name
from patchharbor.errors import PatchHarborError, patch_package_error
from patchharbor.exchange_state import (
    ExchangeApplyStatus,
    ExchangeFileIdentity,
    ExchangePatchSelection,
    ExchangeStateRecord,
    load_exchange_state,
    merge_exchange_classifications,
)
from patchharbor.models import BundlePayload
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_payloads,
)
from patchharbor.platform.filesystem import (
    FileChangedDuringRead,
    FileSystemOperationError,
    UnsupportedFileTypeError,
    read_stable_regular_file_with_sha256,
)
from patchharbor.platform.paths import physically_canonicalize
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.user_paths import RegistrationUserPaths
from patchharbor.zip_payloads import ZipPayloadError, read_zip_payload_bytes


_RESULT_BUNDLE_MANIFEST = "manifest.json"
_RESULT_BUNDLE_MARKER = "patch-harbor-result-bundle"


class ExchangeScanError(RuntimeError):
    """The configured Exchange directory could not be scanned safely."""


class ExchangeArtifactKind(str, Enum):
    """Content class relevant to automatic Exchange selection."""

    PATCH_PACKAGE = "patch_package"
    RESULT_BUNDLE = "result_bundle"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ExchangeArtifact:
    """One top-level regular Exchange file classified from its bytes."""

    path: Path
    identity: ExchangeFileIdentity
    mtime_ns: int
    kind: ExchangeArtifactKind
    selection: ExchangePatchSelection | None = None
    apply_status: ExchangeApplyStatus | None = None
    package: ValidatedPatchPackage | None = None

    def __post_init__(self) -> None:
        if isinstance(self.mtime_ns, bool) or not isinstance(self.mtime_ns, int):
            raise ValueError("Exchange artifact mtime_ns must be an integer")
        is_patch = self.kind is ExchangeArtifactKind.PATCH_PACKAGE
        if (self.selection is not None) != is_patch:
            raise ValueError("only Patch Package artifacts carry selection data")
        if self.package is not None:
            if not is_patch or self.selection is None:
                raise ValueError("only Patch Package artifacts may carry a package")
            if (
                ExchangePatchSelection.from_manifest(self.package.manifest)
                != self.selection
            ):
                raise ValueError("Patch Package selection data is inconsistent")
        if self.apply_status is not None and not is_patch:
            raise ValueError("only Patch Package artifacts may have apply status")
        if self.path != self.identity.path:
            raise ValueError("Exchange artifact path and identity disagree")

    @property
    def attempted(self) -> bool:
        """Return whether automatic apply has started for this identity."""
        return self.apply_status is not None


@dataclass(frozen=True, slots=True)
class _ExchangeFileSnapshot:
    identity: ExchangeFileIdentity
    mtime_ns: int
    content: bytes | None


@dataclass(frozen=True, slots=True)
class _ContentClassification:
    kind: ExchangeArtifactKind
    selection: ExchangePatchSelection | None = None
    package: ValidatedPatchPackage | None = None


def _unique_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def _is_result_bundle(payloads: tuple[BundlePayload, ...]) -> bool:
    manifest = next(
        (
            payload
            for payload in payloads
            if payload.relative_path == _RESULT_BUNDLE_MANIFEST
        ),
        None,
    )
    if manifest is None or manifest.content.startswith(b"\xef\xbb\xbf"):
        return False
    try:
        document = json.loads(
            manifest.content.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_json_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return False
    return (
        type(document) is dict
        and document.get("marker") == _RESULT_BUNDLE_MARKER
    )


def _read_exchange_file(
    path: Path,
    *,
    directory: Path,
    resource_policy: ResourcePolicy,
    retained_content_limit: int | None = None,
) -> _ExchangeFileSnapshot:
    if path.parent != directory:
        raise ExchangeScanError("exchange file is outside the configured directory")
    try:
        canonical_before = physically_canonicalize(path, must_exist=True)
        if canonical_before.parent != directory or canonical_before != path:
            raise ExchangeScanError(
                "exchange file changed or resolves outside the configured directory"
            )
        stable_file = read_stable_regular_file_with_sha256(
            path,
            retained_content_limit=(
                resource_policy.max_input_artifact_bytes
                if retained_content_limit is None
                else retained_content_limit
            ),
            allow_path_identity_fallback=True,
        )
        canonical_after = physically_canonicalize(path, must_exist=True)
    except ExchangeScanError:
        raise
    except (
        FileChangedDuringRead,
        UnsupportedFileTypeError,
        FileSystemOperationError,
        OSError,
        RuntimeError,
    ) as exc:
        raise ExchangeScanError(
            "exchange file changed or could not be read safely"
        ) from exc
    if canonical_after != canonical_before:
        raise ExchangeScanError("exchange file changed while it was being read")
    return _ExchangeFileSnapshot(
        identity=ExchangeFileIdentity(
            path=canonical_after,
            sha256=stable_file.sha256,
        ),
        mtime_ns=stable_file.mtime_ns,
        content=stable_file.content,
    )


def _classify_content(
    path: Path,
    content: bytes | None,
    *,
    resource_policy: ResourcePolicy,
) -> _ContentClassification:
    if content is None:
        return _ContentClassification(kind=ExchangeArtifactKind.OTHER)
    try:
        payloads = read_zip_payload_bytes(content, policy=resource_policy)
    except ZipPayloadError:
        return _ContentClassification(kind=ExchangeArtifactKind.OTHER)

    if _is_result_bundle(payloads):
        return _ContentClassification(kind=ExchangeArtifactKind.RESULT_BUNDLE)

    try:
        package = resolve_patch_payloads(
            payloads,
            resource_policy=resource_policy,
            package_path=path,
        )
    except PatchHarborError:
        return _ContentClassification(kind=ExchangeArtifactKind.OTHER)

    return _ContentClassification(
        kind=ExchangeArtifactKind.PATCH_PACKAGE,
        selection=ExchangePatchSelection.from_manifest(package.manifest),
        package=package,
    )


def _artifact_from_record(
    path: Path,
    record: ExchangeStateRecord,
    *,
    mtime_ns: int,
    package: ValidatedPatchPackage | None = None,
) -> ExchangeArtifact:
    return ExchangeArtifact(
        path=path,
        identity=record.identity,
        mtime_ns=mtime_ns,
        kind=ExchangeArtifactKind(record.kind),
        selection=record.manifest,
        apply_status=record.apply_status,
        package=package,
    )


def _record_from_classification(
    snapshot: _ExchangeFileSnapshot,
    classification: _ContentClassification,
) -> ExchangeStateRecord:
    return ExchangeStateRecord(
        identity=snapshot.identity,
        kind=classification.kind.value,
        manifest=classification.selection,
    )


def classify_exchange_artifact(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ExchangeArtifact:
    """Classify one regular file solely from one stable byte capture."""
    try:
        directory = physically_canonicalize(path.parent, must_exist=True)
    except (OSError, RuntimeError) as exc:
        raise ExchangeScanError("cannot resolve exchange directory") from exc
    snapshot = _read_exchange_file(
        path,
        directory=directory,
        resource_policy=resource_policy,
    )
    classification = _classify_content(
        snapshot.identity.path,
        snapshot.content,
        resource_policy=resource_policy,
    )
    return _artifact_from_record(
        snapshot.identity.path,
        _record_from_classification(snapshot, classification),
        mtime_ns=snapshot.mtime_ns,
        package=classification.package,
    )


def _top_level_regular_paths(directory: Path) -> tuple[Path, ...]:
    try:
        with os.scandir(directory) as entries:
            regular_paths: list[Path] = []
            for entry in entries:
                if is_browser_temporary_name(entry.name):
                    continue
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISREG(metadata.st_mode):
                    regular_paths.append(directory / entry.name)
    except OSError as exc:
        raise ExchangeScanError("cannot scan exchange directory") from exc
    regular_paths.sort(key=lambda candidate: os.fsencode(candidate.name))
    return tuple(regular_paths)


def scan_exchange_directory(
    directory: Path,
    *,
    paths: RegistrationUserPaths | None = None,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[ExchangeArtifact, ...]:
    """Classify top-level files with persistent identity and cached content kind."""
    initial_state = (
        load_exchange_state(paths)
        if paths is not None
        else None
    )
    initial_records = (
        {record.identity: record for record in initial_state.records}
        if initial_state is not None
        else {}
    )
    artifacts: list[ExchangeArtifact] = []
    uncached_records: list[ExchangeStateRecord] = []

    for path in _top_level_regular_paths(directory):
        try:
            snapshot = _read_exchange_file(
                path,
                directory=directory,
                resource_policy=resource_policy,
            )
        except ExchangeScanError:
            # One unstable, unreadable, or concurrently changing download is
            # not evidence that the configured directory itself is unusable.
            # Ignore it for this scan; selected patches are re-opened and
            # hash-verified again before any repository mutation.
            continue
        cached = initial_records.get(snapshot.identity)
        if cached is not None:
            artifacts.append(
                _artifact_from_record(
                    path,
                    cached,
                    mtime_ns=snapshot.mtime_ns,
                )
            )
            continue

        classification = _classify_content(
            snapshot.identity.path,
            snapshot.content,
            resource_policy=resource_policy,
        )
        record = _record_from_classification(snapshot, classification)
        uncached_records.append(record)
        artifacts.append(
            _artifact_from_record(
                path,
                record,
                mtime_ns=snapshot.mtime_ns,
                package=classification.package,
            )
        )

    if paths is None:
        return tuple(artifacts)

    current_state = merge_exchange_classifications(paths, uncached_records)
    current_records = {
        record.identity: record for record in current_state.records
    }
    return tuple(
        _artifact_from_record(
            artifact.path,
            current_records.get(artifact.identity)
            or _record_from_artifact(artifact),
            mtime_ns=artifact.mtime_ns,
            package=artifact.package,
        )
        for artifact in artifacts
    )


def _record_from_artifact(artifact: ExchangeArtifact) -> ExchangeStateRecord:
    return ExchangeStateRecord(
        identity=artifact.identity,
        kind=artifact.kind.value,
        manifest=artifact.selection,
        apply_status=artifact.apply_status,
    )


def materialize_exchange_patch(
    artifact: ExchangeArtifact,
    *,
    directory: Path,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ValidatedPatchPackage:
    """Reopen the unique selected identity and require the same valid package."""
    if (
        artifact.kind is not ExchangeArtifactKind.PATCH_PACKAGE
        or artifact.selection is None
    ):
        raise ValueError("only Patch Package artifacts can be materialized")
    try:
        snapshot = _read_exchange_file(
            artifact.path,
            directory=directory,
            resource_policy=resource_policy,
        )
    except ExchangeScanError as exc:
        raise patch_package_error(
            "selected exchange patch changed during automatic discovery"
        ) from exc
    if snapshot.identity != artifact.identity:
        raise patch_package_error(
            "selected exchange patch changed during automatic discovery"
        )
    classification = _classify_content(
        artifact.path,
        snapshot.content,
        resource_policy=resource_policy,
    )
    if (
        classification.kind is not ExchangeArtifactKind.PATCH_PACKAGE
        or classification.selection != artifact.selection
        or classification.package is None
    ):
        raise patch_package_error(
            "selected exchange patch changed during automatic discovery"
        )
    return classification.package


def require_exchange_identity_unchanged(
    identity: ExchangeFileIdentity,
    *,
    directory: Path,
) -> None:
    """Require one selected Exchange path to retain the exact captured bytes."""
    try:
        current = _read_exchange_file(
            identity.path,
            directory=directory,
            resource_policy=DEFAULT_RESOURCE_POLICY,
            retained_content_limit=1,
        )
    except ExchangeScanError as exc:
        raise patch_package_error(
            "selected exchange patch changed before repository mutation"
        ) from exc
    if current.identity != identity:
        raise patch_package_error(
            "selected exchange patch changed before repository mutation"
        )


def read_exchange_artifact_content(artifact: ExchangeArtifact, *, directory: Path) -> bytes:
    """Reopen the exact classified identity for stricter, non-discovery consumers."""
    snapshot = _read_exchange_file(
        artifact.path, directory=directory, resource_policy=DEFAULT_RESOURCE_POLICY,
    )
    if snapshot.identity != artifact.identity or snapshot.content is None:
        raise ExchangeScanError("exchange artifact changed or exceeds the parsing limit")
    return snapshot.content
