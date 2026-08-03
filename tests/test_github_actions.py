"""Static contract tests for the public GitHub Actions acceptance lanes."""

from __future__ import annotations

from tests.platform_support import PROJECT_ROOT


WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "acceptance-tests.yml"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_acceptance_workflow_separates_release_gates_and_preview_lane() -> None:
    text = _workflow_text()

    assert "name: Release gate - Ubuntu 24.04" in text
    assert "runner: ubuntu-24.04" in text
    assert "name: Release gate - Windows 2025" in text
    assert "runner: windows-2025" in text
    assert "name: Preview - Ubuntu 26.04" in text
    assert "runner: ubuntu-26.04" in text
    assert text.count("preview: false") == 2
    assert text.count("preview: true") == 1
    assert "continue-on-error: ${{ matrix.preview }}" in text
    assert "docker run" not in text
    assert "container:" not in text


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


def test_acceptance_workflow_requires_both_windows_powershell_variants() -> None:
    text = _workflow_text()

    assert "Get-Command powershell.exe -ErrorAction Stop" in text
    assert "Get-Command pwsh -ErrorAction Stop" in text
    assert "powershell.exe -NoLogo -NoProfile -NonInteractive" in text
    assert "pwsh -NoLogo -NoProfile -NonInteractive" in text


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
        "test_packaging_e2e.py": "packaging",
    }
    for filename, marker in expected.items():
        text = (PROJECT_ROOT / "tests" / filename).read_text(encoding="utf-8")
        assert f"pytestmark = pytest.mark.{marker}" in text
