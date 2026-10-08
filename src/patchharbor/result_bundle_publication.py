"""Verify, synchronize, and atomically publish one Result Bundle."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import secrets
import stat
from typing import BinaryIO, Iterator
from uuid import UUID

from patchharbor.progress import activity

from patchharbor.bundle_handoff import BundleHandoff
from patchharbor.errors import PatchHarborError, result_bundle_error
from patchharbor.identifier_presentation import shorten_identifier
from patchharbor.platform.filesystem import (
    MetadataSyncStatus,
    PathKind,
    path_kind,
    replace_path,
    read_stable_regular_file_with_sha256,
    sync_directory_best_effort,
    sync_regular_file_best_effort,
)
from patchharbor.platform.file_handles import open_regular_nofollow
from patchharbor.result_verification import ResultVerification
from patchharbor.result_bundle_snapshot import ResultBundleSnapshot
from patchharbor.result_reader import read_result_reference
from patchharbor.run_report import RunReport, RunSession
from patchharbor.result_bundle_writer import write_result_bundle
from patchharbor.result_resources import ResultRuntimePayload
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY


@dataclass(frozen=True)
class ResultBundlePublication:
    """The temporary and final names of one same-directory publication."""

    temporary_path: Path
    final_path: Path
    reservation_stat: os.stat_result | None = None
    reservation_token: bytes | None = None

    def __post_init__(self) -> None:
        if (self.reservation_stat is None) != (self.reservation_token is None):
            raise ValueError("Result Bundle reservation is incomplete")

    @property
    def reserved(self) -> bool:
        """Whether PatchHarbor already owns the temporary path."""
        return self.reservation_stat is not None


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


def result_bundle_filename(
    session: RunSession,
    *,
    repository_name: str,
) -> str:
    """Return the human-oriented final filename for one Result Bundle."""
    return (
        f"{repository_name}_Result_{session.filename_timestamp}_"
        f"{shorten_identifier(session.run_id, with_ellipsis=False)}.zip"
    )


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


def reserve_result_bundle_publication(
    final_path: Path,
    *,
    run_id: UUID,
) -> ResultBundlePublication:
    """Exclusively reserve the same-directory temporary path for a later run."""
    activity("RESERVE", f"Reserve Result destination: {final_path}")
    publication = prepare_result_bundle_publication(
        final_path,
        run_id=run_id,
    )
    try:
        if path_kind(publication.final_path) is not PathKind.MISSING:
            raise result_bundle_error("Result Bundle destination already exists")
        reservation_token = secrets.token_bytes(32)
        with publication.temporary_path.open("xb") as destination:
            destination.write(reservation_token)
            destination.flush()
            reservation_stat = os.fstat(destination.fileno())
    except PatchHarborError:
        raise
    except OSError as exc:
        raise result_bundle_error(
            "cannot reserve the Result Bundle temporary path"
        ) from exc
    return ResultBundlePublication(
        temporary_path=publication.temporary_path,
        final_path=publication.final_path,
        reservation_stat=reservation_stat,
        reservation_token=reservation_token,
    )


def _same_regular_file(
    path: Path,
    expected: os.stat_result,
    expected_token: bytes | None = None,
) -> bool:
    try:
        observed = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        return False
    if not stat.S_ISREG(observed.st_mode) or not os.path.samestat(
        observed,
        expected,
    ):
        return False
    if expected_token is None:
        return True
    try:
        with os.fdopen(open_regular_nofollow(path), "rb") as stream:
            opened = os.fstat(stream.fileno())
            return (
                os.path.samestat(observed, opened)
                and stream.read() == expected_token
            )
    except OSError:
        return False


def _require_owned_temporary_file(
    path: Path,
    expected: os.stat_result,
) -> None:
    if not _same_regular_file(path, expected):
        raise result_bundle_error(
            "Result Bundle temporary file changed during publication"
        )


def _remove_owned_temporary_file(
    path: Path,
    expected: os.stat_result | None,
    expected_token: bytes | None = None,
) -> None:
    if expected is None or not _same_regular_file(
        path,
        expected,
        expected_token,
    ):
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def release_result_bundle_publication(
    publication: ResultBundlePublication,
) -> None:
    """Release one unused reservation without touching another process' file."""
    _remove_owned_temporary_file(
        publication.temporary_path,
        publication.reservation_stat,
        publication.reservation_token,
    )


def _verify_result_bundle(path: Path, *, execution_present: bool,
                          expected_identity: os.stat_result | None = None) -> str:
    # The shared bounded read already verifies CRC, names and all versioned
    # inventories. Publication only adds its producer-specific obligations.
    try:
        facts, digest = read_result_reference(path, expected_identity=expected_identity)
    except (PatchHarborError, OSError, RuntimeError, ValueError) as exc:
        raise result_bundle_error(f"Result Bundle integrity verification failed: {exc}") from exc
    if not facts.handoff_present:
        raise result_bundle_error("Result publication requires passive handoff data")
    if facts.primary_result.entrypoint_started != execution_present:
        raise result_bundle_error("Result Bundle execution state changed")
    return digest


@contextmanager
def _publication_destination(
    publication: ResultBundlePublication,
) -> Iterator[tuple[BinaryIO, os.stat_result]]:
    stream: BinaryIO | None = None
    descriptor: int | None = None
    try:
        if publication.reservation_stat is None:
            if path_kind(publication.temporary_path) is not PathKind.MISSING:
                raise result_bundle_error(
                    "Result Bundle temporary path already exists"
                )
            stream = publication.temporary_path.open("xb")
            owned_stat = os.fstat(stream.fileno())
        else:
            descriptor = open_regular_nofollow(publication.temporary_path, writable=True)
            stream = os.fdopen(descriptor, "r+b")
            descriptor = None
            owned_stat = os.fstat(stream.fileno())
            observed = os.lstat(publication.temporary_path)
            if (
                not stat.S_ISREG(observed.st_mode)
                or not os.path.samestat(observed, owned_stat)
                or not os.path.samestat(
                    publication.reservation_stat,
                    owned_stat,
                )
            ):
                raise result_bundle_error(
                    "Result Bundle temporary reservation changed"
                )
            stream.seek(0)
            if stream.read() != publication.reservation_token:
                raise result_bundle_error(
                    "Result Bundle temporary reservation changed"
                )
            stream.seek(0)
            stream.truncate(0)
        yield stream, owned_stat
    except PatchHarborError:
        raise
    except OSError as exc:
        raise result_bundle_error("cannot create the Result Bundle") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if stream is not None:
            stream.close()


def publish_result_bundle(
    publication: ResultBundlePublication,
    *,
    manifest: dict[str, object],
    context_document: dict[str, object],
    handoff: BundleHandoff,
    run_report: RunReport,
    snapshot: ResultBundleSnapshot,
    execution_log: bytes | None = None,
    before_publish: Callable[[str], None] | None = None,
    runtime: ResultRuntimePayload | None = None,
) -> PublishedResultBundle:
    """Write, verify, best-effort sync, and atomically publish one bundle."""
    activity("PUBLISH", f"Prepare atomic Result publication: {publication.final_path}", "heading")
    owned_stat = publication.reservation_stat
    owned_token = publication.reservation_token
    try:
        if path_kind(publication.final_path) is not PathKind.MISSING:
            raise result_bundle_error("Result Bundle destination already exists")

        with _publication_destination(publication) as (
            destination,
            destination_stat,
        ):
            owned_stat = destination_stat
            owned_token = None
            write_result_bundle(
                destination,
                manifest=manifest,
                context_document=context_document,
                handoff=handoff,
                run_report=run_report,
                snapshot=snapshot,
                execution_log=execution_log,
                runtime=runtime,
            )

        def require_owned() -> None:
            _require_owned_temporary_file(publication.temporary_path, owned_stat)

        def synchronize() -> tuple[MetadataSyncStatus, MetadataSyncStatus]:
            file_sync = sync_regular_file_best_effort(
                publication.temporary_path, expected_identity=owned_stat,
            )
            directory_sync = sync_directory_best_effort(publication.temporary_path.parent)
            return file_sync, directory_sync

        verification = ResultVerification(publication.temporary_path,
                                          require_owned=require_owned, synchronize=synchronize)
        activity("VERIFY", "Verify temporary Result structure, required files and CRC")
        digest = verification.run(
            "temporary-result-stable-read",
            lambda: _verify_result_bundle(publication.temporary_path,
                                         execution_present=run_report.execution_present,
                                         expected_identity=owned_stat),
        )
        if before_publish is not None:
            activity("RECEIPT", "Pin verified Result bytes as recovery evidence before publication")
            before_publish(digest)
            require_owned()
        final_digest = verification.run(
            "temporary-result-final-read",
            lambda: read_stable_regular_file_with_sha256(
                publication.temporary_path, retained_content_limit=1,
                allow_path_identity_fallback=True, expected_identity=owned_stat,
                max_bytes=DEFAULT_RESOURCE_POLICY.max_input_artifact_bytes,
            ).sha256,
        )
        if final_digest != digest:
            raise result_bundle_error("Result Bundle bytes changed before publication")
        activity("PUBLISH", f"Publish verified Result atomically: {publication.final_path}")
        replace_path(
            publication.temporary_path,
            publication.final_path,
        )
        directory_after_replace = sync_directory_best_effort(
            publication.final_path.parent
        )
        activity("PUBLISH", f"Result Bundle published: {publication.final_path}", "success")
        return PublishedResultBundle(
            path=publication.final_path,
            durability=PublicationDurability(
                temporary_file=verification.file_sync,
                directory_before_replace=verification.directory_sync,
                directory_after_replace=directory_after_replace,
            ),
        )
    except PatchHarborError:
        raise
    except OSError as exc:
        raise result_bundle_error("cannot publish the Result Bundle") from exc
    finally:
        _remove_owned_temporary_file(
            publication.temporary_path,
            owned_stat,
            owned_token,
        )
