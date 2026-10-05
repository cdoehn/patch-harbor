"""Real offline handoff and previous-path checks, independent of document prose."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest

from patchharbor import api
from scripts import runtime_bootstrap as bootstrap
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
    assessment = bootstrap.assess(reference, trusted_source_sha256=sha256(reference.read_bytes()).hexdigest())
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
    assessment = bootstrap.assess(reference, trusted_source_sha256=sha256(reference.read_bytes()).hexdigest())
    result = bootstrap.install(assessment, tmp_path / "runtime", installer_python=str(tmp_path / "absent-python"))
    assert result.status == "fallback" and result.reason == "installer_or_python_incompatible"
    assert bootstrap.check_patch(patch, result)["method"] == "previous_handoff"
