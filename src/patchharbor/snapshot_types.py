"""Immutable public snapshot values; supported imports live in patchharbor.api."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.models import GitObjectId
from patchharbor.result_reader import ReferenceContext
from patchharbor.run_report import PrimaryResult


class SnapshotErrorCode(str, Enum):
    INVALID_RESULT = 'invalid_result'
    DIGEST_MISMATCH = 'digest_mismatch'
    INVALID_PATCH = 'invalid_patch'
    UNSUPPORTED_PATCH = 'unsupported_patch'
    PATH_COLLISION = 'path_collision'
    RESOURCE_LIMIT = 'resource_limit'


class ResultSnapshotError(PatchHarborError):
    """Complete snapshot validation failed; no partial snapshot is returned."""

    def __init__(self, code: SnapshotErrorCode, message: str) -> None:
        super().__init__(message, FailureReason.SOURCE_ERROR)
        self.code = code


@dataclass(frozen=True, slots=True)
class SnapshotFile:
    path: str
    mode: str
    content: bytes
    sha256: str
    object_id: GitObjectId

    @property
    def size(self) -> int:
        return len(self.content)

    @property
    def kind(self) -> str:
        return 'regular'


@dataclass(frozen=True, slots=True)
class SnapshotLayer:
    name: str
    files: Mapping[str, SnapshotFile]


@dataclass(frozen=True, slots=True)
class SnapshotRuntime:
    status: str
    reason: str | None
    version: str | None
    requires_python: str | None
    profile: str | None
    content_id: str | None
    artifact_sha256: str | None
    artifact_size: int | None


@dataclass(frozen=True, slots=True)
class ResultSnapshot:
    sha256: str
    format_version: int
    context: ReferenceContext
    run_id: str
    operation: str
    dry_run: bool
    primary_result: PrimaryResult
    warnings: tuple[str, ...]
    runtime: SnapshotRuntime
    base: SnapshotLayer
    index: SnapshotLayer
    worktree: SnapshotLayer
    untracked: SnapshotLayer
    effective: SnapshotLayer


@dataclass(frozen=True, slots=True)
class IntegrationCapabilities:
    contract_version: int
    snapshot_contract_version: int | None
    guarded_apply_contract_version: int | None
