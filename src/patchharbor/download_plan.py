from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

from patchharbor.download_selection import (
    DEFAULT_DONE_DIRNAME,
    DEFAULT_FAILED_DIRNAME,
    DEFAULT_LEDGER_FILENAME,
    DownloadArtifactSelection,
    DownloadSelectionError,
    select_download_artifact,
)


DEFAULT_PHASE_ORDER = (
    "metadata",
    "repeat",
    "freshness",
    "syntax",
    "preflight",
    "execute",
    "move",
    "ledger",
)
DEFAULT_ZIP_EXTRACT_PREFIX = ".patchharbor-zip."


class DownloadPlanError(ValueError):
    pass


@dataclass(frozen=True)
class DownloadLifecyclePlan:
    selection: DownloadArtifactSelection
    download_directory: Path
    done_directory: Path
    failed_directory: Path
    log_file: Path
    ledger_file: Path
    execution_script_path: Path
    lifecycle_input_path: Path
    success_destination: Path
    failure_destination: Path
    extraction_directory: Path | None = None
    cleanup_paths: tuple[Path, ...] = ()
    phase_order: tuple[str, ...] = DEFAULT_PHASE_ORDER

    def __post_init__(self) -> None:
        if not isinstance(self.selection, DownloadArtifactSelection):
            raise DownloadPlanError("selection must be a DownloadArtifactSelection")
        for field in (
            "download_directory",
            "done_directory",
            "failed_directory",
            "log_file",
            "ledger_file",
            "execution_script_path",
            "lifecycle_input_path",
            "success_destination",
            "failure_destination",
        ):
            object.__setattr__(self, field, _path_from(getattr(self, field), field))
        if self.extraction_directory is not None:
            object.__setattr__(self, "extraction_directory", _path_from(self.extraction_directory, "extraction_directory"))
        object.__setattr__(self, "cleanup_paths", tuple(_path_from(path, "cleanup_path") for path in self.cleanup_paths))
        object.__setattr__(self, "phase_order", tuple(self.phase_order))
        if not self.phase_order:
            raise DownloadPlanError("phase_order must not be empty")

    @property
    def is_archive(self) -> bool:
        return self.selection.candidate.is_archive

    @property
    def is_script(self) -> bool:
        return self.selection.candidate.is_script

    @property
    def artifact_path(self) -> Path:
        return self.selection.artifact_path

    @property
    def artifact_type(self) -> str:
        return self.selection.artifact_type

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "selection": self.selection.to_mapping(),
            "download_directory": str(self.download_directory),
            "done_directory": str(self.done_directory),
            "failed_directory": str(self.failed_directory),
            "log_file": str(self.log_file),
            "ledger_file": str(self.ledger_file),
            "execution_script_path": str(self.execution_script_path),
            "lifecycle_input_path": str(self.lifecycle_input_path),
            "success_destination": str(self.success_destination),
            "failure_destination": str(self.failure_destination),
            "cleanup_paths": [str(path) for path in self.cleanup_paths],
            "phase_order": list(self.phase_order),
        }
        if self.extraction_directory is not None:
            result["extraction_directory"] = str(self.extraction_directory)
        return result


def create_lifecycle_plan(
    *,
    download_directory: str | Path | None = None,
    explicit_path: str | Path | None = None,
    run_timestamp: str | None = None,
) -> DownloadLifecyclePlan:
    selection = select_download_artifact(download_directory=download_directory, explicit_path=explicit_path)
    return create_lifecycle_plan_for_selection(selection, run_timestamp=run_timestamp)


def create_lifecycle_plan_for_selection(
    selection: DownloadArtifactSelection,
    *,
    run_timestamp: str | None = None,
) -> DownloadLifecyclePlan:
    if not isinstance(selection, DownloadArtifactSelection):
        raise DownloadPlanError("selection must be a DownloadArtifactSelection")

    download_directory = _resolve_download_directory(selection)
    timestamp = _validated_timestamp(run_timestamp)
    artifact_path = selection.artifact_path
    done_directory = download_directory / DEFAULT_DONE_DIRNAME
    failed_directory = download_directory / DEFAULT_FAILED_DIRNAME
    log_file = download_directory / f"{artifact_path.stem}_{timestamp}.log"
    ledger_file = done_directory / DEFAULT_LEDGER_FILENAME

    extraction_directory: Path | None = None
    cleanup_paths: tuple[Path, ...] = ()
    execution_script_path = artifact_path
    if selection.candidate.is_archive:
        embedded = selection.candidate.embedded_script_name
        if embedded is None:
            raise DownloadPlanError("archive selection requires embedded_script_name")
        extraction_directory = download_directory / f"{DEFAULT_ZIP_EXTRACT_PREFIX}{artifact_path.stem}"
        execution_script_path = extraction_directory / embedded
        cleanup_paths = (extraction_directory,)

    return DownloadLifecyclePlan(
        selection=selection,
        download_directory=download_directory,
        done_directory=done_directory,
        failed_directory=failed_directory,
        log_file=log_file,
        ledger_file=ledger_file,
        execution_script_path=execution_script_path,
        lifecycle_input_path=artifact_path,
        success_destination=done_directory / artifact_path.name,
        failure_destination=failed_directory / artifact_path.name,
        extraction_directory=extraction_directory,
        cleanup_paths=cleanup_paths,
        phase_order=DEFAULT_PHASE_ORDER,
    )


def _resolve_download_directory(selection: DownloadArtifactSelection) -> Path:
    if selection.download_directory is not None:
        return selection.download_directory
    parent = selection.artifact_path.parent
    if parent == Path(""):
        raise DownloadPlanError("download directory could not be resolved")
    return parent


def _validated_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if not isinstance(value, str) or not value:
        raise DownloadPlanError("run_timestamp must be a non-empty string")
    if not re.fullmatch(r"[0-9]{8}_[0-9]{6}", value):
        raise DownloadPlanError("run_timestamp must use YYYYMMDD_HHMMSS")
    return value


def _path_from(value: str | Path, field: str) -> Path:
    if isinstance(value, str) and not value:
        raise DownloadPlanError(f"{field} must be a non-empty path")
    try:
        return Path(value)
    except TypeError as exc:
        raise DownloadPlanError(f"{field} must be a path-like value") from exc
