"""Executable report contracts, never human-readable console or XML layout."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tools.test_evidence import EvidenceError, equivalent, validate
from tests.platform_support import PROJECT_ROOT


def example() -> dict:
    return {"format_version": 1, "run_id": "example", "binding": {"source_sha256": "a"},
            "exitstatus": 0, "expected_workers": 0, "collections": {"serial": ["test_a.py::test_a"]},
            "collection_reports": [], "errors": [], "reports": [
                {"nodeid": "test_a.py::test_a", "when": when, "outcome": "passed", "reason": "", "xfail": False}
                for when in ("setup", "call", "teardown")]}


def test_complete_report_is_a_reference():
    result = example()
    assert validate(result)[0] == ("test_a.py::test_a",)
    equivalent(result, deepcopy(result))


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_missing_or_failed_phase_is_not_success(phase):
    result = example()
    result["reports"] = [r for r in result["reports"] if r["when"] != phase]
    with pytest.raises(EvidenceError):
        validate(result)
    result = example()
    next(r for r in result["reports"] if r["when"] == phase)["outcome"] = "failed"
    with pytest.raises(EvidenceError):
        validate(result)


def test_collection_skip_is_not_an_extra_executable_test():
    result = example()
    result["collection_reports"].append({"nodeid": "test_windows.py", "outcome": "skipped", "reason": "platform"})
    assert len(validate(result)[0]) == 1
    assert len(validate(result)[1]) == 1


def test_comparison_ignores_arrival_order_but_checks_inputs():
    a = example(); b = deepcopy(a)
    b["reports"].reverse(); b["run_id"] = "different"; b["controller_pid"] = 123
    equivalent(a, b)
    b["binding"]["source_sha256"] = "other"
    with pytest.raises(EvidenceError): equivalent(a, b)


def invoke(suite: Path, report: Path, *, workers: str = "0", reference: Path | None = None):
    env = os.environ.copy()
    env["PYTEST_ADDOPTS"] = ""
    env["PYTHONPATH"] = os.pathsep.join([str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), env.get("PYTHONPATH", "")])
    command = [sys.executable, "-m", "pytest", "-p", "no:timeout", "-p", "tools.test_evidence",
               "-c", str(suite / "pytest.ini"), "--rootdir", str(suite), "--ph-report", str(report), "-q"]
    if workers != "0": command += ["-n", workers, "--max-worker-restart=0"]
    if reference: command += ["--ph-reference", str(reference)]
    command += [str(suite)]
    return subprocess.run(command, cwd=suite, env=env, text=True, capture_output=True, check=False)


def make_suite(tmp_path: Path, body: str, conftest: str = "") -> Path:
    suite = tmp_path / "suite"; suite.mkdir()
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (suite / "test_probe.py").write_text(textwrap.dedent(body), encoding="utf-8")
    (suite / "conftest.py").write_text(textwrap.dedent(conftest), encoding="utf-8")
    return suite


def test_real_serial_report_includes_collection_skip_and_skip_phase(tmp_path):
    suite = make_suite(tmp_path, """
        import pytest
        def test_good(): pass
        @pytest.mark.skip(reason='declared')
        def test_skipped(): pass
    """)
    (suite / "test_platform.py").write_text("import pytest\npytest.skip('platform', allow_module_level=True)\n", encoding="utf-8")
    path = tmp_path / "result.json"
    completed = invoke(suite, path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(path.read_text())
    assert len(validate(report)[0]) == 2
    assert len(validate(report)[1]) == 1
    assert report["controller_pid"] > 0
    assert not list(path.parent.glob(path.name + ".*"))


@pytest.mark.parametrize("workers", ["2", "4"])
def test_real_parallel_reports_match_serial(tmp_path, workers):
    suite = make_suite(tmp_path, "import pytest\n@pytest.mark.parametrize('i', range(8))\ndef test_good(i): assert i >= 0\n")
    reference = tmp_path / "serial.json"; report = tmp_path / "parallel.json"
    before = invoke(suite, reference); assert before.returncode == 0, before.stderr
    result = invoke(suite, report, workers=workers, reference=reference)
    assert result.returncode == 0, result.stdout + result.stderr
    equivalent(json.loads(reference.read_text()), json.loads(report.read_text()))
