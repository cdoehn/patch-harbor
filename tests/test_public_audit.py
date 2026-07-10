from __future__ import annotations

from pathlib import Path
import unittest

from patchharbor.public_audit import (
    PublicAuditFinding,
    PublicAuditModelError,
    PublicAuditPattern,
    PublicAuditResult,
    PublicAuditTarget,
    public_audit_pattern_from_mapping,
    public_audit_pattern_index,
    public_audit_patterns_from_mappings,
)


class PatchHarborPublicAuditModelTests(unittest.TestCase):
    def test_pattern_validates_and_serializes_generic_contract(self) -> None:
        pattern = PublicAuditPattern(
            name="private-token",
            value="TOKEN=secret",
            severity="warning",
            description="Sensitive token marker",
        )

        self.assertEqual(pattern.name, "private-token")
        self.assertEqual(pattern.value, "TOKEN=secret")
        self.assertEqual(pattern.severity, "warning")
        self.assertEqual(
            pattern.to_mapping(),
            {
                "name": "private-token",
                "value": "TOKEN=secret",
                "severity": "warning",
                "description": "Sensitive token marker",
            },
        )

    def test_pattern_round_trips_from_mapping_and_defaults_severity(self) -> None:
        pattern = public_audit_pattern_from_mapping({"name": "path", "value": "secret/path"})

        self.assertEqual(pattern, PublicAuditPattern("path", "secret/path"))
        self.assertEqual(pattern.severity, "error")
        self.assertEqual(PublicAuditPattern.from_mapping(pattern.to_mapping()), pattern)

    def test_pattern_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(PublicAuditModelError, "pattern name"):
            PublicAuditPattern("", "x")
        with self.assertRaisesRegex(PublicAuditModelError, "pattern value"):
            PublicAuditPattern("x", "")
        with self.assertRaisesRegex(PublicAuditModelError, "severity must be"):
            PublicAuditPattern("x", "y", severity="critical")
        with self.assertRaisesRegex(PublicAuditModelError, "must be a mapping"):
            PublicAuditPattern.from_mapping("bad")  # type: ignore[arg-type]

    def test_pattern_collection_validates_duplicates_and_accepts_mappings(self) -> None:
        patterns = public_audit_patterns_from_mappings(
            [
                {"name": "one", "value": "first"},
                {"name": "two", "value": "second", "severity": "info"},
            ]
        )

        self.assertEqual(tuple(pattern.name for pattern in patterns), ("one", "two"))
        self.assertEqual(patterns[1].severity, "info")
        self.assertEqual(set(public_audit_pattern_index(patterns)), {"one", "two"})

        with self.assertRaisesRegex(PublicAuditModelError, "duplicate public audit pattern name: one"):
            public_audit_patterns_from_mappings(
                [
                    {"name": "one", "value": "first"},
                    {"name": "one", "value": "again"},
                ]
            )
        with self.assertRaisesRegex(PublicAuditModelError, "iterable of mappings"):
            public_audit_patterns_from_mappings("bad")  # type: ignore[arg-type]
        with self.assertRaisesRegex(PublicAuditModelError, "PublicAuditPattern or mapping"):
            public_audit_pattern_index([object()])  # type: ignore[list-item]

    def test_target_validates_relative_posix_path_and_serializes(self) -> None:
        target = PublicAuditTarget("src/package/module.py", target_type="tracked", label="module")

        self.assertEqual(target.path, "src/package/module.py")
        self.assertEqual(target.target_type, "tracked")
        self.assertEqual(
            target.to_mapping(),
            {"path": "src/package/module.py", "target_type": "tracked", "label": "module"},
        )
        self.assertEqual(PublicAuditTarget.from_mapping(target.to_mapping()), target)

    def test_target_rejects_invalid_paths_and_target_types(self) -> None:
        invalid_paths = ["", ".", "/absolute", "../escape", "nested/../escape", "nested\\windows"]
        for value in invalid_paths:
            with self.subTest(value=value):
                with self.assertRaises(PublicAuditModelError):
                    PublicAuditTarget(value)
        with self.assertRaisesRegex(PublicAuditModelError, "target type"):
            PublicAuditTarget("file.txt", target_type="workspace")

    def test_finding_links_target_pattern_line_column_and_text(self) -> None:
        target = PublicAuditTarget("README.md")
        pattern = PublicAuditPattern("mail", "example at domain", severity="error")
        finding = PublicAuditFinding(target=target, pattern=pattern, line=12, column=4, text="contact example at domain")

        self.assertEqual(finding.path, "README.md")
        self.assertEqual(finding.severity, "error")
        self.assertEqual(finding.line, 12)
        self.assertEqual(finding.column, 4)
        self.assertEqual(PublicAuditFinding.from_mapping(finding.to_mapping()), finding)

    def test_finding_rejects_invalid_nested_values(self) -> None:
        target = PublicAuditTarget("file.txt")
        pattern = PublicAuditPattern("token", "TOKEN")
        with self.assertRaisesRegex(PublicAuditModelError, "line must be a positive integer"):
            PublicAuditFinding(target, pattern, line=0, text="x")
        with self.assertRaisesRegex(PublicAuditModelError, "column must be a positive integer"):
            PublicAuditFinding(target, pattern, line=1, column=0, text="x")
        with self.assertRaisesRegex(PublicAuditModelError, "finding text"):
            PublicAuditFinding(target, pattern, line=1, text="")
        with self.assertRaisesRegex(PublicAuditModelError, "finding must be a mapping"):
            PublicAuditFinding.from_mapping("bad")  # type: ignore[arg-type]

    def test_result_reports_ok_failed_counts_and_severity_groups(self) -> None:
        warning = PublicAuditFinding(
            PublicAuditTarget("docs/readme.md"),
            PublicAuditPattern("warn", "maybe", severity="warning"),
            line=1,
            text="maybe",
        )
        error = PublicAuditFinding(
            PublicAuditTarget("src/main.py"),
            PublicAuditPattern("secret", "secret", severity="error"),
            line=2,
            text="secret",
        )
        result = PublicAuditResult((warning, error), scanned_targets=3, skipped_targets=1, metadata={"mode": "tracked"})

        self.assertFalse(result.ok)
        self.assertTrue(result.failed)
        self.assertEqual(result.finding_count, 2)
        self.assertEqual(result.findings_by_severity("warning"), (warning,))
        self.assertEqual(result.findings_by_severity("error"), (error,))
        self.assertEqual(result.to_mapping()["scanned_targets"], 3)
        self.assertEqual(result.to_mapping()["metadata"], {"mode": "tracked"})

        clean = PublicAuditResult((warning,), scanned_targets=1)
        self.assertTrue(clean.ok)
        self.assertFalse(clean.failed)

    def test_result_accepts_finding_mappings_and_validates_counters(self) -> None:
        finding_mapping = {
            "target": {"path": "file.txt"},
            "pattern": {"name": "secret", "value": "secret"},
            "line": 1,
            "text": "secret text",
        }
        result = PublicAuditResult((finding_mapping,), scanned_targets=1)  # type: ignore[arg-type]

        self.assertEqual(result.finding_count, 1)
        self.assertEqual(result.findings[0].pattern.name, "secret")

        with self.assertRaisesRegex(PublicAuditModelError, "scanned_targets"):
            PublicAuditResult(scanned_targets=-1)
        with self.assertRaisesRegex(PublicAuditModelError, "skipped_targets"):
            PublicAuditResult(skipped_targets=-1)
        with self.assertRaisesRegex(PublicAuditModelError, "metadata value"):
            PublicAuditResult(metadata={"mode": 1})  # type: ignore[dict-item]
        with self.assertRaisesRegex(PublicAuditModelError, "severity must"):
            result.findings_by_severity("critical")

    def test_public_audit_model_does_not_store_source_specific_defaults(self) -> None:
        import patchharbor.public_audit as public_audit

        module_source = Path(public_audit.__file__).read_text(encoding="utf-8")
        forbidden = [
            "RepoDossier",
            "repodossier",
            "audit_public_repo.py",
            "FORBIDDEN_PATTERNS",
            "market_" + "research",
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, module_source)


if __name__ == "__main__":
    unittest.main()
