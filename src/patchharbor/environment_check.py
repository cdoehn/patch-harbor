from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


class EnvironmentCheckError(ValueError):
    """Raised when an environment check model value is invalid."""


_ALLOWED_SPEC_TYPES = frozenset({"command", "file", "git-config", "python-module", "custom"})


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentCheckError(f"environment check {label} must be a non-empty string")
    return value


def _optional_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise EnvironmentCheckError(f"environment check {label} must be a string")
    return value


def _require_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise EnvironmentCheckError(f"environment check {label} must be a boolean")
    return value


def _normalize_metadata(metadata: Mapping[str, object] | None) -> dict[str, str]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise EnvironmentCheckError("environment check metadata must be a mapping")
    normalized: dict[str, str] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not key.strip():
            raise EnvironmentCheckError("environment check metadata keys must be non-empty strings")
        if not isinstance(value, str):
            raise EnvironmentCheckError("environment check metadata values must be strings")
        normalized[key] = value
    return normalized


def _normalize_command(command: Iterable[object] | None) -> tuple[str, ...]:
    if command is None:
        return ()
    if isinstance(command, (str, bytes, bytearray)):
        raise EnvironmentCheckError("environment check command must be an iterable of strings")
    values = tuple(command)
    for value in values:
        if not isinstance(value, str) or not value:
            raise EnvironmentCheckError("environment check command entries must be non-empty strings")
    return values


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    ok: bool
    detail: str
    hint: str = ""
    required: bool = True
    category: str = "general"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_non_empty_string(self.name, "name"))
        object.__setattr__(self, "ok", _require_bool(self.ok, "ok"))
        object.__setattr__(self, "detail", _require_non_empty_string(self.detail, "detail"))
        object.__setattr__(self, "hint", _optional_string(self.hint, "hint"))
        object.__setattr__(self, "required", _require_bool(self.required, "required"))
        object.__setattr__(self, "category", _require_non_empty_string(self.category, "category"))
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))

    @property
    def failed(self) -> bool:
        return not self.ok

    @property
    def blocking(self) -> bool:
        return self.failed and self.required

    @property
    def status(self) -> str:
        if self.ok:
            return "ok"
        if self.required:
            return "fail"
        return "warn"

    def to_mapping(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "hint": self.hint,
            "required": self.required,
            "category": self.category,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "EnvironmentCheck":
        if not isinstance(value, Mapping):
            raise EnvironmentCheckError("environment check must be a mapping")
        return cls(
            name=value.get("name"),
            ok=value.get("ok"),
            detail=value.get("detail"),
            hint=value.get("hint", ""),
            required=value.get("required", True),
            category=value.get("category", "general"),
            metadata=value.get("metadata", {}),
        )


@dataclass(frozen=True)
class EnvironmentCheckSpec:
    name: str
    check_type: str
    required: bool = True
    category: str = "general"
    command: tuple[str, ...] = ()
    path: str = ""
    hint: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_non_empty_string(self.name, "name"))
        object.__setattr__(self, "check_type", _require_non_empty_string(self.check_type, "type"))
        if self.check_type not in _ALLOWED_SPEC_TYPES:
            allowed = ", ".join(sorted(_ALLOWED_SPEC_TYPES))
            raise EnvironmentCheckError(f"environment check type must be one of: {allowed}")
        object.__setattr__(self, "required", _require_bool(self.required, "required"))
        object.__setattr__(self, "category", _require_non_empty_string(self.category, "category"))
        object.__setattr__(self, "command", _normalize_command(self.command))
        object.__setattr__(self, "path", _optional_string(self.path, "path"))
        object.__setattr__(self, "hint", _optional_string(self.hint, "hint"))
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))

        if self.check_type == "command" and not self.command:
            raise EnvironmentCheckError("environment check command spec requires a command")
        if self.check_type == "file" and not self.path:
            raise EnvironmentCheckError("environment check file spec requires a path")

    def to_mapping(self) -> dict[str, object]:
        return {
            "name": self.name,
            "check_type": self.check_type,
            "required": self.required,
            "category": self.category,
            "command": list(self.command),
            "path": self.path,
            "hint": self.hint,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "EnvironmentCheckSpec":
        if not isinstance(value, Mapping):
            raise EnvironmentCheckError("environment check spec must be a mapping")
        return cls(
            name=value.get("name"),
            check_type=value.get("check_type"),
            required=value.get("required", True),
            category=value.get("category", "general"),
            command=_normalize_command(value.get("command", ())),
            path=value.get("path", ""),
            hint=value.get("hint", ""),
            metadata=value.get("metadata", {}),
        )


@dataclass(frozen=True)
class EnvironmentCheckResult:
    checks: tuple[EnvironmentCheck, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.checks, (str, bytes, bytearray)):
            raise EnvironmentCheckError("environment check result checks must be an iterable")
        checks = tuple(_environment_check_from_any(value) for value in self.checks)
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))

    @property
    def total_count(self) -> int:
        return len(self.checks)

    @property
    def ok_count(self) -> int:
        return sum(1 for check in self.checks if check.ok)

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if check.failed)

    @property
    def required_failed_count(self) -> int:
        return sum(1 for check in self.checks if check.blocking)

    @property
    def optional_failed_count(self) -> int:
        return sum(1 for check in self.checks if check.failed and not check.required)

    @property
    def ok(self) -> bool:
        return self.required_failed_count == 0

    @property
    def failed(self) -> bool:
        return not self.ok

    def failed_checks(self) -> tuple[EnvironmentCheck, ...]:
        return tuple(check for check in self.checks if check.failed)

    def blocking_checks(self) -> tuple[EnvironmentCheck, ...]:
        return tuple(check for check in self.checks if check.blocking)

    def checks_by_category(self) -> dict[str, tuple[EnvironmentCheck, ...]]:
        categories: dict[str, list[EnvironmentCheck]] = {}
        for check in self.checks:
            categories.setdefault(check.category, []).append(check)
        return {key: tuple(value) for key, value in categories.items()}

    def summary(self) -> dict[str, int | bool]:
        return {
            "ok": self.ok,
            "total": self.total_count,
            "passed": self.ok_count,
            "failed": self.failed_count,
            "required_failed": self.required_failed_count,
            "optional_failed": self.optional_failed_count,
        }

    def to_mapping(self) -> dict[str, object]:
        return {
            "checks": [check.to_mapping() for check in self.checks],
            "summary": self.summary(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mappings(
        cls,
        checks: Iterable[EnvironmentCheck | Mapping[str, object]],
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> "EnvironmentCheckResult":
        return cls(tuple(_environment_check_from_any(value) for value in checks), metadata=_normalize_metadata(metadata))


def _environment_check_from_any(value: EnvironmentCheck | Mapping[str, object]) -> EnvironmentCheck:
    if isinstance(value, EnvironmentCheck):
        return value
    if isinstance(value, Mapping):
        return EnvironmentCheck.from_mapping(value)
    raise EnvironmentCheckError("environment check result entries must be EnvironmentCheck or mapping")


def environment_check_from_mapping(value: Mapping[str, object]) -> EnvironmentCheck:
    return EnvironmentCheck.from_mapping(value)


def environment_check_spec_from_mapping(value: Mapping[str, object]) -> EnvironmentCheckSpec:
    return EnvironmentCheckSpec.from_mapping(value)


def environment_check_result_from_mappings(
    checks: Iterable[EnvironmentCheck | Mapping[str, object]],
    *,
    metadata: Mapping[str, object] | None = None,
) -> EnvironmentCheckResult:
    return EnvironmentCheckResult.from_mappings(checks, metadata=metadata)
