from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable, Mapping

from patchharbor.compat_config import AliasSpec, CompatibilityConfig, CompatibilityConfigError, LifecycleDefaults, WrapperSpec


VALID_PLAN_ACTIONS = frozenset({
    "create_wrapper",
    "update_wrapper",
    "skip_wrapper",
    "create_alias",
    "update_alias",
    "ensure_lifecycle",
})


class CompatibilityPlanningError(ValueError):
    pass


@dataclass(frozen=True)
class CompatibilityPlanAction:
    action: str
    target: str
    reason: str
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action not in VALID_PLAN_ACTIONS:
            allowed = ", ".join(sorted(VALID_PLAN_ACTIONS))
            raise CompatibilityPlanningError(f"unsupported plan action: {self.action}; allowed: {allowed}")
        _require_non_empty_string(self.target, "plan target")
        _require_non_empty_string(self.reason, "plan reason")
        object.__setattr__(self, "payload", _plain_payload_mapping(self.payload))

    def render(self) -> str:
        return f"{self.action}: {self.target} - {self.reason}"

    def to_mapping(self) -> dict[str, object]:
        return {
            "action": self.action,
            "target": self.target,
            "reason": self.reason,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class CompatibilityPlan:
    source_name: str
    actions: tuple[CompatibilityPlanAction, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_string(self.source_name, "source_name")
        actions = _action_tuple(self.actions)
        object.__setattr__(self, "actions", actions)

    @property
    def has_actions(self) -> bool:
        return bool(self.actions)

    def actions_by_type(self, action: str) -> tuple[CompatibilityPlanAction, ...]:
        if action not in VALID_PLAN_ACTIONS:
            allowed = ", ".join(sorted(VALID_PLAN_ACTIONS))
            raise CompatibilityPlanningError(f"unsupported plan action: {action}; allowed: {allowed}")
        return tuple(item for item in self.actions if item.action == action)

    def actions_for_target(self, target: str) -> tuple[CompatibilityPlanAction, ...]:
        _require_non_empty_string(target, "plan target")
        return tuple(item for item in self.actions if item.target == target)

    def render_lines(self) -> tuple[str, ...]:
        if not self.actions:
            return (f"compatibility plan for {self.source_name}: no actions",)
        return (f"compatibility plan for {self.source_name}:", *(f"- {action.render()}" for action in self.actions))

    def to_mapping(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "actions": [action.to_mapping() for action in self.actions],
        }


def plan_compatibility(
    config: CompatibilityConfig,
    *,
    existing_wrapper_paths: Iterable[str] = (),
    existing_aliases: Iterable[str] = (),
    include_disabled: bool = True,
) -> CompatibilityPlan:
    compatibility = _require_config(config)
    actions: list[CompatibilityPlanAction] = []
    actions.extend(plan_lifecycle_actions(compatibility))
    actions.extend(plan_wrapper_actions(compatibility, existing_wrapper_paths=existing_wrapper_paths, include_disabled=include_disabled))
    actions.extend(plan_alias_actions(compatibility, existing_aliases=existing_aliases))
    return CompatibilityPlan(source_name=compatibility.source_name, actions=tuple(actions))


def plan_lifecycle_actions(config: CompatibilityConfig) -> tuple[CompatibilityPlanAction, ...]:
    compatibility = _require_config(config)
    lifecycle = compatibility.lifecycle
    return (
        CompatibilityPlanAction(
            "ensure_lifecycle",
            lifecycle.downloads_dirname,
            "plan lifecycle directory names without creating them",
            payload=lifecycle.to_mapping(),
        ),
    )


def plan_wrapper_actions(
    config: CompatibilityConfig,
    *,
    existing_wrapper_paths: Iterable[str] = (),
    include_disabled: bool = True,
) -> tuple[CompatibilityPlanAction, ...]:
    compatibility = _require_config(config)
    existing = _relative_path_set(existing_wrapper_paths, "existing_wrapper_paths")
    if not isinstance(include_disabled, bool):
        raise CompatibilityPlanningError("include_disabled must be a boolean")

    actions: list[CompatibilityPlanAction] = []
    for wrapper in compatibility.wrappers:
        if not wrapper.enabled:
            if include_disabled:
                actions.append(_wrapper_action("skip_wrapper", wrapper, "wrapper is disabled"))
            continue
        if wrapper.relative_path in existing:
            actions.append(_wrapper_action("update_wrapper", wrapper, "wrapper path already exists"))
        else:
            actions.append(_wrapper_action("create_wrapper", wrapper, "wrapper path is missing"))
    return tuple(actions)


def plan_alias_actions(
    config: CompatibilityConfig,
    *,
    existing_aliases: Iterable[str] = (),
) -> tuple[CompatibilityPlanAction, ...]:
    compatibility = _require_config(config)
    existing = _string_set(existing_aliases, "existing_aliases")
    actions: list[CompatibilityPlanAction] = []
    for alias in compatibility.aliases:
        if alias.name in existing:
            actions.append(_alias_action("update_alias", alias, "alias already exists"))
        else:
            actions.append(_alias_action("create_alias", alias, "alias is missing"))
    return tuple(actions)


def empty_plan(source_name: str) -> CompatibilityPlan:
    return CompatibilityPlan(source_name=source_name)


def _wrapper_action(action: str, wrapper: WrapperSpec, reason: str) -> CompatibilityPlanAction:
    return CompatibilityPlanAction(action, wrapper.relative_path, reason, payload=wrapper.to_mapping())


def _alias_action(action: str, alias: AliasSpec, reason: str) -> CompatibilityPlanAction:
    return CompatibilityPlanAction(action, alias.name, reason, payload=alias.to_mapping())


def _require_config(config: CompatibilityConfig) -> CompatibilityConfig:
    if not isinstance(config, CompatibilityConfig):
        raise CompatibilityPlanningError("config must be a CompatibilityConfig")
    return config


def _action_tuple(value: object) -> tuple[CompatibilityPlanAction, ...]:
    if isinstance(value, (str, bytes)):
        raise CompatibilityPlanningError("actions must be a sequence")
    try:
        actions = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise CompatibilityPlanningError("actions must be a sequence") from exc
    for action in actions:
        if not isinstance(action, CompatibilityPlanAction):
            raise CompatibilityPlanningError("actions must contain CompatibilityPlanAction items")
    return actions


def _plain_payload_mapping(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CompatibilityPlanningError("plan payload must be a mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise CompatibilityPlanningError("plan payload keys must be non-empty strings")
        result[key] = item
    return result


def _relative_path_set(values: Iterable[str], field: str) -> set[str]:
    result: set[str] = set()
    for value in _iter_strings(values, field):
        result.add(_relative_path_string(value, field))
    return result


def _string_set(values: Iterable[str], field: str) -> set[str]:
    return set(_iter_strings(values, field))


def _iter_strings(values: Iterable[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise CompatibilityPlanningError(f"{field} must be an iterable of strings, not a single string")
    try:
        items = tuple(values)
    except TypeError as exc:
        raise CompatibilityPlanningError(f"{field} must be an iterable of strings") from exc
    for item in items:
        _require_non_empty_string(item, field)
    return items


def _relative_path_string(value: object, field: str) -> str:
    _require_non_empty_string(value, field)
    assert isinstance(value, str)
    path = PurePosixPath(value)
    if path.is_absolute():
        raise CompatibilityPlanningError(f"{field} entries must be repository-relative")
    if any(part in ("", ".", "..") for part in path.parts):
        raise CompatibilityPlanningError(f"{field} entries must not contain empty, current, or parent path parts")
    if ".git" in path.parts:
        raise CompatibilityPlanningError(f"{field} entries must not point inside .git")
    return str(path)


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise CompatibilityPlanningError(f"{field} must be a non-empty string")
