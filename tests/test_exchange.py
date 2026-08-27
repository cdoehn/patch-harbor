from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import zipfile

import pytest

import patchharbor.exchange as exchange_module
from patchharbor.errors import PatchHarborError
from patchharbor.exchange import (
    ExchangeArtifactKind,
    ExchangeScanError,
    classify_exchange_artifact,
    materialize_exchange_patch,
    scan_exchange_directory,
)
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor.user_paths import registration_user_paths
from tests.registration_support import set_isolated_user_environment


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


def test_persistent_classification_cache_is_reused_only_for_same_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    patch = tmp_path / "patch.package"
    _write_patch(patch)

    first = scan_exchange_directory(tmp_path, paths=paths)
    assert first[0].kind is ExchangeArtifactKind.PATCH_PACKAGE

    def fail_reclassification(*_args: object, **_kwargs: object):
        raise AssertionError("unchanged identity was reclassified")

    monkeypatch.setattr(exchange_module, "_classify_content", fail_reclassification)
    cached = scan_exchange_directory(tmp_path, paths=paths)
    assert cached[0].identity == first[0].identity
    assert cached[0].package is None

    patch.write_bytes(patch.read_bytes() + b"changed")
    with pytest.raises(AssertionError, match="reclassified"):
        scan_exchange_directory(tmp_path, paths=paths)


def test_selected_patch_is_reopened_and_rejected_after_byte_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    paths = registration_user_paths()
    patch = tmp_path / "patch.package"
    _write_patch(patch)
    selected = scan_exchange_directory(tmp_path, paths=paths)[0]
    original_identity = selected.identity

    patch.write_bytes(patch.read_bytes() + b"replacement")

    with pytest.raises(
        PatchHarborError,
        match="selected exchange patch changed during automatic discovery",
    ):
        materialize_exchange_patch(selected, directory=tmp_path.resolve())

    assert patch.is_file()
    state = exchange_module.load_exchange_state(paths)
    original_record = state.record_for(original_identity)
    assert original_record is not None and original_record.attempted is False


def test_oversized_exchange_file_is_hashed_without_retaining_or_parsing_bytes(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "large-download.bin"
    artifact_path.write_bytes(b"0123456789abcdef")
    policy = ResourcePolicy(
        warning_bytes=4,
        max_input_artifact_bytes=8,
        max_content_bytes=8,
        max_zip_total_bytes=16,
        max_zip_entries=10,
    )

    artifact = classify_exchange_artifact(
        artifact_path,
        resource_policy=policy,
    )

    assert artifact.kind is ExchangeArtifactKind.OTHER
    assert artifact.identity.sha256 == sha256(
        artifact_path.read_bytes()
    ).hexdigest()
