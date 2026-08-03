"""PatchHarbor tool errors, public exit codes, and message prefixes."""

from __future__ import annotations

from enum import IntEnum


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
    TIMEOUT = 124
    INTERRUPTED = 130


class PatchHarborError(Exception):
    """A visible PatchHarbor failure that did not come from the script."""

    def __init__(self, message: str, exit_code: ExitCode) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def format_tool_message(message: str) -> str:
    """Prefix one visible PatchHarbor status or error message."""
    return f"{TOOL_PREFIX} {message}"


def format_tool_warning(message: str) -> str:
    """Prefix one visible PatchHarbor warning message."""
    return f"{WARNING_PREFIX} {message}"
