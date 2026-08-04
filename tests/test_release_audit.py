from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib

from tests.platform_support import PROJECT_ROOT


PACKAGE_ROOT = PROJECT_ROOT / "src" / "patchharbor"
EXPECTED_RUNTIME_FILES = {
    "__init__.py",
    "application.py",
    "bundle_paths.py",
    "bundles.py",
    "cli.py",
    "errors.py",
    "execution.py",
    "interpreters.py",
    "models.py",
    "output.py",
    "parser.py",
    "payload_files.py",
    "presentation.py",
    "resource_policy.py",
    "run_log.py",
    "sources.py",
    "platform/__init__.py",
    "platform/errors.py",
    "platform/filesystem.py",
    "platform/lifecycle.py",
    "platform/posix.py",
    "platform/runtime.py",
    "platform/windows.py",
}
DEFERRED_FEATURE_MODULES = {
    "clipboard.py",
    "git.py",
    "save.py",
    "ssh.py",
    "tests.py",
    "websocket.py",
}


def test_runtime_module_inventory_matches_the_release_architecture() -> None:
    observed = {
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*.py")
    }

    assert observed == EXPECTED_RUNTIME_FILES
    assert observed.isdisjoint(DEFERRED_FEATURE_MODULES)


def test_release_entry_point_and_runtime_dependency_contract_are_exact() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert project["scripts"] == {"patchharbor": "patchharbor.cli:main"}
    assert project["dependencies"] == []


def test_release_builder_uses_only_audited_source_inputs() -> None:
    source = (PROJECT_ROOT / "scripts" / "build_release.py").read_text(
        encoding="utf-8"
    )
    for required in (
        '"LICENSE"',
        '"README.md"',
        '"pyproject.toml"',
        '"src"',
        'TemporaryDirectory(prefix="patchharbor-release-")',
    ):
        assert required in source
    for forbidden in (
        '"MANIFEST.in"',
        '"tests"',
        "scripts_directory",
        "planning",
        ".github",
        "docker",
    ):
        assert forbidden not in source

    assert not (PROJECT_ROOT / "MANIFEST.in").exists()


def test_version_one_plan_is_closed_without_publishing_deferred_scope() -> None:
    plan = (
        PROJECT_ROOT
        / "planning"
        / "0.0.1"
        / "patchharbor-specifikation-and-commit-plan.md"
    ).read_text(encoding="utf-8")

    for required in (
        "## Review nach Step 4.d und Meilenstein 4",
        "**Umsetzungsstand Version 1:** `60 / 60` geplante W-R-C-Commits",
        "Release-Tag und Veröffentlichung bleiben bis zu grünen stabilen CI-Gates",
        "WebSocket bleibt außerhalb von Version 1",
    ):
        assert required in plan
    assert "## Step 5." not in plan


def test_release_builder_stages_only_the_release_source_set(
    tmp_path: Path,
) -> None:
    script_path = PROJECT_ROOT / "scripts" / "build_release.py"
    spec = importlib.util.spec_from_file_location(
        "patchharbor_release_builder",
        script_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    stage = tmp_path / "stage"
    stage.mkdir()
    module._copy_release_inputs(stage)

    assert {path.name for path in stage.iterdir()} == {
        "LICENSE",
        "README.md",
        "pyproject.toml",
        "src",
    }
    assert not any(stage.rglob("*.log"))
    assert not (stage / "planning").exists()
    assert not (stage / ".github").exists()
    assert not (stage / "docker").exists()
