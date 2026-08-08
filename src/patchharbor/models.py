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


@dataclass(frozen=True)
class RepositoryContext:
    """One reproducible state description of a registered repository."""

    repo_id: RepositoryId
    repository_path: RepositoryPath
    base_commit: str
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
