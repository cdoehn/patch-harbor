from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping

from patchharbor.patch_lint import PatchLintError, PatchLintFinding
from patchharbor.patch_lint_api import lint_patch_file
from patchharbor.runner_preflight import run_preflight_checks
from patchharbor.runner_status import RunnerIssue, RunnerPhaseResult, RunnerResult, RunnerStatusError


class RunnerCoreError(RunnerStatusError):
    pass


@dataclass(frozen=True)
class RunnerExecutionConfig:
    working_directory: str | Path | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    successful_patch_ids: tuple[str, ...] = ()
    max_age_seconds: int | float | None = None
    now: int | float | None = None
    timeout_seconds: int | float | None = None
    run_lint: bool = False
    execute: bool = True

    def __post_init__(self) -> None:
        if self.working_directory is not None:
            object.__setattr__(self, "working_directory", _path_from(self.working_directory, "working_directory"))
        if not isinstance(self.environment, Mapping):
            raise RunnerCoreError("environment must be a mapping of strings")
        env = dict(self.environment)
        for key, value in env.items():
            if not isinstance(key, str) or not key:
                raise RunnerCoreError("environment keys must be non-empty strings")
            if not isinstance(value, str):
                raise RunnerCoreError("environment values must be strings")
        object.__setattr__(self, "environment", env)

        if isinstance(self.successful_patch_ids, (str, bytes)):
            raise RunnerCoreError("successful_patch_ids must be a tuple of patch id strings, not a single string")
        successful_patch_ids = tuple(self.successful_patch_ids)
        for patch_id in successful_patch_ids:
            if not isinstance(patch_id, str) or not patch_id:
                raise RunnerCoreError("successful_patch_ids must contain non-empty strings")
        object.__setattr__(self, "successful_patch_ids", successful_patch_ids)

        if self.max_age_seconds is not None and (not _is_number(self.max_age_seconds) or float(self.max_age_seconds) < 0):
            raise RunnerCoreError("max_age_seconds must be a non-negative number when provided")
        if self.now is not None and not _is_number(self.now):
            raise RunnerCoreError("now must be a number when provided")
        if self.timeout_seconds is not None and (not _is_number(self.timeout_seconds) or float(self.timeout_seconds) < 0):
            raise RunnerCoreError("timeout_seconds must be a non-negative number when provided")
        if not isinstance(self.run_lint, bool):
            raise RunnerCoreError("run_lint must be a boolean")
        if not isinstance(self.execute, bool):
            raise RunnerCoreError("execute must be a boolean")


def check_bash_syntax(script_path: str | Path, *, timeout_seconds: int | float | None = None) -> RunnerPhaseResult:
    script = _path_from(script_path, "script_path")
    timeout = _timeout_from(timeout_seconds)

    try:
        completed = subprocess.run(
            ["bash", "-n", str(script)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RunnerPhaseResult(
            "syntax",
            status="failed",
            message="bash syntax check timed out",
            issues=(RunnerIssue(str(exc), phase="syntax", code="syntax.timeout"),),
        )
    except OSError as exc:
        return RunnerPhaseResult(
            "syntax",
            status="failed",
            message="unable to run bash syntax check",
            issues=(RunnerIssue(str(exc), phase="syntax", code="syntax.unavailable"),),
        )

    if completed.returncode == 0:
        return RunnerPhaseResult("syntax", status="passed", message="bash syntax ok", exit_code=0)

    message = completed.stderr.strip() or completed.stdout.strip() or f"bash -n exited with {completed.returncode}"
    return RunnerPhaseResult(
        "syntax",
        status="failed",
        message="bash syntax failed",
        exit_code=completed.returncode,
        issues=(
            RunnerIssue(
                message,
                phase="syntax",
                code="syntax.failed",
                data={"exit_code": completed.returncode},
            ),
        ),
    )


def lint_script_for_runner(script_path: str | Path) -> RunnerPhaseResult:
    try:
        lint_result = lint_patch_file(script_path)
    except PatchLintError as exc:
        return RunnerPhaseResult(
            "lint",
            status="failed",
            message="patch lint failed",
            issues=(RunnerIssue(str(exc), phase="lint", code="lint.failed"),),
        )

    if not lint_result.has_findings:
        return RunnerPhaseResult("lint", status="passed", message="patch lint ok")

    issues = tuple(_issue_from_lint_finding(finding) for finding in lint_result.findings)
    status = "failed" if lint_result.errors else "passed"
    message = "patch lint errors" if lint_result.errors else "patch lint warnings"
    return RunnerPhaseResult("lint", status=status, message=message, issues=issues)


def execute_patch_script(script_path: str | Path, config: RunnerExecutionConfig | None = None) -> RunnerPhaseResult:
    effective_config = config or RunnerExecutionConfig()
    script = _path_from(script_path, "script_path")
    env = os.environ.copy()
    env.update(effective_config.environment)
    cwd = None if effective_config.working_directory is None else str(effective_config.working_directory)
    timeout = _timeout_from(effective_config.timeout_seconds)

    start = time.monotonic()
    try:
        completed = subprocess.run(
            ["bash", str(script)],
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RunnerPhaseResult(
            "execute",
            status="failed",
            message="script execution timed out",
            issues=(RunnerIssue(str(exc), phase="execute", code="execute.timeout"),),
        )
    except OSError as exc:
        return RunnerPhaseResult(
            "execute",
            status="failed",
            message="unable to execute script",
            issues=(RunnerIssue(str(exc), phase="execute", code="execute.unavailable"),),
        )

    duration_seconds = time.monotonic() - start
    if completed.returncode == 0:
        return RunnerPhaseResult(
            "execute",
            status="passed",
            message="script exited 0",
            exit_code=0,
            duration_seconds=duration_seconds,
        )

    return RunnerPhaseResult(
        "execute",
        status="failed",
        message=f"script exited {completed.returncode}",
        exit_code=completed.returncode,
        duration_seconds=duration_seconds,
        issues=(
            RunnerIssue(
                f"patch script exited with code {completed.returncode}",
                phase="execute",
                code="execute.failed",
                data={
                    "exit_code": completed.returncode,
                    "stdout_tail": _tail(completed.stdout),
                    "stderr_tail": _tail(completed.stderr),
                },
            ),
        ),
    )


def run_patch_script(script_path: str | Path, config: RunnerExecutionConfig | None = None) -> RunnerResult:
    effective_config = config or RunnerExecutionConfig()
    script = _path_from(script_path, "script_path")

    result = run_preflight_checks(
        script,
        successful_patch_ids=effective_config.successful_patch_ids,
        max_age_seconds=effective_config.max_age_seconds,
        now=effective_config.now,
    )

    if result.status == "failed":
        result = result.with_phase(RunnerPhaseResult("syntax", status="skipped", message="syntax skipped after failed preflight"))
        result = result.with_phase(RunnerPhaseResult("lint", status="skipped", message="lint skipped after failed preflight"))
        result = result.with_phase(RunnerPhaseResult("execute", status="skipped", message="execution skipped after failed preflight"))
        return result

    syntax = check_bash_syntax(script, timeout_seconds=effective_config.timeout_seconds)
    result = result.with_phase(syntax)
    if syntax.status == "failed":
        result = result.with_phase(RunnerPhaseResult("lint", status="skipped", message="lint skipped after syntax failure"))
        result = result.with_phase(RunnerPhaseResult("execute", status="skipped", message="execution skipped after syntax failure"))
        return result

    if effective_config.run_lint:
        lint = lint_script_for_runner(script)
    else:
        lint = RunnerPhaseResult("lint", status="skipped", message="patch lint disabled")
    result = result.with_phase(lint)
    if lint.status == "failed":
        result = result.with_phase(RunnerPhaseResult("execute", status="skipped", message="execution skipped after lint failure"))
        return result

    if not effective_config.execute:
        result = result.with_phase(RunnerPhaseResult("execute", status="skipped", message="execution disabled"))
        return result

    return result.with_phase(execute_patch_script(script, effective_config))


def _issue_from_lint_finding(finding: PatchLintFinding) -> RunnerIssue:
    data: dict[str, Any] = {}
    if finding.line_number is not None:
        data["line_number"] = finding.line_number
    if finding.column is not None:
        data["column"] = finding.column
    if finding.hint is not None:
        data["hint"] = finding.hint

    return RunnerIssue(
        finding.message,
        severity=finding.severity,
        phase="lint",
        code=finding.rule_id,
        data=data,
    )


def _path_from(value: str | Path, field: str) -> Path:
    if isinstance(value, str) and not value:
        raise RunnerCoreError(f"{field} must be a non-empty path")
    try:
        return Path(value).expanduser()
    except TypeError as exc:
        raise RunnerCoreError(f"{field} must be a path-like value") from exc


def _timeout_from(value: int | float | None) -> float | None:
    if value is None:
        return None
    if not _is_number(value) or float(value) < 0:
        raise RunnerCoreError("timeout_seconds must be a non-negative number when provided")
    return float(value)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _tail(text: str, *, lines: int = 20) -> str:
    if not text:
        return ""
    split = text.splitlines()
    return "\n".join(split[-lines:])
