from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from patchharbor.public_audit import PublicAuditModelError, PublicAuditPattern, PublicAuditTarget
from patchharbor.public_audit_checks import (
    PublicAuditCheckError,
    is_probably_binary,
    scan_public_audit_bytes,
    scan_public_audit_file,
    scan_public_audit_targets,
    scan_public_audit_text,
)


class PatchHarborPublicAuditChecksTests(unittest.TestCase):
    def patterns(self) -> tuple[PublicAuditPattern, PublicAuditPattern]:
        return (
            PublicAuditPattern("secret", "SECRET_TOKEN", severity="error"),
            PublicAuditPattern("mail", "contact@example.test", severity="warning"),
        )

    def test_scan_text_reports_findings_with_line_column_and_severity(self) -> None:
        text = "safe\nvalue SECRET_TOKEN here\nemail contact@example.test\n"
        result = scan_public_audit_text("docs/readme.md", text, self.patterns())

        self.assertFalse(result.ok)
        self.assertEqual(result.finding_count, 2)
        self.assertEqual(result.scanned_targets, 1)
        self.assertEqual(result.skipped_targets, 0)
        self.assertEqual(result.metadata, {"mode": "text"})
        self.assertEqual(result.findings[0].path, "docs/readme.md")
        self.assertEqual(result.findings[0].line, 2)
        self.assertEqual(result.findings[0].column, 7)
        self.assertEqual(result.findings[0].severity, "error")
        self.assertEqual(result.findings[1].severity, "warning")
        self.assertEqual(result.findings_by_severity("warning"), (result.findings[1],))

    def test_scan_text_accepts_pattern_mappings_and_detects_duplicates(self) -> None:
        result = scan_public_audit_text(
            "file.txt",
            "alpha beta",
            [
                {"name": "alpha", "value": "alpha"},
                {"name": "beta", "value": "beta", "severity": "info"},
            ],
        )

        self.assertEqual(result.finding_count, 2)
        self.assertEqual(result.findings[1].severity, "info")

        with self.assertRaisesRegex(PublicAuditModelError, "duplicate public audit pattern name"):
            scan_public_audit_text(
                "file.txt",
                "alpha",
                [
                    {"name": "same", "value": "alpha"},
                    {"name": "same", "value": "beta"},
                ],
            )

    def test_binary_detection_validates_input_and_detects_nul_in_sample(self) -> None:
        self.assertFalse(is_probably_binary(b"plain text"))
        self.assertTrue(is_probably_binary(b"abc\0def"))
        self.assertFalse(is_probably_binary(b"abc\0def", sample_size=3))

        with self.assertRaisesRegex(PublicAuditCheckError, "requires bytes"):
            is_probably_binary("plain")  # type: ignore[arg-type]
        with self.assertRaisesRegex(PublicAuditCheckError, "sample_size"):
            is_probably_binary(b"plain", sample_size=0)

    def test_scan_bytes_skips_binary_and_decodes_text_with_replacement(self) -> None:
        binary = scan_public_audit_bytes("binary.bin", b"abc\0SECRET_TOKEN", self.patterns())
        self.assertTrue(binary.ok)
        self.assertEqual(binary.scanned_targets, 0)
        self.assertEqual(binary.skipped_targets, 1)
        self.assertEqual(binary.metadata, {"mode": "bytes", "skip_reason": "binary"})

        text = scan_public_audit_bytes("text.txt", b"SECRET_TOKEN \xff", self.patterns())
        self.assertFalse(text.ok)
        self.assertEqual(text.scanned_targets, 1)
        self.assertEqual(text.metadata, {"mode": "bytes"})

    def test_scan_file_scans_text_and_skips_missing_or_binary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "docs").mkdir()
            (base / "docs/readme.md").write_text("SECRET_TOKEN\n", encoding="utf-8")
            (base / "binary.bin").write_bytes(b"\0SECRET_TOKEN")

            found = scan_public_audit_file(base, PublicAuditTarget("docs/readme.md"), self.patterns())
            missing = scan_public_audit_file(base, PublicAuditTarget("missing.txt"), self.patterns())
            binary = scan_public_audit_file(base, PublicAuditTarget("binary.bin"), self.patterns())

            self.assertEqual(found.finding_count, 1)
            self.assertEqual(found.scanned_targets, 1)
            self.assertEqual(found.metadata, {"mode": "file"})
            self.assertEqual(missing.scanned_targets, 0)
            self.assertEqual(missing.skipped_targets, 1)
            self.assertEqual(missing.metadata, {"mode": "file", "skip_reason": "missing"})
            self.assertEqual(binary.scanned_targets, 0)
            self.assertEqual(binary.skipped_targets, 1)
            self.assertEqual(binary.metadata, {"mode": "file", "skip_reason": "binary"})

    def test_scan_targets_aggregates_scanned_skipped_and_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "src").mkdir()
            (base / "src/one.py").write_text("safe\nSECRET_TOKEN\n", encoding="utf-8")
            (base / "src/two.py").write_text("contact@example.test\n", encoding="utf-8")

            result = scan_public_audit_targets(
                base,
                [
                    {"path": "src/one.py", "target_type": "tracked"},
                    {"path": "src/two.py", "label": "second"},
                    {"path": "src/missing.py"},
                ],
                self.patterns(),
            )

            self.assertEqual(result.finding_count, 2)
            self.assertEqual(result.scanned_targets, 2)
            self.assertEqual(result.skipped_targets, 1)
            self.assertEqual(result.metadata, {"mode": "targets"})
            self.assertFalse(result.ok)

    def test_scan_helpers_validate_target_base_and_encoding_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PublicAuditCheckError, "base path"):
                scan_public_audit_file(object(), PublicAuditTarget("file.txt"), self.patterns())  # type: ignore[arg-type]
            with self.assertRaisesRegex(PublicAuditCheckError, "target must"):
                scan_public_audit_file(tmp, object(), self.patterns())  # type: ignore[arg-type]
            with self.assertRaisesRegex(PublicAuditCheckError, "targets must be an iterable"):
                scan_public_audit_targets(tmp, "file.txt", self.patterns())  # type: ignore[arg-type]
            with self.assertRaisesRegex(PublicAuditCheckError, "encoding"):
                scan_public_audit_bytes("file.txt", b"text", self.patterns(), encoding="")

    def test_public_audit_checks_do_not_store_source_specific_defaults(self) -> None:
        import patchharbor.public_audit_checks as public_audit_checks

        module_source = Path(public_audit_checks.__file__).read_text(encoding="utf-8")
        forbidden = [
            "Repo" + "Dossier",
            "repodossier",
            "audit_public_" + "repo.py",
            "FORBIDDEN_" + "PATTERNS",
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
