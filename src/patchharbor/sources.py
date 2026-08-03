"""Source adapters that provide neutral PatchHarbor input artifacts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import DEFAULT_BUFFER_SIZE
import os
from pathlib import Path
import tempfile
from typing import TextIO

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import InputArtifact
from patchharbor.platform.errors import describe_os_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy


def _input_limit_error(
    display_name: str,
    policy: ResourcePolicy,
) -> PatchHarborError:
    return PatchHarborError(
        "resource limit exceeded "
        f"(input artifact {display_name!r} exceeds "
        f"{policy.max_input_artifact_bytes} bytes)",
        ExitCode.SOURCE_ERROR,
    )


def file_input_artifact(path: Path) -> InputArtifact:
    """Reference one filesystem input without interpreting its content."""
    return InputArtifact(path=path, display_name=str(path))


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
def stdin_input_artifact(
    stream: TextIO,
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> Iterator[InputArtifact]:
    """Copy standard input as bounded bytes to one secure temporary artifact."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-input-",
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
                        DEFAULT_BUFFER_SIZE,
                    )
                    if chunk is None:
                        break
                    if (
                        bytes_written + len(chunk)
                        > policy.max_input_artifact_bytes
                    ):
                        raise _input_limit_error("standard input", policy)
                    handle.write(chunk)
                    bytes_written += len(chunk)
        except (OSError, TypeError, UnicodeError) as exc:
            raise PatchHarborError(
                "cannot read script source standard input: "
                f"{describe_os_error(exc) if isinstance(exc, OSError) else exc}",
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
        )
    finally:
        artifact_path.unlink(missing_ok=True)


@dataclass(frozen=True)
class DirectoryCandidate:
    """Stable display and sorting data for one regular directory entry."""

    path: Path
    modified_ns: int

    @property
    def display_name(self) -> str:
        return self.path.name


def list_directory_entries(directory: Path) -> tuple[DirectoryCandidate, ...]:
    """Scan once and return sorted regular non-symlink files."""
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        raise PatchHarborError(
            f"cannot read script source directory {directory}: "
            f"{describe_os_error(exc)}",
            ExitCode.SOURCE_ERROR,
        ) from exc

    candidates: list[DirectoryCandidate] = []
    for entry in entries:
        try:
            if entry.is_symlink() or not entry.is_file():
                continue
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
    """Choose exactly one candidate without accessing the filesystem."""
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
