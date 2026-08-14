from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import stat
import warnings
import zipfile

import pytest

from patchharbor.patch_manifest import PATCH_FORMAT_VERSION, PATCH_MARKER
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from tests.platform_support import run_cli
from tests.registration_support import (
    create_repository,
    isolated_user_environment,
)


pytestmark = pytest.mark.e2e

_VALID_MANIFEST = {
    "marker": PATCH_MARKER,
    "format_version": PATCH_FORMAT_VERSION,
    "repo_id": "a3f9c2e1-7b4d-4a91-9d2e-5c6f8a1b2c3d",
    "base_commit": "f4e9c2a7b8c9d01234567890abcdef1234567890",
    "state_fingerprint": "a1b2c3d4e5f67890",
    "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
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
    entrypoint: bytes = (
        b"# PATCHHARBOR\n"
        b"printf 'executed' > executed.txt\n"
    ),
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        payload = _manifest_bytes() if manifest is None else manifest
        archive.writestr(
            manifest_info or manifest_name,
            b"" if manifest_info is not None and manifest_info.is_dir() else payload,
        )
        if duplicate_manifest:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr("patch.json", payload)
        archive.writestr("run.sh", entrypoint)
        archive.writestr("files/payload.bin", b"\x00payload\xff")


def _run_dry_run(
    package: Path,
    cwd: Path,
    *,
    environment: dict[str, str] | None = None,
):
    return run_cli(
        cwd,
        "apply",
        "--dry-run",
        str(package),
        environment_overrides=environment,
    )


def _registered_context(
    repository: Path,
    user_root: Path,
) -> tuple[dict[str, str], dict[str, object]]:
    environment = isolated_user_environment(user_root)
    assert run_cli(
        repository,
        "register",
        environment_overrides=environment,
    ).returncode == 0
    completed = run_cli(
        repository,
        "context",
        "--json",
        environment_overrides=environment,
    )
    assert completed.returncode == 0
    envelope = json.loads(completed.stdout)
    result = envelope["result"]
    assert isinstance(result, dict)
    return environment, result


def _manifest_for_context(context: dict[str, object]) -> bytes:
    document = dict(_VALID_MANIFEST)
    document.update(
        {
            "repo_id": context["repo_id"],
            "base_commit": context["base_commit"],
            "state_fingerprint": context["state_fingerprint"],
            "fingerprint_algorithm": context["fingerprint_algorithm"],
        }
    )
    return _manifest_bytes(document)


def test_dry_run_validates_actual_zip_bytes_without_mutation(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _registered_context(repository, tmp_path / "user")
    working_directory = tmp_path / "working"
    working_directory.mkdir()
    package = tmp_path / "not-a-zip-extension.data"
    _write_package(package, manifest=_manifest_for_context(context))
    before = package.read_bytes()

    completed = _run_dry_run(
        package,
        working_directory,
        environment=environment,
    )

    assert completed.returncode == 0
    assert package.read_bytes() == before
    assert list(working_directory.iterdir()) == []
    assert not (repository / "executed.txt").exists()
    assert not (repository / "files" / "payload.bin").exists()


def test_dry_run_never_executes_entrypoint_marker_payload_or_nested_archive(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _registered_context(repository, tmp_path / "user")
    package = tmp_path / "classification.zip"
    nested = BytesIO()
    with zipfile.ZipFile(nested, "w") as archive:
        archive.writestr(
            "nested.sh",
            "# PATCHHARBOR\nprintf nested > nested-ran.txt\n",
        )
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("patch.json", _manifest_for_context(context))
        archive.writestr(
            "run.sh",
            "# PATCHHARBOR\nprintf entrypoint > entrypoint-ran.txt\n",
        )
        archive.writestr(
            "helper.sh",
            "# PATCHHARBOR\nprintf helper > helper-ran.txt\n",
        )
        archive.writestr("nested.zip", nested.getvalue())

    completed = _run_dry_run(
        package,
        tmp_path,
        environment=environment,
    )

    assert completed.returncode == 0
    assert not (repository / "entrypoint-ran.txt").exists()
    assert not (repository / "helper-ran.txt").exists()
    assert not (repository / "nested-ran.txt").exists()



def test_dry_run_rejects_markerless_entrypoint_without_mutation(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path / "repository")
    environment, context = _registered_context(repository, tmp_path / "user")
    package = tmp_path / "markerless.zip"
    _write_package(
        package,
        manifest=_manifest_for_context(context),
        entrypoint=b"printf executed > executed.txt\n",
    )

    caller = tmp_path / "caller"
    caller.mkdir()
    completed = _run_dry_run(
        package,
        caller,
        environment=environment,
    )

    assert completed.returncode == 3
    assert not (repository / "executed.txt").exists()
    assert not (repository / "files" / "payload.bin").exists()


def test_dry_run_accepts_a_full_sha256_object_id(tmp_path: Path) -> None:
    repository = create_repository(
        tmp_path / "repository",
        object_format="sha256",
    )
    environment, context = _registered_context(repository, tmp_path / "user")
    package = tmp_path / "sha256-package"
    _write_package(package, manifest=_manifest_for_context(context))

    completed = _run_dry_run(
        package,
        tmp_path,
        environment=environment,
    )

    assert completed.returncode == 0


def test_dry_run_rejects_a_non_zip_despite_zip_extension(tmp_path: Path) -> None:
    package = tmp_path / "patch.zip"
    package.write_bytes(b"not a zip archive")

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


@pytest.mark.parametrize(
    ("manifest_name", "manifest_info", "expected_exit"),
    [
        ("files/patch.json", None, 10),
        ("patch.json", zipfile.ZipInfo("patch.json/"), 10),
        ("patch.json", zipfile.ZipInfo("patch.json"), 4),
    ],
    ids=("nested", "directory", "symlink"),
)
def test_dry_run_requires_one_regular_root_manifest(
    tmp_path: Path,
    manifest_name: str,
    manifest_info: zipfile.ZipInfo | None,
    expected_exit: int,
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

    assert completed.returncode == expected_exit


def test_dry_run_rejects_duplicate_root_manifests(tmp_path: Path) -> None:
    package = tmp_path / "duplicate.zip"
    _write_package(package, duplicate_manifest=True)

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 4


def test_dry_run_propagates_invalid_manifest_documents(tmp_path: Path) -> None:
    package = tmp_path / "invalid-document.zip"
    duplicate_marker = (
        f'{{"marker":"{PATCH_MARKER}","marker":"{PATCH_MARKER}"}}'
    ).encode("utf-8")
    _write_package(package, manifest=duplicate_marker)

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


def test_dry_run_propagates_closed_manifest_violations(tmp_path: Path) -> None:
    manifest = dict(_VALID_MANIFEST)
    manifest["future_field"] = "not format 1"
    package = tmp_path / "unknown-field.zip"
    _write_package(package, manifest=_manifest_bytes(manifest))

    completed = _run_dry_run(package, tmp_path)

    assert completed.returncode == 10


def test_apply_without_dry_run_is_not_available_yet(tmp_path: Path) -> None:
    package = tmp_path / "patch.zip"
    _write_package(package)

    completed = run_cli(tmp_path, "apply", str(package))

    assert completed.returncode == 2
