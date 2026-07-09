from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import PurePosixPath
import shlex
from typing import Any, Mapping, Sequence


VALID_WRAPPER_KINDS = frozenset({"runner", "export", "alias", "diagnostic", "audit", "other"})


class CompatibilityConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AliasSpec:
    name: str
    command: tuple[str, ...]
    description: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.name, "alias name")
        command = _string_tuple(self.command, "alias command")
        object.__setattr__(self, "command", command)
        if self.description is not None:
            _require_non_empty_string(self.description, "alias description")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> AliasSpec:
        if not isinstance(mapping, Mapping):
            raise CompatibilityConfigError("alias spec must be a mapping")
        return cls(
            name=_string_from_mapping(mapping, "name"),
            command=_string_tuple_from_mapping(mapping, "command"),
            description=_optional_string_from_mapping(mapping, "description"),
        )

    def render_command(self) -> str:
        return shlex.join(self.command)

    def to_mapping(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "command": list(self.command),
        }
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass(frozen=True)
class WrapperSpec:
    name: str
    kind: str
    relative_path: str
    command: tuple[str, ...]
    enabled: bool = True
    description: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.name, "wrapper name")
        if self.kind not in VALID_WRAPPER_KINDS:
            allowed = ", ".join(sorted(VALID_WRAPPER_KINDS))
            raise CompatibilityConfigError(f"unsupported wrapper kind: {self.kind}; allowed: {allowed}")
        object.__setattr__(self, "relative_path", _relative_path_string(self.relative_path, "wrapper relative_path"))
        object.__setattr__(self, "command", _string_tuple(self.command, "wrapper command"))
        if not isinstance(self.enabled, bool):
            raise CompatibilityConfigError("wrapper enabled must be a boolean")
        if self.description is not None:
            _require_non_empty_string(self.description, "wrapper description")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> WrapperSpec:
        if not isinstance(mapping, Mapping):
            raise CompatibilityConfigError("wrapper spec must be a mapping")
        return cls(
            name=_string_from_mapping(mapping, "name"),
            kind=_string_from_mapping(mapping, "kind"),
            relative_path=_string_from_mapping(mapping, "relative_path"),
            command=_string_tuple_from_mapping(mapping, "command"),
            enabled=_optional_bool_from_mapping(mapping, "enabled", default=True),
            description=_optional_string_from_mapping(mapping, "description"),
        )

    def render_command(self) -> str:
        return shlex.join(self.command)

    def to_mapping(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "kind": self.kind,
            "relative_path": self.relative_path,
            "command": list(self.command),
            "enabled": self.enabled,
        }
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass(frozen=True)
class LifecycleDefaults:
    downloads_dirname: str = "downloads"
    done_dirname: str = "done"
    failed_dirname: str = "failed"

    def __post_init__(self) -> None:
        object.__setattr__(self, "downloads_dirname", _safe_dirname(self.downloads_dirname, "downloads_dirname"))
        object.__setattr__(self, "done_dirname", _safe_dirname(self.done_dirname, "done_dirname"))
        object.__setattr__(self, "failed_dirname", _safe_dirname(self.failed_dirname, "failed_dirname"))
        if self.done_dirname == self.failed_dirname:
            raise CompatibilityConfigError("done_dirname and failed_dirname must be different")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> LifecycleDefaults:
        if not isinstance(mapping, Mapping):
            raise CompatibilityConfigError("lifecycle defaults must be a mapping")
        return cls(
            downloads_dirname=_optional_string_from_mapping(mapping, "downloads_dirname", default="downloads"),
            done_dirname=_optional_string_from_mapping(mapping, "done_dirname", default="done"),
            failed_dirname=_optional_string_from_mapping(mapping, "failed_dirname", default="failed"),
        )

    def to_mapping(self) -> dict[str, str]:
        return {
            "downloads_dirname": self.downloads_dirname,
            "done_dirname": self.done_dirname,
            "failed_dirname": self.failed_dirname,
        }


@dataclass(frozen=True)
class CompatibilityConfig:
    source_name: str
    wrappers: tuple[WrapperSpec, ...] = ()
    aliases: tuple[AliasSpec, ...] = ()
    lifecycle: LifecycleDefaults = field(default_factory=LifecycleDefaults)
    environment: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.source_name, "source_name")
        wrappers = _wrapper_tuple(self.wrappers)
        aliases = _alias_tuple(self.aliases)
        environment = _environment_mapping(self.environment)
        metadata = _plain_metadata_mapping(self.metadata)

        _require_unique((wrapper.name for wrapper in wrappers), "wrapper name")
        _require_unique((wrapper.relative_path for wrapper in wrappers), "wrapper relative_path")
        _require_unique((alias.name for alias in aliases), "alias name")

        if not isinstance(self.lifecycle, LifecycleDefaults):
            raise CompatibilityConfigError("lifecycle must be LifecycleDefaults")

        object.__setattr__(self, "wrappers", wrappers)
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "metadata", metadata)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> CompatibilityConfig:
        if not isinstance(mapping, Mapping):
            raise CompatibilityConfigError("compatibility config must be a mapping")
        return cls(
            source_name=_string_from_mapping(mapping, "source_name"),
            wrappers=tuple(WrapperSpec.from_mapping(item) for item in _sequence_from_mapping(mapping, "wrappers", default=())),
            aliases=tuple(AliasSpec.from_mapping(item) for item in _sequence_from_mapping(mapping, "aliases", default=())),
            lifecycle=LifecycleDefaults.from_mapping(_mapping_from_mapping(mapping, "lifecycle", default={})),
            environment=_string_mapping_from_mapping(mapping, "environment", default={}),
            metadata=_mapping_from_mapping(mapping, "metadata", default={}),
        )

    def enabled_wrappers(self) -> tuple[WrapperSpec, ...]:
        return tuple(wrapper for wrapper in self.wrappers if wrapper.enabled)

    def wrappers_by_kind(self, kind: str) -> tuple[WrapperSpec, ...]:
        if kind not in VALID_WRAPPER_KINDS:
            allowed = ", ".join(sorted(VALID_WRAPPER_KINDS))
            raise CompatibilityConfigError(f"unsupported wrapper kind: {kind}; allowed: {allowed}")
        return tuple(wrapper for wrapper in self.wrappers if wrapper.kind == kind)

    def wrapper_by_name(self, name: str) -> WrapperSpec | None:
        _require_non_empty_string(name, "wrapper name")
        for wrapper in self.wrappers:
            if wrapper.name == name:
                return wrapper
        return None

    def alias_by_name(self, name: str) -> AliasSpec | None:
        _require_non_empty_string(name, "alias name")
        for alias in self.aliases:
            if alias.name == name:
                return alias
        return None

    def to_mapping(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "wrappers": [wrapper.to_mapping() for wrapper in self.wrappers],
            "aliases": [alias.to_mapping() for alias in self.aliases],
            "lifecycle": self.lifecycle.to_mapping(),
            "environment": dict(self.environment),
            "metadata": dict(self.metadata),
        }


def compatibility_config_from_mapping(mapping: Mapping[str, object]) -> CompatibilityConfig:
    return CompatibilityConfig.from_mapping(mapping)


def compatibility_config_from_text(text: str) -> CompatibilityConfig:
    if not isinstance(text, str):
        raise CompatibilityConfigError("compatibility config text must be a string")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CompatibilityConfigError(f"invalid compatibility config JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise CompatibilityConfigError("compatibility config JSON must be an object")
    return CompatibilityConfig.from_mapping(data)


def minimal_compatibility_config(source_name: str) -> CompatibilityConfig:
    return CompatibilityConfig(source_name=source_name)


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise CompatibilityConfigError(f"{field} must be a non-empty string")


def _string_from_mapping(mapping: Mapping[str, object], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise CompatibilityConfigError(f"{field} must be a non-empty string")
    return value


def _optional_string_from_mapping(mapping: Mapping[str, object], field: str, *, default: str | None = None) -> str | None:
    value = mapping.get(field, default)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise CompatibilityConfigError(f"{field} must be a non-empty string when provided")
    return value


def _optional_bool_from_mapping(mapping: Mapping[str, object], field: str, *, default: bool) -> bool:
    value = mapping.get(field, default)
    if not isinstance(value, bool):
        raise CompatibilityConfigError(f"{field} must be a boolean when provided")
    return value


def _sequence_from_mapping(mapping: Mapping[str, object], field: str, *, default: Sequence[object]) -> tuple[object, ...]:
    value = mapping.get(field, default)
    if isinstance(value, (str, bytes)):
        raise CompatibilityConfigError(f"{field} must be a sequence, not a string")
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CompatibilityConfigError(f"{field} must be a sequence") from exc


def _mapping_from_mapping(mapping: Mapping[str, object], field: str, *, default: Mapping[str, object]) -> Mapping[str, object]:
    value = mapping.get(field, default)
    if not isinstance(value, Mapping):
        raise CompatibilityConfigError(f"{field} must be a mapping")
    return value


def _string_mapping_from_mapping(mapping: Mapping[str, object], field: str, *, default: Mapping[str, str]) -> dict[str, str]:
    value = _mapping_from_mapping(mapping, field, default=default)
    return _environment_mapping(value)


def _string_tuple_from_mapping(mapping: Mapping[str, object], field: str) -> tuple[str, ...]:
    if field not in mapping:
        raise CompatibilityConfigError(f"{field} is required")
    return _string_tuple(mapping[field], field)


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise CompatibilityConfigError(f"{field} must be a sequence of strings, not a single string")
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CompatibilityConfigError(f"{field} must be a sequence of strings") from exc
    if not items:
        raise CompatibilityConfigError(f"{field} must not be empty")
    for item in items:
        if not isinstance(item, str) or not item:
            raise CompatibilityConfigError(f"{field} must contain only non-empty strings")
    return items


def _relative_path_string(value: object, field: str) -> str:
    _require_non_empty_string(value, field)
    assert isinstance(value, str)
    path = PurePosixPath(value)
    if path.is_absolute():
        raise CompatibilityConfigError(f"{field} must be repository-relative")
    if any(part in ("", ".", "..") for part in path.parts):
        raise CompatibilityConfigError(f"{field} must not contain empty, current, or parent path parts")
    if ".git" in path.parts:
        raise CompatibilityConfigError(f"{field} must not point inside .git")
    return str(path)


def _safe_dirname(value: object, field: str) -> str:
    _require_non_empty_string(value, field)
    assert isinstance(value, str)
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) != 1 or path.name in (".", "..") or path.name != value:
        raise CompatibilityConfigError(f"{field} must be a simple directory name")
    if value == ".git":
        raise CompatibilityConfigError(f"{field} must not be .git")
    return value


def _wrapper_tuple(value: object) -> tuple[WrapperSpec, ...]:
    if isinstance(value, (str, bytes)):
        raise CompatibilityConfigError("wrappers must be a sequence")
    try:
        wrappers = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CompatibilityConfigError("wrappers must be a sequence") from exc
    for wrapper in wrappers:
        if not isinstance(wrapper, WrapperSpec):
            raise CompatibilityConfigError("wrappers must contain WrapperSpec items")
    return wrappers


def _alias_tuple(value: object) -> tuple[AliasSpec, ...]:
    if isinstance(value, (str, bytes)):
        raise CompatibilityConfigError("aliases must be a sequence")
    try:
        aliases = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CompatibilityConfigError("aliases must be a sequence") from exc
    for alias in aliases:
        if not isinstance(alias, AliasSpec):
            raise CompatibilityConfigError("aliases must contain AliasSpec items")
    return aliases


def _environment_mapping(value: Mapping[str, object]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise CompatibilityConfigError("environment must be a mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise CompatibilityConfigError("environment keys must be non-empty strings")
        if not isinstance(item, str):
            raise CompatibilityConfigError("environment values must be strings")
        result[key] = item
    return result


def _plain_metadata_mapping(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CompatibilityConfigError("metadata must be a mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise CompatibilityConfigError("metadata keys must be non-empty strings")
        result[key] = item
    return result


def _require_unique(values: Sequence[str] | object, field: str) -> None:
    seen: set[str] = set()
    for value in values:  # type: ignore[union-attr]
        if value in seen:
            raise CompatibilityConfigError(f"duplicate {field}: {value}")
        seen.add(value)
