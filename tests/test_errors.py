from __future__ import annotations

from patchharbor.errors import (
    ErrorKind,
    ExitCode,
    format_tool_message,
    format_tool_warning,
    registry_error,
    result_bundle_error,
    repository_busy_error,
    repository_resolution_error,
    unsupported_repository_state_error,
)


def test_public_tool_exit_codes_are_complete_and_stable() -> None:
    assert {member.name: int(member) for member in ExitCode} == {
        "USAGE_ERROR": 2,
        "NO_VALID_SCRIPT": 3,
        "SOURCE_ERROR": 4,
        "INTERPRETER_ERROR": 5,
        "PAYLOAD_PREPARATION_ERROR": 6,
        "EXECUTION_ERROR": 7,
        "REPOSITORY_ERROR": 8,
        "PATCH_PACKAGE_ERROR": 10,
        "RESULT_BUNDLE_ERROR": 11,
        "REPOSITORY_BUSY": 12,
        "UNSUPPORTED_REPOSITORY_STATE": 13,
        "TIMEOUT": 124,
        "INTERRUPTED": 130,
    }


def test_public_tool_message_prefixes_are_stable() -> None:
    assert format_tool_message("failed") == "patchharbor: failed"
    assert format_tool_warning("large input") == (
        "patchharbor: warning: large input"
    )


def test_repository_error_factories_keep_public_codes_and_categories() -> None:
    registry_failure = registry_error("registry failed")
    resolution_failure = repository_resolution_error("resolution failed")
    result_bundle_failure = result_bundle_error("bundle failed")
    busy_failure = repository_busy_error()
    unsupported_failure = unsupported_repository_state_error(
        "unsupported state"
    )

    assert registry_failure.exit_code is ExitCode.REPOSITORY_ERROR
    assert registry_failure.error_kind is ErrorKind.REGISTRY_ERROR
    assert resolution_failure.exit_code is ExitCode.REPOSITORY_ERROR
    assert (
        resolution_failure.error_kind
        is ErrorKind.REPOSITORY_RESOLUTION_ERROR
    )
    assert (
        result_bundle_failure.exit_code is ExitCode.RESULT_BUNDLE_ERROR
    )
    assert (
        result_bundle_failure.error_kind is ErrorKind.RESULT_BUNDLE_ERROR
    )
    assert busy_failure.exit_code is ExitCode.REPOSITORY_BUSY
    assert busy_failure.error_kind is ErrorKind.REPOSITORY_BUSY
    assert (
        unsupported_failure.exit_code
        is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    )
    assert (
        unsupported_failure.error_kind
        is ErrorKind.UNSUPPORTED_REPOSITORY_STATE
    )
