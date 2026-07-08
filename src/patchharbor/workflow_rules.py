from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


DEFAULT_RULESET_VERSION = "1"
VALID_SEVERITIES = frozenset({"error", "warning", "info"})


class WorkflowRulesError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowRule:
    id: str
    description: str
    category: str = "general"
    severity: str = "error"
    enabled: bool = True
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.id, "rule id")
        _require_non_empty_string(self.description, f"rule {self.id} description")
        _require_non_empty_string(self.category, f"rule {self.id} category")

        if self.severity not in VALID_SEVERITIES:
            allowed = ", ".join(sorted(VALID_SEVERITIES))
            raise WorkflowRulesError(f"rule {self.id} has unsupported severity: {self.severity}; allowed: {allowed}")

        if not isinstance(self.enabled, bool):
            raise WorkflowRulesError(f"rule {self.id} enabled must be a boolean")

        if not isinstance(self.data, Mapping):
            raise WorkflowRulesError(f"rule {self.id} data must be a mapping")

        object.__setattr__(self, "data", dict(self.data))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> WorkflowRule:
        if not isinstance(mapping, Mapping):
            raise WorkflowRulesError("workflow rule must be a mapping")

        known_fields = {"id", "description", "category", "severity", "enabled"}
        extra = {key: value for key, value in mapping.items() if key not in known_fields}
        return cls(
            id=_string_from_mapping(mapping, "id"),
            description=_string_from_mapping(mapping, "description"),
            category=_optional_string_from_mapping(mapping, "category", "general"),
            severity=_optional_string_from_mapping(mapping, "severity", "error"),
            enabled=_optional_bool_from_mapping(mapping, "enabled", True),
            data=extra,
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "enabled": self.enabled,
        }
        result.update(self.data)
        return result


@dataclass(frozen=True)
class WorkflowRuleSet:
    version: str = DEFAULT_RULESET_VERSION
    rules: tuple[WorkflowRule, ...] = ()
    source: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.version, "ruleset version")
        normalized_rules = tuple(self.rules)
        for rule in normalized_rules:
            if not isinstance(rule, WorkflowRule):
                raise WorkflowRulesError("ruleset rules must contain WorkflowRule instances")

        ids = [rule.id for rule in normalized_rules]
        duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
        if duplicates:
            raise WorkflowRulesError(f"duplicate workflow rule ids: {', '.join(duplicates)}")

        if self.source is not None and (not isinstance(self.source, str) or not self.source):
            raise WorkflowRulesError("ruleset source must be a non-empty string when provided")

        object.__setattr__(self, "rules", normalized_rules)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any], *, source: str | None = None) -> WorkflowRuleSet:
        if not isinstance(mapping, Mapping):
            raise WorkflowRulesError("workflow rules document must be a mapping")

        version_value = mapping.get("version", DEFAULT_RULESET_VERSION)
        if not isinstance(version_value, str) or not version_value:
            raise WorkflowRulesError("workflow rules document requires non-empty string field: version")

        raw_rules = mapping.get("rules", ())
        if not isinstance(raw_rules, list):
            raise WorkflowRulesError("workflow rules document field rules must be a list")

        return cls(
            version=version_value,
            rules=tuple(WorkflowRule.from_mapping(item) for item in raw_rules),
            source=source,
        )

    def enabled_rules(self) -> tuple[WorkflowRule, ...]:
        return tuple(rule for rule in self.rules if rule.enabled)

    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.rules)

    def by_id(self) -> dict[str, WorkflowRule]:
        return {rule.id: rule for rule in self.rules}

    def to_mapping(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "rules": [rule.to_mapping() for rule in self.rules],
        }


def load_rules_from_text(text: str, *, source: str | None = None) -> WorkflowRuleSet:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkflowRulesError(f"workflow rules JSON is invalid: {exc.msg}") from exc

    if not isinstance(data, Mapping):
        raise WorkflowRulesError("workflow rules JSON must contain an object")

    return WorkflowRuleSet.from_mapping(data, source=source)


def rules_by_category(rules: Iterable[WorkflowRule]) -> dict[str, tuple[WorkflowRule, ...]]:
    grouped: dict[str, list[WorkflowRule]] = {}
    for rule in rules:
        grouped.setdefault(rule.category, []).append(rule)
    return {category: tuple(items) for category, items in grouped.items()}


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise WorkflowRulesError(f"{field} must be a non-empty string")


def _string_from_mapping(mapping: Mapping[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise WorkflowRulesError(f"workflow rule requires non-empty string field: {field}")
    return value


def _optional_string_from_mapping(mapping: Mapping[str, Any], field: str, default: str) -> str:
    value = mapping.get(field, default)
    if not isinstance(value, str) or not value:
        raise WorkflowRulesError(f"workflow rule field {field} must be a non-empty string")
    return value


def _optional_bool_from_mapping(mapping: Mapping[str, Any], field: str, default: bool) -> bool:
    value = mapping.get(field, default)
    if not isinstance(value, bool):
        raise WorkflowRulesError(f"workflow rule field {field} must be a boolean")
    return value
