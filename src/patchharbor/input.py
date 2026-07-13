"""Script input and orchestration for PatchHarbor."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import stat
from typing import TextIO
import zipfile

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_file
from patchharbor.files import temporary_script_file
from patchharbor.parser import ScriptFormatError, validate_required_marker


MAX_ZIP_ENTRIES = 1_000
MAX_ZIP_ENTRY_BYTES = 256 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 512 * 1024 * 1024
_ZIP_READ_CHUNK_BYTES = 64 * 1024
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


@dataclass(frozen=True)
class ScriptSource:
    """Neutral script input handed to the parsing and execution pipeline."""

    text: str
    suffix: str


def read_script_file(script_path: Path) -> ScriptSource:
    """Read one UTF-8 script file into a neutral source value."""
    try:
        script_text = script_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script source {script_path}: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    return ScriptSource(
        text=script_text,
        suffix=script_path.suffix,
    )


def read_script_stdin(stream: TextIO) -> ScriptSource:
    """Read standard input once into a neutral source value."""
    try:
        script_text = stream.read()
    except (OSError, UnicodeError) as exc:
        raise PatchHarborError(
            f"cannot read script source standard input: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    if not script_text:
        raise PatchHarborError(
            "no script input received",
            ExitCode.USAGE_ERROR,
        )

    return ScriptSource(
        text=script_text,
        suffix=".ps1" if os.name == "nt" else ".sh",
    )


def run_script_source(
    source: ScriptSource,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Validate and run one neutral script source."""
    try:
        validate_required_marker(source.text)
    except ScriptFormatError as exc:
        raise PatchHarborError(
            str(exc),
            ExitCode.NO_VALID_SCRIPT,
        ) from exc

    try:
        with temporary_script_file(source.text, suffix=source.suffix) as temporary_path:
            return execute_script_file(
                temporary_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


@dataclass(frozen=True)
class DirectoryCandidate:
    """Stable display and sorting data for one directory candidate."""

    path: Path
    modified_ns: int

    @property
    def display_name(self) -> str:
        return self.path.name


def _zip_limit_error(path: Path, detail: str) -> PatchHarborError:
    return PatchHarborError(
        f"ZIP archive exceeds resource limit ({detail}): {path}",
        ExitCode.SOURCE_ERROR,
    )


def _validate_zip_budgets(
    path: Path,
    entries: list[zipfile.ZipInfo],
) -> None:
    if len(entries) > MAX_ZIP_ENTRIES:
        raise _zip_limit_error(path, f"more than {MAX_ZIP_ENTRIES} entries")

    total_bytes = 0
    for entry in entries:
        if entry.file_size > MAX_ZIP_ENTRY_BYTES:
            raise _zip_limit_error(
                path,
                f"entry {entry.filename!r} exceeds {MAX_ZIP_ENTRY_BYTES} bytes",
            )
        total_bytes += entry.file_size
        if total_bytes > MAX_ZIP_TOTAL_BYTES:
            raise _zip_limit_error(
                path,
                f"uncompressed data exceeds {MAX_ZIP_TOTAL_BYTES} bytes",
            )


def _is_regular_zip_entry(entry: zipfile.ZipInfo) -> bool:
    if entry.is_dir():
        return False

    if entry.create_system != 3:
        return True

    file_type = stat.S_IFMT(entry.external_attr >> 16)
    return file_type in (0, stat.S_IFREG)


def _read_zip_entry(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
    *,
    path: Path,
    total_bytes_read: int,
) -> tuple[bytes, int]:
    chunks: list[bytes] = []
    entry_bytes_read = 0

    with archive.open(entry, "r") as stream:
        while chunk := stream.read(_ZIP_READ_CHUNK_BYTES):
            entry_bytes_read += len(chunk)
            total_bytes_read += len(chunk)
            if entry_bytes_read > MAX_ZIP_ENTRY_BYTES:
                raise _zip_limit_error(
                    path,
                    f"entry {entry.filename!r} exceeds {MAX_ZIP_ENTRY_BYTES} bytes",
                )
            if total_bytes_read > MAX_ZIP_TOTAL_BYTES:
                raise _zip_limit_error(
                    path,
                    f"uncompressed data exceeds {MAX_ZIP_TOTAL_BYTES} bytes",
                )
            chunks.append(chunk)

    return b"".join(chunks), total_bytes_read


def _iter_zip_script_sources(
    archive: zipfile.ZipFile,
    *,
    path: Path,
) -> Iterator[ScriptSource]:
    entries = archive.infolist()
    _validate_zip_budgets(path, entries)
    total_bytes_read = 0

    for entry in entries:
        if not _is_regular_zip_entry(entry):
            continue

        raw_content, total_bytes_read = _read_zip_entry(
            archive,
            entry,
            path=path,
            total_bytes_read=total_bytes_read,
        )
        if raw_content.startswith(_ZIP_SIGNATURES):
            continue

        try:
            script_text = raw_content.decode("utf-8")
            validate_required_marker(script_text)
        except (UnicodeError, ScriptFormatError):
            continue

        yield ScriptSource(
            text=script_text,
            suffix=PurePosixPath(entry.filename).suffix,
        )


def _zip_contains_valid_script(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return next(_iter_zip_script_sources(archive, path=path), None) is not None
    except (OSError, RuntimeError, zipfile.BadZipFile, PatchHarborError):
        return False


def _is_directory_candidate(path: Path) -> bool:
    try:
        source = read_script_file(path)
        validate_required_marker(source.text)
        return True
    except (PatchHarborError, ScriptFormatError):
        return _zip_contains_valid_script(path)


def discover_directory_candidates(
    directory: Path,
) -> tuple[DirectoryCandidate, ...]:
    """Scan a directory once and return sorted script or ZIP candidates."""
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        raise PatchHarborError(
            f"cannot read script source directory {directory}: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    candidates: list[DirectoryCandidate] = []
    for entry in entries:
        try:
            if entry.is_symlink() or not entry.is_file():
                continue
            if _is_directory_candidate(entry):
                candidates.append(
                    DirectoryCandidate(
                        path=entry,
                        modified_ns=entry.stat().st_mtime_ns,
                    )
                )
        except OSError:
            continue

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.modified_ns,
                candidate.display_name,
            ),
        )
    )


def select_directory_candidate(
    candidates: tuple[DirectoryCandidate, ...],
    *,
    input_stream: TextIO,
    output_stream: TextIO,
) -> DirectoryCandidate:
    """Choose exactly one candidate without performing filesystem discovery."""
    if len(candidates) == 1:
        return candidates[0]

    for index, candidate in enumerate(candidates, start=1):
        print(f"{index} {candidate.display_name}", file=output_stream)

    count = len(candidates)
    while True:
        print(
            f"Select [1-{count}]: ",
            end="",
            file=output_stream,
            flush=True,
        )
        value = input_stream.readline().strip()
        if not value:
            raise PatchHarborError(
                "no script selected",
                ExitCode.USAGE_ERROR,
            )

        if value.isascii() and value.isdecimal():
            index = int(value) - 1
            if 0 <= index < count:
                return candidates[index]

        print(f"Enter 1-{count}.", file=output_stream)


def _no_valid_zip_script(path: Path) -> PatchHarborError:
    return PatchHarborError(
        f"no valid PatchHarbor scripts found in ZIP archive {path}",
        ExitCode.NO_VALID_SCRIPT,
    )


def _looks_like_zip(path: Path) -> bool:
    if path.suffix.lower() == ".zip":
        return True
    try:
        with path.open("rb") as handle:
            return handle.read(4) in _ZIP_SIGNATURES
    except OSError:
        return False


def _invalid_zip_error(path: Path, exc: BaseException) -> PatchHarborError:
    return PatchHarborError(
        f"cannot read ZIP archive {path}: {exc}",
        ExitCode.SOURCE_ERROR,
    )


def _run_zip_file(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    direct_error: PatchHarborError,
) -> int:
    try:
        archive = zipfile.ZipFile(path)
    except OSError:
        raise direct_error
    except zipfile.BadZipFile as exc:
        if isinstance(direct_error.__cause__, ScriptFormatError) and not _looks_like_zip(
            path
        ):
            raise direct_error
        if not _looks_like_zip(path):
            raise PatchHarborError(
                f"file is neither a UTF-8 PatchHarbor script nor a ZIP archive: {path}",
                ExitCode.NO_VALID_SCRIPT,
            ) from exc
        raise _invalid_zip_error(path, exc) from exc

    executed = False
    last_exit_code = 0
    try:
        with archive:
            for source in _iter_zip_script_sources(archive, path=path):
                executed = True
                last_exit_code = run_script_source(
                    source,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                )
                if last_exit_code != 0:
                    return last_exit_code
    except PatchHarborError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise _invalid_zip_error(path, exc) from exc

    if not executed:
        raise _no_valid_zip_script(path)
    return last_exit_code


def _run_script_file_or_zip(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    try:
        source = read_script_file(path)
        return run_script_source(
            source,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
    except PatchHarborError as exc:
        if exc.exit_code not in {
            ExitCode.NO_VALID_SCRIPT,
            ExitCode.SOURCE_ERROR,
        }:
            raise
        return _run_zip_file(
            path,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            direct_error=exc,
        )


def _run_selected_candidate(
    candidate: DirectoryCandidate,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    if candidate.path.is_symlink() or not candidate.path.is_file():
        raise PatchHarborError(
            f"selected script is no longer available: {candidate.display_name}",
            ExitCode.SOURCE_ERROR,
        )

    return _run_script_file_or_zip(
        candidate.path,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )


def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    selection_input: TextIO,
    selection_output: TextIO,
) -> int:
    """Run a script/ZIP file or select one from a directory."""
    if not path.is_dir():
        return _run_script_file_or_zip(
            path,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )

    candidates = discover_directory_candidates(path)
    if not candidates:
        raise PatchHarborError(
            f"no PatchHarbor scripts found in directory {path}",
            ExitCode.NO_VALID_SCRIPT,
        )
    selected = select_directory_candidate(
        candidates,
        input_stream=selection_input,
        output_stream=selection_output,
    )
    return _run_selected_candidate(
        selected,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )
