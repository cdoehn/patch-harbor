"""Older Windows primitives also protect the standalone pre-import bootstrap."""
import ctypes
import errno
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
from time import sleep

import pytest

from scripts import pyz_bootstrap as bootstrap
from tests.windows_creation_support import assert_private_creation
from tests.pyz_variant_support import variant
from tests.pyz_variant_support import result_file


@pytest.mark.parametrize('fault', [None, 'change', 'capture_change', 'missing_primitive', 'stat_disagreement'])
def test_old_windows_bootstrap_uses_native_change_time_and_closes_owned_handle(tmp_path, monkeypatch, fault):
    path = tmp_path / 'input'
    path.write_bytes(b'unchanged')
    original = path.stat()
    original_fstat, original_close = os.fstat, os.close
    opened = []
    original_open = os.open
    def open_file(*a, **k):
        fd = original_open(*a, **k); opened.append(fd); return fd
    def metadata(info):
        return SimpleNamespace(**{k: getattr(info, k) for k in ('st_dev','st_ino','st_size','st_mode')},
                               st_ctime_ns=100, st_mtime_ns=200, st_file_attributes=32)
    class Input:
        def __fspath__(self): return str(path)
        def lstat(self): return metadata(original)
    monkeypatch.setattr(bootstrap, '_WINDOWS', True)
    monkeypatch.setattr(bootstrap, '_legacy_windows', lambda: True)
    # Keep the platform's genuine file open; substitute only observed legacy times.
    if os.name == 'nt':
        native_open = bootstrap._windows_open
        def track_windows(path):
            fd = native_open(path); opened.append(fd); return fd
        monkeypatch.setattr(bootstrap, '_windows_open', track_windows)
    else:
        monkeypatch.setattr(bootstrap.os, 'open', open_file)
    monkeypatch.setattr(bootstrap.os, 'fstat', lambda fd: metadata(original_fstat(fd)))
    calls = []
    def times(fd):
        calls.append(fd)
        if fault == 'missing_primitive': raise OSError(errno.ENOTSUP, 'unsupported native metadata')
        creation = 101 if fault == 'stat_disagreement' else 100
        change = 301 if (fault == 'change' and len(calls) > 2) or (fault == 'capture_change' and len(calls) > 1) else 300
        return creation, 200, change, 32
    monkeypatch.setattr(bootstrap, '_windows_times', times)
    if fault is None:
        assert bootstrap._capture(Input(), 100) == b'unchanged'
    else:
        with pytest.raises((OSError, ValueError)): bootstrap._capture(Input(), 100)
    assert len(opened) == 1
    with pytest.raises(OSError): original_fstat(opened[0])
    assert path.read_bytes() == b'unchanged'


@pytest.mark.parametrize('fault', ['open', 'query', 'reparse', 'directory', 'crt', None])
def test_native_bootstrap_open_never_follows_reparse_and_transfers_ownership_once(monkeypatch, fault):
    calls = []
    def create(path, access, share, security, disposition, flags, template):
        assert (path, access, share, disposition, flags) == ('input', 0x80000000, 7, 3, 0x00200000)
        calls.append('create')
        return ctypes.c_void_p(-1).value if fault == 'open' else 101
    def query(handle, kind, output, size):
        assert handle == 101 and kind == 9
        calls.append('query')
        output._obj.attributes = 0x400 if fault == 'reparse' else 0x10 if fault == 'directory' else 32
        return fault != 'query'
    def close(handle):
        assert handle == 101; calls.append('close'); return True
    def convert(handle, flags):
        assert handle == 101; calls.append('crt')
        if fault == 'crt': raise OSError(errno.EMFILE, 'descriptor unavailable')
        return 202
    kernel = SimpleNamespace(CreateFileW=create, GetFileInformationByHandleEx=query, CloseHandle=close)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *a, **k: kernel, raising=False)
    monkeypatch.setattr(ctypes, 'get_last_error', lambda: 5, raising=False)
    monkeypatch.setattr(ctypes, 'WinError', lambda code: OSError(code, 'native error'), raising=False)
    monkeypatch.setattr(os, 'O_BINARY', getattr(os, 'O_BINARY', 0), raising=False)
    monkeypatch.setitem(sys.modules, 'msvcrt', SimpleNamespace(open_osfhandle=convert))
    if fault is None:
        assert bootstrap._windows_open(Path('input')) == 202
    else:
        with pytest.raises((OSError, ValueError)): bootstrap._windows_open(Path('input'))
    assert calls.count('close') == (fault is not None and fault != 'open')
    assert calls.count('crt') == (fault in {None, 'crt'})


@pytest.mark.parametrize('failure', [None, 'thread', 'token', 'size', 'info', 'sid', 'convert', 'create'])
@pytest.mark.parametrize('impersonated', [False, True])
def test_bootstrap_atomic_dacl_keeps_core_failure_and_cleanup_contract(tmp_path, monkeypatch, failure, impersonated):
    assert_private_creation(bootstrap._windows_create_private_directory,
                            tmp_path, monkeypatch, failure, impersonated)


def test_fdopen_failure_closes_bootstrap_descriptor(tmp_path, monkeypatch):
    path = tmp_path / 'input'; path.write_bytes(b'unchanged')
    fdopen, opened = os.fdopen, []
    def fail(fd, *a, **k):
        opened.append(fd)
        raise OSError(errno.EMFILE, 'stream unavailable')
    monkeypatch.setattr(bootstrap.os, 'fdopen', fail)
    with pytest.raises(OSError): bootstrap._capture(path, 100)
    assert len(opened) == 1
    with pytest.raises(OSError): os.fstat(opened[0])
    assert path.read_bytes() == b'unchanged'


@pytest.mark.parametrize('tag', [0, 0xA0000003, 0xA000000C, 0x80000000])
def test_bootstrap_rejects_reparse_metadata_without_pathlib_junction(tmp_path, monkeypatch, tag):
    path = tmp_path / 'input'; path.write_bytes(b'untouched')
    class Input:
        def __fspath__(self): return str(path)
        def lstat(self): return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400, st_reparse_tag=tag)
    def forbidden(*a, **k): pytest.fail('reparse input was opened')
    monkeypatch.setattr(bootstrap.os, 'open', forbidden)
    monkeypatch.setattr(bootstrap, '_windows_open', forbidden)
    with pytest.raises(ValueError): bootstrap._capture(Input(), 100)
    assert path.read_bytes() == b'untouched'


@pytest.mark.skipif(os.name == 'nt', reason='POSIX symlink parent; native junction covered separately')
def test_bootstrap_refuses_redirected_input_and_workspace_parents(tmp_path):
    real = tmp_path / 'real'; real.mkdir()
    (real / 'input').write_bytes(b'untouched')
    link = tmp_path / 'linked'; link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError): bootstrap._capture(link / 'input', 100)
    reference, _, _ = result_file(tmp_path, variant('>=3.10'))
    import hashlib
    assessment = bootstrap.assess(reference, trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
    with pytest.raises(ValueError): bootstrap.prepare(assessment, link / 'private')
    assert not (real / 'private').exists()


@pytest.mark.platform
@pytest.mark.skipif(os.name != 'nt', reason='native Windows metadata and DACLs')
def test_native_bootstrap_detects_same_size_restored_mtime_change(tmp_path, monkeypatch):
    path = tmp_path / 'input'; path.write_bytes(b'original')
    original = path.stat(); fdopen = os.fdopen; descriptors = []; observations = []
    monkeypatch.setattr(bootstrap, '_legacy_windows', lambda: True)
    class Observed:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): self.stream.close()
        def fileno(self): return self.stream.fileno()
        def read(self, maximum):
            data = self.stream.read(maximum)
            before = bootstrap._windows_times(self.fileno())
            # Keep distinct native clock ticks; no assumption that a same-tick
            # rewrite must change a timestamp at the filesystem's resolution.
            sleep(0.05)
            with path.open('wb') as writer:
                writer.write(b'modified'); writer.flush(); os.fsync(writer.fileno())
            os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
            after = bootstrap._windows_times(self.fileno())
            observations.append((before, after))
            assert before[2] != after[2], ('native ChangeTime did not advance', observations)
            return data
    def observe(fd, *args, **kwargs):
        descriptors.append(fd)
        return Observed(fdopen(fd, *args, **kwargs))
    monkeypatch.setattr(bootstrap.os, 'fdopen', observe)
    with pytest.raises(ValueError): bootstrap._capture(path, 100)
    assert len(observations) == 1
    before, after = observations[0]
    assert before[:2] == after[:2] and before[2] != after[2]
    assert path.read_bytes() == b'modified' and path.stat().st_mtime_ns == original.st_mtime_ns
    assert len(descriptors) == 1 and os.path.samestat(original, path.stat())
    with pytest.raises(OSError): os.fstat(descriptors[0])


@pytest.mark.platform
@pytest.mark.skipif(os.name != 'nt', reason='native Windows junction')
def test_native_bootstrap_rejects_junction_parent_without_pathlib_api(tmp_path, monkeypatch):
    real = tmp_path / 'real'; real.mkdir(); (real / 'input').write_bytes(b'keep')
    link = tmp_path / 'junction'
    result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(real)],
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    try:
        monkeypatch.delattr(Path, 'is_junction', raising=False)
        with pytest.raises(ValueError): bootstrap._capture(link / 'input', 100)
    finally:
        link.rmdir()
    assert (real / 'input').read_bytes() == b'keep'


@pytest.mark.platform
@pytest.mark.skipif(os.name != 'nt', reason='native Windows protected workspace DACL')
def test_native_bootstrap_prepares_private_inheriting_dacl(tmp_path):
    import hashlib
    from tests.windows_private_support import assert_private_dacl
    reference, _, _ = result_file(tmp_path, variant('>=3.10'))
    assessment = bootstrap.assess(reference, trusted_source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
    prepared = bootstrap.prepare(assessment, tmp_path / 'private')
    assert_private_dacl(prepared.path.parent, prepared.path, tmp_path)
    with pytest.raises(FileExistsError): bootstrap.prepare(assessment, prepared.path.parent)
    assert prepared.path.read_bytes() == assessment.pyz_bytes
