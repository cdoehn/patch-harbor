"""Scoped terminal input for the monitor; no optional runtime dependency."""
from __future__ import annotations

from contextlib import contextmanager
import os
import shutil
import time


@contextmanager
def terminal_mode(stdin, stdout):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        handle = kernel.GetStdHandle(-11)
        previous = wintypes.DWORD()
        if not kernel.GetConsoleMode(handle, ctypes.byref(previous)) or not kernel.SetConsoleMode(handle, previous.value | 4):
            raise OSError('terminal does not support virtual terminal output; use --once')
        restore = lambda: kernel.SetConsoleMode(handle, previous.value)
    else:
        import termios
        import tty
        fd = stdin.fileno()
        previous = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, previous)
    try:
        stdout.write('\x1b[?1049h\x1b[?25l')
        stdout.flush()
        yield
    finally:
        try:
            stdout.write('\x1b[0m\x1b[?25h\x1b[?1049l')
            stdout.flush()
        finally:
            restore()


def size():
    return shutil.get_terminal_size((100, 30))


def read_key(stdin, wait=0.2):
    if os.name == 'nt':
        import msvcrt
        deadline = time.monotonic() + wait
        while not msvcrt.kbhit():
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)
        key = msvcrt.getwch()
        if key in ('\x00', '\xe0'):
            return {'H': 'up', 'P': 'down', 'I': 'pageup', 'Q': 'pagedown'}.get(msvcrt.getwch())
        return key
    import select
    if not select.select([stdin], [], [], wait)[0]:
        return None
    key = os.read(stdin.fileno(), 1)
    if key == b'':
        return 'q'
    if key == b'\x1b':
        while select.select([stdin], [], [], 0.015)[0] and len(key) < 8:
            key += os.read(stdin.fileno(), 1)
        return {b'\x1b[A': 'up', b'\x1b[B': 'down', b'\x1b[5~': 'pageup', b'\x1b[6~': 'pagedown'}.get(key, '\x1b')
    length = 1 if key[0] < 128 else 2 if key[0] < 224 else 3 if key[0] < 240 else 4
    while len(key) < length and select.select([stdin], [], [], 0.05)[0]:
        key += os.read(stdin.fileno(), 1)
    return key.decode('utf-8', errors='replace')
