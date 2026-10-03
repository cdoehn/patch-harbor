"""Read-only public package contracts, independent of a Git repository."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
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
import patchharbor.application as application
from patchharbor.cli import main
from patchharbor.exit_status import exit_code_for_error
from patchharbor.patch_inspection import inspect_patch
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY


MANIFEST = {
    "marker": "patch-harbor", "format_version": 1,
    "repo_id": "01234567-89ab-4cde-8fab-0123456789ab",
    "base_commit": "12" * 20, "state_fingerprint": "0123456789abcdef",
    "fingerprint_algorithm": "patchharbor-state-v1", "entrypoint": "run.sh",
}
SCRIPT = (b"#!/usr/bin/env bash\n# PATCHHARBOR\n"
          b"# PATCHHARBOR MESSAGE Notice START\n# Facts only\n# PATCHHARBOR MESSAGE Notice END\n"
          b"printf executed > SHOULD_NOT_EXIST\n")


def write_package(path: Path, *, changes: dict[str, bytes] | None = None,
                  handoff: bool = False) -> dict[str, bytes]:
    entries = {"patch.json": json.dumps(MANIFEST).encode(), "run.sh": SCRIPT,
               "docs/data.bin": b"\x00\xff\r\nbyte-exact"}
    if handoff:
        environment = {
            "marker": "patch-harbor-environment", "format_version": 1, "bundle_type": "Patch",
            "repository_context": {k: MANIFEST[k] for k in
                                   ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")},
        }
        entries.update({"PATCHHARBOR_META/CHAT_INSTRUCTIONS.md": b"# Passive\n",
                        "PATCHHARBOR_META/environment.json": json.dumps(environment).encode()})
    entries.update(changes or {})
    with ZipFile(path, "w") as archive:
        directory = ZipInfo("docs/")
        directory.create_system = 3
        directory.external_attr = (stat.S_IFDIR | 0o755) << 16
        archive.writestr(directory, b"")
        for name, data in entries.items():
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name == "run.sh" else 0o644)) << 16
            archive.writestr(info, data)
    return entries


def test_inspection_reports_all_roles_and_exact_bytes_without_payload_copies(tmp_path, capsys):
    path = tmp_path / "patch.zip"
    entries = write_package(path, handoff=True)
    info = api.inspect_patch(path)
    assert info.package_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert info.package_size == path.stat().st_size
    assert str(info.manifest.repo_id) == MANIFEST["repo_id"]
    assert str(info.manifest.base_commit) == MANIFEST["base_commit"]
    assert info.entrypoint == "run.sh"
    assert len(info.entries) == len(entries)  # Explicit directory is not a file.
    assert [entry.path for entry in info.entries] == sorted(entries)
    expected_roles = {"patch.json": "manifest", "run.sh": "entrypoint", "docs/data.bin": "payload",
                      "PATCHHARBOR_META/CHAT_INSTRUCTIONS.md": "handoff",
                      "PATCHHARBOR_META/environment.json": "handoff"}
    for entry in info.entries:
        assert entry.role.value == expected_roles[entry.path]
        assert entry.size == len(entries[entry.path])
        assert entry.sha256 == hashlib.sha256(entries[entry.path]).hexdigest()
        assert entry.unix_mode == (0o755 if entry.path == "run.sh" else 0o644)
        assert not hasattr(entry, "content")
    assert info.messages == (api.PatchMessage("Notice", "Facts only"),)
    assert info.warnings == ()
    assert capsys.readouterr() == ("", "")


def test_validation_separates_static_validity_binding_and_authenticity(tmp_path):
    path = tmp_path / "patch.zip"
    write_package(path)
    before = datetime.now(timezone.utc)
    result = api.validate_patch(path)
    assert result.inspection == api.inspect_patch(path)
    assert result.scope is api.PatchValidationScope.PACKAGE
    assert result.binding_matches is None and result.context is None
    assert result.reference_sha256 is None
    assert before <= result.checked_at <= datetime.now(timezone.utc)
    assert {"authenticity", "execution", "repository_binding", "tests", "ci", "replay"} <= set(result.not_checked)


@pytest.mark.parametrize("operation", [api.inspect_patch, api.validate_patch])
def test_package_mode_performs_no_writes_lookup_subprocess_or_apply(tmp_path, monkeypatch, operation):
    path = tmp_path / "patch.zip"
    write_package(path, handoff=True)
    monkeypatch.chdir(tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    def forbidden(*args, **kwargs):
        pytest.fail("static package inspection crossed a mutation or process boundary")
    for name in ("Popen", "run"):
        monkeypatch.setattr(subprocess, name, forbidden)
    for name in ("run_apply_path", "configuration_user_paths", "prepare_patch_package", "RunSession"):
        monkeypatch.setattr(application, name, forbidden)
    import patchharbor.interpreters as interpreters
    monkeypatch.setattr(interpreters, "find_executable", forbidden)
    original_open = os.open
    def readonly_open(path, flags, *args, **kwargs):
        assert flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC) == 0
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", readonly_open)
    operation(path)
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before and not (tmp_path / "SHOULD_NOT_EXIST").exists()


def test_public_inspection_graph_is_immutable(tmp_path):
    path = tmp_path / "patch.zip"
    write_package(path)
    result = api.validate_patch(path)
    for obj, name in ((result, "scope"), (result.inspection, "package_size"),
                      (result.inspection.manifest, "base_commit"),
                      (result.inspection.entries[0], "path"), (result.inspection.messages[0], "text")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, None)
    assert isinstance(result.inspection.entries, tuple)
    assert isinstance(result.inspection.messages, tuple)
    assert isinstance(result.inspection.warnings, tuple)
    assert isinstance(result.not_checked, tuple)
    for name in ("PatchInspection", "PatchValidationResult", "PatchEntry", "PatchEntryRole",
                 "PatchManifest", "PatchMessage", "PatchValidationScope", "inspect_patch", "validate_patch"):
        assert name in api.__all__ and hasattr(api, name)


@pytest.mark.parametrize("operation", [api.inspect_patch, api.validate_patch])
@pytest.mark.parametrize("value,error", [(b"patch.zip", TypeError), (None, TypeError),
                                        (7, TypeError), ("", ValueError), ("bad\x00path", ValueError)])
def test_invalid_path_arguments_fail_before_core(value, error, operation, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid argument reached Core")
    monkeypatch.setattr(application, "inspect_patch", forbidden)
    monkeypatch.setattr(application, "validate_patch", forbidden)
    with pytest.raises(error):
        operation(value)


@pytest.mark.parametrize("operation", [api.inspect_patch, api.validate_patch])
def test_invalid_observer_is_rejected(operation):
    with pytest.raises(TypeError):
        operation("missing.zip", observer=42)


@pytest.mark.parametrize("changes,code", [
    ({"run.sh": b"#!/usr/bin/env bash\nprintf missing-marker\n"}, 3),
    ({"run.sh": b"\xff# PATCHHARBOR\n"}, 3),
    ({"run.sh": b"#!/usr/bin/env python\n# PATCHHARBOR\n"}, 5),
    ({"patch.json": b"{}"}, 10),
    ({"../outside.txt": b"unsafe"}, 4),
    ({"DOCS/data.bin": b"collision"}, 4),
    ({"PATCHHARBOR_META/environment.json": b"{}"}, 10),
])
@pytest.mark.parametrize("command", ["inspect", "validate"])
def test_api_and_json_cli_share_security_errors(tmp_path, changes, code, command):
    path = tmp_path / "patch.zip"
    write_package(path, changes=changes)
    with pytest.raises(api.PatchHarborError) as caught:
        getattr(api, command + "_patch")(path)
    assert int(exit_code_for_error(caught.value)) == code
    stdout, stderr = StringIO(), StringIO()
    assert main([command, str(path), "--json", "--verbose"], stdout=stdout, stderr=stderr) == code
    document = json.loads(stdout.getvalue())
    assert document["output_version"] == 2 and document["command"] == command
    assert document["success"] is False and document["result"] is None
    assert document["process_exit_code"] == document["error"]["patchharbor_error_code"] == code
    assert stderr.getvalue() == ""


@pytest.mark.parametrize("command", ["inspect", "validate"])
def test_json_cli_uses_public_api_and_complete_typed_facts(tmp_path, monkeypatch, command):
    path = tmp_path / "patch.zip"
    write_package(path, handoff=True)
    real = getattr(api, command + "_patch")
    calls = []
    def observed(patch, *, observer=None):
        calls.append(patch)
        return real(patch, observer=observer)
    monkeypatch.setattr(api, command + "_patch", observed)
    stdout, stderr = StringIO(), StringIO()
    assert main([command, str(path), "--json", "-v", "--no-color"], stdout=stdout, stderr=stderr) == 0
    assert calls == [path]
    document = json.loads(stdout.getvalue())
    assert set(document) == {"output_version", "command", "success", "result", "error", "process_exit_code"}
    assert document["output_version"] == 2 and document["error"] is None
    assert document["command"] == command and document["success"] is True
    result = document["result"]
    if command == "validate":
        assert result["scope"] == "package" and result["binding_matches"] is None
        assert result["context"] is None and result["reference_sha256"] is None
        assert datetime.fromisoformat(result["checked_at"]).tzinfo is not None
        result = result["inspection"]
    assert result["manifest"] == MANIFEST
    assert result["package_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["package_size"] == path.stat().st_size
    assert result["messages"] == [{"name": "Notice", "text": "Facts only"}]
    assert len(result["entries"]) == 5 and stderr.getvalue() == ""


@pytest.mark.parametrize("command", ["inspect", "validate"])
def test_explicit_file_required_and_future_binding_modes_not_offered(command, tmp_path):
    for arguments in ([command], [command, "patch.zip", "--repository", str(tmp_path)],
                      [command, "patch.zip", "--reference-bundle", "result.zip"]):
        with pytest.raises(SystemExit) as caught:
            main(arguments, stdout=StringIO(), stderr=StringIO())
        assert caught.value.code == 2
    with pytest.raises(TypeError):
        api.validate_patch("patch.zip", repository=tmp_path)


def test_package_resource_limit_is_the_existing_core_limit(tmp_path):
    path = tmp_path / "patch.zip"
    write_package(path)
    policy = replace(DEFAULT_RESOURCE_POLICY, warning_bytes=1,
                     max_input_artifact_bytes=path.stat().st_size - 1)
    with pytest.raises(api.PatchHarborError) as caught:
        inspect_patch(path, resource_policy=policy)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR


def test_older_json_command_keeps_version_one(monkeypatch):
    def failure(*args, **kwargs):
        raise api.PatchHarborError("missing repository", api.FailureReason.REPOSITORY_ERROR)
    monkeypatch.setattr(api, "context", failure)
    stdout = StringIO()
    assert main(["context", "--json"], stdout=stdout, stderr=StringIO()) == 8
    assert json.loads(stdout.getvalue())["output_version"] == 1
