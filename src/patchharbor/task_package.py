"""Resolve one fully prevalidated format-1 patch package."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from patchharbor.progress import activity

from patchharbor.bundle_paths import BundlePathError, normalize_bundle_path
from patchharbor.bundle_handoff import BundleHandoff, split_task_handoff
from patchharbor.errors import FailureReason, PatchHarborError, task_bundle_error
from patchharbor.models import BundlePayload
from patchharbor.parser import ParsedScript, ScriptFormatError, parse_script
from patchharbor.task_manifest import (
    TASK_MANIFEST_NAME,
    TaskManifest,
    parse_task_manifest,
)
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileReadLimitExceeded, FileSystemOperationError, UnsupportedFileTypeError,
    read_stable_regular_file_with_sha256,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.zip_payloads import (
    NotZipArchiveError,
    ZipPayloadError,
    read_zip_payload_bytes,
    zip_payload_warnings,
)


@dataclass(frozen=True, slots=True)
class ValidatedTaskBundle:
    """One fully read and classified format-1 patch package."""

    manifest: TaskManifest
    entrypoint: BundlePayload
    payloads: tuple[BundlePayload, ...]
    warnings: tuple[str, ...] = ()
    handoff: BundleHandoff | None = None
    package_sha256: str | None = None
    package_size: int | None = None
    entries: tuple[BundlePayload, ...] = ()

    def __post_init__(self) -> None:
        if self.package_sha256 is not None and (
            type(self.package_sha256) is not str or len(self.package_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.package_sha256)
        ):
            raise ValueError("package digest must be a complete lowercase SHA-256")


def _unsafe_patch_zip(path: Path, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"unsafe or unreadable patch ZIP {path}: {detail}",
        FailureReason.SOURCE_ERROR,
    )


def parse_task_entrypoint(entrypoint: BundlePayload) -> ParsedScript:
    """Shared static contract; no interpreter lookup or temporary resources."""
    activity("SCRIPT", f"Parse marker, metadata and MESSAGE blocks: {entrypoint.relative_path}")
    try:
        return parse_script(entrypoint.content.decode("utf-8"))
    except (UnicodeError, ScriptFormatError) as exc:
        raise PatchHarborError(
            "patch package entrypoint is not a valid PatchHarbor script",
            FailureReason.NO_VALID_SCRIPT,
        ) from exc


def resolve_task_payloads(
    payloads: tuple[BundlePayload, ...],
    *,
    resource_policy: ResourcePolicy,
    package_path: Path,
    package_sha256: str | None = None,
    package_size: int | None = None,
) -> ValidatedTaskBundle:
    if any(item.relative_path.casefold() in {"patch.json", "manifest.json"} for item in payloads):
        raise task_bundle_error("legacy or mixed bundle manifest is not a Task Bundle")
    activity("MANIFEST", "Locate regular root task.json")
    manifest_payload = next(
        (
            payload
            for payload in payloads
            if payload.relative_path == TASK_MANIFEST_NAME
        ),
        None,
    )
    if manifest_payload is None:
        raise task_bundle_error(
            "patch package must contain exactly one regular root task.json"
        )

    activity("MANIFEST", "Validate exact schema, marker and full repository binding")
    manifest = parse_task_manifest(manifest_payload.content)
    all_payloads = payloads
    activity("HANDOFF", "Validate passive chat/environment metadata separately from payloads")
    payloads, handoff = split_task_handoff(payloads, manifest)
    try:
        entrypoint_path = normalize_bundle_path(manifest.entrypoint)
    except BundlePathError as exc:
        raise _unsafe_patch_zip(package_path, exc) from exc

    entrypoint: BundlePayload | None = None
    package_payloads: list[BundlePayload] = []
    for payload in payloads:
        if payload is manifest_payload:
            continue
        if payload.relative_path == entrypoint_path:
            entrypoint = payload
        else:
            package_payloads.append(payload)

    if entrypoint is None:
        raise task_bundle_error(
            "task.json entrypoint must reference exactly one regular ZIP entry"
        )

    payload_tuple = tuple(package_payloads)
    warnings = zip_payload_warnings(
        tuple(payload for payload in all_payloads if payload is not manifest_payload),
        policy=resource_policy,
    )
    activity("MANIFEST", f"Validated entrypoint {entrypoint.relative_path} and {len(payload_tuple)} payload(s)", "success")
    return ValidatedTaskBundle(
        manifest=manifest,
        entrypoint=entrypoint,
        payloads=payload_tuple,
        warnings=warnings,
        handoff=handoff,
        package_sha256=package_sha256,
        package_size=package_size,
        entries=all_payloads,
    )


def resolve_task_bundle(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
    expected_identity: os.stat_result | None = None,
) -> ValidatedTaskBundle:
    """Read every ZIP member, then apply format-1 package roles."""
    activity("OPEN", f"Open explicit patch and capture stable content with SHA-256: {path}")
    try:
        target = path.resolve(strict=True) if expected_identity is None else path
        if target.lstat().st_size > resource_policy.max_input_artifact_bytes:
            raise _unsafe_patch_zip(path, "input artifact exceeds the resource limit")
        owned = ({} if expected_identity is None else
                 {'expected_identity': expected_identity, 'max_bytes': resource_policy.max_input_artifact_bytes})
        captured = read_stable_regular_file_with_sha256(
            target, retained_content_limit=resource_policy.max_input_artifact_bytes,
            allow_path_identity_fallback=expected_identity is None, **owned,
        )
        if captured.content is None:
            raise _unsafe_patch_zip(path, "input artifact exceeds the resource limit")
        payloads = read_zip_payload_bytes(captured.content, policy=resource_policy)
    except NotZipArchiveError as exc:
        raise task_bundle_error("patch package is not a ZIP archive") from exc
    except (ZipPayloadError, FileChangedDuringRead, FileReadLimitExceeded, FileSystemOperationError,
            UnsupportedFileTypeError, OSError, RuntimeError, UnicodeError) as exc:
        raise _unsafe_patch_zip(path, exc) from exc

    return resolve_task_payloads(
        payloads,
        resource_policy=resource_policy,
        package_path=path,
        package_sha256=captured.sha256,
        package_size=len(captured.content),
    )


def validate_task_bundle(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> TaskManifest:
    """Validate one complete package and return its typed manifest."""
    return resolve_task_bundle(
        path,
        resource_policy=resource_policy,
    ).manifest
