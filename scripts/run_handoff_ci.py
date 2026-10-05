"""Project handoff CI: one dispatch after push, correlated evidence in Apply logs.

This is repository orchestration, not a Core or Watcher feature. The caller
owns the five-bundle cadence. No automatic retry, rerun, push or Git mutation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.test_results import validate

REPOSITORY = "cdoehn/patch-harbor"
WORKFLOW = "acceptance-tests.yml"
BRANCH = "dev"
JOBS = {
    "Release gate - Ubuntu 24.04", "Release gate - Ubuntu 26.04",
    "Release gate - Windows 2025", "Release gate - Windows 2025 - PowerShell 7",
    "Docker release gate - Ubuntu 24.04", "Docker release gate - Ubuntu 26.04",
}
ARTIFACTS = {
    "patchharbor-packaging-ubuntu-24.04": ("Linux", "3.12", ""),
    "patchharbor-packaging-ubuntu-26.04": ("Linux", "3.14", ""),
    "patchharbor-packaging-windows-2025": ("Windows", "3.12", "powershell.exe"),
    "patchharbor-windows-powershell7": ("Windows", "3.12", "pwsh"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def request(route, body=None, *, binary=False):
    command = ["gh", "api", "--hostname", "github.com", "--method",
               "GET" if body is None else "POST", "-H", "X-GitHub-Api-Version: 2026-03-10",
               f"repos/{REPOSITORY}/{route}"]
    if body is not None:
        command += ["--input", "-"]
    result = subprocess.run(command, input=None if body is None else json.dumps(body).encode(),
                            capture_output=True, check=True, timeout=120)
    if binary:
        return result.stdout
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(route, key):
    rows = []
    for page in range(1, 11):
        separator = "&" if "?" in route else "?"
        document = request(f"{route}{separator}per_page=100&page={page}")
        current = document[key]
        require(isinstance(current, list), "invalid GitHub page")
        rows.extend(current)
        if len(current) < 100:
            return rows
    raise ValueError("GitHub result exceeds pagination budget")


def save(path, document):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    print("PATCHHARBOR_CI_JSON=" + json.dumps(document, ensure_ascii=True), flush=True)


def artifact_evidence(artifact, expected, *, source_digest=None):
    raw = request(f"actions/artifacts/{artifact['id']}/zip", binary=True)
    require(len(raw) <= 32 * 1024 * 1024, "CI artifact exceeds compressed budget")
    platform, python, engine = expected
    with ZipFile(BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        expected_names = ({"patchharbor-windows-tests.json"} if engine == "pwsh" else
                          {f"patchharbor-{suite}-tests.json" for suite in ("core", "e2e", "platform", "packaging")})
        require(len(names) == len(set(names)) and set(names) == expected_names,
                "CI report inventory mismatch")
        require(all(info.file_size <= 32 * 1024 * 1024 and not info.flag_bits & 1 for info in infos),
                "CI report exceeds budget or is encrypted")
        reports = []
        for name in sorted(names):
            data = archive.read(name)
            document = json.loads(data)
            signature = validate(document)
            binding = document["binding"]
            require(binding["platform"] == platform and binding["python"].startswith(python + ".")
                    and binding["windows_engine"] == engine, "CI platform evidence mismatch")
            if source_digest is None:
                source_digest = binding["source_sha256"]
            require(binding["source_sha256"] == source_digest, "CI reports use different source bytes")
            counts = Counter(outcome for _, outcome, _ in signature[2])
            counts["skipped"] += len(signature[1])
            focus = [{"nodeid": nodeid, "outcome": outcome} for nodeid, outcome, _ in signature[2]
                     if any(part in nodeid for part in ("test_runtime_bootstrap", "test_handoff_commit_sequence",
                                                        "test_runtime_packaging", "test_runtime_acl",
                                                        "test_watcher_events_native", "test_watcher_event_loop_e2e",
                                                        "test_watcher_scheduling",
                                                        "test_release_distributions_run_after_pipx_installation"))]
            if "packaging" in name:
                require(any("test_actual_offline_install" in row["nodeid"] and row["outcome"] == "passed"
                            for row in focus), "missing actual bootstrap proof")
                if platform == "Linux" and python == "3.14":
                    require(any("test_uv_installed_runtime" in row["nodeid"] and row["outcome"] == "passed"
                                for row in focus), "missing designated uv proof")
            if "e2e" in name:
                require(sum("test_real_diagnostic_and_commit_sequences" in row["nodeid"]
                            and row["outcome"] == "passed" for row in focus) == 3,
                        "missing zero/one/multiple commit proof")
            reports.append({"name": name, "sha256": sha256(data).hexdigest(), "binding": binding,
                            "workers": document["expected_workers"], "counts": dict(counts), "focus": focus})
    return {"name": artifact["name"], "id": artifact["id"], "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw), "reports": reports}, source_digest


def run(commit, handoff_id, *, workspace=None, timeout=8100):
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "full Git commit required")
    require(re.fullmatch(r"patchharbor-riv-[0-9]{3}-[0-9a-f-]{36}", handoff_id), "invalid handoff ID")
    workspace = workspace or ROOT / "build" / "handoff-ci" / handoff_id
    workspace.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(mode=0o700)  # never redispatch an existing attempt
    receipt = workspace / "evidence.json"
    evidence = {"format_version": 1, "handoff_id": handoff_id, "repository": REPOSITORY,
                "workflow": WORKFLOW, "commit": commit, "branch": BRANCH,
                "status": "preflight", "dispatch_attempts": 0, "jobs": [], "artifacts": []}
    save(receipt, evidence)
    try:
        workflow = request(f"actions/workflows/{WORKFLOW}")
        require(workflow["state"] == "active", "Acceptance workflow is disabled")
        title = "PatchHarbor acceptance - " + handoff_id
        # Correlation title is unique; no source has permission to select an old
        # green run by branch, truncated SHA or similar timestamp alone.
        route = f"actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&branch={BRANCH}"
        require(not any(row["display_title"] == title for row in pages(route, "workflow_runs")),
                "handoff was already dispatched")
        evidence.update(status="dispatch_intent", dispatch_attempts=1,
                        requested_at=datetime.now(timezone.utc).isoformat())
        save(receipt, evidence)
        dispatched = request(f"actions/workflows/{WORKFLOW}/dispatches",
                             {"ref": BRANCH, "inputs": {"handoff_id": handoff_id, "expected_commit": commit}})
        evidence["dispatch_response"] = ({key: dispatched.get(key) for key in
                                          ("workflow_run_id", "run_url", "html_url")}
                                         if isinstance(dispatched, dict) else None)
        evidence["status"] = "awaiting_run"
        save(receipt, evidence)
        deadline = time.monotonic() + timeout
        binding_deadline = time.monotonic() + min(timeout, 120)
        run_id = dispatched.get("workflow_run_id") if isinstance(dispatched, dict) else None
        while True:
            require(time.monotonic() < deadline, "CI wait deadline exceeded; do not redispatch")
            if run_id is None:
                found = [row for row in pages(route, "workflow_runs") if row["display_title"] == title]
                require(len(found) <= 1, "multiple runs for the same handoff")
                if not found:
                    time.sleep(60)
                    continue
                run_id = found[0]["id"]
            observed = request(f"actions/runs/{run_id}")
            expected = {"id": run_id, "head_sha": commit, "head_branch": BRANCH,
                        "event": "workflow_dispatch", "display_title": title,
                        "workflow_id": workflow["id"], "run_attempt": 1}
            mismatches = {key: {"expected": value, "observed": observed.get(key)}
                          for key, value in expected.items() if observed.get(key) != value}
            # A newly dispatched run can be visible before its metadata settles.
            # Persist the actual response even on failure; no job/artifact is
            # accepted until every binding field matches, including at completion.
            evidence.update(run_id=run_id, url=observed.get("html_url"),
                            run_attempt=observed.get("run_attempt"), binding_verified=not mismatches,
                            observed_run={key: observed.get(key) for key in
                                          (*expected, "status", "conclusion", "html_url")},
                            binding_mismatches=mismatches)
            if mismatches:
                evidence["status"] = "awaiting_run_binding"
                evidence.setdefault("binding_observations", []).append(evidence["observed_run"])
                save(receipt, evidence)
                pending = observed.get("status") in {"requested", "waiting", "pending", "queued", "in_progress"}
                require(pending and time.monotonic() < binding_deadline,
                        "CI run binding mismatch: " + ", ".join(sorted(mismatches)))
                time.sleep(60)
                continue
            if evidence["status"] != "running":
                evidence["status"] = "running"
                save(receipt, evidence)
            if observed["status"] == "completed":
                break
            time.sleep(60)
        evidence["conclusion"] = observed["conclusion"]
        jobs = pages(f"actions/runs/{run_id}/attempts/1/jobs", "jobs")
        evidence["jobs"] = [{key: row.get(key) for key in
                             ("id", "name", "status", "conclusion", "html_url", "head_sha", "steps")}
                            for row in jobs]
        artifacts = pages(f"actions/runs/{run_id}/artifacts", "artifacts")
        evidence["available_artifacts"] = [{key: row.get(key) for key in ("id", "name", "size_in_bytes", "expired")}
                                           for row in artifacts]
        save(receipt, evidence)
        if observed["conclusion"] != "success" or any(row["conclusion"] != "success" for row in jobs):
            failure = subprocess.run(["gh", "run", "view", str(run_id), "--repo", REPOSITORY, "--log-failed"],
                                     capture_output=True, timeout=120)
            raw = failure.stdout + failure.stderr
            (workspace / "failed-jobs.log").write_bytes(raw)
            evidence["failure_log"] = {"sha256": sha256(raw).hexdigest(), "bytes": len(raw),
                                       "tail": raw[-48000:].decode("utf-8", errors="replace")}
            raise ValueError("GitHub acceptance failed")
        require(len(jobs) == len(JOBS) and {row["name"] for row in jobs} == JOBS
                and all(row["status"] == "completed" and row["head_sha"] == commit for row in jobs),
                "incomplete CI job matrix, including Windows")
        for name, expected in ARTIFACTS.items():
            matching = [row for row in artifacts if row["name"] == name and not row["expired"]]
            require(len(matching) == 1, "missing or duplicate CI report: " + name)
            report, _ = artifact_evidence(matching[0], expected)
            evidence["artifacts"].append(report)
        evidence["status"] = "success"
        save(receipt, evidence)
        return evidence
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, subprocess.SubprocessError) as exc:
        evidence.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
        save(receipt, evidence)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--handoff-id", required=True)
    arguments = parser.parse_args(argv)
    run(arguments.commit, arguments.handoff_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
