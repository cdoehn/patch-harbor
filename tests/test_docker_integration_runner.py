from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tomllib

import pytest

from tests.platform_support import PROJECT_ROOT, REQUIRES_BASH_DOCKER_RUNNER

RUNNER = PROJECT_ROOT / "scripts" / "run_docker_integration_tests.sh"
ENVIRONMENT_CHECK = PROJECT_ROOT / "scripts" / "check_docker_integration_environment.py"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile.integration"
DOCKER_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "docker-integration-tests.yml"


def _environment_check_module():
    spec = importlib.util.spec_from_file_location(
        "patchharbor_docker_environment_check",
        ENVIRONMENT_CHECK,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert len(calls) == 6

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
        "patchharbor-integration:ubuntu-24-04",
    ]
    assert all(call[: len(expected_prefix)] == expected_prefix for call in run_calls)
    assert run_calls[0][len(expected_prefix) :] == [
        "python",
        "scripts/check_docker_integration_environment.py",
        "--require-init",
    ]

    pytest_calls = run_calls[1:]
    marker_expressions = [
        call[max(index for index, value in enumerate(call) if value == "-m") + 1]
        for call in pytest_calls
    ]
    assert marker_expressions == [
        "not e2e and not acceptance and not platform and not packaging",
        "e2e or acceptance",
        "platform",
        "packaging",
    ]
    assert all("--timeout=120" in call for call in pytest_calls)
    assert all("--durations=20" in call for call in pytest_calls)

    expected_logs = {
        "00-build.log",
        "10-environment-preflight.log",
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
    assert len(calls) == 5
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


def test_environment_check_covers_every_declared_development_distribution() -> None:
    module = _environment_check_module()
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = project["project"]["optional-dependencies"]["dev"]
    expected_names = tuple(requirement.split(">=", 1)[0] for requirement in declared)

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
    workflow = DOCKER_WORKFLOW.read_text(encoding="utf-8")

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
    assert "PATCHHARBOR_DOCKER_SUITE_TIMEOUT_SECONDS" in runner
    assert "PATCHHARBOR_DOCKER_LOG_DIR" in runner
    assert "--timeout=\"$test_timeout_seconds\"" in runner
    assert "--durations=\"$test_durations\"" in runner
    assert "sleep " not in runner
    assert "retry" not in runner.lower()

    assert "timeout-minutes: 90" in workflow
    assert "if: always()" in workflow
    assert "uses: actions/upload-artifact@v7" in workflow
    assert "if-no-files-found: error" in workflow
