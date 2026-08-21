from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from tests.platform_support import PROJECT_ROOT, REQUIRES_BASH_DOCKER_RUNNER

RUNNER = PROJECT_ROOT / "scripts" / "run_docker_integration_tests.sh"
ENVIRONMENT_CHECK = PROJECT_ROOT / "scripts" / "check_docker_integration_environment.py"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile.integration"
DOCKER_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "docker-integration-tests.yml"


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
def test_docker_runner_builds_once_and_runs_every_gate_with_init(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    call_log = tmp_path / "docker-calls.jsonl"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

log = Path(os.environ["PATCHHARBOR_FAKE_DOCKER_LOG"])
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(fake_bin), environment["PATH"]))
    environment["PATCHHARBOR_FAKE_DOCKER_LOG"] = str(call_log)
    environment["PATCHHARBOR_DOCKER_BUILD_TIMEOUT_SECONDS"] = "10"
    environment["PATCHHARBOR_DOCKER_PREFLIGHT_TIMEOUT_SECONDS"] = "10"
    environment["PATCHHARBOR_DOCKER_SUITE_TIMEOUT_SECONDS"] = "10"

    completed = subprocess.run(
        ["bash", str(RUNNER), "24.04"],
        cwd=PROJECT_ROOT,
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
    assert "UBUNTU_VERSION=24.04" in build_call
    assert build_call[-1] == str(PROJECT_ROOT)

    run_calls = calls[1:]
    assert all(call[:3] == ["run", "--rm", "--init"] for call in run_calls)
    assert all(call[3] == "patchharbor-integration:ubuntu-24-04" for call in run_calls)
    assert run_calls[0][4:] == [
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


def test_docker_integration_image_provides_the_release_gate_environment() -> None:
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
    assert "python scripts/check_docker_integration_environment.py" in dockerfile
    assert "python scripts/build_release.py --outdir /tmp/patchharbor-dist" in dockerfile

    assert "sys.version_info[:2] == (3, 12)" in environment_check
    assert 'for command in ("bash", "git", "pipx")' in environment_check
    assert 'for module in ("build", "pytest", "pytest_timeout")' in environment_check
    assert 'init_name in {"docker-init", "tini"}' in environment_check

    assert "docker run --rm --init" in runner
    assert "PATCHHARBOR_DOCKER_BUILD_TIMEOUT_SECONDS" in runner
    assert "PATCHHARBOR_DOCKER_PREFLIGHT_TIMEOUT_SECONDS" in runner
    assert "PATCHHARBOR_DOCKER_SUITE_TIMEOUT_SECONDS" in runner
    assert "--timeout=\"$test_timeout_seconds\"" in runner
    assert "timeout-minutes: 90" in workflow
