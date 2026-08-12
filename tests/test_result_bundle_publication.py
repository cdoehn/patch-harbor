from __future__ import annotations

import errno
from pathlib import Path
from uuid import UUID

import pytest

import patchharbor.result_bundle_publication as publication_module
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.platform.filesystem import FileSystemOperationError
from patchharbor.result_bundle_publication import (
    prepare_result_bundle_publication,
    publish_result_bundle,
)
from patchharbor.result_bundle_snapshot import build_result_bundle_snapshot
from tests.run_report_support import successful_bundle_run_report


def _publish_empty_bundle(final_path: Path) -> None:
    publication = prepare_result_bundle_publication(
        final_path,
        run_id=UUID("12345678-1234-4234-8234-123456789abc"),
    )
    publish_result_bundle(
        publication,
        manifest={},
        context_document={},
        run_report=successful_bundle_run_report(
            final_path.parent / "repository",
            final_path,
        ),
        snapshot=build_result_bundle_snapshot(
            base_entries=(),
            staged_patch=b"",
            unstaged_patch=b"",
            untracked_entries=(),
        ),
    )


def test_publication_preserves_a_temporary_file_it_did_not_create(
    tmp_path: Path,
) -> None:
    final_path = tmp_path / "result.zip"
    publication = prepare_result_bundle_publication(
        final_path,
        run_id=UUID("12345678-1234-4234-8234-123456789abc"),
    )
    publication.temporary_path.write_bytes(b"owned by another process")

    with pytest.raises(PatchHarborError) as captured:
        _publish_empty_bundle(final_path)

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
    assert publication.temporary_path.read_bytes() == b"owned by another process"
    assert not final_path.exists()


def test_publication_cleans_its_temporary_zip_after_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    final_path = tmp_path / "result.zip"
    publication = prepare_result_bundle_publication(
        final_path,
        run_id=UUID("12345678-1234-4234-8234-123456789abc"),
    )

    def fail_cross_device_replace(_source: Path, _target: Path) -> None:
        cause = OSError(errno.EXDEV, "cross-device link")
        raise FileSystemOperationError("cannot replace target", cause)

    monkeypatch.setattr(
        publication_module,
        "replace_path",
        fail_cross_device_replace,
    )

    with pytest.raises(PatchHarborError) as captured:
        _publish_empty_bundle(final_path)

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
    assert not publication.temporary_path.exists()
    assert not final_path.exists()
