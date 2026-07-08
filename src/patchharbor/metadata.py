from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


DEFAULT_MARKER = "patchharbor-meta"
LEGACY_MARKER = "repodossier-meta"


class MetadataError(ValueError):
    pass


@dataclass(frozen=True)
class MetadataRecord:
    type: str
    data: Mapping[str, Any]
    line_number: int
    marker: str

    def require_string(self, field: str) -> str:
        value = self.data.get(field)
        if not isinstance(value, str) or not value:
            raise MetadataError(
                f"{self.type} record line {self.line_number} requires non-empty string field: {field}"
            )
        return value


@dataclass(frozen=True)
class MetadataValidationResult:
    records: tuple[MetadataRecord, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise MetadataError("; ".join(self.errors))


def _metadata_payload_from_line(line: str, *, markers: Iterable[str]) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None

    body = stripped[1:].strip()
    for marker in markers:
        prefix = f"{marker}:"
        if body.startswith(prefix):
            return marker, body[len(prefix):].strip()
    return None


def parse_metadata_lines(
    text: str,
    *,
    markers: Iterable[str] = (DEFAULT_MARKER, LEGACY_MARKER),
) -> tuple[MetadataRecord, ...]:
    records: list[MetadataRecord] = []
    marker_tuple = tuple(markers)

    for line_number, line in enumerate(text.splitlines(), start=1):
        payload = _metadata_payload_from_line(line, markers=marker_tuple)
        if payload is None:
            continue

        marker, raw_json = payload
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise MetadataError(f"metadata line {line_number} contains invalid JSON: {exc.msg}") from exc

        if not isinstance(data, dict):
            raise MetadataError(f"metadata line {line_number} must contain a JSON object")

        record_type = data.get("type")
        if not isinstance(record_type, str) or not record_type:
            raise MetadataError(f"metadata line {line_number} requires non-empty string field: type")

        records.append(
            MetadataRecord(
                type=record_type,
                data=data,
                line_number=line_number,
                marker=marker,
            )
        )

    return tuple(records)


def records_by_type(records: Iterable[MetadataRecord]) -> dict[str, tuple[MetadataRecord, ...]]:
    grouped: dict[str, list[MetadataRecord]] = {}
    for record in records:
        grouped.setdefault(record.type, []).append(record)
    return {key: tuple(value) for key, value in grouped.items()}


def validate_patch_metadata(records: Iterable[MetadataRecord]) -> MetadataValidationResult:
    record_tuple = tuple(records)
    grouped = records_by_type(record_tuple)
    errors: list[str] = []

    patch_records = grouped.get("patch", ())
    if len(patch_records) != 1:
        errors.append("expected exactly one patch metadata record")
    else:
        patch = patch_records[0]
        for field in ("id", "title", "commit"):
            value = patch.data.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"patch metadata requires non-empty string field: {field}")

    progress_records = grouped.get("progress", ())
    panels = {record.data.get("panel") for record in progress_records}
    if "roadmap" not in panels:
        errors.append("missing roadmap progress metadata record")
    if "milestone" not in panels:
        errors.append("missing milestone progress metadata record")

    for record in progress_records:
        for field in ("panel", "status", "file", "label"):
            value = record.data.get(field)
            if not isinstance(value, str) or not value:
                errors.append(
                    f"progress metadata line {record.line_number} requires non-empty string field: {field}"
                )

    display_records = grouped.get("display", ())
    if len(display_records) != 1:
        errors.append("expected exactly one display metadata record")

    return MetadataValidationResult(records=record_tuple, errors=tuple(errors))


def validate_patch_text(
    text: str,
    *,
    markers: Iterable[str] = (DEFAULT_MARKER, LEGACY_MARKER),
) -> MetadataValidationResult:
    return validate_patch_metadata(parse_metadata_lines(text, markers=markers))
