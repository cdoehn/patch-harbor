"""Public runtime export facts and errors; import through patchharbor.api."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from patchharbor.errors import FailureReason, PatchHarborError


class RuntimeExportErrorCode(str, Enum):
    UNAVAILABLE = 'unavailable'
    UNSAFE_PATH = 'unsafe_path'
    COLLISION = 'collision'
    IO = 'io'
    INTERRUPTED = 'interrupted'


class RuntimeExportError(PatchHarborError):
    def __init__(self, code: RuntimeExportErrorCode, message: str, *,
                 unavailable_reason: str | None = None,
                 published_path: Path | None = None) -> None:
        reason = {
            RuntimeExportErrorCode.UNAVAILABLE: FailureReason.SOURCE_ERROR,
            RuntimeExportErrorCode.UNSAFE_PATH: FailureReason.SOURCE_ERROR,
            RuntimeExportErrorCode.INTERRUPTED: FailureReason.INTERRUPTED,
        }.get(code, FailureReason.PAYLOAD_PREPARATION_ERROR)
        super().__init__(message, reason)
        self.code = code
        self.unavailable_reason = unavailable_reason
        self.published_path = published_path


@dataclass(frozen=True, slots=True)
class RuntimeExportResult:
    path: Path
    distribution_version: str
    size: int
    sha256: str
    profile: str
    requires_python: str
    content_id: str
    source_commit: str | None
    warnings: tuple[str, ...] = ()
