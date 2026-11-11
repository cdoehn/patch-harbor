"""One immutable projection of observed facts, with no execution or I/O."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from patchharbor.monitor_format import timestamp

Status = Literal['running', 'success', 'failure', 'waiting', 'unknown']


@dataclass(frozen=True, slots=True)
class Activity:
    code: str
    status: Status
    message: str
    sequence: int
    at: str | None
    since: str | None

    def document(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Operation:
    kind: str
    repo_id: str | None
    repository_path: str | None
    run_id: str | None
    task_path: str | None
    task_sha256: str | None
    bundle_number: str | None
    entrypoint_name: str | None
    activity: Activity

    @property
    def producing_result(self) -> bool:
        return self.kind == 'bundle' or self.activity.code.startswith('result-')


@dataclass(frozen=True, slots=True)
class Observation:
    operation: Operation
    current: bool
    completed: bool
    stale: bool
    status: Status


def activity(row: dict) -> Activity:
    """Missing current-generation activity stays unknown; never parse log prose."""
    value = row.get('activity')
    if value:
        return Activity(**value)
    stamp = row.get('facts_updated_at')
    return Activity('unknown', 'unknown', 'Aktivität unbekannt', 0, stamp, stamp)


def operation(row: dict) -> Operation:
    data = row.get('data', {})
    return Operation(row.get('kind', 'unknown'),
        *(data.get(key) for key in ('repo_id', 'repository_path', 'run_id', 'task_path',
                                    'task_sha256', 'bundle_number', 'entrypoint_name')),
        activity(row))


def observe(row: dict, document: dict, now: datetime | None = None) -> Observation:
    value = operation(row)
    completed = bool(row.get('completed'))
    stamp = timestamp(row.get('updated_at'))
    seconds = ((now or datetime.now(timezone.utc)) - stamp).total_seconds() if stamp else None
    current = bool(not completed and row.get('live') and not row.get('stale')
        and not document.get('live_view', {}).get('stale')
        and seconds is not None and 0 <= seconds <= 15)
    stale = not completed and not current
    status = value.activity.status
    if stale or (completed and status == 'running'):
        status = 'unknown'
    return Observation(value, current, completed, stale, status)


def result_outcome(data: dict, *, uncertain: bool = False) -> Status:
    """A failed Result publication is a failure even after a successful script."""
    if uncertain or data.get('stale'):
        return 'unknown'
    if data.get('error') or data.get('result_status') == 'failed':
        return 'failure'
    primary = data.get('primary_result')
    if primary:
        return 'success' if primary.get('success') is True else 'failure'
    return 'failure' if data.get('replay_status') == 'failed' else 'unknown'
