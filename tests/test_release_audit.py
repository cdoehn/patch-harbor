from __future__ import annotations

import re
import tomllib
from pathlib import Path

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
    "configuration.py",
    "context_output.py",
    "errors.py",
    "execution.py",
    "exchange.py",
    "exchange_paths.py",
    "exchange_state.py",
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
    "lifecycle.py",
    "loop.py",
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


def test_automatic_apply_discovery_stays_in_the_core_application_boundary() -> None:
    application_source = (CORE_PACKAGE_ROOT / "application.py").read_text(
        encoding="utf-8"
    )
    exchange_source = (CORE_PACKAGE_ROOT / "exchange.py").read_text(
        encoding="utf-8"
    )
    cli_source = (CORE_PACKAGE_ROOT / "cli.py").read_text(encoding="utf-8")

    assert "discover_exchange_patch" in application_source
    assert "scan_exchange_directory" in application_source
    assert "capture_repository_context_for_id" in application_source
    assert "resolve_patch_payloads" in exchange_source
    assert 'nargs="?"' in cli_source
    assert "scan_exchange_directory" not in cli_source


def test_result_bundle_defaults_use_shared_configuration_not_legacy_paths() -> None:
    target_source = (
        CORE_PACKAGE_ROOT / "result_bundle_target.py"
    ).read_text(encoding="utf-8")
    assert "from patchharbor.configuration import" in target_source
    assert "from patchharbor.path_configuration import" not in target_source
    assert "load_configuration" in target_source
    assert "uses_exchange_directory" in target_source

    for relative_path in ("apply_repository.py", "result_bundle.py"):
        source = (CORE_PACKAGE_ROOT / relative_path).read_text(encoding="utf-8")
        assert "paths.result_directory" not in source


def test_release_entry_point_and_runtime_dependency_contract_are_exact() -> None:
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = configuration["project"]

    assert project["scripts"] == {
        "patchharbor": "patchharbor.cli:main",
        "patchharbor-watcher": "patchharbor_watcher.cli:main",
    }
    assert project["dependencies"] == []
    assert configuration["tool"]["setuptools"]["data-files"] == {
        "share/patchharbor": ["CHAT_INSTRUCTIONS.md"]
    }

    build_source = (
        PROJECT_ROOT / "scripts" / "build_release.py"
    ).read_text(encoding="utf-8")
    assert '_RELEASE_INPUT_FILES = (\n    "CHAT_INSTRUCTIONS.md",' in (
        build_source
    )
    assert ".data/data/share/patchharbor/CHAT_INSTRUCTIONS.md" in (
        build_source
    )
    assert not (PROJECT_ROOT / "MANIFEST.in").exists()


def test_release_documents_exist_at_their_canonical_paths() -> None:
    expected_documents = {
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "CHAT_INSTRUCTIONS.md",
        PROJECT_ROOT / "spec" / "SPECIFICATION.md",
        PROJECT_ROOT / "spec" / "SPECIFICATION_CHANGELOG.md",
        PROJECT_ROOT / "planning" / "1.0.0" / "commit-plan.md",
        PROJECT_ROOT / "planning" / "1.1.0" / "commit-plan-cleanup.md",
        PROJECT_ROOT / "planning" / "1.1.0" / "commit-plan.md",
        PROJECT_ROOT / "planning" / "1.1.1" / "commit-plan.md",
    }

    assert all(path.is_file() for path in expected_documents)


def test_v111_commit_plan_has_one_consistent_consolidated_sequence() -> None:
    plan = (
        PROJECT_ROOT / "planning" / "1.1.1" / "commit-plan.md"
    ).read_text(encoding="utf-8")

    rows = re.findall(
        r"^\| (\d+) \| `([^`]+)` \| (DONE|NEXT|OPEN) "
        r"\| `([^`]+)` \|",
        plan,
        flags=re.MULTILINE,
    )
    assert [int(position) for position, *_ in rows] == list(range(1, 13))

    statuses = [status for _, _, status, _ in rows]
    completed = 0
    while completed < len(statuses) and statuses[completed] == "DONE":
        completed += 1
    if completed < len(statuses):
        assert statuses[completed] == "NEXT"
        assert statuses[completed + 1 :] == ["OPEN"] * (
            len(statuses) - completed - 1
        )
    else:
        assert "NEXT" not in statuses
        assert "OPEN" not in statuses

    status_match = re.search(
        r"\*\*Planstatus:\*\* (\d+) / 12 Plan-Commits umgesetzt;",
        plan,
    )
    assert status_match is not None
    assert int(status_match.group(1)) == completed

    identifiers = re.findall(
        r"^### ([0-9]+\.[a-z]+\.[WRC]) –",
        plan,
        flags=re.MULTILINE,
    )
    positions = re.findall(
        r"^\*\*Commitposition:\*\* (\d+) / 12<br>$",
        plan,
        flags=re.MULTILINE,
    )
    messages = re.findall(
        r"^\*\*Commit-Message:\*\* `([^`]+)`<br>$",
        plan,
        flags=re.MULTILINE,
    )
    assert identifiers == [identifier for _, identifier, _, _ in rows]
    assert [int(position) for position in positions] == list(range(1, 13))
    assert messages == [message for _, _, _, message in rows]

    specification = (
        PROJECT_ROOT / "spec" / "SPECIFICATION.md"
    ).read_text(encoding="utf-8")
    assert "🟩 1 / 12" in specification
    assert "11 Plan-Commits" in specification
    assert "🟩 1 / 33" not in specification
    assert "32 Plan-Commits" not in specification
    assert "`OFF-PLAN` `PLAN12`" in plan
    assert "ohne künstliche Einzeltest- oder Gesamtsuite-Timeouts" in plan
    assert "patchharbor bundle --output-dir \"$HOME/Downloads\"" in plan
    assert (
        "verwendet im dokumentierten Pixel-/Termux-Workflow keinen "
        "künstlichen Einzeltest- oder Gesamtsuite-Timeout"
    ) in specification
    assert "führt die zur Änderung passenden Tests mit harten Timeouts aus" not in specification


def test_exchange_attempt_state_is_core_owned_and_published_at_mutation_boundary() -> None:
    state_source = (CORE_PACKAGE_ROOT / "exchange_state.py").read_text(
        encoding="utf-8"
    )
    application_source = (CORE_PACKAGE_ROOT / "application.py").read_text(
        encoding="utf-8"
    )
    mutation_source = (CORE_PACKAGE_ROOT / "apply_mutation.py").read_text(
        encoding="utf-8"
    )
    exchange_source = (CORE_PACKAGE_ROOT / "exchange.py").read_text(
        encoding="utf-8"
    )
    user_paths_source = (CORE_PACKAGE_ROOT / "user_paths.py").read_text(
        encoding="utf-8"
    )

    assert "ExchangeFileIdentity" in state_source
    assert "mark_exchange_attempted" in state_source
    assert '"sha256"' in state_source
    assert '"attempted"' in state_source
    assert "atomic_replace_bytes" in state_source
    assert "mark_exchange_attempted" in application_source
    assert "before_mutation" in mutation_source
    assert "read_stable_regular_file_with_sha256" in exchange_source
    assert "exchange_state_path" in user_paths_source
    assert "exchange_state_lock_path" in user_paths_source

    forbidden_exchange_mutations = (
        ".unlink(",
        ".rename(",
        ".replace(",
        "shutil.move",
        "os.remove",
    )
    assert not any(
        operation in exchange_source for operation in forbidden_exchange_mutations
    )


def test_watcher_is_only_shared_configuration_lifecycle_and_core_apply() -> None:
    cli_source = (WATCHER_PACKAGE_ROOT / "cli.py").read_text(encoding="utf-8")
    loop_source = (WATCHER_PACKAGE_ROOT / "loop.py").read_text(encoding="utf-8")
    boundary_source = (WATCHER_PACKAGE_ROOT / "apply_boundary.py").read_text(
        encoding="utf-8"
    )
    user_paths_source = (CORE_PACKAGE_ROOT / "user_paths.py").read_text(
        encoding="utf-8"
    )
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "load_configuration" in cli_source
    assert "revalidate_exchange_directory" in cli_source
    assert "run_shared_exchange_watcher" in cli_source
    assert "delegate_to_automatic_apply" in cli_source
    assert '"apply", "--json"' in boundary_source
    assert "delegate_to_apply" not in boundary_source
    assert "scan_exchange_directory" not in loop_source
    assert "ExchangeFileIdentity" not in loop_source
    assert "os.scandir" not in loop_source
    assert "sha256" not in loop_source
    assert "zipfile" not in loop_source
    assert "watcher_configuration_path" not in user_paths_source
    assert "path_configuration_path" not in user_paths_source
    assert "watcher_state_directory" not in user_paths_source
    assert "result_directory" not in user_paths_source
    assert "patchharbor-watcher --configure" not in readme
    assert "patchharbor configure exchange-directory" in readme
    assert not (CORE_PACKAGE_ROOT / "path_configuration.py").exists()
    for removed in ("configuration.py", "loop_guard.py", "state.py"):
        assert not (WATCHER_PACKAGE_ROOT / removed).exists()
