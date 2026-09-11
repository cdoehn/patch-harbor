from __future__ import annotations

from datetime import datetime, timezone
import errno
from pathlib import Path
from uuid import UUID

import pytest

import patchharbor.result_bundle_publication as publication_module
from patchharbor.bundle_handoff import BundleHandoff
from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.platform.filesystem import FileSystemOperationError
from patchharbor.result_bundle_publication import (
    ResultBundlePublication,
    prepare_result_bundle_publication,
    publish_result_bundle,
    release_result_bundle_publication,
    reserve_result_bundle_publication,
    result_bundle_filename,
)
from patchharbor.result_bundle_snapshot import build_result_bundle_snapshot
from patchharbor.run_report import RunSession
from tests.run_report_support import successful_bundle_run_report


def test_result_bundle_filename_starts_with_repository_and_uses_short_run_id() -> None:
    session = RunSession(
        run_id=UUID("12345678-1234-4234-8234-123456789abc"),
        started_at=datetime(2026, 8, 30, 10, 21, 39, tzinfo=timezone.utc),
        started_monotonic=1.0,
    )

    assert result_bundle_filename(
        session,
        repository_name="patch-harbor",
    ) == "patch-harbor_Result_102139_0830_123456.zip"


def _publish(publication: ResultBundlePublication, **options) -> None:
    final_path = publication.final_path
    publish_result_bundle(
        publication,
        manifest={},
        context_document={},
        handoff=BundleHandoff(b"contract\n", b"{}\n"),
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
        **options,
    )


def _publish_empty_bundle(final_path: Path) -> None:
    _publish(
        prepare_result_bundle_publication(
            final_path,
            run_id=UUID("12345678-1234-4234-8234-123456789abc"),
        )
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


def test_reserved_publication_uses_and_consumes_owned_temporary_path(
    tmp_path: Path,
) -> None:
    final_path = tmp_path / "result.zip"
    publication = reserve_result_bundle_publication(
        final_path,
        run_id=UUID("12345678-1234-4234-8234-123456789abc"),
    )

    assert publication.reserved is True
    assert publication.temporary_path.is_file()
    assert publication.temporary_path.stat().st_size > 0

    _publish(publication)

    assert final_path.is_file()
    assert not publication.temporary_path.exists()
    release_result_bundle_publication(publication)
    assert final_path.is_file()


def test_reserved_publication_never_overwrites_a_replaced_temporary_file(
    tmp_path: Path,
) -> None:
    final_path = tmp_path / "result.zip"
    publication = reserve_result_bundle_publication(
        final_path,
        run_id=UUID("12345678-1234-4234-8234-123456789abc"),
    )
    publication.temporary_path.unlink()
    publication.temporary_path.write_bytes(b"replacement")

    with pytest.raises(PatchHarborError) as captured:
        _publish(publication)

    assert captured.value.exit_code == ExitCode.RESULT_BUNDLE_ERROR
    assert publication.temporary_path.read_bytes() == b"replacement"
    assert not final_path.exists()
    release_result_bundle_publication(publication)
    assert publication.temporary_path.read_bytes() == b"replacement"


def test_result_digest_is_pinned_before_atomic_publication(tmp_path: Path) -> None:
    from hashlib import sha256
    final_path = tmp_path / "result.zip"
    publication = prepare_result_bundle_publication(final_path, run_id=UUID("12345678-1234-4234-8234-123456789abc"))
    observed = []
    def pin(digest):
        assert publication.temporary_path.is_file()
        assert not final_path.exists()
        assert digest == sha256(publication.temporary_path.read_bytes()).hexdigest()
        observed.append(digest)
    _publish(publication, before_publish=pin)
    assert observed == [sha256(final_path.read_bytes()).hexdigest()]


@pytest.mark.parametrize("failure", ["write-error", "edited-bytes", "replaced-file"])
def test_receipt_failure_or_late_edit_never_publishes_success(tmp_path: Path, failure: str) -> None:
    from patchharbor.errors import patch_package_error
    final_path = tmp_path / "result.zip"
    publication = prepare_result_bundle_publication(final_path, run_id=UUID("12345678-1234-4234-8234-123456789abc"))
    def pin(_digest):
        if failure == "write-error":
            raise patch_package_error("simulated receipt write failure")
        if failure == "replaced-file":
            # Keep the original inode allocated, even on aggressively reusing FSes.
            publication.temporary_path.rename(tmp_path / "displaced.zip")
        publication.temporary_path.write_bytes(b"changed after hashing")
    with pytest.raises(PatchHarborError):
        _publish(publication, before_publish=pin)
    assert not final_path.exists()
    if failure == "replaced-file":
        assert publication.temporary_path.read_bytes() == b"changed after hashing"
    else:
        assert not publication.temporary_path.exists()
