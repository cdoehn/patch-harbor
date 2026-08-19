"""Thin polling watcher that delegates stable files through a public boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from io import BufferedReader
import json
import os
from pathlib import Path
import stat
import time
from typing import TextIO

from patchharbor.watcher_loop_guard import is_result_bundle_for_loop_prevention
from patchharbor.watcher_state import (
    FileIdentity,
    FileObservation,
    ProcessedFileStore,
    StabilityTracker,
)


_BROWSER_TEMP_SUFFIXES = (
    ".crdownload",
    ".download",
    ".opdownload",
    ".part",
    ".partial",
    ".tmp",
)


@dataclass(frozen=True)
class ApplyCompletion:
    """Opaque completion returned by the public apply subprocess boundary."""

    process_exit_code: int
    apply_result: dict[str, object] | None
    invalid_response_text: str | None
    stderr_text: str


def is_browser_temporary_name(name: str) -> bool:
    """Recognize common browser download-temporary suffixes."""
    return name.casefold().endswith(_BROWSER_TEMP_SUFFIXES)


def observe_input_directory(directory: Path) -> tuple[FileObservation, ...]:
    """Observe top-level regular non-temporary files without recursion."""
    observations: list[FileObservation] = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if is_browser_temporary_name(entry.name):
                continue
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if not stat.S_ISREG(metadata.st_mode):
                continue
            observations.append(
                FileObservation(
                    path=directory / entry.name,
                    size=metadata.st_size,
                    mtime_ns=metadata.st_mtime_ns,
                )
            )
    observations.sort(key=lambda item: os.fsencode(item.path.name))
    return tuple(observations)


def _hash_open_file(stream: BufferedReader) -> str:
    digest = sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def identify_stable_file(observation: FileObservation) -> FileIdentity | None:
    """Hash one observation only while its regular-file identity stays stable."""
    try:
        before = observation.path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size != observation.size
            or before.st_mtime_ns != observation.mtime_ns
        ):
            return None
        with observation.path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened):
                return None
            content_hash = _hash_open_file(stream)
            after_open = os.fstat(stream.fileno())
        after_path = observation.path.stat(follow_symlinks=False)
        if (
            not os.path.samestat(before, after_open)
            or not os.path.samestat(before, after_path)
            or after_open.st_size != observation.size
            or after_open.st_mtime_ns != observation.mtime_ns
            or after_path.st_size != observation.size
            or after_path.st_mtime_ns != observation.mtime_ns
        ):
            return None
        canonical_path = observation.path.resolve(strict=True)
    except OSError:
        return None
    return FileIdentity(
        path=canonical_path,
        content_sha256=content_hash,
    )


def _never_stop() -> bool:
    return False


def _write_operational_record(
    identity: FileIdentity,
    completion: ApplyCompletion,
    stream: TextIO,
) -> None:
    record = {
        "event": "apply_completed",
        "input_path": os.fspath(identity.path),
        "input_sha256": identity.content_sha256,
        "process_exit_code": completion.process_exit_code,
        "apply_response_is_json_object": completion.apply_result is not None,
        "apply_result": completion.apply_result,
        "invalid_apply_response": completion.invalid_response_text,
    }
    stream.write(
        json.dumps(
            record,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    stream.write("\n")
    stream.flush()


def poll_input_directory_once(
    directory: Path,
    stability: StabilityTracker,
    processed: ProcessedFileStore,
    *,
    delegate: Callable[[Path], ApplyCompletion],
    log_stream: TextIO,
    error_stream: TextIO,
    stop_requested: Callable[[], bool] = _never_stop,
) -> int:
    """Observe once and delegate newly stable file identities until stopped."""
    observations = observe_input_directory(directory)
    processed.forget_absent(tuple(item.path for item in observations))
    stable = stability.observe(observations)
    delegated = 0
    for observation in stable:
        if stop_requested():
            break
        identity = identify_stable_file(observation)
        if identity is None or processed.was_processed(identity):
            continue
        if is_result_bundle_for_loop_prevention(identity.path):
            processed.mark_processed(identity)
            continue
        completion = delegate(identity.path)
        _write_operational_record(identity, completion, log_stream)
        if completion.stderr_text:
            error_stream.write(completion.stderr_text)
            if not completion.stderr_text.endswith("\n"):
                error_stream.write("\n")
            error_stream.flush()
        processed.mark_processed(identity)
        delegated += 1
    return delegated


def run_watcher(
    input_directory: Path,
    *,
    delegate: Callable[[Path], ApplyCompletion],
    state_path: Path | None = None,
    poll_interval_seconds: float = 1.0,
    log_stream: TextIO,
    error_stream: TextIO,
    stop_requested: Callable[[], bool] = _never_stop,
    wait_between_polls: Callable[[float], object] = time.sleep,
) -> None:
    """Periodically scan one non-recursive input directory until stopped."""
    if poll_interval_seconds <= 0:
        raise ValueError("poll interval must be greater than zero")
    directory = input_directory.expanduser().resolve(strict=True)
    if not directory.is_dir():
        raise NotADirectoryError(os.fspath(directory))

    stability = StabilityTracker()
    processed = (
        ProcessedFileStore.load(directory, state_path)
        if state_path is not None
        else ProcessedFileStore.in_memory(directory)
    )
    while not stop_requested():
        poll_input_directory_once(
            directory,
            stability,
            processed,
            delegate=delegate,
            log_stream=log_stream,
            error_stream=error_stream,
            stop_requested=stop_requested,
        )
        if stop_requested():
            break
        wait_between_polls(poll_interval_seconds)
