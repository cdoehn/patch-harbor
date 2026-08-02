"""Windows process-tree ownership based on Job Objects."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from pathlib import Path
import signal
import subprocess
import threading

from patchharbor.platform.lifecycle import ProcessTree


_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JobExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JobBasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
_KERNEL32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
_KERNEL32.CreateJobObjectW.restype = wintypes.HANDLE
_KERNEL32.SetInformationJobObject.argtypes = (
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
)
_KERNEL32.SetInformationJobObject.restype = wintypes.BOOL
_KERNEL32.AssignProcessToJobObject.argtypes = (
    wintypes.HANDLE,
    wintypes.HANDLE,
)
_KERNEL32.AssignProcessToJobObject.restype = wintypes.BOOL
_KERNEL32.QueryInformationJobObject.argtypes = (
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_void_p,
)
_KERNEL32.QueryInformationJobObject.restype = wintypes.BOOL
_KERNEL32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
_KERNEL32.TerminateJobObject.restype = wintypes.BOOL
_KERNEL32.CloseHandle.argtypes = (wintypes.HANDLE,)
_KERNEL32.CloseHandle.restype = wintypes.BOOL


def _windows_error() -> OSError:
    return ctypes.WinError(ctypes.get_last_error())


def _create_job() -> object:
    job_handle = _KERNEL32.CreateJobObjectW(None, None)
    if not job_handle:
        raise _windows_error()

    information = _JobExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = (
        _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    if not _KERNEL32.SetInformationJobObject(
        job_handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        error = _windows_error()
        _KERNEL32.CloseHandle(job_handle)
        raise error
    return job_handle


@contextmanager
def _break_interrupt() -> Iterator[None]:
    if (
        not hasattr(signal, "SIGBREAK")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGBREAK)

    def raise_keyboard_interrupt(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGBREAK, raise_keyboard_interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGBREAK, previous_handler)


class WindowsProcessTree(ProcessTree):
    """Own a Windows process tree through one kill-on-close Job Object."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        job_handle: object,
    ) -> None:
        super().__init__(process)
        self._job_handle: object | None = job_handle

    @classmethod
    def start(cls, command: list[str], *, cwd: Path) -> WindowsProcessTree:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        job_handle: object | None = None
        try:
            job_handle = _create_job()
            process_handle = wintypes.HANDLE(
                int(process._handle)  # type: ignore[attr-defined]
            )
            if not _KERNEL32.AssignProcessToJobObject(job_handle, process_handle):
                raise _windows_error()
        except BaseException:
            process.kill()
            process.wait()
            if job_handle is not None:
                _KERNEL32.CloseHandle(job_handle)
            raise
        return cls(process, job_handle)

    def _wait_root(self, *, timeout_seconds: float) -> int:
        with _break_interrupt():
            return self._process.wait(timeout=timeout_seconds)

    def _tree_has_processes(self) -> bool:
        self._process.poll()
        if self._job_handle is None:
            return self._process.poll() is None

        information = _JobBasicAccountingInformation()
        if not _KERNEL32.QueryInformationJobObject(
            self._job_handle,
            _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
            None,
        ):
            raise _windows_error()
        return bool(information.ActiveProcesses)

    def _request_stop(self) -> None:
        if not self._tree_has_processes() or self._process.poll() is not None:
            return
        try:
            self._process.send_signal(signal.CTRL_BREAK_EVENT)
        except (OSError, ValueError):
            try:
                self._process.terminate()
            except OSError:
                # The root may end between poll() and the signal. Remaining
                # descendants are still owned by the Job Object and will be
                # handled by the force-stop fallback after the grace period.
                pass

    def _force_stop(self) -> None:
        if not self._tree_has_processes():
            return
        if self._job_handle is not None:
            if not _KERNEL32.TerminateJobObject(self._job_handle, 1):
                error = _windows_error()
                if self._tree_has_processes():
                    raise error
        else:
            try:
                self._process.kill()
            except OSError:
                if self._tree_has_processes():
                    raise

    def _close_platform_resources(self) -> None:
        if self._job_handle is None:
            return
        job_handle = self._job_handle
        self._job_handle = None
        if not _KERNEL32.CloseHandle(job_handle):
            raise _windows_error()
