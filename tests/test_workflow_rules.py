from __future__ import annotations

import unittest

from patchharbor.workflow_rules import (
    DEFAULT_RULESET_VERSION,
    VALID_SEVERITIES,
    WorkflowRule,
    WorkflowRulesError,
    WorkflowRuleSet,
    load_rules_from_text,
    rules_by_category,
)


class PatchHarborWorkflowRulesModelTests(unittest.TestCase):
    def test_rule_defaults_are_generic_and_enabled(self) -> None:
        rule = WorkflowRule(id="generic.rule", description="A generic rule")
        self.assertEqual(rule.category, "general")
        self.assertEqual(rule.severity, "error")
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.data, {})

    def test_rule_from_mapping_preserves_extra_data(self) -> None:
        rule = WorkflowRule.from_mapping(
            {
                "id": "patch.no_pager",
                "description": "Avoid commands that can hang in a pager",
                "category": "git",
                "severity": "warning",
                "enabled": True,
                "command": "git diff",
            }
        )
        self.assertEqual(rule.id, "patch.no_pager")
        self.assertEqual(rule.category, "git")
        self.assertEqual(rule.severity, "warning")
        self.assertEqual(rule.data["command"], "git diff")

    def test_rule_to_mapping_round_trips_known_and_extra_fields(self) -> None:
        rule = WorkflowRule(
            id="patch.tests",
            description="Run focused tests",
            category="tests",
            severity="info",
            enabled=False,
            data={"requires": ["compileall", "unittest"]},
        )
        mapping = rule.to_mapping()
        self.assertEqual(mapping["id"], "patch.tests")
        self.assertEqual(mapping["requires"], ["compileall", "unittest"])
        self.assertFalse(mapping["enabled"])

    def test_rule_rejects_empty_required_strings(self) -> None:
        for kwargs in (
            {"id": "", "description": "desc"},
            {"id": "rule", "description": ""},
            {"id": "rule", "description": "desc", "category": ""},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(WorkflowRulesError):
                    WorkflowRule(**kwargs)

    def test_rule_rejects_unsupported_severity(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRule(id="rule", description="desc", severity="fatal")

    def test_rule_rejects_non_boolean_enabled(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRule(id="rule", description="desc", enabled="yes")  # type: ignore[arg-type]

    def test_rule_from_mapping_requires_mapping(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRule.from_mapping(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_rule_from_mapping_requires_string_fields(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRule.from_mapping({"id": "rule"})

    def test_ruleset_defaults_to_current_version(self) -> None:
        ruleset = WorkflowRuleSet()
        self.assertEqual(ruleset.version, DEFAULT_RULESET_VERSION)
        self.assertEqual(ruleset.rules, ())

    def test_ruleset_from_mapping_loads_rules(self) -> None:
        ruleset = WorkflowRuleSet.from_mapping(
            {
                "version": "1",
                "rules": [
                    {
                        "id": "patch.metadata",
                        "description": "Require patch metadata",
                        "category": "metadata",
                    }
                ],
            },
            source="memory",
        )
        self.assertEqual(ruleset.version, "1")
        self.assertEqual(ruleset.source, "memory")
        self.assertEqual(ruleset.rule_ids(), ("patch.metadata",))
        self.assertEqual(ruleset.enabled_rules()[0].category, "metadata")

    def test_ruleset_rejects_duplicate_ids(self) -> None:
        rule_a = WorkflowRule(id="duplicate", description="first")
        rule_b = WorkflowRule(id="duplicate", description="second")
        with self.assertRaises(WorkflowRulesError):
            WorkflowRuleSet(rules=(rule_a, rule_b))

    def test_ruleset_rejects_non_rule_items(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRuleSet(rules=("not-a-rule",))  # type: ignore[arg-type]

    def test_ruleset_rejects_invalid_source(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRuleSet(source="")

    def test_ruleset_helpers_return_enabled_rules_ids_and_lookup(self) -> None:
        enabled = WorkflowRule(id="enabled.rule", description="enabled")
        disabled = WorkflowRule(id="disabled.rule", description="disabled", enabled=False)
        ruleset = WorkflowRuleSet(rules=(enabled, disabled))
        self.assertEqual(ruleset.enabled_rules(), (enabled,))
        self.assertEqual(ruleset.rule_ids(), ("enabled.rule", "disabled.rule"))
        self.assertIs(ruleset.by_id()["enabled.rule"], enabled)

    def test_ruleset_to_mapping_is_plain_data(self) -> None:
        ruleset = WorkflowRuleSet(
            version="1",
            rules=(WorkflowRule(id="rule", description="desc", data={"pattern": "*.sh"}),),
        )
        mapping = ruleset.to_mapping()
        self.assertEqual(mapping["version"], "1")
        self.assertEqual(mapping["rules"][0]["pattern"], "*.sh")

    def test_load_rules_from_text_accepts_json_object(self) -> None:
        text = (
            '{"version":"1","rules":['
            '{"id":"patch.shell","description":"Shell scripts stay safe","category":"shell","severity":"warning"}'
            ']}'
        )
        ruleset = load_rules_from_text(text, source="memory")
        self.assertEqual(ruleset.source, "memory")
        self.assertEqual(ruleset.rule_ids(), ("patch.shell",))

    def test_load_rules_from_text_rejects_invalid_json(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            load_rules_from_text('{"version":')

    def test_load_rules_from_text_rejects_non_object_json(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            load_rules_from_text("[]")

    def test_ruleset_from_mapping_rejects_non_list_rules(self) -> None:
        with self.assertRaises(WorkflowRulesError):
            WorkflowRuleSet.from_mapping({"version": "1", "rules": {}})

    def test_rules_by_category_groups_rules(self) -> None:
        first = WorkflowRule(id="a", description="A", category="metadata")
        second = WorkflowRule(id="b", description="B", category="metadata")
        third = WorkflowRule(id="c", description="C", category="shell")
        grouped = rules_by_category((first, second, third))
        self.assertEqual(grouped["metadata"], (first, second))
        self.assertEqual(grouped["shell"], (third,))

    def test_valid_severities_are_stable(self) -> None:
        self.assertEqual(VALID_SEVERITIES, frozenset({"error", "warning", "info"}))

    def test_test_file_does_not_store_local_private_values(self) -> None:
        text = __import__("pathlib").Path(__file__).read_text(encoding="utf-8")
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
