from __future__ import annotations

from hashlib import sha256
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
    MAX_HANDOFF_ENTRY_BYTES, TASK_HANDOFF_DIRECTORY,
)
from patchharbor.chat_instructions import load_chat_template, render_chat_handoff
from patchharbor.errors import PatchHarborError
from patchharbor.task_package import resolve_task_bundle
from patchharbor.platform.environment import capture_runtime_environment
from tests.platform_support import PROJECT_ROOT, native_script, native_value


BINDING = {
    "repo_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "base_commit": "a" * 40,
    "state_fingerprint": "7c9d2a24e397e0e5",
    "fingerprint_algorithm": "patchharbor-state-v1",
}


def patch_environment(**overrides: object) -> dict[str, object]:
    helper = (PROJECT_ROOT / "tools/pyz_bootstrap.py").read_bytes()
    return {
        "marker": ENVIRONMENT_MARKER, "format_version": 3,
        "bootstrap": {"path": "tools/pyz_bootstrap.py", "size": len(helper), "sha256": sha256(helper).hexdigest()},
        "bundle_type": "Task", "bundle_filename": "repo_Task_Bundle_120000_0908_abcdef.zip.txt",
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
    manifest = {"patchharbor_version": "2.0.0", "marker": "patch-harbor-task-bundle", "format_version": 3, **BINDING, "entrypoint": selected}
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("task.json", json.dumps(manifest))
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






@pytest.mark.parametrize("directory", ["src", "site-packages"])
@pytest.mark.parametrize("available", [True, False])
def test_prepared_template_owns_lookup_even_in_directory_named_src(tmp_path, monkeypatch, directory, available):
    module = tmp_path / directory / "patchharbor/chat_instructions.py"
    resources = module.parent / "_runtime"
    resources.mkdir(parents=True)
    module.touch()
    (tmp_path / CHAT_INSTRUCTIONS_NAME).write_bytes(b"adjacent source lookalike\n")
    template = resources / CHAT_INSTRUCTIONS_NAME
    if available:
        template.write_bytes(b"own prepared producer\n")
    monkeypatch.setattr(instructions_module, "__file__", str(module))
    monkeypatch.chdir(tmp_path)
    if available:
        assert load_chat_template() == "own prepared producer\n"
    else:
        with pytest.raises(PatchHarborError):
            load_chat_template()


# Write exact bytes rather than relying on the host's text-mode newline
# translation: these Windows regressions must fail on Linux before the fix too.
LINE_ENDING_CASES = [
    pytest.param("first\nsecond\n", "first\nsecond\n", id="lf"),
    pytest.param("first\r\nsecond\r\n", "first\nsecond\n", id="crlf"),
    pytest.param("first\rsecond\r", "first\nsecond\n", id="cr"),
    pytest.param("first\r\n\rsecond\n\r\n", "first\n\nsecond\n\n", id="mixed"),
    pytest.param("first\r\nlast", "first\nlast", id="no-final-newline"),
    pytest.param("  Übung\t\r\n\r\nEnde  ", "  Übung\t\n\nEnde  ", id="whitespace"),
    pytest.param("one\u2028two\u0085three\r\nfour", "one\u2028two\u0085three\nfour", id="unicode-not-newline"),
]


@pytest.mark.parametrize("text,expected", LINE_ENDING_CASES)
def test_template_line_endings_are_lf_without_rewriting_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, expected: str,
) -> None:
    template = tmp_path / "template.md"
    original = text.encode("utf-8")
    template.write_bytes(original)
    monkeypatch.setattr(instructions_module, "_template_path", lambda: template)
    assert load_chat_template() == expected
    handoff = render_chat_handoff(patch_environment())
    assert handoff.instructions == render_chat_handoff(patch_environment(), template=expected).instructions
    assert b"\r" not in handoff.instructions
    assert template.read_bytes() == original


@pytest.mark.parametrize("text,expected", LINE_ENDING_CASES)
@pytest.mark.parametrize("bundle_type", ["Task", "Result"])
def test_explicit_template_line_endings_are_lf_and_environment_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, text: str, expected: str, bundle_type: str,
) -> None:
    def unexpected_load() -> str:
        raise AssertionError("explicit templates must not load local instructions")
    monkeypatch.setattr(instructions_module, "load_chat_template", unexpected_load)
    document = patch_environment(bundle_type=bundle_type, note="exact\r\nvalue\rpreserved")
    handoff = render_chat_handoff(document, template=text)
    canonical = render_chat_handoff(document, template=expected)
    assert handoff == canonical
    assert handoff.instructions.endswith(expected.encode("utf-8"))
    assert b"\r" not in handoff.instructions
    assert json.loads(handoff.environment) == document
    assert b"```json" not in handoff.instructions
    assert document["note"] == "exact\r\nvalue\rpreserved"


@pytest.mark.parametrize("line_ending", [b"\n", b"\r\n", b"\r"], ids=["lf", "crlf", "cr"])
def test_installed_template_line_endings_are_lf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, line_ending: bytes,
) -> None:
    module = tmp_path / "site-packages" / "patchharbor" / "chat_instructions.py"
    module.parent.mkdir(parents=True)
    module.touch()
    template = module.parent / "_runtime" / CHAT_INSTRUCTIONS_NAME
    template.parent.mkdir(parents=True)
    raw = b"installed canonical contract" + line_ending
    template.write_bytes(raw)
    monkeypatch.setattr(instructions_module, "__file__", str(module))
    assert load_chat_template() == "installed canonical contract\n"
    assert render_chat_handoff(patch_environment(), bootstrap=(PROJECT_ROOT / "tools/pyz_bootstrap.py").read_bytes()).instructions.endswith(b"installed canonical contract\n")
    assert template.read_bytes() == raw


def test_template_raw_size_limit_is_checked_before_newline_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = tmp_path / "template.md"
    monkeypatch.setattr(instructions_module, "_template_path", lambda: template)
    raw = b"\r\n" * (MAX_HANDOFF_ENTRY_BYTES // 2)
    template.write_bytes(raw)
    assert load_chat_template() == "\n" * (MAX_HANDOFF_ENTRY_BYTES // 2)
    template.write_bytes(raw + b"\r\n")
    with pytest.raises(PatchHarborError, match="chat-instructions template"):
        load_chat_template()


def test_renderer_preserves_exact_values_and_quotes_local_commands() -> None:
    document = patch_environment()
    handoff = render_chat_handoff(document, template="STATIC CONTRACT\n")
    assert json.loads(handoff.environment) == document
    text = handoff.instructions.decode()
    assert text.endswith("STATIC CONTRACT\n")
    assert "cd -- '/home/example/My Project'\"'\"'s repo' && patchharbor bundle" in text
    assert BINDING["base_commit"] not in text
    assert BINDING["repo_id"] not in text
    assert "/sdcard/Download" not in text
    assert "environment.json" in text
    assert dict(handoff.entries())[CHAT_INSTRUCTIONS_NAME] == handoff.instructions


@pytest.mark.parametrize("path", [None, "C:\\bad\npath", "control\x1bpath"])
def test_unknown_or_control_paths_are_not_executable_examples(path: str | None) -> None:
    document = patch_environment(repository_path=path)
    text = render_chat_handoff(document, template="contract\n").instructions.decode()
    assert "cd -- " not in text


def test_markdown_fences_in_metadata_remain_data() -> None:
    document = patch_environment(repository_name="repo```\nforged", exchange_directory="/tmp/```/evil")
    text = render_chat_handoff(document, template="contract\n").instructions.decode()
    assert "\\u0060\\u0060\\u0060" in text
    assert text.count("```json") == 0
    assert "repo```\nforged" not in text
    assert "\\nforged" in text
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
    write_handoff_patch(path, dict(handoff.entries(task=True)))
    package = resolve_task_bundle(path)
    assert package.handoff == handoff
    assert {payload.relative_path for payload in package.payloads} == {"actual-payload.txt", "CHAT_INSTRUCTIONS.md"}
    write_handoff_patch(path, {})
    assert resolve_task_bundle(path).handoff is None


@pytest.mark.parametrize("fault", ["missing", "extra", "binding", "type", "version", "duplicate", "nan", "bom", "encoding", "size", "entrypoint", "case"])
def test_invalid_reserved_metadata_is_rejected_before_mutation(tmp_path: Path, fault: str) -> None:
    entries = dict(render_chat_handoff(patch_environment()).entries(task=True))
    env_name = f"{TASK_HANDOFF_DIRECTORY}/{ENVIRONMENT_NAME}"
    chat_name = f"{TASK_HANDOFF_DIRECTORY}/{CHAT_INSTRUCTIONS_NAME}"
    doc = json.loads(entries[env_name])
    entrypoint = None
    if fault == "missing":
        del entries[chat_name]
    elif fault == "extra":
        entries[f"{TASK_HANDOFF_DIRECTORY}/payload.txt"] = b"not metadata"
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
        resolve_task_bundle(path)


@pytest.mark.parametrize("fault", [None, "missing", "hash", "size", "path", "bom", "extra", "entrypoint", "downgrade"])
def test_version3_helper_is_passive_and_strictly_bound(tmp_path, fault):
    from patchharbor.bundle_handoff import BOOTSTRAP_NAME
    helper = b'raise AssertionError("metadata must not execute")\n'
    handoff = render_chat_handoff(patch_environment(format_version=3), bootstrap=helper)
    entries = dict(handoff.entries(task=True))
    name = TASK_HANDOFF_DIRECTORY + '/' + BOOTSTRAP_NAME
    env_name = TASK_HANDOFF_DIRECTORY + '/' + ENVIRONMENT_NAME
    doc = json.loads(entries[env_name])
    selected = None
    if fault == "missing": entries.pop(name)
    elif fault == "hash": entries[name] += b'# changed\n'
    elif fault == "size": doc['bootstrap']['size'] = True
    elif fault == "path": doc['bootstrap']['path'] = '../escape.py'
    elif fault == "bom": entries[name] = b'\xef\xbb\xbf' + helper
    elif fault == "extra": entries[name + '.extra'] = helper
    elif fault == "entrypoint": selected = name
    elif fault == "downgrade": doc['format_version'] = 2
    entries[env_name] = json.dumps(doc).encode()
    path = tmp_path / 'task.zip'
    write_handoff_patch(path, entries, entrypoint=selected)
    if fault:
        with pytest.raises(PatchHarborError): resolve_task_bundle(path)
    else:
        package = resolve_task_bundle(path)
        assert package.handoff.bootstrap == helper
        assert {p.relative_path for p in package.payloads} == {'actual-payload.txt', 'CHAT_INSTRUCTIONS.md'}
        assert json.loads(handoff.environment)['bootstrap']['size'] == len(helper)


@pytest.mark.parametrize('fault', [None, 'missing', 'changed', 'extra', 'downgrade'])
def test_result_reader_preserves_and_verifies_separate_helper(tmp_path, fault):
    from patchharbor.bundle_handoff import BOOTSTRAP_NAME
    from patchharbor.result_reader import capture_result_reference
    from tests.reference_support import reference_entries, write_reference
    files, _ = reference_entries()
    document = json.loads(files[ENVIRONMENT_NAME])
    document['format_version'] = 3
    handoff = render_chat_handoff(document, template='contract\n', bootstrap=b'# passive\n')
    files.update(dict(handoff.entries()))
    if fault == 'missing': files.pop(BOOTSTRAP_NAME)
    elif fault == 'changed': files[BOOTSTRAP_NAME] += b'changed'
    elif fault == 'extra': files['tools/another.py'] = b'# unwanted'
    elif fault == 'downgrade':
        document = json.loads(files[ENVIRONMENT_NAME]); document['format_version'] = 2
        files[ENVIRONMENT_NAME] = json.dumps(document).encode()
    path = tmp_path / 'result.zip'; write_reference(path, files)
    if fault:
        with pytest.raises(PatchHarborError): capture_result_reference(path)
    else:
        assert capture_result_reference(path).handoff == handoff


def test_compact_header_keeps_all_environment_fields_without_repeating_them():
    document = patch_environment(note='detail-' * 9000, future_field={'nested': [None, 'exact\r\nvalue']})
    original = json.loads(json.dumps(document))
    handoff = render_chat_handoff(document, template='contract\n')
    assert json.loads(handoff.environment) == original == document
    assert len(handoff.instructions) < 2000
    assert b'detail-' not in handoff.instructions
    assert b'future_field' not in handoff.instructions


def test_compact_header_still_enforces_full_environment_budget():
    document = patch_environment(note='x' * MAX_HANDOFF_ENTRY_BYTES)
    with pytest.raises(PatchHarborError, match='size limit'):
        render_chat_handoff(document, template='contract\n')
