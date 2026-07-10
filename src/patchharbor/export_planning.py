from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from patchharbor.export_model import (
    ExportArtifact,
    ExportJob,
    ExportModelError,
    export_jobs_from_mappings,
)


DEFAULT_EXPORT_PHASE_ORDER = (
    "prepare",
    "execute",
    "collect_artifacts",
    "copy_artifacts",
    "finish",
)


class ExportPlanError(ValueError):
    pass


@dataclass(frozen=True)
class PlannedExportArtifact:
    job_name: str
    artifact: ExportArtifact
    source_path: str
    destination_path: str
    required: bool

    def __post_init__(self) -> None:
        _require_non_empty_string(self.job_name, "planned artifact job_name")
        if not isinstance(self.artifact, ExportArtifact):
            raise ExportPlanError("planned artifact must reference an ExportArtifact")
        object.__setattr__(self, "source_path", _relative_path_string(self.source_path, "planned artifact source_path"))
        object.__setattr__(
            self,
            "destination_path",
            _relative_path_string(self.destination_path, "planned artifact destination_path"),
        )
        if not isinstance(self.required, bool):
            raise ExportPlanError("planned artifact required must be a boolean")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "job_name": self.job_name,
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "required": self.required,
        }


@dataclass(frozen=True)
class ExportPlan:
    jobs: tuple[ExportJob, ...]
    requested_names: tuple[str, ...]
    selected_jobs: tuple[ExportJob, ...]
    artifacts: tuple[PlannedExportArtifact, ...]
    dry_run: bool = False
    output_directory: str | None = None
    phase_order: tuple[str, ...] = DEFAULT_EXPORT_PHASE_ORDER
    environment: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "jobs", _job_tuple(self.jobs, "export plan jobs"))
        object.__setattr__(self, "requested_names", _name_tuple(self.requested_names, "export plan requested_names"))
        object.__setattr__(self, "selected_jobs", _job_tuple(self.selected_jobs, "export plan selected_jobs"))
        object.__setattr__(self, "artifacts", _artifact_tuple(self.artifacts))
        if not isinstance(self.dry_run, bool):
            raise ExportPlanError("export plan dry_run must be a boolean")
        if self.output_directory is not None:
            object.__setattr__(
                self,
                "output_directory",
                _relative_path_string(self.output_directory, "export plan output_directory"),
            )
        object.__setattr__(self, "phase_order", _name_tuple(self.phase_order, "export plan phase_order"))
        object.__setattr__(self, "environment", _string_mapping(self.environment, "export plan environment"))
        _validate_selected_jobs(self.jobs, self.requested_names, self.selected_jobs)

    @property
    def selected_names(self) -> tuple[str, ...]:
        return tuple(job.name for job in self.selected_jobs)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "jobs": [job.to_mapping() for job in self.jobs],
            "requested_names": list(self.requested_names),
            "selected_names": list(self.selected_names),
            "selected_jobs": [job.to_mapping() for job in self.selected_jobs],
            "artifacts": [artifact.to_mapping() for artifact in self.artifacts],
            "dry_run": self.dry_run,
            "phase_order": list(self.phase_order),
        }
        if self.output_directory is not None:
            result["output_directory"] = self.output_directory
        if self.environment:
            result["environment"] = dict(self.environment)
        return result


def create_export_plan(
    jobs: Iterable[ExportJob | Mapping[str, Any]],
    *,
    requested_names: Sequence[str] | None = None,
    dry_run: bool = False,
    output_directory: str | None = None,
    environment: Mapping[str, str] | None = None,
    phase_order: Sequence[str] = DEFAULT_EXPORT_PHASE_ORDER,
) -> ExportPlan:
    normalized_jobs = _normalize_jobs(jobs)
    requested = tuple(job.name for job in normalized_jobs) if requested_names is None else _name_tuple(
        requested_names,
        "requested_names",
    )
    selected_jobs = _select_jobs(normalized_jobs, requested)
    artifacts = _planned_artifacts(selected_jobs)
    return ExportPlan(
        jobs=normalized_jobs,
        requested_names=requested,
        selected_jobs=selected_jobs,
        artifacts=artifacts,
        dry_run=dry_run,
        output_directory=output_directory,
        phase_order=tuple(phase_order),
        environment={} if environment is None else environment,
    )


def create_export_plan_from_mappings(
    mappings: Iterable[Mapping[str, Any]],
    *,
    requested_names: Sequence[str] | None = None,
    dry_run: bool = False,
    output_directory: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> ExportPlan:
    return create_export_plan(
        export_jobs_from_mappings(mappings),
        requested_names=requested_names,
        dry_run=dry_run,
        output_directory=output_directory,
        environment=environment,
    )


def _normalize_jobs(jobs: Iterable[ExportJob | Mapping[str, Any]]) -> tuple[ExportJob, ...]:
    if isinstance(jobs, (str, bytes, bytearray)):
        raise ExportPlanError("export plan jobs must be an iterable of ExportJob or mappings")
    normalized: list[ExportJob] = []
    for job in jobs:
        if isinstance(job, ExportJob):
            normalized.append(job)
        elif isinstance(job, Mapping):
            try:
                normalized.append(ExportJob.from_mapping(job))
            except ExportModelError as exc:
                raise ExportPlanError(str(exc)) from exc
        else:
            raise ExportPlanError("export plan jobs must contain ExportJob or mapping values")
    if not normalized:
        raise ExportPlanError("export plan jobs must not be empty")
    _ensure_unique_job_names(tuple(normalized))
    return tuple(normalized)


def _select_jobs(jobs: tuple[ExportJob, ...], requested_names: tuple[str, ...]) -> tuple[ExportJob, ...]:
    _ensure_unique_names(requested_names, "requested_names")
    by_name = {job.name: job for job in jobs}
    missing = [name for name in requested_names if name not in by_name]
    if missing:
        raise ExportPlanError(f"unknown export job: {missing[0]}")
    return tuple(by_name[name] for name in requested_names)


def _planned_artifacts(jobs: tuple[ExportJob, ...]) -> tuple[PlannedExportArtifact, ...]:
    artifacts: list[PlannedExportArtifact] = []
    for job in jobs:
        for artifact in job.artifacts:
            artifacts.append(
                PlannedExportArtifact(
                    job_name=job.name,
                    artifact=artifact,
                    source_path=artifact.source_path,
                    destination_path=artifact.destination_path or artifact.source_path,
                    required=artifact.required,
                )
            )
    return tuple(artifacts)


def _validate_selected_jobs(
    jobs: tuple[ExportJob, ...],
    requested_names: tuple[str, ...],
    selected_jobs: tuple[ExportJob, ...],
) -> None:
    _ensure_unique_job_names(jobs)
    _ensure_unique_job_names(selected_jobs)
    if tuple(job.name for job in selected_jobs) != requested_names:
        raise ExportPlanError("selected_jobs must match requested_names order")
    by_name = {job.name for job in jobs}
    for job in selected_jobs:
        if job.name not in by_name:
            raise ExportPlanError(f"selected job is not part of jobs: {job.name}")


def _job_tuple(value: object, field: str) -> tuple[ExportJob, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ExportPlanError(f"{field} must be a sequence of ExportJob")
    result: list[ExportJob] = []
    for item in value:
        if not isinstance(item, ExportJob):
            raise ExportPlanError(f"{field} must contain ExportJob values")
        result.append(item)
    if not result:
        raise ExportPlanError(f"{field} must not be empty")
    return tuple(result)


def _artifact_tuple(value: object) -> tuple[PlannedExportArtifact, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ExportPlanError("export plan artifacts must be a sequence of PlannedExportArtifact")
    result: list[PlannedExportArtifact] = []
    for item in value:
        if not isinstance(item, PlannedExportArtifact):
            raise ExportPlanError("export plan artifacts must contain PlannedExportArtifact values")
        result.append(item)
    return tuple(result)


def _ensure_unique_job_names(jobs: Sequence[ExportJob]) -> None:
    _ensure_unique_names(tuple(job.name for job in jobs), "export job names")


def _ensure_unique_names(names: Sequence[str], field: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ExportPlanError(f"duplicate {field}: {name}")
        seen.add(name)


def _name_tuple(value: object, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ExportPlanError(f"{field} must be a sequence of strings")
    result: list[str] = []
    for item in value:
        _require_non_empty_string(item, field)
        result.append(item)
    if not result:
        raise ExportPlanError(f"{field} must not be empty")
    return tuple(result)


def _string_mapping(value: object, field: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ExportPlanError(f"{field} must be a mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        _require_non_empty_string(key, f"{field} key")
        if not isinstance(item, str):
            raise ExportPlanError(f"{field} values must be strings")
        result[key] = item
    return result


def _relative_path_string(value: object, field: str) -> str:
    _require_non_empty_string(value, field)
    if "\\" in value:
        raise ExportPlanError(f"{field} must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ExportPlanError(f"{field} must be relative")
    if str(path) in {"", "."}:
        raise ExportPlanError(f"{field} must not be empty")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ExportPlanError(f"{field} must not contain empty, current, or parent segments")
    return path.as_posix()


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ExportPlanError(f"{field} must be a non-empty string")
