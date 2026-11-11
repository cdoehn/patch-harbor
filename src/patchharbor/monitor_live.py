"""Nonblocking optional publishers, scoped independently to each request/instance."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from threading import Event, Lock, Thread
from time import sleep
from uuid import uuid4

from patchharbor.monitor_live_schema import MAX_DOCUMENT
from patchharbor.monitor_activity import record_activity, activity_event, WATCH_LABELS
from patchharbor.monitor_live_storage import observation_directory, prune_completed
from patchharbor.monitor_types import observed_at
from patchharbor.platform.filesystem import FileSystemOperationError, PathKind, path_kind, atomic_replace_bytes
from patchharbor.platform.monitor_process import process_identity
from patchharbor.progress import ActivityEvent, RequestStarted, RepositoryResolved, ScriptPrepared, observe_additional
from patchharbor.user_paths import raw_registration_user_paths

_current = ContextVar('patchharbor_monitor_publication', default=None)


def current_publication():
    return _current.get()


class Publication:
    """Only bounded memory updates on producer threads; all disk I/O is optional."""
    def __init__(self, kind, **data):
        self.instance_id = str(uuid4())
        self.paths = raw_registration_user_paths()
        self.lock, self.wake, self.stop = Lock(), Event(), Event()
        self.data, self.tail = data, b''
        self.document = {'format_version': 2, 'kind': kind, 'instance_id': self.instance_id,
                         'pid': os.getpid(), 'process_identity': None, 'started_at': observed_at(),
                         'updated_at': observed_at(), 'facts_updated_at': observed_at(), 'completed': False, 'phase': 'starting',
                         'history': []}
        record_activity(self.document, 'starting', 'running',
                        'Watcher startet' if kind == 'watcher' else 'PatchHarbor startet', observed_at())
        self.thread = Thread(target=self._publish, name='patchharbor-observation', daemon=True)
        self.thread.start()

    def update(self, *, phase=None, activity_code=None, activity_status='running', activity_message=None, **data):
        try:
            with self.lock:
                self.data.update(data)
                self.document['facts_updated_at'] = observed_at()
                if phase is not None:
                    self.document['phase'] = phase
                if activity_code is None and self.document['kind'] == 'watcher' and phase in WATCH_LABELS:
                    activity_code = phase
                    activity_status = ('failure' if self.data.get('last_error') else 'success') if phase == 'stopped' else 'waiting' if phase == 'watching' else 'running'
                if activity_code is not None:
                    record_activity(self.document, activity_code, activity_status,
                                    activity_message or WATCH_LABELS.get(activity_code, activity_code), observed_at())
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
            item = activity_event(event)
            if item is not None:
                code, status, message = item
                self.update(activity_code=code, activity_status=status, activity_message=message)
        elif isinstance(event, RequestStarted):
            entrypoint = next((f.name for f in event.files if f.kind == 'entrypoint'), None)
            self.update(patch_path=event.source_name, repo_id=event.requested_repo_id, entrypoint_name=entrypoint)
        elif isinstance(event, RepositoryResolved):
            self.update(repo_id=str(event.context.repo_id), repository_path=str(event.context.repository_path),
                        base_commit=str(event.context.base_commit), fingerprint=event.context.state_fingerprint)
        elif isinstance(event, ScriptPrepared):
            self.update(entrypoint_name=event.name)

    def execution_started(self, timeout):
        self.update(phase='entrypoint', effective_timeout_seconds=timeout, entrypoint_started_at=observed_at(),
                    activity_code='entrypoint', activity_message='Entrypoint läuft')

    def finish(self, report):
        try:
            automatic = report.automatic.status.value if report.automatic is not None else None
            code, status = 'completed', 'success' if report.success else 'failure'
            message = ('Result-Bundle' if self.document['kind'] == 'bundle' else 'Apply') + (' erfolgreich abgeschlossen' if report.success else ' fehlgeschlagen')
            if automatic == 'no_candidate':
                code, status, message = 'no-candidate', 'waiting', 'Kein ausführbarer Patch gefunden'
            elif automatic == 'locked':
                code, status = report.automatic.blocked_on.kind.value + '-lock', 'waiting'
                message = WATCH_LABELS[code]
            elif report.dry_run:
                message = 'Validierung abgeschlossen · Dry-run' if report.success else 'Validierung fehlgeschlagen · Dry-run'
            self.update(phase='completed', primary_result=report.primary_result.as_document(),
                        result_status=report.result_bundle.status.value,
                        result_path=str(report.result_bundle.path) if report.result_bundle.path else None,
                        automatic_status=automatic, activity_code=code, activity_status=status, activity_message=message)
        except Exception:
            pass

    def close(self):
        try:
            with self.lock:
                if self.document['kind'] in ('apply', 'bundle') and 'primary_result' not in self.data and self.document['activity']['status'] != 'failure':
                    self.data['completion_unknown'] = True
                    self.document['phase'] = 'outcome-unknown'
                    record_activity(self.document, 'outcome-unknown', 'unknown', 'Abschluss nicht bestätigt', observed_at())
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
            replacement_conflicts = 0
            while True:
                with self.lock:
                    document = {**self.document, 'updated_at': observed_at(), 'data': dict(self.data),
                                'history': list(self.document['history']), 'activity': dict(self.document['activity']),
                                'log_tail': self.tail.decode('utf-8', errors='replace')}
                content = json.dumps(document, ensure_ascii=False, allow_nan=False).encode('utf-8')
                if len(content) <= MAX_DOCUMENT:
                    try:
                        atomic_replace_bytes(path, content, mode=0o600)
                    except FileSystemOperationError as exc:
                        # A concurrent Windows reader may briefly deny replacement.
                        # Retry only this optional publication, with bounded work;
                        # every retry captures the latest state, including shutdown.
                        if (exc.operation != 'cannot replace target'
                                or getattr(exc.cause, 'winerror', None) not in (5, 32, 33)
                                or replacement_conflicts >= 4):
                            raise
                        replacement_conflicts += 1
                        sleep(.25)
                        continue
                    replacement_conflicts = 0
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


@contextmanager
def bundle_observation(session, repository):
    publication = start_publication('bundle', run_id=str(session.run_id), origin='manual',
                                    dry_run=False, repository_path=str(repository))
    token = _current.set(publication)
    try:
        with observe_additional(publication.event):
            yield publication
    except Exception as exc:
        publication.update(phase='completed', activity_code='completed', activity_status='failure',
                           activity_message='Result-Bundle fehlgeschlagen', last_error=str(exc)[:1024])
        raise
    finally:
        _current.reset(token)
        publication.close()
