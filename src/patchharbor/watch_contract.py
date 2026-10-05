"""Immutable, advisory facts for event-driven automatic Apply clients.

These values never authorize a candidate or reserve a lock. Core rechecks the
configuration, directory identity and normal Apply gates on every invocation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from patchharbor.models import RepositoryId


@dataclass(frozen=True, slots=True)
class ExchangeWatchTarget:
    """One canonical directory and its observed physical identity/owners."""

    directory: Path
    device: int
    inode: int
    repository_ids: tuple[RepositoryId, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.directory, Path) or not self.directory.is_absolute():
            raise ValueError("watch directory must be an absolute Path")
        for value in (self.device, self.inode):
            if type(value) is not int or value < 0:
                raise ValueError("watch identity must contain nonnegative integers")
        if (not isinstance(self.repository_ids, tuple) or not self.repository_ids
                or any(not isinstance(item, RepositoryId) for item in self.repository_ids)
                or len(set(self.repository_ids)) != len(self.repository_ids)):
            raise ValueError("watch target requires distinct repository IDs")


@dataclass(frozen=True, slots=True)
class WatchControlPaths:
    """Registry-derived control paths, readable even with broken local config."""

    registry_path: Path
    configuration_paths: tuple[Path, ...]
    exchange_paths: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class WatchTargets:
    """Validated Exchange roots and control files (also for unset/missing repos).

Clients watch control-file parents/ancestors to notice atomic replacements and
restoration. No directory enumeration, bundle reads or Git state capture occurs.
"""

    exchanges: tuple[ExchangeWatchTarget, ...]
    registry_path: Path
    configuration_paths: tuple[Path, ...]


class ApplyLockKind(str, Enum):
    REGISTRY = "registry"
    REPOSITORY = "repository"
    EXCHANGE_STATE = "exchange_state"


@dataclass(frozen=True, slots=True)
class ApplyLock:
    """A technical lock, not an acquired handle or candidate reservation."""

    kind: ApplyLockKind
    repo_id: RepositoryId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ApplyLockKind):
            raise TypeError("lock kind must be ApplyLockKind")
        if self.kind is ApplyLockKind.REPOSITORY:
            if not isinstance(self.repo_id, RepositoryId):
                raise ValueError("repository lock requires a repository ID")
        elif self.repo_id is not None:
            raise ValueError("global lock must not carry a repository ID")


@dataclass(frozen=True, slots=True)
class ApplyReadiness:
    """Momentary availability; all probed locks have already been released."""

    blocked_on: ApplyLock | None = None

    @property
    def ready(self) -> bool:
        return self.blocked_on is None


class AutomaticApplyStatus(str, Enum):
    NO_CANDIDATE = "no_candidate"
    ATTEMPTED = "attempted"
    LOCKED = "locked"
    DRY_RUN = "dry_run"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AutomaticApplyResult:
    """Drain/stop decision independent of messages and primary Apply success.

ATTEMPTED means the replay boundary consumed a candidate, even if execution
failed. LOCKED permits readiness probes; ERROR requires a new external event.
Dry-runs never consume candidates and must not trigger a drain loop.
"""

    status: AutomaticApplyStatus
    blocked_on: ApplyLock | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AutomaticApplyStatus):
            raise TypeError("automatic status must be AutomaticApplyStatus")
        if ((self.status is AutomaticApplyStatus.LOCKED and not isinstance(self.blocked_on, ApplyLock))
                or (self.status is not AutomaticApplyStatus.LOCKED and self.blocked_on is not None)):
            raise ValueError("only locked automatic outcomes require a lock")
