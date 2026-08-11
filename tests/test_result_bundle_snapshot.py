from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import stat
import zipfile

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import GitObjectFormat, GitObjectId
from patchharbor.result_bundle_snapshot import build_result_bundle_snapshot
from patchharbor.result_bundle_writer import write_result_bundle


def _object_id(value: str = "1" * 40) -> GitObjectId:
    return GitObjectId(value=value, object_format=GitObjectFormat.SHA1)


def test_snapshot_bytes_drive_metadata_and_zip_entries(tmp_path: Path) -> None:
    base_content = memoryview(b"committed\x00bytes\n")
    untracked_content = b"local\x00bytes\xff\r\n"
    snapshot = build_result_bundle_snapshot(
        base_entries=(
            (b"bin/base.dat", b"100644", _object_id(), base_content),
        ),
        staged_patch=b"staged\x00patch",
        unstaged_patch=b"unstaged\x00patch",
        untracked_entries=(
            (b"tools/local.sh", b"100755", untracked_content),
        ),
    )

    base_entry = snapshot.base_entries[0]
    untracked_entry = snapshot.untracked_entries[0]
    assert base_entry.path.original_bytes == b"bin/base.dat"
    assert base_entry.size == len(base_content)
    assert base_entry.git_mode == "100644"
    assert untracked_entry.path.original_bytes == b"tools/local.sh"
    assert untracked_entry.size == len(untracked_content)
    assert untracked_entry.content_sha256 == sha256(untracked_content).hexdigest()
    assert untracked_entry.mode == "100755"

    destination = tmp_path / "result.zip"
    write_result_bundle(
        destination,
        manifest={},
        context_document={},
        run_document={},
        snapshot=snapshot,
    )

    with zipfile.ZipFile(destination) as archive:
        assert archive.read("base/bin/base.dat") == base_content
        assert archive.read("changes/staged.patch") == b"staged\x00patch"
        assert archive.read("changes/unstaged.patch") == b"unstaged\x00patch"
        assert archive.read("untracked/tools/local.sh") == untracked_content
        base_mode = archive.getinfo("base/bin/base.dat").external_attr >> 16
        untracked_mode = (
            archive.getinfo("untracked/tools/local.sh").external_attr >> 16
        )

    assert stat.S_IMODE(base_mode) == 0o644
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
