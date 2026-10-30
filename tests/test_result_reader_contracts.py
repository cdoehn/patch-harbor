"""Result-3 reader boundaries retained from the retired format-2 test suite."""
from dataclasses import FrozenInstanceError, replace
from io import BytesIO, StringIO
import hashlib
import json
import os
import subprocess
from zipfile import ZipFile
import pytest
from patchharbor import api, result_pyz, runtime_pyz as pyz
from patchharbor import result_bundle_publication as publication
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.cli import main
from patchharbor.exchange import ExchangeArtifactKind, _classify_content
from patchharbor.errors import registry_error, repository_busy_error, state_mismatch_error, unsupported_repository_state_error
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import read_result_reference
from patchharbor.run_report import PrimaryResult
from tests.result_pyz_support import canonical, format3
from tests.result_runtime_support import descriptor, edit_metadata
from tests.reference_support import bound_package, edit_document, reference_runtime, write_reference


@pytest.mark.parametrize("make_error", [state_mismatch_error, repository_busy_error,
                                       registry_error, unsupported_repository_state_error])
def test_categorized_tool_failure_remains_a_reference_and_can_be_published(canonical, tmp_path, make_error):
    files, binding = format3(canonical, kind="mismatch")
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
    assert facts.format_version == 3 and facts.primary_result == primary
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
def test_format3_reference_preserves_binding_and_separates_success_policy(canonical, tmp_path, status, kind, dirty):
    files, binding = format3(canonical if status == "embedded" else None, kind=kind, dirty=dirty)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    facts, digest = read_result_reference(ref)
    assert facts.format_version == 3 and facts.runtime.status == status
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

def test_inner_bytes_share_the_remaining_outer_request_budget(canonical, tmp_path, monkeypatch):
    files, _ = format3(canonical)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    outer = sum(map(len, files.values()))
    with ZipFile(BytesIO(canonical)) as archive:
        inner = sum(info.file_size for info in archive.infolist())
    policy = replace(DEFAULT_RESOURCE_POLICY, max_zip_total_bytes=outer + inner)
    assert read_result_reference(ref, resource_policy=policy)[0].runtime.status == "embedded"
    original = pyz.read_pyz
    def inspect_only(*args, **kwargs):
        with monkeypatch.context() as guard:
            guard.setattr(ZipFile, "read", lambda *a, **k: pytest.fail("over-budget inner member was read"))
            return original(*args, **kwargs)
    monkeypatch.setattr(pyz, "read_pyz", inspect_only)
    with pytest.raises(api.PatchHarborError):
        read_result_reference(ref, resource_policy=replace(policy, max_zip_total_bytes=outer + inner - 1))

def test_inner_entry_count_uses_request_limit_before_resource_reads(canonical, tmp_path, monkeypatch):
    files, _ = format3(canonical)
    with ZipFile(BytesIO(canonical)) as archive:
        count = len(archive.infolist())
    assert count > len(files)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    policy = replace(DEFAULT_RESOURCE_POLICY, max_zip_entries=count)
    assert read_result_reference(ref, resource_policy=policy)[0].runtime.status == "embedded"
    original = pyz.read_pyz
    def inspect_only(*args, **kwargs):
        with monkeypatch.context() as guard:
            guard.setattr(ZipFile, "read", lambda *a, **k: pytest.fail("over-budget inventory was read"))
            return original(*args, **kwargs)
    monkeypatch.setattr(pyz, "read_pyz", inspect_only)
    with pytest.raises(api.PatchHarborError):
        read_result_reference(ref, resource_policy=replace(policy, max_zip_entries=count - 1))

def test_metadata_budget_is_enforced_before_json_parse(tmp_path, monkeypatch):
    files, _ = format3(None)
    name = "runtime/runtime.json"
    files[name] += b" " * (result_pyz.MAX_METADATA_BYTES + 1 - len(files[name]))
    edit_document(files, "manifest.json", lambda doc: doc["runtime"].update(metadata=descriptor(name, files[name])))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    monkeypatch.setattr(result_pyz, "parse_json_document", lambda *a: pytest.fail("oversize runtime JSON parsed"))
    with pytest.raises(api.PatchHarborError): read_result_reference(ref)

def test_repository_runtime_path_is_not_the_embedded_namespace(canonical, tmp_path):
    files, binding = format3(canonical)
    files["base/runtime/runtime.json"] = files.pop("base/tracked.txt")
    edit_document(files, "manifest.json", lambda doc: doc["base_entries"][0].update(path="runtime/runtime.json"))
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    assert api.validate_patch(patch, reference_bundle=ref).binding_matches

def test_snapshot_unicode_paths_work_for_classifier_and_archive_without_relaxing_patches(canonical, tmp_path):
    from patchharbor.result_reader import read_result_or_patch_payloads
    from patchharbor.zip_payloads import ZipPayloadError
    files, binding = format3(canonical)
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

def test_reader_does_not_import_execute_or_write_runtime(tmp_path, monkeypatch):
    files, binding = format3(reference_runtime())
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    def forbidden(*args, **kwargs): pytest.fail("Result reader crossed a runtime execution/write boundary")
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
    files, _ = format3(canonical)
    edit_document(files, "manifest.json", lambda doc: doc.update(format_version=version))
    ref = tmp_path / "looks-like-a-patch.zip"; write_reference(ref, files)
    classification = _classify_content(ref, ref.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY)
    assert classification.kind is ExchangeArtifactKind.RESULT_BUNDLE and classification.package is None
    assert _classify_content(tmp_path / "runtime.pyz", canonical, resource_policy=DEFAULT_RESOURCE_POLICY).kind is ExchangeArtifactKind.OTHER

@pytest.mark.parametrize("status", ["embedded", "unavailable"])
def test_publication_verifies_format3_bytes_and_detects_corruption(canonical, tmp_path, status):
    files, _ = format3(canonical if status == "embedded" else None)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    publication._verify_result_bundle(ref, execution_present=False)
    files["runtime/runtime.json"] += b" "
    write_reference(ref, files)
    with pytest.raises(api.PatchHarborError) as caught:
        publication._verify_result_bundle(ref, execution_present=False)
    assert caught.value.reason is api.FailureReason.RESULT_BUNDLE_ERROR

def test_cli_reference_validation_accepts_format3(canonical, tmp_path):
    files, binding = format3(canonical)
    ref = tmp_path / "result.zip"; write_reference(ref, files)
    patch = tmp_path / "patch.zip"; bound_package(patch, binding)
    out = StringIO()
    assert main(["validate", str(patch), "--reference-bundle", str(ref), "--json"], stdout=out, stderr=StringIO()) == 0
    doc = json.loads(out.getvalue())
    assert doc["success"] is True and doc["result"]["binding_matches"] is True
