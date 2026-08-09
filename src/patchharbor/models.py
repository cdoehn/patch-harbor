"""Small immutable data carriers shared by PatchHarbor."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4


@dataclass(frozen=True)
class InputArtifact:
    """One locally readable artifact supplied by an input source."""

    path: Path
    display_name: str


@dataclass(frozen=True)
class BundleScript:
    """One named script in its bundle order."""

    text: str
    display_name: str


@dataclass(frozen=True)
class BundlePayload:
    """One byte-exact file carried by a ZIP PatchBundle."""

    relative_path: str
    content: bytes


@dataclass(frozen=True)
class PatchBundle:
    """Ordered scripts plus files made available before execution."""

    scripts: tuple[BundleScript, ...]
    payloads: tuple[BundlePayload, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class RepositoryId:
    """Canonical UUID-v4 identity of one local repository instance."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("repository ID is not a valid UUID")
        try:
            parsed = UUID(self.value)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("repository ID is not a valid UUID") from exc
        if parsed.version != 4 or str(parsed) != self.value:
            raise ValueError("repository ID is not a canonical UUID v4")

    @classmethod
    def new(cls) -> RepositoryId:
        """Create one canonical UUID-v4 repository identity."""
        return cls(str(uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RepositoryPath:
    """Physically canonical absolute path of one local repository."""

    value: Path

    def __post_init__(self) -> None:
        if not self.value.is_absolute():
            raise ValueError("repository path must be absolute")

    def __str__(self) -> str:
        return str(self.value)


class GitObjectFormat(str, Enum):
    """Supported storage formats for full Git object names."""

    SHA1 = "sha1"
    SHA256 = "sha256"

    @property
    def object_id_hex_length(self) -> int:
        return 40 if self is GitObjectFormat.SHA1 else 64

    @classmethod
    def for_hex_length(cls, length: int) -> GitObjectFormat:
        if length == cls.SHA1.object_id_hex_length:
            return cls.SHA1
        if length == cls.SHA256.object_id_hex_length:
            return cls.SHA256
        raise ValueError("unsupported Git object ID length")


@dataclass(frozen=True)
class GitObjectId:
    """One complete lowercase hexadecimal Git object name."""

    value: str
    object_format: GitObjectFormat

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("Git object ID must be text")
        if not isinstance(self.object_format, GitObjectFormat):
            raise ValueError("unsupported Git object format")
        if len(self.value) != self.object_format.object_id_hex_length:
            raise ValueError("Git object ID has the wrong length")
        if self.value != self.value.lower() or any(
            character not in "0123456789abcdef" for character in self.value
        ):
            raise ValueError("Git object ID must be lowercase hexadecimal")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class StagedRecord:
    """One canonical difference between the base tree and Git index."""

    path: bytes
    head_mode: bytes
    head_object: bytes
    index_mode: bytes
    index_object: bytes


@dataclass(frozen=True)
class UnstagedRecord:
    """One canonical difference between Git index and working tree."""

    path: bytes
    status: bytes
    index_mode: bytes
    index_object: bytes
    worktree_kind: bytes
    worktree_mode: bytes
    worktree_content: bytes


@dataclass(frozen=True)
class UntrackedRecord:
    """One canonical non-ignored file outside the Git index."""

    path: bytes
    mode: bytes
    size: int
    content: bytes

    def __post_init__(self) -> None:
        if self.size < 0 or self.size != len(self.content):
            raise ValueError("untracked size does not match content")


@dataclass(frozen=True)
class RepositoryState:
    """One immutable capture of all supported non-HEAD state."""

    staged: tuple[StagedRecord, ...] = ()
    unstaged: tuple[UnstagedRecord, ...] = ()
    untracked: tuple[UntrackedRecord, ...] = ()

    @property
    def dirty(self) -> bool:
        """Whether any supported state differs from HEAD."""
        return bool(self.staged or self.unstaged or self.untracked)


@dataclass(frozen=True)
class RepositoryContext:
    """One reproducible state description of a registered repository."""

    repo_id: RepositoryId
    repository_path: RepositoryPath
    base_commit: GitObjectId
    dirty: bool
    state_fingerprint: str
    fingerprint_algorithm: str


class RegistryStatus(str, Enum):
    """Observed consistency of one central registry mapping."""

    OK = "ok"
    MISSING = "missing"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class RegistryMapping:
    """One immutable central mapping from repository ID to local path."""

    repo_id: RepositoryId
    repository_path: RepositoryPath


@dataclass(frozen=True)
class RegistrySnapshot:
    """One complete, consistently read central registry snapshot."""

    repositories: tuple[RegistryMapping, ...]


@dataclass(frozen=True)
class RegistryRepository:
    """One registered repository together with its observed status."""

    repo_id: RepositoryId
    repository_path: RepositoryPath
    status: RegistryStatus


@dataclass(frozen=True)
class RegistryListResult:
    """Structured result of resolving all mappings in one snapshot."""

    repositories: tuple[RegistryRepository, ...]
