"""Classify files from the shared flat PatchHarbor Exchange directory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import stat

from patchharbor.errors import PatchHarborError
from patchharbor.models import BundlePayload
from patchharbor.patch_package import (
    ValidatedPatchPackage,
    resolve_patch_payloads,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.zip_payloads import ZipPayloadError, read_zip_payloads


_RESULT_BUNDLE_MANIFEST = "manifest.json"
_RESULT_BUNDLE_MARKER = "patch-harbor-result-bundle"
_BROWSER_TEMP_SUFFIXES = (
    ".crdownload",
    ".download",
    ".opdownload",
    ".part",
    ".partial",
    ".tmp",
)


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
    kind: ExchangeArtifactKind
    package: ValidatedPatchPackage | None = None

    def __post_init__(self) -> None:
        package_present = self.package is not None
        if package_present != (self.kind is ExchangeArtifactKind.PATCH_PACKAGE):
            raise ValueError("only Patch Package artifacts may carry a package")


def is_browser_temporary_name(name: str) -> bool:
    """Recognize common incomplete browser-download names."""
    return name.casefold().endswith(_BROWSER_TEMP_SUFFIXES)


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


def classify_exchange_artifact(
    path: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> ExchangeArtifact:
    """Classify one regular file solely from its validated archive content."""
    try:
        payloads = read_zip_payloads(path, policy=resource_policy)
    except ZipPayloadError:
        return ExchangeArtifact(path=path, kind=ExchangeArtifactKind.OTHER)

    if _is_result_bundle(payloads):
        return ExchangeArtifact(
            path=path,
            kind=ExchangeArtifactKind.RESULT_BUNDLE,
        )

    try:
        package = resolve_patch_payloads(
            payloads,
            resource_policy=resource_policy,
            package_path=path,
        )
    except PatchHarborError:
        return ExchangeArtifact(path=path, kind=ExchangeArtifactKind.OTHER)

    return ExchangeArtifact(
        path=path,
        kind=ExchangeArtifactKind.PATCH_PACKAGE,
        package=package,
    )


def scan_exchange_directory(
    directory: Path,
    *,
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> tuple[ExchangeArtifact, ...]:
    """Classify top-level regular non-temporary files without recursion."""
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

    regular_paths.sort(key=lambda path: os.fsencode(path.name))
    return tuple(
        classify_exchange_artifact(path, resource_policy=resource_policy)
        for path in regular_paths
    )
