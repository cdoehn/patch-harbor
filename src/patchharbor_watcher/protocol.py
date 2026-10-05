"""Private worker metadata; the persisted Core/CLI Apply envelope stays unchanged."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from uuid import UUID

MAX_REQUEST_BYTES = 1024 * 1024
STATUSES = frozenset({'no_candidate', 'attempted', 'locked', 'dry_run', 'error'})


@dataclass(frozen=True)
class LockReference:
    kind: str
    repo_id: str | None = None

    def __post_init__(self):
        if self.kind not in ('registry', 'repository', 'exchange_state'):
            raise ValueError('invalid worker lock kind')
        if self.kind == 'repository':
            if not isinstance(self.repo_id, str) or str(UUID(self.repo_id)) != self.repo_id:
                raise ValueError('invalid worker repository ID')
        elif self.repo_id is not None:
            raise ValueError('global lock carries repository ID')


@dataclass(frozen=True)
class Progress:
    status: str
    blocked_on: LockReference | None = None

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError('invalid automatic progress')
        if (self.status == 'locked') != isinstance(self.blocked_on, LockReference):
            raise ValueError('invalid automatic lock progress')


def progress_document(progress) -> dict:
    lock = progress.blocked_on
    return {'version': 1, 'status': progress.status.value,
            'blocked_on': None if lock is None else {
                'kind': lock.kind.value, 'repo_id': None if lock.repo_id is None else str(lock.repo_id)}}


def read_progress(document) -> Progress:
    if not isinstance(document, dict) or set(document) != {'version', 'status', 'blocked_on'}:
        raise ValueError('missing or invalid worker progress')
    if type(document['version']) is not int or document['version'] != 1:
        raise ValueError('unsupported worker progress version')
    lock = document['blocked_on']
    if lock is not None:
        if not isinstance(lock, dict) or set(lock) != {'kind', 'repo_id'}:
            raise ValueError('invalid worker lock')
        lock = LockReference(**lock)
    return Progress(document['status'], lock)


def encode_scope(targets) -> bytes:
    document = {'version': 1, 'exchanges': None if targets is None else [
        {'directory': str(t.directory), 'device': t.device, 'inode': t.inode,
         'repository_ids': [str(repo_id) for repo_id in t.repository_ids]} for t in targets]}
    raw = json.dumps(document, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError('worker scope exceeds request limit')
    return raw


def decode_scope(raw: bytes):
    if not raw:  # Legacy explicit one-shot worker still requests global automatic Apply.
        return None
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError('worker scope exceeds request limit')
    def reject_constant(value):
        raise ValueError('non-finite worker input')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate worker key')
            result[key] = value
        return result
    document = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique)
    if (not isinstance(document, dict) or set(document) != {'version', 'exchanges'}
            or type(document['version']) is not int or document['version'] != 1):
        raise ValueError('invalid worker scope envelope')
    entries = document['exchanges']
    if entries is None:
        return None
    if not isinstance(entries, list):
        raise ValueError('invalid worker exchanges')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'directory', 'device', 'inode', 'repository_ids'}:
            raise ValueError('invalid worker exchange')
        directory = entry['directory']
        if not isinstance(directory, str) or not Path(directory).is_absolute() or directory in seen:
            raise ValueError('invalid worker directory')
        seen.add(directory)
        if any(type(entry[k]) is not int or entry[k] < 0 for k in ('device', 'inode')):
            raise ValueError('invalid worker physical identity')
        ids = entry['repository_ids']
        if (not isinstance(ids, list) or not ids or any(not isinstance(v, str) or str(UUID(v)) != v for v in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError('invalid worker owners')
    return entries
