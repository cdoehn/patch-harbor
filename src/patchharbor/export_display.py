from __future__ import annotations

from typing import Iterable, Sequence

from patchharbor.export_model import ExportJob
from patchharbor.export_planning import ExportPlan, PlannedExportArtifact


class ExportDisplayError(ValueError):
    pass


def format_export_command(command: Sequence[str]) -> str:
    if isinstance(command, (str, bytes, bytearray)):
        raise ExportDisplayError("export command must be a sequence of strings")
    parts: list[str] = []
    for part in command:
        if not isinstance(part, str) or not part:
            raise ExportDisplayError("export command parts must be non-empty strings")
        parts.append(_shellish_quote(part))
    if not parts:
        raise ExportDisplayError("export command must not be empty")
    return " ".join(parts)


def render_export_job_table(jobs: Iterable[ExportJob]) -> str:
    normalized = _job_tuple(jobs)
    rows = [["name", "command", "artifacts", "description"]]
    for job in normalized:
        rows.append(
            [
                job.name,
                format_export_command(job.command),
                str(len(job.artifacts)),
                "" if job.description is None else job.description,
            ]
        )
    return _render_table(rows)


def render_export_artifact_table(plan: ExportPlan) -> str:
    _require_plan(plan)
    rows = [["job", "source", "destination", "required"]]
    for artifact in plan.artifacts:
        rows.append(_artifact_row(artifact))
    return _render_table(rows)


def render_export_plan_summary(plan: ExportPlan) -> str:
    _require_plan(plan)
    lines = [
        "Export plan",
        f"requested: {', '.join(plan.requested_names)}",
        f"selected: {', '.join(plan.selected_names)}",
        f"dry_run: {_bool_text(plan.dry_run)}",
        f"phases: {', '.join(plan.phase_order)}",
        f"artifacts: {len(plan.artifacts)}",
    ]
    if plan.output_directory is not None:
        lines.append(f"output_directory: {plan.output_directory}")
    if plan.environment:
        lines.append(f"environment: {len(plan.environment)}")
    return "\n".join(lines)


def render_export_plan(plan: ExportPlan, *, include_jobs: bool = True, include_artifacts: bool = True) -> str:
    _require_plan(plan)
    if not isinstance(include_jobs, bool):
        raise ExportDisplayError("include_jobs must be a boolean")
    if not isinstance(include_artifacts, bool):
        raise ExportDisplayError("include_artifacts must be a boolean")

    sections = [render_export_plan_summary(plan)]
    if include_jobs:
        sections.append("Jobs")
        sections.append(render_export_job_table(plan.selected_jobs))
    if include_artifacts:
        sections.append("Artifacts")
        sections.append(render_export_artifact_table(plan))
    return "\n\n".join(sections)


def _artifact_row(artifact: PlannedExportArtifact) -> list[str]:
    if not isinstance(artifact, PlannedExportArtifact):
        raise ExportDisplayError("export artifact rows require PlannedExportArtifact values")
    return [
        artifact.job_name,
        artifact.source_path,
        artifact.destination_path,
        _bool_text(artifact.required),
    ]


def _job_tuple(jobs: Iterable[ExportJob]) -> tuple[ExportJob, ...]:
    if isinstance(jobs, (str, bytes, bytearray)):
        raise ExportDisplayError("export jobs must be an iterable of ExportJob")
    result = tuple(jobs)
    if not result:
        raise ExportDisplayError("export jobs must not be empty")
    for job in result:
        if not isinstance(job, ExportJob):
            raise ExportDisplayError("export jobs must contain ExportJob values")
    return result


def _require_plan(plan: object) -> None:
    if not isinstance(plan, ExportPlan):
        raise ExportDisplayError("export display helpers require an ExportPlan")


def _bool_text(value: bool) -> str:
    return "yes" if value else "no"


def _shellish_quote(value: str) -> str:
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./:-")
    if value and all(character in safe for character in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _render_table(rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        raise ExportDisplayError("table rows must not be empty")
    normalized: list[list[str]] = []
    width = len(rows[0])
    if width == 0:
        raise ExportDisplayError("table rows must not be empty")
    for row in rows:
        if len(row) != width:
            raise ExportDisplayError("table rows must have equal width")
        normalized.append([str(cell) for cell in row])

    widths = [max(len(row[index]) for row in normalized) for index in range(width)]

    def render_row(row: Sequence[str]) -> str:
        return " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)).rstrip()

    header = render_row(normalized[0])
    separator = " | ".join("-" * widths[index] for index in range(width)).rstrip()
    body = [render_row(row) for row in normalized[1:]]
    return "\n".join([header, separator, *body])
