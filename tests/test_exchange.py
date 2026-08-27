from __future__ import annotations

import json
import os
from pathlib import Path
import zipfile

import pytest

from patchharbor.exchange import (
    ExchangeArtifactKind,
    ExchangeScanError,
    classify_exchange_artifact,
    scan_exchange_directory,
)
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM


_MANIFEST = {
    "marker": PATCH_MARKER,
    "format_version": PATCH_FORMAT_VERSION,
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
    "entrypoint": "run.sh",
}


def _write_patch(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            json.dumps(_MANIFEST, separators=(",", ":")).encode("utf-8"),
        )
        archive.writestr("run.sh", b"# PATCHHARBOR\nprintf ok\n")


def _write_result_bundle(path: Path, *, include_patch: bool = False) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "marker": "patch-harbor-result-bundle",
                    "format_version": 1,
                },
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        if include_patch:
            archive.writestr(
                "patch.json",
                json.dumps(_MANIFEST, separators=(",", ":")).encode("utf-8"),
            )
            archive.writestr("run.sh", b"# PATCHHARBOR\nprintf unsafe\n")


def test_content_classification_does_not_depend_on_name_or_extension(
    tmp_path: Path,
) -> None:
    patch = tmp_path / "downloaded-file.bin"
    result = tmp_path / "looks-like-a-patch.zip"
    foreign_zip = tmp_path / "foreign.zip"
    direct_script = tmp_path / "direct.sh"
    _write_patch(patch)
    _write_result_bundle(result, include_patch=True)
    with zipfile.ZipFile(foreign_zip, "w") as archive:
        archive.writestr("payload.txt", b"foreign")
    direct_script.write_bytes(b"# PATCHHARBOR\nprintf direct\n")

    patch_artifact = classify_exchange_artifact(patch)
    result_artifact = classify_exchange_artifact(result)
    foreign_artifact = classify_exchange_artifact(foreign_zip)
    direct_artifact = classify_exchange_artifact(direct_script)

    assert patch_artifact.kind is ExchangeArtifactKind.PATCH_PACKAGE
    assert patch_artifact.package is not None
    assert result_artifact.kind is ExchangeArtifactKind.RESULT_BUNDLE
    assert result_artifact.package is None
    assert foreign_artifact.kind is ExchangeArtifactKind.OTHER
    assert direct_artifact.kind is ExchangeArtifactKind.OTHER


def test_flat_scan_skips_temporary_nonregular_and_nested_entries(
    tmp_path: Path,
) -> None:
    patch = tmp_path / "z-patch"
    result = tmp_path / "a-result"
    _write_patch(patch)
    _write_result_bundle(result)

    temporary = tmp_path / "ignored.crdownload"
    _write_patch(temporary)
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_patch(nested / "nested-patch.zip")

    if os.name != "nt":
        (tmp_path / "patch-link").symlink_to(patch)

    artifacts = scan_exchange_directory(tmp_path)

    assert tuple(artifact.path.name for artifact in artifacts) == (
        "a-result",
        "z-patch",
    )
    assert tuple(artifact.kind for artifact in artifacts) == (
        ExchangeArtifactKind.RESULT_BUNDLE,
        ExchangeArtifactKind.PATCH_PACKAGE,
    )


def test_scan_reports_an_unreadable_or_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ExchangeScanError, match="cannot scan exchange directory"):
        scan_exchange_directory(tmp_path / "missing")
