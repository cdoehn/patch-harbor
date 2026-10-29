"""Executable handoff examples and public parser behavior, independent of prose."""
from __future__ import annotations

import json
import re
import socket
import subprocess
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor.bundle_handoff import MAX_HANDOFF_ENTRY_BYTES
from patchharbor.chat_instructions import load_chat_template, render_chat_handoff
from patchharbor.cli import _build_parser as build_core_parser
from patchharbor_watcher.cli import _build_parser as build_watcher_parser
from tests.compatibility_140_support import artifact
from tests.platform_support import PROJECT_ROOT


def test_canonical_contract_can_be_loaded_and_rendered_without_execution(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("passive handoff attempted process or network activity")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    raw = (PROJECT_ROOT / "CHAT_INSTRUCTIONS.md").read_bytes()
    template = load_chat_template()
    assert template == raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    document = {"repository_path": "/example/repo", "runtime": {"system": "Linux"}}
    handoff = render_chat_handoff(document)
    assert handoff.instructions.endswith(template.encode("utf-8"))
    assert 0 < len(handoff.instructions) <= MAX_HANDOFF_ENTRY_BYTES
    assert json.loads(handoff.environment) == document


def test_documented_patch_manifest_validates_against_a_real_reference(tmp_path, monkeypatch) -> None:
    reference, expected = artifact("result", "clean")
    document = load_chat_template()
    examples = [json.loads(block) for block in re.findall(
        r"^```json\s*\n(.*?)\n```$", document, flags=re.MULTILINE | re.DOTALL)]
    manifests = [example for example in examples if isinstance(example, dict) and "entrypoint" in example]
    assert len(manifests) == 1
    manifest = manifests[0]
    # Resolve only the three target-specific placeholders. All remaining example
    # fields are validated unchanged by the actual public package reader.
    for field in ("repo_id", "base_commit", "state_fingerprint"):
        manifest[field] = expected["binding"][field]
    package = tmp_path / "documented.zip"
    with ZipFile(package, "w") as archive:
        archive.writestr("patch.json", json.dumps(manifest))
        archive.writestr("run.sh", "#!/usr/bin/env bash\n# PATCHHARBOR\nexit 23\n")
    def forbidden(*args, **kwargs):
        pytest.fail("example validation attempted execution or network activity")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    checked = api.validate_patch(package, reference_bundle=reference)
    assert checked.binding_matches is True
    assert checked.scope is api.PatchValidationScope.REFERENCE
    assert checked.reference_sha256 == expected["sha256"]
    assert "execution" in checked.not_checked


def test_public_commands_accept_documented_arguments_and_reject_missing_or_unknown_ones() -> None:
    parser = build_core_parser()
    for arguments in (
        ["configure", "exchange-directory", "exchange"],
        ["configure", "show"],
        ["configure", "bundle-suffix", ".txt"],
        ["configure", "bundle-suffix", "--clear"],
        ["configure", "archive-dir", "PatchHarbor-Archive"],
        ["configure", "archive-dir", "--clear"],
        ["register"], ["register", "repository"], ["registry", "list"],
        ["unregister", "repository-or-id"],
        ["context"], ["context", "repository"],
        ["bundle"], ["bundle", "repository"],
        ["apply"], ["apply", "package.zip"],
        ["apply", "--dry-run"], ["apply", "--dry-run", "package.zip"],
        ["fs", "run", "source"],
    ):
        parser.parse_args(arguments)
    build_watcher_parser().parse_args([])
    for arguments in (["unregister"], ["apply", "--retry-failed"],
                      ["chat"], ["commit"], ["plan"], ["rollback"], ["test"]):
        with pytest.raises(SystemExit) as error:
            parser.parse_args(arguments)
        assert error.value.code == 2
