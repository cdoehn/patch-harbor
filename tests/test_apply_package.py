from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import zipfile

import pytest

from patchharbor.patch_package import (
    resolve_patch_package,
    validate_patch_package,
)
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.resource_policy import ResourcePolicy
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM


_VALID_MANIFEST: dict[str, object] = {
    "marker": PATCH_MARKER,
    "format_version": PATCH_FORMAT_VERSION,
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
    "entrypoint": "run.sh",
}
_ENTRYPOINT = b"# PATCHHARBOR\nprintf 'entrypoint' > entrypoint-ran.txt\n"


def _manifest_bytes(
    document: dict[str, object] | None = None,
) -> bytes:
    return json.dumps(
        _VALID_MANIFEST if document is None else document,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_exact_member(
    archive: zipfile.ZipFile,
    member: str | zipfile.ZipInfo,
    content: bytes,
) -> None:
    if isinstance(member, zipfile.ZipInfo):
        archive.writestr(member, content)
        return

    entry = zipfile.ZipInfo("placeholder")
    entry.filename = member
    entry.orig_filename = member
    archive.writestr(entry, content)


def _write_package(
    path: Path,
    *,
    manifest: bytes | None = None,
    entries: tuple[tuple[str | zipfile.ZipInfo, bytes], ...] = (),
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "patch.json",
            _manifest_bytes() if manifest is None else manifest,
        )
        archive.writestr("run.sh", _ENTRYPOINT)
        for name, content in entries:
            _write_exact_member(archive, name, content)


def _assert_source_error(path: Path, policy: ResourcePolicy | None = None) -> None:
    with pytest.raises(PatchHarborError) as captured:
        resolve_patch_package(
            path,
            resource_policy=policy or ResourcePolicy(),
        )
    assert captured.value.exit_code is ExitCode.SOURCE_ERROR


def _nested_zip_bytes() -> bytes:
    destination = BytesIO()
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr("inside.bin", b"\x00nested\xff")
    return destination.getvalue()


def test_manifest_validation_retains_the_typed_manifest_result(
    tmp_path: Path,
) -> None:
    package_path = tmp_path / "patch.zip"
    _write_package(package_path)

    manifest = validate_patch_package(package_path)

    assert manifest.entrypoint == "run.sh"
    assert manifest.repo_id.value == _VALID_MANIFEST["repo_id"]


def test_package_classifies_only_the_manifest_entrypoint_as_executable(
    tmp_path: Path,
) -> None:
    package_path = tmp_path / "patch.data"
    nested_zip = _nested_zip_bytes()
    helper = b"# PATCHHARBOR\nprintf helper > helper-ran.txt\n"
    _write_package(
        package_path,
        entries=(
            ("helper.sh", helper),
            ("files/archive.zip", nested_zip),
            ("files/payload.bin", b"\x00payload\xff"),
        ),
    )

    package = resolve_patch_package(package_path)

    assert package.entrypoint.relative_path == "run.sh"
    assert package.entrypoint.content == _ENTRYPOINT
    assert tuple(item.relative_path for item in package.payloads) == (
        "helper.sh",
        "files/archive.zip",
        "files/payload.bin",
    )
    assert package.payloads[0].content == helper
    assert package.payloads[1].content == nested_zip
    assert package.payloads[2].content == b"\x00payload\xff"


@pytest.mark.parametrize(
    "unsafe_path",
    (
        ".git/config",
        "files/.PATCHHARBOR/id",
        "../escape.bin",
        r"files\payload.bin",
        "C:/payload.bin",
    ),
)
def test_package_rejects_unsafe_and_internal_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    package_path = tmp_path / "unsafe.zip"
    _write_package(package_path, entries=((unsafe_path, b"payload"),))

    _assert_source_error(package_path)


def test_package_rejects_raw_backslash_after_host_normalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_path = tmp_path / "windows-normalized.zip"
    monkeypatch.setattr(zipfile.os, "sep", "\\")
    monkeypatch.setattr(zipfile.os, "altsep", "/")
    _write_package(
        package_path,
        entries=((r"files\payload.bin", b"payload"),),
    )

    _assert_source_error(package_path)


def test_archive_safety_is_checked_before_manifest_roles(
    tmp_path: Path,
) -> None:
    package_path = tmp_path / "unsafe-before-manifest.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("patch.json", b"not-json")
        archive.writestr("run.sh", _ENTRYPOINT)
        archive.writestr("../escape.bin", b"payload")

    with pytest.raises(PatchHarborError) as captured:
        resolve_patch_package(package_path)

    assert captured.value.exit_code is ExitCode.SOURCE_ERROR



@pytest.mark.parametrize(
    "entrypoint",
    (
        "../run.sh",
        r"scripts\run.sh",
        "C:/run.sh",
        ".git/run.sh",
        "scripts/.PATCHHARBOR/run.sh",
    ),
)
def test_manifest_entrypoint_must_be_a_safe_non_internal_path(
    tmp_path: Path,
    entrypoint: str,
) -> None:
    document = dict(_VALID_MANIFEST)
    document["entrypoint"] = entrypoint
    package_path = tmp_path / "unsafe-entrypoint.zip"
    _write_package(package_path, manifest=_manifest_bytes(document))

    _assert_source_error(package_path)


@pytest.mark.parametrize("directory_entrypoint", (False, True))
def test_manifest_entrypoint_must_reference_one_regular_entry(
    tmp_path: Path,
    directory_entrypoint: bool,
) -> None:
    document = dict(_VALID_MANIFEST)
    document["entrypoint"] = "scripts/run.sh"
    package_path = tmp_path / "entrypoint.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("patch.json", _manifest_bytes(document))
        if directory_entrypoint:
            archive.writestr("scripts/run.sh/", b"")

    with pytest.raises(PatchHarborError) as captured:
        resolve_patch_package(package_path)

    assert captured.value.exit_code is ExitCode.PATCH_PACKAGE_ERROR


def test_package_accepts_exact_resource_boundaries(tmp_path: Path) -> None:
    manifest = _manifest_bytes()
    payload = b"payload"
    package_path = tmp_path / "boundary.zip"
    _write_package(
        package_path,
        manifest=manifest,
        entries=(("data.bin", payload),),
    )
    policy = ResourcePolicy(
        warning_bytes=max(len(manifest), len(_ENTRYPOINT), len(payload)),
        max_content_bytes=max(len(manifest), len(_ENTRYPOINT), len(payload)),
        max_zip_total_bytes=len(manifest) + len(_ENTRYPOINT) + len(payload),
        max_zip_entries=3,
    )

    package = resolve_patch_package(package_path, resource_policy=policy)

    assert package.entrypoint.content == _ENTRYPOINT
    assert package.payloads[0].content == payload
    assert package.warnings == ()


def test_large_entry_warnings_are_preserved_on_the_classified_package(
    tmp_path: Path,
) -> None:
    package_path = tmp_path / "warning.zip"
    _write_package(package_path, entries=(("payload.bin", b"12345"),))
    policy = ResourcePolicy(
        warning_bytes=4,
        max_content_bytes=1024,
        max_zip_total_bytes=4096,
    )

    package = resolve_patch_package(package_path, resource_policy=policy)

    assert len(package.warnings) == 2
    assert any("run.sh" in warning for warning in package.warnings)
    assert any("payload.bin" in warning for warning in package.warnings)


def test_patch_digest_covers_exact_zip_bytes_and_not_only_manifest(tmp_path: Path) -> None:
    from hashlib import sha256
    first = tmp_path / "first.zip"
    _write_package(first, entries=(("payload.txt", b"original"),))
    initial = resolve_patch_package(first)
    assert initial.package_sha256 == sha256(first.read_bytes()).hexdigest()
    renamed = tmp_path / "renamed.zip.txt"
    renamed.write_bytes(first.read_bytes())
    assert resolve_patch_package(renamed) == initial
    _write_package(first, entries=(("payload.txt", b"changed!"),))
    changed = resolve_patch_package(first)
    assert changed.manifest == initial.manifest
    assert changed.package_sha256 != initial.package_sha256


def test_parser_and_digest_use_the_same_immutable_package_capture(tmp_path: Path, monkeypatch) -> None:
    from hashlib import sha256
    import patchharbor.patch_package as package_module
    first = tmp_path / "patch.zip"
    _write_package(first, entries=(("payload.txt", b"original"),))
    original_bytes = first.read_bytes()
    original_read = package_module.read_stable_regular_file_with_sha256
    def captured_then_changed(*args, **kwargs):
        captured = original_read(*args, **kwargs)
        _write_package(first, entries=(("payload.txt", b"changed!"),))
        return captured
    monkeypatch.setattr(package_module, "read_stable_regular_file_with_sha256", captured_then_changed)
    package = resolve_patch_package(first)
    assert package.package_sha256 == sha256(original_bytes).hexdigest()
    assert package.payloads[0].content == b"original"
    # Revalidation before mutation, not a second uncorrelated hash here, rejects
    # the replaced source. Existing Apply race tests exercise that boundary.
