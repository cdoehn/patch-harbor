from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


class ExportModelError(ValueError):
    pass


@dataclass(frozen=True)
class ExportArtifact:
    source_path: str
    destination_path: str | None = None
    required: bool = False
    description: str | None = None

    def __post_init__(self) -> None:
        source_path = _relative_path_string(self.source_path, "source_path")
        destination_path = source_path if self.destination_path is None else _relative_path_string(
            self.destination_path,
            "destination_path",
        )
        if not isinstance(self.required, bool):
            raise ExportModelError("artifact required must be a boolean")
        if self.description is not None:
            _require_non_empty_string(self.description, "artifact description")
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "destination_path", destination_path)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> ExportArtifact:
        if not isinstance(mapping, Mapping):
            raise ExportModelError("export artifact must be a mapping")
        return cls(
            source_path=_string_from_mapping(mapping, "source_path"),
            destination_path=_optional_string_from_mapping(mapping, "destination_path"),
            required=_bool_from_mapping(mapping, "required", default=False),
            description=_optional_string_from_mapping(mapping, "description"),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "required": self.required,
        }
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass(frozen=True)
class ExportJob:
    name: str
    command: tuple[str, ...]
    artifacts: tuple[ExportArtifact, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)
    description: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.name, "export job name")
        object.__setattr__(self, "command", _string_tuple(self.command, "export job command"))
        artifacts = tuple(_artifact_from(value) for value in self.artifacts)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "environment", _string_mapping(self.environment, "export job environment"))
        if self.description is not None:
            _require_non_empty_string(self.description, "export job description")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> ExportJob:
        if not isinstance(mapping, Mapping):
            raise ExportModelError("export job must be a mapping")
        artifacts_value = mapping.get("artifacts", ())
        if not isinstance(artifacts_value, Sequence) or isinstance(artifacts_value, (str, bytes, bytearray)):
            raise ExportModelError("export job artifacts must be a sequence")
        return cls(
            name=_string_from_mapping(mapping, "name"),
            command=_string_tuple_from_mapping(mapping, "command"),
            artifacts=tuple(ExportArtifact.from_mapping(item) for item in artifacts_value),
            environment=_string_mapping_from_mapping(mapping, "environment"),
            description=_optional_string_from_mapping(mapping, "description"),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "command": list(self.command),
            "artifacts": [artifact.to_mapping() for artifact in self.artifacts],
        }
        if self.environment:
            result["environment"] = dict(self.environment)
        if self.description is not None:
            result["description"] = self.description
        return result


def export_job_from_mapping(mapping: Mapping[str, Any]) -> ExportJob:
    return ExportJob.from_mapping(mapping)


def export_jobs_from_mappings(mappings: Iterable[Mapping[str, Any]]) -> tuple[ExportJob, ...]:
    if isinstance(mappings, (str, bytes, bytearray)):
        raise ExportModelError("export jobs must be an iterable of mappings")
    jobs = tuple(ExportJob.from_mapping(mapping) for mapping in mappings)
    _ensure_unique_names(jobs)
    return jobs


def export_job_index(jobs: Iterable[ExportJob]) -> dict[str, ExportJob]:
    if isinstance(jobs, (str, bytes, bytearray)):
        raise ExportModelError("export jobs must be an iterable of ExportJob")
    normalized = tuple(_job_from(job) for job in jobs)
    _ensure_unique_names(normalized)
    return {job.name: job for job in normalized}


def _ensure_unique_names(jobs: Sequence[ExportJob]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for job in jobs:
        if job.name in seen:
            duplicates.append(job.name)
        seen.add(job.name)
    if duplicates:
        raise ExportModelError(f"duplicate export job name: {duplicates[0]}")


def _artifact_from(value: object) -> ExportArtifact:
    if isinstance(value, ExportArtifact):
        return value
    if isinstance(value, Mapping):
        return ExportArtifact.from_mapping(value)
    raise ExportModelError("export job artifacts must be ExportArtifact or mapping values")


def _job_from(value: object) -> ExportJob:
    if isinstance(value, ExportJob):
        return value
    if isinstance(value, Mapping):
        return ExportJob.from_mapping(value)
    raise ExportModelError("export jobs must be ExportJob or mapping values")


def _string_from_mapping(mapping: Mapping[str, Any], key: str) -> str:
    if key not in mapping:
        raise ExportModelError(f"missing required string field: {key}")
    value = mapping[key]
    _require_non_empty_string(value, key)
    return value


def _optional_string_from_mapping(mapping: Mapping[str, Any], key: str) -> str | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    _require_non_empty_string(value, key)
    return value


def _bool_from_mapping(mapping: Mapping[str, Any], key: str, *, default: bool) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise ExportModelError(f"{key} must be a boolean")
    return value


def _string_tuple_from_mapping(mapping: Mapping[str, Any], key: str) -> tuple[str, ...]:
    if key not in mapping:
        raise ExportModelError(f"missing required sequence field: {key}")
    return _string_tuple(mapping[key], key)


def _string_mapping_from_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, str]:
    if key not in mapping or mapping[key] is None:
        return {}
    return _string_mapping(mapping[key], key)


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ExportModelError(f"{field} must be a sequence of strings")
    result: list[str] = []
    for item in value:
        _require_non_empty_string(item, field)
        result.append(item)
    if not result:
        raise ExportModelError(f"{field} must not be empty")
    return tuple(result)


def _string_mapping(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ExportModelError(f"{field} must be a mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        _require_non_empty_string(key, f"{field} key")
        if not isinstance(item, str):
            raise ExportModelError(f"{field} values must be strings")
        result[key] = item
    return result


def _relative_path_string(value: object, field: str) -> str:
    _require_non_empty_string(value, field)
    if "\\" in value:
        raise ExportModelError(f"{field} must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ExportModelError(f"{field} must be relative")
    if str(path) in {"", "."}:
        raise ExportModelError(f"{field} must not be empty")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ExportModelError(f"{field} must not contain empty, current, or parent segments")
    return path.as_posix()


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ExportModelError(f"{field} must be a non-empty string")
