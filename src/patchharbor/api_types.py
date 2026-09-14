"""Public value types for the synchronous API; import them from patchharbor.api.

Existing immutable repository/run facts are intentionally reused. There is no
second interpretation of security decisions, identifiers or completed runs.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TextIO
from uuid import UUID

from patchharbor.models import (
    DirectoryCandidate, GitObjectFormat, GitObjectId, RegistryListResult,
    RegistryRepository, RegistryStatus, RepositoryContext, RepositoryId,
    RepositoryPath,
)
from patchharbor.progress import (
    ActivityEvent, PackageFile, ProgressEvent, RepositoryResolved,
    RequestStarted, ScriptPrepared,
)
from patchharbor.run_report import (
    PrimaryResult, PrimaryResultKind, ResultBundleResult, ResultBundleStatus,
    RunOperation, RunReport, RunTiming, RunToolError,
)


ProgressObserver = Callable[[ProgressEvent], None]
CandidateSelector = Callable[[tuple[DirectoryCandidate, ...]], DirectoryCandidate]


@dataclass(frozen=True, slots=True)
class ConfigurationResult:
    """Persisted repository-local configuration, including its physical configuration file."""

    path: Path
    exchange_directory: Path | None
    bundle_suffix: str
    archive_directory: str


@dataclass(frozen=True, slots=True)
class UnregisterResult:
    """The mapping removed from the central registry, not deleted repository data."""

    repo_id: RepositoryId
    repository_path: RepositoryPath


@dataclass(frozen=True, slots=True)
class BundleResult:
    """One published manual bundle plus its unchanged structured run report."""

    report: RunReport

    @property
    def run_id(self) -> UUID:
        return self.report.run_id

    @property
    def context(self) -> RepositoryContext:
        context = self.report.context
        if context is None:
            raise RuntimeError("successful bundle has no repository context")
        return context

    @property
    def path(self) -> Path:
        path = self.report.result_bundle.path
        if path is None:
            raise RuntimeError("successful bundle has no published path")
        return path


@dataclass(frozen=True, slots=True)
class ScriptResult:
    """Normal completion of fs-run scripts, stopping at the first nonzero exit.

The exit code belongs to the child, not to PatchHarbor. Tool failures and
interrupted/timed-out executions instead raise PatchHarborError. No repository
Result Bundle is created by this legacy explicit runner.
    """

    exit_code: int

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True, slots=True)
class OutputStreams:
    """Optional caller-owned sinks. None means no delivery, never sys.stdout.

text receives live decoded, newline-normalized merged child stdout/stderr;
raw receives the complete merged original bytes. The current execution backend
does not retain separate stdout/stderr channels. Warnings have a separate sink
and callback. Text/raw sinks may be called on an output-reader thread. The API
flushes, but never closes, the sinks. Sink failures are execution errors, unlike
best-effort progress observers. The facade adds no in-memory capture buffer;
the existing Core still captures Apply logs for the Result Bundle.
    """

    text: TextIO | None = None
    raw: BinaryIO | None = None
    warnings: TextIO | None = None
    on_warning: Callable[[str], None] | None = None
