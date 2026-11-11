"""Transient Windows reader conflicts must not permanently freeze live status."""
import errno
import json
import os
from threading import Event

import pytest

from patchharbor import api, monitor_live
from patchharbor.platform.filesystem import FileSystemOperationError
from tests.test_monitor import registered
from tests.test_monitor_live import instance, wait_for


def replacement_conflict(code):
    cause = PermissionError(errno.EACCES, 'another reader temporarily prevents replacement')
    cause.winerror = code
    return FileSystemOperationError('cannot replace target', cause)


@pytest.mark.parametrize('code', [5, 32, 33], ids=['access-denied', 'sharing', 'lock'])
def test_live_updates_resume_after_transient_windows_replacement_conflict(tmp_path, monkeypatch, code):
    registered(tmp_path, monkeypatch)
    real_write = monitor_live.atomic_replace_bytes
    failed = Event()

    def write(path, content, **options):
        if json.loads(content)['phase'] == 'watching' and not failed.is_set():
            failed.set()
            raise replacement_conflict(code)
        return real_write(path, content, **options)

    monkeypatch.setattr(monitor_live, 'atomic_replace_bytes', write)
    publication = api.watcher_observation()
    try:
        wait_for(lambda: instance(publication.instance_id))
        publication.update(phase='watching', targets=[{'directory': '/after-conflict'}])
        assert failed.wait(5)
        row = wait_for(lambda: (r if r['data'].get('targets') == [{'directory': '/after-conflict'}] else None)
                       if (r := instance(publication.instance_id)) else None, timeout=3)
        assert row['live'] and not row['completed']
        publication.close()
        final = wait_for(lambda: (r if r['completed'] else None)
                         if (r := instance(publication.instance_id)) else None)
        assert final['data']['targets'] == row['data']['targets']
    finally:
        publication.close()
        publication.thread.join(timeout=3)


def test_persistent_replacement_failure_has_bounded_background_work(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    attempts = []

    def denied(*args, **kwargs):
        attempts.append(None)
        raise replacement_conflict(5)

    monkeypatch.setattr(monitor_live, 'atomic_replace_bytes', denied)
    publication = api.watcher_observation()
    try:
        publication.thread.join(timeout=5)
        assert not publication.thread.is_alive()
        assert 1 < len(attempts) <= 6
        assert instance(publication.instance_id) is None
    finally:
        publication.close()


def test_staging_failure_is_not_retried_as_a_windows_reader_conflict(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    attempts = []

    def denied(*args, **kwargs):
        attempts.append(None)
        cause = PermissionError(errno.EACCES, 'directory denies creation')
        cause.winerror = 5
        raise FileSystemOperationError('cannot stage replacement', cause)

    monkeypatch.setattr(monitor_live, 'atomic_replace_bytes', denied)
    publication = api.watcher_observation()
    try:
        publication.thread.join(timeout=3)
        assert not publication.thread.is_alive() and len(attempts) == 1
    finally:
        publication.close()


@pytest.mark.skipif(os.name != 'nt', reason='native Windows open-reader replacement conflict')
def test_native_windows_open_reader_does_not_disable_publisher(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    real_write = monitor_live.atomic_replace_bytes
    conflict = Event()

    def write(path, content, **options):
        if json.loads(content)['phase'] == 'watching' and not conflict.is_set():
            # CRT open denies DELETE sharing. The actual atomic writer must
            # encounter this native conflict; close the reader before retry.
            with path.open('rb'):
                try:
                    return real_write(path, content, **options)
                except FileSystemOperationError:
                    conflict.set()
                    raise
        return real_write(path, content, **options)

    monkeypatch.setattr(monitor_live, 'atomic_replace_bytes', write)
    publication = api.watcher_observation()
    try:
        wait_for(lambda: instance(publication.instance_id))
        publication.update(phase='watching', targets=[{'directory': '/native-reader'}])
        assert conflict.wait(5), 'native replacement conflict was not exercised'
        row = wait_for(lambda: (r if r['data'].get('targets') == [{'directory': '/native-reader'}] else None)
                       if (r := instance(publication.instance_id)) else None)
        assert row['live'] and publication.thread.is_alive()
    finally:
        publication.close()
        publication.thread.join(timeout=3)
