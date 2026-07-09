from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import zipfile


DEFAULT_SCRIPT_SUFFIX = ".sh"
DEFAULT_ARCHIVE_SUFFIX = ".zip"
DEFAULT_DONE_DIRNAME = "done"
DEFAULT_FAILED_DIRNAME = "failed"
DEFAULT_LEDGER_FILENAME = ".applied_patch_hashes.tsv"


class DownloadSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class DownloadArtifactCandidate:
    path: Path
    modified_time: float
    size_bytes: int
    artifact_type: str
    embedded_script_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _path_from(self.path, "path"))
        if not _is_number(self.modified_time):
            raise DownloadSelectionError("modified_time must be a number")
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise DownloadSelectionError("size_bytes must be a non-negative integer")
        if self.artifact_type not in {"script", "archive"}:
            raise DownloadSelectionError("artifact_type must be script or archive")
        if self.artifact_type == "script" and self.embedded_script_name is not None:
            raise DownloadSelectionError("script candidates must not have embedded_script_name")
        if self.artifact_type == "archive":
            _require_non_empty_string(self.embedded_script_name, "embedded_script_name")
        object.__setattr__(self, "modified_time", float(self.modified_time))

    @classmethod
    def from_path(cls, path: str | Path) -> DownloadArtifactCandidate:
        file_path = _path_from(path, "path")
        try:
            stat = file_path.stat()
        except OSError as exc:
            raise DownloadSelectionError(f"unable to stat download artifact: {file_path}") from exc
        if not file_path.is_file():
            raise DownloadSelectionError(f"download artifact is not a file: {file_path}")
        artifact_type = artifact_type_for_path(file_path)
        embedded_script_name = None
        if artifact_type == "archive":
            embedded_script_name = single_script_in_archive(file_path)
        return cls(
            path=file_path,
            modified_time=stat.st_mtime,
            size_bytes=stat.st_size,
            artifact_type=artifact_type,
            embedded_script_name=embedded_script_name,
        )

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_archive(self) -> bool:
        return self.artifact_type == "archive"

    @property
    def is_script(self) -> bool:
        return self.artifact_type == "script"

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": str(self.path),
            "modified_time": self.modified_time,
            "size_bytes": self.size_bytes,
            "artifact_type": self.artifact_type,
        }
        if self.embedded_script_name is not None:
            result["embedded_script_name"] = self.embedded_script_name
        return result


@dataclass(frozen=True)
class DownloadArtifactSelection:
    candidate: DownloadArtifactCandidate
    download_directory: Path | None = None
    selection_source: str = "latest"

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, DownloadArtifactCandidate):
            raise DownloadSelectionError("candidate must be a DownloadArtifactCandidate")
        directory = None if self.download_directory is None else _path_from(self.download_directory, "download_directory")
        if self.selection_source not in {"latest", "explicit"}:
            raise DownloadSelectionError("selection_source must be latest or explicit")
        object.__setattr__(self, "download_directory", directory)

    @property
    def artifact_path(self) -> Path:
        return self.candidate.path

    @property
    def artifact_type(self) -> str:
        return self.candidate.artifact_type

    def to_mapping(self) -> dict[str, Any]:
        result = {
            "candidate": self.candidate.to_mapping(),
            "selection_source": self.selection_source,
        }
        if self.download_directory is not None:
            result["download_directory"] = str(self.download_directory)
        return result


def artifact_type_for_path(path: str | Path) -> str:
    file_path = _path_from(path, "path")
    suffix = file_path.suffix.lower()
    if suffix == DEFAULT_SCRIPT_SUFFIX:
        return "script"
    if suffix == DEFAULT_ARCHIVE_SUFFIX:
        return "archive"
    raise DownloadSelectionError(f"unsupported download artifact suffix: {file_path.name}")


def single_script_in_archive(path: str | Path) -> str:
    archive_path = _path_from(path, "path")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            script_names = tuple(
                info.filename
                for info in archive.infolist()
                if not info.is_dir() and _is_visible_script_member(info.filename)
            )
    except zipfile.BadZipFile as exc:
        raise DownloadSelectionError(f"invalid zip archive: {archive_path}") from exc
    except OSError as exc:
        raise DownloadSelectionError(f"unable to read zip archive: {archive_path}") from exc

    if len(script_names) != 1:
        raise DownloadSelectionError(
            f"zip archive must contain exactly one visible .sh script, found {len(script_names)}: {archive_path.name}"
        )
    return script_names[0]


def discover_download_artifacts(
    download_directory: str | Path,
    *,
    include_hidden: bool = False,
) -> tuple[DownloadArtifactCandidate, ...]:
    directory = _existing_directory(download_directory, "download_directory")
    if not isinstance(include_hidden, bool):
        raise DownloadSelectionError("include_hidden must be a boolean")

    candidates: list[DownloadArtifactCandidate] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if _is_ignored_download_entry(path, root=directory, include_hidden=include_hidden):
            continue
        try:
            candidates.append(DownloadArtifactCandidate.from_path(path))
        except DownloadSelectionError:
            if path.suffix.lower() in {DEFAULT_SCRIPT_SUFFIX, DEFAULT_ARCHIVE_SUFFIX}:
                raise
            continue

    return tuple(sorted(candidates, key=lambda candidate: (-candidate.modified_time, str(candidate.path))))


def select_latest_download_artifact(download_directory: str | Path) -> DownloadArtifactSelection | None:
    directory = _existing_directory(download_directory, "download_directory")
    candidates = discover_download_artifacts(directory)
    if not candidates:
        return None
    return DownloadArtifactSelection(candidates[0], download_directory=directory, selection_source="latest")


def select_download_artifact(
    *,
    download_directory: str | Path | None = None,
    explicit_path: str | Path | None = None,
) -> DownloadArtifactSelection:
    if explicit_path is not None:
        if download_directory is not None:
            directory = _path_from(download_directory, "download_directory")
        else:
            directory = None
        return DownloadArtifactSelection(
            DownloadArtifactCandidate.from_path(explicit_path),
            download_directory=directory,
            selection_source="explicit",
        )

    if download_directory is None:
        raise DownloadSelectionError("download_directory is required when explicit_path is not provided")

    selection = select_latest_download_artifact(download_directory)
    if selection is None:
        raise DownloadSelectionError(f"no download patch artifact found in: {_path_from(download_directory, 'download_directory')}")
    return selection


def _existing_directory(value: str | Path, field: str) -> Path:
    path = _path_from(value, field)
    if not path.exists():
        raise DownloadSelectionError(f"{field} does not exist: {path}")
    if not path.is_dir():
        raise DownloadSelectionError(f"{field} is not a directory: {path}")
    return path


def _path_from(value: str | Path, field: str) -> Path:
    if isinstance(value, str) and not value:
        raise DownloadSelectionError(f"{field} must be a non-empty path")
    try:
        return Path(value).expanduser()
    except TypeError as exc:
        raise DownloadSelectionError(f"{field} must be a path-like value") from exc


def _is_ignored_download_entry(path: Path, *, root: Path, include_hidden: bool) -> bool:
    if path.name in {DEFAULT_LEDGER_FILENAME}:
        return True
    if path.suffix.lower() == ".log":
        return True
    if path.name in {DEFAULT_DONE_DIRNAME, DEFAULT_FAILED_DIRNAME}:
        return True
    if not include_hidden and _is_hidden(path, root=root):
        return True
    return False


def _is_visible_script_member(name: str) -> bool:
    path = Path(name)
    return path.suffix.lower() == DEFAULT_SCRIPT_SUFFIX and not any(part.startswith(".") for part in path.parts)


def _is_hidden(path: Path, *, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_non_empty_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise DownloadSelectionError(f"{field} must be a non-empty string")
