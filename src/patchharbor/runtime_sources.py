"""Read only the executing distribution's directory or canonical ZIP resources."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipimport import zipimporter

from patchharbor.platform.filesystem import (
    PathKind, path_kind, read_stable_regular_file_bounded,
)
from patchharbor.runtime_wheel import RuntimeDataError


def read_directory_resource(root: Path, name: str, maximum: int, *,
                            read_file=None) -> bytes:
    """No-follow bounded file read, retaining each owned parent identity."""
    if read_file is None:
        read_file = read_stable_regular_file_bounded
    parts = name.split('/')
    if any(not part or part in {'.', '..'} or '\\' in part for part in parts):
        raise RuntimeDataError('unsafe resource path')
    path, parents = root, []
    for segment in (None, *parts[:-1]):
        if segment is not None:
            path = path / segment
        kind = path_kind(path)
        if kind is PathKind.MISSING:
            raise FileNotFoundError(path)
        if kind is not PathKind.DIRECTORY:
            raise RuntimeDataError('linked or special runtime resource')
        info = path.stat(follow_symlinks=False)
        parents.append((path, info.st_dev, info.st_ino))
    path = path / parts[-1]
    if path_kind(path) is PathKind.MISSING:
        raise FileNotFoundError(path)
    raw = read_file(path, max_bytes=maximum).content
    for parent, device, inode in parents:
        info = parent.stat(follow_symlinks=False)
        if path_kind(parent) is not PathKind.DIRECTORY or (info.st_dev, info.st_ino) != (device, inode):
            raise RuntimeDataError('runtime resource directory changed')
    return raw


@dataclass(frozen=True, slots=True)
class DirectoryResources:
    root: Path

    def read(self, name: str, maximum: int) -> bytes:
        return read_directory_resource(self.root, name, maximum)


@dataclass(frozen=True, slots=True)
class ZipResources:
    archive: Path

    def capture(self, maximum: int) -> bytes:
        # The installed/imported artifact is already trusted as executable code;
        # the provider still verifies its entire finite profile as current data.
        if path_kind(self.archive) is PathKind.MISSING:
            raise FileNotFoundError(self.archive)
        return read_stable_regular_file_bounded(self.archive, max_bytes=maximum).content


def own_resources() -> DirectoryResources | ZipResources:
    """Anchor to this loaded module; never search CWD or distribution metadata."""
    if isinstance(__loader__, zipimporter):
        archive = Path(__loader__.archive)
        expected = archive / 'patchharbor' / 'runtime_sources.py'
        if not archive.is_absolute() or Path(__file__) != expected:
            raise RuntimeDataError('unexpected executing PYZ origin')
        return ZipResources(archive)
    module = Path(__file__).resolve()
    if module.name != 'runtime_sources.py' or module.parent.name != 'patchharbor':
        raise RuntimeDataError('unexpected executing distribution origin')
    return DirectoryResources(module.parent.parent)
