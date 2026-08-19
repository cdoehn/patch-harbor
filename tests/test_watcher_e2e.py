from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import sys

import pytest

from patchharbor.watcher import run_watcher
from patchharbor.watcher_subprocess import delegate_to_apply


pytestmark = pytest.mark.e2e


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

    stop_requested = False
    completed_poll_cycles = 0
    watcher_stdout = StringIO()
    watcher_stderr = StringIO()

    def delegate(path: Path):
        return delegate_to_apply(
            path,
            apply_command=(sys.executable, str(stub_path)),
            environment=environment,
        )

    def complete_poll_cycle(_timeout_seconds: float) -> None:
        nonlocal completed_poll_cycles, stop_requested
        completed_poll_cycles += 1
        stop_requested = completed_poll_cycles == 2

    run_watcher(
        input_directory,
        delegate=delegate,
        poll_interval_seconds=1.0,
        log_stream=watcher_stdout,
        error_stream=watcher_stderr,
        stop_requested=lambda: stop_requested,
        wait_between_polls=complete_poll_cycle,
    )

    assert completed_poll_cycles == 2
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
