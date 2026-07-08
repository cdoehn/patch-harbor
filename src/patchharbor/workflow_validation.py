from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from patchharbor.workflow_rules import VALID_SEVERITIES, WorkflowRulesError, WorkflowRuleSet, load_rules_from_text


@dataclass(frozen=True)
class WorkflowRuleIssue:
    message: str
    severity: str = "error"
    path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.message, str) or not self.message:
            raise WorkflowRulesError("workflow rule issue message must be a non-empty string")
        if self.severity not in VALID_SEVERITIES:
            allowed = ", ".join(sorted(VALID_SEVERITIES))
            raise WorkflowRulesError(f"workflow rule issue has unsupported severity: {self.severity}; allowed: {allowed}")
        object.__setattr__(self, "path", tuple(self.path))

    def path_label(self) -> str:
        if not self.path:
            return "."
        return ".".join(self.path)

    def render(self) -> str:
        return f"{self.severity}: {self.path_label()}: {self.message}"


@dataclass(frozen=True)
class WorkflowRulesValidationResult:
    ruleset: WorkflowRuleSet | None
    issues: tuple[WorkflowRuleIssue, ...] = ()

    def __post_init__(self) -> None:
        for issue in self.issues:
            if not isinstance(issue, WorkflowRuleIssue):
                raise WorkflowRulesError("validation result issues must contain WorkflowRuleIssue instances")
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def errors(self) -> tuple[WorkflowRuleIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise WorkflowRulesError("; ".join(issue.render() for issue in self.errors))

    def render_issues(self) -> tuple[str, ...]:
        return tuple(issue.render() for issue in self.issues)


def validate_workflow_rules_text(text: str, *, source: str | None = None) -> WorkflowRulesValidationResult:
    try:
        ruleset = load_rules_from_text(text, source=source)
    except WorkflowRulesError as exc:
        return WorkflowRulesValidationResult(
            ruleset=None,
            issues=(WorkflowRuleIssue(str(exc), path=("document",)),),
        )

    return WorkflowRulesValidationResult(ruleset=ruleset)


def validate_workflow_rules_mapping(
    mapping: Mapping[str, Any],
    *,
    source: str | None = None,
) -> WorkflowRulesValidationResult:
    try:
        ruleset = WorkflowRuleSet.from_mapping(mapping, source=source)
    except WorkflowRulesError as exc:
        return WorkflowRulesValidationResult(
            ruleset=None,
            issues=(WorkflowRuleIssue(str(exc), path=("document",)),),
        )

    return WorkflowRulesValidationResult(ruleset=ruleset)


def validate_workflow_rules_file(path: str | Path) -> WorkflowRulesValidationResult:
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return WorkflowRulesValidationResult(
            ruleset=None,
            issues=(WorkflowRuleIssue(str(exc), path=("file",)),),
        )

    return validate_workflow_rules_text(text, source=str(file_path))


def summarize_validation_result(result: WorkflowRulesValidationResult) -> tuple[str, ...]:
    if result.ok:
        count = len(result.ruleset.rules) if result.ruleset is not None else 0
        return (f"status: ok", f"rules: {count}")
    return ("status: error", *result.render_issues())


def issues_with_severity(
    issues: Sequence[WorkflowRuleIssue],
    severity: str,
) -> tuple[WorkflowRuleIssue, ...]:
    if severity not in VALID_SEVERITIES:
        allowed = ", ".join(sorted(VALID_SEVERITIES))
        raise WorkflowRulesError(f"unsupported severity: {severity}; allowed: {allowed}")
    return tuple(issue for issue in issues if issue.severity == severity)
