from __future__ import annotations

import unittest
from pathlib import Path

from patchharbor.workflow_rule_store import load_workflow_rules_file

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "patch-workflow-rules.json"

EXPECTED_RULE_IDS = (
    'chatbot.engineering-expertise',
    'chatbot.follow-commit-plan',
    'chatbot.one-commit-at-a-time',
    'chatbot.green-n-advances',
    'chatbot.inspect-before-patching',
    'chatbot.linux-bash-python-only',
    'chatbot.deliver-next-commit-script',
    'chatbot.use-patchharbor-interfaces',
    'chatbot.provide-download-link',
    'chatbot.select-focused-tests',
    'chatbot.use-stable-prerequisites',
    'chatbot.validate-against-current-patchharbor',
    'chatbot.report-verification-honestly',
    'chatbot.follow-patchharbor-contract',
    'patchharbor-contract.context-display-disabled',
    'patchharbor-contract.runner-owned-logging',
    'patchharbor-contract.required-patch-metadata',
    'patchharbor-contract.required-progress-metadata',
    'patchharbor-contract.unique-patch-id',
    'patchharbor-contract.runner-entrypoint',
    'patchharbor-contract.bash-and-lint-validation',
    'patchharbor-contract.noninteractive-git-output',
    'patchharbor-contract.footer-and-status',
    'patchharbor-contract.repository-preflight',
    'patchharbor-contract.repeat-protection',
    'patchharbor-contract.rollback-and-exit-status',
    'patchharbor-contract.no-literal-markdown-fences',
)


class PatchHarborDefaultWorkflowRulesTests(unittest.TestCase):
    def test_default_rules_file_uses_responsibility_categories(self) -> None:
        ruleset = load_workflow_rules_file(RULES_FILE)

        self.assertEqual(ruleset.version, "1")
        self.assertEqual(ruleset.rule_ids(), EXPECTED_RULE_IDS)
        self.assertEqual(len(ruleset.enabled_rules()), len(EXPECTED_RULE_IDS))
        self.assertEqual(len(ruleset.rules), 27)

        categories = {rule.category for rule in ruleset.rules}
        self.assertEqual(categories, {"chatbot", "patchharbor-contract"})
        self.assertEqual(sum(rule.category == "chatbot" for rule in ruleset.rules), 14)
        self.assertEqual(
            sum(rule.category == "patchharbor-contract" for rule in ruleset.rules),
            13,
        )

        for rule in ruleset.rules:
            with self.subTest(rule=rule.id):
                self.assertTrue(rule.id.startswith(rule.category + "."))
                self.assertEqual(rule.severity, "error")
                self.assertTrue(rule.enabled)

    def test_rules_distinguish_chatbot_actions_from_patchharbor_contracts(self) -> None:
        ruleset = load_workflow_rules_file(RULES_FILE)
        descriptions = "\n".join(rule.description for rule in ruleset.rules)

        required_markers = (
            'Linux and Windows',
            'planning/commit_plan.md',
            "standalone lowercase 'n'",
            'exactly one commit at a time',
            'Do not guess',
            'Do not use PowerShell for Linux-targeted work',
            'self-contained executable Bash shell script',
            'current PatchHarbor CLI, loader',
            'downloadable .sh file',
            'focused automated tests',
            'Do not rely exclusively on an original commit hash',
            'current PatchHarbor repository',
            'Do not claim',
            'current PatchHarbor script contract',
            'context set to 0',
            "user's Downloads directory",
            'exactly one valid patchharbor-meta patch record',
            'roadmap and milestone progress metadata',
            'distinct fix ID',
            'patchharbor run-script --lint',
            'strict error handling',
            'git --no-pager',
            'footer and execution-status mechanism',
            'standard repository preflight',
            'repeat protection',
            'rollback and exit-status contract',
            'triple-backtick Markdown fence sequences',
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, descriptions)

        self.assertFalse(any(rule.id.startswith("patch-script.") for rule in ruleset.rules))
        self.assertFalse(any(rule.category == "patchharbor-internal" for rule in ruleset.rules))

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
