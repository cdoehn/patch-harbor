from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from patchharbor.errors import ErrorKind, ExitCode, PatchHarborError
from patchharbor.models import (
    GitObjectFormat,
    GitObjectId,
    RepositoryContext,
    RepositoryId,
    RepositoryPath,
)
from patchharbor.run_report import (
    ApplyPrimaryOutcome,
    PrimaryResult,
    PrimaryResultKind,
    ResultBundleResult,
    ResultBundleStatus,
    RunOperation,
    RunReport,
    RunSession,
    RunTiming,
    physical_absolute_path_text,
)


_RUN_ID = UUID("12345678-1234-4234-8234-123456789abc")
_REPO_ID = RepositoryId("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _context(repository: Path) -> RepositoryContext:
    return RepositoryContext(
        repo_id=_REPO_ID,
        repository_path=RepositoryPath(repository.resolve()),
        base_commit=GitObjectId("a" * 40, GitObjectFormat.SHA1),
        dirty=False,
        state_fingerprint="7c9d2a24e397e0e5",
        fingerprint_algorithm="patchharbor-state-v1",
    )


def _timing(duration_seconds: float = 1.25) -> RunTiming:
    return RunTiming(
        run_id=_RUN_ID,
        started_at=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 12, 10, 0, 2, tzinfo=timezone.utc),
        duration_seconds=duration_seconds,
    )


def test_run_report_drives_persisted_and_bundle_json_results(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    context = _context(repository)
    bundle_path = tmp_path / "results" / "bundle.zip"
    report = RunReport(
        timing=_timing(),
        operation=RunOperation.BUNDLE,
        dry_run=False,
        context=context,
        repository=context.repository_path,
        repo_id=context.repo_id,
        warnings=(),
        primary_result=PrimaryResult.success_result(),
        result_bundle=ResultBundleResult.created(bundle_path),
        process_exit_code=0,
    )

    persisted = report.as_run_document()
    completion = report.manual_bundle_result()

    assert set(persisted) == {
        "run_id",
        "operation",
        "dry_run",
        "started_at",
        "ended_at",
        "duration_seconds",
        "repository_resolved",
        "repo_id",
        "repository_path",
        "base_commit",
        "state_fingerprint",
        "fingerprint_algorithm",
        "warnings",
        "execution_present",
        "primary_result",
        "result_bundle",
        "process_exit_code",
    }
    assert set(persisted["primary_result"]) == {
        "kind",
        "success",
        "patchharbor_error_code",
        "entrypoint_started",
        "entrypoint_exit_code",
        "timed_out",
        "interrupted",
    }
    assert set(persisted["result_bundle"]) == {
        "attempted",
        "status",
        "error",
    }
    assert set(completion) == {
        "run_id",
        "repo_id",
        "repository_path",
        "base_commit",
        "state_fingerprint",
        "fingerprint_algorithm",
        "result_bundle_status",
        "result_bundle_path",
        "emergency_diagnostics_path",
    }

    assert persisted["run_id"] == completion["run_id"]
    assert persisted["repo_id"] == completion["repo_id"]
    assert persisted["repository_path"] == completion["repository_path"]
    assert persisted["base_commit"] == completion["base_commit"]
    assert persisted["state_fingerprint"] == completion["state_fingerprint"]
    assert persisted["fingerprint_algorithm"] == completion["fingerprint_algorithm"]
    assert persisted["result_bundle"]["status"] == completion["result_bundle_status"]
    assert persisted["execution_present"] is False
    assert completion["result_bundle_path"] == str(bundle_path.resolve())
    json.dumps(persisted, allow_nan=False)
    json.dumps(completion, allow_nan=False)


@pytest.mark.parametrize("ended_monotonic", [float("nan"), float("inf"), 9.0])
def test_run_session_never_emits_nonfinite_or_negative_duration(
    ended_monotonic: float,
) -> None:
    session = RunSession(
        run_id=_RUN_ID,
        started_at=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
        started_monotonic=10.0,
    )

    timing = session.finish(
        ended_at=datetime(2026, 8, 12, 12, 0, 1, tzinfo=timezone.utc),
        ended_monotonic=ended_monotonic,
    )

    assert timing.duration_seconds == 0.0
    json.dumps({"duration_seconds": timing.duration_seconds}, allow_nan=False)


def test_run_report_redacts_secret_environment_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sensitive-value-123"
    monkeypatch.setenv("PATCHHARBOR_TEST_SECRET", secret)
    repository = tmp_path / "repository"
    repository.mkdir()
    context = _context(repository)
    report = RunReport(
        timing=_timing(),
        operation=RunOperation.BUNDLE,
        dry_run=False,
        context=context,
        repository=context.repository_path,
        repo_id=context.repo_id,
        warnings=(f"warning contains {secret}",),
        primary_result=PrimaryResult.tool_failure(
            kind=PrimaryResultKind.EXECUTION_ERROR,
            patchharbor_error_code=11,
        ),
        result_bundle=ResultBundleResult.failed(
            f"bundle error contains {secret}"
        ),
        process_exit_code=11,
    )

    serialized = json.dumps(report.as_run_document(), allow_nan=False)

    assert secret not in serialized
    assert "[redacted]" in serialized

    monkeypatch.setenv("PATCHHARBOR_SHORT_TOKEN", "x7")
    short_secret_report = ResultBundleResult.failed("failure contains x7")
    assert "x7" not in json.dumps(
        short_secret_report.as_run_document(),
        allow_nan=False,
    )


@pytest.mark.parametrize(
    ("error", "expected_kind"),
    (
        (
            PatchHarborError(
                "mismatch",
                ExitCode.STATE_MISMATCH,
                error_kind=ErrorKind.STATE_MISMATCH,
            ),
            PrimaryResultKind.STATE_MISMATCH,
        ),
        (
            PatchHarborError(
                "busy",
                ExitCode.REPOSITORY_BUSY,
                error_kind=ErrorKind.REPOSITORY_BUSY,
            ),
            PrimaryResultKind.REPOSITORY_BUSY,
        ),
        (
            PatchHarborError(
                "repository",
                ExitCode.REPOSITORY_ERROR,
                error_kind=ErrorKind.REPOSITORY_RESOLUTION_ERROR,
            ),
            PrimaryResultKind.REPOSITORY_ERROR,
        ),
        (
            PatchHarborError(
                "invalid entrypoint",
                ExitCode.NO_VALID_SCRIPT,
            ),
            PrimaryResultKind.VALIDATION_ERROR,
        ),
        (
            PatchHarborError(
                "execution",
                ExitCode.EXECUTION_ERROR,
            ),
            PrimaryResultKind.EXECUTION_ERROR,
        ),
    ),
)
def test_apply_primary_outcome_maps_tool_errors_once(
    error: PatchHarborError,
    expected_kind: PrimaryResultKind,
) -> None:
    outcome = ApplyPrimaryOutcome.from_tool_error(error)

    assert outcome.result.kind is expected_kind
    assert outcome.result.success is False
    assert outcome.result.patchharbor_error_code == int(error.exit_code)
    assert outcome.exit_code == int(error.exit_code)


def test_apply_primary_outcome_keeps_primary_and_bundle_results_separate() -> None:
    dry_run = ApplyPrimaryOutcome.dry_run_success()
    failure = ApplyPrimaryOutcome.from_tool_error(
        PatchHarborError("missing interpreter", ExitCode.INTERPRETER_ERROR)
    )

    assert dry_run.result.kind is PrimaryResultKind.DRY_RUN_SUCCESS
    assert dry_run.process_exit_code_for(ResultBundleStatus.CREATED) == 0
    assert dry_run.process_exit_code_for(ResultBundleStatus.FAILED) == int(
        ExitCode.RESULT_BUNDLE_ERROR
    )
    assert failure.result.kind is PrimaryResultKind.VALIDATION_ERROR
    assert failure.process_exit_code_for(ResultBundleStatus.CREATED) == int(
        ExitCode.INTERPRETER_ERROR
    )
    assert failure.process_exit_code_for(ResultBundleStatus.FAILED) == int(
        ExitCode.INTERPRETER_ERROR
    )

    with pytest.raises(ValueError):
        ApplyPrimaryOutcome(
            result=PrimaryResult.dry_run_success_result(),
            exit_code=int(ExitCode.RESULT_BUNDLE_ERROR),
        )
    with pytest.raises(ValueError):
        ApplyPrimaryOutcome(
            result=PrimaryResult.tool_failure(
                kind=PrimaryResultKind.VALIDATION_ERROR,
                patchharbor_error_code=int(ExitCode.NO_VALID_SCRIPT),
            ),
            exit_code=int(ExitCode.INTERPRETER_ERROR),
        )


def test_result_bundle_outcome_rejects_inconsistent_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ResultBundleResult(
            attempted=True,
            status=ResultBundleStatus.CREATED,
            path=tmp_path / "bundle.zip",
            emergency_diagnostics_path=tmp_path / "emergency",
        )
    with pytest.raises(ValueError):
        ResultBundleResult(
            attempted=True,
            status=ResultBundleStatus.FAILED,
        )


def test_manual_bundle_report_rejects_execution_or_wrong_exit_code(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    context = _context(repository)
    with pytest.raises(ValueError):
        RunReport(
            timing=_timing(),
            operation=RunOperation.BUNDLE,
            dry_run=False,
            context=context,
            repository=context.repository_path,
            repo_id=context.repo_id,
            warnings=(),
            primary_result=PrimaryResult(
                kind=PrimaryResultKind.SUCCESS,
                success=True,
                patchharbor_error_code=None,
                entrypoint_started=True,
                entrypoint_exit_code=0,
            ),
            result_bundle=ResultBundleResult.created(tmp_path / "bundle.zip"),
            process_exit_code=0,
        )
    with pytest.raises(ValueError):
        RunReport(
            timing=_timing(),
            operation=RunOperation.BUNDLE,
            dry_run=False,
            context=context,
            repository=context.repository_path,
            repo_id=context.repo_id,
            warnings=(),
            primary_result=PrimaryResult.tool_failure(
                kind=PrimaryResultKind.REPOSITORY_ERROR,
                patchharbor_error_code=8,
            ),
            result_bundle=ResultBundleResult.failed("repository failed"),
            process_exit_code=8,
        )

def test_run_timestamps_uuid_and_paths_are_canonical(tmp_path: Path) -> None:
    timing = RunTiming(
        run_id=_RUN_ID,
        started_at=datetime(
            2026,
            8,
            12,
            14,
            30,
            tzinfo=timezone(timedelta(hours=2)),
        ),
        ended_at=datetime(
            2026,
            8,
            12,
            14,
            30,
            1,
            tzinfo=timezone(timedelta(hours=2)),
        ),
        duration_seconds=1.0,
    )

    assert str(timing.run_id) == "12345678-1234-4234-8234-123456789abc"
    assert timing.started_at_text == "2026-08-12T12:30:00Z"
    assert timing.ended_at_text == "2026-08-12T12:30:01Z"
    assert physical_absolute_path_text(tmp_path / "missing" / "result.zip") == str(
        (tmp_path / "missing" / "result.zip").resolve()
    )


def test_resolved_apply_report_cannot_leave_bundle_unattempted(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    context = _context(repository)

    with pytest.raises(ValueError):
        RunReport(
            timing=_timing(),
            operation=RunOperation.APPLY,
            dry_run=True,
            context=context,
            repository=context.repository_path,
            repo_id=context.repo_id,
            warnings=(),
            primary_result=PrimaryResult.tool_failure(
                kind=PrimaryResultKind.STATE_MISMATCH,
                patchharbor_error_code=9,
            ),
            result_bundle=ResultBundleResult.not_attempted(
                "repository has already been resolved"
            ),
            process_exit_code=9,
        )

def test_apply_result_reports_dry_run_without_execution(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    context = _context(repository)
    bundle_path = tmp_path / "results" / "dry-run.zip"
    report = RunReport(
        timing=_timing(),
        operation=RunOperation.APPLY,
        dry_run=True,
        context=context,
        repository=context.repository_path,
        repo_id=context.repo_id,
        warnings=(),
        primary_result=PrimaryResult.dry_run_success_result(),
        result_bundle=ResultBundleResult.created(bundle_path),
        process_exit_code=0,
    )

    result = report.apply_result()

    assert set(result) == {
        "run_id",
        "repository_resolved",
        "repo_id",
        "repository_path",
        "primary_result",
        "result_bundle",
    }
    assert result["repository_resolved"] is True
    assert result["repo_id"] == str(context.repo_id)
    assert result["repository_path"] == str(repository.resolve())
    assert result["primary_result"] == {
        "kind": "dry_run_success",
        "entrypoint_started": False,
        "entrypoint_exit_code": None,
        "timed_out": False,
        "interrupted": False,
        "patchharbor_error_code": None,
    }
    assert result["result_bundle"] == {
        "attempted": True,
        "status": "created",
        "path": str(bundle_path.resolve()),
        "emergency_diagnostics_path": None,
    }
    assert report.as_run_document()["execution_present"] is False
    json.dumps(result, allow_nan=False)
