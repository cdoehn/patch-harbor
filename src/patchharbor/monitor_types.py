"""Immutable observations, never Execute permissions or reservations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def observed_at() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class MonitorRepository:
    repo_id: str
    path: str
    name: str
    registration: str
    observed_at: str
    git_status: str = 'unknown'
    commit: str | None = None
    fingerprint: str | None = None
    staged: int | None = None
    unstaged: int | None = None
    untracked: int | None = None
    exchange: str | None = None
    archive: str | None = None
    error: str | None = None
    configuration_status: str = 'unknown'


@dataclass(frozen=True, slots=True)
class MonitorExchange:
    path: str
    repository_ids: tuple[str, ...]
    available: bool
    observed_at: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MonitorSnapshot:
    observed_at: str
    repositories: tuple[MonitorRepository, ...]
    exchanges: tuple[MonitorExchange, ...]
    errors: tuple[str, ...] = ()

    def document(self) -> dict:
        return {'format_version': 2, 'kind': 'patchharbor-monitor', **asdict(self)}
