from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.run_report import (
    PrimaryResult,
    ResultBundleResult,
    RunOperation,
    RunReport,
    RunTiming,
)


def successful_bundle_run_report(
    repository: Path,
    final_path: Path,
) -> RunReport:
    repository.mkdir(parents=True, exist_ok=True)
    context = RepositoryContext(
        repo_id=RepositoryId("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        repository_path=RepositoryPath(repository.resolve()),
        base_commit=GitObjectId("a" * 40, GitObjectFormat.SHA1),
        dirty=False,
        state_fingerprint="7c9d2a24e397e0e5",
        fingerprint_algorithm="patchharbor-state-v1",
    )
    return RunReport(
        timing=RunTiming(
            run_id=UUID("12345678-1234-4234-8234-123456789abc"),
            started_at=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 8, 12, 10, 0, 1, tzinfo=timezone.utc),
            duration_seconds=1.0,
        ),
        operation=RunOperation.BUNDLE,
        dry_run=False,
        context=context,
        repository=context.repository_path,
        repo_id=context.repo_id,
        warnings=(),
        primary_result=PrimaryResult.success_result(),
        result_bundle=ResultBundleResult.created(final_path),
        process_exit_code=0,
    )
