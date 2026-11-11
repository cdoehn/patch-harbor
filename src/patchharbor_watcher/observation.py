"""Filtered native subscriptions to paths supplied by the public Core boundary."""
from __future__ import annotations

from pathlib import Path

import patchharbor.api as api
from patchharbor_watcher.events import EventBackendError, EventErrorKind, EventKind, directory_identity


def nearest_directory(path: Path) -> Path:
    for candidate in (path, *path.parents):
        try:
            directory_identity(candidate)
            return candidate
        except EventBackendError:
            continue
    raise EventBackendError(EventErrorKind.INVALID_TARGET, 'no observable ancestor for control path')


def touches(path: Path, directory: Path, name: str | None) -> bool:
    """Notice a direct control change or creation/replacement of a missing parent."""
    if path == directory:
        return name is None
    if directory not in path.parents or name is None:
        return False
    return path.relative_to(directory).parts[0] == name


class Observation:
    def __init__(self):
        self.controls: tuple[Path, ...] = ()
        self.exchange_paths: tuple[Path, ...] = ()
        self.targets = ()

    def refresh(self, target_provider, control_provider):
        # Keep the old paths on a damaged registry so its repair remains visible.
        failure = None
        try:
            controls = control_provider()
            self.controls = (controls.registry_path, *controls.configuration_paths)
            self.exchange_paths = tuple(sorted(set(self.exchange_paths) | set(controls.exchange_paths), key=str))
            targets = target_provider()
            self.targets = targets.exchanges
            self.exchange_paths = tuple(t.directory for t in self.targets)
            self.controls = (targets.registry_path, *targets.configuration_paths)
        except (api.PatchHarborError, OSError) as exc:
            self.targets = ()
            failure = exc
        if not self.controls:
            if failure is not None:
                raise failure
            raise RuntimeError('Core returned no control paths')
        directories = {nearest_directory(path.parent) for path in self.controls}
        directories.update(nearest_directory(path) for path in self.exchange_paths)
        return tuple(sorted(directories, key=str)), failure

    def needs_refresh(self, event) -> bool:
        if event.kind in (EventKind.ROOT_INVALIDATED, EventKind.OVERFLOW):
            return True
        return any(touches(path, event.directory, event.name)
                   for path in (*self.controls, *self.exchange_paths)
                   if path != event.directory)



def live_observation(schedule, subscribed, *, executing, control_lock, control_probe, now, wall, active_exchanges=()):
    """Describe the event loop's own facts without acquiring/probing any lock."""
    def lock_fact(lock):
        return None if lock is None else {'kind': lock.kind, 'repo_id': lock.repo_id}
    def deadline(value):
        return None if value is None else wall + max(0, value - now)
    roots = list(schedule.roots.values())
    pending = [root for root in roots if root.dirty]
    lock = control_lock or next((root.lock for root in pending if root.lock is not None), None)
    code = ('executing' if executing else lock.kind + '-lock' if lock else
            'no-targets' if not roots else 'quiet' if any(root.due > now for root in pending) else
            'ready' if pending else 'watching')
    return dict(phase='executing' if executing else 'watching',
        activity_code=code, activity_status='running' if executing else 'waiting',
        active_exchanges=[str(p) for p in active_exchanges][:128],
        subscriptions=[str(p) for p in subscribed],
        targets=[{'directory': str(root.target.directory),
                  'repository_ids': [str(v) for v in root.target.repository_ids],
                  'dirty': root.dirty, 'quiet_until': deadline(root.due),
                  'blocked_on': lock_fact(root.lock), 'probe_at': deadline(root.probe_at)}
                 for root in roots[:128]], targets_truncated=len(roots) > 128,
        control_lock=lock_fact(control_lock), control_probe_at=deadline(control_probe))
