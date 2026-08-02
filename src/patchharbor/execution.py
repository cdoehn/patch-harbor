"""Process execution for PatchHarbor scripts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time

from patchharbor.errors import ExitCode, PatchHarborError
from patchharbor.interpreters import (
    InterpreterSpec,
    build_interpreter_command,
    resolve_interpreter,
    select_interpreter,
)


DEFAULT_TIMEOUT_SECONDS = 300.0
FORCE_KILL_GRACE_SECONDS = 2.0
_PROCESS_TREE_POLL_SECONDS = 0.05


if os.name == "nt":  # pragma: no cover - imported and exercised on Windows CI
    import ctypes
    from ctypes import wintypes

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


@contextmanager
def _temporary_script_file(script_text: str, *, suffix: str) -> Iterator[Path]:
    """Write script text to a secure system-temp file and remove it afterwards."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-",
        suffix=suffix,
        text=True,
    )
    script_path = Path(raw_path)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(script_text)
        yield script_path
    finally:
        script_path.unlink(missing_ok=True)


def _windows_error() -> OSError:
    return ctypes.WinError(ctypes.get_last_error())


def _create_windows_job() -> object:
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


def _assign_windows_job(job_handle: object, process: subprocess.Popen[bytes]) -> None:
    process_handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
    if not _KERNEL32.AssignProcessToJobObject(job_handle, process_handle):
        raise _windows_error()


def _windows_job_has_processes(job_handle: object) -> bool:
    information = _JobBasicAccountingInformation()
    if not _KERNEL32.QueryInformationJobObject(
        job_handle,
        _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
        ctypes.byref(information),
        ctypes.sizeof(information),
        None,
    ):
        raise _windows_error()
    return bool(information.ActiveProcesses)


def _terminate_windows_job(job_handle: object) -> None:
    if not _KERNEL32.TerminateJobObject(job_handle, 1):
        raise _windows_error()


def _close_windows_job(job_handle: object) -> None:
    if not _KERNEL32.CloseHandle(job_handle):
        raise _windows_error()


def _start_process(
    command: list[str],
    *,
    cwd: Path,
) -> tuple[subprocess.Popen[bytes], object | None]:
    if os.name != "nt":
        return (
            subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            ),
            None,
        )

    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    job_handle: object | None = None
    try:
        job_handle = _create_windows_job()
        _assign_windows_job(job_handle, process)
    except BaseException:
        process.kill()
        process.wait()
        if job_handle is not None:
            _close_windows_job(job_handle)
        raise
    return process, job_handle


def _posix_group_has_processes(process: subprocess.Popen[bytes]) -> bool:
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_tree_has_processes(
    process: subprocess.Popen[bytes],
    job_handle: object | None,
) -> bool:
    process.poll()
    if os.name == "nt":
        if job_handle is None:
            return process.poll() is None
        return _windows_job_has_processes(job_handle)
    return _posix_group_has_processes(process)


def _request_process_tree_stop(
    process: subprocess.Popen[bytes],
    job_handle: object | None,
) -> None:
    if not _process_tree_has_processes(process, job_handle):
        return

    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        return

    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.CTRL_BREAK_EVENT)
    except (OSError, ValueError):
        process.terminate()


def _force_process_tree_stop(
    process: subprocess.Popen[bytes],
    job_handle: object | None,
) -> None:
    if not _process_tree_has_processes(process, job_handle):
        return

    if os.name == "nt" and job_handle is not None:
        _terminate_windows_job(job_handle)
    elif os.name == "nt":
        process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _wait_for_process_tree_exit(
    process: subprocess.Popen[bytes],
    job_handle: object | None,
    *,
    timeout_seconds: float,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while _process_tree_has_processes(process, job_handle):
        if time.monotonic() >= deadline:
            return False
        time.sleep(_PROCESS_TREE_POLL_SECONDS)
    return True


def _reap_root_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _stop_process_tree(
    process: subprocess.Popen[bytes],
    job_handle: object | None,
    *,
    graceful: bool,
) -> None:
    if graceful:
        _request_process_tree_stop(process, job_handle)
        stopped = _wait_for_process_tree_exit(
            process,
            job_handle,
            timeout_seconds=FORCE_KILL_GRACE_SECONDS,
        )
    else:
        stopped = not _process_tree_has_processes(process, job_handle)

    if not stopped:
        _force_process_tree_stop(process, job_handle)
        stopped = _wait_for_process_tree_exit(
            process,
            job_handle,
            timeout_seconds=1.0,
        )
    if not stopped:
        raise OSError("script process tree did not terminate")
    _reap_root_process(process)


@contextmanager
def _windows_break_interrupt() -> Iterator[None]:
    if (
        os.name != "nt"
        or not hasattr(signal, "SIGBREAK")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGBREAK)

    def raise_keyboard_interrupt(
        _signum: int,
        _frame: object,
    ) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGBREAK, raise_keyboard_interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGBREAK, previous_handler)


def execute_script_text(
    script_text: str,
    *,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Stage and execute script text with a supported interpreter."""
    selected = select_interpreter(script_text)
    executable_path = resolve_interpreter(selected)

    try:
        with _temporary_script_file(
            script_text,
            suffix=selected.script_suffix,
        ) as script_path:
            return execute_script_file(
                script_path,
                interpreter=selected,
                executable_path=executable_path,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
    except OSError as exc:
        raise PatchHarborError(
            f"cannot prepare temporary script: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc


def execute_script_file(
    script_path: Path,
    *,
    interpreter: InterpreterSpec,
    executable_path: str,
    cwd: Path,
    timeout_seconds: float,
) -> int:
    """Run one staged script and own its complete process tree."""
    command = build_interpreter_command(
        interpreter,
        executable_path,
        script_path,
    )
    job_handle: object | None = None

    try:
        process, job_handle = _start_process(command, cwd=cwd)
    except OSError as exc:
        raise PatchHarborError(
            f"cannot start script interpreter: {exc}",
            ExitCode.INTERPRETER_ERROR,
        ) from exc

    try:
        try:
            with _windows_break_interrupt():
                return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            _stop_process_tree(process, job_handle, graceful=True)
            raise PatchHarborError(
                f"script timed out after {timeout_seconds:g} seconds",
                ExitCode.TIMEOUT,
            ) from exc
        except KeyboardInterrupt as exc:
            _stop_process_tree(process, job_handle, graceful=True)
            raise PatchHarborError(
                "script aborted by user",
                ExitCode.INTERRUPTED,
            ) from exc

        # A script may exit while leaving descendants behind. PatchHarbor owns
        # the complete tree and must not allow those processes to escape.
        _stop_process_tree(process, job_handle, graceful=False)
        return return_code
    except PatchHarborError:
        raise
    except OSError as exc:
        try:
            _stop_process_tree(process, job_handle, graceful=False)
        except OSError:
            pass
        raise PatchHarborError(
            f"cannot control script process tree: {exc}",
            ExitCode.EXECUTION_ERROR,
        ) from exc
    finally:
        if os.name == "nt" and job_handle is not None:
            try:
                _close_windows_job(job_handle)
            except OSError:
                pass
