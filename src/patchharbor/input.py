"""Script input and orchestration for PatchHarbor."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
from typing import TextIO
import zipfile

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_file
from patchharbor.files import temporary_script_file
from patchharbor.parser import ScriptFormatError, validate_required_marker


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


def discover_directory_candidates(
    directory: Path,
) -> tuple[DirectoryCandidate, ...]:
    """Scan a directory once and return sorted direct-script candidates."""
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
            source = read_script_file(entry)
            validate_required_marker(source.text)
            candidates.append(
                DirectoryCandidate(
                    path=entry,
                    modified_ns=entry.stat().st_mtime_ns,
                )
            )
        except (PatchHarborError, ScriptFormatError, OSError):
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


def _read_selected_candidate(candidate: DirectoryCandidate) -> ScriptSource:
    try:
        return read_script_file(candidate.path)
    except PatchHarborError as exc:
        raise PatchHarborError(
            f"selected script is no longer available: {candidate.display_name}",
            ExitCode.SOURCE_ERROR,
        ) from exc



def _no_valid_zip_script(path: Path) -> PatchHarborError:
    return PatchHarborError(
        f"no valid PatchHarbor scripts found in ZIP archive {path}",
        ExitCode.NO_VALID_SCRIPT,
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
        if isinstance(direct_error.__cause__, ScriptFormatError):
            raise direct_error
        raise PatchHarborError(
            f"file is neither a UTF-8 PatchHarbor script nor a ZIP archive: {path}",
            ExitCode.NO_VALID_SCRIPT,
        ) from exc

    executed = False
    last_exit_code = 0
    try:
        with archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                try:
                    script_text = archive.read(entry).decode("utf-8")
                    validate_required_marker(script_text)
                except (OSError, RuntimeError, UnicodeError, ScriptFormatError):
                    continue

                executed = True
                last_exit_code = run_script_source(
                    ScriptSource(
                        text=script_text,
                        suffix=PurePosixPath(entry.filename).suffix,
                    ),
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                )
                if last_exit_code != 0:
                    return last_exit_code
    except zipfile.BadZipFile as exc:
        raise PatchHarborError(
            f"cannot read ZIP archive {path}: {exc}",
            ExitCode.SOURCE_ERROR,
        ) from exc

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

def run_script_path(
    path: Path,
    *,
    cwd: Path,
    timeout_seconds: float,
    selection_input: TextIO,
    selection_output: TextIO,
) -> int:
    """Run a script file or select one direct script from a directory."""
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
    return run_script_source(
        _read_selected_candidate(selected),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )

