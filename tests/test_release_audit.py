from __future__ import annotations

from pathlib import Path
import tomllib

from tests.platform_support import PROJECT_ROOT


CORE_PACKAGE_ROOT = PROJECT_ROOT / "src" / "patchharbor"
WATCHER_PACKAGE_ROOT = PROJECT_ROOT / "src" / "patchharbor_watcher"
EXPECTED_CORE_RUNTIME_FILES = {
    "__init__.py",
    "application.py",
    "apply_mutation.py",
    "apply_preflight.py",
    "apply_repository.py",
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
    "json_document.py",
    "models.py",
    "output.py",
    "parser.py",
    "patch_manifest.py",
    "patch_package.py",
    "payload_files.py",
    "path_configuration.py",
    "presentation.py",
    "registration.py",
    "registry.py",
    "repository.py",
    "repository_paths.py",
    "repository_state.py",
    "result_bundle.py",
    "result_bundle_capture.py",
    "result_bundle_publication.py",
    "result_bundle_snapshot.py",
    "result_bundle_target.py",
    "result_bundle_writer.py",
    "locks.py",
    "resource_policy.py",
    "run_log.py",
    "run_report.py",
    "sources.py",
    "state_fingerprint.py",
    "temporary_resources.py",
    "user_paths.py",
    "zip_payloads.py",
    "platform/__init__.py",
    "platform/errors.py",
    "platform/filesystem.py",
    "platform/lifecycle.py",
    "platform/locking.py",
    "platform/paths.py",
    "platform/posix.py",
    "platform/runtime.py",
    "platform/windows.py",
}
EXPECTED_WATCHER_RUNTIME_FILES = {
    "__init__.py",
    "apply_boundary.py",
    "cli.py",
    "configuration.py",
    "lifecycle.py",
    "loop.py",
    "loop_guard.py",
    "state.py",
    "systemd_linux.py",
}


def _runtime_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
    }


def test_runtime_module_inventory_matches_the_release_architecture() -> None:
    assert _runtime_files(CORE_PACKAGE_ROOT) == EXPECTED_CORE_RUNTIME_FILES
    assert _runtime_files(WATCHER_PACKAGE_ROOT) == EXPECTED_WATCHER_RUNTIME_FILES
    assert not (PROJECT_ROOT / "src" / "repo_assist").exists()
    assert not (PROJECT_ROOT / "src" / "promptbridge").exists()


def test_release_entry_point_and_runtime_dependency_contract_are_exact() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert project["scripts"] == {
        "patchharbor": "patchharbor.cli:main",
        "patchharbor-watcher": "patchharbor_watcher.cli:main",
    }
    assert project["dependencies"] == []


def test_release_documents_exist_at_their_canonical_paths() -> None:
    expected_documents = {
        PROJECT_ROOT / "spec" / "SPECIFICATION.md",
        PROJECT_ROOT / "spec" / "SPECIFICATION_CHANGELOG.md",
        PROJECT_ROOT / "planning" / "1.0.0" / "commit-plan.md",
        PROJECT_ROOT / "planning" / "1.1.0" / "commit-plan-cleanup.md",
        PROJECT_ROOT / "planning" / "1.1.0" / "commit-plan.md",
    }

    assert all(path.is_file() for path in expected_documents)
