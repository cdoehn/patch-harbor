from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


class PublicAuditModelError(ValueError):
    pass


VALID_SEVERITIES = frozenset({"error", "warning", "info"})
VALID_TARGET_TYPES = frozenset({"tracked", "history", "text"})


@dataclass(frozen=True)
class PublicAuditPattern:
    name: str
    value: str
    severity: str = "error"
    description: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.name, "public audit pattern name")
        _require_non_empty_string(self.value, "public audit pattern value")
        if self.severity not in VALID_SEVERITIES:
            raise PublicAuditModelError("public audit pattern severity must be error, warning, or info")
        if self.description is not None:
            _require_non_empty_string(self.description, "public audit pattern description")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PublicAuditPattern:
        if not isinstance(mapping, Mapping):
            raise PublicAuditModelError("public audit pattern must be a mapping")
        return cls(
            name=_string_from_mapping(mapping, "name"),
            value=_string_from_mapping(mapping, "value"),
            severity=_string_from_mapping(mapping, "severity", default="error"),
            description=_optional_string_from_mapping(mapping, "description"),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "severity": self.severity,
        }
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass(frozen=True)
class PublicAuditTarget:
    path: str
    target_type: str = "tracked"
    label: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path_string(self.path, "public audit target path"))
        if self.target_type not in VALID_TARGET_TYPES:
            raise PublicAuditModelError("public audit target type must be tracked, history, or text")
        if self.label is not None:
            _require_non_empty_string(self.label, "public audit target label")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PublicAuditTarget:
        if not isinstance(mapping, Mapping):
            raise PublicAuditModelError("public audit target must be a mapping")
        return cls(
            path=_string_from_mapping(mapping, "path"),
            target_type=_string_from_mapping(mapping, "target_type", default="tracked"),
            label=_optional_string_from_mapping(mapping, "label"),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": self.path,
            "target_type": self.target_type,
        }
        if self.label is not None:
            result["label"] = self.label
        return result


@dataclass(frozen=True)
class PublicAuditFinding:
    target: PublicAuditTarget
    pattern: PublicAuditPattern
    line: int
    text: str
    column: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target, PublicAuditTarget):
            raise PublicAuditModelError("public audit finding target must be PublicAuditTarget")
        if not isinstance(self.pattern, PublicAuditPattern):
            raise PublicAuditModelError("public audit finding pattern must be PublicAuditPattern")
        if not isinstance(self.line, int) or self.line < 1:
            raise PublicAuditModelError("public audit finding line must be a positive integer")
        _require_non_empty_string(self.text, "public audit finding text")
        if self.column is not None and (not isinstance(self.column, int) or self.column < 1):
            raise PublicAuditModelError("public audit finding column must be a positive integer")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> PublicAuditFinding:
        if not isinstance(mapping, Mapping):
            raise PublicAuditModelError("public audit finding must be a mapping")
        return cls(
            target=PublicAuditTarget.from_mapping(_mapping_from_mapping(mapping, "target")),
            pattern=PublicAuditPattern.from_mapping(_mapping_from_mapping(mapping, "pattern")),
            line=_positive_int_from_mapping(mapping, "line"),
            text=_string_from_mapping(mapping, "text"),
            column=_optional_positive_int_from_mapping(mapping, "column"),
        )

    @property
    def severity(self) -> str:
        return self.pattern.severity

    @property
    def path(self) -> str:
        return self.target.path

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "target": self.target.to_mapping(),
            "pattern": self.pattern.to_mapping(),
            "line": self.line,
            "text": self.text,
        }
        if self.column is not None:
            result["column"] = self.column
        return result


@dataclass(frozen=True)
class PublicAuditResult:
    findings: tuple[PublicAuditFinding, ...] = ()
    scanned_targets: int = 0
    skipped_targets: int = 0
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        findings = tuple(_finding_from(value) for value in self.findings)
        object.__setattr__(self, "findings", findings)
        object.__setattr__(self, "metadata", _string_mapping(self.metadata, "public audit metadata"))
        if not isinstance(self.scanned_targets, int) or self.scanned_targets < 0:
            raise PublicAuditModelError("scanned_targets must be a non-negative integer")
        if not isinstance(self.skipped_targets, int) or self.skipped_targets < 0:
            raise PublicAuditModelError("skipped_targets must be a non-negative integer")

    @property
    def ok(self) -> bool:
        return not any(finding.severity == "error" for finding in self.findings)

    @property
    def failed(self) -> bool:
        return not self.ok

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def findings_by_severity(self, severity: str) -> tuple[PublicAuditFinding, ...]:
        if severity not in VALID_SEVERITIES:
            raise PublicAuditModelError("severity must be error, warning, or info")
        return tuple(finding for finding in self.findings if finding.severity == severity)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "findings": [finding.to_mapping() for finding in self.findings],
            "scanned_targets": self.scanned_targets,
            "skipped_targets": self.skipped_targets,
            "ok": self.ok,
        }
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


def public_audit_pattern_from_mapping(mapping: Mapping[str, Any]) -> PublicAuditPattern:
    return PublicAuditPattern.from_mapping(mapping)


def public_audit_patterns_from_mappings(mappings: Iterable[Mapping[str, Any]]) -> tuple[PublicAuditPattern, ...]:
    if isinstance(mappings, (str, bytes, bytearray)):
        raise PublicAuditModelError("public audit patterns must be an iterable of mappings")
    patterns = tuple(PublicAuditPattern.from_mapping(mapping) for mapping in mappings)
    _ensure_unique_pattern_names(patterns)
    return patterns


def public_audit_pattern_index(patterns: Iterable[PublicAuditPattern]) -> dict[str, PublicAuditPattern]:
    if isinstance(patterns, (str, bytes, bytearray)):
        raise PublicAuditModelError("public audit patterns must be an iterable of PublicAuditPattern")
    normalized = tuple(_pattern_from(pattern) for pattern in patterns)
    _ensure_unique_pattern_names(normalized)
    return {pattern.name: pattern for pattern in normalized}


def _ensure_unique_pattern_names(patterns: Sequence[PublicAuditPattern]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for pattern in patterns:
        if pattern.name in seen:
            duplicates.append(pattern.name)
        seen.add(pattern.name)
    if duplicates:
        raise PublicAuditModelError(f"duplicate public audit pattern name: {duplicates[0]}")


def _pattern_from(value: object) -> PublicAuditPattern:
    if isinstance(value, PublicAuditPattern):
        return value
    if isinstance(value, Mapping):
        return PublicAuditPattern.from_mapping(value)
    raise PublicAuditModelError("public audit patterns must contain PublicAuditPattern or mapping values")


def _finding_from(value: object) -> PublicAuditFinding:
    if isinstance(value, PublicAuditFinding):
        return value
    if isinstance(value, Mapping):
        return PublicAuditFinding.from_mapping(value)
    raise PublicAuditModelError("public audit findings must contain PublicAuditFinding or mapping values")


def _mapping_from_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    if key not in mapping:
        raise PublicAuditModelError(f"missing required mapping field: {key}")
    value = mapping[key]
    if not isinstance(value, Mapping):
        raise PublicAuditModelError(f"{key} must be a mapping")
    return value


def _string_from_mapping(mapping: Mapping[str, Any], key: str, *, default: str | None = None) -> str:
    if key not in mapping:
        if default is None:
            raise PublicAuditModelError(f"missing required string field: {key}")
        return default
    value = mapping[key]
    _require_non_empty_string(value, key)
    return value


def _optional_string_from_mapping(mapping: Mapping[str, Any], key: str) -> str | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    _require_non_empty_string(value, key)
    return value


def _positive_int_from_mapping(mapping: Mapping[str, Any], key: str) -> int:
    if key not in mapping:
        raise PublicAuditModelError(f"missing required integer field: {key}")
    value = mapping[key]
    if not isinstance(value, int) or value < 1:
        raise PublicAuditModelError(f"{key} must be a positive integer")
    return value


def _optional_positive_int_from_mapping(mapping: Mapping[str, Any], key: str) -> int | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if not isinstance(value, int) or value < 1:
        raise PublicAuditModelError(f"{key} must be a positive integer")
    return value


def _string_mapping(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise PublicAuditModelError(f"{field} must be a mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        _require_non_empty_string(key, f"{field} key")
        _require_non_empty_string(item, f"{field} value")
        result[key] = item
    return result


def _relative_path_string(value: object, field: str) -> str:
    _require_non_empty_string(value, field)
    if "\\" in value:
        raise PublicAuditModelError(f"{field} must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise PublicAuditModelError(f"{field} must be relative")
    if str(path) in {"", "."}:
        raise PublicAuditModelError(f"{field} must not be empty")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise PublicAuditModelError(f"{field} must not contain empty, current, or parent segments")
    return path.as_posix()


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise PublicAuditModelError(f"{field} must be a non-empty string")
