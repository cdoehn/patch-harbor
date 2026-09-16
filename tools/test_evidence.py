"""Development-only pytest report adapter; xdist remains the only scheduler."""
from __future__ import annotations

from collections import Counter
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import tempfile
import uuid

import pytest

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


class EvidenceError(ValueError):
    """A run cannot be accepted as a complete successful reference."""


def report_digest(reports: list[dict]) -> str:
    """Order-independent multiset digest, retaining duplicate reports."""
    rows = sorted(json.dumps(row, sort_keys=True, ensure_ascii=True) for row in reports)
    return hashlib.sha256(json.dumps(rows, ensure_ascii=True).encode()).hexdigest()


def _collection_reports(reports: list) -> tuple:
    if not isinstance(reports, list):
        raise EvidenceError("Collection reports missing")
    result = []
    for report in reports:
        if (not isinstance(report, dict) or report.get("outcome") != "skipped"
                or not isinstance(report.get("nodeid"), str) or not report["nodeid"]
                or not isinstance(report.get("reason"), str)):
            raise EvidenceError("Failed or invalid collection report")
        result.append((report["nodeid"], report["reason"]))
    if len({key for key, _ in result}) != len(result):
        raise EvidenceError("Duplicate collection skips")
    return tuple(sorted(result))


def validate(document: dict, *, collection_only: bool = False) -> tuple:
    """Return a neutral, order-independent signature of a complete result.

    A skip is not a passed test. It remains visible in the signature; a changed
    skip, missing test or changed bound input cannot match a serial reference.
    """
    if (not isinstance(document, dict) or document.get("format_version") != 1
            or type(document.get("exitstatus")) is not int or document["exitstatus"] != 0
            or document.get("errors") != [] or not isinstance(document.get("binding"), dict)
            or not document["binding"] or not isinstance(document.get("run_id"), str)
            or not document["run_id"]):
        raise EvidenceError("Failed or invalid run")
    if document.get("mode") != ("collection" if collection_only else "run"):
        raise EvidenceError("Collection-only evidence is not a completed test run")
    collections = document.get("collections")
    count = document.get("expected_workers")
    if (not isinstance(collections, dict) or type(count) is not int or count < 0
            or len(collections) != max(1, count)):
        raise EvidenceError("Missing worker collection")
    ids = None
    for worker_ids in collections.values():
        if (not isinstance(worker_ids, list) or not worker_ids
                or not all(isinstance(i, str) and i for i in worker_ids)
                or len(set(worker_ids)) != len(worker_ids)):
            raise EvidenceError("Empty, invalid or duplicate collection")
        if ids is not None and ids != worker_ids:
            raise EvidenceError("Worker collections differ")
        ids = worker_ids
    skips = _collection_reports(document.get("collection_reports"))
    if set(ids) & {i for i, _ in skips}:
        raise EvidenceError("Collection skip also appears as a runnable test")
    started = document.get("started")
    finished = document.get("finished")
    if not isinstance(started, list) or not isinstance(finished, dict):
        raise EvidenceError("Worker lifecycle evidence missing")
    if count:
        if (len(started) != count or len(set(started)) != count
                or set(started) != set(collections) or set(finished) != set(started)):
            raise EvidenceError("Not every expected worker completed")
    elif started or finished or set(collections) != {"serial"}:
        raise EvidenceError("Serial run has unexpected worker evidence")
    reports = document.get("reports")
    if not isinstance(reports, list):
        raise EvidenceError("Runtime reports missing")
    for worker, end in finished.items():
        if (not isinstance(end, dict) or end.get("run_id") != document["run_id"]
                or end.get("binding") != document["binding"]
                or type(end.get("exitstatus")) is not int or end["exitstatus"] != 0
                or end.get("collection") != collections[worker]
                or _collection_reports(end.get("collection_reports")) != skips):
            raise EvidenceError("Worker result, binding or collection missing or inconsistent")
        received = [r for r in reports if isinstance(r, dict) and r.get("worker") == worker]
        if end.get("report_count") != len(received) or end.get("reports_sha256") != report_digest(received):
            raise EvidenceError("Worker report delivery is incomplete")
    if collection_only:
        if reports:
            raise EvidenceError("Collection-only run unexpectedly executed tests")
        return tuple(sorted(ids)), skips
    phases = {}
    subtests = []
    for report in reports:
        if (not isinstance(report, dict) or report.get("nodeid") not in ids
                or report.get("when") not in ("setup", "call", "teardown")
                or report.get("worker") not in collections
                or report.get("outcome") not in ("passed", "skipped")
                or report.get("xfail") is not False or not isinstance(report.get("reason"), str)):
            raise EvidenceError("Unexpected, failed or invalid runtime report")
        key = report["nodeid"]
        subtest = report.get("subtest")
        if subtest is not None:
            if report["when"] != "call" or not isinstance(subtest, str):
                raise EvidenceError("Invalid subtest phase")
            subtests.append((key, subtest, report["outcome"], report["reason"]))
            continue
        items = phases.setdefault(key, {})
        if report["when"] in items:
            raise EvidenceError("Duplicate runtime phase")
        items[report["when"]] = (report["outcome"], report["reason"])
    if set(phases) != set(ids):
        raise EvidenceError("Test results missing")
    results = []
    for nodeid, phase in phases.items():
        if phase.get("teardown") != ("passed", "") or "setup" not in phase:
            raise EvidenceError("Setup or teardown missing")
        if phase["setup"][0] == "skipped":
            if "call" in phase or any(key == nodeid for key, *_ in subtests):
                raise EvidenceError("Skipped setup has a call")
            outcome = phase["setup"]
        else:
            if phase["setup"] != ("passed", "") or "call" not in phase:
                raise EvidenceError("Invalid setup or missing call")
            outcome = phase["call"]
        results.append((nodeid, *outcome))
    return tuple(sorted(ids)), skips, tuple(sorted(results)), tuple(sorted(subtests))


def equivalent(reference: dict, actual: dict) -> None:
    if reference.get("binding") != actual.get("binding"):
        raise EvidenceError("Inputs or interpreter differ")
    if validate(reference) != validate(actual):
        raise EvidenceError("Test IDs, results, subtests or skips differ")


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
        path = Path(self.config.getoption("--ph-report")).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=path.name + ".", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(self.document, stream, ensure_ascii=True, sort_keys=True)
                stream.write("\n")
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
