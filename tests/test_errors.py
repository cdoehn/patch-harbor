from __future__ import annotations

from patchharbor.errors import (
    ExitCode,
    format_tool_message,
    format_tool_warning,
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
