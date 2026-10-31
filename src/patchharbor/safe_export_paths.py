"""Linux descriptor-anchored operating directories for the explicit safe exporter."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat

from patchharbor.safe_export_types import SafeExportError, SafeExportErrorCode


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode))


def _open_directory(path: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open('/', flags)
    try:
        for component in path.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class BoundDirectory:
    def __init__(self, path: Path, *, _descriptor: int | None = None):
        self.path = Path(os.path.abspath(path.expanduser()))
        self.fd = -1
        try:
            self.fd = _open_directory(self.path) if _descriptor is None else _descriptor
            info = os.fstat(self.fd)
            if info.st_uid != os.getuid() or info.st_mode & 0o002:
                raise SafeExportError(SafeExportErrorCode.UNSAFE_PATH,
                                      'safe export operating directory must be owned and not world-writable')
            self.identity = _identity(info)
            if not Path('/proc/self/fd', str(self.fd)).is_dir():
                raise SafeExportError(SafeExportErrorCode.UNSUPPORTED_HOST, '/proc/self/fd is required')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def verify(self):
        try:
            current = _open_directory(self.path)
            try:
                valid = _identity(os.fstat(current)) == self.identity == _identity(os.fstat(self.fd))
            finally:
                os.close(current)
            if not valid:
                raise OSError('directory identity changed')
        except OSError as exc:
            raise SafeExportError(SafeExportErrorCode.STALE, 'safe export directory changed') from exc

    def io_path(self, name: str) -> Path:
        if not name or Path(name).name != name or name in ('.', '..'):
            raise ValueError('one owned filename is required')
        return Path('/proc/self/fd', str(self.fd), name)

    def create(self, name: str) -> int:
        self.io_path(name)
        self.verify()
        return os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                       0o600, dir_fd=self.fd)

    def create_directory(self, name: str) -> BoundDirectory:
        self.io_path(name)
        self.verify()
        os.mkdir(name, mode=0o700, dir_fd=self.fd)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=self.fd)
        child = BoundDirectory(self.path / name, _descriptor=fd)
        try:
            self.verify()
            child.verify()
            return child
        except BaseException:
            child.close()
            raise

    def current_path(self) -> Path | None:
        """Report a relocated owned directory only after verifying its identity."""
        try:
            candidate = Path(os.readlink('/proc/self/fd/' + str(self.fd)))
            fd = _open_directory(candidate)
            try:
                return candidate if _identity(os.fstat(fd)) == self.identity else None
            finally:
                os.close(fd)
        except OSError:
            return None

    def remove_owned(self, name: str, identity: os.stat_result):
        try:
            current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISREG(current.st_mode) or not os.path.samestat(current, identity):
            raise SafeExportError(SafeExportErrorCode.CLEANUP, 'owned temporary file identity changed')
        os.unlink(name, dir_fd=self.fd)

    def publish(self, source_fd: int, final_name: str):
        self.io_path(final_name)
        self.verify()
        # linkat follows this kernel-owned descriptor reference, not a mutable
        # temporary filename. Destination creation is atomic and exclusive.
        os.link('/proc/self/fd/' + str(source_fd), final_name,
                dst_dir_fd=self.fd, follow_symlinks=True)


@contextmanager
def bound_lock(directory: BoundDirectory, name: str, *, busy_error):
    from patchharbor.platform.locking import _try_acquire, _release
    directory.io_path(name)
    directory.verify()
    fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                 0o600, dir_fd=directory.fd)
    acquired = False
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.getuid() or info.st_mode & 0o002):
            raise SafeExportError(SafeExportErrorCode.UNSAFE_PATH, 'invalid existing lock file')
        acquired = _try_acquire(fd)
        if not acquired:
            raise busy_error
        def verify():
            directory.verify()
            current = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
            if not os.path.samestat(current, info) or current.st_nlink != 1:
                raise SafeExportError(SafeExportErrorCode.STALE, 'safe export lock changed')
        verify()
        yield verify
    finally:
        try:
            if acquired:
                _release(fd)
        finally:
            os.close(fd)
