"""PP-01: one immutable, fully verified reference for later pack orchestration."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

from patchharbor import api
from patchharbor import patch_inspection as inspection
from patchharbor import result_reader as reader
from patchharbor.errors import FailureReason, PatchHarborError
from patchharbor.exit_status import exit_code_for_error
from patchharbor.json_document import parse_json_document
from patchharbor.platform.filesystem import FileChangedDuringRead
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from tests.result_runtime_support import attach_runtime
from tests.test_reference_validation import (
    bound_package, edit_document, reference_entries, write_reference,
)


def _reference(tmp_path, *, kind="bundle", dirty=False, handoff=True, version=1, suffix=".txt"):
    files, binding = reference_entries(kind=kind, dirty=dirty, handoff=handoff)
    edit_document(files, "context.json", lambda doc: doc.update(bundle_suffix=suffix))
    if handoff:
        edit_document(files, "environment.json", lambda doc: doc.update(
            bundle_suffix=suffix, repository_path="/foreign/missing/repository",
            captured_at="2026-10-03T12:00:00Z", repository_name="recorded-repo",
            exchange_directory="/foreign/exchange", output_directory=None,
            runtime={"system": "ForeignOS", "python_version": "3.12.0", "unknown": None,
                     "extra": {"items": [1, {"nested": True}]}}))
    if version == 2:
        files = attach_runtime(files, None)
    path = tmp_path / "reference.zip"
    write_reference(path, files)
    return path, files, binding


@pytest.mark.parametrize("kind", ["bundle", "success", "dry_run", "failure", "mismatch", "timeout", "interrupted"])
@pytest.mark.parametrize("dirty", [False, True])
@pytest.mark.parametrize("handoff", [False, True])
def test_capture_retains_actual_binding_suffix_and_exact_handoff(tmp_path, kind, dirty, handoff):
    path, files, binding = _reference(tmp_path, kind=kind, dirty=dirty, handoff=handoff)
    captured = reader.capture_result_reference(path)
    assert captured.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert captured.bundle_suffix == ".txt"
    assert captured.facts.context.dirty is dirty
    for name, value in binding.items():
        assert str(getattr(captured.facts.context, name)) == value
    if kind != "bundle":
        assert captured.facts.expected.base_commit != captured.facts.context.base_commit
    assert captured.facts.handoff_present is handoff
    if handoff:
        assert captured.handoff.instructions == files["CHAT_INSTRUCTIONS.md"]
        assert captured.handoff.environment == files["environment.json"]
    else:
        assert captured.handoff is None
    legacy = reader.read_result_reference(path)
    assert type(legacy) is tuple and len(legacy) == 2
    assert legacy == (captured.facts, captured.sha256)


def test_missing_legacy_suffix_is_empty_and_does_not_invent_environment(tmp_path):
    path, files, _ = _reference(tmp_path, handoff=False)
    edit_document(files, "context.json", lambda doc: doc.pop("bundle_suffix"))
    write_reference(path, files)
    captured = reader.capture_result_reference(path)
    assert captured.bundle_suffix == "" and captured.handoff is None


def test_capture_and_passive_bytes_cannot_be_changed_by_a_renderer(tmp_path):
    path, _, _ = _reference(tmp_path)
    captured = reader.capture_result_reference(path)
    with pytest.raises(FrozenInstanceError):
        captured.bundle_suffix = ".wrong"
    with pytest.raises(FrozenInstanceError):
        captured.facts.context.repository_path = "/local"
    with pytest.raises(FrozenInstanceError):
        captured.handoff.environment = b"{}"
    document = parse_json_document(captured.handoff.environment)
    document["runtime"]["extra"]["items"][1]["nested"] = False
    fresh = parse_json_document(captured.handoff.environment)
    assert fresh["runtime"]["extra"]["items"][1]["nested"] is True


@pytest.mark.parametrize("kind,dirty", [("bundle", False), ("success", True), ("failure", True), ("dry_run", False)])
def test_unavailable_runtime_is_still_a_complete_reference(tmp_path, kind, dirty):
    path, files, _ = _reference(tmp_path, version=2, kind=kind, dirty=dirty)
    captured = reader.capture_result_reference(path)
    assert captured.facts.format_version == 2
    assert captured.facts.runtime.status == "unavailable"
    assert captured.facts.warnings
    assert captured.handoff.environment == files["environment.json"]


@pytest.mark.parametrize("fault", ["runtime_hash", "extra_runtime", "snapshot_hash", "handoff_suffix", "unknown_algorithm"])
def test_capture_never_uses_weaker_repository_only_diagnostics(tmp_path, monkeypatch, fault):
    path, files, _ = _reference(tmp_path, version=2)
    if fault == "runtime_hash":
        files["runtime/runtime.json"] += b" "
    elif fault == "extra_runtime":
        files["runtime/extra.bin"] = b"unaccounted"
    elif fault == "snapshot_hash":
        files["base/tracked.txt"] += b"changed"
    elif fault == "handoff_suffix":
        edit_document(files, "environment.json", lambda doc: doc.update(bundle_suffix=".different"))
    else:
        for name in ("manifest.json", "context.json", "logs/run.json"):
            edit_document(files, name, lambda doc: doc.update(fingerprint_algorithm="unknown-v1"))
    write_reference(path, files)
    def forbidden(*args, **kwargs):
        pytest.fail("native capture reached the weaker diagnostics fallback")
    monkeypatch.setattr(reader, "_parse_repository_payloads", forbidden)
    with pytest.raises(PatchHarborError) as caught:
        reader.capture_result_reference(path)
    assert caught.value.reason is FailureReason.SOURCE_ERROR
    assert int(exit_code_for_error(caught.value)) == 4


def test_one_capture_keeps_handoff_and_hash_when_path_is_replaced(tmp_path, monkeypatch):
    path, files, binding = _reference(tmp_path)
    original_bytes = path.read_bytes()
    replacement = dict(files)
    edit_document(replacement, "context.json", lambda doc: doc.update(bundle_suffix=".other"))
    edit_document(replacement, "environment.json", lambda doc: doc.update(bundle_suffix=".other", repository_name="other"))
    other = tmp_path / "replacement.zip"
    write_reference(other, replacement)
    actual_read = reader.read_stable_regular_file_with_sha256
    calls = []
    def capture_then_replace(target, **kwargs):
        calls.append(target)
        result = actual_read(target, **kwargs)
        os.replace(other, path)
        return result
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", capture_then_replace)
    captured = reader.capture_result_reference(path)
    assert calls == [path]
    assert captured.bundle_suffix == ".txt"
    assert captured.handoff.environment == files["environment.json"]
    assert captured.sha256 == hashlib.sha256(original_bytes).hexdigest()
    patch = tmp_path / "patch.zip"
    bound_package(patch, binding)
    path.unlink()
    report = inspection.validate_patch_against_reference(patch, captured)
    assert calls == [path]  # no later reference-path read for end validation
    assert report.reference_sha256 == captured.sha256
    assert report.binding_matches is True


def test_unstable_capture_is_one_source_error_without_retry(tmp_path, monkeypatch):
    path, _, _ = _reference(tmp_path)
    calls = []
    def changed(*args, **kwargs):
        calls.append(args)
        raise FileChangedDuringRead("changed")
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", changed)
    with pytest.raises(PatchHarborError) as caught:
        reader.capture_result_reference(path)
    assert len(calls) == 1 and caught.value.reason is FailureReason.SOURCE_ERROR


def test_capture_forwards_publication_identity_and_existing_budgets(tmp_path, monkeypatch):
    path, _, _ = _reference(tmp_path)
    identity = path.stat()
    policy = replace(DEFAULT_RESOURCE_POLICY, max_input_artifact_bytes=16 * 1024 * 1024)
    actual_read = reader.read_stable_regular_file_with_sha256
    actual_parse = reader.parse_result_payloads
    reads, parses = [], []
    def observed_read(target, **kwargs):
        reads.append((target, kwargs))
        return actual_read(target, **kwargs)
    def observed_parse(payloads, **kwargs):
        parses.append(kwargs)
        return actual_parse(payloads, **kwargs)
    monkeypatch.setattr(reader, "read_stable_regular_file_with_sha256", observed_read)
    monkeypatch.setattr(reader, "parse_result_payloads", observed_parse)
    reader.read_result_reference(path, expected_identity=identity, resource_policy=policy)
    assert len(reads) == 1 and reads[0][0] == path
    assert reads[0][1]["expected_identity"] is identity
    assert reads[0][1]["retained_content_limit"] == policy.max_input_artifact_bytes
    assert reads[0][1]["max_bytes"] == policy.max_input_artifact_bytes
    assert len(parses) == 1 and parses[0]["resource_policy"] is policy


@pytest.mark.parametrize("limit", ["max_input_artifact_bytes", "max_zip_total_bytes", "max_zip_entries"])
def test_capture_does_not_open_an_extra_resource_budget(tmp_path, limit):
    path, _, _ = _reference(tmp_path)
    policy = replace(DEFAULT_RESOURCE_POLICY, warning_bytes=1, **{limit: 1})
    with pytest.raises(PatchHarborError) as caught:
        reader.capture_result_reference(path, resource_policy=policy)
    assert caught.value.reason is FailureReason.SOURCE_ERROR


def test_internal_and_public_reference_validation_have_identical_facts(tmp_path):
    path, _, binding = _reference(tmp_path, version=2, kind="failure", dirty=True)
    captured = reader.capture_result_reference(path)
    patch = tmp_path / "patch.zip"
    bound_package(patch, binding)
    public = api.validate_patch(patch, reference_bundle=path)
    internal = inspection.validate_patch_against_reference(patch, captured)
    assert replace(internal, checked_at=public.checked_at) == public


@pytest.mark.parametrize("field,value", [("repo_id", "12345678-1234-4567-8123-123456789abc"),
                                         ("base_commit", "ff" * 20), ("state_fingerprint", "ff" * 8)])
def test_internal_validation_does_not_skip_any_binding_comparison(tmp_path, field, value):
    path, _, binding = _reference(tmp_path)
    captured = reader.capture_result_reference(path)
    patch = tmp_path / "patch.zip"
    bound_package(patch, {**binding, field: value})
    with pytest.raises(PatchHarborError) as caught:
        inspection.validate_patch_against_reference(patch, captured)
    assert int(exit_code_for_error(caught.value)) == 9


def test_internal_validation_uses_actual_package_bytes_and_original_error_categories(tmp_path):
    from tests.test_patch_inspection import MANIFEST, write_package
    path, _, binding = _reference(tmp_path)
    captured = reader.capture_result_reference(path)
    patch = tmp_path / "patch.zip"
    bound_package(patch, binding)
    first = inspection.validate_patch_against_reference(patch, captured)
    write_package(patch, changes={"patch.json": json.dumps({**MANIFEST, **binding}).encode(),
                                  "docs/data.bin": b"new payload"})
    second = inspection.validate_patch_against_reference(patch, captured)
    assert second.inspection.package_sha256 == hashlib.sha256(patch.read_bytes()).hexdigest()
    assert first.inspection.package_sha256 != second.inspection.package_sha256
    assert first.reference_sha256 == second.reference_sha256
    write_package(patch, changes={"patch.json": json.dumps({**MANIFEST, **binding}).encode(),
                                  "run.sh": b"#!/usr/bin/env bash\ntrue\n"})
    with pytest.raises(PatchHarborError) as caught:
        inspection.validate_patch_against_reference(patch, captured)
    assert int(exit_code_for_error(caught.value)) == 3


def test_internal_end_validation_honours_package_budget(tmp_path):
    path, _, binding = _reference(tmp_path)
    captured = reader.capture_result_reference(path)
    patch = tmp_path / "patch.zip"
    bound_package(patch, binding)
    policy = replace(DEFAULT_RESOURCE_POLICY, warning_bytes=1, max_input_artifact_bytes=1)
    with pytest.raises(PatchHarborError) as caught:
        inspection.validate_patch_against_reference(patch, captured, resource_policy=policy)
    assert int(exit_code_for_error(caught.value)) == 4


def test_capture_and_internal_validation_are_read_only_without_git_registry_or_network(tmp_path, monkeypatch):
    import patchharbor.registry as registry
    import patchharbor.repository_state as state
    path, _, binding = _reference(tmp_path, version=2)
    patch = tmp_path / "patch.zip"
    bound_package(patch, binding)
    before = {item.name: item.read_bytes() for item in tmp_path.iterdir()}
    def forbidden(*args, **kwargs):
        pytest.fail("static reference work crossed a side-effect boundary")
    monkeypatch.setattr(registry, "load_registry", forbidden)
    monkeypatch.setattr(state, "registration_user_paths", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    original_open = os.open
    def read_only(target, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return original_open(target, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", read_only)
    original_resolve = Path.resolve
    def no_foreign_resolution(target, *args, **kwargs):
        assert not str(target).startswith("/foreign/")
        return original_resolve(target, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", no_foreign_resolution)
    captured = reader.capture_result_reference(path)
    assert inspection.validate_patch_against_reference(patch, captured).binding_matches
    assert {item.name: item.read_bytes() for item in tmp_path.iterdir()} == before
