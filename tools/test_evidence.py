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


def validate(document: dict, *, collection_only: bool = False) -> tuple:
    """Validate full phase coverage, not a count of JUnit XML elements."""
    if document.get("format_version") != 1 or document.get("exitstatus") != 0 or document.get("errors"):
        raise EvidenceError("Failed or invalid run")
    collections = document.get("collections", {})
    count = document.get("expected_workers")
    if not isinstance(count, int) or count < 0 or len(collections) != max(1, count):
        raise EvidenceError("Missing worker collection")
    ids = None
    for worker_ids in collections.values():
        if not worker_ids or len(set(worker_ids)) != len(worker_ids):
            raise EvidenceError("Empty or duplicate collection")
        if ids is not None and ids != worker_ids:
            raise EvidenceError("Worker collections differ")
        ids = worker_ids
    skips = tuple(sorted((r["nodeid"], r["reason"]) for r in document.get("collection_reports", []) if r["outcome"] == "skipped"))
    if any(r["outcome"] != "skipped" for r in document.get("collection_reports", [])):
        raise EvidenceError("Collection failed")
    if collection_only:
        return tuple(sorted(ids)), skips
    phases = {}
    for report in document.get("reports", []):
        key = report["nodeid"]
        if key not in ids or report["when"] not in ("setup", "call", "teardown"):
            raise EvidenceError("Unexpected test or phase")
        items = phases.setdefault(key, {})
        if report["when"] in items or report["outcome"] not in ("passed", "skipped") or report["xfail"]:
            raise EvidenceError("Duplicate, failed or xfailed phase")
        items[report["when"]] = (report["outcome"], report["reason"])
    if set(phases) != set(ids):
        raise EvidenceError("Test results missing")
    results = []
    for nodeid, phase in phases.items():
        if phase.get("teardown") != ("passed", "") or "setup" not in phase:
            raise EvidenceError("Setup or teardown missing")
        if phase["setup"][0] == "skipped":
            if "call" in phase:
                raise EvidenceError("Skipped setup has a call")
            outcome = phase["setup"]
        else:
            if "call" not in phase:
                raise EvidenceError("Call missing")
            outcome = phase["call"]
        results.append((nodeid, *outcome))
    return tuple(sorted(ids)), skips, tuple(sorted(results))


def equivalent(reference: dict, actual: dict) -> None:
    if reference.get("binding") != actual.get("binding"):
        raise EvidenceError("Inputs or interpreter differ")
    if validate(reference) != validate(actual):
        raise EvidenceError("Test IDs, results or skips differ")


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
                         "binding": input_binding(), "expected_workers": config.getoption("numprocesses", default=0) or 0,
                         "collections": {}, "collection_reports": [], "reports": [], "errors": [],
                         "exitstatus": None, "controller_pid": os.getpid()}

    def pytest_collection_finish(self, session):
        self.document["collections"]["serial"] = [item.nodeid for item in session.items]

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node, ids):
        self.document["collections"][node.gateway.id] = list(ids)

    def pytest_collectreport(self, report):
        if not report.passed:
            row = {"nodeid": report.nodeid, "outcome": report.outcome, "reason": _reason(report)}
            if row not in self.document["collection_reports"]:
                self.document["collection_reports"].append(row)

    def pytest_runtest_logreport(self, report):
        self.document["reports"].append({"nodeid": report.nodeid, "when": report.when,
                                         "outcome": report.outcome, "reason": _reason(report),
                                         "xfail": bool(getattr(report, "wasxfail", False))})

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node, error):
        if error:
            self.document["errors"].append(str(error))

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.worker:
            return
        self.document["exitstatus"] = int(session.exitstatus)
        try:
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
