from __future__ import annotations

from patchharbor.errors import (
    ErrorKind,
    ExitCode,
    format_tool_message,
    format_tool_warning,
    registry_error,
    repository_resolution_error,
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
        "TIMEOUT": 124,
        "INTERRUPTED": 130,
    }


def test_public_tool_message_prefixes_are_stable() -> None:
    assert format_tool_message("failed") == "patchharbor: failed"
    assert format_tool_warning("large input") == (
        "patchharbor: warning: large input"
    )


def test_repository_error_factories_share_exit_code_and_keep_categories() -> None:
    registry_failure = registry_error("registry failed")
    resolution_failure = repository_resolution_error("resolution failed")

    assert registry_failure.exit_code is ExitCode.REPOSITORY_ERROR
    assert registry_failure.error_kind is ErrorKind.REGISTRY_ERROR
    assert resolution_failure.exit_code is ExitCode.REPOSITORY_ERROR
    assert (
        resolution_failure.error_kind
        is ErrorKind.REPOSITORY_RESOLUTION_ERROR
    )
