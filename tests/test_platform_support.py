"""Functional CLI tests must not inherit an unrelated subprocess deadline."""

from __future__ import annotations

import inspect
import subprocess

import pytest

from tests import platform_support as support


@pytest.mark.parametrize("helper", [support.run_cli, support.run_cli_bytes, support.run_patchharbor])
def test_functional_cli_helpers_have_no_default_deadline(helper):
    assert inspect.signature(helper).parameters["timeout_seconds"].default is None


@pytest.mark.parametrize("helper", ["text", "bytes", "file"])
@pytest.mark.parametrize("deadline", [None, 0.25])
def test_cli_helpers_preserve_default_or_explicit_subprocess_timeout(tmp_path, monkeypatch, helper, deadline):
    calls = []

    def completed(command, **kwargs):
        calls.append((command, kwargs))
        # Simulates a slow CLI without adding a wall-clock sleep to the suite.
        # With the old default of 20 the default-deadline assertions fail.
        if kwargs["timeout"] is not None:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        output = b"ok" if helper == "bytes" else "ok"
        return subprocess.CompletedProcess(command, 0, output, output[:0])

    monkeypatch.setattr(support.subprocess, "run", completed)
    arguments = {} if deadline is None else {"timeout_seconds": deadline}

    def run():
        if helper == "text":
            return support.run_cli(tmp_path, "apply", **arguments)
        if helper == "bytes":
            return support.run_cli_bytes(tmp_path, "fs", "run", "-", input_bytes=b"script", **arguments)
        return support.run_patchharbor(tmp_path / "run.sh", cwd=tmp_path, **arguments)

    if deadline is None:
        assert run().returncode == 0
    else:
        with pytest.raises(subprocess.TimeoutExpired) as error:
            run()
        assert error.value.timeout == deadline
    assert len(calls) == 1
    assert calls[0][1]["timeout"] is deadline
