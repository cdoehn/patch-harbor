"""Pinned output ownership and exclusive publication of a validated pack file.

Linux links the open file via procfs/linkat; Windows renames by the pinned file
handle with ReplaceIfExists=False. Neither primitive selects a new source inode
by its temporary pathname. Existing Result replace/retry policy is separate.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
import ctypes
import errno
import os
from pathlib import Path
import secrets
import stat
import sys

from patchharbor.platform.directories import open_directory_nofollow, pin_windows_directory
from patchharbor.platform.file_handles import open_regular_nofollow
from patchharbor.platform.filesystem import (
    FileChangedDuringRead, require_file_identity, sync_directory_best_effort,
    read_stable_regular_file_with_sha256,
    _same_open_file_state,
)
from patchharbor.platform.runtime import is_windows


@dataclass(frozen=True, slots=True)
class OutputDirectory:
    path: Path
    identity: os.stat_result
    descriptor: int | None
    cleanup_warnings: list[str]=field(default_factory=list,compare=False)

    def revalidate(self) -> None:
        observed=self.path.lstat()
        if (not stat.S_ISDIR(observed.st_mode)
                or getattr(observed,'st_file_attributes',0)&0x400
                or not os.path.samestat(observed,self.identity)
                or self.path.resolve(strict=True)!=self.path):
            raise OSError('pack output directory identity changed')
        if self.descriptor is not None and not os.path.samestat(os.fstat(self.descriptor),self.identity):
            raise OSError('pack output directory handle changed')

    def child_stat(self,name):
        return ((self.path/name).lstat() if self.descriptor is None
                else os.stat(name,dir_fd=self.descriptor,follow_symlinks=False))

    def owned_path(self,name) -> Path:
        # Common validators receive an anchored directory path on Linux. They
        # must not resolve the final name or discard the expected file identity.
        return self.path/name if self.descriptor is None else Path('/proc/self/fd')/str(self.descriptor)/name

    def reserve(self):
        self.revalidate()
        name='.patchharbor-pack-'+secrets.token_hex(16)+'.partial'
        flags=os.O_RDWR|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)
        fd=(os.open(self.path/name,flags,0o600) if self.descriptor is None
            else os.open(name,flags,0o600,dir_fd=self.descriptor))
        owned=OwnedPackFile(self,name,os.fstat(fd))
        try:
            os.set_inheritable(fd,False)
            return owned,os.fdopen(fd,'w+b')
        except BaseException as exc:
            try:
                os.close(fd)
            except (OSError,KeyboardInterrupt) as cleanup:
                exc.add_note('cannot close reserved pack handle: '+str(cleanup))
            for warning in owned.cleanup():
                exc.add_note(warning)
            raise


@contextmanager
def open_output_directory(root: Path):
    if not root.is_absolute() or root.resolve(strict=True)!=root:
        raise OSError('pack output directory must be physically resolved')
    initial=root.lstat()
    if not stat.S_ISDIR(initial.st_mode) or getattr(initial,'st_file_attributes',0)&0x400:
        raise OSError('pack output requires a non-link directory')
    warnings=[]
    def close_handle(close,handle):
        try:
            close(handle)
        except (OSError,KeyboardInterrupt) as exc:
            warnings.append(f'cannot close own pack output directory handle for {root}: {exc}')
    with ExitStack() as stack:
        if is_windows():
            for parent in reversed((root,*root.parents)):
                handle,close=pin_windows_directory(parent)
                stack.callback(close_handle,close,handle)
            descriptor=None
        elif sys.platform.startswith('linux'):
            descriptor=open_directory_nofollow(root)
            stack.callback(close_handle,os.close,descriptor)
        else:
            raise OSError(errno.ENOTSUP,'safe pack publication is unavailable on this platform')
        location=OutputDirectory(root,initial,descriptor,warnings)
        location.revalidate()
        yield location


def _rename_windows_handle(descriptor: int,target: Path) -> None:
    import msvcrt
    from ctypes import wintypes

    class RenameInfo(ctypes.Structure):
        _fields_=[('flags',wintypes.DWORD),('root',wintypes.HANDLE),
                  ('length',wintypes.DWORD),('name',wintypes.WCHAR*1)]

    encoded=str(target).encode('utf-16-le')
    buffer=ctypes.create_string_buffer(max(ctypes.sizeof(RenameInfo),RenameInfo.name.offset+len(encoded)+2))
    info=RenameInfo.from_buffer(buffer)
    info.flags=0  # ReplaceIfExists=False; no POSIX replace semantics.
    info.root=None
    info.length=len(encoded)
    ctypes.memmove(ctypes.addressof(buffer)+RenameInfo.name.offset,encoded,len(encoded))
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    rename=kernel.SetFileInformationByHandle
    rename.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    rename.restype=wintypes.BOOL
    if not rename(msvcrt.get_osfhandle(descriptor),3,buffer,len(buffer)):
        raise ctypes.WinError(ctypes.get_last_error())


@dataclass(slots=True)
class OwnedPackFile:
    directory: OutputDirectory
    name: str
    identity: os.stat_result
    descriptor: int | None=None
    published: bool=False
    moved: bool=False
    verified_state: os.stat_result | None=None

    @property
    def path(self) -> Path:
        return self.directory.owned_path(self.name)

    @property
    def display_path(self) -> Path:
        return self.directory.path/self.name

    def require_owned(self) -> None:
        try:
            self.directory.revalidate()
            observed=self.directory.child_stat(self.name)
            require_file_identity(observed,self.identity)
            if observed.st_nlink!=1:
                raise FileChangedDuringRead('pack temporary file acquired a foreign hardlink')
            if self.descriptor is not None:
                opened=os.fstat(self.descriptor)
                require_file_identity(opened,self.identity)
                if self.verified_state is not None and not _same_open_file_state(self.verified_state,opened):
                    raise FileChangedDuringRead('pack output metadata changed after validation')
        except OSError as exc:
            raise FileChangedDuringRead('pack output ownership changed') from exc

    def pin(self) -> None:
        self.require_owned()
        self.descriptor=open_regular_nofollow(self.path,writable=is_windows(),publication=True)
        self.require_owned()

    def sync(self) -> None:
        os.fsync(self.descriptor)
        sync_directory_best_effort(self.directory.path)

    def verify_hash(self,expected: str,maximum: int) -> None:
        self.require_owned()
        before=os.fstat(self.descriptor)
        captured=read_stable_regular_file_with_sha256(
            self.path,retained_content_limit=1,max_bytes=maximum,
            expected_identity=self.identity,allow_path_identity_fallback=False,
        )
        if captured.sha256!=expected:
            raise FileChangedDuringRead('pack output changed after complete validation')
        after=os.fstat(self.descriptor)
        if not _same_open_file_state(before,after):
            raise FileChangedDuringRead('pack output changed during final hash verification')
        self.verified_state=after
        self.require_owned()

    def publish(self,target_name: str) -> None:
        if self.descriptor is None or self.published:
            raise RuntimeError('pack output is not pinned for publication')
        if not target_name or target_name in ('.','..') or any(c in target_name for c in '/\\\0'):
            raise ValueError('publication requires one filename')
        self.require_owned()
        if self.directory.descriptor is None:
            _rename_windows_handle(self.descriptor,self.directory.path/target_name)
            self.moved=True
        else:
            # A directory descriptor forces linkat with AT_SYMLINK_FOLLOW.
            # procfs selects this open inode, not a swappable temporary name.
            os.link('/proc/self/fd/'+str(self.descriptor),target_name,
                    dst_dir_fd=self.directory.descriptor,follow_symlinks=True)
        self.published=True

    def cleanup(self) -> tuple[str, ...]:
        warnings=[]
        if self.descriptor is not None:
            descriptor,self.descriptor=self.descriptor,None
            try:
                os.close(descriptor)
            except (OSError,KeyboardInterrupt) as exc:
                warnings.append(f'cannot close own pack handle for {self.display_path}: {exc}')
        if not self.moved:
            try:
                observed=self.directory.child_stat(self.name)
                require_file_identity(observed,self.identity)
                if self.directory.descriptor is None:
                    self.display_path.unlink()
                else:
                    os.unlink(self.name,dir_fd=self.directory.descriptor)
            except FileNotFoundError:
                pass
            except (OSError,KeyboardInterrupt,FileChangedDuringRead) as exc:
                warnings.append(f'cannot remove own temporary pack path {self.display_path}: {exc}')
        return tuple(warnings)
