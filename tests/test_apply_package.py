from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import stat
import warnings
import zipfile

import pytest

import patchharbor.zip_payloads as zip_payloads
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
            archive.writestr(name, content)


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


def test_package_rejects_directory_entries_with_content(tmp_path: Path) -> None:
    package_path = tmp_path / "directory-content.zip"
    _write_package(package_path, entries=(("files/", b"not-empty"),))

    _assert_source_error(package_path)


@pytest.mark.parametrize(
    "entry_type",
    (
        stat.S_IFLNK,
        stat.S_IFCHR,
        stat.S_IFBLK,
        stat.S_IFIFO,
        stat.S_IFSOCK,
    ),
    ids=("symlink", "character-device", "block-device", "fifo", "socket"),
)
def test_package_rejects_special_archive_entries(
    tmp_path: Path,
    entry_type: int,
) -> None:
    special = zipfile.ZipInfo("special.bin")
    special.create_system = 3
    special.external_attr = (entry_type | 0o777) << 16
    package_path = tmp_path / "special.zip"
    _write_package(package_path, entries=((special, b"target"),))

    _assert_source_error(package_path)


@pytest.mark.parametrize(
    "members",
    (
        (("same.bin", b"one"), ("same.bin", b"two")),
        (("Files/data.bin", b"one"), ("files/data.bin", b"two")),
        (("files", b"file"), ("files/data.bin", b"child")),
    ),
    ids=("duplicate", "case-collision", "file-directory-collision"),
)
def test_package_rejects_ambiguous_archive_trees(
    tmp_path: Path,
    members: tuple[tuple[str, bytes], tuple[str, bytes]],
) -> None:
    package_path = tmp_path / "ambiguous.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        _write_package(package_path, entries=members)

    _assert_source_error(package_path)


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


@pytest.mark.parametrize(
    "policy",
    (
        ResourcePolicy(
            warning_bytes=1,
            max_content_bytes=1024,
            max_zip_total_bytes=4096,
            max_zip_entries=2,
        ),
        ResourcePolicy(
            warning_bytes=1,
            max_content_bytes=512,
            max_zip_total_bytes=4096,
        ),
    ),
    ids=("entry-count", "entry-size"),
)
def test_declared_resource_limits_are_enforced_before_acceptance(
    tmp_path: Path,
    policy: ResourcePolicy,
) -> None:
    payload = b"x" * (513 if policy.max_zip_entries == 1_000 else 1)
    package_path = tmp_path / "limited.zip"
    _write_package(package_path, entries=(("payload.bin", payload),))

    _assert_source_error(package_path, policy)


def test_declared_total_resource_limit_is_enforced(tmp_path: Path) -> None:
    manifest = _manifest_bytes()
    payload = b"payload"
    declared_total = len(manifest) + len(_ENTRYPOINT) + len(payload)
    policy = ResourcePolicy(
        warning_bytes=1,
        max_content_bytes=max(len(manifest), len(_ENTRYPOINT), len(payload)),
        max_zip_total_bytes=declared_total - 1,
    )
    package_path = tmp_path / "total.zip"
    _write_package(
        package_path,
        manifest=manifest,
        entries=(("data.bin", payload),),
    )

    _assert_source_error(package_path, policy)


def test_live_read_budget_rejects_underreported_entry_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_path = tmp_path / "misreported.zip"
    _write_package(package_path, entries=(("payload.bin", b"x"),))
    policy = ResourcePolicy(
        warning_bytes=1,
        max_content_bytes=512,
        max_zip_total_bytes=4096,
    )
    original_open = zip_payloads.zipfile.ZipFile.open

    def open_with_extra_bytes(
        archive: zipfile.ZipFile,
        member: str | zipfile.ZipInfo,
        mode: str = "r",
        pwd: bytes | None = None,
        *,
        force_zip64: bool = False,
    ) -> object:
        member_name = (
            member.filename if isinstance(member, zipfile.ZipInfo) else member
        )
        if member_name == "payload.bin":
            return BytesIO(b"x" * 513)
        return original_open(
            archive,
            member,
            mode,
            pwd,
            force_zip64=force_zip64,
        )

    monkeypatch.setattr(
        zip_payloads.zipfile.ZipFile,
        "open",
        open_with_extra_bytes,
    )

    _assert_source_error(package_path, policy)


def test_live_total_budget_rejects_underreported_uncompressed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_path = tmp_path / "misreported-total.zip"
    _write_package(package_path, entries=(("payload.bin", b"x"),))
    declared_total = len(_manifest_bytes()) + len(_ENTRYPOINT) + 1
    policy = ResourcePolicy(
        warning_bytes=1,
        max_content_bytes=1024,
        max_zip_total_bytes=declared_total + 4,
    )
    original_open = zip_payloads.zipfile.ZipFile.open

    def open_with_extra_bytes(
        archive: zipfile.ZipFile,
        member: str | zipfile.ZipInfo,
        mode: str = "r",
        pwd: bytes | None = None,
        *,
        force_zip64: bool = False,
    ) -> object:
        member_name = (
            member.filename if isinstance(member, zipfile.ZipInfo) else member
        )
        if member_name == "payload.bin":
            return BytesIO(b"x" * 6)
        return original_open(
            archive,
            member,
            mode,
            pwd,
            force_zip64=force_zip64,
        )

    monkeypatch.setattr(
        zip_payloads.zipfile.ZipFile,
        "open",
        open_with_extra_bytes,
    )

    _assert_source_error(package_path, policy)


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
