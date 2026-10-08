"""Real offline handoff and previous-path checks, independent of document prose."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

from patchharbor import api
from patchharbor import runtime_wheel
from patchharbor.zip_payloads import ZipPayloadError
from build_backend import _prepare_recipe
from scripts import runtime_bootstrap as bootstrap
from tests.result_runtime_support import attach_runtime, replace_wheel, rewrite_wheel
from tests.registration_support import create_repository
from tests.test_result_runtime_writer import package

pytestmark = pytest.mark.packaging


@pytest.fixture
def handoff(tmp_path, prepared_result_producer):
    repo = create_repository(tmp_path / "repository")
    api.register(repo)
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange, repository=repo)
    reference = api.bundle(repo).path
    # This legacy bootstrap consumes a real frozen Format-2 runtime; the current
    # producer now emits Format 3 and must not keep an old writer just for tests.
    fixture=Path(__file__).parent/'fixtures/result_format2'
    provenance=json.loads((fixture/'provenance.json').read_bytes())
    raw=(fixture/provenance['wheel_file']).read_bytes()
    assert sha256(raw).hexdigest()==provenance['wheel_sha256']
    with ZipFile(reference) as archive:files={name:archive.read(name) for name in archive.namelist()}
    files=attach_runtime(files,raw)
    with ZipFile(reference,'w') as archive:
        for name,data in files.items():archive.writestr(name,data)
    patch = package(repo, exchange)
    return reference, patch


@pytest.fixture
def network_guard(tmp_path, monkeypatch):
    original = bootstrap._run
    log = tmp_path / "network-guard.jsonl"
    runner = Path(__file__).parent / "bootstrap_process.py"
    def run(command, workspace, environment):
        assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
        assert "EXAMPLE_SESSION_SECRET" not in environment
        return original([command[0], "-I", "-B", str(runner), str(log), *command[1:]], workspace, environment)
    monkeypatch.setattr(bootstrap, "_run", run)
    return log


def test_assessment_is_read_only_and_unknown_source_never_installs(handoff, tmp_path, monkeypatch):
    reference, patch = handoff
    before = reference.read_bytes()
    def no_process(*args, **kwargs):
        pytest.fail("read-only assessment or unknown runtime launched a process")
    monkeypatch.setattr(subprocess, "run", no_process)
    assessment = bootstrap.assess(reference)
    assert assessment.reason == "runtime_source_untrusted" and assessment.full_reference_valid
    result = bootstrap.install(assessment, tmp_path / "must-not-exist")
    assert result.status == "fallback" and not (tmp_path / "must-not-exist").exists()
    checked = bootstrap.check_patch(patch, result)
    assert checked["method"] == "previous_handoff" and checked["native_validation"] is False
    assert reference.read_bytes() == before


def test_actual_offline_install_and_native_reference_check(handoff, tmp_path, monkeypatch, network_guard):
    reference, patch = handoff
    monkeypatch.setenv("EXAMPLE_SESSION_SECRET", "must-not-be-forwarded")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "shadow"))
    monkeypatch.setenv("PYTHONHOME", str(tmp_path / "invalid-python-home"))
    assessment = trusted_assessment(reference)
    assert assessment.reason is None
    result = bootstrap.install(assessment, tmp_path / "isolated-runtime")
    assert result.status == "ready", result
    checked = bootstrap.check_patch(patch, result)
    assert checked["method"] == "native_reference" and checked["native_validation"] is True
    assert checked["package_sha256"] == sha256(patch.read_bytes()).hexdigest()
    guards = [json.loads(row) for row in network_guard.read_text().splitlines()]
    assert len(guards) >= 7 and all(row["network_denied"] for row in guards)
    assert any(Path(row["python"]) == result.python for row in guards)


@pytest.mark.parametrize("fault", ["missing_wheel", "corrupt_wheel", "corrupt_metadata"])
def test_runtime_only_defect_uses_original_reference_without_forging_native_success(handoff, tmp_path, fault):
    reference, patch = handoff
    with ZipFile(reference) as archive:
        files = {info.filename: (info, archive.read(info)) for info in archive.infolist()}
    wheel_name = next(name for name in files if name.startswith("runtime/") and name.endswith(".whl"))
    if fault == "missing_wheel":
        del files[wheel_name]
    else:
        name = wheel_name if fault == "corrupt_wheel" else "runtime/runtime.json"
        info, raw = files[name]; files[name] = (info, raw + b"corrupt")
    with ZipFile(reference, "w") as archive:
        for info, raw in files.values(): archive.writestr(info, raw)
    original = reference.read_bytes()
    assessment = bootstrap.assess(reference, trusted_source_sha256=sha256(original).hexdigest())
    assert assessment.reason == "runtime_invalid" and not assessment.full_reference_valid
    outcome = bootstrap.install(assessment, tmp_path / "unused")
    checked = bootstrap.check_patch(patch, outcome)
    assert checked["method"] == "previous_handoff" and checked["native_validation"] is False
    assert checked["reference_sha256"] == sha256(original).hexdigest()
    assert reference.read_bytes() == original and not (tmp_path / "unused").exists()
    with pytest.raises(api.PatchHarborError):
        api.validate_patch(patch, reference_bundle=reference)


def test_missing_installer_uses_previous_handoff(handoff, tmp_path, network_guard):
    reference, patch = handoff
    assessment = trusted_assessment(reference)
    result = bootstrap.install(assessment, tmp_path / "runtime", installer_python=str(tmp_path / "absent-python"))
    assert result.status == "fallback" and result.reason == "installer_or_python_incompatible"
    assert bootstrap.check_patch(patch, result)["method"] == "previous_handoff"


def trusted_assessment(reference):
    # Fixture identity stands in for an independently trusted source channel.
    return bootstrap.assess(reference, trusted_source_sha256=sha256(reference.read_bytes()).hexdigest())


def rewrite(path, change):
    with ZipFile(path) as archive:
        files = {info.filename: archive.read(info) for info in archive.infolist()}
    change(files)
    with ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


@pytest.mark.parametrize("fault", ["snapshot", "context", "run", "extra", "unsafe"])
def test_bad_repository_evidence_still_blocks_runtime_fallback(handoff, fault, monkeypatch):
    reference, _ = handoff
    def change(files):
        files["runtime/runtime.json"] = b"broken optional runtime"
        if fault == "snapshot":
            name = next(name for name in files if name.startswith("base/"))
            files[name] += b"changed"
        elif fault in {"context", "run"}:
            name = "context.json" if fault == "context" else "logs/run.json"
            doc = json.loads(files[name]); doc["base_commit"] = "a" * 40
            files[name] = json.dumps(doc).encode()
        else:
            files["extra.txt" if fault == "extra" else "../escape"] = b"bad"
    rewrite(reference, change)
    monkeypatch.setattr(bootstrap, "_run", lambda *a: pytest.fail("invalid reference launched code"))
    with pytest.raises((ValueError, api.PatchHarborError, ZipPayloadError)):
        bootstrap.assess(reference)


@pytest.mark.parametrize("name", ["foreign.py", "patchharbor/unsafe.pth"])
def test_forbidden_runtime_profile_never_executes_even_with_rehashed_outer_descriptors(handoff, tmp_path, name, monkeypatch):
    reference, patch = handoff
    def change(files):
        wheel = next(raw for name, raw in files.items() if name.endswith(".whl"))
        bad = rewrite_wheel(wheel, lambda rows: rows.append((name, b"raise AssertionError('untrusted')")))
        replace_wheel(files, bad)
    rewrite(reference, change)
    monkeypatch.setattr(bootstrap, "_run", lambda *a: pytest.fail("untrusted runtime executed"))
    assessment = trusted_assessment(reference)
    outcome = bootstrap.install(assessment, tmp_path / "never-created")
    assert outcome.status == "fallback" and outcome.reason == "runtime_invalid"
    assert bootstrap.check_patch(patch, outcome)["native_validation"] is False


def test_complete_python_requirement_is_enforced_before_installation(handoff, tmp_path, network_guard):
    reference, patch = handoff
    def change(files):
        raw = next(raw for name, raw in files.items() if name.endswith(".whl"))
        with ZipFile(BytesIO(raw)) as wheel:
            original = runtime_wheel.parse_recipe(wheel.read(runtime_wheel.RECIPE_PATH))
            payloads = {entry.path: wheel.read(entry.path) for entry in original.entries}
        requirement = ">=3.12,!=3.*"  # a valid conjunction with no compatible Python 3
        for name in (original.dist_info + "/METADATA", runtime_wheel.RESOURCE_ROOT + "metadata/METADATA"):
            payloads[name] = payloads[name].replace(original.requires_python.encode(), requirement.encode())
        initial = _prepare_recipe(runtime_wheel, payloads, version=original.version, requires_python=requirement)
        payloads[runtime_wheel.IDENTITY_PATH] = runtime_wheel.identity_module(runtime_wheel.producer_id(initial))
        recipe = _prepare_recipe(runtime_wheel, payloads, version=original.version, requires_python=requirement)
        raw = runtime_wheel.materialize(recipe, lambda name, size: payloads[name])
        updated = attach_runtime(files, raw); files.clear(); files.update(updated)
    rewrite(reference, change)
    assessment = trusted_assessment(reference)
    assert assessment.reason is None  # profile valid, current interpreter incompatible
    outcome = bootstrap.install(assessment, tmp_path / "incompatible")
    assert outcome.reason == "installer_or_python_incompatible"
    assert not (outcome.workspace / "installation_failed.log").exists()
    assert not list((outcome.workspace / "venv").rglob("patchharbor/__init__.py"))
    assert bootstrap.check_patch(patch, outcome)["method"] == "previous_handoff"


@pytest.mark.parametrize("fault", ["missing_venv", "install", "import", "wheel_changed"])
def test_failed_bootstrap_has_one_attempt_and_uses_previous_handoff(handoff, tmp_path, monkeypatch, network_guard, fault):
    reference, patch = handoff
    assessment = trusted_assessment(reference)
    original = bootstrap._run
    calls = []
    def run(command, workspace, environment):
        calls.append(command)
        if (fault == "missing_venv" and "venv" in command or
                fault == "install" and "pip" in command and "--dry-run" not in command or
                fault == "import" and "-c" in command):
            return subprocess.CompletedProcess(command, 1, "", "injected technical failure")
        if fault == "wheel_changed" and "--dry-run" in command:
            (workspace / assessment.wheel_name).write_bytes(b"changed after verified capture")
        return original(command, workspace, environment)
    monkeypatch.setattr(bootstrap, "_run", run)
    outcome = bootstrap.install(assessment, tmp_path / "failed-runtime")
    expected = {"missing_venv": "venv_unavailable", "install": "installation_failed",
                "import": "runtime_import_failed", "wheel_changed": "installer_or_python_incompatible"}
    assert outcome.status == "fallback" and outcome.reason == expected[fault]
    assert len(calls) == len({tuple(command) for command in calls})
    assert bootstrap.check_patch(patch, outcome)["method"] == "previous_handoff"


def test_runtime_cannot_import_project_shadow_modules(handoff, tmp_path, monkeypatch, network_guard):
    reference, patch = handoff
    shadow = tmp_path / "shadow"; shadow.mkdir()
    poison = b"raise AssertionError('project module must not be imported')\n"
    (shadow / "patchharbor.py").write_bytes(poison)
    monkeypatch.setenv("PYTHONPATH", str(shadow))
    original = bootstrap._run
    def run(command, workspace, environment):
        (workspace / "patchharbor.py").write_bytes(poison)
        return original(command, workspace, environment)
    monkeypatch.setattr(bootstrap, "_run", run)
    assessment = trusted_assessment(reference)
    outcome = bootstrap.install(assessment, tmp_path / "isolated")
    assert outcome.status == "ready"
    assert bootstrap.check_patch(patch, outcome)["native_validation"] is True


@pytest.mark.parametrize("fault", ["missing_python", "encoding", "crash", "json_shape", "json_missing"])
def test_technical_native_tool_failure_uses_previous_checks(handoff, tmp_path, monkeypatch, fault):
    reference, patch = handoff
    assessment = bootstrap.assess(reference)
    workspace = tmp_path / "existing-runtime"; workspace.mkdir()
    outcome = bootstrap.Bootstrap(assessment, "ready", None, workspace / "python", workspace)
    def run(*args):
        if fault == "missing_python": raise FileNotFoundError("interpreter disappeared")
        if fault == "encoding": raise UnicodeError("invalid process encoding")
        return subprocess.CompletedProcess([], 1 if fault == "crash" else 0,
                {"crash": "traceback", "json_shape": "[]", "json_missing": '{"success":true}'}[fault], "")
    monkeypatch.setattr(bootstrap, "_run", run)
    result = bootstrap.check_patch(patch, outcome)
    assert result["method"] == "previous_handoff" and result["reason"] == "native_tool_unavailable"


@pytest.mark.parametrize("fault", ["binding", "patch_changed", "reference_changed", "semantic_rejection", "wrong_evidence"])
def test_invalid_or_changed_validation_inputs_never_receive_success(handoff, tmp_path, monkeypatch, fault):
    reference, patch = handoff
    assessment = bootstrap.assess(reference)
    workspace = tmp_path / "existing-runtime"; workspace.mkdir()
    outcome = bootstrap.Bootstrap(assessment, "ready", None, workspace / "python", workspace)
    if fault == "binding":
        def change(files):
            doc = json.loads(files["patch.json"]); doc["base_commit"] = "a" * 40
            files["patch.json"] = json.dumps(doc).encode()
        rewrite(patch, change)
    def run(*args):
        if fault == "binding": pytest.fail("mismatched binding reached native code")
        if fault == "patch_changed": rewrite(patch, lambda files: files.update({"later.txt": b"changed"}))
        if fault == "reference_changed": reference.write_bytes(reference.read_bytes() + b"changed")
        if fault == "semantic_rejection": return subprocess.CompletedProcess([], 4, '{"success":false}', "")
        if fault == "wrong_evidence":
            return subprocess.CompletedProcess([], 0, json.dumps({"success": True, "result": {"inspection": {}, "scope": "package"}}), "")
        return subprocess.CompletedProcess([], 1, "technical failure", "")
    monkeypatch.setattr(bootstrap, "_run", run)
    with pytest.raises(ValueError): bootstrap.check_patch(patch, outcome)


def test_uv_installed_runtime_works_outside_checkout(handoff, tmp_path, network_guard):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv route runs on the designated Ubuntu 26.04 CI lane")
    reference, patch = handoff
    assessment = trusted_assessment(reference)
    workspace = tmp_path / "uv-runtime"; workspace.mkdir()
    environment = bootstrap._environment(workspace)
    wheel = workspace / assessment.wheel_name; wheel.write_bytes(assessment.wheel_bytes)
    target = workspace / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    # Installer preparation is separate. Actual installed runtime operations run
    # under the process-family network guard, including their import proof.
    for command in ([uv, "venv", "--offline", "--no-python-downloads", "--python", sys.executable, str(target.parent.parent)],
                    [uv, "pip", "install", "--offline", "--no-index", "--no-deps", "--python", str(target), str(wheel)]):
        result = subprocess.run(command, cwd=workspace, env=environment, capture_output=True)
        assert result.returncode == 0, result.stderr
    outcome = bootstrap.Bootstrap(assessment, "ready", None, target, workspace)
    assert bootstrap.check_patch(patch, outcome)["native_validation"] is True
