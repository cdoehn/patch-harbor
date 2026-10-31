"""Shared runner fixtures and behavior probes."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import textwrap

from tests.platform_support import PROJECT_ROOT


ENVIRONMENT_CHECK = PROJECT_ROOT / "scripts" / "check_docker_integration_environment.py"


def _environment_check_module():
    spec = importlib.util.spec_from_file_location(
        "patchharbor_docker_environment_check",
        ENVIRONMENT_CHECK,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def example() -> dict:
    return {"format_version": 1, "run_id": "example", "binding": {"source_sha256": "a"},
            "mode": "run", "started": [], "finished": {},
            "exitstatus": 0, "expected_workers": 0, "collections": {"serial": ["test_a.py::test_a"]},
            "collection_reports": [], "errors": [], "reports": [
                {"nodeid": "test_a.py::test_a", "when": when, "outcome": "passed", "reason": "", "xfail": False, "subtest": None, "worker": "serial"}
                for when in ("setup", "call", "teardown")]}


def invoke(suite: Path, report: Path | None, *, workers: str = "0", reference: Path | None = None):
    env = os.environ.copy()
    env["PYTEST_ADDOPTS"] = ""
    env["PYTHONPATH"] = os.pathsep.join([str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), env.get("PYTHONPATH", "")])
    command = [sys.executable, "-m", "pytest", "-p", "no:timeout", "-p", "tools.test_evidence",
               "-c", str(suite / "pytest.ini"), "--rootdir", str(suite), "--ph-check", "-q"]
    if report is not None: command += ["--ph-report", str(report)]
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
