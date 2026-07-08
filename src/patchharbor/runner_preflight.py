from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Iterable, Mapping

from patchharbor.metadata import MetadataError, MetadataRecord, parse_metadata_lines, validate_patch_metadata
from patchharbor.runner_status import RunnerIssue, RunnerPhaseResult, RunnerResult, RunnerStatusError


METADATA_PREFIXES = frozenset({"patchharbor-meta", "repodossier-meta"})


@dataclass(frozen=True)
class PatchMetadataEntry:
    prefix: str
    payload: Mapping[str, Any]
    line_number: int

    def __post_init__(self) -> None:
        if self.prefix not in METADATA_PREFIXES:
            allowed = ", ".join(sorted(METADATA_PREFIXES))
            raise RunnerStatusError(f"unsupported metadata prefix: {self.prefix}; allowed: {allowed}")
        if not isinstance(self.payload, Mapping):
            raise RunnerStatusError("metadata payload must be a mapping")
        if not isinstance(self.line_number, int) or self.line_number < 1:
            raise RunnerStatusError("metadata line_number must be a positive integer")
        object.__setattr__(self, "payload", dict(self.payload))

    @property
    def type(self) -> str | None:
        value = self.payload.get("type")
        return value if isinstance(value, str) else None

    @property
    def patch_id(self) -> str | None:
        value = self.payload.get("id")
        return value if isinstance(value, str) and value else None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "prefix": self.prefix,
            "payload": dict(self.payload),
            "line_number": self.line_number,
        }


def collect_patch_metadata_entries(text: str) -> tuple[PatchMetadataEntry, ...]:
    records = _parse_metadata_records(text)
    return tuple(PatchMetadataEntry(record.marker, record.data, record.line_number) for record in records)


def patch_entries(entries: Iterable[PatchMetadataEntry]) -> tuple[PatchMetadataEntry, ...]:
    return tuple(entry for entry in entries if entry.type == "patch")


def first_patch_id(entries: Iterable[PatchMetadataEntry]) -> str | None:
    for entry in patch_entries(entries):
        if entry.patch_id:
            return entry.patch_id
    return None


def check_metadata_text(text: str) -> RunnerPhaseResult:
    try:
        records = _parse_metadata_records(text)
    except RunnerStatusError as exc:
        return RunnerPhaseResult(
            "metadata",
            status="failed",
            message="metadata invalid",
            issues=(RunnerIssue(str(exc), phase="metadata", code="metadata.invalid"),),
        )

    if not records:
        return RunnerPhaseResult(
            "metadata",
            status="failed",
            message="metadata missing",
            issues=(RunnerIssue("patch script has no patch metadata comments", phase="metadata", code="metadata.missing"),),
        )

    validation = validate_patch_metadata(records)
    if not validation.ok:
        return RunnerPhaseResult(
            "metadata",
            status="failed",
            message="metadata contract invalid",
            issues=(
                RunnerIssue(
                    "; ".join(validation.errors),
                    phase="metadata",
                    code="metadata.invalid_contract",
                    data={"errors": validation.errors},
                ),
            ),
        )

    patch_record = next(record for record in records if record.type == "patch")
    patch_id = patch_record.data["id"]
    return RunnerPhaseResult(
        "metadata",
        status="passed",
        message=f"metadata ok: {patch_id}",
    )


def check_metadata_file(path: str | Path) -> RunnerPhaseResult:
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return RunnerPhaseResult(
            "metadata",
            status="failed",
            message="unable to read script",
            issues=(RunnerIssue(str(exc), phase="metadata", code="file.read_error"),),
        )
    return check_metadata_text(text)


def check_script_freshness(
    path: str | Path,
    *,
    max_age_seconds: int | float,
    now: int | float | None = None,
) -> RunnerPhaseResult:
    if not _is_number(max_age_seconds) or float(max_age_seconds) < 0:
        raise RunnerStatusError("max_age_seconds must be a non-negative number")
    if now is not None and not _is_number(now):
        raise RunnerStatusError("now must be a number when provided")

    file_path = Path(path)
    try:
        modified = file_path.stat().st_mtime
    except OSError as exc:
        return RunnerPhaseResult(
            "freshness",
            status="failed",
            message="unable to stat script",
            issues=(RunnerIssue(str(exc), phase="freshness", code="file.stat_error"),),
        )

    current = time.time() if now is None else float(now)
    age_seconds = max(0.0, current - modified)

    if age_seconds > float(max_age_seconds):
        return RunnerPhaseResult(
            "freshness",
            status="failed",
            message="script is too old",
            issues=(
                RunnerIssue(
                    f"patch script is older than allowed freshness window: {age_seconds:.0f}s > {float(max_age_seconds):.0f}s",
                    phase="freshness",
                    code="freshness.too_old",
                    data={"age_seconds": age_seconds, "max_age_seconds": float(max_age_seconds)},
                ),
            ),
        )

    return RunnerPhaseResult(
        "freshness",
        status="passed",
        message=f"script fresh: {age_seconds:.0f}s",
        duration_seconds=0.0,
    )


def check_repeat_success(
    patch_id: str | None,
    successful_patch_ids: Iterable[str],
) -> RunnerPhaseResult:
    if isinstance(successful_patch_ids, (str, bytes)):
        raise RunnerStatusError("successful_patch_ids must be an iterable of patch id strings, not a single string")

    successful = tuple(successful_patch_ids)
    if patch_id is None:
        return RunnerPhaseResult(
            "repeat",
            status="skipped",
            message="repeat check skipped without patch id",
        )

    if not isinstance(patch_id, str) or not patch_id:
        raise RunnerStatusError("patch_id must be a non-empty string or None")

    for value in successful:
        if not isinstance(value, str) or not value:
            raise RunnerStatusError("successful_patch_ids must contain non-empty strings")

    if patch_id in successful:
        return RunnerPhaseResult(
            "repeat",
            status="failed",
            message="patch already applied",
            issues=(
                RunnerIssue(
                    f"patch id was already applied successfully: {patch_id}",
                    phase="repeat",
                    code="repeat.already_applied",
                    data={"patch_id": patch_id},
                ),
            ),
        )

    return RunnerPhaseResult("repeat", status="passed", message=f"patch id not repeated: {patch_id}")


def run_preflight_checks(
    path: str | Path,
    *,
    successful_patch_ids: Iterable[str] = (),
    max_age_seconds: int | float | None = None,
    now: int | float | None = None,
) -> RunnerResult:
    file_path = Path(path)
    result = RunnerResult(script_path=str(file_path))

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        metadata = RunnerPhaseResult(
            "metadata",
            status="failed",
            message="unable to read script",
            issues=(RunnerIssue(str(exc), phase="metadata", code="file.read_error"),),
        )
        result = result.with_phase(metadata)
        result = result.with_phase(check_repeat_success(None, successful_patch_ids))
        result = result.with_phase(RunnerPhaseResult("freshness", status="skipped", message="freshness check skipped after read error"))
        return result

    metadata = check_metadata_text(text)
    result = result.with_phase(metadata)

    patch_id: str | None = None
    if metadata.status == "passed":
        try:
            patch_id = first_patch_id(collect_patch_metadata_entries(text))
        except RunnerStatusError:
            patch_id = None

    result = result.with_phase(check_repeat_success(patch_id, successful_patch_ids))

    if max_age_seconds is None:
        result = result.with_phase(RunnerPhaseResult("freshness", status="skipped", message="freshness check disabled"))
    else:
        result = result.with_phase(check_script_freshness(file_path, max_age_seconds=max_age_seconds, now=now))

    return result


def metadata_summary(entries: Iterable[PatchMetadataEntry]) -> tuple[str, ...]:
    lines: list[str] = []
    for entry in entries:
        label = entry.type or "unknown"
        if entry.patch_id:
            label = f"{label}:{entry.patch_id}"
        lines.append(f"line {entry.line_number}: {entry.prefix}: {label}")
    return tuple(lines)


def _parse_metadata_records(text: str) -> tuple[MetadataRecord, ...]:
    if not isinstance(text, str):
        raise RunnerStatusError("patch script text must be a string")
    try:
        return parse_metadata_lines(text, markers=METADATA_PREFIXES)
    except MetadataError as exc:
        raise RunnerStatusError(str(exc)) from exc


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
