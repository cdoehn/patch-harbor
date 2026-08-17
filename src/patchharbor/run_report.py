"""Immutable structured outcomes shared by Result Bundles and JSON CLI output."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import math
import os
from pathlib import Path
from time import monotonic
from typing import Mapping
from uuid import UUID, uuid4

from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.models import RepositoryContext, RepositoryId, RepositoryPath


_SECRET_ENV_MARKERS = (
    "ACCESS_KEY",
    "API_KEY",
    "CREDENTIAL",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
)


class RunOperation(str, Enum):
    """Public operations that produce the shared structured run contract."""

    BUNDLE = "bundle"
    APPLY = "apply"


class PrimaryResultKind(str, Enum):
    """Stable primary-result categories defined by the 1.1.0 contract."""

    SUCCESS = "success"
    DRY_RUN_SUCCESS = "dry_run_success"
    VALIDATION_ERROR = "validation_error"
    REPOSITORY_ERROR = "repository_error"
    STATE_MISMATCH = "state_mismatch"
    REPOSITORY_BUSY = "repository_busy"
    ENTRYPOINT_EXIT = "entrypoint_exit"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"
    EXECUTION_ERROR = "execution_error"

    @classmethod
    def for_tool_error(cls, error: PatchHarborError) -> PrimaryResultKind:
        """Map one tool failure to its stable primary-result category."""
        if error.error_kind is ErrorKind.STATE_MISMATCH:
            return cls.STATE_MISMATCH
        if error.error_kind is ErrorKind.REPOSITORY_BUSY:
            return cls.REPOSITORY_BUSY
        if error.error_kind in {
            ErrorKind.REGISTRY_ERROR,
            ErrorKind.REPOSITORY_RESOLUTION_ERROR,
            ErrorKind.UNSUPPORTED_REPOSITORY_STATE,
        }:
            return cls.REPOSITORY_ERROR
        if error.exit_code in {
            ExitCode.NO_VALID_SCRIPT,
            ExitCode.INTERPRETER_ERROR,
            ExitCode.PAYLOAD_PREPARATION_ERROR,
            ExitCode.PATCH_PACKAGE_ERROR,
        }:
            return cls.VALIDATION_ERROR
        return cls.EXECUTION_ERROR


class ResultBundleStatus(str, Enum):
    """Stable status of the Result-Bundle side of one run."""

    CREATED = "created"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


def canonical_uuid_text(value: UUID) -> str:
    """Return one canonical UUID-v4 string or reject the value."""
    text = str(value)
    if value.version != 4 or UUID(text) != value or text != text.lower():
        raise ValueError("run ID must be a canonical UUID v4")
    return text


def rfc3339_utc(value: datetime) -> str:
    """Render one timezone-aware timestamp as RFC-3339 UTC with ``Z``."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("run timestamp must be timezone-aware")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def finite_duration_seconds(value: float) -> float:
    """Keep structured durations finite and non-negative."""
    duration = float(value)
    if not math.isfinite(duration) or duration < 0.0:
        return 0.0
    return duration


def physical_absolute_path(path: Path) -> Path:
    """Return the physically canonical absolute representation of one path."""
    return path.expanduser().resolve(strict=False)


def physical_absolute_path_text(path: Path | RepositoryPath | None) -> str | None:
    """Serialize one path through the shared physical absolute-path boundary."""
    if path is None:
        return None
    raw_path = path.value if isinstance(path, RepositoryPath) else path
    return str(physical_absolute_path(raw_path))


def sanitize_structured_text(
    value: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Redact secret-looking environment values from structured output text."""
    sanitized = value
    source = os.environ if environment is None else environment
    for name, secret in source.items():
        if not secret:
            continue
        normalized_name = name.upper()
        if any(marker in normalized_name for marker in _SECRET_ENV_MARKERS):
            sanitized = sanitized.replace(secret, "[redacted]")
    return sanitized


@dataclass(frozen=True)
class RunSession:
    """One generated run identity together with its starting clocks."""

    run_id: UUID
    started_at: datetime
    started_monotonic: float

    def __post_init__(self) -> None:
        canonical_uuid_text(self.run_id)
        rfc3339_utc(self.started_at)
        if not math.isfinite(float(self.started_monotonic)):
            raise ValueError("run monotonic start must be finite")

    @classmethod
    def start(cls) -> RunSession:
        """Start one run using the system UTC and monotonic clocks."""
        return cls(
            run_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            started_monotonic=monotonic(),
        )

    @property
    def filename_timestamp(self) -> str:
        """Stable UTC timestamp component for Result-Bundle filenames."""
        return self.started_at.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def finish(
        self,
        *,
        ended_at: datetime | None = None,
        ended_monotonic: float | None = None,
    ) -> RunTiming:
        """Finish the session while keeping duration JSON-safe."""
        actual_ended_at = ended_at or datetime.now(timezone.utc)
        actual_ended_monotonic = (
            monotonic() if ended_monotonic is None else ended_monotonic
        )
        return RunTiming(
            run_id=self.run_id,
            started_at=self.started_at,
            ended_at=actual_ended_at,
            duration_seconds=finite_duration_seconds(
                actual_ended_monotonic - self.started_monotonic
            ),
        )


@dataclass(frozen=True)
class RunTiming:
    """Completed wall-clock and monotonic timing of one run."""

    run_id: UUID
    started_at: datetime
    ended_at: datetime
    duration_seconds: float

    def __post_init__(self) -> None:
        canonical_uuid_text(self.run_id)
        rfc3339_utc(self.started_at)
        rfc3339_utc(self.ended_at)
        object.__setattr__(
            self,
            "duration_seconds",
            finite_duration_seconds(self.duration_seconds),
        )

    @property
    def started_at_text(self) -> str:
        return rfc3339_utc(self.started_at)

    @property
    def ended_at_text(self) -> str:
        return rfc3339_utc(self.ended_at)


@dataclass(frozen=True)
class PrimaryResult:
    """The primary side of one run, independent from bundle publication."""

    kind: PrimaryResultKind
    success: bool
    patchharbor_error_code: int | None
    entrypoint_started: bool = False
    entrypoint_exit_code: int | None = None
    timed_out: bool = False
    interrupted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("primary success flag must be boolean")
        if not isinstance(self.entrypoint_started, bool):
            raise ValueError("entrypoint-started flag must be boolean")
        if not isinstance(self.timed_out, bool) or not isinstance(
            self.interrupted, bool
        ):
            raise ValueError("process terminal flags must be boolean")
        for name, value in (
            ("PatchHarbor error code", self.patchharbor_error_code),
            ("entrypoint exit code", self.entrypoint_exit_code),
        ):
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise ValueError(f"{name} must be an integer")

        if self.success:
            if self.patchharbor_error_code is not None:
                raise ValueError("successful primary result cannot have a tool error")
            if self.timed_out or self.interrupted:
                raise ValueError("successful primary result cannot be terminated")
            if self.entrypoint_started:
                if self.entrypoint_exit_code != 0:
                    raise ValueError("successful entrypoint requires exit code zero")
            elif self.entrypoint_exit_code is not None:
                raise ValueError("unstarted entrypoint cannot have an exit code")
            return

        if self.kind is PrimaryResultKind.ENTRYPOINT_EXIT:
            if (
                not self.entrypoint_started
                or self.entrypoint_exit_code in (None, 0)
                or self.patchharbor_error_code is not None
                or self.timed_out
                or self.interrupted
            ):
                raise ValueError("entrypoint exit result is inconsistent")
            return

        if self.kind is PrimaryResultKind.TIMEOUT:
            if (
                not self.entrypoint_started
                or self.entrypoint_exit_code is not None
                or self.patchharbor_error_code != int(ExitCode.TIMEOUT)
                or not self.timed_out
                or self.interrupted
            ):
                raise ValueError("timeout result is inconsistent")
            return

        if self.kind is PrimaryResultKind.INTERRUPTED:
            if (
                not self.entrypoint_started
                or self.entrypoint_exit_code is not None
                or self.patchharbor_error_code != int(ExitCode.INTERRUPTED)
                or self.timed_out
                or not self.interrupted
            ):
                raise ValueError("interrupted result is inconsistent")
            return

        if (
            self.entrypoint_exit_code is not None
            or self.patchharbor_error_code is None
            or self.timed_out
            or self.interrupted
        ):
            raise ValueError("PatchHarbor tool failure result is inconsistent")

    @property
    def kind_text(self) -> str:
        """Return the stable public primary-result kind."""
        return self.kind.value

    @classmethod
    def success_result(cls) -> PrimaryResult:
        return cls(
            kind=PrimaryResultKind.SUCCESS,
            success=True,
            patchharbor_error_code=None,
        )

    @classmethod
    def dry_run_success_result(cls) -> PrimaryResult:
        return cls(
            kind=PrimaryResultKind.DRY_RUN_SUCCESS,
            success=True,
            patchharbor_error_code=None,
        )

    @classmethod
    def entrypoint_success_result(cls) -> PrimaryResult:
        return cls(
            kind=PrimaryResultKind.SUCCESS,
            success=True,
            patchharbor_error_code=None,
            entrypoint_started=True,
            entrypoint_exit_code=0,
        )

    @classmethod
    def entrypoint_exit_result(cls, exit_code: int) -> PrimaryResult:
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise ValueError("entrypoint exit code must be an integer")
        if exit_code == 0:
            raise ValueError("entrypoint failure requires a nonzero exit code")
        return cls(
            kind=PrimaryResultKind.ENTRYPOINT_EXIT,
            success=False,
            patchharbor_error_code=None,
            entrypoint_started=True,
            entrypoint_exit_code=exit_code,
        )

    @classmethod
    def timeout_result(cls) -> PrimaryResult:
        return cls(
            kind=PrimaryResultKind.TIMEOUT,
            success=False,
            patchharbor_error_code=int(ExitCode.TIMEOUT),
            entrypoint_started=True,
            timed_out=True,
        )

    @classmethod
    def interrupted_result(cls) -> PrimaryResult:
        return cls(
            kind=PrimaryResultKind.INTERRUPTED,
            success=False,
            patchharbor_error_code=int(ExitCode.INTERRUPTED),
            entrypoint_started=True,
            interrupted=True,
        )

    @classmethod
    def tool_failure(
        cls,
        *,
        kind: PrimaryResultKind,
        patchharbor_error_code: int,
    ) -> PrimaryResult:
        return cls(
            kind=kind,
            success=False,
            patchharbor_error_code=patchharbor_error_code,
        )

    @classmethod
    def from_tool_error(cls, error: PatchHarborError) -> PrimaryResult:
        """Create the structured primary result for one tool failure."""
        return cls.tool_failure(
            kind=PrimaryResultKind.for_tool_error(error),
            patchharbor_error_code=int(error.exit_code),
        )

    def as_document(self) -> dict[str, object]:
        return {
            "kind": self.kind_text,
            "success": self.success,
            "patchharbor_error_code": self.patchharbor_error_code,
            "entrypoint_started": self.entrypoint_started,
            "entrypoint_exit_code": self.entrypoint_exit_code,
            "timed_out": self.timed_out,
            "interrupted": self.interrupted,
        }

    def as_apply_document(self) -> dict[str, object]:
        return {
            "kind": self.kind_text,
            "entrypoint_started": self.entrypoint_started,
            "entrypoint_exit_code": self.entrypoint_exit_code,
            "timed_out": self.timed_out,
            "interrupted": self.interrupted,
            "patchharbor_error_code": self.patchharbor_error_code,
        }


@dataclass(frozen=True, slots=True)
class ApplyPrimaryOutcome:
    """One primary apply outcome before Result-Bundle publication."""

    result: PrimaryResult
    primary_process_exit_code: int

    def __post_init__(self) -> None:
        exit_code = self.primary_process_exit_code
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise ValueError("primary process exit code must be an integer")
        if self.result.success != (exit_code == 0):
            raise ValueError("primary success and process exit code disagree")
        if (
            self.result.patchharbor_error_code is not None
            and self.result.patchharbor_error_code != exit_code
        ):
            raise ValueError("primary tool error and process exit codes disagree")
        if (
            self.result.entrypoint_exit_code is not None
            and self.result.entrypoint_exit_code != exit_code
        ):
            raise ValueError("entrypoint and process exit codes disagree")

    @classmethod
    def success(cls) -> ApplyPrimaryOutcome:
        return cls(
            result=PrimaryResult.success_result(),
            primary_process_exit_code=0,
        )

    @classmethod
    def dry_run_success(cls) -> ApplyPrimaryOutcome:
        return cls(
            result=PrimaryResult.dry_run_success_result(),
            primary_process_exit_code=0,
        )

    @classmethod
    def entrypoint_success(cls) -> ApplyPrimaryOutcome:
        return cls(
            result=PrimaryResult.entrypoint_success_result(),
            primary_process_exit_code=0,
        )

    @classmethod
    def entrypoint_exit(cls, exit_code: int) -> ApplyPrimaryOutcome:
        return cls(
            result=PrimaryResult.entrypoint_exit_result(exit_code),
            primary_process_exit_code=exit_code,
        )

    @classmethod
    def timeout(cls) -> ApplyPrimaryOutcome:
        return cls(
            result=PrimaryResult.timeout_result(),
            primary_process_exit_code=int(ExitCode.TIMEOUT),
        )

    @classmethod
    def interrupted(cls) -> ApplyPrimaryOutcome:
        return cls(
            result=PrimaryResult.interrupted_result(),
            primary_process_exit_code=int(ExitCode.INTERRUPTED),
        )

    @classmethod
    def tool_failure(
        cls,
        *,
        kind: PrimaryResultKind,
        exit_code: int,
    ) -> ApplyPrimaryOutcome:
        return cls(
            result=PrimaryResult.tool_failure(
                kind=kind,
                patchharbor_error_code=exit_code,
            ),
            primary_process_exit_code=exit_code,
        )

    @classmethod
    def from_tool_error(cls, error: PatchHarborError) -> ApplyPrimaryOutcome:
        """Create one primary outcome without duplicating error mappings."""
        return cls(
            result=PrimaryResult.from_tool_error(error),
            primary_process_exit_code=int(error.exit_code),
        )

    @classmethod
    def from_execution_result(
        cls,
        *,
        entrypoint_started: bool,
        entrypoint_exit_code: int | None,
        patchharbor_error: PatchHarborError | None,
    ) -> ApplyPrimaryOutcome:
        """Apply process-result priority without conflating its three codes."""
        if patchharbor_error is not None:
            if entrypoint_exit_code is not None:
                raise ValueError(
                    "tool failure cannot also carry an entrypoint exit code"
                )
            if patchharbor_error.exit_code is ExitCode.INTERRUPTED:
                if not entrypoint_started:
                    raise ValueError("interruption requires a started entrypoint")
                return cls.interrupted()
            if patchharbor_error.exit_code is ExitCode.TIMEOUT:
                if not entrypoint_started:
                    raise ValueError("timeout requires a started entrypoint")
                return cls.timeout()
            return cls(
                result=PrimaryResult(
                    kind=PrimaryResultKind.for_tool_error(patchharbor_error),
                    success=False,
                    patchharbor_error_code=int(patchharbor_error.exit_code),
                    entrypoint_started=entrypoint_started,
                ),
                primary_process_exit_code=int(patchharbor_error.exit_code),
            )

        if not entrypoint_started or entrypoint_exit_code is None:
            raise ValueError("completed execution requires a started entrypoint")
        if entrypoint_exit_code == 0:
            return cls.entrypoint_success()
        return cls.entrypoint_exit(entrypoint_exit_code)

    def process_exit_code_for(
        self,
        result_bundle_status: ResultBundleStatus,
    ) -> int:
        """Apply the specified Result-Bundle precedence to the process exit."""
        if (
            self.result.success
            and result_bundle_status is ResultBundleStatus.FAILED
        ):
            return int(ExitCode.RESULT_BUNDLE_ERROR)
        return self.primary_process_exit_code


@dataclass(frozen=True)
class ResultBundleResult:
    """Result-Bundle outcome kept separate from the primary result."""

    attempted: bool
    status: ResultBundleStatus
    path: Path | None = None
    error: str | None = None
    emergency_diagnostics_path: Path | None = None

    def __post_init__(self) -> None:
        if self.status is ResultBundleStatus.NOT_ATTEMPTED and self.attempted:
            raise ValueError("not_attempted Result Bundle cannot be attempted")
        if self.status is not ResultBundleStatus.NOT_ATTEMPTED and not self.attempted:
            raise ValueError("created or failed Result Bundle must be attempted")
        if self.status is ResultBundleStatus.CREATED:
            if (
                self.path is None
                or self.error is not None
                or self.emergency_diagnostics_path is not None
            ):
                raise ValueError(
                    "created Result Bundle requires only a published path"
                )
        else:
            if self.path is not None:
                raise ValueError("failed or unattempted Result Bundle has no path")
            if self.error is None:
                raise ValueError(
                    "failed or unattempted Result Bundle requires an error"
                )

        if self.path is not None:
            object.__setattr__(self, "path", physical_absolute_path(self.path))
        if self.emergency_diagnostics_path is not None:
            object.__setattr__(
                self,
                "emergency_diagnostics_path",
                physical_absolute_path(self.emergency_diagnostics_path),
            )
        if self.error is not None:
            object.__setattr__(
                self,
                "error",
                sanitize_structured_text(self.error),
            )

    @property
    def status_text(self) -> str:
        """Return the stable public Result-Bundle status."""
        return self.status.value

    @classmethod
    def created(cls, path: Path) -> ResultBundleResult:
        return cls(
            attempted=True,
            status=ResultBundleStatus.CREATED,
            path=path,
        )

    @classmethod
    def failed(cls, error: str) -> ResultBundleResult:
        return cls(
            attempted=True,
            status=ResultBundleStatus.FAILED,
            error=error,
        )

    @classmethod
    def not_attempted(cls, error: str) -> ResultBundleResult:
        return cls(
            attempted=False,
            status=ResultBundleStatus.NOT_ATTEMPTED,
            error=error,
        )

    def with_emergency_diagnostics(
        self,
        path: Path | None,
    ) -> ResultBundleResult:
        return replace(self, emergency_diagnostics_path=path)

    def as_run_document(self) -> dict[str, object]:
        return {
            "attempted": self.attempted,
            "status": self.status_text,
            "error": self.error,
        }

    def as_apply_document(self) -> dict[str, object]:
        return {
            "attempted": self.attempted,
            "status": self.status_text,
            "path": physical_absolute_path_text(self.path),
            "emergency_diagnostics_path": physical_absolute_path_text(
                self.emergency_diagnostics_path
            ),
        }


@dataclass(frozen=True)
class RunReport:
    """Single source for persisted and machine-readable run completion data."""

    timing: RunTiming
    operation: RunOperation
    dry_run: bool
    context: RepositoryContext | None
    repository: RepositoryPath | None
    repo_id: RepositoryId | None
    warnings: tuple[str, ...]
    primary_result: PrimaryResult
    result_bundle: ResultBundleResult
    process_exit_code: int

    def __post_init__(self) -> None:
        if isinstance(self.process_exit_code, bool) or not isinstance(
            self.process_exit_code, int
        ):
            raise ValueError("process exit code must be an integer")
        object.__setattr__(
            self,
            "warnings",
            tuple(sanitize_structured_text(warning) for warning in self.warnings),
        )
        if self.context is not None:
            if self.repository not in (None, self.context.repository_path):
                raise ValueError("run repository conflicts with its context")
            if self.repo_id not in (None, self.context.repo_id):
                raise ValueError("run repository ID conflicts with its context")
        if self.result_bundle.status is ResultBundleStatus.NOT_ATTEMPTED:
            if self.repository_resolved:
                raise ValueError(
                    "Result Bundle may be not_attempted only before repository resolution"
                )
        if self.operation is RunOperation.BUNDLE:
            if self.dry_run or self.execution_present:
                raise ValueError("manual bundle runs cannot execute or be dry-runs")
            if self.primary_result.success:
                if (
                    self.result_bundle.status is not ResultBundleStatus.CREATED
                    or self.process_exit_code != 0
                ):
                    raise ValueError(
                        "successful manual bundle requires a created bundle and exit 0"
                    )
            elif (
                self.result_bundle.status is ResultBundleStatus.CREATED
                or self.process_exit_code != 11
            ):
                raise ValueError(
                    "failed manual bundle requires failure status and exit 11"
                )

    @property
    def run_id(self) -> UUID:
        return self.timing.run_id

    @property
    def run_id_text(self) -> str:
        """Return the stable public run identifier."""
        return canonical_uuid_text(self.run_id)

    @property
    def resolved_repository(self) -> RepositoryPath | None:
        if self.context is not None:
            return self.context.repository_path
        return self.repository

    @property
    def resolved_repo_id(self) -> RepositoryId | None:
        if self.context is not None:
            return self.context.repo_id
        return self.repo_id

    @property
    def repository_resolved(self) -> bool:
        return self.resolved_repository is not None and self.resolved_repo_id is not None

    @property
    def execution_present(self) -> bool:
        """An execution log exists only after an entrypoint actually started."""
        return self.primary_result.entrypoint_started

    def with_result_bundle(self, result: ResultBundleResult) -> RunReport:
        return replace(self, result_bundle=result)

    def reported_error(
        self,
        primary_error: PatchHarborError | None = None,
    ) -> PatchHarborError:
        """Attach this completed report to the effective Apply failure."""
        bundle_result = self.result_bundle
        if primary_error is None:
            message = bundle_result.error or "cannot create the Result Bundle"
            exit_code = ExitCode.RESULT_BUNDLE_ERROR
            error_kind = ErrorKind.RESULT_BUNDLE_ERROR
        else:
            message = str(primary_error)
            exit_code = primary_error.exit_code
            error_kind = primary_error.error_kind
        return PatchHarborError(
            message,
            exit_code,
            error_kind=error_kind,
            emergency_diagnostics_path=(
                bundle_result.emergency_diagnostics_path
            ),
            emergency_diagnostics_failed=(
                bundle_result.status is ResultBundleStatus.FAILED
                and bundle_result.emergency_diagnostics_path is None
            ),
            run_report=self,
        )

    def as_run_document(self) -> dict[str, object]:
        context = self.context
        return {
            "run_id": self.run_id_text,
            "operation": self.operation.value,
            "dry_run": self.dry_run,
            "started_at": self.timing.started_at_text,
            "ended_at": self.timing.ended_at_text,
            "duration_seconds": self.timing.duration_seconds,
            "repository_resolved": self.repository_resolved,
            "repo_id": (
                None
                if self.resolved_repo_id is None
                else str(self.resolved_repo_id)
            ),
            "repository_path": physical_absolute_path_text(
                self.resolved_repository
            ),
            "base_commit": None if context is None else str(context.base_commit),
            "state_fingerprint": (
                None if context is None else context.state_fingerprint
            ),
            "fingerprint_algorithm": (
                None if context is None else context.fingerprint_algorithm
            ),
            "warnings": list(self.warnings),
            "execution_present": self.execution_present,
            "primary_result": self.primary_result.as_document(),
            "result_bundle": self.result_bundle.as_run_document(),
            "process_exit_code": self.process_exit_code,
        }

    def apply_result(self) -> dict[str, object]:
        """Return the closed ``apply --json`` result object."""
        if self.operation is not RunOperation.APPLY:
            raise ValueError("run report is not an apply result")
        return {
            "run_id": self.run_id_text,
            "repository_resolved": self.repository_resolved,
            "repo_id": (
                None
                if self.resolved_repo_id is None
                else str(self.resolved_repo_id)
            ),
            "repository_path": physical_absolute_path_text(
                self.resolved_repository
            ),
            "primary_result": self.primary_result.as_apply_document(),
            "result_bundle": self.result_bundle.as_apply_document(),
        }

    def manual_bundle_result(self) -> dict[str, object]:
        """Return the closed successful ``bundle --json`` result object."""
        if (
            self.operation is not RunOperation.BUNDLE
            or not self.primary_result.success
            or self.context is None
            or self.result_bundle.status is not ResultBundleStatus.CREATED
            or self.result_bundle.path is None
        ):
            raise ValueError("run report is not a successful manual bundle")
        return {
            "run_id": self.run_id_text,
            "repo_id": str(self.context.repo_id),
            "repository_path": physical_absolute_path_text(
                self.context.repository_path
            ),
            "base_commit": str(self.context.base_commit),
            "state_fingerprint": self.context.state_fingerprint,
            "fingerprint_algorithm": self.context.fingerprint_algorithm,
            "result_bundle_status": self.result_bundle.status_text,
            "result_bundle_path": physical_absolute_path_text(
                self.result_bundle.path
            ),
            "emergency_diagnostics_path": physical_absolute_path_text(
                self.result_bundle.emergency_diagnostics_path
            ),
        }


def unresolved_apply_report(
    *,
    session: RunSession,
    dry_run: bool,
    error: PatchHarborError,
    warnings: tuple[str, ...] = (),
) -> RunReport:
    """Complete one Apply failure before a repository is safely resolved."""
    primary_outcome = ApplyPrimaryOutcome.from_tool_error(error)
    return RunReport(
        timing=session.finish(),
        operation=RunOperation.APPLY,
        dry_run=dry_run,
        context=None,
        repository=None,
        repo_id=None,
        warnings=warnings,
        primary_result=primary_outcome.result,
        result_bundle=ResultBundleResult.not_attempted(str(error)),
        process_exit_code=primary_outcome.primary_process_exit_code,
    )
