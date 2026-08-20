"""Persistent processing status kept separate from watcher observations."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    path_kind,
)


_WATCHER_STATE_VERSION = 1


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


@dataclass
class StabilityTracker:
    """Consecutive observations used only to decide whether a file is stable."""

    _previous: set[FileObservation] = field(default_factory=set)

    def observe(
        self,
        current: tuple[FileObservation, ...],
    ) -> tuple[FileObservation, ...]:
        """Return observations unchanged across two consecutive scans."""
        current_set = set(current)
        stable = tuple(
            observation
            for observation in current
            if observation in self._previous
        )
        self._previous = current_set
        return stable


@dataclass
class ProcessedFileStore:
    """Persistent processed-content status for one canonical input directory."""

    input_directory: Path
    state_path: Path | None = None
    _processed_hashes: dict[Path, str] = field(default_factory=dict)

    @classmethod
    def in_memory(cls, input_directory: Path) -> ProcessedFileStore:
        """Create a non-persistent status store for tests and direct use."""
        return cls(input_directory=input_directory)

    @classmethod
    def load(
        cls,
        input_directory: Path,
        state_path: Path,
    ) -> ProcessedFileStore:
        """Load one persistent processed-file store or an empty one."""
        try:
            kind = path_kind(state_path)
        except FileSystemOperationError as exc:
            raise RuntimeError("cannot inspect watcher state") from exc
        if kind is PathKind.MISSING:
            return cls(
                input_directory=input_directory,
                state_path=state_path,
            )
        if kind is not PathKind.REGULAR_FILE:
            raise RuntimeError("watcher state is not a regular file")
        try:
            document = json.loads(state_path.read_bytes().decode("utf-8"))
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
            if not _is_sha256(content_hash):
                raise RuntimeError("watcher state contains an invalid content hash")
            processed_hashes[path] = content_hash
        return cls(
            input_directory=input_directory,
            state_path=state_path,
            _processed_hashes=processed_hashes,
        )

    def was_processed(self, identity: FileIdentity) -> bool:
        """Whether the same canonical path and content were already delegated."""
        return self._processed_hashes.get(identity.path) == identity.content_sha256

    def mark_processed(self, identity: FileIdentity) -> None:
        """Atomically persist one new status before publishing it in memory."""
        next_hashes = dict(self._processed_hashes)
        next_hashes[identity.path] = identity.content_sha256
        self._replace(next_hashes)

    def forget_absent(self, present_paths: tuple[Path, ...]) -> None:
        """Forget entries for files no longer present in the flat input."""
        present = set(present_paths)
        self._replace(
            {
                path: content_hash
                for path, content_hash in self._processed_hashes.items()
                if path in present
            }
        )

    def _replace(self, processed_hashes: dict[Path, str]) -> None:
        if processed_hashes == self._processed_hashes:
            return
        if self.state_path is not None:
            self._persist(processed_hashes)
        self._processed_hashes = processed_hashes

    def _persist(self, processed_hashes: dict[Path, str]) -> None:
        if self.state_path is None:
            return
        document = {
            "format_version": _WATCHER_STATE_VERSION,
            "input_directory": os.fspath(self.input_directory),
            "processed": {
                os.fspath(path): content_hash
                for path, content_hash in sorted(
                    processed_hashes.items(),
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
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            if path_kind(self.state_path.parent) is not PathKind.DIRECTORY:
                raise RuntimeError("watcher state parent is not a directory")
            if path_kind(self.state_path) not in {
                PathKind.MISSING,
                PathKind.REGULAR_FILE,
            }:
                raise RuntimeError("watcher state is not a regular file")
            atomic_replace_bytes(self.state_path, payload)
        except RuntimeError:
            raise
        except (FileSystemOperationError, OSError) as exc:
            raise RuntimeError("cannot persist watcher state") from exc


def _is_sha256(value: str) -> bool:
    return (
        len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )
