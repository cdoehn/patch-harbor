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
    """Base class for a visible PatchHarbor failure."""

    exit_code: ExitCode


class NoValidScriptError(PatchHarborError):
    """The source did not contain a valid PatchHarbor script."""

    exit_code = ExitCode.NO_VALID_SCRIPT


class SourceError(PatchHarborError):
    """The requested source could not be read."""

    exit_code = ExitCode.SOURCE_ERROR


class InterpreterError(PatchHarborError):
    """The selected interpreter could not be started."""

    exit_code = ExitCode.INTERPRETER_ERROR


class ExecutionPreparationError(PatchHarborError):
    """The script could not be prepared before process start."""

    exit_code = ExitCode.EXECUTION_ERROR


class ScriptTimeoutError(PatchHarborError):
    """The executed script exceeded its configured timeout."""

    exit_code = ExitCode.TIMEOUT
