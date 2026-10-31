"""Shared watcher fixtures and behavior probes."""
from __future__ import annotations

import struct

from patchharbor_watcher.platform import linux
from patchharbor import api
from patchharbor_watcher.apply_boundary import ApplyCompletion


def inotify_record(wd=1, mask=linux.IN_CREATE, name=b"file"):
    raw = b"" if name is None else name + b"\0"
    raw += b"\0" * (-len(raw) % 4)
    return struct.pack("=iIII", wd, mask, 0, len(raw)) + raw


def completion(status='no_candidate', lock=None, code=10):
    return ApplyCompletion(code, {'command': 'apply', 'success': code == 0,
        'process_exit_code': code, 'error': None, 'watcher_progress': {
            'version': 1, 'status': status, 'blocked_on': None if lock is None else {
                'kind': lock.kind, 'repo_id': lock.repo_id}}}, None, '')


def target(path):
    identity = path.stat()
    return api.ExchangeWatchTarget(path, identity.st_dev, identity.st_ino, (api.RepositoryId('00000000-0000-4000-8000-000000000001'),))
