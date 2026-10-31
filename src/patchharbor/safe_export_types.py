"""Public source-safe export values; import through patchharbor.api."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import platform
import sys

from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.models import RepositoryContext


class SafeExportErrorCode(str, Enum):
    UNSUPPORTED_HOST = 'unsupported_host'
    UNSUPPORTED_CONVERSION = 'unsupported_conversion'
    REPOSITORY = 'repository'
    CONFIGURATION = 'configuration'
    UNSAFE_PATH = 'unsafe_path'
    STALE = 'stale'
    RESOURCE_LIMIT = 'resource_limit'
    IO = 'io'
    INTERRUPTED = 'interrupted'
    CLEANUP = 'cleanup'


class SafeExportError(PatchHarborError):
    def __init__(self, code: SafeExportErrorCode, message: str, *,
                 emergency_diagnostics_path: Path | None = None,
                 published_path: Path | None = None) -> None:
        reason = {
            SafeExportErrorCode.UNSUPPORTED_HOST: FailureReason.UNSUPPORTED_REPOSITORY_STATE,
            SafeExportErrorCode.UNSUPPORTED_CONVERSION: FailureReason.UNSUPPORTED_REPOSITORY_STATE,
            SafeExportErrorCode.REPOSITORY: FailureReason.REPOSITORY_ERROR,
            SafeExportErrorCode.CONFIGURATION: FailureReason.SOURCE_ERROR,
            SafeExportErrorCode.UNSAFE_PATH: FailureReason.SOURCE_ERROR,
            SafeExportErrorCode.STALE: FailureReason.STATE_MISMATCH,
            SafeExportErrorCode.INTERRUPTED: FailureReason.INTERRUPTED,
        }.get(code, FailureReason.RESULT_BUNDLE_ERROR)
        super().__init__(message, reason, emergency_diagnostics_path=emergency_diagnostics_path)
        self.code = code
        self.published_path = published_path


def supported_host() -> bool:
    return (sys.implementation.name == 'cpython' and (3, 10) <= sys.version_info[:2] <= (3, 14)
            and sys.platform.startswith('linux') and platform.machine().lower() in ('x86_64', 'amd64'))


def require_host() -> None:
    if not supported_host():
        raise SafeExportError(SafeExportErrorCode.UNSUPPORTED_HOST,
                              'safe reference contract 1 requires Linux x86-64 and CPython 3.10 through 3.14')


@dataclass(frozen=True, slots=True)
class SafeExportPlan:
    context: RepositoryContext
    output_directory: Path
    diagnostics_parent: Path
    lock_paths: tuple[Path, ...]
    configured_exchange: Path | None
    maintenance_enabled: bool
    binding_sha256: str
    _facts: tuple = field(repr=False)


def capture_mode(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError('capture_mode must be text')
    if value not in ('git', 'safe'):
        raise ValueError('capture_mode must be git or safe')
    return value
