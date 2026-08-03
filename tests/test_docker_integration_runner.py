from __future__ import annotations

import subprocess

from tests.platform_support import PROJECT_ROOT, REQUIRES_BASH_DOCKER_RUNNER
RUNNER = PROJECT_ROOT / "scripts" / "run_docker_integration_tests.sh"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile.integration"


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
    assert completed.stdout == ""
    assert "Usage:" in completed.stderr
    assert "24.04|26.04" in completed.stderr


def test_docker_integration_image_installs_required_test_tools_and_init() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")

    assert "pytest-timeout" in dockerfile
    assert "pipx" in dockerfile
    assert "pip install --upgrade pip setuptools wheel" in dockerfile
    assert "pip install --upgrade pip setuptools wheel build pytest" not in dockerfile
    assert "PY_TEST_REQUIREMENTS" not in dockerfile
    assert "python -c" in dockerfile
    assert '["project"]["optional-dependencies"]["dev"]' in dockerfile
    assert dockerfile.count("pip install --requirement") == 1
    assert "pip show pytest-timeout pipx" in dockerfile
    assert "python scripts/build_release.py --outdir /tmp/patchharbor-dist" in dockerfile
    assert "python -m build --wheel --outdir /tmp/patchharbor-dist" not in dockerfile
    assert "docker run --rm --init" in runner
    assert '--timeout="$test_timeout_seconds"' in runner
