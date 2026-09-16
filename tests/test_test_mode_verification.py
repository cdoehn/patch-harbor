"""Mode-verifier behavior and evidence contracts, not console presentation."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from tools import verify_test_modes as modes
from tools import test_runner
from tests.test_test_evidence import example, make_suite, invoke


def test_matrix_retains_serial_two_four_auto_and_multiple_hash_seeds():
    matrix = modes.verification_matrix()
    assert matrix[0] == ("0", "0")
    assert {workers for workers, _ in matrix} == {"0", "2", "4", "auto"}
    assert len({seed for _, seed in matrix}) >= 3
    assert len(matrix) == len(set(matrix))


def test_verification_uses_fresh_reports_and_checks_every_mode(tmp_path, monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        report = example(); report["run_id"] = str(len(calls))
        Path(command[command.index("--report") + 1]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(modes.subprocess, "run", run)
    assert modes.verify(tmp_path / "results", ["tests"], python="python-for-test") == 0
    assert len(calls) == len(modes.verification_matrix())
    for command, options in calls:
        assert command[0] == "python-for-test"
        assert options["env"]["PYTEST_ADDOPTS"] == ""
        assert "timeout" not in options and "shell" not in options
    assert "--serial" in calls[0][0]
    assert "--reference" not in calls[0][0]
    assert all("--reference" in command for command, _ in calls[1:])


@pytest.mark.parametrize("failure", ["exit", "missing_report", "different_result", "different_binding", "collection_only"])
def test_failure_stops_without_accepting_later_modes(tmp_path, monkeypatch, failure):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        report = example()
        if len(calls) == 2:
            if failure == "exit": return subprocess.CompletedProcess(command, 17)
            if failure == "missing_report": return subprocess.CompletedProcess(command, 0)
            if failure == "different_result": report["reports"][1].update(outcome="skipped", reason="unexpected")
            if failure == "different_binding": report["binding"] = {"source_sha256": "other"}
            if failure == "collection_only": report["mode"] = "collection"
        Path(command[command.index("--report") + 1]).write_text(json.dumps(report))
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(modes.subprocess, "run", run)
    status = modes.main(["--outdir", str(tmp_path / "results")])
    assert status != 0
    assert len(calls) == 2
    assert (tmp_path / "results" / "00-workers-0-seed-0.json").is_file()


def test_stale_output_directory_is_not_reused(tmp_path, monkeypatch):
    def run(*args, **kwargs): raise AssertionError("must not start")
    monkeypatch.setattr(modes.subprocess, "run", run)
    assert modes.main(["--outdir", str(tmp_path)]) != 0


@pytest.mark.parametrize("argument", ["--max-worker-restart=2", "--ph-report=other.json", "--ph-reference=old.json"])
def test_passthrough_cannot_replace_restart_or_evidence_policy(argument):
    with pytest.raises(SystemExit) as error:
        test_runner.prepare_invocation(["--serial", "--", argument], environment={})
    assert error.value.code == 2


def test_real_auto_uses_xdist_resource_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTEST_XDIST_AUTO_NUM_WORKERS", "2")
    suite = make_suite(tmp_path, "import pytest\n@pytest.mark.parametrize('i',range(5))\ndef test_ok(i): pass\n")
    report = tmp_path / "auto.json"
    result = invoke(suite, report, workers="auto")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(report.read_text())["expected_workers"] == 2
