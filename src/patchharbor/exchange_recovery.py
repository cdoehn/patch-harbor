"""Recover orphaned attempts from locally pinned, fully validated result bytes.

No PID/screen heuristics, no automatic rollback, and no success inference from
an ancestor commit alone. The existing repository lock is the liveness gate.
"""
from __future__ import annotations

from dataclasses import replace

from patchharbor.progress import activity

from patchharbor.archive_evidence import ArchiveEvidence, parse_archive_evidence
from patchharbor.archive_git import is_ancestor, is_proven_result_state
from patchharbor.configuration import (
    UserConfiguration, load_configuration, revalidate_exchange_directory,
)
from patchharbor.errors import PatchHarborError
from patchharbor.exchange import (
    ExchangeArtifact, ExchangeArtifactKind, ExchangeScanError,
    read_exchange_artifact_content,
)
from patchharbor.exchange_paths import ExchangePathPolicyError, require_exchange_outside_registry
from patchharbor.exchange_state import (
    ExchangeApplyStatus, ExchangeStateRecord, load_exchange_state,
    recover_exchange_apply_finished,
)
from patchharbor.locks import registry_lock
from patchharbor.models import RepositoryContext, RepositoryId
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

_KEEP_ERRORS = (
    PatchHarborError, ExchangeScanError, ExchangePathPolicyError, ZipPayloadError,
    FileChangedDuringRead, FileSystemOperationError, UnsupportedFileTypeError,
    OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError,
)


def _matches_receipt(record: ExchangeStateRecord, evidence: ArchiveEvidence) -> bool:
    receipt = evidence.receipt
    return (
        receipt is not None
        and receipt.patch_sha256 == record.identity.sha256
        and receipt.expected == record.manifest
        and receipt.run_id == record.attempt_run_id
        and receipt.completed_commit == evidence.selection.base_commit
    )


def _proven_result(
    record: ExchangeStateRecord, evidence: ArchiveEvidence, context: RepositoryContext,
) -> bool:
    if not _matches_receipt(record, evidence) or not is_proven_result_state(evidence, context):
        return False
    assert record.manifest is not None and evidence.receipt is not None
    return is_ancestor(context.repository_path, record.manifest.base_commit,
                       evidence.receipt.completed_commit)


def recover_exchange_artifacts(
    artifacts: tuple[ExchangeArtifact, ...], *, configuration: UserConfiguration,
    paths: RegistrationUserPaths, repository_id: RepositoryId | None,
) -> tuple[ExchangeArtifact, ...]:
    """Repair only this scan's scope before archival, even when archival is off.

    Results are searched only on the active Exchange level, regardless of file
    name/suffix. A missing, moved, corrupt or contradictory proof means KEEP.
    Legacy attempts have no pinned receipt and cannot be retrospectively proven.
    """
    activity("RECOVERY", "Check locally pinned evidence for interrupted attempts", "heading")
    try:
        snapshot = load_exchange_state(paths)
        pending = tuple(record for record in snapshot.records if (
            record.apply_status is ExchangeApplyStatus.ATTEMPTED
            and record.attempt_run_id is not None and record.result_sha256 is not None
            and record.manifest is not None
            and (repository_id is None or record.manifest.repo_id == repository_id)
        ))
        if not pending:
            activity("RECOVERY", "No in-scope attempted entries with pinned Result evidence", "detail")
            return artifacts
        by_identity = {artifact.identity: artifact for artifact in artifacts}
        results: dict[str, list[ExchangeArtifact]] = {}
        for artifact in artifacts:
            if artifact.kind is ExchangeArtifactKind.RESULT_BUNDLE:
                results.setdefault(artifact.identity.sha256, []).append(artifact)
        with registry_lock(paths):
            if revalidate_exchange_directory(load_configuration(paths)) != configuration:
                return artifacts
            registry = load_registry(paths)
            require_exchange_outside_registry(configuration.exchange_directory, registry,
                                              exchange_must_exist=True)
        changed = False
        for record in pending:
            activity("RECOVERY", f"Examine attempted package: {record.identity.path.name}")
            patch = by_identity.get(record.identity)
            if patch is None or patch.kind is not ExchangeArtifactKind.PATCH_PACKAGE:
                activity("KEEP", f"{record.identity.path.name}: matching patch not available", "detail")
                continue
            if not results.get(record.result_sha256, ()):
                activity("KEEP", f"{patch.path.name}: pinned Result content not available", "detail")
            for result in results.get(record.result_sha256, ()):
                activity("RECOVERY", f"Validate receipt pair: {patch.path.name} + {result.path.name}")
                try:
                    package_evidence = parse_archive_evidence(
                        read_exchange_artifact_content(patch, directory=configuration.exchange_directory),
                        patch.path,
                    )
                    if package_evidence.kind != "patch_package" or package_evidence.selection != record.manifest:
                        activity("KEEP", f"{patch.path.name}: patch proof does not match the recorded binding", "detail")
                        continue
                    evidence = parse_archive_evidence(
                        read_exchange_artifact_content(result, directory=configuration.exchange_directory),
                        result.path,
                    )
                    if not _matches_receipt(record, evidence):
                        activity("KEEP", f"{result.path.name}: receipt does not match the attempt", "detail")
                        continue
                    assert record.manifest is not None and evidence.receipt is not None
                    selected_id = record.manifest.repo_id
                    # A busy repository is not a crash. Acquire the SAME lock as
                    # apply/context; never delete a lock file or inspect screen.
                    activity("RECOVERY", "Acquire real repository lock and verify clean Git/state proof")
                    with locked_repository_context_for_id(selected_id) as context:
                        if context is None or not _proven_result(record, evidence, context):
                            activity("KEEP", f"{patch.path.name}: no current clean repository/result proof", "detail")
                            continue
                        with registry_lock(paths):
                            def verify_evidence() -> None:
                                if (load_registry(paths) != registry
                                    or revalidate_exchange_directory(load_configuration(paths)) != configuration
                                    or inspect_repository(context.repository_path.value) != context.repository_path):
                                    raise ValueError("recovery repository/configuration changed")
                                require_local_repository_identity(context.repository_path, selected_id)
                                # These reads check the full, previously captured
                                # digests again. Edited logs/ZIPs cannot pass.
                                for artifact in (patch, result):
                                    read_exchange_artifact_content(
                                        artifact, directory=configuration.exchange_directory,
                                    )
                                observed = repository_context_from_snapshot(
                                    context.repository_path, selected_id,
                                    capture_consistent_repository_snapshot(context.repository_path),
                                )
                                if observed != context or not _proven_result(record, evidence, observed):
                                    raise ValueError("recovery Git/state proof changed")
                                if (load_registry(paths) != registry or load_configuration(paths) != configuration):
                                    raise ValueError("recovery registration/configuration changed")
                                require_local_repository_identity(context.repository_path, selected_id)

                            recover_exchange_apply_finished(
                                paths, record, evidence.receipt.completed_commit,
                                verify_evidence=verify_evidence,
                            )
                            changed = True
                            activity("RECOVERY", f"{patch.path.name}: proven attempt recovered as succeeded", "success")
                    break  # identical copies of a result are one receipt
                except _KEEP_ERRORS as exc:
                    activity("KEEP", f"{patch.path.name}: recovery not proven ({exc})", "detail")
                    continue
        if not changed:
            return artifacts
        latest = load_exchange_state(paths)
        return tuple(
            replace(artifact, apply_status=record.apply_status)
            if artifact.kind is ExchangeArtifactKind.PATCH_PACKAGE
            and (record := latest.record_for(artifact.identity)) is not None
            else artifact for artifact in artifacts
        )
    except _KEEP_ERRORS as exc:
        activity("RECOVERY", f"Recovery unavailable; preserve existing state ({exc})", "warning")
        return artifacts
