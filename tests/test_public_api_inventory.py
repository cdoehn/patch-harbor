from __future__ import annotations

import dataclasses
import importlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_API = ROOT / "docs" / "public-api-inventory.md"
PUBLIC_DOCS_INVENTORY = ROOT / "docs" / "public-docs-inventory.md"
MIGRATION_ARTIFACT_INVENTORY = ROOT / "docs" / "migration-artifact-inventory.md"
CLI_DOC = ROOT / "docs" / "cli.md"
RUNNER_DOC = ROOT / "docs" / "runner.md"
COMPAT_DOC = ROOT / "docs" / "compatibility.md"

PUBLIC_OBJECTS = {
    "patchharbor.cli": ["build_parser", "main"],
    "patchharbor.patch_lint_api": [
        "default_patch_lint_rules",
        "lint_patch_text",
        "lint_patch_file",
        "lint_patch_files",
        "render_patch_lint_result",
        "patch_lint_rule_names",
    ],
    "patchharbor.runner_core": [
        "RunnerCoreError",
        "RunnerExecutionConfig",
        "check_bash_syntax",
        "lint_script_for_runner",
        "execute_patch_script",
        "run_patch_script",
    ],
    "patchharbor.workflow_rules": [
        "WorkflowRulesError",
        "WorkflowRule",
        "WorkflowRuleSet",
        "load_rules_from_text",
        "rules_by_category",
    ],
    "patchharbor.workflow_validation": [
        "WorkflowRuleIssue",
        "WorkflowRulesValidationResult",
        "validate_workflow_rules_text",
        "validate_workflow_rules_mapping",
        "validate_workflow_rules_file",
        "summarize_validation_result",
        "issues_with_severity",
    ],
    "patchharbor.compat_config": [
        "CompatibilityConfigError",
        "AliasSpec",
        "WrapperSpec",
        "LifecycleDefaults",
        "CompatibilityConfig",
        "compatibility_config_from_mapping",
        "compatibility_config_from_text",
        "minimal_compatibility_config",
    ],
    "patchharbor.public_audit": [
        "PublicAuditModelError",
        "PublicAuditPattern",
        "PublicAuditTarget",
        "PublicAuditFinding",
        "PublicAuditResult",
        "public_audit_pattern_from_mapping",
        "public_audit_patterns_from_mappings",
        "public_audit_pattern_index",
    ],
    "patchharbor.environment_check": [
        "EnvironmentCheckError",
        "EnvironmentCheck",
        "EnvironmentCheckSpec",
        "EnvironmentCheckResult",
        "environment_check_from_mapping",
        "environment_check_spec_from_mapping",
        "environment_check_result_from_mappings",
    ],
}

PUBLIC_DATACLASSES = {
    ("patchharbor.runner_core", "RunnerExecutionConfig"),
    ("patchharbor.workflow_rules", "WorkflowRule"),
    ("patchharbor.workflow_rules", "WorkflowRuleSet"),
    ("patchharbor.workflow_validation", "WorkflowRuleIssue"),
    ("patchharbor.workflow_validation", "WorkflowRulesValidationResult"),
    ("patchharbor.compat_config", "AliasSpec"),
    ("patchharbor.compat_config", "WrapperSpec"),
    ("patchharbor.compat_config", "LifecycleDefaults"),
    ("patchharbor.compat_config", "CompatibilityConfig"),
    ("patchharbor.public_audit", "PublicAuditPattern"),
    ("patchharbor.public_audit", "PublicAuditTarget"),
    ("patchharbor.public_audit", "PublicAuditFinding"),
    ("patchharbor.public_audit", "PublicAuditResult"),
    ("patchharbor.environment_check", "EnvironmentCheck"),
    ("patchharbor.environment_check", "EnvironmentCheckSpec"),
    ("patchharbor.environment_check", "EnvironmentCheckResult"),
}


class PatchHarborPublicApiInventoryTests(unittest.TestCase):
    def read_public_api(self) -> str:
        return PUBLIC_API.read_text(encoding="utf-8")

    def test_public_api_inventory_doc_exists(self) -> None:
        self.assertTrue(PUBLIC_API.is_file())
        text = self.read_public_api()
        self.assertIn("PATCHHARBOR.15c1 – Public API inventory", text)
        self.assertIn("target-only", text)

    def test_public_api_inventory_lists_cli_commands(self) -> None:
        text = self.read_public_api()
        expected = [
            "patchharbor --help",
            "patchharbor --version",
            "patchharbor doctor --repo",
            "patchharbor lint-script",
            "patchharbor run-script",
            "patchharbor audit-public",
            "patchharbor check-env",
            "docs/cli.md",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_public_api_inventory_lists_python_modules_and_objects(self) -> None:
        text = self.read_public_api()
        for module_name, object_names in PUBLIC_OBJECTS.items():
            with self.subTest(module=module_name):
                self.assertIn(module_name, text)
            for object_name in object_names:
                with self.subTest(module=module_name, object=object_name):
                    self.assertIn(f"`{object_name}`", text)

    def test_inventory_objects_exist_in_current_package(self) -> None:
        for module_name, object_names in PUBLIC_OBJECTS.items():
            module = importlib.import_module(module_name)
            for object_name in object_names:
                with self.subTest(module=module_name, object=object_name):
                    self.assertTrue(hasattr(module, object_name))

    def test_inventory_dataclasses_are_dataclasses(self) -> None:
        for module_name, object_name in PUBLIC_DATACLASSES:
            module = importlib.import_module(module_name)
            obj = getattr(module, object_name)
            with self.subTest(module=module_name, object=object_name):
                self.assertTrue(dataclasses.is_dataclass(obj))

    def test_related_docs_link_to_public_api_inventory(self) -> None:
        for path in [PUBLIC_DOCS_INVENTORY, MIGRATION_ARTIFACT_INVENTORY, CLI_DOC, RUNNER_DOC, COMPAT_DOC]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.15c1 applied", text)
                self.assertIn("docs/public-api-inventory.md", text)

    def test_public_api_inventory_records_stability_next_steps_and_non_goals(self) -> None:
        text = self.read_public_api()
        expected = [
            "Stability rules for PATCHHARBOR.15c2",
            "all listed public modules import successfully",
            "all listed public objects exist",
            "public dataclasses remain dataclasses",
            "PATCHHARBOR.15c2 adds public API stability tests",
            "PATCHHARBOR.15c3 adds final public readiness acceptance",
            "PATCHHARBOR.15c1 does not",
            "change runtime code",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_public_api_inventory_marks_non_public_modules(self) -> None:
        text = self.read_public_api()
        expected = [
            "Non-public implementation modules",
            "patchharbor.console",
            "patchharbor.patch_lint",
            "patchharbor.runner_display",
            "patchharbor.runner_lifecycle",
            "patchharbor.runner_preflight",
            "patchharbor.shell_scan",
        ]
        for item in expected:
            with self.subTest(item=item):
                self.assertIn(item, text)

    def test_public_api_inventory_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                PUBLIC_API,
                PUBLIC_DOCS_INVENTORY,
                MIGRATION_ARTIFACT_INVENTORY,
                CLI_DOC,
                RUNNER_DOC,
                COMPAT_DOC,
                Path(__file__).resolve(),
            ]
        )
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "Example" + "Machine",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
