"""PatchHarbor tool errors, public exit codes, and message prefixes."""

from __future__ import annotations

from enum import Enum, IntEnum
from pathlib import Path


TOOL_PREFIX = "patchharbor:"
WARNING_PREFIX = f"{TOOL_PREFIX} warning:"


class ExitCode(IntEnum):
    """Exit codes owned by PatchHarbor rather than the executed script."""

    USAGE_ERROR = 2
    NO_VALID_SCRIPT = 3
    SOURCE_ERROR = 4
    INTERPRETER_ERROR = 5
    PAYLOAD_PREPARATION_ERROR = 6
    EXECUTION_ERROR = 7
    REPOSITORY_ERROR = 8
    PATCH_PACKAGE_ERROR = 10
    RESULT_BUNDLE_ERROR = 11
    REPOSITORY_BUSY = 12
    UNSUPPORTED_REPOSITORY_STATE = 13
    TIMEOUT = 124
    INTERRUPTED = 130


class ErrorKind(str, Enum):
    """Stable machine-readable categories for structured tool failures."""

    TOOL_ERROR = "tool_error"
    REGISTRY_ERROR = "registry_error"
    REPOSITORY_RESOLUTION_ERROR = "repository_resolution_error"
    RESULT_BUNDLE_ERROR = "result_bundle_error"
    REPOSITORY_BUSY = "repository_busy"
    UNSUPPORTED_REPOSITORY_STATE = "unsupported_repository_state"


class PatchHarborError(Exception):
    """A visible PatchHarbor failure that did not come from the script."""

    def __init__(
        self,
        message: str,
        exit_code: ExitCode,
        *,
        error_kind: ErrorKind = ErrorKind.TOOL_ERROR,
        emergency_diagnostics_path: Path | None = None,
        emergency_diagnostics_failed: bool = False,
        run_report: object | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.error_kind = error_kind
        self.emergency_diagnostics_path = emergency_diagnostics_path
        self.emergency_diagnostics_failed = emergency_diagnostics_failed
        self.run_report = run_report


def registry_error(message: str) -> PatchHarborError:
    """Create one centrally categorized registry failure."""
    return PatchHarborError(
        message,
        ExitCode.REPOSITORY_ERROR,
        error_kind=ErrorKind.REGISTRY_ERROR,
    )


def repository_resolution_error(message: str) -> PatchHarborError:
    """Create one centrally categorized repository-resolution failure."""
    return PatchHarborError(
        message,
        ExitCode.REPOSITORY_ERROR,
        error_kind=ErrorKind.REPOSITORY_RESOLUTION_ERROR,
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
        ExitCode.RESULT_BUNDLE_ERROR,
        error_kind=ErrorKind.RESULT_BUNDLE_ERROR,
        emergency_diagnostics_path=emergency_diagnostics_path,
        emergency_diagnostics_failed=emergency_diagnostics_failed,
    )


def repository_busy_error(message: str = "repository is busy") -> PatchHarborError:
    """Create one failure for an already exclusively locked repository."""
    return PatchHarborError(
        message,
        ExitCode.REPOSITORY_BUSY,
        error_kind=ErrorKind.REPOSITORY_BUSY,
    )


def unsupported_repository_state_error(message: str) -> PatchHarborError:
    """Create one failure for state the safe repository path cannot model."""
    return PatchHarborError(
        message,
        ExitCode.UNSUPPORTED_REPOSITORY_STATE,
        error_kind=ErrorKind.UNSUPPORTED_REPOSITORY_STATE,
    )


def format_tool_message(message: str) -> str:
    """Prefix one visible PatchHarbor status or error message."""
    return f"{TOOL_PREFIX} {message}"


def format_tool_warning(message: str) -> str:
    """Prefix one visible PatchHarbor warning message."""
    return f"{WARNING_PREFIX} {message}"
