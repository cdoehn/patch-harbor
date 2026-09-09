"""Resolve one fully prevalidated format-1 patch package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.bundle_paths import BundlePathError, normalize_bundle_path
from patchharbor.bundle_handoff import BundleHandoff, split_patch_handoff
from patchharbor.errors import ExitCode, PatchHarborError, patch_package_error
from patchharbor.models import BundlePayload
from patchharbor.patch_manifest import (
    PATCH_MANIFEST_NAME,
    PatchManifest,
    parse_patch_manifest,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.zip_payloads import (
    NotZipArchiveError,
    ZipPayloadError,
    read_zip_payloads,
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
) -> ValidatedPatchPackage:
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

    manifest = parse_patch_manifest(manifest_payload.content)
    all_payloads = payloads
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
    return ValidatedPatchPackage(
        manifest=manifest,
        entrypoint=entrypoint,
        payloads=payload_tuple,
        warnings=warnings,
        handoff=handoff,
    )


def resolve_patch_package(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ValidatedPatchPackage:
    """Read every ZIP member, then apply format-1 package roles."""
    try:
        payloads = read_zip_payloads(path, policy=resource_policy)
    except NotZipArchiveError as exc:
        raise patch_package_error("patch package is not a ZIP archive") from exc
    except ZipPayloadError as exc:
        raise _unsafe_patch_zip(path, exc) from exc

    return resolve_patch_payloads(
        payloads,
        resource_policy=resource_policy,
        package_path=path,
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
