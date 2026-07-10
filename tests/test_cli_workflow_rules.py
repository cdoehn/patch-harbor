from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run_patchharbor(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "patchharbor", *args],
        cwd=ROOT if cwd is None else cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PatchHarborWorkflowRulesCliTests(unittest.TestCase):
    def test_add_creates_rules_file_with_existing_model_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "config" / "rules.json"
            result = run_patchharbor(
                "rules",
                "add",
                "--file",
                str(rules_file),
                "--id",
                "milestone.finish-current",
                "--description",
                "Finish the current milestone before starting another one.",
                "--category",
                "workflow",
                "--severity",
                "warning",
                "--disabled",
            )
            document = json.loads(rules_file.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            document,
            {
                "version": "1",
                "rules": [
                    {
                        "id": "milestone.finish-current",
                        "description": "Finish the current milestone before starting another one.",
                        "category": "workflow",
                        "severity": "warning",
                        "enabled": False,
                    }
                ],
            },
        )

    def test_add_uses_existing_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            result = run_patchharbor(
                "rules",
                "add",
                "--file",
                str(rules_file),
                "--id",
                "rule.one",
                "--description",
                "One rule",
            )
            rule = json.loads(rules_file.read_text(encoding="utf-8"))["rules"][0]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rule["category"], "general")
        self.assertEqual(rule["severity"], "error")
        self.assertIs(rule["enabled"], True)


    def test_add_preserves_existing_version_and_extension_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            rules_file.write_text(
                json.dumps(
                    {
                        "version": "5",
                        "rules": [
                            {
                                "id": "existing",
                                "description": "Existing rule",
                                "pattern": "*.py",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = run_patchharbor(
                "rules",
                "add",
                "--file",
                str(rules_file),
                "--id",
                "new.rule",
                "--description",
                "New rule",
            )
            document = json.loads(rules_file.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(document["version"], "5")
        self.assertEqual(document["rules"][0]["pattern"], "*.py")
        self.assertEqual([rule["id"] for rule in document["rules"]], ["existing", "new.rule"])

    def test_add_rejects_duplicate_id_without_changing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            original = {
                "version": "2",
                "rules": [{"id": "same", "description": "Original", "custom": {"keep": True}}],
            }
            rules_file.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
            before = rules_file.read_bytes()

            result = run_patchharbor(
                "rules",
                "add",
                "--file",
                str(rules_file),
                "--id",
                "same",
                "--description",
                "Replacement",
            )

            after = rules_file.read_bytes()

        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(before, after)

    def test_delete_removes_only_matching_rule_and_preserves_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            rules_file.write_text(
                json.dumps(
                    {
                        "version": "7",
                        "rules": [
                            {"id": "remove", "description": "Remove me"},
                            {
                                "id": "keep",
                                "description": "Keep me",
                                "category": "custom",
                                "severity": "info",
                                "enabled": False,
                                "pattern": "*.sh",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = run_patchharbor("rules", "delete", "--file", str(rules_file), "remove")
            document = json.loads(rules_file.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(document["version"], "7")
        self.assertEqual([rule["id"] for rule in document["rules"]], ["keep"])
        self.assertEqual(document["rules"][0]["pattern"], "*.sh")

    def test_delete_unknown_id_does_not_change_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            rules_file.write_text('{"version":"1","rules":[]}\n', encoding="utf-8")
            before = rules_file.read_bytes()
            result = run_patchharbor("rules", "delete", "--file", str(rules_file), "missing")
            after = rules_file.read_bytes()

        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)
        self.assertEqual(before, after)

    def test_list_shows_core_existing_fields_for_each_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            rules_file.write_text(
                json.dumps(
                    {
                        "version": "1",
                        "rules": [
                            {
                                "id": "rule.one",
                                "description": "First rule",
                                "category": "workflow",
                                "severity": "error",
                                "enabled": True,
                            },
                            {
                                "id": "rule.two",
                                "description": "Second rule",
                                "category": "tests",
                                "severity": "warning",
                                "enabled": False,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = run_patchharbor("rules", "list", "--file", str(rules_file))

        self.assertEqual(result.returncode, 0, result.stderr)
        for marker in ["ID", "SEVERITY", "ENABLED", "CATEGORY", "DESCRIPTION", "rule.one", "rule.two"]:
            self.assertIn(marker, result.stdout)
        self.assertIn("warning", result.stdout)
        self.assertIn("no", result.stdout)

    def test_dump_outputs_only_the_complete_json_document(self) -> None:
        document = {
            "version": "3",
            "rules": [
                {
                    "id": "rule.one",
                    "description": "First rule",
                    "category": "workflow",
                    "severity": "info",
                    "enabled": True,
                    "custom": "preserved",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            rules_file.write_text(json.dumps(document), encoding="utf-8")
            result = run_patchharbor("rules", "dump", "--file", str(rules_file))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), document)
        self.assertFalse(result.stderr)

    def test_missing_file_lists_empty_and_dumps_empty_document_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "missing.json"
            listed = run_patchharbor("rules", "list", "--file", str(rules_file))
            dumped = run_patchharbor("rules", "dump", "--file", str(rules_file))
            exists = rules_file.exists()

        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("No workflow rules configured", listed.stdout)
        self.assertEqual(json.loads(dumped.stdout), {"version": "1", "rules": []})
        self.assertFalse(exists)

    def test_invalid_json_is_reported_and_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules_file = Path(tmp) / "rules.json"
            rules_file.write_text('{"version":', encoding="utf-8")
            before = rules_file.read_bytes()
            result = run_patchharbor(
                "rules",
                "add",
                "--file",
                str(rules_file),
                "--id",
                "rule.one",
                "--description",
                "One rule",
            )
            after = rules_file.read_bytes()

        self.assertEqual(result.returncode, 2)
        self.assertIn("JSON is invalid", result.stderr)
        self.assertEqual(before, after)

    def test_default_file_name_is_usable_from_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            result = run_patchharbor(
                "rules",
                "add",
                "--id",
                "default.path",
                "--description",
                "Use the default path",
                cwd=cwd,
            )
            rules_file = cwd / "patch-workflow-rules.json"
            document = json.loads(rules_file.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(document["rules"][0]["id"], "default.path")


if __name__ == "__main__":
    unittest.main()
