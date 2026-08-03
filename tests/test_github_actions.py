"""Static contract tests for the public GitHub Actions acceptance matrix."""

from __future__ import annotations

from tests.platform_support import PROJECT_ROOT


WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "acceptance-tests.yml"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_acceptance_workflow_runs_on_all_required_real_runners() -> None:
    text = _workflow_text()

    assert "runner: ubuntu-24.04" in text
    assert "runner: ubuntu-26.04" in text
    assert "runner: windows-2025" in text
    assert "docker run" not in text
    assert "container:" not in text


def test_acceptance_workflow_uses_current_python_actions_and_full_suite() -> None:
    text = _workflow_text()

    assert "uses: actions/checkout@v7" in text
    assert "uses: actions/setup-python@v7" in text
    assert 'python-version: "3.12"' in text
    assert 'python -m pip install --disable-pip-version-check -e ".[dev]"' in text
    assert "python -m pytest -q --timeout=120 tests" in text


def test_acceptance_workflow_requires_both_windows_powershell_variants() -> None:
    text = _workflow_text()

    assert "Get-Command powershell.exe -ErrorAction Stop" in text
    assert "Get-Command pwsh -ErrorAction Stop" in text
    assert "powershell.exe -NoLogo -NoProfile -NonInteractive" in text
    assert "pwsh -NoLogo -NoProfile -NonInteractive" in text


def test_acceptance_workflow_is_automatic_and_manually_runnable() -> None:
    text = _workflow_text()

    assert "  push:" in text
    assert "  pull_request:" in text
    assert "  workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
