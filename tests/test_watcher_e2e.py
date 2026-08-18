from __future__ import annotations

from collections.abc import Callable
from io import StringIO
import json
import os
from pathlib import Path
import sys
from threading import Event, Thread
import time

import pytest

from patchharbor.watcher import run_watcher
from patchharbor.watcher_subprocess import delegate_to_apply


pytestmark = pytest.mark.e2e


def _wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 5.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def test_watcher_delegates_stable_file_to_real_apply_stub_process(
    tmp_path: Path,
) -> None:
    input_directory = tmp_path / "incoming"
    input_directory.mkdir()
    patch_path = input_directory / "patch.bin"
    patch_path.write_bytes(b"byte-exact-input\x00")

    calls_path = tmp_path / "calls.jsonl"
    stub_path = tmp_path / "apply_stub.py"
    stub_path.write_text(
        """\
import json
import os
from pathlib import Path
import sys

with Path(os.environ["PATCHHARBOR_WATCHER_TEST_CALLS"]).open(
    "a", encoding="utf-8"
) as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps({"stub": "applied", "input_path": sys.argv[-1]}))
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PATCHHARBOR_WATCHER_TEST_CALLS"] = str(calls_path)

    stop = Event()
    watcher_stdout = StringIO()
    watcher_stderr = StringIO()

    def delegate(path: Path):
        return delegate_to_apply(
            path,
            apply_command=(sys.executable, str(stub_path)),
            environment=environment,
        )

    thread = Thread(
        target=run_watcher,
        kwargs={
            "input_directory": input_directory,
            "delegate": delegate,
            "poll_interval_seconds": 0.02,
            "log_stream": watcher_stdout,
            "error_stream": watcher_stderr,
            "stop_requested": stop.is_set,
            "wait_for_stop": stop.wait,
        },
        daemon=True,
    )
    thread.start()
    try:
        _wait_until(calls_path.exists)
        _wait_until(lambda: bool(watcher_stdout.getvalue().strip()))
        time.sleep(0.08)
    finally:
        stop.set()
        thread.join(timeout=2.0)

    assert not thread.is_alive()
    calls = [
        json.loads(line)
        for line in calls_path.read_text(encoding="utf-8").splitlines()
    ]
    assert calls == [["apply", "--json", str(patch_path)]]

    records = [json.loads(line) for line in watcher_stdout.getvalue().splitlines()]
    assert len(records) == 1
    assert records[0]["input_path"] == str(patch_path)
    assert records[0]["process_exit_code"] == 0
    assert records[0]["apply_response_is_json_object"] is True
    assert records[0]["apply_result"] == {
        "stub": "applied",
        "input_path": str(patch_path),
    }
    assert records[0]["invalid_apply_response"] is None
    assert watcher_stderr.getvalue() == ""
