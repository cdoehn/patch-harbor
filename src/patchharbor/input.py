"""Input artifacts, PatchBundle resolution, and current orchestration."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import TextIO
import zipfile

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.execution import execute_script_file
from patchharbor.files import temporary_script_file, write_payload_files
from patchharbor.models import BundleScript, InputArtifact, PatchBundle
from patchharbor.parser import ParsedScript, ScriptFormatError, parse_script


MAX_ZIP_ENTRIES = 1_000
MAX_ZIP_ENTRY_BYTES = 256 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 512 * 1024 * 1024
_ARTIFACT_COPY_CHUNK_BYTES = 64 * 1024
_ZIP_READ_CHUNK_BYTES = 64 * 1024
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def file_input_artifact(path: Path) -> InputArtifact:
    """Reference one existing filesystem input without copying it."""
    return InputArtifact(
        path=path,
        display_name=str(path),
        remove_after_use=False,
    )


def _read_stream_chunk(stream: object, size: int) -> bytes | None:
    read = getattr(stream, "read", None)
    if read is None:
        raise TypeError("standard input is not readable")
    chunk = read(size)
    if chunk in (b"", ""):
        return None
    if isinstance(chunk, str):
        return chunk.encode("utf-8")
    if isinstance(chunk, bytes):
        return chunk
    raise TypeError("standard input returned unsupported data")


@contextmanager
def stdin_input_artifact(stream: TextIO) -> Iterator[InputArtifact]:
    """Copy standard input as bytes to one secure temporary artifact."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-input-",
        suffix=".artifact",
    )
    artifact_path = Path(raw_path)
    byte_stream = getattr(stream, "buffer", stream)
    bytes_written = 0

    try:
        try:
            with os.fdopen(descriptor, "wb") as handle:
                while True:
                    chunk = _read_stream_chunk(
                        byte_stream,
                        _ARTIFACT_COPY_CHUNK_BYTES,
                    )
                    if chunk is None:
                        break
                    handle.write(chunk)
                    bytes_written += len(chunk)
        except (OSError, TypeError, UnicodeError) as exc:
            raise PatchHarborError(
                f"cannot read script source standard input: {exc}",
                ExitCode.SOURCE_ERROR,
            ) from exc

        if bytes_written == 0:
            raise PatchHarborError(
                "no script input received",
                ExitCode.USAGE_ERROR,
            )

        yield InputArtifact(
            path=artifact_path,
            display_name="standard input",
            remove_after_use=True,
        )
    finally:
        artifact_path.unlink(missing_ok=True)


def _default_script_suffix() -> str:
    return ".ps1" if os.name == "nt" else ".sh"


def _direct_script_suffix(artifact: InputArtifact) -> str:
    if artifact.remove_after_use:
        return _default_script_suffix()
    return artifact.path.suffix or _default_script_suffix()


def _artifact_source_error(
    artifact: InputArtifact,
    detail: object,
) -> PatchHarborError:
    return PatchHarborError(
        f"cannot read script source {artifact.display_name}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


def _zip_source_error(
    artifact: InputArtifact,
    detail: object,
) -> PatchHarborError:
    return PatchHarborError(
        f"cannot read ZIP archive {artifact.display_name}: {detail}",
        ExitCode.SOURCE_ERROR,
    )


def _zip_limit_error(
    artifact: InputArtifact,
    detail: str,
) -> PatchHarborError:
    return _zip_source_error(
        artifact,
        f"resource limit exceeded ({detail})",
    )


def _validate_zip_budgets(
    artifact: InputArtifact,
    entries: list[zipfile.ZipInfo],
) -> None:
    if len(entries) > MAX_ZIP_ENTRIES:
        raise _zip_limit_error(
            artifact,
            f"more than {MAX_ZIP_ENTRIES} entries",
        )

    total_bytes = 0
    for entry in entries:
        if entry.file_size > MAX_ZIP_ENTRY_BYTES:
            raise _zip_limit_error(
                artifact,
                f"entry {entry.filename!r} exceeds {MAX_ZIP_ENTRY_BYTES} bytes",
            )
        total_bytes += entry.file_size
        if total_bytes > MAX_ZIP_TOTAL_BYTES:
            raise _zip_limit_error(
                artifact,
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
    artifact: InputArtifact,
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
                    artifact,
                    f"entry {entry.filename!r} exceeds {MAX_ZIP_ENTRY_BYTES} bytes",
                )
            if total_bytes_read > MAX_ZIP_TOTAL_BYTES:
                raise _zip_limit_error(
                    artifact,
                    f"uncompressed data exceeds {MAX_ZIP_TOTAL_BYTES} bytes",
                )
            chunks.append(chunk)

    return b"".join(chunks), total_bytes_read


def _iter_zip_scripts(
    archive: zipfile.ZipFile,
    *,
    artifact: InputArtifact,
) -> Iterator[BundleScript]:
    entries = archive.infolist()
    _validate_zip_budgets(artifact, entries)
    total_bytes_read = 0

    for entry in entries:
        if not _is_regular_zip_entry(entry):
            continue

        raw_content, total_bytes_read = _read_zip_entry(
            archive,
            entry,
            artifact=artifact,
            total_bytes_read=total_bytes_read,
        )
        if raw_content.startswith(_ZIP_SIGNATURES):
            continue

        try:
            parsed_script = parse_script(raw_content.decode("utf-8"))
        except (UnicodeError, ScriptFormatError):
            continue

        yield BundleScript(
            script=parsed_script,
            suffix=PurePosixPath(entry.filename).suffix or _default_script_suffix(),
            display_name=entry.filename,
        )


def _looks_like_zip(artifact: InputArtifact) -> bool:
    if artifact.path.suffix.lower() == ".zip":
        return True
    try:
        with artifact.path.open("rb") as handle:
            return handle.read(4) in _ZIP_SIGNATURES
    except OSError:
        return False


def _no_valid_zip_script(artifact: InputArtifact) -> PatchHarborError:
    return PatchHarborError(
        "no valid PatchHarbor scripts found in ZIP archive "
        f"{artifact.display_name}",
        ExitCode.NO_VALID_SCRIPT,
    )


def _try_direct_script(
    artifact: InputArtifact,
) -> tuple[BundleScript | None, PatchHarborError | None, bool]:
    try:
        raw_content = artifact.path.read_bytes()
    except OSError as exc:
        raise _artifact_source_error(artifact, exc) from exc

    try:
        script_text = raw_content.decode("utf-8")
    except UnicodeError as exc:
        return (
            None,
            _artifact_source_error(artifact, exc),
            False,
        )

    try:
        parsed_script = parse_script(script_text)
    except ScriptFormatError as exc:
        return (
            None,
            PatchHarborError(str(exc), ExitCode.NO_VALID_SCRIPT),
            True,
        )

    return (
        BundleScript(
            script=parsed_script,
            suffix=_direct_script_suffix(artifact),
            display_name=artifact.display_name,
        ),
        None,
        True,
    )


def resolve_patch_bundle(artifact: InputArtifact) -> PatchBundle:
    """Resolve one source-neutral artifact to an ordered PatchBundle."""
    direct_script, direct_error, direct_was_utf8 = _try_direct_script(artifact)
    if direct_script is not None:
        return PatchBundle(scripts=(direct_script,))
    assert direct_error is not None

    try:
        archive = zipfile.ZipFile(artifact.path)
    except OSError:
        raise direct_error
    except zipfile.BadZipFile as exc:
        if not _looks_like_zip(artifact):
            if direct_was_utf8:
                raise direct_error
            raise PatchHarborError(
                "file is neither a UTF-8 PatchHarbor script nor a ZIP archive: "
                f"{artifact.display_name}",
                ExitCode.NO_VALID_SCRIPT,
            ) from exc
        raise _zip_source_error(artifact, exc) from exc

    try:
        with archive:
            scripts = tuple(_iter_zip_scripts(archive, artifact=artifact))
    except PatchHarborError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise _zip_source_error(artifact, exc) from exc

    if not scripts:
        raise _no_valid_zip_script(artifact)
    return PatchBundle(scripts=scripts)


def _execute_parsed_script(
    script: ParsedScript,
    *,
    suffix: str,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    write_payload_files(
        ((payload.name, payload.text) for payload in script.payload_files),
        cwd=cwd,
    )
    try:
        with temporary_script_file(script.text, suffix=suffix) as temporary_path:
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


def run_input_artifact(
    artifact: InputArtifact,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Resolve and execute every script in one input artifact."""
    bundle = resolve_patch_bundle(artifact)
    last_exit_code = 0
    for bundle_script in bundle.scripts:
        last_exit_code = _execute_parsed_script(
            bundle_script.script,
            suffix=bundle_script.suffix,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        if last_exit_code != 0:
            return last_exit_code
    return last_exit_code


@dataclass(frozen=True)
class DirectoryCandidate:
    """Stable display and sorting data for one directory candidate."""

    path: Path
    modified_ns: int

    @property
    def display_name(self) -> str:
        return self.path.name


def _is_directory_candidate(path: Path) -> bool:
    try:
        resolve_patch_bundle(file_input_artifact(path))
        return True
    except PatchHarborError:
        return False


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

    return run_input_artifact(
        file_input_artifact(candidate.path),
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
        return run_input_artifact(
            file_input_artifact(path),
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
