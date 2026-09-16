"""Static contract tests for the public GitHub Actions acceptance lanes."""

from __future__ import annotations

from tests.platform_support import PROJECT_ROOT


WORKFLOW_DIRECTORY = PROJECT_ROOT / ".github" / "workflows"
WORKFLOW_PATH = WORKFLOW_DIRECTORY / "acceptance-tests.yml"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
TEST_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "test.sh"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_acceptance_workflow_has_blocking_native_and_docker_release_gates() -> None:
    text = _workflow_text()

    for name, runner in (
        ("Release gate - Ubuntu 24.04", "ubuntu-24.04"),
        ("Release gate - Windows 2025", "windows-2025"),
        ("Release gate - Ubuntu 26.04", "ubuntu-26.04"),
    ):
        assert f"name: {name}" in text
        assert f"runner: {runner}" in text

    assert "ubuntu-docker-integration:" in text
    assert "name: Docker release gate - Ubuntu ${{ matrix.ubuntu }}" in text
    assert '          - "24.04"' in text
    assert '          - "26.04"' in text
    assert './scripts/run_docker_integration_tests.sh "${{ matrix.ubuntu }}"' in text
    assert "PATCHHARBOR_DOCKER_LOG_DIR" in text
    assert "if: always()" in text
    assert "uses: actions/upload-artifact@v7" in text
    assert "if-no-files-found: error" in text
    assert "timeout-minutes: 90" in text
    assert "preview:" not in text
    assert "continue-on-error" not in text
    assert "docker run" not in text
    assert "container:" not in text


def test_acceptance_workflow_is_the_only_docker_integration_entrypoint() -> None:
    runner_reference = "scripts/run_docker_integration_tests.sh"
    workflow_references = {
        path.name
        for path in WORKFLOW_DIRECTORY.glob("*.yml")
        if runner_reference in path.read_text(encoding="utf-8")
    }

    assert workflow_references == {"acceptance-tests.yml"}
    assert not (WORKFLOW_DIRECTORY / "docker-integration-tests.yml").exists()


def test_acceptance_workflow_uses_current_python_actions_and_grouped_suites() -> None:
    text = _workflow_text()

    assert "uses: actions/checkout@v7" in text
    assert "uses: actions/setup-python@v7" in text
    assert 'python-version: "3.12"' in text
    assert 'python -m pip install --disable-pip-version-check -e ".[dev]"' in text
    assert "Run core and architecture tests" in text
    assert '-m "not e2e and not acceptance and not platform and not packaging"' in text
    assert "Run E2E and acceptance tests" in text
    assert '-m "e2e or acceptance"' in text
    assert "Run platform tests" in text
    assert '-m "platform"' in text
    assert "Run packaging tests" in text
    assert '-m "packaging"' in text
    assert text.count("--durations=10") == 5


def test_acceptance_workflow_requires_both_windows_powershell_variants() -> None:
    text = _workflow_text()

    assert "Get-Command powershell.exe -ErrorAction Stop" in text
    assert "Get-Command pwsh -ErrorAction Stop" in text
    assert "powershell.exe -NoLogo -NoProfile -NonInteractive" in text
    assert "pwsh -NoLogo -NoProfile -NonInteractive" in text
    assert "windows_engine: powershell.exe" in text
    assert "PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE: ${{ matrix.windows_engine }}" in text
    assert "windows-powershell7-acceptance:" in text
    assert "name: Release gate - Windows 2025 - PowerShell 7" in text
    assert "runs-on: windows-2025" in text
    assert "PATCHHARBOR_WINDOWS_ACCEPTANCE_ENGINE: pwsh" in text
    assert "tests/test_windows_acceptance_e2e.py" in text
    assert "continue-on-error" not in text


def test_acceptance_workflow_is_automatic_manual_and_has_no_retries() -> None:
    text = _workflow_text()
    lowered = text.lower()

    assert "  push:" in text
    assert "  pull_request:" in text
    assert "  workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "retry" not in lowered
    assert "rerun" not in lowered
    assert "max-attempts" not in lowered


def test_pytest_groups_are_registered_and_assigned_to_public_suites() -> None:
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")

    assert 'addopts = "--strict-markers"' in pyproject
    for marker in ("acceptance", "e2e", "platform", "packaging"):
        assert f'"{marker}:' in pyproject

    expected = {
        "test_acceptance_e2e.py": "acceptance",
        "test_cli_e2e.py": "e2e",
        "test_platform_e2e.py": "platform",
        "test_v111_acceptance_e2e.py": "acceptance",
        "test_windows_acceptance_e2e.py": "platform",
        "test_packaging_e2e.py": "packaging",
    }
    for filename, marker in expected.items():
        text = (PROJECT_ROOT / "tests" / filename).read_text(encoding="utf-8")
        assert f"pytestmark = pytest.mark.{marker}" in text


def test_local_test_runner_reports_slowest_tests_with_configurable_count(monkeypatch) -> None:
    import subprocess
    from tools import test_runner as runner

    captured = []
    monkeypatch.setenv("PATCHHARBOR_TEST_DURATIONS", "7")
    def run(command, **kwargs):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main([]) == 0
    assert "--durations=7" in captured[0]


def test_native_acceptance_matrix_allows_120_minutes() -> None:
    text = _workflow_text()
    matrix_job = text.split("  acceptance:\n", 1)[1].split(
        "  windows-powershell7-acceptance:", 1,
    )[0]
    assert "    timeout-minutes: 120\n" in matrix_job
