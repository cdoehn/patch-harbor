from __future__ import annotations

from patchharbor.errors import (
    ErrorKind,
    ExitCode,
    configuration_error,
    format_tool_message,
    format_tool_warning,
    patch_package_error,
    registry_error,
    result_bundle_error,
    state_mismatch_error,
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
        "STATE_MISMATCH": 9,
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


def test_error_factories_keep_public_codes_and_categories() -> None:
    configuration_failure = configuration_error("configuration failed")
    registry_failure = registry_error("registry failed")
    resolution_failure = repository_resolution_error("resolution failed")
    result_bundle_failure = result_bundle_error("bundle failed")
    mismatch_failure = state_mismatch_error("state mismatch")
    busy_failure = repository_busy_error()
    package_failure = patch_package_error("package failed")
    unsupported_failure = unsupported_repository_state_error(
        "unsupported state"
    )

    assert configuration_failure.exit_code is ExitCode.SOURCE_ERROR
    assert (
        configuration_failure.error_kind
        is ErrorKind.CONFIGURATION_ERROR
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
    assert mismatch_failure.exit_code is ExitCode.STATE_MISMATCH
    assert mismatch_failure.error_kind is ErrorKind.STATE_MISMATCH
    assert busy_failure.exit_code is ExitCode.REPOSITORY_BUSY
    assert busy_failure.error_kind is ErrorKind.REPOSITORY_BUSY
    assert package_failure.exit_code is ExitCode.PATCH_PACKAGE_ERROR
    assert package_failure.error_kind is ErrorKind.PATCH_PACKAGE_ERROR
    assert (
        unsupported_failure.exit_code
        is ExitCode.UNSUPPORTED_REPOSITORY_STATE
    )
    assert (
        unsupported_failure.error_kind
        is ErrorKind.UNSUPPORTED_REPOSITORY_STATE
    )
