"""Neutral validation of test evidence. No pytest hooks, worker transport or scheduler."""
from __future__ import annotations

import hashlib
import json


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
