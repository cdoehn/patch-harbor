from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "docker" / "Dockerfile.integration"
RUNNER = ROOT / "scripts" / "run_docker_integration_tests.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "docker-integration-tests.yml"
DOCS = ROOT / "docs" / "docker-integration-tests.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dockerfile_builds_wheel_and_runs_full_tests() -> None:
    text = read(DOCKERFILE)

    assert "ARG UBUNTU_VERSION=24.04" in text
    assert "FROM ubuntu:${UBUNTU_VERSION}" in text
    assert "python -m build --wheel" in text
    assert "python -m pip install --force-reinstall" in text
    assert "python -m pip check" in text
    assert 'CMD ["python", "-m", "pytest", "-q", "tests"]' in text


def test_local_runner_defaults_to_both_supported_ubuntu_versions() -> None:
    text = read(RUNNER)

    assert 'versions=("24.04" "26.04")' in text
    assert "docker build" in text
    assert "docker run --rm" in text
    assert "Docker integration tests passed" in text
    assert os.access(RUNNER, os.X_OK)

    result = subprocess.run(
        ["bash", "-n", str(RUNNER)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_github_workflow_is_manual_only_and_uses_a_matrix() -> None:
    text = read(WORKFLOW)

    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "push:" not in text
    assert '          - "24.04"' in text
    assert '          - "26.04"' in text
    assert "actions/checkout@v7" in text
    assert './scripts/run_docker_integration_tests.sh "${{ matrix.ubuntu }}"' in text


def test_documentation_marks_the_suite_as_explicitly_started() -> None:
    text = read(DOCS)

    assert "deliberately separate" in text
    assert "normal test" in text
    assert "workflow_dispatch" in text
    assert "default branch" in text
    assert "./scripts/run_docker_integration_tests.sh" in text


def test_new_files_do_not_contain_private_local_values() -> None:
    combined = "\n".join(read(path) for path in (DOCKERFILE, RUNNER, WORKFLOW, DOCS))
    private_user = "chris" + "tian"
    private_person = "Chris" + "tian D" + "\u00f6hn"

    for forbidden in ("/home/", private_user, private_person, "repo_dossier"):
        assert forbidden not in combined
