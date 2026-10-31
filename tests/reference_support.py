"""Shared reference fixtures and behavior probes."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import stat
from zipfile import ZipFile, ZipInfo

from patchharbor import api
from patchharbor.archive_evidence import CLEAN_FINGERPRINT
from patchharbor.run_report import PrimaryResult

from tests.patch_inspection_support import MANIFEST, write_package
from tests.result_runtime_support import attach_pyz, edit_document
from tests.runtime_pyz_support import prepared


def reference_entries(*, kind="bundle", dirty=False, object_format="sha1", handoff=True):
    binding = {k: MANIFEST[k] for k in ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")}
    binding["base_commit"] = "12" * (20 if object_format == "sha1" else 32)
    binding["state_fingerprint"] = "a" * 16 if dirty else CLEAN_FINGERPRINT
    run_id = "11223344-5566-4788-9911-aabbccddeeff"
    stamp = "2026-10-03T12:00:00Z"
    primary = {"bundle": PrimaryResult.success_result, "success": PrimaryResult.entrypoint_success_result,
               "dry_run": PrimaryResult.dry_run_success_result,
               "failure": lambda: PrimaryResult.entrypoint_exit_result(27),
               "mismatch": lambda: PrimaryResult.from_tool_error(api.PatchHarborError("mismatch", api.FailureReason.STATE_MISMATCH)),
               "timeout": PrimaryResult.timeout_result, "interrupted": PrimaryResult.interrupted_result}[kind]()
    raw = b"base\x00\xff\n"
    blob = hashlib.new(object_format, b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    manifest = {"marker": "patch-harbor-result-bundle", "format_version": 3, **binding,
                "created_at": stamp, "run_id": run_id, "dirty": dirty, "dry_run": kind == "dry_run",
                "entrypoint_started": primary.entrypoint_started, "execution_present": primary.entrypoint_started,
                "primary_result": primary.kind.value, "result_bundle_status": "created",
                "base_entries": [{"path": "tracked.txt", "git_mode": "100644", "object_id": blob, "size": len(raw)}],
                "untracked_entries": []}
    context = {**binding, "dirty": dirty, "created_at": stamp, "bundle_suffix": ""}
    run = {**binding, "run_id": run_id, "operation": "bundle" if kind == "bundle" else "apply",
           "dry_run": kind == "dry_run", "started_at": stamp, "ended_at": stamp, "duration_seconds": 0.2,
           "repository_resolved": True, "repository_path": "/foreign/missing/repository", "warnings": [],
           "execution_present": primary.entrypoint_started, "primary_result": primary.as_document(),
           "result_bundle": {"attempted": True, "status": "created", "error": None},
           "process_exit_code": primary.process_exit_code}
    files = {"base/tracked.txt": raw, "changes/staged.patch": b"", "changes/unstaged.patch": b""}
    if kind != "bundle":
        for key in ("base_commit", "state_fingerprint", "fingerprint_algorithm"):
            manifest["actual_" + key] = binding[key]
            manifest["expected_" + key] = ("34" * (20 if object_format == "sha1" else 32)) if key == "base_commit" else binding[key]
    if primary.entrypoint_started:
        files["logs/execution.log"] = b"actual diagnostic bytes\n"
    if dirty:
        data = b"untracked\x00\xff"
        files["untracked/new.bin"] = data
        manifest["untracked_entries"].append({"path": "new.bin", "mode": "100644", "size": len(data),
                                              "sha256": hashlib.sha256(data).hexdigest()})
        # Opaque legacy deltas are not applied or claimed to have an independent hash.
        files["changes/unstaged.patch"] = b"opaque captured delta\n"
    if handoff:
        files["CHAT_INSTRUCTIONS.md"] = b"# Passive reference\n"
        files["environment.json"] = json.dumps({"marker": "patch-harbor-environment", "format_version": 1,
                                                "bundle_type": "Result", "repository_context": binding,
                                                "run_id": run_id, "bundle_suffix": ""}).encode()
    files.update({name: json.dumps(doc).encode() for name, doc in
                  (("manifest.json", manifest), ("context.json", context), ("logs/run.json", run))})
    return attach_pyz(files, reference_runtime()), binding


def write_reference(path, files, *, executable=()):
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name in executable else 0o644)) << 16
            archive.writestr(info, content)


def bound_package(path, binding):
    write_package(path, changes={"patch.json": json.dumps({**MANIFEST, **binding}).encode()})


@lru_cache(maxsize=1)
def reference_runtime():
    # One immutable synthetic data artifact; static readers must never execute it.
    from tests.runtime_pyz_support import inputs
    payloads = inputs()
    payloads['patchharbor/api.py'] = b'raise AssertionError("reference data executed")\n'
    return prepared(payloads)[2]
