"""Test-only Python process-family guard for real offline bootstrap commands."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys


def main():
    log, *arguments = sys.argv[1:]
    runner = str(Path(__file__).resolve())
    original = subprocess.Popen

    def guarded_child(command, *args, **kwargs):
        if not isinstance(command, (list, tuple)) or not Path(command[0]).name.lower().startswith("python"):
            # pip optionally probes lsb_release/uname. Model those unavailable;
            # do not execute an unguarded process merely for platform metadata.
            raise FileNotFoundError("non-Python subprocess denied by bootstrap test guard")
        return original([command[0], "-I", "-B", runner, log, *command[1:]], *args, **kwargs)

    def deny_network(event, arguments):
        if event in {"socket.__new__", "socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
            raise RuntimeError("network denied by bootstrap test guard")

    subprocess.Popen = guarded_child
    sys.addaudithook(deny_network)
    try:
        socket.socket()
    except RuntimeError:
        with Path(log).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"python": sys.executable, "network_denied": True}) + "\n")
    else:
        raise AssertionError("network guard ineffective")
    while arguments and arguments[0] in {"-I", "-B"}:
        arguments.pop(0)
    if arguments[0] == "-m":
        module = arguments[1]
        sys.argv = [module, *arguments[2:]]
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    elif arguments[0] == "-c":
        code = arguments[1]
        sys.argv = ["-c", *arguments[2:]]
        exec(compile(code, "<guarded-bootstrap-command>", "exec"), {"__name__": "__main__"})
    else:
        script, *tail = arguments
        sys.argv = [script, *tail]
        runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
