"""Optional observation files: private, bounded and independent of execution."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from threading import Event, Lock, Thread
import time
from uuid import uuid4, UUID

from patchharbor.configuration import RepositoryConfigurationPaths, load_configuration
from patchharbor.monitor_types import observed_at
from patchharbor.json_document import parse_json_document
from patchharbor.result_reader import _primary
from patchharbor.platform.filesystem import (PathKind, path_kind, atomic_replace_bytes,
                                           read_stable_regular_file_bounded)
from patchharbor.platform.monitor_process import process_identity
from patchharbor.progress import ActivityEvent, RequestStarted, RepositoryResolved, observe_additional
from patchharbor.registry import _parse_registry
from patchharbor.user_paths import raw_registration_user_paths

_current = ContextVar('patchharbor_monitor_publication', default=None)
MAX_DOCUMENT = 256 * 1024


def current_publication():
    return _current.get()


def observation_directory(paths):
    child = paths.state_directory / 'monitor-v1'
    if path_kind(child) not in (PathKind.MISSING, PathKind.DIRECTORY):
        raise ValueError('observation directory must not be linked')
    directory = child.resolve()
    if paths.registry_path.exists():
        registry = _parse_registry(read_stable_regular_file_bounded(paths.registry_path, max_bytes=4*1024*1024).content)
        for mapping in registry.repositories:
            if not mapping.repository_path.value.is_dir():
                continue
            config = load_configuration(RepositoryConfigurationPaths(mapping.repository_path, mapping.repo_id), validate_directory=False)
            exchange = config.exchange_directory
            if exchange is not None and (exchange == directory or exchange in directory.parents):
                raise ValueError('observation directory overlaps a configured Exchange')
    return directory


class Publication:
    """Only bounded memory updates on producer threads; all disk I/O is optional."""
    def __init__(self, kind, **data):
        self.instance_id = str(uuid4())
        self.paths = raw_registration_user_paths()
        self.lock, self.wake, self.stop = Lock(), Event(), Event()
        self.data, self.tail = data, b''
        self.document = {'format_version': 1, 'kind': kind, 'instance_id': self.instance_id,
                         'pid': os.getpid(), 'process_identity': None, 'started_at': observed_at(),
                         'updated_at': observed_at(), 'facts_updated_at': observed_at(), 'completed': False, 'phase': 'starting'}
        self.thread = Thread(target=self._publish, name='patchharbor-observation', daemon=True)
        self.thread.start()

    def update(self, *, phase=None, **data):
        try:
            with self.lock:
                self.data.update(data)
                self.document['facts_updated_at'] = observed_at()
                if phase is not None:
                    self.document['phase'] = phase
            self.wake.set()
        except Exception:
            pass

    def append(self, chunk):
        try:
            with self.lock:
                self.tail = (self.tail + chunk[-32768:])[-32768:]
            self.wake.set()
        except Exception:
            pass

    def event(self, event):
        if isinstance(event, ActivityEvent):
            self.update(phase=event.phase, message=event.message[:1024])
        elif isinstance(event, RequestStarted):
            self.update(patch_path=event.source_name, repo_id=event.requested_repo_id)
        elif isinstance(event, RepositoryResolved):
            self.update(repo_id=str(event.context.repo_id), repository_path=str(event.context.repository_path),
                        base_commit=str(event.context.base_commit), fingerprint=event.context.state_fingerprint)

    def execution_started(self, timeout):
        self.update(phase='entrypoint', effective_timeout_seconds=timeout, entrypoint_started_at=observed_at())

    def finish(self, report):
        try:
            self.update(phase='completed', primary_result=report.primary_result.as_document(),
                        result_status=report.result_bundle.status.value,
                        result_path=str(report.result_bundle.path) if report.result_bundle.path else None)
        except Exception:
            pass

    def close(self):
        try:
            with self.lock:
                if self.document['kind'] == 'apply' and 'primary_result' not in self.data:
                    self.data['completion_unknown'] = True
                    self.document['phase'] = 'outcome-unknown'
                self.document['completed'] = True
            self.stop.set()
            self.wake.set()
            self.thread.join(timeout=.1)
        except Exception:
            pass

    def _publish(self):
        try:
            directory = observation_directory(self.paths)
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if path_kind(directory) is not PathKind.DIRECTORY:
                return
            identity = process_identity(os.getpid())
            with self.lock:
                self.document['process_identity'] = identity
            path = directory / (self.document['kind'] + '-' + self.instance_id + '.json')
            while True:
                with self.lock:
                    document = {**self.document, 'updated_at': observed_at(), 'data': dict(self.data),
                                'log_tail': self.tail.decode('utf-8', errors='replace')}
                content = json.dumps(document, ensure_ascii=False, allow_nan=False).encode('utf-8')
                if len(content) <= MAX_DOCUMENT:
                    atomic_replace_bytes(path, content, mode=0o600)
                if document['completed']:
                    prune_completed(directory)
                    return
                if self.stop.is_set():
                    continue
                self.wake.wait(2)
                self.wake.clear()
                # Coalesce busy event/output producers; never queue a write per chunk.
                self.stop.wait(.25)
        except Exception:
            # Observation is optional. Its failure cannot change the run result.
            return


class NullPublication:
    instance_id = None
    def update(self, **kwargs): pass
    def append(self, chunk): pass
    def event(self, event): pass
    def execution_started(self, timeout): pass
    def finish(self, report): pass
    def close(self): pass


def start_publication(kind, **data):
    try:
        return Publication(kind, **data)
    except Exception:
        return NullPublication()


@contextmanager
def apply_observation(session, *, automatic, dry_run, timeout):
    publication = start_publication('apply', run_id=str(session.run_id),
        origin='automatic' if automatic else 'manual', dry_run=dry_run,
        requested_timeout_seconds=timeout, effective_timeout_seconds=None)
    token = _current.set(publication)
    try:
        with observe_additional(publication.event):
            yield publication
    finally:
        _current.reset(token)
        publication.close()


def _stamp(value):
    if type(value) is not str:
        raise ValueError('invalid observation timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('observation timestamp requires a timezone')
    return result


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError('observation identity must be a canonical UUID')


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def parse_live(content, name):
    row = parse_json_document(content)
    fields = {'format_version', 'kind', 'instance_id', 'pid', 'process_identity',
              'started_at', 'updated_at', 'facts_updated_at', 'completed', 'phase', 'data', 'log_tail'}
    if set(row) != fields or type(row['format_version']) is not int or row['format_version'] != 1:
        raise ValueError('unsupported live observation schema')
    _uuid(row['instance_id'])
    if row['kind'] not in ('apply', 'watcher') or name != row['kind'] + '-' + row['instance_id'] + '.json':
        raise ValueError('live filename and identity disagree')
    if type(row['pid']) is not int or not 0 < row['pid'] <= 2**32-1:
        raise ValueError('invalid publisher PID')
    if row['process_identity'] is not None and (type(row['process_identity']) is not str or not 0 < len(row['process_identity']) <= 128):
        raise ValueError('invalid publisher birth identity')
    _stamp(row['started_at']); _stamp(row['updated_at']); _stamp(row['facts_updated_at'])
    if type(row['completed']) is not bool or type(row['phase']) is not str or len(row['phase']) > 64:
        raise ValueError('invalid publisher lifecycle')
    if type(row['log_tail']) is not str or len(row['log_tail'].encode('utf-8')) > 3*32768:
        raise ValueError('invalid bounded log tail')
    data = row['data']
    allowed = {'message', 'patch_path', 'repo_id', 'repository_path', 'base_commit', 'fingerprint',
        'run_id', 'origin', 'dry_run', 'requested_timeout_seconds', 'effective_timeout_seconds',
        'entrypoint_started_at', 'entrypoint_exit_code', 'process_state', 'primary_result',
        'result_status', 'result_path', 'patch_sha256', 'subscriptions', 'targets',
        'targets_truncated', 'control_lock', 'control_probe_at', 'last_error', 'completion_unknown'}
    if type(data) is not dict or set(data) - allowed:
        raise ValueError('unknown live observation data')
    for key in ('message', 'patch_path', 'repository_path', 'base_commit', 'fingerprint',
                'result_path', 'last_error', 'process_state'):
        if data.get(key) is not None and type(data[key]) is not str:
            raise ValueError('invalid live text field: ' + key)
    for key in ('run_id', 'repo_id'):
        if data.get(key) is not None:
            _uuid(data[key])
    if data.get('patch_sha256') is not None and (type(data['patch_sha256']) is not str or
            len(data['patch_sha256']) != 64 or any(c not in '0123456789abcdef' for c in data['patch_sha256'])):
        raise ValueError('invalid patch digest')
    for key in ('dry_run', 'targets_truncated', 'completion_unknown'):
        if key in data and type(data[key]) is not bool:
            raise ValueError('invalid live boolean')
    for key in ('requested_timeout_seconds', 'effective_timeout_seconds', 'control_probe_at'):
        if data.get(key) is not None and (not _finite(data[key]) or data[key] <= 0):
            raise ValueError('invalid live duration/deadline')
    if data.get('entrypoint_started_at') is not None:
        _stamp(data['entrypoint_started_at'])
    if data.get('effective_timeout_seconds') is not None and data.get('entrypoint_started_at') is None:
        raise ValueError('effective timeout requires actual entrypoint start')
    if data.get('entrypoint_exit_code') is not None and type(data['entrypoint_exit_code']) is not int:
        raise ValueError('invalid exit code')
    if data.get('primary_result') is not None:
        _primary(data['primary_result'])
    if data.get('result_status') is not None and data['result_status'] not in ('created', 'failed', 'not_attempted'):
        raise ValueError('invalid Result publication status')
    if row['kind'] == 'apply' and (not data.get('run_id') or data.get('origin') not in ('manual', 'automatic') or type(data.get('dry_run')) is not bool):
        raise ValueError('incomplete Apply observation')
    targets, subscriptions = data.get('targets', []), data.get('subscriptions', [])
    if type(targets) is not list or len(targets) > 128 or type(subscriptions) is not list or len(subscriptions) > 1024:
        raise ValueError('invalid watcher target list')
    if any(type(path) is not str for path in subscriptions):
        raise ValueError('invalid watcher subscription')
    for target in targets:
        if type(target) is not dict or type(target.get('directory')) is not str:
            raise ValueError('invalid watcher target')
        for key in ('quiet_until', 'probe_at'):
            if target.get(key) is not None and not _finite(target[key]):
                raise ValueError('invalid watcher deadline')
        ids = target.get('repository_ids', [])
        if type(ids) is not list or len(ids) > 256:
            raise ValueError('invalid watcher repository identities')
        for identity in ids:
            _uuid(identity)
        if 'dirty' in target and type(target['dirty']) is not bool:
            raise ValueError('invalid watcher pending state')
    return row


def prune_completed(directory):
    """Only recognized completed observations; never active runs or other state."""
    try:
        paths = []
        for index, path in enumerate(directory.iterdir()):
            if index >= 512:
                break
            if path_kind(path) is PathKind.REGULAR_FILE and path.name.startswith(('apply-', 'watcher-')) and path.suffix == '.json':
                paths.append(path)
        if len(paths) <= 128:
            return
        completed = []
        for path in paths:
            try:
                row = parse_live(read_stable_regular_file_bounded(path, max_bytes=MAX_DOCUMENT).content, path.name)
                if row['completed']:
                    completed.append((_stamp(row['updated_at']), path))
            except Exception:
                pass
        for _, path in sorted(completed, key=lambda item: (item[0], str(item[1])), reverse=True)[128:]:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def monitor_live(*, instance_id=None):
    result = {'format_version': 1, 'kind': 'patchharbor-monitor-live', 'observed_at': observed_at(),
              'instances': [], 'errors': [], 'incomplete': False}
    paths = raw_registration_user_paths()
    directory = paths.state_directory / 'monitor-v1'
    try:
        if path_kind(directory) is PathKind.MISSING:
            return result
        if path_kind(directory) is not PathKind.DIRECTORY:
            raise ValueError('observation directory is not a regular directory')
        candidates = []
        if instance_id is not None:
            candidates = [directory / (kind + '-' + instance_id + '.json') for kind in ('apply', 'watcher')]
            candidates = [path for path in candidates if path.exists()]
        else:
            for index, path in enumerate(directory.iterdir()):
                if index >= 512:
                    result['incomplete'] = True
                    break
                if path.name.endswith('.json') and path.name.startswith(('apply-', 'watcher-')):
                    candidates.append(path)
            candidates.sort(key=lambda p: p.lstat().st_mtime_ns, reverse=True)
        if len(candidates) > 64:
            result['incomplete'] = True
        for path in candidates[:64]:
            try:
                content = read_stable_regular_file_bounded(path, max_bytes=MAX_DOCUMENT).content
                row = parse_live(content, path.name)
                age = (datetime.now(timezone.utc) - _stamp(row['updated_at'])).total_seconds()
                current = process_identity(row['pid'])
                row['live'] = not row['completed'] and current is not None and current == row['process_identity'] and 0 <= age <= 15
                row['stale'] = not row['completed'] and not row['live']
                row['stale_reason'] = ('publisher identity unavailable or changed' if current is None or current != row['process_identity']
                                       else 'heartbeat expired or clock changed') if row['stale'] else None
                row['age_seconds'] = max(0, age)
                if instance_id is None:
                    row.pop('log_tail', None)
                result['instances'].append(row)
            except Exception as exc:
                result['errors'].append(path.name + ': ' + str(exc))
    except Exception as exc:
        result['errors'].append(str(exc))
    return result
