from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import stat
import zipfile

import pytest

from patchharbor.bundle_handoff import BundleHandoff
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import GitObjectFormat, GitObjectId
from patchharbor.result_bundle_snapshot import build_result_bundle_snapshot
from patchharbor.result_bundle_writer import write_result_bundle
from tests.run_report_support import successful_bundle_run_report


def _object_id(value: str = "1" * 40) -> GitObjectId:
    return GitObjectId(value=value, object_format=GitObjectFormat.SHA1)


def test_snapshot_bytes_drive_manifest_and_zip_in_canonical_order(
    tmp_path: Path,
) -> None:
    base_contents = {
        "alpha/base.dat": b"alpha\x00bytes\n",
        "zeta/tool.sh": b"#!/bin/sh\nexit 0\n",
    }
    base_modes = {"alpha/base.dat": "100644", "zeta/tool.sh": "100755"}
    base_objects = {"alpha/base.dat": "1" * 40, "zeta/tool.sh": "2" * 40}
    untracked_contents = {
        "artifacts/local.dat": b"local\x00bytes\xff\r\n",
        "tools/local.sh": b"#!/bin/sh\nprintf local\n",
    }
    untracked_modes = {
        "artifacts/local.dat": "100644",
        "tools/local.sh": "100755",
    }
    snapshot = build_result_bundle_snapshot(
        base_entries=(
            (
                path.encode("utf-8"),
                base_modes[path].encode("ascii"),
                _object_id(base_objects[path]),
                memoryview(base_contents[path]),
            )
            for path in reversed(tuple(base_contents))
        ),
        staged_patch=b"staged\x00patch",
        unstaged_patch=b"unstaged\x00patch",
        untracked_entries=(
            (
                path.encode("utf-8"),
                untracked_modes[path].encode("ascii"),
                untracked_contents[path],
            )
            for path in reversed(tuple(untracked_contents))
        ),
    )

    manifest_entries = snapshot.manifest_entries()
    assert [entry["path"] for entry in manifest_entries["base_entries"]] == sorted(
        base_contents, key=lambda path: path.encode("utf-8")
    )
    assert [
        entry["path"] for entry in manifest_entries["untracked_entries"]
    ] == sorted(untracked_contents, key=lambda path: path.encode("utf-8"))
    for entry in manifest_entries["base_entries"]:
        relative_path = entry["path"]
        assert entry == {
            "path": relative_path,
            "git_mode": base_modes[relative_path],
            "object_id": base_objects[relative_path],
            "size": len(base_contents[relative_path]),
        }
    for entry in manifest_entries["untracked_entries"]:
        relative_path = entry["path"]
        content = untracked_contents[relative_path]
        assert entry == {
            "path": relative_path,
            "mode": untracked_modes[relative_path],
            "size": len(content),
            "sha256": sha256(content).hexdigest(),
        }

    destination = tmp_path / "result.zip"
    with destination.open("xb") as bundle_file:
        write_result_bundle(
            bundle_file,
            manifest={},
            context_document={},
        handoff=BundleHandoff(b"contract\n", b"{}\n"),
            run_report=successful_bundle_run_report(
                tmp_path / "repository",
                destination,
            ),
            snapshot=snapshot,
        )

    with zipfile.ZipFile(destination) as archive:
        for relative_path, expected in base_contents.items():
            assert archive.read(f"base/{relative_path}") == expected
        assert archive.read("changes/staged.patch") == b"staged\x00patch"
        assert archive.read("changes/unstaged.patch") == b"unstaged\x00patch"
        for relative_path, expected in untracked_contents.items():
            assert archive.read(f"untracked/{relative_path}") == expected

        base_mode = archive.getinfo("base/zeta/tool.sh").external_attr >> 16
        untracked_mode = (
            archive.getinfo("untracked/tools/local.sh").external_attr >> 16
        )

    assert stat.S_IMODE(base_mode) == 0o755
    assert stat.S_IMODE(untracked_mode) == 0o755


@pytest.mark.parametrize(
    "path",
    (
        b".patchharbor/id",
        b"nested/.GIT/config",
        b"NUL.txt",
    ),
)
def test_snapshot_reuses_repository_path_validation(path: bytes) -> None:
    with pytest.raises(PatchHarborError) as captured:
        build_result_bundle_snapshot(
            base_entries=(),
            staged_patch=b"",
            unstaged_patch=b"",
            untracked_entries=((path, b"100644", b"secret"),),
        )

    assert captured.value.exit_code == ExitCode.UNSUPPORTED_REPOSITORY_STATE


def test_snapshot_rejects_casefold_collisions_across_sources() -> None:
    with pytest.raises(PatchHarborError) as captured:
        build_result_bundle_snapshot(
            base_entries=(
                (b"Readme.txt", b"100644", _object_id(), b"base"),
            ),
            staged_patch=b"",
            unstaged_patch=b"",
            untracked_entries=((b"README.TXT", b"100644", b"local"),),
        )

    assert captured.value.exit_code == ExitCode.UNSUPPORTED_REPOSITORY_STATE


def test_snapshot_rejects_non_regular_file_modes() -> None:
    with pytest.raises(PatchHarborError) as captured:
        build_result_bundle_snapshot(
            base_entries=(),
            staged_patch=b"",
            unstaged_patch=b"",
            untracked_entries=((b"link", b"120000", b"target"),),
        )

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
