from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


VALID_RUN_STATUSES = frozenset({"pending", "running", "passed", "failed", "skipped"})
VALID_RUN_PHASES = frozenset(
    {
        "discover",
        "metadata",
        "repeat",
        "freshness",
        "syntax",
        "lint",
        "execute",
        "log",
        "lifecycle",
        "display",
    }
)
VALID_RUN_SEVERITIES = frozenset({"error", "warning", "info"})


class RunnerStatusError(ValueError):
    pass


@dataclass(frozen=True)
class RunnerIssue:
    message: str
    severity: str = "error"
    phase: str | None = None
    code: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.message, "runner issue message")
        if self.severity not in VALID_RUN_SEVERITIES:
            allowed = ", ".join(sorted(VALID_RUN_SEVERITIES))
            raise RunnerStatusError(f"runner issue has unsupported severity: {self.severity}; allowed: {allowed}")
        if self.phase is not None:
            _validate_phase(self.phase)
        if self.code is not None:
            _require_non_empty_string(self.code, "runner issue code")
        if not isinstance(self.data, Mapping):
            raise RunnerStatusError("runner issue data must be a mapping")
        object.__setattr__(self, "data", dict(self.data))

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    def render(self) -> str:
        prefix = self.severity
        if self.phase:
            prefix = f"{prefix}:{self.phase}"
        if self.code:
            prefix = f"{prefix}:{self.code}"
        return f"{prefix}: {self.message}"

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"message": self.message, "severity": self.severity}
        if self.phase is not None:
            result["phase"] = self.phase
        if self.code is not None:
            result["code"] = self.code
        result.update(self.data)
        return result

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> RunnerIssue:
        if not isinstance(mapping, Mapping):
            raise RunnerStatusError("runner issue must be a mapping")
        known_fields = {"message", "severity", "phase", "code"}
        data = {key: value for key, value in mapping.items() if key not in known_fields}
        return cls(
            message=_string_from_mapping(mapping, "message"),
            severity=_optional_string_from_mapping(mapping, "severity", "error"),
            phase=_optional_string_or_none_from_mapping(mapping, "phase"),
            code=_optional_string_or_none_from_mapping(mapping, "code"),
            data=data,
        )


@dataclass(frozen=True)
class RunnerPhaseResult:
    phase: str
    status: str = "pending"
    message: str | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    issues: tuple[RunnerIssue, ...] = ()

    def __post_init__(self) -> None:
        _validate_phase(self.phase)
        _validate_status(self.status)
        if self.message is not None:
            _require_non_empty_string(self.message, f"runner phase {self.phase} message")
        if self.exit_code is not None and not isinstance(self.exit_code, int):
            raise RunnerStatusError(f"runner phase {self.phase} exit_code must be an integer when provided")
        if self.duration_seconds is not None:
            if not isinstance(self.duration_seconds, (int, float)) or self.duration_seconds < 0:
                raise RunnerStatusError(f"runner phase {self.phase} duration_seconds must be a non-negative number")
            object.__setattr__(self, "duration_seconds", float(self.duration_seconds))
        normalized_issues = tuple(self.issues)
        for issue in normalized_issues:
            if not isinstance(issue, RunnerIssue):
                raise RunnerStatusError("runner phase issues must contain RunnerIssue instances")
        object.__setattr__(self, "issues", normalized_issues)

    @property
    def errors(self) -> tuple[RunnerIssue, ...]:
        return tuple(issue for issue in self.issues if issue.is_error)

    @property
    def ok(self) -> bool:
        return self.status in {"passed", "skipped"} and not self.errors

    def with_issue(self, issue: RunnerIssue) -> RunnerPhaseResult:
        if not isinstance(issue, RunnerIssue):
            raise RunnerStatusError("issue must be a RunnerIssue")
        return RunnerPhaseResult(
            phase=self.phase,
            status="failed" if issue.is_error else self.status,
            message=self.message,
            exit_code=self.exit_code,
            duration_seconds=self.duration_seconds,
            issues=self.issues + (issue,),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "phase": self.phase,
            "status": self.status,
            "issues": [issue.to_mapping() for issue in self.issues],
        }
        if self.message is not None:
            result["message"] = self.message
        if self.exit_code is not None:
            result["exit_code"] = self.exit_code
        if self.duration_seconds is not None:
            result["duration_seconds"] = self.duration_seconds
        return result

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> RunnerPhaseResult:
        if not isinstance(mapping, Mapping):
            raise RunnerStatusError("runner phase result must be a mapping")
        return cls(
            phase=_string_from_mapping(mapping, "phase"),
            status=_optional_string_from_mapping(mapping, "status", "pending"),
            message=_optional_string_or_none_from_mapping(mapping, "message"),
            exit_code=_optional_int_from_mapping(mapping, "exit_code"),
            duration_seconds=_optional_number_from_mapping(mapping, "duration_seconds"),
            issues=tuple(RunnerIssue.from_mapping(item) for item in _optional_sequence_from_mapping(mapping, "issues")),
        )


@dataclass(frozen=True)
class RunnerResult:
    status: str = "pending"
    script_path: str | None = None
    log_path: str | None = None
    exit_code: int | None = None
    phases: tuple[RunnerPhaseResult, ...] = ()
    issues: tuple[RunnerIssue, ...] = ()

    def __post_init__(self) -> None:
        _validate_status(self.status)
        if self.script_path is not None:
            _require_non_empty_string(self.script_path, "runner result script_path")
        if self.log_path is not None:
            _require_non_empty_string(self.log_path, "runner result log_path")
        if self.exit_code is not None and not isinstance(self.exit_code, int):
            raise RunnerStatusError("runner result exit_code must be an integer when provided")

        normalized_phases = tuple(self.phases)
        seen: set[str] = set()
        for phase in normalized_phases:
            if not isinstance(phase, RunnerPhaseResult):
                raise RunnerStatusError("runner result phases must contain RunnerPhaseResult instances")
            if phase.phase in seen:
                raise RunnerStatusError(f"duplicate runner phase: {phase.phase}")
            seen.add(phase.phase)
        object.__setattr__(self, "phases", normalized_phases)

        normalized_issues = tuple(self.issues)
        for issue in normalized_issues:
            if not isinstance(issue, RunnerIssue):
                raise RunnerStatusError("runner result issues must contain RunnerIssue instances")
        object.__setattr__(self, "issues", normalized_issues)

    @property
    def errors(self) -> tuple[RunnerIssue, ...]:
        phase_errors = tuple(issue for phase in self.phases for issue in phase.errors)
        own_errors = tuple(issue for issue in self.issues if issue.is_error)
        return own_errors + phase_errors

    @property
    def ok(self) -> bool:
        return self.status == "passed" and not self.errors

    def phase_names(self) -> tuple[str, ...]:
        return tuple(phase.phase for phase in self.phases)

    def by_phase(self) -> dict[str, RunnerPhaseResult]:
        return {phase.phase: phase for phase in self.phases}

    def with_phase(self, phase: RunnerPhaseResult) -> RunnerResult:
        if not isinstance(phase, RunnerPhaseResult):
            raise RunnerStatusError("phase must be a RunnerPhaseResult")
        existing = self.by_phase()
        existing[phase.phase] = phase
        return RunnerResult(
            status=derive_runner_status(existing.values(), self.issues),
            script_path=self.script_path,
            log_path=self.log_path,
            exit_code=self.exit_code,
            phases=tuple(existing.values()),
            issues=self.issues,
        )

    def with_issue(self, issue: RunnerIssue) -> RunnerResult:
        if not isinstance(issue, RunnerIssue):
            raise RunnerStatusError("issue must be a RunnerIssue")
        issues = self.issues + (issue,)
        return RunnerResult(
            status="failed" if issue.is_error else self.status,
            script_path=self.script_path,
            log_path=self.log_path,
            exit_code=self.exit_code,
            phases=self.phases,
            issues=issues,
        )

    def render_summary(self) -> tuple[str, ...]:
        lines = [f"status: {self.status}"]
        if self.script_path:
            lines.append(f"script: {self.script_path}")
        if self.log_path:
            lines.append(f"log: {self.log_path}")
        if self.exit_code is not None:
            lines.append(f"exit_code: {self.exit_code}")
        for phase in self.phases:
            label = phase.phase
            if phase.message:
                label = f"{label} - {phase.message}"
            lines.append(f"phase: {label}: {phase.status}")
        for issue in self.issues:
            lines.append(issue.render())
        for phase in self.phases:
            for issue in phase.issues:
                lines.append(issue.render())
        return tuple(lines)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
            "phases": [phase.to_mapping() for phase in self.phases],
            "issues": [issue.to_mapping() for issue in self.issues],
        }
        if self.script_path is not None:
            result["script_path"] = self.script_path
        if self.log_path is not None:
            result["log_path"] = self.log_path
        if self.exit_code is not None:
            result["exit_code"] = self.exit_code
        return result

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> RunnerResult:
        if not isinstance(mapping, Mapping):
            raise RunnerStatusError("runner result must be a mapping")
        return cls(
            status=_optional_string_from_mapping(mapping, "status", "pending"),
            script_path=_optional_string_or_none_from_mapping(mapping, "script_path"),
            log_path=_optional_string_or_none_from_mapping(mapping, "log_path"),
            exit_code=_optional_int_from_mapping(mapping, "exit_code"),
            phases=tuple(RunnerPhaseResult.from_mapping(item) for item in _optional_sequence_from_mapping(mapping, "phases")),
            issues=tuple(RunnerIssue.from_mapping(item) for item in _optional_sequence_from_mapping(mapping, "issues")),
        )


def derive_runner_status(phases: Iterable[RunnerPhaseResult], issues: Iterable[RunnerIssue] = ()) -> str:
    phase_tuple = tuple(phases)
    issue_tuple = tuple(issues)

    if any(issue.is_error for issue in issue_tuple):
        return "failed"
    if any(phase.status == "failed" or phase.errors for phase in phase_tuple):
        return "failed"
    if any(phase.status == "running" for phase in phase_tuple):
        return "running"
    if phase_tuple and all(phase.status in {"passed", "skipped"} for phase in phase_tuple):
        return "passed"
    return "pending"


def passed_phase(phase: str, message: str | None = None) -> RunnerPhaseResult:
    return RunnerPhaseResult(phase=phase, status="passed", message=message)


def failed_phase(phase: str, message: str, *, code: str | None = None) -> RunnerPhaseResult:
    issue = RunnerIssue(message=message, phase=phase, code=code)
    return RunnerPhaseResult(phase=phase, status="failed", message=message, issues=(issue,))


def _validate_status(status: str) -> None:
    if status not in VALID_RUN_STATUSES:
        allowed = ", ".join(sorted(VALID_RUN_STATUSES))
        raise RunnerStatusError(f"unsupported runner status: {status}; allowed: {allowed}")


def _validate_phase(phase: str) -> None:
    if phase not in VALID_RUN_PHASES:
        allowed = ", ".join(sorted(VALID_RUN_PHASES))
        raise RunnerStatusError(f"unsupported runner phase: {phase}; allowed: {allowed}")


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise RunnerStatusError(f"{field} must be a non-empty string")


def _string_from_mapping(mapping: Mapping[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise RunnerStatusError(f"runner status mapping requires non-empty string field: {field}")
    return value


def _optional_string_from_mapping(mapping: Mapping[str, Any], field: str, default: str) -> str:
    value = mapping.get(field, default)
    if not isinstance(value, str) or not value:
        raise RunnerStatusError(f"runner status field {field} must be a non-empty string")
    return value


def _optional_string_or_none_from_mapping(mapping: Mapping[str, Any], field: str) -> str | None:
    value = mapping.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RunnerStatusError(f"runner status field {field} must be a non-empty string when provided")
    return value


def _optional_int_from_mapping(mapping: Mapping[str, Any], field: str) -> int | None:
    value = mapping.get(field)
    if value is None:
        return None
    if not isinstance(value, int):
        raise RunnerStatusError(f"runner status field {field} must be an integer when provided")
    return value


def _optional_number_from_mapping(mapping: Mapping[str, Any], field: str) -> float | None:
    value = mapping.get(field)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise RunnerStatusError(f"runner status field {field} must be a number when provided")
    return float(value)


def _optional_sequence_from_mapping(mapping: Mapping[str, Any], field: str) -> tuple[Any, ...]:
    value = mapping.get(field, ())
    if not isinstance(value, list | tuple):
        raise RunnerStatusError(f"runner status field {field} must be a sequence when provided")
    return tuple(value)
