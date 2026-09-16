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

from tools.test_evidence import EvidenceError, equivalent, report_digest, validate
from tests.platform_support import PROJECT_ROOT


def example() -> dict:
    return {"format_version": 1, "run_id": "example", "binding": {"source_sha256": "a"},
            "mode": "run", "started": [], "finished": {},
            "exitstatus": 0, "expected_workers": 0, "collections": {"serial": ["test_a.py::test_a"]},
            "collection_reports": [], "errors": [], "reports": [
                {"nodeid": "test_a.py::test_a", "when": when, "outcome": "passed", "reason": "", "xfail": False, "subtest": None, "worker": "serial"}
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


def worker_example() -> dict:
    result = example()
    result["expected_workers"] = 2
    result["collections"] = {key: ["test_a.py::test_a"] for key in ("gw0", "gw1")}
    result["started"] = ["gw0", "gw1"]
    for r in result["reports"]: r["worker"] = "gw0"
    for worker in result["started"]:
        reports = result["reports"] if worker == "gw0" else []
        result["finished"][worker] = {"run_id": result["run_id"], "binding": deepcopy(result["binding"]),
                                      "exitstatus": 0, "collection": result["collections"][worker],
                                      "collection_reports": [], "report_count": len(reports),
                                      "reports_sha256": report_digest(reports)}
    return result


def test_idle_worker_must_still_complete():
    result = worker_example(); validate(result)
    del result["finished"]["gw1"]
    with pytest.raises(EvidenceError): validate(result)


@pytest.mark.parametrize("corruption", ["missing_worker", "crash", "missing_reports", "duplicate_report", "different_collection", "empty_collection", "duplicate_id", "changed_binding", "missing_completion", "wrong_run", "missing_teardown", "failed_setup", "failed_call", "failed_teardown", "xfail", "new_id", "no_errors_field", "missing_mode"])
def test_incomplete_reports_never_become_green(corruption):
    result = worker_example()
    if corruption == "missing_worker": del result["collections"]["gw1"]
    elif corruption == "crash": result["errors"] = ["crash"]
    elif corruption == "missing_reports": result["reports"] = []
    elif corruption == "duplicate_report": result["reports"].append(deepcopy(result["reports"][1]))
    elif corruption == "different_collection": result["collections"]["gw1"] = ["other"]
    elif corruption == "empty_collection": result["collections"] = {"gw0": [], "gw1": []}
    elif corruption == "duplicate_id": result["collections"]["gw0"] *= 2
    elif corruption == "changed_binding": result["finished"]["gw1"]["binding"] = {"source_sha256": "b"}
    elif corruption == "missing_completion": del result["finished"]["gw0"]
    elif corruption == "wrong_run": result["finished"]["gw0"]["run_id"] = "stale"
    elif corruption == "missing_teardown": result["reports"].pop()
    elif corruption.startswith("failed_"):
        phase = corruption.removeprefix("failed_")
        next(r for r in result["reports"] if r["when"] == phase)["outcome"] = "failed"
    elif corruption == "xfail": result["reports"][1]["xfail"] = True
    elif corruption == "new_id": result["reports"][1]["nodeid"] = "other"
    elif corruption == "no_errors_field": del result["errors"]
    elif corruption == "missing_mode": del result["mode"]
    with pytest.raises(EvidenceError): validate(result)


def test_changed_runtime_skip_cannot_match_reference():
    reference = example(); actual = deepcopy(reference)
    actual["reports"][1].update(outcome="skipped", reason="unexpected")
    validate(actual)  # complete report, but definitely not equivalent
    with pytest.raises(EvidenceError): equivalent(reference, actual)


def test_subtest_reports_do_not_replace_parent_or_hide_failure():
    result = example()
    subtest = deepcopy(result["reports"][1]); subtest["subtest"] = '{"value": 1}'
    result["reports"].insert(1, subtest)
    assert len(validate(result)[3]) == 1
    subtest["outcome"] = "failed"
    with pytest.raises(EvidenceError): validate(result)


@pytest.mark.parametrize("workers", ["0", "2"])
@pytest.mark.parametrize("scenario", ["setup", "teardown", "assertion", "subtest", "collection"])
def test_real_failed_phase_or_subtest_is_red(tmp_path, workers, scenario):
    config = ""
    body = "def test_good(): pass\n"
    if scenario == "setup": config = "import pytest\n@pytest.fixture(autouse=True)\ndef broken(): raise RuntimeError('setup')\n"
    elif scenario == "teardown": config = "import pytest\n@pytest.fixture(autouse=True)\ndef broken():\n yield\n raise RuntimeError('teardown')\n"
    elif scenario == "assertion": body = "def test_bad(): assert False\n"
    elif scenario == "subtest": body = "import unittest\nclass TestSub(unittest.TestCase):\n def test_sub(self):\n  with self.subTest(value=1): self.assertEqual(1,2)\n"
    elif scenario == "collection": body = "raise RuntimeError('collection')\n"
    suite = make_suite(tmp_path, body, config); path = tmp_path / "report.json"
    result = invoke(suite, path, workers=workers)
    assert result.returncode != 0
    with pytest.raises(EvidenceError): validate(json.loads(path.read_text()))


@pytest.mark.parametrize("scenario", ["crash", "collection_mismatch", "missing_completion", "dropped_report"])
def test_real_parallel_worker_failures_are_red(tmp_path, scenario):
    config = ""
    body = "import pytest\n@pytest.mark.parametrize('i', range(8))\ndef test_good(i): pass\n"
    if scenario == "crash": body = "import os\ndef test_crash(): os._exit(7)\n"
    elif scenario == "collection_mismatch":
        config = "def pytest_collection_modifyitems(config,items):\n if getattr(config,'workerinput',{}).get('workerid')=='gw1': items.pop()\n"
    elif scenario == "missing_completion":
        config = "import pytest\n@pytest.hookimpl(wrapper=True,trylast=True)\ndef pytest_sessionfinish(session,exitstatus):\n yield\n if hasattr(session.config,'workerinput'): session.config.workeroutput.pop('ph_evidence',None)\n"
    else:
        config = "import pytest\n@pytest.hookimpl(wrapper=True)\ndef pytest_runtest_logreport(report):\n yield\n if getattr(report,'node',None) is not None and report.when=='call':\n  capture=report.node.config.pluginmanager.getplugin('patchharbor-development-capture')\n  capture.document['reports'].pop()\n"
    suite = make_suite(tmp_path, body, config); path = tmp_path / "report.json"
    result = invoke(suite, path, workers="2")
    assert result.returncode != 0, result.stdout + result.stderr
    with pytest.raises(EvidenceError): validate(json.loads(path.read_text()))


def test_real_reference_rejects_unexpected_skip(tmp_path):
    # The bound repository source does not change; an external resource controls
    # this intentionally broken test's outcome, illustrating why IDs alone fail.
    signal = tmp_path / "skip-now"
    suite = make_suite(tmp_path, f"import pytest\nfrom pathlib import Path\ndef test_result():\n if Path({str(signal)!r}).exists(): pytest.skip('unexpected')\n")
    reference = tmp_path / "reference.json"; actual = tmp_path / "actual.json"
    result = invoke(suite, reference); assert result.returncode == 0, result.stderr
    signal.touch()
    result = invoke(suite, actual, reference=reference)
    assert result.returncode != 0
    assert json.loads(actual.read_text())["errors"]


def test_collection_only_is_never_a_successful_runtime_report():
    result = example(); result["mode"] = "collection"; result["reports"] = []
    validate(result, collection_only=True)
    with pytest.raises(EvidenceError): validate(result)


def test_crashed_worker_without_output_still_has_a_rejected_completion():
    from types import SimpleNamespace
    from tools.test_evidence import Capture
    capture = object.__new__(Capture)
    capture.document = {"errors": [], "finished": {}}
    node = SimpleNamespace(gateway=SimpleNamespace(id="gw0"))
    capture.pytest_testnodedown(node, "worker terminated")
    assert capture.document["errors"]
    assert capture.document["finished"] == {}
