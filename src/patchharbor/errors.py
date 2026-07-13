"""PatchHarbor tool errors and their public exit codes."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes owned by PatchHarbor rather than the executed script."""

    NO_VALID_SCRIPT = 3
    SOURCE_ERROR = 4
    INTERPRETER_ERROR = 5
    EXECUTION_ERROR = 7
    TIMEOUT = 124


class PatchHarborError(Exception):
    """A visible PatchHarbor failure that did not come from the script."""

    def __init__(self, message: str, exit_code: ExitCode) -> None:
        super().__init__(message)
        self.exit_code = exit_code
