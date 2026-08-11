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
    "context_output.py",
    "errors.py",
    "execution.py",
    "git_capture.py",
    "git_objects.py",
    "git_patches.py",
    "git_commands.py",
    "interpreters.py",
    "models.py",
    "output.py",
    "parser.py",
    "payload_files.py",
    "physical_paths.py",
    "presentation.py",
    "registration.py",
    "registry.py",
    "repository.py",
    "repository_paths.py",
    "repository_state.py",
    "result_bundle.py",
    "result_bundle_snapshot.py",
    "result_bundle_writer.py",
    "locks.py",
    "resource_policy.py",
    "run_log.py",
    "sources.py",
    "state_fingerprint.py",
    "user_paths.py",
    "platform/__init__.py",
    "platform/errors.py",
    "platform/filesystem.py",
    "platform/lifecycle.py",
    "platform/locking.py",
    "platform/posix.py",
    "platform/runtime.py",
    "platform/windows.py",
}


def test_runtime_module_inventory_matches_the_release_architecture() -> None:
    observed = {
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*.py")
    }

    assert observed == EXPECTED_RUNTIME_FILES


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


def test_current_specification_changelog_and_plans_are_published() -> None:
    specification_path = PROJECT_ROOT / "spec" / "SPECIFICATION.md"
    changelog_path = PROJECT_ROOT / "spec" / "SPECIFICATION_CHANGELOG.md"
    cleanup_plan_path = (
        PROJECT_ROOT / "planning" / "1.1.0" / "commit-plan-cleanup.md"
    )
    implementation_plan_path = (
        PROJECT_ROOT / "planning" / "1.1.0" / "commit-plan.md"
    )
    historical_plan_path = PROJECT_ROOT / "planning" / "1.0.0" / "commit-plan.md"

    specification = specification_path.read_text(encoding="utf-8")
    cleanup_plan = cleanup_plan_path.read_text(encoding="utf-8")
    implementation_plan = implementation_plan_path.read_text(encoding="utf-8")

    assert "**Produktversion:** `1.1.0`" in specification
    assert "`spec/SPECIFICATION_CHANGELOG.md`" in specification
    assert "`planning/1.1.0/commit-plan-cleanup.md`" in specification
    assert "`planning/1.1.0/commit-plan.md`" in specification
    assert changelog_path.is_file()
    assert cleanup_plan.startswith(
        "# PatchHarbor 1.1.0 – Cleanup- und Rückbau-Commit-Plan"
    )
    assert implementation_plan.startswith(
        "# PatchHarbor 1.1.0 – W-R-C-Commit-Plan"
    )
    assert historical_plan_path.is_file()


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
