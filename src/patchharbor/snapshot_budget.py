"""Bound reconstructed allocations independently of compressed archive sizes."""
from __future__ import annotations

from dataclasses import dataclass
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.snapshot_types import ResultSnapshotError, SnapshotErrorCode


@dataclass(slots=True)
class SnapshotBudget:
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY
    allocated: int = 0

    def require_file(self, size: int) -> None:
        if size < 0 or size > self.policy.max_content_bytes:
            raise ResultSnapshotError(SnapshotErrorCode.RESOURCE_LIMIT,
                                      f'reconstructed content size {size} exceeds {self.policy.max_content_bytes}')

    def require(self, size: int) -> None:
        self.require_file(size)
        if self.allocated + size > self.policy.max_zip_total_bytes:
            raise ResultSnapshotError(SnapshotErrorCode.RESOURCE_LIMIT,
                                      f'reconstruction allocation exceeds {self.policy.max_zip_total_bytes}')

    def take(self, size: int) -> None:
        self.require(size)
        self.allocated += size
