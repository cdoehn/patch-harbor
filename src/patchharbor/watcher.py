"""Thin polling watcher that delegates stable files through a public boundary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from io import BufferedReader
import json
import os
from pathlib import Path
import stat
import tempfile
import time
from typing import TextIO
import zipfile


_BROWSER_TEMP_SUFFIXES = (
    ".crdownload",
    ".download",
    ".opdownload",
    ".part",
    ".partial",
    ".tmp",
)
_RESULT_BUNDLE_MARKER = "patch-harbor-result-bundle"
_WATCHER_STATE_VERSION = 1
_MAX_RESULT_MANIFEST_BYTES = 1024 * 1024


@dataclass(frozen=True)
class FileObservation:
    """One top-level regular file observation used for stability checks."""

    path: Path
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class FileIdentity:
    """One physically stable file identified by canonical path and SHA-256."""

    path: Path
    content_sha256: str


@dataclass(frozen=True)
class ApplyCompletion:
    """Opaque completion returned by the public apply subprocess boundary."""

    process_exit_code: int
    apply_result: dict[str, object] | None
    invalid_response_text: str | None
    stderr_text: str


@dataclass
class WatcherState:
    """Consecutive observations and persistent processed file identities."""

    previous: set[FileObservation] = field(default_factory=set)
    processed_hashes: dict[Path, str] = field(default_factory=dict)
    state_path: Path | None = None
    input_directory: Path | None = None

    @classmethod
    def load(cls, input_directory: Path, state_path: Path) -> WatcherState:
        """Load one persistent watcher state or start with an empty state."""
        if not state_path.exists():
            return cls(
                state_path=state_path,
                input_directory=input_directory,
            )
        if not state_path.is_file() or state_path.is_symlink():
            raise RuntimeError("watcher state is not a regular file")
        try:
            document = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("cannot read watcher state") from exc
        if not isinstance(document, dict) or set(document) != {
            "format_version",
            "input_directory",
            "processed",
        }:
            raise RuntimeError("watcher state has an invalid schema")
        if document["format_version"] != _WATCHER_STATE_VERSION:
            raise RuntimeError("watcher state has an unsupported version")
        if document["input_directory"] != os.fspath(input_directory):
            raise RuntimeError("watcher state belongs to another input directory")
        processed = document["processed"]
        if not isinstance(processed, dict):
            raise RuntimeError("watcher state processed entries are invalid")
        processed_hashes: dict[Path, str] = {}
        for path_text, content_hash in processed.items():
            if not isinstance(path_text, str) or not isinstance(content_hash, str):
                raise RuntimeError("watcher state processed entries are invalid")
            path = Path(path_text)
            if not path.is_absolute() or path.parent != input_directory:
                raise RuntimeError("watcher state contains an invalid input path")
            if len(content_hash) != 64 or content_hash != content_hash.lower() or any(
                character not in "0123456789abcdef"
                for character in content_hash
            ):
                raise RuntimeError("watcher state contains an invalid content hash")
            processed_hashes[path] = content_hash
        return cls(
            processed_hashes=processed_hashes,
            state_path=state_path,
            input_directory=input_directory,
        )

    def observe(
        self,
        current: Sequence[FileObservation],
    ) -> tuple[FileObservation, ...]:
        """Return files unchanged across two consecutive observations."""
        current_set = set(current)
        stable = tuple(
            observation
            for observation in current
            if observation in self.previous
        )
        self.previous = current_set
        return stable

    def was_processed(self, identity: FileIdentity) -> bool:
        """Whether the same canonical path and content were already delegated."""
        return self.processed_hashes.get(identity.path) == identity.content_sha256

    def mark_processed(self, identity: FileIdentity) -> None:
        """Persist the newest processed content hash for one canonical path."""
        self.processed_hashes[identity.path] = identity.content_sha256
        self._persist()

    def _persist(self) -> None:
        if self.state_path is None or self.input_directory is None:
            return
        document = {
            "format_version": _WATCHER_STATE_VERSION,
            "input_directory": os.fspath(self.input_directory),
            "processed": {
                os.fspath(path): content_hash
                for path, content_hash in sorted(
                    self.processed_hashes.items(),
                    key=lambda item: os.fsencode(os.fspath(item[0])),
                )
            },
        }
        payload = (
            json.dumps(
                document,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.state_path.parent,
                prefix=".patchharbor-watcher-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                staged_path = Path(stream.name)
                try:
                    os.chmod(staged_path, 0o600)
                except OSError:
                    pass
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(staged_path, self.state_path)
            staged_path = None
        except OSError as exc:
            raise RuntimeError("cannot persist watcher state") from exc
        finally:
            if staged_path is not None:
                try:
                    staged_path.unlink(missing_ok=True)
                except OSError:
                    pass


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


def is_patchharbor_result_bundle(path: Path) -> bool:
    """Recognize only the Result Bundle marker needed to prevent watcher loops."""
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            matching = [
                info
                for info in archive.infolist()
                if info.filename == "manifest.json" and not info.is_dir()
            ]
            if len(matching) != 1 or matching[0].file_size > _MAX_RESULT_MANIFEST_BYTES:
                return False
            payload = archive.read(matching[0])
        document = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile):
        return False
    return (
        isinstance(document, dict)
        and document.get("marker") == _RESULT_BUNDLE_MARKER
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
    state: WatcherState,
    *,
    delegate: Callable[[Path], ApplyCompletion],
    log_stream: TextIO,
    error_stream: TextIO,
    stop_requested: Callable[[], bool] = _never_stop,
) -> int:
    """Observe once and delegate newly stable file identities until stopped."""
    stable = state.observe(observe_input_directory(directory))
    delegated = 0
    for observation in stable:
        if stop_requested():
            break
        identity = identify_stable_file(observation)
        if identity is None or state.was_processed(identity):
            continue
        if is_patchharbor_result_bundle(identity.path):
            state.mark_processed(identity)
            continue
        completion = delegate(identity.path)
        _write_operational_record(identity, completion, log_stream)
        if completion.stderr_text:
            error_stream.write(completion.stderr_text)
            if not completion.stderr_text.endswith("\n"):
                error_stream.write("\n")
            error_stream.flush()
        state.mark_processed(identity)
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

    state = (
        WatcherState.load(directory, state_path)
        if state_path is not None
        else WatcherState(input_directory=directory)
    )
    while not stop_requested():
        poll_input_directory_once(
            directory,
            state,
            delegate=delegate,
            log_stream=log_stream,
            error_stream=error_stream,
            stop_requested=stop_requested,
        )
        if stop_requested():
            break
        wait_between_polls(poll_interval_seconds)
