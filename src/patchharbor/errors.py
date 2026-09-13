"""Semantic tool failures and legacy message-prefix helpers for output adapters."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


TOOL_PREFIX = "patchharbor:"
WARNING_PREFIX = f"{TOOL_PREFIX} warning:"


class FailureReason(str, Enum):
    """Semantic failure reasons independent of CLI status numbers."""

    USAGE_ERROR = "usage_error"
    NO_VALID_SCRIPT = "no_valid_script"
    SOURCE_ERROR = "source_error"
    INTERPRETER_ERROR = "interpreter_error"
    PAYLOAD_PREPARATION_ERROR = "payload_preparation_error"
    EXECUTION_ERROR = "execution_error"
    REPOSITORY_ERROR = "repository_error"
    STATE_MISMATCH = "state_mismatch"
    PATCH_PACKAGE_ERROR = "patch_package_error"
    RESULT_BUNDLE_ERROR = "result_bundle_error"
    REPOSITORY_BUSY = "repository_busy"
    UNSUPPORTED_REPOSITORY_STATE = "unsupported_repository_state"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


class ErrorKind(str, Enum):
    """Stable machine-readable categories for structured tool failures."""

    TOOL_ERROR = "tool_error"
    CONFIGURATION_ERROR = "configuration_error"
    REGISTRY_ERROR = "registry_error"
    REPOSITORY_RESOLUTION_ERROR = "repository_resolution_error"
    STATE_MISMATCH = "state_mismatch"
    RESULT_BUNDLE_ERROR = "result_bundle_error"
    REPOSITORY_BUSY = "repository_busy"
    UNSUPPORTED_REPOSITORY_STATE = "unsupported_repository_state"
    PATCH_PACKAGE_ERROR = "patch_package_error"


class PatchHarborError(Exception):
    """A visible PatchHarbor failure that did not come from the script."""

    def __init__(
        self,
        message: str,
        reason: FailureReason,
        *,
        error_kind: ErrorKind = ErrorKind.TOOL_ERROR,
        emergency_diagnostics_path: Path | None = None,
        emergency_diagnostics_failed: bool = False,
        run_report: object | None = None,
    ) -> None:
        super().__init__(message)
        if not isinstance(reason, FailureReason):
            raise TypeError("PatchHarbor failures require a FailureReason")
        self.reason = reason
        self.error_kind = error_kind
        self.emergency_diagnostics_path = emergency_diagnostics_path
        self.emergency_diagnostics_failed = emergency_diagnostics_failed
        self.run_report = run_report


def configuration_error(message: str) -> PatchHarborError:
    """Create one centrally categorized user-configuration failure."""
    return PatchHarborError(
        message,
        FailureReason.SOURCE_ERROR,
        error_kind=ErrorKind.CONFIGURATION_ERROR,
    )


def registry_error(message: str) -> PatchHarborError:
    """Create one centrally categorized registry failure."""
    return PatchHarborError(
        message,
        FailureReason.REPOSITORY_ERROR,
        error_kind=ErrorKind.REGISTRY_ERROR,
    )


def repository_resolution_error(message: str) -> PatchHarborError:
    """Create one centrally categorized repository-resolution failure."""
    return PatchHarborError(
        message,
        FailureReason.REPOSITORY_ERROR,
        error_kind=ErrorKind.REPOSITORY_RESOLUTION_ERROR,
    )


def state_mismatch_error(
    message: str,
    *,
    emergency_diagnostics_path: Path | None = None,
    emergency_diagnostics_failed: bool = False,
    run_report: object | None = None,
) -> PatchHarborError:
    """Create one failure for a repository state that differs from the manifest."""
    return PatchHarborError(
        message,
        FailureReason.STATE_MISMATCH,
        error_kind=ErrorKind.STATE_MISMATCH,
        emergency_diagnostics_path=emergency_diagnostics_path,
        emergency_diagnostics_failed=emergency_diagnostics_failed,
        run_report=run_report,
    )


def patch_package_error(message: str) -> PatchHarborError:
    """Create one centrally categorized patch-package failure."""
    return PatchHarborError(
        message,
        FailureReason.PATCH_PACKAGE_ERROR,
        error_kind=ErrorKind.PATCH_PACKAGE_ERROR,
    )


def result_bundle_error(
    message: str,
    *,
    emergency_diagnostics_path: Path | None = None,
    emergency_diagnostics_failed: bool = False,
) -> PatchHarborError:
    """Create one failure for manual Result Bundle generation."""
    return PatchHarborError(
        message,
        FailureReason.RESULT_BUNDLE_ERROR,
        error_kind=ErrorKind.RESULT_BUNDLE_ERROR,
        emergency_diagnostics_path=emergency_diagnostics_path,
        emergency_diagnostics_failed=emergency_diagnostics_failed,
    )


def repository_busy_error(message: str = "repository is busy") -> PatchHarborError:
    """Create one failure for an already exclusively locked repository."""
    return PatchHarborError(
        message,
        FailureReason.REPOSITORY_BUSY,
        error_kind=ErrorKind.REPOSITORY_BUSY,
    )


def unsupported_repository_state_error(message: str) -> PatchHarborError:
    """Create one failure for state the safe repository path cannot model."""
    return PatchHarborError(
        message,
        FailureReason.UNSUPPORTED_REPOSITORY_STATE,
        error_kind=ErrorKind.UNSUPPORTED_REPOSITORY_STATE,
    )


def format_tool_message(message: str) -> str:
    """Prefix one visible PatchHarbor status or error message."""
    return f"{TOOL_PREFIX} {message}"


def format_tool_warning(message: str) -> str:
    """Prefix one visible PatchHarbor warning message."""
    return f"{WARNING_PREFIX} {message}"
