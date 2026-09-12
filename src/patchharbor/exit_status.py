"""Compatibility adapter for numeric CLI, JSON and persisted run statuses.

Core decisions use FailureReason and structured outcomes. The established wire
formats still require these numbers, including logs created without the CLI.
A child's own exit status is data and is never reclassified as a tool failure.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Protocol

from patchharbor.errors import FailureReason, PatchHarborError


class ExitCode(IntEnum):
    """Exit codes owned by PatchHarbor rather than the executed script."""

    USAGE_ERROR = 2
    NO_VALID_SCRIPT = 3
    SOURCE_ERROR = 4
    INTERPRETER_ERROR = 5
    PAYLOAD_PREPARATION_ERROR = 6
    EXECUTION_ERROR = 7
    REPOSITORY_ERROR = 8
    STATE_MISMATCH = 9
    PATCH_PACKAGE_ERROR = 10
    RESULT_BUNDLE_ERROR = 11
    REPOSITORY_BUSY = 12
    UNSUPPORTED_REPOSITORY_STATE = 13
    TIMEOUT = 124
    INTERRUPTED = 130


_REASON_TO_EXIT = {
    FailureReason.USAGE_ERROR: ExitCode.USAGE_ERROR,
    FailureReason.NO_VALID_SCRIPT: ExitCode.NO_VALID_SCRIPT,
    FailureReason.SOURCE_ERROR: ExitCode.SOURCE_ERROR,
    FailureReason.INTERPRETER_ERROR: ExitCode.INTERPRETER_ERROR,
    FailureReason.PAYLOAD_PREPARATION_ERROR: ExitCode.PAYLOAD_PREPARATION_ERROR,
    FailureReason.EXECUTION_ERROR: ExitCode.EXECUTION_ERROR,
    FailureReason.REPOSITORY_ERROR: ExitCode.REPOSITORY_ERROR,
    FailureReason.STATE_MISMATCH: ExitCode.STATE_MISMATCH,
    FailureReason.PATCH_PACKAGE_ERROR: ExitCode.PATCH_PACKAGE_ERROR,
    FailureReason.RESULT_BUNDLE_ERROR: ExitCode.RESULT_BUNDLE_ERROR,
    FailureReason.REPOSITORY_BUSY: ExitCode.REPOSITORY_BUSY,
    FailureReason.UNSUPPORTED_REPOSITORY_STATE: ExitCode.UNSUPPORTED_REPOSITORY_STATE,
    FailureReason.TIMEOUT: ExitCode.TIMEOUT,
    FailureReason.INTERRUPTED: ExitCode.INTERRUPTED,
}
_EXIT_TO_REASON = {code: reason for reason, code in _REASON_TO_EXIT.items()}


def exit_code_for_reason(reason: FailureReason) -> ExitCode:
    if not isinstance(reason, FailureReason):
        raise TypeError("status mapping requires a FailureReason")
    return _REASON_TO_EXIT[reason]


def reason_for_exit_code(code: int) -> FailureReason:
    """Decode an owned numeric status at a compatibility boundary."""
    if isinstance(code, bool) or not isinstance(code, int):
        raise ValueError("PatchHarbor status must be an integer")
    return _EXIT_TO_REASON[ExitCode(code)]


def exit_code_for_error(error: PatchHarborError) -> ExitCode:
    return exit_code_for_reason(error.reason)


class PrimaryOutcomeView(Protocol):
    @property
    def success(self) -> bool: ...

    @property
    def failure_reason(self) -> FailureReason | None: ...

    @property
    def entrypoint_exit_code(self) -> int | None: ...


def primary_process_exit_code(result: PrimaryOutcomeView) -> int:
    if result.entrypoint_exit_code is not None:
        return result.entrypoint_exit_code
    if result.failure_reason is not None:
        return int(exit_code_for_reason(result.failure_reason))
    return 0


def completed_process_exit_code(
    *, operation: str, primary_result: PrimaryOutcomeView, result_bundle_status: str,
) -> int:
    """Preserve existing completion priority for every numeric wire consumer."""
    if operation == "bundle":
        return (0 if primary_result.success and result_bundle_status == "created"
                else int(ExitCode.RESULT_BUNDLE_ERROR))
    if primary_result.success and result_bundle_status == "failed":
        return int(ExitCode.RESULT_BUNDLE_ERROR)
    return primary_process_exit_code(primary_result)
