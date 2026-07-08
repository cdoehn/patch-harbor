from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Mapping


DEFAULT_PATCH_SCRIPT_PATTERN = "*.sh"
DEFAULT_DONE_DIRNAME = "done"
DEFAULT_FAILED_DIRNAME = "failed"


class RunnerLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class PatchScriptCandidate:
    path: Path
    modified_time: float
    size_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _path_from(self.path, "candidate path"))
        if not _is_number(self.modified_time):
            raise RunnerLifecycleError("candidate modified_time must be a number")
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise RunnerLifecycleError("candidate size_bytes must be a non-negative integer")
        object.__setattr__(self, "modified_time", float(self.modified_time))

    @classmethod
    def from_path(cls, path: str | Path) -> PatchScriptCandidate:
        file_path = _path_from(path, "candidate path")
        try:
            stat = file_path.stat()
        except OSError as exc:
            raise RunnerLifecycleError(f"unable to stat patch script candidate: {file_path}") from exc
        if not file_path.is_file():
            raise RunnerLifecycleError(f"patch script candidate is not a file: {file_path}")
        return cls(path=file_path, modified_time=stat.st_mtime, size_bytes=stat.st_size)

    @property
    def name(self) -> str:
        return self.path.name

    def age_seconds(self, *, now: int | float | None = None) -> float:
        current = time.time() if now is None else _number_from(now, "now")
        return max(0.0, current - self.modified_time)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "modified_time": self.modified_time,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class RunnerLifecyclePlan:
    script_path: Path
    success_destination: Path
    failure_destination: Path
    log_path: Path | None = None

    def __post_init__(self) -> None:
        script_path = _path_from(self.script_path, "script_path")
        success_destination = _path_from(self.success_destination, "success_destination")
        failure_destination = _path_from(self.failure_destination, "failure_destination")
        log_path = None if self.log_path is None else _path_from(self.log_path, "log_path")

        if success_destination == failure_destination:
            raise RunnerLifecycleError("success_destination and failure_destination must be different")
        if script_path == success_destination or script_path == failure_destination:
            raise RunnerLifecycleError("lifecycle destinations must not be identical to script_path")

        object.__setattr__(self, "script_path", script_path)
        object.__setattr__(self, "success_destination", success_destination)
        object.__setattr__(self, "failure_destination", failure_destination)
        object.__setattr__(self, "log_path", log_path)

    def destination_for_status(self, status: str) -> Path:
        if status == "passed":
            return self.success_destination
        if status == "failed":
            return self.failure_destination
        raise RunnerLifecycleError("lifecycle destination is only defined for passed or failed status")

    def render_summary(self) -> tuple[str, ...]:
        lines = [
            f"script: {self.script_path}",
            f"success_destination: {self.success_destination}",
            f"failure_destination: {self.failure_destination}",
        ]
        if self.log_path is not None:
            lines.append(f"log: {self.log_path}")
        return tuple(lines)

    def to_mapping(self) -> dict[str, str]:
        result = {
            "script_path": str(self.script_path),
            "success_destination": str(self.success_destination),
            "failure_destination": str(self.failure_destination),
        }
        if self.log_path is not None:
            result["log_path"] = str(self.log_path)
        return result


def discover_patch_scripts(
    directory: str | Path,
    *,
    pattern: str = DEFAULT_PATCH_SCRIPT_PATTERN,
    recursive: bool = False,
    include_hidden: bool = False,
) -> tuple[PatchScriptCandidate, ...]:
    directory_path = _existing_directory(directory, "directory")
    if not isinstance(pattern, str) or not pattern:
        raise RunnerLifecycleError("pattern must be a non-empty string")
    if not isinstance(recursive, bool):
        raise RunnerLifecycleError("recursive must be a boolean")
    if not isinstance(include_hidden, bool):
        raise RunnerLifecycleError("include_hidden must be a boolean")

    iterator = directory_path.rglob(pattern) if recursive else directory_path.glob(pattern)
    candidates: list[PatchScriptCandidate] = []
    for path in iterator:
        if not path.is_file():
            continue
        if not include_hidden and _is_hidden(path, root=directory_path):
            continue
        candidates.append(PatchScriptCandidate.from_path(path))

    return tuple(sorted(candidates, key=lambda candidate: (-candidate.modified_time, str(candidate.path))))


def select_latest_patch_script(
    directory: str | Path,
    *,
    pattern: str = DEFAULT_PATCH_SCRIPT_PATTERN,
    recursive: bool = False,
    include_hidden: bool = False,
) -> PatchScriptCandidate | None:
    candidates = discover_patch_scripts(
        directory,
        pattern=pattern,
        recursive=recursive,
        include_hidden=include_hidden,
    )
    return candidates[0] if candidates else None


def plan_patch_script_lifecycle(
    script_path: str | Path,
    *,
    done_directory: str | Path,
    failed_directory: str | Path,
    log_path: str | Path | None = None,
) -> RunnerLifecyclePlan:
    script = _path_from(script_path, "script_path")
    done_dir = _path_from(done_directory, "done_directory")
    failed_dir = _path_from(failed_directory, "failed_directory")
    return RunnerLifecyclePlan(
        script_path=script,
        success_destination=done_dir / script.name,
        failure_destination=failed_dir / script.name,
        log_path=None if log_path is None else _path_from(log_path, "log_path"),
    )


def plan_download_lifecycle(
    downloads_directory: str | Path,
    script_name: str,
    *,
    done_dirname: str = DEFAULT_DONE_DIRNAME,
    failed_dirname: str = DEFAULT_FAILED_DIRNAME,
    log_path: str | Path | None = None,
) -> RunnerLifecyclePlan:
    downloads = _path_from(downloads_directory, "downloads_directory")
    _require_non_empty_string(script_name, "script_name")
    _require_non_empty_string(done_dirname, "done_dirname")
    _require_non_empty_string(failed_dirname, "failed_dirname")
    return plan_patch_script_lifecycle(
        downloads / script_name,
        done_directory=downloads / done_dirname,
        failed_directory=downloads / failed_dirname,
        log_path=log_path,
    )


def lifecycle_directories(
    downloads_directory: str | Path,
    *,
    done_dirname: str = DEFAULT_DONE_DIRNAME,
    failed_dirname: str = DEFAULT_FAILED_DIRNAME,
) -> dict[str, Path]:
    downloads = _path_from(downloads_directory, "downloads_directory")
    _require_non_empty_string(done_dirname, "done_dirname")
    _require_non_empty_string(failed_dirname, "failed_dirname")
    return {
        "downloads": downloads,
        "done": downloads / done_dirname,
        "failed": downloads / failed_dirname,
    }


def destination_exists(plan: RunnerLifecyclePlan) -> dict[str, bool]:
    if not isinstance(plan, RunnerLifecyclePlan):
        raise RunnerLifecycleError("plan must be a RunnerLifecyclePlan")
    return {
        "success_destination": plan.success_destination.exists(),
        "failure_destination": plan.failure_destination.exists(),
        "log_path": False if plan.log_path is None else plan.log_path.exists(),
    }


def _existing_directory(value: str | Path, field: str) -> Path:
    path = _path_from(value, field)
    if not path.exists():
        raise RunnerLifecycleError(f"{field} does not exist: {path}")
    if not path.is_dir():
        raise RunnerLifecycleError(f"{field} is not a directory: {path}")
    return path


def _path_from(value: str | Path, field: str) -> Path:
    if isinstance(value, str) and not value:
        raise RunnerLifecycleError(f"{field} must be a non-empty path")
    try:
        return Path(value).expanduser()
    except TypeError as exc:
        raise RunnerLifecycleError(f"{field} must be a path-like value") from exc


def _is_hidden(path: Path, *, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number_from(value: object, field: str) -> float:
    if not _is_number(value):
        raise RunnerLifecycleError(f"{field} must be a number")
    return float(value)


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise RunnerLifecycleError(f"{field} must be a non-empty string")
