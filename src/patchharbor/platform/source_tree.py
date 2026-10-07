"""Read-only traversal anchored to non-link directory handles.

POSIX accesses children relative to open directory descriptors. Windows pins
the entire ancestor chain against replacement and rejects reparse points.
These operations never create directories or modify the captured tree.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Iterator

from patchharbor.platform.directories import open_directory_nofollow, pin_windows_directory
from patchharbor.platform.file_handles import open_regular_nofollow
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, FileReadLimitExceeded, UnsupportedFileTypeError,
    _same_open_file_state, _same_path_and_open_file_state,
)
from patchharbor.platform.runtime import is_windows


def metadata_signature(metadata: os.stat_result) -> tuple[int, ...]:
    """Compare observations of the same kind; access times are not mutations."""
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink,
            metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns,
            getattr(metadata, 'st_file_attributes', 0))


def _name(name: str) -> None:
    if not name or name in ('.', '..') or any(c in name for c in '/\\\0'):
        raise ValueError('a direct child name is required')


def _plain(metadata: os.stat_result, *, directory: bool) -> None:
    permitted = stat.S_ISDIR if directory else stat.S_ISREG
    if not permitted(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
        raise UnsupportedFileTypeError('non-link directory or regular file required')
    if not directory and metadata.st_nlink > 1:
        raise UnsupportedFileTypeError('source hardlinks are not supported')


@dataclass(frozen=True)
class SourceFile:
    content: bytes
    descriptor_metadata: os.stat_result


@dataclass(frozen=True)
class SourceDirectory:
    path: Path
    metadata: os.stat_result
    descriptor: int | None

    def child_stat(self, name: str) -> os.stat_result:
        _name(name)
        return ((self.path/name).lstat() if self.descriptor is None
                else os.stat(name, dir_fd=self.descriptor, follow_symlinks=False))

    @contextmanager
    def entries(self):
        with os.scandir(self.path if self.descriptor is None else self.descriptor) as entries:
            yield entries

    def revalidate(self) -> None:
        current=self.path.lstat()
        _plain(current, directory=True)
        if metadata_signature(current) != metadata_signature(self.metadata):
            raise FileChangedDuringRead('source-directory-changed')
        if self.descriptor is not None and not os.path.samestat(os.fstat(self.descriptor), current):
            raise FileChangedDuringRead('source-directory-replaced')

    @contextmanager
    def child(self, name: str, expected: os.stat_result) -> Iterator[SourceDirectory]:
        _name(name)
        current=self.child_stat(name)
        _plain(current, directory=True)
        if metadata_signature(current) != metadata_signature(expected):
            raise FileChangedDuringRead('source-directory-changed')
        with ExitStack() as stack:
            path=self.path/name
            if self.descriptor is None:
                handle, close=pin_windows_directory(path)
                stack.callback(close,handle)
                opened=path.lstat()
                descriptor=None
            else:
                descriptor=open_directory_nofollow(Path(name), parent_fd=self.descriptor)
                stack.callback(os.close,descriptor)
                opened=os.fstat(descriptor)
            _plain(opened,directory=True)
            if metadata_signature(opened) != metadata_signature(expected):
                raise FileChangedDuringRead('source-directory-open-changed')
            directory=SourceDirectory(path,opened,descriptor)
            directory.revalidate()
            yield directory
            directory.revalidate()

    @contextmanager
    def open_file(self, name: str, expected: os.stat_result):
        """Pin a regular file and keep path/descriptor observations separate."""
        initial=self.child_stat(name)
        _plain(initial,directory=False)
        if metadata_signature(initial) != metadata_signature(expected):
            raise FileChangedDuringRead('source-file-changed-since-scan')
        path=self.path/name if self.descriptor is None else Path(name)
        descriptor=open_regular_nofollow(path,parent_fd=self.descriptor)
        try:
            opened=os.fstat(descriptor)
            _plain(opened,directory=False)
            if not _same_path_and_open_file_state(initial,opened,allow_path_identity_fallback=False):
                raise FileChangedDuringRead('source-file-open-changed')
            current=self.child_stat(name)
            _plain(current,directory=False)
            if metadata_signature(current)!=metadata_signature(initial):
                raise FileChangedDuringRead('source-file-path-changed')
            yield descriptor, opened
            finished=os.fstat(descriptor)
            _plain(finished,directory=False)
            if not _same_open_file_state(opened,finished):
                raise FileChangedDuringRead('source-file-changed-during-read')
            final=self.child_stat(name)
            _plain(final,directory=False)
            if (metadata_signature(final)!=metadata_signature(initial)
                    or not _same_path_and_open_file_state(final,finished,allow_path_identity_fallback=False)):
                raise FileChangedDuringRead('source-file-final-state-changed')
        finally:
            os.close(descriptor)

    def revalidate_file(self, name: str, expected: os.stat_result,
                        descriptor_metadata: os.stat_result) -> None:
        # Windows descriptor ctime is change time; path ctime can be birth time.
        # Reopening metadata catches same-size writes with restored mtime after
        # capture, without a second content read or a stability retry.
        with self.open_file(name, expected) as (_, current):
            if not _same_open_file_state(descriptor_metadata, current):
                raise FileChangedDuringRead('captured-source-file-changed')

    def read_file(self, name: str, expected: os.stat_result, *, max_bytes: int) -> SourceFile:
        """Read bounded bytes through the existing non-following file adapter."""
        if expected.st_size > max_bytes:
            raise FileReadLimitExceeded('source file exceeds read budget')
        with self.open_file(name, expected) as (descriptor, opened):
            content=bytearray()
            while chunk:=os.read(descriptor,min(1024*1024,max_bytes-len(content)+1)):
                content.extend(chunk)
                if len(content)>max_bytes:
                    raise FileReadLimitExceeded('source file grew beyond read budget')
            if len(content)!=opened.st_size:
                raise FileChangedDuringRead('source-file-size-changed')
        return SourceFile(bytes(content), opened)


@contextmanager
def open_source_root(root: Path) -> Iterator[SourceDirectory]:
    """Open an already resolved, explicit content root without creating anything."""
    if not root.is_absolute():
        raise ValueError('source root must be physically resolved')
    initial=root.lstat()
    _plain(initial,directory=True)
    with ExitStack() as stack:
        if is_windows():
            for parent in reversed((root,*root.parents)):
                handle,close=pin_windows_directory(parent)
                stack.callback(close,handle)
            descriptor=None
            opened=root.lstat()
        else:
            descriptor=open_directory_nofollow(root)
            stack.callback(os.close,descriptor)
            opened=os.fstat(descriptor)
        if metadata_signature(opened)!=metadata_signature(initial):
            raise FileChangedDuringRead('source-root-open-changed')
        directory=SourceDirectory(root,opened,descriptor)
        directory.revalidate()
        yield directory
        directory.revalidate()
