from __future__ import annotations

import argparse
import dataclasses
import importlib
import inspect
import subprocess
import sys
import tempfile
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

PUBLIC_COMMANDS = [
    "doctor",
    "lint-script",
    "run-script",
    "audit-public",
    "check-env",
]


class PatchHarborPublicApiStabilityTests(unittest.TestCase):
    def test_public_modules_import_successfully(self) -> None:
        for module_name in PUBLIC_OBJECTS:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertEqual(module.__name__, module_name)

    def test_public_objects_exist_and_are_callable_or_types(self) -> None:
        for module_name, object_names in PUBLIC_OBJECTS.items():
            module = importlib.import_module(module_name)
            for object_name in object_names:
                with self.subTest(module=module_name, object=object_name):
                    obj = getattr(module, object_name)
                    self.assertTrue(callable(obj) or isinstance(obj, type))

    def test_public_dataclasses_remain_dataclasses(self) -> None:
        for module_name, object_name in PUBLIC_DATACLASSES:
            module = importlib.import_module(module_name)
            obj = getattr(module, object_name)
            with self.subTest(module=module_name, object=object_name):
                self.assertTrue(dataclasses.is_dataclass(obj))

    def test_cli_parser_contains_public_subcommands(self) -> None:
        from patchharbor.cli import build_parser

        parser = build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

        help_text = parser.format_help()
        for command in PUBLIC_COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, help_text)

    def test_cli_public_commands_have_help_output(self) -> None:
        for command in PUBLIC_COMMANDS:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "patchharbor", command, "--help"],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(command, result.stdout)

    def test_patch_lint_public_api_is_callable(self) -> None:
        from patchharbor.patch_lint_api import (
            default_patch_lint_rules,
            lint_patch_text,
            patch_lint_rule_names,
            render_patch_lint_result,
        )

        rules = default_patch_lint_rules()
        self.assertTrue(rules)
        names = patch_lint_rule_names()
        self.assertTrue(names)

        script_text = (
            "#!/usr/bin/env bash\n"
            "# repodossier-meta: {\"type\":\"patch\",\"id\":\"PATCHHARBOR.TEST\",\"title\":\"Test\",\"commit\":\"Test\"}\n"
            "# repodossier-meta: {\"type\":\"display\",\"progress_context\":false}\n"
            "print_footer() { echo footer; }\n"
            "trap print_footer EXIT\n"
            "echo ok\n"
        )
        result = lint_patch_text(script_text)
        rendered = render_patch_lint_result(result)
        self.assertTrue(isinstance(rendered, str) or isinstance(rendered, tuple) or isinstance(rendered, list))
        rendered_text = "\n".join(rendered) if isinstance(rendered, (tuple, list)) else rendered
        self.assertIsInstance(rendered_text, str)

    def test_runner_public_config_is_constructible_and_syntax_check_is_callable(self) -> None:
        from patchharbor.runner_core import RunnerExecutionConfig, check_bash_syntax

        config = RunnerExecutionConfig()
        self.assertTrue(dataclasses.is_dataclass(config))

        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "syntax_ok.sh"
            script.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
            outcome = check_bash_syntax(script)
            self.assertIsNotNone(outcome)

    def test_workflow_validation_public_api_is_callable(self) -> None:
        from patchharbor.workflow_validation import (
            summarize_validation_result,
            validate_workflow_rules_mapping,
            validate_workflow_rules_text,
        )

        result = validate_workflow_rules_mapping({"rules": []})
        summary = summarize_validation_result(result)
        self.assertTrue(isinstance(summary, str) or isinstance(summary, tuple) or isinstance(summary, list))
        summary_text = "\n".join(summary) if isinstance(summary, (tuple, list)) else summary
        self.assertIsInstance(summary_text, str)

        text_result = validate_workflow_rules_text('{"rules": []}')
        self.assertIsNotNone(text_result)

    def test_compatibility_public_api_is_callable(self) -> None:
        from patchharbor.compat_config import compatibility_config_from_mapping, minimal_compatibility_config

        minimal = minimal_compatibility_config("repodossier")
        self.assertTrue(dataclasses.is_dataclass(minimal))

        parsed = compatibility_config_from_mapping(
            {
                "source_name": "repodossier",
                "aliases": [],
                "wrappers": [],
                "lifecycle_defaults": {},
            }
        )
        self.assertTrue(dataclasses.is_dataclass(parsed))

    def test_public_api_docs_record_15c2_stability_tests(self) -> None:
        public_api = PUBLIC_API.read_text(encoding="utf-8")
        related = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [PUBLIC_DOCS_INVENTORY, MIGRATION_ARTIFACT_INVENTORY, CLI_DOC, RUNNER_DOC, COMPAT_DOC]
        )

        self.assertIn("PATCHHARBOR.15c2 applied", public_api)
        self.assertIn("tests/test_public_api_stability.py", public_api)
        self.assertIn("PATCHHARBOR.15c2 applied", related)
        self.assertIn("docs/public-api-inventory.md", related)

    def test_public_api_stability_test_does_not_store_private_local_values_or_fences(self) -> None:
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
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
