"""Resolve one fully prevalidated format-1 patch package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.progress import activity

from patchharbor.bundle_paths import BundlePathError, normalize_bundle_path
from patchharbor.bundle_handoff import BundleHandoff, split_patch_handoff
from patchharbor.errors import ExitCode, PatchHarborError, patch_package_error
from patchharbor.models import BundlePayload
from patchharbor.patch_manifest import (
    PATCH_MANIFEST_NAME,
    PatchManifest,
    parse_patch_manifest,
)
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileSystemOperationError, UnsupportedFileTypeError,
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
class ValidatedPatchPackage:
    """One fully read and classified format-1 patch package."""

    manifest: PatchManifest
    entrypoint: BundlePayload
    payloads: tuple[BundlePayload, ...]
    warnings: tuple[str, ...] = ()
    handoff: BundleHandoff | None = None
    package_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.package_sha256 is not None and (
            type(self.package_sha256) is not str or len(self.package_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.package_sha256)
        ):
            raise ValueError("package digest must be a complete lowercase SHA-256")


def _unsafe_patch_zip(path: Path, detail: object) -> PatchHarborError:
    return PatchHarborError(
        f"unsafe or unreadable patch ZIP {path}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


def resolve_patch_payloads(
    payloads: tuple[BundlePayload, ...],
    *,
    resource_policy: ResourcePolicy,
    package_path: Path,
    package_sha256: str | None = None,
) -> ValidatedPatchPackage:
    activity("MANIFEST", "Locate regular root patch.json")
    manifest_payload = next(
        (
            payload
            for payload in payloads
            if payload.relative_path == PATCH_MANIFEST_NAME
        ),
        None,
    )
    if manifest_payload is None:
        raise patch_package_error(
            "patch package must contain exactly one regular root patch.json"
        )

    activity("MANIFEST", "Validate exact schema, marker and full repository binding")
    manifest = parse_patch_manifest(manifest_payload.content)
    all_payloads = payloads
    activity("HANDOFF", "Validate passive chat/environment metadata separately from payloads")
    payloads, handoff = split_patch_handoff(payloads, manifest)
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
        raise patch_package_error(
            "patch.json entrypoint must reference exactly one regular ZIP entry"
        )

    payload_tuple = tuple(package_payloads)
    warnings = zip_payload_warnings(
        tuple(payload for payload in all_payloads if payload is not manifest_payload),
        policy=resource_policy,
    )
    activity("MANIFEST", f"Validated entrypoint {entrypoint.relative_path} and {len(payload_tuple)} payload(s)", "success")
    return ValidatedPatchPackage(
        manifest=manifest,
        entrypoint=entrypoint,
        payloads=payload_tuple,
        warnings=warnings,
        handoff=handoff,
        package_sha256=package_sha256,
    )


def resolve_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ValidatedPatchPackage:
    """Read every ZIP member, then apply format-1 package roles."""
    activity("OPEN", f"Open explicit patch and capture stable content with SHA-256: {path}")
    try:
        target = path.resolve(strict=True)
        if target.stat().st_size > resource_policy.max_input_artifact_bytes:
            raise _unsafe_patch_zip(path, "input artifact exceeds the resource limit")
        captured = read_stable_regular_file_with_sha256(
            target, retained_content_limit=resource_policy.max_input_artifact_bytes,
            allow_path_identity_fallback=True,
        )
        if captured.content is None:
            raise _unsafe_patch_zip(path, "input artifact exceeds the resource limit")
        payloads = read_zip_payload_bytes(captured.content, policy=resource_policy)
    except NotZipArchiveError as exc:
        raise patch_package_error("patch package is not a ZIP archive") from exc
    except (ZipPayloadError, FileChangedDuringRead, FileSystemOperationError,
            UnsupportedFileTypeError, OSError, RuntimeError) as exc:
        raise _unsafe_patch_zip(path, exc) from exc

    return resolve_patch_payloads(
        payloads,
        resource_policy=resource_policy,
        package_path=path,
        package_sha256=captured.sha256,
    )


def validate_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> PatchManifest:
    """Validate one complete package and return its typed manifest."""
    return resolve_patch_package(
        path,
        resource_policy=resource_policy,
    ).manifest
