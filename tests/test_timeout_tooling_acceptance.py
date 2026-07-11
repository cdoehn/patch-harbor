from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RULES = ROOT / "patch-workflow-rules.json"
PLAN = ROOT / "planning/1.0.0/commit_plan.md"
RULE_ID = "chatbot.timeout-protect-long-running-commands"


class TimeoutToolingAcceptanceTests(unittest.TestCase):
    def test_readme_documents_timeout_tool_and_bounded_escalation(self) -> None:
        text = README.read_text(encoding="utf-8")
        expected = [
            "## Timeout-protected development commands",
            "scripts/run_with_timeout.sh",
            "--timeout DURATION",
            "--kill-after DURATION",
            "--attempts NUMBER",
            "--retry-delay DURATION",
            "larger bounded timeout",
            "Do not increase the timeout indefinitely",
        ]
        for value in expected:
            with self.subTest(value=value):
                self.assertIn(value, text)

    def test_enabled_rule_requires_the_timeout_tool_and_bounded_retries(self) -> None:
        document = json.loads(RULES.read_text(encoding="utf-8"))
        matching = [rule for rule in document["rules"] if rule["id"] == RULE_ID]
        self.assertEqual(len(matching), 1)
        rule = matching[0]
        self.assertTrue(rule["enabled"])
        self.assertEqual(rule["severity"], "error")
        self.assertEqual(rule["category"], "chatbot")
        self.assertEqual(rule["tool"], "scripts/run_with_timeout.sh")
        description = rule["description"]
        for value in [
            "estimate a task-appropriate maximum runtime",
            "larger bounded timeout",
            "Never retry ordinary failures",
            "increase timeouts indefinitely",
            "timestamped log file in the user's Downloads directory",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, description)

    def test_commit_plan_records_the_authorized_commit(self) -> None:
        text = PLAN.read_text(encoding="utf-8")
        self.assertIn("## Commit 2: Entwicklungsbefehle gegen Hänger absichern", text)
        self.assertIn("feat(tooling): add timeout guard for development commands", text)


if __name__ == "__main__":
    unittest.main()
