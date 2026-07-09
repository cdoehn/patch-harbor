from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from patchharbor.metadata import MetadataError, MetadataRecord, parse_metadata_lines
from patchharbor.runner_status import RunnerIssue, RunnerPhaseResult, RunnerResult, derive_runner_status


VALID_LAYOUTS = frozenset({"stacked", "side-by-side"})
VALID_FOOTER_KINDS = frozenset({"done", "current", "next", "problem", "info"})
VALID_PROGRESS_PANELS = frozenset({"roadmap", "milestone", "context", "status"})
ANSI_COLORS = {
    "done": "\033[32m",
    "current": "\033[35m",
    "next": "\033[33m",
    "problem": "\033[31m",
    "info": "\033[36m",
}
ANSI_RESET = "\033[0m"


class RunnerDisplayError(ValueError):
    pass


@dataclass(frozen=True)
class RunnerDisplayOptions:
    context: int = 0
    layout: str = "stacked"
    frame: bool = False
    color: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.context, int) or isinstance(self.context, bool) or self.context < 0:
            raise RunnerDisplayError("display context must be a non-negative integer")
        if self.layout not in VALID_LAYOUTS:
            allowed = ", ".join(sorted(VALID_LAYOUTS))
            raise RunnerDisplayError(f"unsupported display layout: {self.layout}; allowed: {allowed}")
        if not isinstance(self.frame, bool):
            raise RunnerDisplayError("display frame must be a boolean")
        if not isinstance(self.color, bool):
            raise RunnerDisplayError("display color must be a boolean")


@dataclass(frozen=True)
class ProgressDisplayItem:
    panel: str
    status: str
    label: str
    file: str | None = None
    start: int | None = None
    end: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.panel, "progress panel")
        _require_non_empty_string(self.status, "progress status")
        _require_non_empty_string(self.label, "progress label")
        if self.panel not in VALID_PROGRESS_PANELS:
            allowed = ", ".join(sorted(VALID_PROGRESS_PANELS))
            raise RunnerDisplayError(f"unsupported progress panel: {self.panel}; allowed: {allowed}")
        if self.file is not None:
            _require_non_empty_string(self.file, "progress file")
        if self.start is not None and (not isinstance(self.start, int) or isinstance(self.start, bool) or self.start < 1):
            raise RunnerDisplayError("progress start must be a positive integer when provided")
        if self.end is not None and (not isinstance(self.end, int) or isinstance(self.end, bool) or self.end < 1):
            raise RunnerDisplayError("progress end must be a positive integer when provided")
        if self.start is not None and self.end is not None and self.end < self.start:
            raise RunnerDisplayError("progress end must not be before start")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> ProgressDisplayItem:
        if not isinstance(mapping, Mapping):
            raise RunnerDisplayError("progress item must be a mapping")
        return cls(
            panel=_string_from_mapping(mapping, "panel"),
            status=_string_from_mapping(mapping, "status"),
            label=_string_from_mapping(mapping, "label"),
            file=_optional_string_from_mapping(mapping, "file"),
            start=_optional_int_from_mapping(mapping, "start"),
            end=_optional_int_from_mapping(mapping, "end"),
        )

    def location_label(self) -> str | None:
        if self.file is None:
            return None
        if self.start is None:
            return self.file
        if self.end is None or self.end == self.start:
            return f"{self.file}:{self.start}"
        return f"{self.file}:{self.start}-{self.end}"

    def render(self) -> str:
        location = self.location_label()
        prefix = f"{self.panel}: {self.status}: {self.label}"
        return prefix if location is None else f"{prefix} ({location})"

    def to_mapping(self) -> dict[str, object]:
        result: dict[str, object] = {
            "panel": self.panel,
            "status": self.status,
            "label": self.label,
        }
        if self.file is not None:
            result["file"] = self.file
        if self.start is not None:
            result["start"] = self.start
        if self.end is not None:
            result["end"] = self.end
        return result


@dataclass(frozen=True)
class FooterLine:
    kind: str
    label: str
    text: str

    def __post_init__(self) -> None:
        if self.kind not in VALID_FOOTER_KINDS:
            allowed = ", ".join(sorted(VALID_FOOTER_KINDS))
            raise RunnerDisplayError(f"unsupported footer kind: {self.kind}; allowed: {allowed}")
        _require_non_empty_string(self.label, "footer label")
        _require_non_empty_string(self.text, "footer text")

    def render(self, *, color: bool = False) -> str:
        label = f"{self.label}:"
        if color:
            label = _colorize(label, self.kind)
        return f"{label} {self.text}"

    def to_mapping(self) -> dict[str, str]:
        return {"kind": self.kind, "label": self.label, "text": self.text}


def display_options_from_metadata(records: Iterable[MetadataRecord]) -> RunnerDisplayOptions:
    display_records = [record for record in records if record.type == "display"]
    if not display_records:
        return RunnerDisplayOptions()
    data = display_records[0].data
    context = data.get("context", 0)
    layout = data.get("layout", "stacked")
    frame = data.get("frame", False)
    if not isinstance(context, int) or isinstance(context, bool):
        raise RunnerDisplayError("display metadata context must be an integer")
    if not isinstance(layout, str):
        raise RunnerDisplayError("display metadata layout must be a string")
    if not isinstance(frame, bool):
        raise RunnerDisplayError("display metadata frame must be a boolean")
    return RunnerDisplayOptions(context=context, layout=layout, frame=frame)


def display_options_from_text(text: str) -> RunnerDisplayOptions:
    return display_options_from_metadata(_parse_metadata_text(text))


def progress_items_from_metadata(records: Iterable[MetadataRecord]) -> tuple[ProgressDisplayItem, ...]:
    return tuple(ProgressDisplayItem.from_mapping(record.data) for record in records if record.type == "progress")


def progress_items_from_text(text: str) -> tuple[ProgressDisplayItem, ...]:
    return progress_items_from_metadata(_parse_metadata_text(text))


def render_progress_context(
    items: Iterable[ProgressDisplayItem],
    *,
    options: RunnerDisplayOptions | None = None,
) -> tuple[str, ...]:
    effective_options = options or RunnerDisplayOptions()
    item_tuple = tuple(items)
    if not item_tuple:
        return ("progress: none",)

    if effective_options.layout == "side-by-side":
        return _render_side_by_side_progress(item_tuple, frame=effective_options.frame)
    return _render_stacked_progress(item_tuple, frame=effective_options.frame)


def footer_lines(
    *,
    done: Iterable[str] = (),
    current: str | None = None,
    next_step: str | None = None,
    problem: str | None = None,
    info: Iterable[str] = (),
) -> tuple[FooterLine, ...]:
    lines: list[FooterLine] = []
    for text in done:
        _require_non_empty_string(text, "done footer text")
        lines.append(FooterLine("done", "Done", text))
    if current is not None:
        lines.append(FooterLine("current", "Current", current))
    if next_step is not None:
        lines.append(FooterLine("next", "Next", next_step))
    for text in info:
        _require_non_empty_string(text, "info footer text")
        lines.append(FooterLine("info", "Info", text))
    if problem is not None:
        lines.append(FooterLine("problem", "Problem", problem))
    return tuple(lines)


def render_footer(
    *,
    done: Iterable[str] = (),
    current: str | None = None,
    next_step: str | None = None,
    problem: str | None = None,
    info: Iterable[str] = (),
    options: RunnerDisplayOptions | None = None,
) -> tuple[str, ...]:
    effective_options = options or RunnerDisplayOptions()
    body = tuple(line.render(color=effective_options.color) for line in footer_lines(done=done, current=current, next_step=next_step, problem=problem, info=info))
    if not effective_options.frame:
        return body
    return _with_frame(body)


def render_runner_result(result: RunnerResult, *, include_phase_details: bool = True) -> tuple[str, ...]:
    if not isinstance(result, RunnerResult):
        raise RunnerDisplayError("result must be a RunnerResult")
    status = _display_status(result)
    lines = [f"runner status: {status}"]
    if result.script_path:
        lines.append(f"script: {result.script_path}")
    if result.log_path:
        lines.append(f"log: {result.log_path}")
    if result.exit_code is not None:
        lines.append(f"exit code: {result.exit_code}")

    if include_phase_details:
        for phase in result.phases:
            lines.extend(render_runner_phase(phase))

    for issue in result.issues:
        lines.append(render_runner_issue(issue))
    return tuple(lines)


def render_runner_phase(phase: RunnerPhaseResult) -> tuple[str, ...]:
    if not isinstance(phase, RunnerPhaseResult):
        raise RunnerDisplayError("phase must be a RunnerPhaseResult")
    label = f"phase {phase.phase}: {phase.status}"
    if phase.message:
        label = f"{label} - {phase.message}"
    lines = [label]
    for issue in phase.issues:
        lines.append(f"  {render_runner_issue(issue)}")
    return tuple(lines)


def render_runner_issue(issue: RunnerIssue) -> str:
    if not isinstance(issue, RunnerIssue):
        raise RunnerDisplayError("issue must be a RunnerIssue")
    parts = [issue.severity]
    if issue.phase:
        parts.append(issue.phase)
    if issue.code:
        parts.append(issue.code)
    return f"{'/'.join(parts)}: {issue.message}"


def render_runner_footer(
    result: RunnerResult,
    *,
    done: Iterable[str] = (),
    next_step: str | None = None,
    options: RunnerDisplayOptions | None = None,
) -> tuple[str, ...]:
    if not isinstance(result, RunnerResult):
        raise RunnerDisplayError("result must be a RunnerResult")
    status = _display_status(result)
    current = f"runner status {status}"
    problem = None
    if status == "failed":
        errors = result.errors
        problem = errors[0].message if errors else "runner failed"
    return render_footer(done=done, current=current, next_step=next_step, problem=problem, options=options)


def _display_status(result: RunnerResult) -> str:
    derived = derive_runner_status(result.phases, result.issues)
    if derived != "pending":
        return derived
    return result.status


def _parse_metadata_text(text: str) -> tuple[MetadataRecord, ...]:
    if not isinstance(text, str):
        raise RunnerDisplayError("metadata text must be a string")
    try:
        return parse_metadata_lines(text)
    except MetadataError as exc:
        raise RunnerDisplayError(str(exc)) from exc


def _render_stacked_progress(items: Sequence[ProgressDisplayItem], *, frame: bool) -> tuple[str, ...]:
    lines = tuple(item.render() for item in items)
    return _with_frame(lines) if frame else lines


def _render_side_by_side_progress(items: Sequence[ProgressDisplayItem], *, frame: bool) -> tuple[str, ...]:
    by_panel: dict[str, list[ProgressDisplayItem]] = {}
    for item in items:
        by_panel.setdefault(item.panel, []).append(item)

    ordered_panels = sorted(by_panel)
    rendered_columns = [[item.render() for item in by_panel[panel]] for panel in ordered_panels]
    widths = [max(len(line) for line in column) for column in rendered_columns]
    max_rows = max(len(column) for column in rendered_columns)

    rows: list[str] = []
    header = " | ".join(panel.ljust(widths[index]) for index, panel in enumerate(ordered_panels))
    rows.append(header)
    rows.append("-+-".join("-" * width for width in widths))
    for row_index in range(max_rows):
        cells: list[str] = []
        for column_index, column in enumerate(rendered_columns):
            cell = column[row_index] if row_index < len(column) else ""
            cells.append(cell.ljust(widths[column_index]))
        rows.append(" | ".join(cells))

    result = tuple(rows)
    return _with_frame(result) if frame else result


def _with_frame(lines: Iterable[str]) -> tuple[str, ...]:
    body = tuple(lines)
    width = max((len(line) for line in body), default=0)
    border = "=" * max(width, 12)
    return (border, *body, border)


def _colorize(text: str, kind: str) -> str:
    color = ANSI_COLORS.get(kind)
    if not color:
        return text
    return f"{color}{text}{ANSI_RESET}"


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise RunnerDisplayError(f"{field} must be a non-empty string")


def _string_from_mapping(mapping: Mapping[str, object], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise RunnerDisplayError(f"progress metadata field {field} must be a non-empty string")
    return value


def _optional_string_from_mapping(mapping: Mapping[str, object], field: str) -> str | None:
    value = mapping.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RunnerDisplayError(f"progress metadata field {field} must be a non-empty string when provided")
    return value


def _optional_int_from_mapping(mapping: Mapping[str, object], field: str) -> int | None:
    value = mapping.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise RunnerDisplayError(f"progress metadata field {field} must be an integer when provided")
    return value
