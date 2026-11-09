"""Optional observation files: private, bounded and independent of execution."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Event, Lock, Thread
import time
from uuid import uuid4

from patchharbor.configuration import RepositoryConfigurationPaths, load_configuration
from patchharbor.monitor_types import observed_at
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
    directory = (paths.state_directory / 'monitor-v1').resolve()
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
                         'updated_at': observed_at(), 'completed': False, 'phase': 'starting'}
        self.thread = Thread(target=self._publish, name='patchharbor-observation', daemon=True)
        self.thread.start()

    def update(self, *, phase=None, **data):
        try:
            with self.lock:
                self.data.update(data)
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
            self.document['process_identity'] = process_identity(os.getpid())
            path = directory / (self.document['kind'] + '-' + self.instance_id + '.json')
            while True:
                with self.lock:
                    document = {**self.document, 'updated_at': observed_at(), 'data': dict(self.data),
                                'log_tail': self.tail.decode('utf-8', errors='replace')}
                content = json.dumps(document, ensure_ascii=False, allow_nan=False).encode('utf-8')
                if len(content) <= MAX_DOCUMENT:
                    atomic_replace_bytes(path, content, mode=0o600)
                if self.stop.is_set():
                    return
                self.wake.wait(2)
                self.wake.clear()
                # Coalesce busy event/output producers; never queue a write per chunk.
                self.stop.wait(.1)
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


def monitor_live(*, instance_id=None):
    result = {'format_version': 1, 'kind': 'patchharbor-monitor-live', 'observed_at': observed_at(),
              'instances': [], 'errors': [], 'incomplete': False}
    paths = raw_registration_user_paths()
    directory = paths.state_directory / 'monitor-v1'
    if not directory.exists():
        return result
    try:
        candidates = []
        for path in directory.iterdir():
            if path.name.endswith('.json') and path.name.startswith(('apply-', 'watcher-')):
                candidates.append(path)
            if len(candidates) > 512:
                result['incomplete'] = True
                break
        candidates.sort(key=lambda p: p.stat().st_mtime_ns, reverse=True)
        if len(candidates) > 64:
            result['incomplete'] = True
        for path in candidates[:64]:
            try:
                content = read_stable_regular_file_bounded(path, max_bytes=MAX_DOCUMENT).content
                row = json.loads(content)
                if row.get('format_version') != 1 or row.get('kind') not in ('apply', 'watcher'):
                    raise ValueError('unsupported live observation format')
                if instance_id is not None and row['instance_id'] != instance_id:
                    continue
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(row['updated_at'])).total_seconds()
                current = process_identity(row['pid'])
                row['live'] = not row['completed'] and current is not None and current == row['process_identity'] and 0 <= age <= 15
                row['stale'] = not row['completed'] and not row['live']
                row['age_seconds'] = max(0, age)
                if instance_id is None:
                    row.pop('log_tail', None)
                result['instances'].append(row)
            except Exception as exc:
                result['errors'].append(path.name + ': ' + str(exc))
    except Exception as exc:
        result['errors'].append(str(exc))
    return result
