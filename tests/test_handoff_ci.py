"""Offline GitHub transport fixtures for a single correlated CI request and evidence."""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from zipfile import BadZipFile, ZipFile

import pytest

from scripts import run_handoff_ci as ci
from tests.test_test_evidence import example

COMMIT = "a" * 40
HANDOFF = "patchharbor-riv-014-7a3b531f-f7d2-4c62-9e0d-c23e005a1223"


def reports(expected):
    platform, python, engine = expected
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        suites = ["windows"] if engine == "pwsh" else ["core", "e2e", "platform", "packaging"]
        for suite in suites:
            document = example()
            document["binding"].update(platform=platform, python=python + ".1", windows_engine=engine)
            if suite == "packaging":
                nodes = ["tests/test_runtime_bootstrap.py::test_actual_offline_install_and_native_reference_check",
                         "tests/test_runtime_bootstrap.py::test_uv_installed_runtime_works_outside_checkout"]
            elif suite == "e2e":
                nodes = [f"tests/test_handoff_commit_sequence.py::test_real_diagnostic_and_commit_sequences_keep_gates_and_single_final_push[{n}]"
                         for n in (0, 1, 3)]
            else:
                nodes = ["tests/test_probe.py::test_good"]
            document["collections"]["serial"] = nodes
            sample = document["reports"]
            document["reports"] = [{**row, "nodeid": node} for row in sample for node in nodes]
            archive.writestr(f"patchharbor-{suite}-tests.json", json.dumps(document))
    return output.getvalue()


@pytest.fixture
def github(tmp_path, monkeypatch):
    run = {"id": 100, "head_sha": COMMIT, "head_branch": "dev", "event": "workflow_dispatch",
           "display_title": "PatchHarbor acceptance - " + HANDOFF, "workflow_id": 77, "run_attempt": 1,
           "status": "completed", "conclusion": "success", "html_url": "https://github.com/cdoehn/patch-harbor/actions/runs/100"}
    jobs = [{"id": i+1, "name": name, "status": "completed", "conclusion": "success",
             "head_sha": COMMIT, "steps": []} for i, name in enumerate(sorted(ci.JOBS))]
    artifacts = [{"id": i+1, "name": name, "expired": False} for i, name in enumerate(ci.ARTIFACTS)]
    blobs = {row["id"]: reports(ci.ARTIFACTS[row["name"]]) for row in artifacts}
    state = SimpleNamespace(run=run, jobs=jobs, artifacts=artifacts, blobs=blobs, dispatched=False,
                            calls=[], sleeps=[], fault=None, workspace=tmp_path / "ci", clock=0)
    def request(route, body=None, *, binary=False):
        state.calls.append((route, body))
        if route == "actions/workflows/acceptance-tests.yml":
            if state.fault == "auth": raise subprocess.CalledProcessError(1, ["gh", "api"])
            return {"state": "active", "id": 77}
        if route.endswith("/dispatches"):
            assert body == {"ref": "dev", "inputs": {"handoff_id": HANDOFF, "expected_commit": COMMIT}}
            assert not state.dispatched
            state.dispatched = True
            if state.fault == "dispatch_uncertain": raise subprocess.TimeoutExpired(["gh", "api"], 120)
            return None if state.fault == "legacy_response" else {"workflow_run_id": 100}
        if "/runs?" in route:
            return {"workflow_runs": [deepcopy(run)] if state.dispatched or state.fault == "duplicate" else []}
        if route == "actions/runs/100":
            if state.fault == "waiting":
                if not state.sleeps: return {**run, "status": "queued"}
            if state.fault == "timeout": return {**run, "status": "queued"}
            return deepcopy(run)
        if "/jobs?" in route: return {"jobs": deepcopy(jobs)}
        if "/artifacts?" in route: return {"artifacts": deepcopy(artifacts)}
        if route.startswith("actions/artifacts/") and binary: return blobs[int(route.split("/")[2])]
        pytest.fail("unexpected endpoint: " + route)
    def sleep(seconds):
        state.sleeps.append(seconds); state.clock += seconds
    monkeypatch.setattr(ci, "request", request)
    monkeypatch.setattr(ci.time, "sleep", sleep)
    monkeypatch.setattr(ci.time, "monotonic", lambda: state.clock)
    monkeypatch.setattr(ci.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, b"failure diagnostic", b""))
    return state


@pytest.mark.parametrize("mode", [None, "waiting", "legacy_response"])
def test_one_dispatch_returns_complete_bound_windows_and_second_python_evidence(github, mode):
    github.fault = mode
    result = ci.run(COMMIT, HANDOFF, workspace=github.workspace)
    assert result["status"] == "success" and result["commit"] == COMMIT and result["run_id"] == 100
    assert len([body for route, body in github.calls if body is not None]) == 1
    assert {row["name"] for row in result["jobs"]} == ci.JOBS
    assert len(result["artifacts"]) == 4
    assert all(row["reports"] for row in result["artifacts"])
    assert json.loads((github.workspace / "evidence.json").read_text()) == result
    assert github.sleeps == ([60] if mode == "waiting" else [])
    before = list(github.calls)
    with pytest.raises(FileExistsError): ci.run(COMMIT, HANDOFF, workspace=github.workspace)
    assert github.calls == before  # no second dispatch after restart


@pytest.mark.parametrize("fault", ["auth", "duplicate", "dispatch_uncertain", "timeout", "wrong_sha",
                                   "wrong_branch", "wrong_workflow", "rerun", "missing_windows",
                                   "wrong_job_sha", "failed_job", "missing_report", "expired_report", "corrupt_report"])
def test_ci_failures_preserve_receipt_and_never_rerun(github, fault):
    github.fault = fault
    changes = {"wrong_sha": {"head_sha": "b"*40}, "wrong_branch": {"head_branch": "main"},
               "wrong_workflow": {"workflow_id": 999}, "rerun": {"run_attempt": 2}}
    github.run.update(changes.get(fault, {}))
    if fault == "missing_windows": github.jobs[:] = [row for row in github.jobs if "Windows" not in row["name"]]
    if fault == "wrong_job_sha": github.jobs[0]["head_sha"] = "b"*40
    if fault == "failed_job": github.jobs[0]["conclusion"] = "failure"
    if fault == "missing_report": github.artifacts.pop()
    if fault == "expired_report": github.artifacts[0]["expired"] = True
    if fault == "corrupt_report": github.blobs[1] = b"not a ZIP"
    with pytest.raises((ValueError, OSError, BadZipFile, subprocess.SubprocessError)):
        ci.run(COMMIT, HANDOFF, workspace=github.workspace, timeout=120)
    result = json.loads((github.workspace / "evidence.json").read_text())
    assert result["status"] == "failed" and result["dispatch_attempts"] <= 1
    assert len([body for route, body in github.calls if body is not None]) <= 1
    if fault == "failed_job":
        assert result["failure_log"]["bytes"] > 0 and result["jobs"]


@pytest.mark.parametrize("fault", ["wrong_platform", "wrong_python", "missing_test", "changed_sources", "extra_file"])
def test_artifact_contract_rejects_incomplete_or_mismatched_proofs(github, fault):
    with ZipFile(BytesIO(github.blobs[1])) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    name = "patchharbor-packaging-tests.json"
    doc = json.loads(files[name])
    if fault == "wrong_platform": doc["binding"]["platform"] = "Windows"
    if fault == "wrong_python": doc["binding"]["python"] = "3.14.1"
    if fault == "missing_test": doc["reports"].pop()
    if fault == "changed_sources": doc["binding"]["source_sha256"] = "other"
    files[name] = json.dumps(doc).encode()
    if fault == "extra_file": files["../unexpected.json"] = b"{}"
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, raw in files.items(): archive.writestr(name, raw)
    github.blobs[1] = output.getvalue()
    with pytest.raises(ValueError): ci.run(COMMIT, HANDOFF, workspace=github.workspace)
    assert json.loads((github.workspace / "evidence.json").read_text())["status"] == "failed"


def test_transport_uses_structured_stdin_and_never_shell_or_credentials_in_arguments(monkeypatch):
    calls = []
    def invoke(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, b'{"workflow_run_id":100}', b"")
    monkeypatch.setattr(ci.subprocess, "run", invoke)
    body = {"ref": "dev", "inputs": {"handoff_id": HANDOFF, "expected_commit": COMMIT}}
    assert ci.request("actions/workflows/acceptance-tests.yml/dispatches", body) == {"workflow_run_id": 100}
    command, arguments = calls[0]
    assert command[:4] == ["gh", "api", "--hostname", "github.com"] and command[-2:] == ["--input", "-"]
    assert json.loads(arguments["input"]) == body and not arguments.get("shell")
    assert arguments["check"] and arguments["timeout"] == 120
