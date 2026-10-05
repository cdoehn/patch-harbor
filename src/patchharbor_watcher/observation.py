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
