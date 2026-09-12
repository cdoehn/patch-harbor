"""Source adapters that provide neutral PatchHarbor input artifacts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import DEFAULT_BUFFER_SIZE
import os
from pathlib import Path
from typing import TextIO

from patchharbor.progress import activity

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.models import DirectoryCandidate, InputArtifact
from patchharbor.platform.errors import describe_os_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY, ResourcePolicy
from patchharbor.temporary_resources import (
    create_private_file,
    private_request_directory,
)


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
    activity("SOURCE", f"Use explicit input file: {path}")
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
    activity("SOURCE", "Read standard input into a bounded private artifact")
    byte_stream = getattr(stream, "buffer", stream)
    bytes_written = 0

    try:
        with private_request_directory(prefix="patchharbor-input-") as directory:
            artifact_path = directory / "input.bin"
            descriptor: int | None = None
            try:
                descriptor = create_private_file(artifact_path)
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = None
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
            finally:
                if descriptor is not None:
                    os.close(descriptor)

            if bytes_written == 0:
                raise PatchHarborError(
                    "no script input received",
                    ExitCode.USAGE_ERROR,
                )

            activity("SOURCE", f"Prepared standard input: {bytes_written} bytes", "success")
            yield InputArtifact(
                path=artifact_path,
                display_name="standard input",
            )
    except PatchHarborError:
        raise
    except OSError as exc:
        raise PatchHarborError(
            "cannot read script source standard input: "
            f"{describe_os_error(exc)}",
            ExitCode.SOURCE_ERROR,
        ) from exc


def list_directory_entries(directory: Path) -> tuple[DirectoryCandidate, ...]:
    """Scan once and return sorted regular non-symlink files."""
    activity("SCAN", f"Scan manual input directory: {directory}", "heading")
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
        activity("SCAN", f"Inspect directory entry: {entry.name}")
        try:
            if entry.is_symlink() or not entry.is_file():
                activity("SKIP", f"{entry.name}: link or non-regular input", "detail")
                continue
            candidates.append(
                DirectoryCandidate(
                    path=entry,
                    modified_ns=entry.stat().st_mtime_ns,
                )
            )
        except OSError as exc:
            activity("SKIP", f"{entry.name}: metadata unavailable ({exc})", "detail")
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
