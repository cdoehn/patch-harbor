"""Trusted host admission over owned package bytes within the existing Apply lock."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from patchharbor.apply_repository import SafeResolvedRepository, _inspect_repository_identity
from patchharbor.errors import ErrorKind, FailureReason, PatchHarborError, state_mismatch_error
from patchharbor.models import RepositoryContext
from patchharbor.patch_inspection import PatchInspection, inspect_captured_patch
from patchharbor.patch_package import ValidatedPatchPackage


@dataclass(frozen=True, slots=True)
class PatchAdmission:
    inspection: PatchInspection
    contents: Mapping[str, bytes]
    context: RepositoryContext


AdmissionCallback = Callable[[PatchAdmission], bool]


@dataclass(frozen=True, slots=True)
class ApplyAdmissionPolicy:
    expected_sha256: str
    expected_repository: Path
    admission: AdmissionCallback

    def check_target(self, resolved: SafeResolvedRepository) -> None:
        if resolved.repository.value != self.expected_repository:
            raise state_mismatch_error('registered target differs from explicitly expected repository')
        try:
            actual = _inspect_repository_identity(resolved.repository, resolved.repo_id)
        except PatchHarborError as exc:
            raise state_mismatch_error('expected repository identity changed') from exc
        if actual != resolved.repository:
            raise state_mismatch_error('expected repository path changed')

    def authorize(self, package: ValidatedPatchPackage, resolved: SafeResolvedRepository) -> None:
        self.check_target(resolved)
        if package.package_sha256 != self.expected_sha256:
            raise PatchHarborError('captured package SHA-256 differs from expected bytes', FailureReason.SOURCE_ERROR)
        facts = PatchAdmission(inspect_captured_patch(package),
            MappingProxyType({p.relative_path: p.content for p in package.entries}), resolved.context)
        try:
            decision = self.admission(facts)
        except BaseException as exc:
            raise PatchHarborError('host admission raised an exception', FailureReason.SOURCE_ERROR,
                                  error_kind=ErrorKind.ADMISSION_REJECTED) from exc
        if decision is not True:
            raise PatchHarborError('host admission did not explicitly accept this package', FailureReason.SOURCE_ERROR,
                                  error_kind=ErrorKind.ADMISSION_REJECTED)
        self.check_target(resolved)
