"""Immutable public pack evidence; importing it does not load the pack engine."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from patchharbor.patch_inspection import PatchValidationResult, PatchValidationScope


@dataclass(frozen=True, slots=True)
class PatchPackResult:
    path: Path
    package_id: UUID
    created_at: datetime
    validation: PatchValidationResult
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise ValueError('pack result requires an absolute published path')
        if not isinstance(self.package_id, UUID) or self.package_id.version != 4:
            raise ValueError('pack result requires UUID v4')
        if self.created_at.tzinfo is None or self.created_at.utcoffset().total_seconds() != 0:
            raise ValueError('pack result requires a timezone-aware UTC timestamp')
        if (self.validation.scope is not PatchValidationScope.REFERENCE
                or self.validation.binding_matches is not True
                or not self.validation.reference_sha256 or self.validation.inspection.manifest is None):
            raise ValueError('pack result requires complete successful reference validation')
        if type(self.warnings) is not tuple or any(type(w) is not str for w in self.warnings):
            raise TypeError('pack warnings must be an immutable tuple of strings')

    @property
    def package_sha256(self) -> str:
        return self.validation.inspection.package_sha256

    @property
    def package_size(self) -> int:
        return self.validation.inspection.package_size

    @property
    def reference_sha256(self) -> str:
        assert self.validation.reference_sha256 is not None
        return self.validation.reference_sha256
