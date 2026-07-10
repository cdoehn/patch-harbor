from __future__ import annotations

import unittest
from pathlib import Path

from patchharbor.workflow_rule_store import load_workflow_rules_file

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "patch-workflow-rules.json"

EXPECTED_RULE_IDS = (
    "chatbot.engineering-expertise",
    "chatbot.follow-commit-plan",
    "chatbot.one-commit-at-a-time",
    "chatbot.green-n-advances",
    "chatbot.inspect-before-patching",
    "chatbot.linux-bash-python-only",
    "chatbot.embed-next-commit-patch",
    "chatbot.use-patchharbor-loader-helpers",
    "chatbot.provide-download-link",
    "chatbot.validate-before-delivery",
)


class PatchHarborDefaultWorkflowRulesTests(unittest.TestCase):
    def test_default_rules_file_uses_the_current_workflow_rules_model(self) -> None:
        ruleset = load_workflow_rules_file(RULES_FILE)

        self.assertEqual(ruleset.version, "1")
        self.assertEqual(ruleset.rule_ids(), EXPECTED_RULE_IDS)
        self.assertEqual(len(ruleset.enabled_rules()), len(EXPECTED_RULE_IDS))

        for rule in ruleset.rules:
            with self.subTest(rule=rule.id):
                self.assertEqual(rule.category, "chatbot")
                self.assertEqual(rule.severity, "error")
                self.assertTrue(rule.enabled)

    def test_default_rules_cover_the_general_chatbot_workflow_contract(self) -> None:
        ruleset = load_workflow_rules_file(RULES_FILE)
        descriptions = "\n".join(rule.description for rule in ruleset.rules)

        required_markers = (
            "Linux and Windows",
            "Python, Bash, and PowerShell",
            "planning/commit_plan.md",
            "standalone lowercase 'n'",
            "exactly one commit at a time",
            "Do not guess",
            "Do not use PowerShell for Linux-targeted work",
            "executable Bash shell script",
            "loader and reusable helper functions",
            "downloadable .sh file",
            "Bash syntax checks",
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, descriptions)

    def test_default_rules_file_contains_no_local_private_values(self) -> None:
        text = RULES_FILE.read_text(encoding="utf-8")
        forbidden = (
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
