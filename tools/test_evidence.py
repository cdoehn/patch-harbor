"""Development-only pytest report adapter; xdist remains the only scheduler."""
from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import uuid

import pytest

from tools.test_results import EvidenceError, equivalent, report_digest, validate
from tools.result_io import write_report

ROOT = Path(__file__).resolve().parents[1]


def input_binding(root: Path = ROOT) -> dict:
    """Bind comparison to source bytes and the interpreter, not run timing."""
    digest = hashlib.sha256()
    excluded = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".patchharbor", "build", "dist"}
    files = []
    for name in ("src", "tests", "tools", "scripts", "docker", ".github", "docs", "spec", "planning"):
        directory = root / name
        if directory.is_dir():
            files.extend(p for p in directory.rglob("*") if p.is_file())
    files.extend(p for p in root.iterdir() if p.is_file() and p.suffix in (".py", ".toml", ".md"))
    for path in sorted(set(files)):
        rel = path.relative_to(root)
        if any(part in excluded or part.endswith(".egg-info") for part in rel.parts) or path.suffix in (".pyc", ".log"):
            continue
        data = path.read_bytes()
        digest.update(rel.as_posix().encode() + b"\0" + str(len(data)).encode() + b"\0" + data)
    try:
        xdist = version("pytest-xdist")
    except PackageNotFoundError:
        xdist = None
    return {"source_sha256": digest.hexdigest(), "python": platform.python_version(),
            "platform": platform.system(), "pytest": pytest.__version__, "xdist": xdist,
            "windows_engine": os.environ.get("PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE", "")}


def pytest_addoption(parser):
    group = parser.getgroup("patchharbor-development-evidence")
    group.addoption("--ph-report", default=None, help="Controller-owned development JSON report.")
    group.addoption("--ph-reference", default=None, help="Require equivalence with a serial JSON reference.")


def pytest_configure(config):
    if config.getoption("--ph-reference") and not config.getoption("--ph-report"):
        raise pytest.UsageError("--ph-reference requires --ph-report")
    if config.getoption("--ph-report"):
        config.pluginmanager.register(Capture(config), "patchharbor-development-capture")


def _reason(report) -> str:
    if not report.skipped:
        return ""
    value = report.longrepr
    return str(value[2] if isinstance(value, tuple) and len(value) == 3 else value)


class Capture:
    def __init__(self, config):
        self.config = config
        self.worker = hasattr(config, "workerinput")
        self.document = {"format_version": 1, "run_id": str(uuid.uuid4()),
                         "binding": input_binding(), "expected_workers": 0,
                         "mode": "collection" if config.option.collectonly else "run",
                         "started": [], "finished": {},
                         "collections": {}, "collection_reports": [], "reports": [], "errors": [],
                         "exitstatus": None, "controller_pid": os.getpid()}

        self.worker_key = config.workerinput["workerid"] if self.worker else "serial"
        if self.worker:
            self.document["run_id"] = config.workerinput["ph_evidence_run_id"]

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_setupnodes(self, config, specs):
        self.document["expected_workers"] = len(specs)

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node):
        node.workerinput["ph_evidence_run_id"] = self.document["run_id"]
        self.document["started"].append(node.gateway.id)

    def pytest_collection_finish(self, session):
        self.document["collections"][self.worker_key] = [item.nodeid for item in session.items]

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node, ids):
        self.document["collections"][node.gateway.id] = list(ids)

    def pytest_collectreport(self, report):
        if not report.passed:
            row = {"nodeid": report.nodeid, "outcome": report.outcome, "reason": _reason(report)}
            if row not in self.document["collection_reports"]:
                self.document["collection_reports"].append(row)

    def pytest_runtest_logreport(self, report):
        context = getattr(report, "context", None)
        subtest = None
        if context is not None:
            subtest = json.dumps({"msg": repr(context.msg), "kwargs": {str(k): repr(v) for k, v in context.kwargs.items()}}, sort_keys=True)
        node = getattr(report, "node", None)
        worker = node.gateway.id if node is not None else self.worker_key
        self.document["reports"].append({"nodeid": report.nodeid, "when": report.when,
                                         "outcome": report.outcome, "reason": _reason(report),
                                         "xfail": bool(getattr(report, "wasxfail", False)),
                                         "subtest": subtest, "worker": worker})

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node, error):
        if error:
            self.document["errors"].append(str(error))
        summary = getattr(node, "workeroutput", {}).get("ph_evidence")
        if not isinstance(summary, dict) or node.gateway.id in self.document["finished"]:
            self.document["errors"].append("Missing or duplicate worker completion")
        else:
            self.document["finished"][node.gateway.id] = summary

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.worker:
            self.config.workeroutput["ph_evidence"] = {
                "run_id": self.document["run_id"], "binding": self.document["binding"],
                "exitstatus": int(session.exitstatus),
                "collection": self.document["collections"].get(self.worker_key),
                "collection_reports": self.document["collection_reports"],
                "report_count": len(self.document["reports"]),
                "reports_sha256": report_digest(self.document["reports"]),
            }
            return
        self.document["exitstatus"] = int(session.exitstatus)
        try:
            if self.document["binding"] != input_binding():
                raise EvidenceError("Bound source inputs changed during the run")
            validate(self.document, collection_only=session.config.option.collectonly)
            reference = self.config.getoption("--ph-reference")
            if reference:
                equivalent(json.loads(Path(reference).read_text(encoding="utf-8")), self.document)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.document["errors"].append(str(exc))
            if session.exitstatus == 0:
                session.exitstatus = pytest.ExitCode.TESTS_FAILED
        self.document["exitstatus"] = int(session.exitstatus)
        write_report(Path(self.config.getoption("--ph-report")), self.document)
