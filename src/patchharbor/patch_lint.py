from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


VALID_LINT_SEVERITIES = frozenset({"error", "warning", "info"})


class PatchLintError(ValueError):
    pass


@dataclass(frozen=True)
class PatchLintFinding:
    rule_id: str
    message: str
    severity: str = "warning"
    line_number: int | None = None
    column: int | None = None
    hint: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.rule_id, "finding rule_id")
        _require_non_empty_string(self.message, f"finding {self.rule_id} message")

        if self.severity not in VALID_LINT_SEVERITIES:
            allowed = ", ".join(sorted(VALID_LINT_SEVERITIES))
            raise PatchLintError(f"finding {self.rule_id} has unsupported severity: {self.severity}; allowed: {allowed}")

        if self.line_number is not None and (not isinstance(self.line_number, int) or self.line_number < 1):
            raise PatchLintError(f"finding {self.rule_id} line_number must be a positive integer when provided")

        if self.column is not None and (not isinstance(self.column, int) or self.column < 1):
            raise PatchLintError(f"finding {self.rule_id} column must be a positive integer when provided")

        if self.hint is not None and (not isinstance(self.hint, str) or not self.hint):
            raise PatchLintError(f"finding {self.rule_id} hint must be a non-empty string when provided")

        if not isinstance(self.data, Mapping):
            raise PatchLintError(f"finding {self.rule_id} data must be a mapping")

        object.__setattr__(self, "data", dict(self.data))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PatchLintFinding:
        if not isinstance(mapping, Mapping):
            raise PatchLintError("patch lint finding must be a mapping")

        known_fields = {"rule_id", "message", "severity", "line_number", "column", "hint"}
        extra = {key: value for key, value in mapping.items() if key not in known_fields}
        return cls(
            rule_id=_string_from_mapping(mapping, "rule_id"),
            message=_string_from_mapping(mapping, "message"),
            severity=_optional_string_from_mapping(mapping, "severity", "warning"),
            line_number=_optional_int_from_mapping(mapping, "line_number"),
            column=_optional_int_from_mapping(mapping, "column"),
            hint=_optional_string_or_none_from_mapping(mapping, "hint"),
            data=extra,
        )

    def location_label(self) -> str:
        if self.line_number is None:
            return "."
        if self.column is None:
            return f"line {self.line_number}"
        return f"line {self.line_number}:{self.column}"

    def render(self) -> str:
        text = f"{self.severity}: {self.rule_id}: {self.location_label()}: {self.message}"
        if self.hint:
            text = f"{text} Hint: {self.hint}"
        return text

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "rule_id": self.rule_id,
            "message": self.message,
            "severity": self.severity,
        }
        if self.line_number is not None:
            result["line_number"] = self.line_number
        if self.column is not None:
            result["column"] = self.column
        if self.hint is not None:
            result["hint"] = self.hint
        result.update(self.data)
        return result


@dataclass(frozen=True)
class PatchLintResult:
    findings: tuple[PatchLintFinding, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(self.findings)
        for finding in normalized:
            if not isinstance(finding, PatchLintFinding):
                raise PatchLintError("patch lint result findings must contain PatchLintFinding instances")
        object.__setattr__(self, "findings", normalized)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    @property
    def errors(self) -> tuple[PatchLintFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "error")

    @property
    def warnings(self) -> tuple[PatchLintFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "warning")

    @property
    def infos(self) -> tuple[PatchLintFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "info")

    @property
    def ok(self) -> bool:
        return not self.errors

    def with_finding(self, finding: PatchLintFinding) -> PatchLintResult:
        if not isinstance(finding, PatchLintFinding):
            raise PatchLintError("finding must be a PatchLintFinding")
        return PatchLintResult(self.findings + (finding,))

    def extend(self, findings: Iterable[PatchLintFinding]) -> PatchLintResult:
        result = self
        for finding in findings:
            result = result.with_finding(finding)
        return result

    def render_findings(self) -> tuple[str, ...]:
        return tuple(finding.render() for finding in self.findings)

    def raise_for_errors(self) -> None:
        if self.errors:
            raise PatchLintError("; ".join(finding.render() for finding in self.errors))

    def to_mapping(self) -> dict[str, Any]:
        return {"findings": [finding.to_mapping() for finding in self.findings]}


def findings_with_severity(
    findings: Iterable[PatchLintFinding],
    severity: str,
) -> tuple[PatchLintFinding, ...]:
    if severity not in VALID_LINT_SEVERITIES:
        allowed = ", ".join(sorted(VALID_LINT_SEVERITIES))
        raise PatchLintError(f"unsupported lint severity: {severity}; allowed: {allowed}")
    return tuple(finding for finding in findings if finding.severity == severity)


def sort_findings(findings: Iterable[PatchLintFinding]) -> tuple[PatchLintFinding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.line_number is None,
                finding.line_number or 0,
                finding.column is None,
                finding.column or 0,
                finding.rule_id,
                finding.message,
            ),
        )
    )


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise PatchLintError(f"{field} must be a non-empty string")


def _string_from_mapping(mapping: Mapping[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise PatchLintError(f"patch lint finding requires non-empty string field: {field}")
    return value


def _optional_string_from_mapping(mapping: Mapping[str, Any], field: str, default: str) -> str:
    value = mapping.get(field, default)
    if not isinstance(value, str) or not value:
        raise PatchLintError(f"patch lint finding field {field} must be a non-empty string")
    return value


def _optional_string_or_none_from_mapping(mapping: Mapping[str, Any], field: str) -> str | None:
    value = mapping.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise PatchLintError(f"patch lint finding field {field} must be a non-empty string when provided")
    return value


def _optional_int_from_mapping(mapping: Mapping[str, Any], field: str) -> int | None:
    value = mapping.get(field)
    if value is None:
        return None
    if not isinstance(value, int):
        raise PatchLintError(f"patch lint finding field {field} must be an integer when provided")
    return value
