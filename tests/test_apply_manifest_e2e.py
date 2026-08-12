from __future__ import annotations

import json
from pathlib import Path
import stat
import warnings
import zipfile

import pytest

from tests.platform_support import run_cli


pytestmark = pytest.mark.e2e

_VALID_MANIFEST = {
    "marker": "patch-harbor",
    "format_version": 1,
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": "patchharbor-state-v1",
    "entrypoint": "run.sh",
}


def _manifest_bytes(document: dict[str, object] | None = None) -> bytes:
    return json.dumps(
        _VALID_MANIFEST if document is None else document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_package(
    path: Path,
    *,
    manifest: bytes | None = None,
    manifest_name: str = "patch.json",
    manifest_info: zipfile.ZipInfo | None = None,
    duplicate_manifest: bool = False,
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        payload = _manifest_bytes() if manifest is None else manifest
        archive.writestr(manifest_info or manifest_name, payload)
        if duplicate_manifest:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr("patch.json", payload)
        archive.writestr(
            "run.sh",
            "# PATCHHARBOR\nprintf 'executed' > executed.txt\n",
        )
        archive.writestr("files/payload.bin", b"\x00payload\xff")


def _run_dry_run(package: Path, cwd: Path):
    return run_cli(cwd, "apply", "--dry-run", str(package))


def test_dry_run_validates_actual_zip_bytes_without_mutation(
    tmp_path: Path,
) -> None:
    working_directory = tmp_path / "working"
    working_directory.mkdir()
    package = tmp_path / "not-a-zip-extension.data"
    _write_package(package)
    before = package.read_bytes()

    completed = _run_dry_run(package, working_directory)

    assert completed.returncode == 0
    assert package.read_bytes() == before
    assert list(working_directory.iterdir()) == []


def test_dry_run_accepts_a_full_sha256_object_id(tmp_path: Path) -> None:
    manifest = dict(_VALID_MANIFEST)
    manifest["base_commit"] = "a" * 64
    package = tmp_path / "sha256-package"
    _write_package(package, manifest=_manifest_bytes(manifest))

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 0


def test_dry_run_rejects_a_non_zip_despite_zip_extension(tmp_path: Path) -> None:
    package = tmp_path / "patch.zip"
    package.write_bytes(b"not a zip archive")

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


@pytest.mark.parametrize(
    ("manifest_name", "manifest_info"),
    [
        ("files/patch.json", None),
        (
            "patch.json",
            zipfile.ZipInfo("patch.json"),
        ),
        (
            "patch.json",
            zipfile.ZipInfo("patch.json"),
        ),
    ],
    ids=("nested", "directory", "symlink"),
)
def test_dry_run_requires_one_regular_root_manifest(
    tmp_path: Path,
    manifest_name: str,
    manifest_info: zipfile.ZipInfo | None,
    request: pytest.FixtureRequest,
) -> None:
    package = tmp_path / f"{request.node.callspec.id}.zip"
    if request.node.callspec.id == "directory":
        assert manifest_info is not None
        manifest_info.external_attr = (stat.S_IFDIR | 0o755) << 16
    elif request.node.callspec.id == "symlink":
        assert manifest_info is not None
        manifest_info.create_system = 3
        manifest_info.external_attr = (stat.S_IFLNK | 0o777) << 16
    _write_package(
        package,
        manifest_name=manifest_name,
        manifest_info=manifest_info,
    )

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


def test_dry_run_rejects_duplicate_root_manifests(tmp_path: Path) -> None:
    package = tmp_path / "duplicate.zip"
    _write_package(package, duplicate_manifest=True)

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


@pytest.mark.parametrize(
    "manifest",
    [
        b"\xef\xbb\xbf" + _manifest_bytes(),
        b"\xff",
        b"[]",
        b'{"marker":"patch-harbor","marker":"patch-harbor"}',
        b'{"marker":"patch-harbor" // comment\n}',
        _manifest_bytes() + b"{}",
        b'{"marker":NaN}',
    ],
    ids=(
        "bom",
        "invalid-utf8",
        "non-object",
        "duplicate-key",
        "comment",
        "trailing-data",
        "non-finite-number",
    ),
)
def test_dry_run_rejects_invalid_manifest_documents(
    tmp_path: Path,
    manifest: bytes,
    request: pytest.FixtureRequest,
) -> None:
    package = tmp_path / f"{request.node.callspec.id}.zip"
    _write_package(package, manifest=manifest)

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


def _without(field: str) -> dict[str, object]:
    manifest = dict(_VALID_MANIFEST)
    del manifest[field]
    return manifest


def _with(field: str, value: object) -> dict[str, object]:
    manifest = dict(_VALID_MANIFEST)
    manifest[field] = value
    return manifest


@pytest.mark.parametrize(
    "manifest",
    [
        _without("repo_id"),
        {**_VALID_MANIFEST, "extra": "unexpected"},
        _with("marker", 1),
        _with("marker", "PATCH-HARBOR"),
        _with("format_version", True),
        _with("format_version", 1.0),
        _with("format_version", 2),
        _with("repo_id", 1),
        _with("repo_id", "A3F9C2E1-7B4D-4A91-9D2E-5C6F8A1B2C3D"),
        _with("repo_id", "a3f9c2e1-7b4d-1a91-9d2e-5c6f8a1b2c3d"),
        _with("base_commit", 1),
        _with("base_commit", "a" * 39),
        _with("base_commit", "A" * 40),
        _with("base_commit", "g" * 40),
        _with("state_fingerprint", 1),
        _with("state_fingerprint", "a" * 15),
        _with("state_fingerprint", "A" * 16),
        _with("state_fingerprint", "g" * 16),
        _with("fingerprint_algorithm", 1),
        _with("fingerprint_algorithm", "patchharbor-state-v2"),
        _with("entrypoint", 1),
        _with("entrypoint", ""),
        _with("entrypoint", "patch.json"),
    ],
    ids=(
        "missing-field",
        "extra-field",
        "marker-type",
        "marker-value",
        "version-bool",
        "version-float",
        "version-value",
        "repo-id-type",
        "repo-id-uppercase",
        "repo-id-version",
        "base-commit-type",
        "base-commit-abbreviated",
        "base-commit-uppercase",
        "base-commit-non-hex",
        "fingerprint-type",
        "fingerprint-length",
        "fingerprint-uppercase",
        "fingerprint-non-hex",
        "algorithm-type",
        "algorithm-value",
        "entrypoint-type",
        "entrypoint-empty",
        "entrypoint-is-manifest",
    ),
)
def test_dry_run_rejects_manifest_contract_violations(
    tmp_path: Path,
    manifest: dict[str, object],
    request: pytest.FixtureRequest,
) -> None:
    package = tmp_path / f"{request.node.callspec.id}.zip"
    _write_package(package, manifest=_manifest_bytes(manifest))

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


def test_apply_without_dry_run_is_not_available_yet(tmp_path: Path) -> None:
    package = tmp_path / "patch.zip"
    _write_package(package)

    completed = run_cli(tmp_path, "apply", str(package))

    assert completed.returncode == 2
