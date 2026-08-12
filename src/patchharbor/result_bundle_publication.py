"""Verify, synchronize, and atomically publish one Result Bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
import zipfile

from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    MetadataSyncStatus,
    PathKind,
    path_kind,
    replace_path,
    sync_directory_best_effort,
    sync_regular_file_best_effort,
)
from patchharbor.result_bundle_snapshot import ResultBundleSnapshot
from patchharbor.result_bundle_writer import write_result_bundle


_REQUIRED_RESULT_BUNDLE_ENTRIES = frozenset(
    (
        "manifest.json",
        "context.json",
        "changes/staged.patch",
        "changes/unstaged.patch",
        "logs/run.json",
    )
)


@dataclass(frozen=True)
class ResultBundlePublication:
    """The temporary and final names of one same-directory publication."""

    temporary_path: Path
    final_path: Path


@dataclass(frozen=True)
class PublicationDurability:
    """Best-effort synchronization results without a durability claim."""

    temporary_file: MetadataSyncStatus
    directory_before_replace: MetadataSyncStatus
    directory_after_replace: MetadataSyncStatus


@dataclass(frozen=True)
class PublishedResultBundle:
    """One atomically published Result Bundle and its sync observations."""

    path: Path
    durability: PublicationDurability


def prepare_result_bundle_publication(
    final_path: Path,
    *,
    run_id: UUID,
) -> ResultBundlePublication:
    """Model both names before any bundle bytes are written."""
    temporary_path = final_path.with_name(
        f".{final_path.name}.{run_id}.tmp"
    )
    return ResultBundlePublication(
        temporary_path=temporary_path,
        final_path=final_path,
    )


def _verify_result_bundle(path: Path) -> None:
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            names = archive.namelist()
            if any(
                names.count(name) != 1
                for name in _REQUIRED_RESULT_BUNDLE_ENTRIES
            ):
                raise result_bundle_error(
                    "Result Bundle is missing a required entry"
                )
            if archive.testzip() is not None:
                raise result_bundle_error("Result Bundle failed its CRC check")
    except PatchHarborError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise result_bundle_error("cannot verify the Result Bundle") from exc


def _remove_temporary_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def publish_result_bundle(
    publication: ResultBundlePublication,
    *,
    manifest: dict[str, object],
    context_document: dict[str, object],
    run_document: dict[str, object],
    snapshot: ResultBundleSnapshot,
) -> PublishedResultBundle:
    """Write, verify, best-effort sync, and atomically publish one bundle."""
    try:
        if path_kind(publication.final_path) is not PathKind.MISSING:
            raise result_bundle_error("Result Bundle destination already exists")
        if path_kind(publication.temporary_path) is not PathKind.MISSING:
            raise result_bundle_error("Result Bundle temporary path already exists")

        write_result_bundle(
            publication.temporary_path,
            manifest=manifest,
            context_document=context_document,
            run_document=run_document,
            snapshot=snapshot,
        )
        _verify_result_bundle(publication.temporary_path)
        temporary_file_sync = sync_regular_file_best_effort(
            publication.temporary_path
        )
        directory_before_replace = sync_directory_best_effort(
            publication.temporary_path.parent
        )
        replace_path(
            publication.temporary_path,
            publication.final_path,
        )
        directory_after_replace = sync_directory_best_effort(
            publication.final_path.parent
        )
        return PublishedResultBundle(
            path=publication.final_path,
            durability=PublicationDurability(
                temporary_file=temporary_file_sync,
                directory_before_replace=directory_before_replace,
                directory_after_replace=directory_after_replace,
            ),
        )
    except PatchHarborError:
        raise
    except FileSystemOperationError as exc:
        raise result_bundle_error("cannot publish the Result Bundle") from exc
    except OSError as exc:
        raise result_bundle_error("cannot publish the Result Bundle") from exc
    finally:
        _remove_temporary_file(publication.temporary_path)
