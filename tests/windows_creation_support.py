"""Shared windows creation fixtures and behavior probes."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


def assert_private_creation(create_private_directory, tmp_path, monkeypatch, failure, impersonated):
    import ctypes
    calls = []
    last_error = [0]
    def failed(name):
        calls.append(name)
        if failure == name:
            last_error[0] = 5
            return True
        return False
    def open_thread(handle, access, as_self, result):
        assert access == 8 and as_self is True
        if failed("thread"):
            return False
        if not impersonated:
            last_error[0] = 1008
            return False
        result._obj.value = 101
        return True
    def open_process(handle, access, result):
        if failed("token"):
            return False
        result._obj.value = 101
        return True
    def info(handle, kind, buffer, size, result):
        assert kind == 1
        if buffer is None:
            result._obj.value = 32
            if not failed("size"):
                last_error[0] = 122
            return False
        if failed("info"):
            return False
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0] = 202
        return True
    def sid(pointer, result):
        assert pointer == 202
        if failed("sid"):
            return False
        result._obj.value = "S-1-5-21-1000"
        return True
    def convert(sddl, revision, result, length):
        assert sddl == "D:P(A;OICI;FA;;;S-1-5-21-1000)(A;OICI;FA;;;BA)" and revision == 1
        if failed("convert"):
            return False
        result._obj.value = 303
        return True
    def create(path, attributes):
        assert path == str(tmp_path / "private")
        assert attributes._obj.descriptor == 303 and not attributes._obj.inherit
        return not failed("create")
    def close(value):
        calls.append("close")
        assert value.value == 101
        return True
    def free(value):
        calls.append("free")
        return None
    def current():
        return 404
    kernel = SimpleNamespace(CloseHandle=close, LocalFree=free, GetCurrentThread=current,
                             GetCurrentProcess=current, CreateDirectoryW=create)
    security = SimpleNamespace(OpenThreadToken=open_thread, OpenProcessToken=open_process,
        GetTokenInformation=info, ConvertSidToStringSidW=sid,
        ConvertStringSecurityDescriptorToSecurityDescriptorW=convert)
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kwargs:
                        kernel if name == "kernel32" else security, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: last_error[0], raising=False)
    monkeypatch.setattr(ctypes, "WinError", lambda code: PermissionError(code, "native failure"), raising=False)
    triggered = failure is not None and not (failure == "token" and impersonated)
    if triggered:
        with pytest.raises(PermissionError):
            create_private_directory(tmp_path / "private")
    else:
        create_private_directory(tmp_path / "private")
    assert calls.count("create") == (failure == "create" or not triggered)
    assert calls.count("close") == (failure not in {"thread"} and not (failure == "token" and not impersonated))
    expected_frees = (0 if triggered and failure in {"thread", "token", "size", "info", "sid"}
                      else 1 if failure == "convert" else 2)
    assert calls.count("free") == expected_frees
    if failure == "thread":
        assert "token" not in calls
