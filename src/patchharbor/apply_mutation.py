"""Single checked boundary for the first mutating apply operation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from patchharbor.progress import activity

from patchharbor.apply_preflight import PreparedPatchPackage
from patchharbor.apply_repository import SafeResolvedRepository
from patchharbor.errors import (
    FailureReason,
    PatchHarborError,
    state_mismatch_error,
)
from patchharbor.models import RepositoryContext
from patchharbor.patch_package import ValidatedPatchPackage
from patchharbor.payload_files import (
    PayloadTargetError,
    PayloadWriteError,
    write_bundle_payloads,
)
from patchharbor.repository_state import (
    capture_consistent_repository_snapshot,
    repository_context_from_snapshot,
)
from patchharbor.run_report import RunSession


class MutationFailureKind(str, Enum):
    """Internal failure phases of the first repository mutation."""

    STATE_MISMATCH = "state_mismatch"
    UNSAFE_TARGET = "unsafe_target"
    WRITE_FAILURE = "write_failure"


@dataclass(frozen=True, slots=True)
class ApplyMutationGate:
    """All checked inputs required before the first repository mutation."""

    session: RunSession
    resolved: SafeResolvedRepository
    package: ValidatedPatchPackage
    prepared_package: PreparedPatchPackage
    dry_run: bool
    before_mutation: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dry_run, bool):
            raise ValueError("mutation gate dry-run flag must be boolean")
        if not self.resolved.matches_manifest_state(self.package.manifest):
            raise ValueError("mutation gate requires the exact manifest state")
        if self.prepared_package.payloads != self.package.payloads:
            raise ValueError(
                "mutation gate payloads differ from the validated package"
            )

    @property
    def context(self) -> RepositoryContext:
        return self.resolved.context

    @property
    def warnings(self) -> tuple[str, ...]:
        return (*self.package.warnings, *self.prepared_package.warnings)


@dataclass(frozen=True, slots=True)
class ApplyMutationResult:
    """Observed outcome of the single mutation boundary."""

    context: RepositoryContext
    failure_kind: MutationFailureKind | None = None
    error: PatchHarborError | None = None

    def __post_init__(self) -> None:
        if (self.failure_kind is None) != (self.error is None):
            raise ValueError("mutation failure kind and error must appear together")
        if self.failure_kind is MutationFailureKind.STATE_MISMATCH:
            if (
                self.error is None
                or self.error.reason is not FailureReason.STATE_MISMATCH
            ):
                raise ValueError("state mismatch requires its semantic failure reason")
        elif self.failure_kind in {
            MutationFailureKind.UNSAFE_TARGET,
            MutationFailureKind.WRITE_FAILURE,
        }:
            if (
                self.error is None
                or self.error.reason
                is not FailureReason.PAYLOAD_PREPARATION_ERROR
            ):
                raise ValueError("payload mutation failures require a payload failure reason")

    @property
    def success(self) -> bool:
        return self.error is None

    @classmethod
    def succeeded(cls, context: RepositoryContext) -> ApplyMutationResult:
        return cls(context=context)

    @classmethod
    def failed(
        cls,
        context: RepositoryContext,
        *,
        kind: MutationFailureKind,
        error: PatchHarborError,
    ) -> ApplyMutationResult:
        return cls(context=context, failure_kind=kind, error=error)


def _capture_mutation_context(
    mutation_gate: ApplyMutationGate,
) -> RepositoryContext:
    """Capture the repository again immediately before its first mutation."""
    resolved = mutation_gate.resolved
    snapshot = capture_consistent_repository_snapshot(resolved.repository)
    return repository_context_from_snapshot(
        resolved.repository,
        resolved.repo_id,
        snapshot,
    )


def apply_payload_mutation(
    mutation_gate: ApplyMutationGate,
) -> ApplyMutationResult:
    """Recheck repository state, resolve targets afresh, and write payloads."""
    activity("RECHECK", "Capture repository state again immediately before mutation")
    current_context = _capture_mutation_context(mutation_gate)
    if current_context != mutation_gate.context:
        activity("RECHECK", "Repository changed after preflight; no payload writes", "error")
        return ApplyMutationResult.failed(
            current_context,
            kind=MutationFailureKind.STATE_MISMATCH,
            error=state_mismatch_error(
                "repository changed after apply preflight"
            ),
        )

    activity("RECHECK", "State unchanged; enter checked mutation boundary", "success")
    if mutation_gate.before_mutation is not None:
        mutation_gate.before_mutation()

    try:
        # The mutation boundary deliberately starts again from the repository
        # root plus validated relative names. It never reuses target Path
        # objects from the earlier read-only preflight.
        write_bundle_payloads(
            mutation_gate.prepared_package.payloads,
            cwd=mutation_gate.resolved.repository.value,
        )
    except PayloadTargetError as error:
        return ApplyMutationResult.failed(
            current_context,
            kind=MutationFailureKind.UNSAFE_TARGET,
            error=error,
        )
    except PayloadWriteError as error:
        return ApplyMutationResult.failed(
            current_context,
            kind=MutationFailureKind.WRITE_FAILURE,
            error=error,
        )

    return ApplyMutationResult.succeeded(current_context)
