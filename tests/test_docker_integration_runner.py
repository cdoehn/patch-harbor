from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "scripts" / "run_docker_integration_tests.sh"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile.integration"


@pytest.mark.skipif(os.name == "nt", reason="Docker integration runner is Linux-only")
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
    assert completed.stdout == ""
    assert "Usage:" in completed.stderr
    assert "24.04|26.04" in completed.stderr


def test_docker_integration_image_installs_required_test_tools_and_init() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")

    assert "pytest-timeout" in dockerfile
    assert "pipx" in dockerfile
    assert "pip show pytest-timeout pipx" in dockerfile
    assert "docker run --rm --init" in runner
    assert '--timeout="$test_timeout_seconds"' in runner
