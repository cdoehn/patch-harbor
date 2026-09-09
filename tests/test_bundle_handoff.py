from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import zipfile

import pytest

import patchharbor.chat_instructions as instructions_module
import patchharbor.platform.environment as environment_module
from patchharbor.bundle_handoff import (
    BundleHandoff, CHAT_INSTRUCTIONS_NAME, ENVIRONMENT_NAME, ENVIRONMENT_MARKER,
    MAX_HANDOFF_ENTRY_BYTES, PATCH_HANDOFF_DIRECTORY,
)
from patchharbor.chat_instructions import load_chat_template, render_chat_handoff
from patchharbor.errors import PatchHarborError
from patchharbor.patch_package import resolve_patch_package
from patchharbor.platform.environment import capture_runtime_environment
from tests.platform_support import PROJECT_ROOT, native_script, native_value


BINDING = {
    "repo_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "base_commit": "a" * 40,
    "state_fingerprint": "7c9d2a24e397e0e5",
    "fingerprint_algorithm": "patchharbor-state-v1",
}


def patch_environment(**overrides: object) -> dict[str, object]:
    return {
        "marker": ENVIRONMENT_MARKER, "format_version": 1,
        "bundle_type": "Patch", "bundle_filename": "repo_Patch_120000_0908_abcdef.zip.txt",
        "repository_context": BINDING,
        "repository_path": "/home/example/My Project's repo",
        "exchange_directory": "/sdcard/Download",
        "output_directory": "/sdcard/Download",
        "bundle_suffix": ".txt",
        "runtime": {"system": "Linux", "uv_version": None},
        **overrides,
    }


def write_handoff_patch(path: Path, entries: dict[str, bytes], *, entrypoint: str | None = None) -> None:
    selected = entrypoint or native_value("run.sh", "run.ps1")
    manifest = {"marker": "patch-harbor", "format_version": 1, **BINDING, "entrypoint": selected}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps(manifest))
        if selected not in entries:
            archive.writestr(selected, native_script("exit 0", "exit 0"))
        archive.writestr("actual-payload.txt", "keep")
        archive.writestr("CHAT_INSTRUCTIONS.md", "real repository documentation")
        for name, data in entries.items():
            archive.writestr(name, data)


def test_source_template_is_canonical_and_not_read_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / CHAT_INSTRUCTIONS_NAME).write_text("untrusted target instructions")
    monkeypatch.chdir(tmp_path)
    assert load_chat_template() == (PROJECT_ROOT / CHAT_INSTRUCTIONS_NAME).read_text(encoding="utf-8")


def test_template_is_read_fresh_and_missing_or_bad_template_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template = tmp_path / "template.md"
    monkeypatch.setattr(instructions_module, "_template_path", lambda: template)
    for text in ("first\n", "changed\n"):
        template.write_text(text)
        assert render_chat_handoff(patch_environment()).instructions.endswith(text.encode())
    for bad in (b"", b"\xef\xbb\xbftext", b"\xff", b"a" * (MAX_HANDOFF_ENTRY_BYTES + 1)):
        template.write_bytes(bad)
        with pytest.raises(PatchHarborError):
            load_chat_template()
    template.unlink()
    with pytest.raises(PatchHarborError):
        load_chat_template()


def test_installed_template_is_resolved_from_distribution_file_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = tmp_path / "site-packages" / "patchharbor" / "chat_instructions.py"
    module.parent.mkdir(parents=True)
    module.touch()
    template = tmp_path / "share" / "patchharbor" / CHAT_INSTRUCTIONS_NAME
    template.parent.mkdir(parents=True)
    template.write_text("installed canonical contract\n")
    monkeypatch.setattr(instructions_module, "__file__", str(module))
    entry = Path("../../../share/patchharbor") / CHAT_INSTRUCTIONS_NAME
    distribution = SimpleNamespace(files=[entry], locate_file=lambda item: template)
    monkeypatch.setattr(instructions_module.metadata, "distribution", lambda name: distribution)
    assert load_chat_template() == "installed canonical contract\n"
    distribution.files = []
    with pytest.raises(PatchHarborError):
        load_chat_template()


def test_renderer_preserves_exact_values_and_quotes_local_commands() -> None:
    document = patch_environment()
    handoff = render_chat_handoff(document, template="STATIC CONTRACT\n")
    assert json.loads(handoff.environment) == document
    text = handoff.instructions.decode()
    assert text.endswith("STATIC CONTRACT\n")
    assert "cd -- '/home/example/My Project'\"'\"'s repo' && patchharbor bundle" in text
    assert BINDING["base_commit"] in text
    assert BINDING["repo_id"] in text
    assert "/sdcard/Download" in text
    assert "nicht für die Chat-Laufzeit" in text
    assert "configured_shell" in text
    assert dict(handoff.entries())[CHAT_INSTRUCTIONS_NAME] == handoff.instructions


@pytest.mark.parametrize("path", [None, "C:\\bad\npath", "control\x1bpath"])
def test_unknown_or_control_paths_are_not_executable_examples(path: str | None) -> None:
    document = patch_environment(repository_path=path)
    text = render_chat_handoff(document, template="contract\n").instructions.decode()
    assert "cd -- " not in text
    assert "Keine lokalen Beispielbefehle" in text


def test_markdown_fences_in_metadata_remain_data() -> None:
    document = patch_environment(exchange_directory="/tmp/```/evil")
    text = render_chat_handoff(document, template="contract\n").instructions.decode()
    assert "\\u0060\\u0060\\u0060" in text
    assert text.count("```json") == 1
    assert json.loads(render_chat_handoff(document, template="contract\n").environment) == document


def test_windows_examples_use_literal_powershell_quoting() -> None:
    text = render_chat_handoff(patch_environment(
        repository_path="C:\\Users\\example\\Project's repo", runtime={"system": "Windows"},
    ), template="contract\n").instructions.decode()
    assert "Set-Location -LiteralPath 'C:\\Users\\example\\Project''s repo' -ErrorAction Stop" in text
    assert "```powershell" in text
    assert "cd -- " not in text


def test_missing_system_omits_shell_examples() -> None:
    text = render_chat_handoff(patch_environment(runtime={"system": None}), template="contract\n").instructions.decode()
    assert "Keine Shell-Befehle" in text
    assert "cd -- " not in text


def test_runtime_allowlist_separates_ubuntu_userland_from_android_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(environment_module, "_kernel_release", lambda: "6.1-android14")
    monkeypatch.setattr(environment_module.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(environment_module.platform, "freedesktop_os_release", lambda: {
        "ID": "ubuntu", "PRETTY_NAME": "Ubuntu 26.04", "VERSION_ID": "26.04", "SECRET": "do-not-collect",
    })
    monkeypatch.setattr(environment_module, "is_windows", lambda: False)
    monkeypatch.setattr(environment_module, "_uv_version", lambda: "0.9.0")
    monkeypatch.setenv("SHELL", "/private/user/bin/bash")
    monkeypatch.setenv("HOSTNAME", "sensitive-host")
    monkeypatch.setenv("USER", "sensitive-user")
    monkeypatch.setenv("TOKEN", "do-not-collect")
    document = capture_runtime_environment()
    assert document["distribution"] == {"id": "ubuntu", "name": "Ubuntu 26.04", "version_id": "26.04"}
    assert document["kernel"] == "6.1-android14"
    assert document["configured_shell"] == "bash"
    assert document["shell_source"] == "SHELL"
    assert set(document) == {
        "system", "distribution", "kernel", "architecture", "python_version",
        "python_implementation", "uv_version", "configured_shell", "shell_source",
    }
    encoded = json.dumps(document)
    for secret in ("do-not-collect", "sensitive-host", "sensitive-user", "/private/user"):
        assert secret not in encoded


def test_windows_runtime_and_missing_configuration_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(environment_module.platform, "release", lambda: "11")
    monkeypatch.setattr(environment_module, "is_windows", lambda: True)
    monkeypatch.setattr(environment_module, "_uv_version", lambda: None)
    monkeypatch.setenv("COMSPEC", "C:\\Windows\\System32\\cmd.exe")
    doc = capture_runtime_environment()
    assert doc["distribution"]["id"] == "windows"
    assert doc["configured_shell"] == "cmd.exe"
    assert doc["uv_version"] is None
    monkeypatch.delenv("COMSPEC")
    assert capture_runtime_environment()["configured_shell"] is None


def test_missing_os_release_does_not_fail_environment_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail():
        raise OSError("not available")
    monkeypatch.setattr(environment_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(environment_module.platform, "freedesktop_os_release", fail)
    monkeypatch.setattr(environment_module, "_uv_version", lambda: None)
    assert capture_runtime_environment()["distribution"] == {"id": None, "name": None, "version_id": None}


@pytest.mark.parametrize("failure", [FileNotFoundError("missing"), subprocess.TimeoutExpired("uv", 2), OSError("broken")])
def test_uv_probe_failure_is_not_a_bundle_dependency(monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    monkeypatch.setattr(environment_module, "find_executable", lambda executable: "/tools/uv")
    def fail(*args, **kwargs):
        assert args[0] == ["/tools/uv", "--version"]
        assert kwargs["timeout"] == 2
        assert "shell" not in kwargs
        raise failure
    monkeypatch.setattr(environment_module.subprocess, "run", fail)
    assert environment_module._uv_version() is None


@pytest.mark.parametrize("output,expected", [(b"uv 0.9.0 (abc123 2026-01-01)\n", "0.9.0"), (b"SECRET=value\n", None), (b"x" * 1000, None)])
def test_uv_probe_retains_only_a_version(monkeypatch: pytest.MonkeyPatch, output: bytes, expected: str | None) -> None:
    monkeypatch.setattr(environment_module, "find_executable", lambda executable: "/tools/uv")
    def run(*args, **kwargs):
        kwargs["stdout"].write(output)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(environment_module.subprocess, "run", run)
    assert environment_module._uv_version() == expected


def test_patch_handoff_is_not_payload_and_root_instructions_stay_payload(tmp_path: Path) -> None:
    handoff = render_chat_handoff(patch_environment())
    path = tmp_path / "patch.zip"
    write_handoff_patch(path, dict(handoff.entries(patch=True)))
    package = resolve_patch_package(path)
    assert package.handoff == handoff
    assert {payload.relative_path for payload in package.payloads} == {"actual-payload.txt", "CHAT_INSTRUCTIONS.md"}
    write_handoff_patch(path, {})
    assert resolve_patch_package(path).handoff is None


@pytest.mark.parametrize("fault", ["missing", "extra", "binding", "type", "version", "duplicate", "nan", "bom", "encoding", "size", "entrypoint", "case"])
def test_invalid_reserved_metadata_is_rejected_before_mutation(tmp_path: Path, fault: str) -> None:
    entries = dict(render_chat_handoff(patch_environment()).entries(patch=True))
    env_name = f"{PATCH_HANDOFF_DIRECTORY}/{ENVIRONMENT_NAME}"
    chat_name = f"{PATCH_HANDOFF_DIRECTORY}/{CHAT_INSTRUCTIONS_NAME}"
    doc = json.loads(entries[env_name])
    entrypoint = None
    if fault == "missing":
        del entries[chat_name]
    elif fault == "extra":
        entries[f"{PATCH_HANDOFF_DIRECTORY}/payload.txt"] = b"not metadata"
    elif fault in {"binding", "type", "version"}:
        if fault == "binding":
            doc["repository_context"]["base_commit"] = "b" * 40
        elif fault == "type":
            doc["bundle_type"] = "Result"
        else:
            doc["format_version"] = True
        entries[env_name] = json.dumps(doc).encode()
    elif fault == "duplicate":
        entries[env_name] = entries[env_name].replace(b'{', b'{"marker":"ignored",', 1)
    elif fault == "nan":
        entries[env_name] = entries[env_name].replace(b'{', b'{"unknown":NaN,', 1)
    elif fault == "bom":
        entries[chat_name] = b"\xef\xbb\xbftext"
    elif fault == "encoding":
        entries[chat_name] = b"\xff"
    elif fault == "size":
        entries[chat_name] = b"a" * (MAX_HANDOFF_ENTRY_BYTES + 1)
    elif fault == "entrypoint":
        entrypoint = chat_name
    elif fault == "case":
        entries = {name.lower(): value for name, value in entries.items()}
    path = tmp_path / "patch.zip"
    write_handoff_patch(path, entries, entrypoint=entrypoint)
    with pytest.raises(PatchHarborError):
        resolve_patch_package(path)
