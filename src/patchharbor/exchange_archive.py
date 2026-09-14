"""Conservative maintenance of already classified top-level Exchange artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchharbor.progress import activity

from patchharbor.archive_evidence import ArchiveEvidence, parse_archive_evidence
from patchharbor.archive_files import archive_verified_file
from patchharbor.archive_git import is_proven_obsolete
from patchharbor.configuration import (
    RepositoryConfiguration, load_configuration, revalidate_exchange_directory,
)
from patchharbor.configuration_context import configuration_paths_for_id
from patchharbor.errors import PatchHarborError
from patchharbor.exchange import (
    ExchangeArtifact, ExchangeArtifactKind, ExchangeScanError, read_exchange_artifact_content,
)
from patchharbor.exchange_paths import ExchangePathPolicyError, require_exchange_outside_registry
from patchharbor.exchange_state import ExchangeApplyStatus, ExchangeFileIdentity, load_exchange_state
from patchharbor.locks import registry_lock
from patchharbor.models import RepositoryId
from patchharbor.platform.archive import open_archive_location
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileSystemOperationError, UnsupportedFileTypeError,
)
from patchharbor.registry import load_registry
from patchharbor.repository import inspect_repository, require_local_repository_identity
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot, locked_repository_context_for_id,
    repository_context_from_snapshot,
)
from patchharbor.user_paths import RegistrationUserPaths
from patchharbor.zip_payloads import ZipPayloadError


# Invalid/unreadable input or an unavailable safety primitive means KEEP. No
# broad BaseException handler: interruption stops immediately without mutation.
_KEEP_ERRORS = (
    PatchHarborError, ExchangeScanError, ExchangePathPolicyError, ZipPayloadError,
    FileChangedDuringRead, FileSystemOperationError, UnsupportedFileTypeError,
    OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError,
)


@dataclass(frozen=True)
class ArchiveMaintenance:
    remaining: tuple[ExchangeArtifact, ...]
    archived: tuple[Path, ...] = ()
    warnings: tuple[str, ...] = ()


def archive_exchange_artifacts(
    artifacts: tuple[ExchangeArtifact, ...],
    *,
    configuration: RepositoryConfiguration,
    paths: RegistrationUserPaths,
    repository_id: RepositoryId,
    excluded_paths: frozenset[Path] = frozenset(),
) -> ArchiveMaintenance:
    """Maintain exactly one repository; shared-directory callers invoke each scope."""
    activity("ARCHIVE", "Evaluate conservative Exchange archival", "heading")
    if not configuration.archive_directory:
        activity("ARCHIVE", "Disabled by configuration; no files moved", "detail")
        return ArchiveMaintenance(artifacts)
    moved: set[ExchangeFileIdentity] = set()
    destinations: list[Path] = []
    warnings: list[str] = []
    try:
        with registry_lock(paths):
            registry = load_registry(paths)
            local = configuration_paths_for_id(repository_id, registry)
            if revalidate_exchange_directory(load_configuration(local)) != configuration:
                return ArchiveMaintenance(artifacts)
            require_exchange_outside_registry(
                configuration.exchange_directory, registry, exchange_must_exist=True,
            )
            # Opening is also a containment/type check, not just mkdir(exist_ok).
            activity("ARCHIVE", f"Open or create checked archive folder: {configuration.archive_directory}")
            location_scope = open_archive_location(
                configuration.exchange_directory, configuration.archive_directory,
            )
            location = location_scope.__enter__()
        try:
            # Fully validate bytes before locking any repository. Grouping only
            # reuses its initial context within this call; no evidence is cached
            # across scans, and every actual move has a fresh final proof.
            pending_results = {
                record.result_sha256 for record in load_exchange_state(paths).records
                if record.apply_status is ExchangeApplyStatus.ATTEMPTED and record.result_sha256
            }
            candidates: dict[RepositoryId, list[tuple[ExchangeArtifact, ArchiveEvidence]]] = {}
            for artifact in artifacts:
                activity("ARCHIVE", f"Examine: {artifact.path.name}")
                if (artifact.kind is ExchangeArtifactKind.OTHER
                    or artifact.path in excluded_paths
                    or artifact.identity.sha256 in pending_results):
                    reason = ("not a bundle" if artifact.kind is ExchangeArtifactKind.OTHER
                              else "explicitly selected patch" if artifact.path in excluded_paths
                              else "Result evidence required by a pending attempt")
                    activity("KEEP", f"{artifact.path.name}: {reason}", "detail")
                    continue
                # A known foreign binding cannot belong to the manual scope.
                if (artifact.selection is not None
                    and artifact.selection.repo_id != repository_id):
                    activity("KEEP", f"{artifact.path.name}: outside repository scope", "detail")
                    continue
                try:
                    raw = read_exchange_artifact_content(
                        artifact, directory=configuration.exchange_directory,
                    )
                    evidence = parse_archive_evidence(raw, artifact.path)
                    if evidence.kind != artifact.kind.value:
                        activity("KEEP", f"{artifact.path.name}: content kind changed", "detail")
                        continue
                    if (artifact.selection is not None
                        and artifact.selection != evidence.selection):
                        activity("KEEP", f"{artifact.path.name}: binding changed", "detail")
                        continue
                    selected_id = evidence.selection.repo_id
                    if selected_id != repository_id:
                        activity("KEEP", f"{artifact.path.name}: outside repository scope", "detail")
                        continue
                    candidates.setdefault(selected_id, []).append((artifact, evidence))
                except _KEEP_ERRORS as exc:
                    activity("KEEP", f"{artifact.path.name}: archival evidence unavailable ({exc})", "detail")
                    continue

            for selected_id, repository_candidates in candidates.items():
                try:
                    with locked_repository_context_for_id(selected_id) as context:
                        if context is None:
                            activity("KEEP", "Repository unavailable; retain its archival candidates", "detail")
                            continue
                        state = load_exchange_state(paths)
                        for artifact, evidence in repository_candidates:
                            try:
                                record = state.record_for(artifact.identity)
                                if not is_proven_obsolete(evidence, context, record):
                                    activity("KEEP", f"{artifact.path.name}: no proof that the bundle is obsolete", "detail")
                                    continue
                                # Hold the existing repository and registry locks
                                # through hash verification and the actual move.
                                with registry_lock(paths):
                                    def verify_eligibility() -> None:
                                        # Exactly one fresh consistency capture
                                        # AFTER the final full-file hash, never a
                                        # reused context or cached ancestry proof.
                                        if (load_registry(paths) != registry
                                            or revalidate_exchange_directory(load_configuration(local)) != configuration
                                            or inspect_repository(context.repository_path.value) != context.repository_path):
                                            raise ValueError("archival repository or configuration changed")
                                        require_local_repository_identity(context.repository_path, selected_id)
                                        observed = repository_context_from_snapshot(
                                            context.repository_path, selected_id,
                                            capture_consistent_repository_snapshot(context.repository_path),
                                        )
                                        latest = load_exchange_state(paths).record_for(artifact.identity)
                                        if (observed != context or latest != record
                                            or not is_proven_obsolete(evidence, observed, latest)):
                                            raise ValueError("archival proof changed before the move")
                                        # Also detect non-cooperating identity or
                                        # configuration changes during Git reads.
                                        if (load_registry(paths) != registry
                                            or load_configuration(local) != configuration):
                                            raise ValueError("archival registration or configuration changed")
                                        require_local_repository_identity(context.repository_path, selected_id)

                                    activity("ARCHIVE", f"Recheck full content and current Git proof before moving: {artifact.path.name}")
                                    destination = archive_verified_file(
                                        location, artifact.identity, verify_eligibility=verify_eligibility,
                                    )
                                    moved.add(artifact.identity)
                                    destinations.append(destination)
                                    activity("ARCHIVE", f"Moved {artifact.path.name} to {destination}", "success")
                            except _KEEP_ERRORS as exc:
                                activity("KEEP", f"{artifact.path.name}: final archival check/move refused ({exc})", "detail")
                                # One invalid/stale/unprovable artifact must not
                                # block unrelated candidates or become a move.
                                continue
                except _KEEP_ERRORS as exc:
                    activity("KEEP", f"Repository unavailable for archival ({exc})", "detail")
                    # Unknown, dirty/unsupported or unavailable repositories are
                    # keep cases. Global maintenance may continue with other IDs.
                    continue
        finally:
            location_scope.__exit__(None, None, None)
    except _KEEP_ERRORS as exc:
        activity("ARCHIVE", f"Archival unavailable; retain unarchived files ({exc})", "warning")
        warnings.append("Exchange archival unavailable; unarchived bundles were left in place")
    activity("ARCHIVE", f"Maintenance complete: {len(destinations)} bundle(s) moved", "success")
    return ArchiveMaintenance(
        tuple(artifact for artifact in artifacts if artifact.identity not in moved),
        tuple(destinations), tuple(warnings),
    )
