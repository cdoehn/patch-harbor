"""Validated immutable data shared by Result Bundle manifests and ZIP writing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from hashlib import sha256

from patchharbor.errors import result_bundle_error
from patchharbor.models import GitObjectId
from patchharbor.repository_paths import (
    RepositoryRelativePath,
    validate_repository_paths,
)


_SUPPORTED_FILE_MODES = frozenset(("100644", "100755"))


def _canonical_mode(raw: bytes) -> str:
    try:
        mode = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise result_bundle_error("snapshot contains an invalid file mode") from exc
    if mode not in _SUPPORTED_FILE_MODES:
        raise result_bundle_error("snapshot contains an unsupported file mode")
    return mode


def _content_size(content: bytes | memoryview) -> int:
    if isinstance(content, bytes):
        return len(content)
    if isinstance(content, memoryview):
        return content.nbytes
    raise TypeError("snapshot content must be bytes or memoryview")


@dataclass(frozen=True)
class ResultBaseEntry:
    """One committed file shared by the manifest and ZIP writer."""

    path: RepositoryRelativePath
    git_mode: str
    object_id: GitObjectId
    content: bytes | memoryview
    size: int = field(init=False)

    def __post_init__(self) -> None:
        if self.git_mode not in _SUPPORTED_FILE_MODES:
            raise result_bundle_error("snapshot contains an unsupported file mode")
        object.__setattr__(self, "size", _content_size(self.content))

    @property
    def executable(self) -> bool:
        """Whether the canonical manifest mode marks this file executable."""
        return self.git_mode == "100755"


@dataclass(frozen=True)
class ResultUntrackedEntry:
    """One untracked file shared by the manifest and ZIP writer."""

    path: RepositoryRelativePath
    mode: str
    content: bytes
    size: int = field(init=False)
    content_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.mode not in _SUPPORTED_FILE_MODES:
            raise result_bundle_error("snapshot contains an unsupported file mode")
        if not isinstance(self.content, bytes):
            raise TypeError("untracked snapshot content must be bytes")
        object.__setattr__(self, "size", len(self.content))
        object.__setattr__(self, "content_sha256", sha256(self.content).hexdigest())

    @property
    def executable(self) -> bool:
        """Whether the canonical manifest mode marks this file executable."""
        return self.mode == "100755"


@dataclass(frozen=True)
class ResultBundleSnapshot:
    """One immutable set of bytes used for manifest and ZIP generation."""

    base_entries: tuple[ResultBaseEntry, ...]
    staged_patch: bytes
    unstaged_patch: bytes
    untracked_entries: tuple[ResultUntrackedEntry, ...]


def _require_unique_paths(paths: tuple[bytes, ...], description: str) -> None:
    if len(paths) != len(set(paths)):
        raise result_bundle_error(f"snapshot contains duplicate {description} paths")


def build_result_bundle_snapshot(
    *,
    base_entries: Iterable[
        tuple[bytes, bytes, GitObjectId, bytes | memoryview]
    ],
    staged_patch: bytes,
    unstaged_patch: bytes,
    untracked_entries: Iterable[tuple[bytes, bytes, bytes]],
) -> ResultBundleSnapshot:
    """Build one validated shared snapshot from already captured bytes."""
    raw_base_entries = tuple(base_entries)
    raw_untracked_entries = tuple(untracked_entries)
    base_paths = tuple(entry[0] for entry in raw_base_entries)
    untracked_paths = tuple(entry[0] for entry in raw_untracked_entries)
    _require_unique_paths(base_paths, "base")
    _require_unique_paths(untracked_paths, "untracked")

    validated_paths = validate_repository_paths((*base_paths, *untracked_paths))
    paths_by_bytes = {path.original_bytes: path for path in validated_paths}

    if not isinstance(staged_patch, bytes) or not isinstance(unstaged_patch, bytes):
        raise TypeError("reconstruction patches must be bytes")

    materialized_base = tuple(
        sorted(
            (
                ResultBaseEntry(
                    path=paths_by_bytes[path],
                    git_mode=_canonical_mode(mode),
                    object_id=object_id,
                    content=content,
                )
                for path, mode, object_id, content in raw_base_entries
            ),
            key=lambda entry: entry.path.original_bytes,
        )
    )
    materialized_untracked = tuple(
        sorted(
            (
                ResultUntrackedEntry(
                    path=paths_by_bytes[path],
                    mode=_canonical_mode(mode),
                    content=content,
                )
                for path, mode, content in raw_untracked_entries
            ),
            key=lambda entry: entry.path.original_bytes,
        )
    )
    return ResultBundleSnapshot(
        base_entries=materialized_base,
        staged_patch=staged_patch,
        unstaged_patch=unstaged_patch,
        untracked_entries=materialized_untracked,
    )
