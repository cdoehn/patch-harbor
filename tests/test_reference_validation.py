"""Reference integrity and explicit binding contracts, without live history."""
from dataclasses import FrozenInstanceError
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import stat
import subprocess
from zipfile import ZipFile, ZipInfo

import pytest

from patchharbor import api
from patchharbor.archive_evidence import CLEAN_FINGERPRINT, parse_archive_evidence
from patchharbor.cli import main
from patchharbor.exit_status import exit_code_for_error
from patchharbor.result_reader import read_result_reference
from patchharbor.run_report import PrimaryResult
from tests.test_patch_inspection import MANIFEST, write_package


def reference_entries(*, kind="bundle", dirty=False, object_format="sha1", handoff=False):
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
    manifest = {"marker": "patch-harbor-result-bundle", "format_version": 1, **binding,
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
    return files, binding


def write_reference(path, files, *, executable=()):
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name in executable else 0o644)) << 16
            archive.writestr(info, content)


def bound_package(path, binding):
    write_package(path, changes={"patch.json": json.dumps({**MANIFEST, **binding}).encode()})


def edit_document(files, name, mutate):
    document = json.loads(files[name]); mutate(document)
    files[name] = json.dumps(document).encode()


@pytest.mark.parametrize("kind", ["bundle", "success", "dry_run", "failure", "mismatch", "timeout", "interrupted"])
@pytest.mark.parametrize("dirty", [False, True])
def test_valid_reference_is_independent_of_clean_success_policy(tmp_path, kind, dirty):
    files, binding = reference_entries(kind=kind, dirty=dirty, handoff=True)
    reference = tmp_path / "result.zip"; write_reference(reference, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    report = api.validate_patch(patch, reference_bundle=reference)
    assert report.scope is api.PatchValidationScope.REFERENCE and report.binding_matches is True
    assert report.reference_sha256 == hashlib.sha256(reference.read_bytes()).hexdigest()
    assert report.context.dirty is dirty and report.context.repository_path == "/foreign/missing/repository"
    assert str(report.context.base_commit) == binding["base_commit"]
    assert {"authenticity", "live_repository_state", "local_registration", "legacy_delta_log_hashes",
            "reconstructed_state_fingerprint", "tests", "ci", "replay"} <= set(report.not_checked)
    assert "repository_binding" not in report.not_checked
    with pytest.raises(FrozenInstanceError):
        report.context.dirty = False
    if dirty or kind not in ("bundle", "success"):
        with pytest.raises(ValueError):
            parse_archive_evidence(reference.read_bytes(), reference)
    else:
        assert parse_archive_evidence(reference.read_bytes(), reference).kind == "result_bundle"


@pytest.mark.parametrize("object_format", ["sha1", "sha256"])
def test_reference_checks_blob_object_format_and_portable_snapshot_names(tmp_path, object_format):
    files, binding = reference_entries(object_format=object_format)
    files["base/Grüße dir/script.sh"] = files.pop("base/tracked.txt")
    def change(doc):
        doc["base_entries"][0].update(path="Grüße dir/script.sh", git_mode="100755")
    edit_document(files, "manifest.json", change)
    reference = tmp_path / "result.zip"; write_reference(reference, files, executable=("base/Grüße dir/script.sh",))
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    assert api.validate_patch(patch, reference_bundle=reference).context.base_commit.object_format.value == object_format


def test_reference_does_not_read_registry_run_git_or_write_files(tmp_path, monkeypatch):
    files, binding = reference_entries(kind="failure", dirty=True)
    reference = tmp_path / "result.zip"; write_reference(reference, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    def forbidden(*args, **kwargs):
        pytest.fail("reference crossed a process or registry boundary")
    import patchharbor.registry as registry
    import patchharbor.repository_state as state
    monkeypatch.setattr(registry, "load_registry", forbidden)
    monkeypatch.setattr(state, "registration_user_paths", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    original_open = os.open
    def read_only(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", read_only)
    assert api.validate_patch(patch, reference_bundle=reference).binding_matches
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("field,value", [("repo_id", "12345678-1234-4567-8123-123456789abc"),
                                         ("base_commit", "ff" * 20), ("state_fingerprint", "ff" * 8)])
def test_reference_binding_mismatch_is_error_nine_in_api_and_cli(tmp_path, field, value):
    files, binding = reference_entries(kind="failure")
    reference = tmp_path / "result.zip"; write_reference(reference, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, {**binding, field: value})
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, reference_bundle=reference)
    assert int(exit_code_for_error(caught.value)) == 9
    out = StringIO()
    assert main(["validate", str(patch), "--reference-bundle", str(reference), "--json"], stdout=out, stderr=StringIO()) == 9
    assert json.loads(out.getvalue())["result"] is None


def test_expected_context_is_never_used_as_actual_binding(tmp_path):
    files, binding = reference_entries(kind="mismatch", dirty=True)
    reference = tmp_path / "result.zip"; write_reference(reference, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, {**binding, "base_commit": "34" * 20})
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, reference_bundle=reference)
    assert int(exit_code_for_error(caught.value)) == 9


@pytest.mark.parametrize("field", ["repository", "reference_bundle"])
@pytest.mark.parametrize("value,error", [(b"bad", TypeError), (42, TypeError), ("", ValueError), ("nul\0", ValueError)])
def test_binding_arguments_fail_before_io(monkeypatch, field, value, error):
    import patchharbor.application as app
    monkeypatch.setattr(app, "validate_patch", lambda *a, **k: pytest.fail("invalid arguments reached Core"))
    with pytest.raises(error):
        api.validate_patch("missing.zip", **{field: value})


def test_json_reference_uses_public_api_and_foreign_windows_path(tmp_path, monkeypatch):
    files, binding = reference_entries()
    edit_document(files, "logs/run.json", lambda d: d.update(repository_path="C:\\foreign\\repo"))
    reference = tmp_path / "result.zip"; write_reference(reference, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    calls = []
    original = api.validate_patch
    def observed(*args, **kwargs):
        calls.append(kwargs.get("reference_bundle")); return original(*args, **kwargs)
    monkeypatch.setattr(api, "validate_patch", observed)
    out, err = StringIO(), StringIO()
    assert main(["validate", str(patch), "--reference-bundle", str(reference), "--json", "-v"], stdout=out, stderr=err) == 0
    result = json.loads(out.getvalue())
    assert result["output_version"] == 2 and result["success"] and result["error"] is None
    assert result["result"]["context"]["repository_path"] == "C:\\foreign\\repo"
    assert calls == [reference] and err.getvalue() == ""


@pytest.mark.parametrize("fault", ["blob", "untracked", "extra", "missing", "version", "bool_size", "algorithm", "run_context"])
def test_corrupt_reference_never_produces_success(tmp_path, fault):
    files, binding = reference_entries(dirty=True)
    if fault == "blob": files["base/tracked.txt"] = b"bad"
    elif fault == "untracked": files["untracked/new.bin"] = b"bad"
    elif fault == "extra": files["extra.txt"] = b"extra"
    elif fault == "missing": files.pop("changes/staged.patch")
    elif fault == "version": edit_document(files, "manifest.json", lambda d: d.update(format_version=2))
    elif fault == "bool_size": edit_document(files, "manifest.json", lambda d: d["base_entries"][0].update(size=True))
    elif fault == "algorithm":
        for name in ("manifest.json", "context.json", "logs/run.json"):
            edit_document(files, name, lambda d: d.update(fingerprint_algorithm="unknown"))
    else: edit_document(files, "logs/run.json", lambda d: d.update(base_commit="34" * 20))
    reference = tmp_path / "result.zip"; write_reference(reference, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, reference_bundle=reference)
    assert int(exit_code_for_error(caught.value)) == 4


@pytest.mark.e2e
@pytest.mark.parametrize("dirty", [False, True])
def test_real_registered_repository_and_real_generated_result_agree(tmp_path, monkeypatch, dirty):
    from tests.registration_support import create_repository, set_isolated_user_environment, git
    set_isolated_user_environment(monkeypatch, tmp_path / "user")
    repo = create_repository(tmp_path / "repo")
    api.register(repo)
    if dirty:
        (repo / "tracked.txt").write_bytes(b"staged\n"); git(repo, "add", "tracked.txt")
        (repo / "tracked.txt").write_bytes(b"unstaged\n")
        (repo / "Grüße file.txt").write_text("untracked")
    context = api.context(repo)
    binding = {k: str(getattr(context, k)) for k in ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")}
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    before = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    report = api.validate_patch(patch, repository=repo)
    assert report.scope is api.PatchValidationScope.REPOSITORY and report.context == context
    assert report.reference_sha256 is None and report.binding_matches
    assert {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()} == before
    generated = api.bundle(repo, output_directory=tmp_path / "results")
    ref = api.validate_patch(patch, reference_bundle=generated.report.result_bundle.path)
    assert ref.context.dirty == context.dirty
    assert ref.context.base_commit == context.base_commit
    assert ref.context.state_fingerprint == context.state_fingerprint
    (repo / "later.txt").write_text("different state")
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, repository=repo)
    assert int(exit_code_for_error(caught.value)) == 9
