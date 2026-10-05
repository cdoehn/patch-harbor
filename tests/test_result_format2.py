"""Versioned Result integrity, inner budgets and conservative consumers."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from patchharbor import api
from patchharbor import result_bundle_publication as publication
from patchharbor import result_runtime
from patchharbor import runtime_wheel as wheel
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.cli import main
from patchharbor.exchange import ExchangeArtifactKind, _classify_content
from patchharbor.exit_status import exit_code_for_error
from patchharbor.errors import (
    registry_error, repository_busy_error, state_mismatch_error, unsupported_repository_state_error,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import read_result_reference
from patchharbor.run_report import PrimaryResult
from tests.result_runtime_support import (
    attach_runtime, descriptor, edit_metadata, format2_entries, replace_wheel, rewrite_wheel,
)
from tests.test_reference_validation import bound_package, edit_document, reference_entries, write_reference
from tests.test_runtime_artifact import prepared, _capture


@pytest.fixture(scope="module")
def canonical(prepared):
    return _capture(prepared)


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("make_error", [state_mismatch_error, repository_busy_error,
                                       registry_error, unsupported_repository_state_error])
def test_categorized_tool_failure_remains_a_reference_and_can_be_published(tmp_path, version, make_error):
    files, binding = reference_entries(kind="mismatch", handoff=True)
    if version == 2:
        files = attach_runtime(files, None)
    primary = PrimaryResult.from_tool_error(make_error("diagnostic failure"))
    edit_document(files, "manifest.json", lambda d: d.update(primary_result=primary.kind.value))
    edit_document(files, "logs/run.json", lambda d: d.update(
        primary_result=primary.as_document(), process_exit_code=primary.process_exit_code))
    # Rejected input may even name a different Git object format. The actual
    # context and its blobs, not the rejected expectation, bind the next patch.
    if make_error is state_mismatch_error:
        edit_document(files, "manifest.json", lambda d: d.update(expected_base_commit="a" * 64))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    facts, _ = read_result_reference(ref)
    assert facts.format_version == version and facts.primary_result == primary
    assert api.validate_patch(patch, reference_bundle=ref).binding_matches
    publication._verify_result_bundle(ref, execution_present=False)
    with pytest.raises(ValueError):
        parse_archive_evidence(ref.read_bytes(), ref)
    # A different numeric cause cannot silently inherit the claimed category.
    edit_document(files, "logs/run.json", lambda d: d["primary_result"].update(patchharbor_error_code=7))
    edit_document(files, "logs/run.json", lambda d: d.update(process_exit_code=7))
    write_reference(ref, files)
    with pytest.raises(api.PatchHarborError):
        read_result_reference(ref)


@pytest.mark.parametrize("status", ["embedded", "unavailable"])
@pytest.mark.parametrize("kind,dirty", [("bundle", False), ("success", False), ("success", True),
                                       ("failure", True), ("dry_run", False)])
def test_format2_reference_preserves_binding_and_separates_success_policy(canonical, tmp_path, status, kind, dirty):
    files, binding = format2_entries(canonical if status == "embedded" else None, kind=kind, dirty=dirty)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    facts, digest = read_result_reference(ref)
    assert facts.format_version == 2 and facts.runtime.status == status
    assert facts.context.dirty is dirty and facts.operation == ("bundle" if kind == "bundle" else "apply")
    assert digest == hashlib.sha256(ref.read_bytes()).hexdigest()
    report = api.validate_patch(patch, reference_bundle=ref)
    assert report.binding_matches and report.context.base_commit == facts.context.base_commit
    assert report.context.state_fingerprint == facts.context.state_fingerprint
    with pytest.raises(FrozenInstanceError):
        facts.runtime.status = "forged"
    if status == "embedded" and kind in {"bundle", "success"} and not dirty:
        assert parse_archive_evidence(ref.read_bytes(), ref).kind == "result_bundle"
    else:
        with pytest.raises(ValueError):
            parse_archive_evidence(ref.read_bytes(), ref)


@pytest.mark.parametrize("reason", sorted(result_runtime.UNAVAILABLE_REASONS))
def test_all_unavailable_reasons_are_readable_without_wheel(tmp_path, reason):
    files, _ = format2_entries(None)
    edit_metadata(files, lambda doc: doc.update(reason=reason, version="1.2.1", requires_python=">=3.12"))
    edit_document(files, "manifest.json", lambda doc: doc["runtime"].update(reason=reason))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    runtime = read_result_reference(ref)[0].runtime
    assert runtime.reason == reason and runtime.wheel is None
    assert runtime.content_id is None and runtime.operations == ()


@pytest.mark.parametrize("fault", [
    "missing_metadata", "missing_wheel", "metadata_hash", "wheel_hash", "extra_runtime", "extra_root",
    "root_unknown_field", "metadata_unknown_field", "bool_metadata_size", "bool_wheel_size",
    "float_redundant_size", "wrong_distribution", "wrong_version", "wrong_python", "wrong_content_id",
    "wrong_algorithm", "wrong_tags", "runtime_dependency", "wrong_provenance", "bool_recipe_version",
    "unknown_capability", "bool_patch_version", "unknown_read_version", "different_status", "missing_handoff",
    "metadata_format_bool", "result_version_bool", "result_version_future", "foreign_wheel_path",
])
def test_corrupt_format2_never_validates(canonical, tmp_path, fault):
    files, binding = format2_entries(canonical)
    doc = json.loads(files["runtime/runtime.json"]); name = doc["wheel"]["path"]
    if fault == "missing_metadata": files.pop("runtime/runtime.json")
    elif fault == "missing_wheel": files.pop(name)
    elif fault == "metadata_hash": files["runtime/runtime.json"] += b" "
    elif fault == "wheel_hash": files[name] += b"extra"
    elif fault == "extra_runtime": files["runtime/extra.bin"] = b"extra"
    elif fault == "extra_root": files["unlisted.bin"] = b"extra"
    elif fault == "root_unknown_field": edit_document(files, "manifest.json", lambda d: d["runtime"].update(unknown=1))
    elif fault == "bool_metadata_size": edit_document(files, "manifest.json", lambda d: d["runtime"]["metadata"].update(size=True))
    elif fault == "bool_wheel_size": edit_document(files, "manifest.json", lambda d: d["runtime"]["wheel"].update(size=True))
    elif fault == "float_redundant_size": edit_metadata(files, lambda d: d["wheel"].update(size=float(len(canonical))))
    elif fault == "wrong_provenance": edit_metadata(files, lambda d: d["provenance"].update(source_commit="a" * 40))
    elif fault == "bool_recipe_version": edit_metadata(files, lambda d: d["provenance"].update(recipe_format_version=True))
    elif fault == "unknown_capability": edit_metadata(files, lambda d: d["capabilities"].update(operations=["execute_anything"]))
    elif fault == "bool_patch_version": edit_metadata(files, lambda d: d["capabilities"].update(patch_formats=[True]))
    elif fault == "unknown_read_version": edit_metadata(files, lambda d: d["capabilities"].update(result_formats=[1, 99]))
    elif fault == "missing_handoff":
        files.pop("CHAT_INSTRUCTIONS.md"); files.pop("environment.json")
    elif fault.startswith("result_version_"):
        edit_document(files, "manifest.json", lambda d: d.update(format_version=True if fault.endswith("bool") else 3))
    elif fault == "foreign_wheel_path":
        item = {**doc["wheel"], "path": "../outside.whl"}
        edit_metadata(files, lambda d: d.update(wheel=item))
        edit_document(files, "manifest.json", lambda d: d["runtime"].update(wheel=item))
    else:
        changes = {
            "metadata_unknown_field": {"unknown": 1}, "wrong_distribution": {"distribution": "foreign"},
            "wrong_version": {"version": "9.9"}, "wrong_python": {"requires_python": ">=3.99"},
            "wrong_content_id": {"content_id": "0" * 64}, "wrong_algorithm": {"content_id_algorithm": "unknown"},
            "wrong_tags": {"tags": ["cp312-none-any"]}, "runtime_dependency": {"runtime_dependencies": ["requests"]},
            "different_status": {"status": "unavailable"}, "metadata_format_bool": {"format_version": True},
        }
        edit_metadata(files, lambda d: d.update(changes[fault]))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    with pytest.raises(api.PatchHarborError) as caught:
        api.validate_patch(patch, reference_bundle=ref)
    assert int(exit_code_for_error(caught.value)) == 4


@pytest.mark.parametrize("fault", ["unknown_reason", "no_warning", "invented_hash", "invented_capabilities", "extra_wheel"])
def test_unavailable_is_a_closed_diagnosis_not_implicit_repair(tmp_path, fault):
    files, _ = format2_entries(None)
    if fault == "no_warning": edit_document(files, "logs/run.json", lambda d: d.update(warnings=[]))
    elif fault == "extra_wheel": files["runtime/extra.whl"] = b"not permitted"
    elif fault == "unknown_reason":
        edit_metadata(files, lambda d: d.update(reason="secret host path"))
        edit_document(files, "manifest.json", lambda d: d["runtime"].update(reason="secret host path"))
    else:
        edit_metadata(files, lambda d: d.update({"content_id": "0" * 64} if fault == "invented_hash" else {"capabilities": {}}))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    with pytest.raises(api.PatchHarborError):
        read_result_reference(ref)


@pytest.mark.parametrize("fault", ["record", "resource", "missing_member", "duplicate", "foreign", "order",
                                    "compressed", "mode", "time", "prefix", "suffix", "local_header"])
def test_rehashed_noncanonical_or_corrupt_wheel_is_rejected(canonical, tmp_path, fault):
    def mutate(items):
        if fault in {"record", "resource"}:
            index = (next(i for i, (info, _) in enumerate(items) if info.filename.endswith("/RECORD"))
                     if fault == "record" else 0)
            info, raw = items[index]; items[index] = (info, raw + b"changed")
        elif fault == "missing_member": items.pop(0)
        elif fault == "duplicate": items.append(items[0])
        elif fault == "foreign":
            from copy import copy
            info = copy(items[0][0]); info.filename = info.orig_filename = "foreign.pth"; items.append((info, b"bad"))
        elif fault == "order": items[0], items[1] = items[1], items[0]
    def transform(info):
        if fault == "compressed": info.compress_type = ZIP_DEFLATED
        elif fault == "mode": info.external_attr = 0o100755 << 16
        elif fault == "time": info.date_time = (2026, 1, 1, 0, 0, 0)
    if fault == "prefix": raw = b"prefix" + canonical
    elif fault == "suffix": raw = canonical + b"suffix"
    elif fault == "local_header":
        raw = bytearray(canonical); raw[10] ^= 1; raw = bytes(raw)
    elif fault == "duplicate":
        with pytest.warns(UserWarning): raw = rewrite_wheel(canonical, mutate)
    else: raw = rewrite_wheel(canonical, mutate, transform=transform)
    files, _ = format2_entries(canonical); replace_wheel(files, raw)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    with pytest.raises(api.PatchHarborError): read_result_reference(ref)


def test_inner_bytes_share_the_remaining_outer_request_budget(canonical, tmp_path, monkeypatch):
    files, _ = format2_entries(canonical)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    outer = sum(map(len, files.values()))
    with ZipFile(BytesIO(canonical)) as archive:
        inner = sum(info.file_size for info in archive.infolist())
    policy = replace(DEFAULT_RESOURCE_POLICY, max_zip_total_bytes=outer + inner)
    assert read_result_reference(ref, resource_policy=policy)[0].runtime.status == "embedded"
    original = result_runtime._read_wheel
    def inspect_only(*args, **kwargs):
        with monkeypatch.context() as guard:
            guard.setattr(ZipFile, "read", lambda *a, **k: pytest.fail("over-budget inner member was read"))
            return original(*args, **kwargs)
    monkeypatch.setattr(result_runtime, "_read_wheel", inspect_only)
    with pytest.raises(api.PatchHarborError):
        read_result_reference(ref, resource_policy=replace(policy, max_zip_total_bytes=outer + inner - 1))


def test_inner_entry_count_uses_request_limit_before_resource_reads(canonical, tmp_path, monkeypatch):
    files, _ = format2_entries(canonical)
    with ZipFile(BytesIO(canonical)) as archive:
        count = len(archive.infolist())
    assert count > len(files) + 1
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    policy = replace(DEFAULT_RESOURCE_POLICY, max_zip_entries=count)
    assert read_result_reference(ref, resource_policy=policy)[0].runtime.status == "embedded"
    original = result_runtime._read_wheel
    def inspect_only(*args, **kwargs):
        with monkeypatch.context() as guard:
            guard.setattr(ZipFile, "read", lambda *a, **k: pytest.fail("over-budget inventory was read"))
            return original(*args, **kwargs)
    monkeypatch.setattr(result_runtime, "_read_wheel", inspect_only)
    with pytest.raises(api.PatchHarborError):
        read_result_reference(ref, resource_policy=replace(policy, max_zip_entries=count - 1))


def test_metadata_budget_is_enforced_before_json_parse(tmp_path, monkeypatch):
    files, _ = format2_entries(None)
    name = "runtime/runtime.json"
    files[name] += b" " * (result_runtime.MAX_METADATA_BYTES + 1 - len(files[name]))
    edit_document(files, "manifest.json", lambda doc: doc["runtime"].update(metadata=descriptor(name, files[name])))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    monkeypatch.setattr(result_runtime, "parse_json_document", lambda *a: pytest.fail("oversize runtime JSON parsed"))
    with pytest.raises(api.PatchHarborError): read_result_reference(ref)


def test_repository_runtime_path_is_not_the_embedded_namespace(canonical, tmp_path):
    files, binding = format2_entries(canonical)
    files["base/runtime/runtime.json"] = files.pop("base/tracked.txt")
    edit_document(files, "manifest.json", lambda doc: doc["base_entries"][0].update(path="runtime/runtime.json"))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    assert api.validate_patch(patch, reference_bundle=ref).binding_matches


@pytest.mark.parametrize("version", [1, 2])
def test_snapshot_unicode_paths_work_for_classifier_and_archive_without_relaxing_patches(canonical, tmp_path, version):
    from patchharbor.result_reader import read_result_or_patch_payloads
    from patchharbor.zip_payloads import ZipPayloadError
    files, binding = format2_entries(canonical) if version == 2 else reference_entries()
    name = "base/runtime/Grüße dir/Datei.py"
    files[name] = files.pop("base/tracked.txt")
    edit_document(files, "manifest.json", lambda doc: doc["base_entries"][0].update(path=name.removeprefix("base/")))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    classification = _classify_content(ref, ref.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY)
    assert classification.kind is ExchangeArtifactKind.RESULT_BUNDLE
    assert parse_archive_evidence(ref.read_bytes(), ref).base_entries[0][0] == name.removeprefix("base/")
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    with ZipFile(patch, "a") as archive:
        archive.writestr(name, b"not a permitted patch payload path")
    assert _classify_content(patch, patch.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY).kind is ExchangeArtifactKind.OTHER
    with pytest.raises(ZipPayloadError): read_result_or_patch_payloads(patch.read_bytes())


def test_reader_does_not_materialize_import_execute_or_write_runtime(canonical, tmp_path, monkeypatch):
    files, binding = format2_entries(canonical)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    def forbidden(*args, **kwargs): pytest.fail("Result reader crossed a runtime execution/write boundary")
    monkeypatch.setattr(wheel, "materialize", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden); monkeypatch.setattr(subprocess, "Popen", forbidden)
    original_open = os.open
    def readonly(path, flags, *args, **kwargs):
        assert not flags & (os.O_CREAT | os.O_TRUNC | os.O_RDWR | os.O_WRONLY)
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", readonly)
    assert api.validate_patch(patch, reference_bundle=ref).binding_matches
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("version", [1, 2, 3, True])
def test_result_classification_is_only_a_type_hint_and_never_a_patch(canonical, tmp_path, version):
    files, _ = format2_entries(canonical)
    edit_document(files, "manifest.json", lambda doc: doc.update(format_version=version))
    ref = tmp_path / "looks-like-a-patch.zip"; write_reference(ref, files)
    classification = _classify_content(ref, ref.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY)
    assert classification.kind is ExchangeArtifactKind.RESULT_BUNDLE and classification.package is None
    assert _classify_content(tmp_path / "wheel.zip", canonical, resource_policy=DEFAULT_RESOURCE_POLICY).kind is ExchangeArtifactKind.OTHER


@pytest.mark.parametrize("status", ["embedded", "unavailable"])
def test_publication_verifies_format2_bytes_and_detects_corruption(canonical, tmp_path, status):
    files, _ = format2_entries(canonical if status == "embedded" else None)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    publication._verify_result_bundle(ref, execution_present=False)
    files["runtime/runtime.json"] += b" "
    write_reference(ref, files)
    with pytest.raises(api.PatchHarborError) as caught:
        publication._verify_result_bundle(ref, execution_present=False)
    assert caught.value.reason is api.FailureReason.RESULT_BUNDLE_ERROR


def test_cli_reference_validation_accepts_format2(canonical, tmp_path):
    files, binding = format2_entries(canonical)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    out = StringIO()
    assert main(["validate", str(patch), "--reference-bundle", str(ref), "--json"], stdout=out, stderr=StringIO()) == 0
    doc = json.loads(out.getvalue())
    assert doc["success"] is True and doc["result"]["binding_matches"] is True


@pytest.mark.e2e
@pytest.mark.parametrize("state", ["embedded", "unavailable", "corrupt", "future"])
def test_real_recovery_consumes_only_complete_successful_format2_evidence(canonical, tmp_path, state):
    from tests.test_exchange_recovery_e2e import _pending, _result, _edit_record
    from tests.test_exchange_archive_e2e import _rewrite, _scan, ARCHIVE
    from tests.test_exchange_e2e import _identity_record
    from tests.registration_support import git
    env, exchange, repo, _, patch, record = _pending(tmp_path)
    result = _result(exchange, record)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    patch_bytes = patch.read_bytes()
    def upgrade(files):
        files.update(attach_runtime(files, None if state == "unavailable" else canonical))
        if state == "corrupt": files["runtime/runtime.json"] += b"changed"
        elif state == "future": edit_document(files, "manifest.json", lambda doc: doc.update(format_version=3))
    _rewrite(result, upgrade)
    # Model the fixture producer's locally pinned replacement bytes; all actual
    # recovery checks still run, including conservative unavailable evidence.
    _edit_record(env, patch, lambda row: row.update(result_sha256=hashlib.sha256(result.read_bytes()).hexdigest()))
    assert _scan(repo, env, automatic=True).returncode == 10
    saved = _identity_record(env, patch, hashlib.sha256(patch_bytes).hexdigest())
    assert saved["apply_status"] == ("succeeded" if state == "embedded" else "attempted")
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == head
    assert result.exists()
    if state == "embedded":
        assert saved["completed_commit"] == head and not patch.exists()
        assert (exchange / ARCHIVE / patch.name).read_bytes() == patch_bytes
    else:
        assert saved["completed_commit"] is None and patch.read_bytes() == patch_bytes
