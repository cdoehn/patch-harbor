from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Explicit build/dev dependency on Python 3.10 only.
    import tomli as tomllib

import pytest

from tests.platform_support import PROJECT_ROOT, REQUIRES_BASH_DOCKER_RUNNER
from tests.runner_support import ENVIRONMENT_CHECK, _environment_check_module

RUNNER = PROJECT_ROOT / "scripts" / "run_docker_integration_tests.sh"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile.integration"
ACCEPTANCE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "acceptance-tests.yml"


def _write_fake_docker(fake_bin: Path) -> Path:
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
log = Path(os.environ["PATCHHARBOR_FAKE_DOCKER_LOG"])
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(arguments) + "\\n")
print("fake docker stdout", flush=True)
print("fake docker stderr", file=sys.stderr, flush=True)
fail_argument = os.environ.get("PATCHHARBOR_FAKE_DOCKER_FAIL_ARGUMENT")
if fail_argument and fail_argument in arguments:
    raise SystemExit(int(os.environ.get("PATCHHARBOR_FAKE_DOCKER_FAIL_CODE", "17")))
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    return fake_docker


def _runner_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)
    call_log = tmp_path / "docker-calls.jsonl"
    diagnostic_directory = tmp_path / "diagnostics"
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(fake_bin), environment["PATH"]))
    environment["PATCHHARBOR_FAKE_DOCKER_LOG"] = str(call_log)
    environment["PATCHHARBOR_DOCKER_LOG_DIR"] = str(diagnostic_directory)
    environment["PATCHHARBOR_DOCKER_BUILD_TIMEOUT_SECONDS"] = "10"
    environment["PATCHHARBOR_DOCKER_PREFLIGHT_TIMEOUT_SECONDS"] = "10"
    environment["PATCHHARBOR_DOCKER_SUITE_TIMEOUT_SECONDS"] = "10"
    return environment, call_log, diagnostic_directory


def _summary(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


@REQUIRES_BASH_DOCKER_RUNNER
def test_docker_integration_runner_accepts_only_supported_ubuntu_versions() -> None:
    completed = subprocess.run(
        ["bash", str(RUNNER), "25.10"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert completed.returncode == 2


@REQUIRES_BASH_DOCKER_RUNNER
def test_docker_runner_builds_once_and_runs_every_offline_gate_with_diagnostics(
    tmp_path: Path,
) -> None:
    environment, call_log, diagnostic_directory = _runner_environment(tmp_path)

    completed = subprocess.run(
        ["bash", str(RUNNER), "24.04"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 0
    calls = [json.loads(line) for line in call_log.read_text().splitlines()]
    assert len(calls) == 7

    build_call = calls[0]
    assert build_call[0] == "build"
    assert "--progress=plain" in build_call
    assert "UBUNTU_VERSION=24.04" in build_call
    assert build_call[-1] == str(PROJECT_ROOT)

    run_calls = calls[1:]
    expected_prefix = [
        "run",
        "--rm",
        "--init",
        "--network",
        "none",
        "--workdir",
        "/workspace",
        "--mount",
        f"type=bind,source={diagnostic_directory},target=/evidence",
        "patchharbor-integration:ubuntu-24-04",
    ]
    assert all(call[: len(expected_prefix)] == expected_prefix for call in run_calls)
    assert run_calls[0][len(expected_prefix) :] == [
        "python",
        "scripts/check_docker_integration_environment.py",
        "--require-init",
    ]

    assert "scripts/capture_ci_build.py" in run_calls[1]
    assert "--commit" in run_calls[1]
    for call in run_calls[1:]:
        assert call[len(expected_prefix):len(expected_prefix) + 2] == [
            "python", "scripts/run_docker_report.py"]
        assert call[call.index("--uid") + 1] == str(os.getuid())
        assert call[call.index("--gid") + 1] == str(os.getgid())
        boundary = call.index("--")
        report = call[call.index("--report") + 1]
        assert call[boundary + 1] == "python"
        assert call[call.index("--report", boundary) + 1] == report
    pytest_calls = run_calls[2:]
    scopes = [call[call.index("--suite") + 1] for call in pytest_calls]
    assert scopes == ["core", "e2e", "platform", "packaging"]
    assert all(call[call.index("--report") + 1] == f"/evidence/patchharbor-{suite}-tests.json"
               for call, suite in zip(pytest_calls, scopes))
    assert all("tools/run_tests.py" in call for call in pytest_calls)
    assert all("--durations=20" in call for call in pytest_calls)
    assert not any(value.startswith("--timeout") for call in pytest_calls for value in call)

    expected_logs = {
        "00-build.log",
        "10-environment-preflight.log",
        "15-build-evidence.log",
        "20-core-and-architecture.log",
        "30-e2e-and-acceptance.log",
        "40-platform.log",
        "50-packaging.log",
        "summary.txt",
    }
    assert {path.name for path in diagnostic_directory.iterdir()} == expected_logs
    assert _summary(diagnostic_directory / "summary.txt")["status"] == "0"


@REQUIRES_BASH_DOCKER_RUNNER
def test_docker_runner_preserves_complete_failed_gate_diagnostics(
    tmp_path: Path,
) -> None:
    environment, call_log, diagnostic_directory = _runner_environment(tmp_path)
    environment["PATCHHARBOR_FAKE_DOCKER_FAIL_ARGUMENT"] = "platform"
    environment["PATCHHARBOR_FAKE_DOCKER_FAIL_CODE"] = "17"

    completed = subprocess.run(
        ["bash", str(RUNNER), "26.04"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 17
    calls = [json.loads(line) for line in call_log.read_text().splitlines()]
    assert len(calls) == 6
    assert any("platform" in call for call in calls)
    assert not (diagnostic_directory / "50-packaging.log").exists()
    failed_log = (diagnostic_directory / "40-platform.log").read_text(
        encoding="utf-8"
    )
    assert "fake docker stdout" in failed_log
    assert "fake docker stderr" in failed_log
    summary = _summary(diagnostic_directory / "summary.txt")
    assert summary["status"] == "17"
    assert summary["stage"] == "platform tests"
    assert Path(summary["log"]) == diagnostic_directory / "40-platform.log"


@REQUIRES_BASH_DOCKER_RUNNER
def test_docker_runner_preserves_gate_status_when_summary_publication_fails(
    tmp_path: Path,
) -> None:
    environment, _call_log, diagnostic_directory = _runner_environment(tmp_path)
    fake_bin = Path(environment["PATH"].split(os.pathsep, 1)[0])
    fake_mv = fake_bin / "mv"
    fake_mv.write_text("#!/bin/sh\nexit 19\n", encoding="utf-8")
    fake_mv.chmod(0o755)
    environment["PATCHHARBOR_FAKE_DOCKER_FAIL_ARGUMENT"] = "platform"
    environment["PATCHHARBOR_FAKE_DOCKER_FAIL_CODE"] = "17"

    completed = subprocess.run(
        ["bash", str(RUNNER), "26.04"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 17
    assert not (diagnostic_directory / "summary.txt").exists()
    assert not tuple(diagnostic_directory.glob("summary.txt.tmp.*"))


def test_environment_check_covers_every_declared_development_distribution() -> None:
    module = _environment_check_module()
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = project["project"]["optional-dependencies"]["dev"]
    from packaging.requirements import Requirement
    expected_names = tuple(r.name for text in declared if
                           (r := Requirement(text)).marker is None or r.marker.evaluate(environment={"extra": "dev"}))
    assert module.declared_dev_distribution_names() == expected_names


def test_environment_check_rejects_a_missing_declared_distribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _environment_check_module()
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[project.optional-dependencies]
dev = ["missing-patchharbor-distribution>=1"]
""",
        encoding="utf-8",
    )

    def missing(_name: str):
        raise module.PackageNotFoundError

    monkeypatch.setattr(module, "distribution", missing)
    with pytest.raises(SystemExit):
        module._require_declared_dev_distributions(pyproject)


def test_docker_integration_image_provides_a_deterministic_release_gate() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    environment_check = ENVIRONMENT_CHECK.read_text(encoding="utf-8")
    workflow = ACCEPTANCE_WORKFLOW.read_text(encoding="utf-8")

    assert "ARG UBUNTU_VERSION=24.04" in dockerfile
    assert "ARG PYTHON_VERSION=3.12.14" in dockerfile
    assert "Python-${PYTHON_VERSION}.tar.xz" in dockerfile
    assert "sha256sum --check --strict" in dockerfile
    assert "python3.12 -m venv" in dockerfile
    assert 'project["project"]["optional-dependencies"]["dev"]' in dockerfile
    assert "python -m pip check" in dockerfile
    assert "python scripts/check_docker_integration_environment.py" in dockerfile
    assert "python scripts/build_release.py --outdir /tmp/patchharbor-dist" in dockerfile
    assert "pip install --upgrade" not in dockerfile
    for expected in (
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        "TZ=UTC",
        "PYTHONHASHSEED=0",
        "PYTHONUTF8=1",
        "GIT_CONFIG_NOSYSTEM=1",
        "GIT_CONFIG_GLOBAL=/dev/null",
        "GIT_TERMINAL_PROMPT=0",
    ):
        assert expected in dockerfile

    assert "sys.version_info[:2] == (3, 12)" in environment_check
    assert "declared_dev_distribution_names" in environment_check
    assert "_require_deterministic_environment()" in environment_check
    assert "_require_empty_global_git_configuration()" in environment_check
    assert 'init_name in {"docker-init", "tini"}' in environment_check

    assert "docker run --rm --init --network none --workdir /workspace" in runner
    assert "PATCHHARBOR_DOCKER_BUILD_TIMEOUT_SECONDS" in runner
    assert "PATCHHARBOR_DOCKER_PREFLIGHT_TIMEOUT_SECONDS" in runner
    assert "PATCHHARBOR_DOCKER_SUITE_TIMEOUT_SECONDS" not in runner
    assert "PATCHHARBOR_DOCKER_LOG_DIR" in runner
    assert "test_timeout_seconds" not in runner
    assert "--durations=\"$test_durations\"" in runner
    assert "sleep " not in runner
    assert "retry" not in runner.lower()

    assert "timeout-minutes: 90" in workflow
    assert "if: always()" in workflow
    assert "uses: actions/upload-artifact@v7" in workflow
    assert "if-no-files-found: error" in workflow


@pytest.mark.parametrize('python_version,expected', [
    ('3.10', ('build', 'tomli', 'pytest')),
    ('3.11', ('build', 'pytest')),
    ('3.12', ('build', 'pytest')),
    ('3.14', ('build', 'pytest')),
])
def test_environment_check_evaluates_conditional_requirements(tmp_path, python_version, expected):
    module = _environment_check_module()
    project = tmp_path / 'pyproject.toml'
    project.write_text("[project.optional-dependencies]\ndev = [\"build>=1.2\", \"tomli>=2.0.1; python_version < '3.11'\", \"pytest>=8.4; extra == 'dev'\", \"not-for-linux; sys_platform == 'win32'\"]\n")
    assert module.declared_dev_distribution_names(project, environment={
        'python_version': python_version, 'sys_platform': 'linux'}) == expected


def test_docker_preflight_does_not_query_an_inapplicable_distribution(tmp_path, monkeypatch):
    module = _environment_check_module()
    project = tmp_path / 'pyproject.toml'
    project.write_text("[project.optional-dependencies]\ndev = [\"build>=1.2\", \"unavailable; python_version < '1'\"]\n")
    calls = []
    def installed(name):
        calls.append(name)
        if name != 'build': raise module.PackageNotFoundError(name)
        from types import SimpleNamespace
        return SimpleNamespace(version='1.2.0')
    monkeypatch.setattr(module, 'distribution', installed)
    module._require_declared_dev_distributions(project)
    assert calls == ['build']


@pytest.mark.parametrize('requirement', ['pytest>=', 'pytest; python_version ??? 3.10'])
def test_docker_preflight_rejects_invalid_requirement_syntax(tmp_path, requirement):
    module = _environment_check_module()
    project = tmp_path / 'pyproject.toml'
    project.write_text('[project.optional-dependencies]\ndev = [' + json.dumps(requirement) + ']\n')
    with pytest.raises(SystemExit): module.declared_dev_distribution_names(project)


def _report_export_module():
    spec = importlib.util.spec_from_file_location(
        "patchharbor_docker_report", PROJECT_ROOT / "scripts/run_docker_report.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_POSIX_REPORTS = pytest.mark.skipif(os.name != "posix", reason="Docker report export uses POSIX ownership")


@_POSIX_REPORTS
@pytest.mark.parametrize("status", [0, 17])
def test_docker_report_export_preserves_private_bytes_and_failed_gate_status(tmp_path, status):
    report = tmp_path / "report.json"
    counter = tmp_path / "executions"
    unrelated = tmp_path / "untouched.json"
    unrelated.write_bytes(b"private unrelated evidence")
    unrelated.chmod(0o640)
    before = unrelated.stat()
    # Exercise the actual CLI and a real atomic 0600 producer, including failure.
    program = """import os, pathlib, sys, tempfile
report, counter = map(pathlib.Path, sys.argv[1:3])
with counter.open('a') as stream: stream.write('once\\n')
with tempfile.NamedTemporaryFile(dir=report.parent, delete=False) as stream:
    stream.write(b'{"status": "evidence"}\\n'); temporary = stream.name
os.replace(temporary, report)
raise SystemExit(int(sys.argv[3]))
"""
    completed = subprocess.run([
        sys.executable, str(PROJECT_ROOT / "scripts/run_docker_report.py"),
        "--report", str(report), "--uid", str(os.getuid()), "--gid", str(os.getgid()), "--",
        sys.executable, "-c", program, str(report), str(counter), str(status),
    ], capture_output=True, timeout=10)
    assert completed.returncode == status, completed.stderr
    assert report.read_bytes() == b'{"status": "evidence"}\n'
    metadata = report.stat()
    assert (metadata.st_uid, metadata.st_gid, stat.S_IMODE(metadata.st_mode)) == (os.getuid(), os.getgid(), 0o600)
    assert counter.read_text().splitlines() == ["once"]
    assert unrelated.stat() == before
    assert unrelated.read_bytes() == b"private unrelated evidence"


@_POSIX_REPORTS
@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "fifo", "missing"])
def test_docker_report_export_rejects_links_and_nonregular_files(tmp_path, kind):
    module = _report_export_module()
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"unchanged")
    outside.chmod(0o640)
    report = tmp_path / "report.json"
    if kind == "symlink": report.symlink_to(outside)
    elif kind == "hardlink": os.link(outside, report)
    elif kind == "directory": report.mkdir()
    elif kind == "fifo": os.mkfifo(report)
    before = outside.stat()
    with pytest.raises((OSError, ValueError)):
        module.export_report(report, os.getuid(), os.getgid())
    assert outside.stat() == before
    assert outside.read_bytes() == b"unchanged"


@_POSIX_REPORTS
@pytest.mark.parametrize("failure", ["missing", "chown", "owner_mismatch"])
@pytest.mark.parametrize("status", [0, 17])
def test_docker_export_failure_cannot_hide_test_failure_or_report_success(tmp_path, monkeypatch, status, failure):
    module = _report_export_module()
    report = tmp_path / "report.json"
    child = [sys.executable, "-c", "import sys; raise SystemExit(int(sys.argv[1]))", str(status)]
    descriptors = []
    if failure != "missing":
        report.write_bytes(b"evidence")
        def chown(descriptor, uid, gid):
            descriptors.append(descriptor)
            if failure == "chown": raise PermissionError("simulated chown denial")
        monkeypatch.setattr(module.os, "fchown", chown)
    uid = os.getuid() + 1 if failure == "owner_mismatch" else os.getuid()
    assert module.run_gate(child, report, uid, os.getgid()) == (status or 1)
    for descriptor in descriptors:
        with pytest.raises(OSError): os.fstat(descriptor)
