from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class PatchHarborExtractionAcceptanceTests(unittest.TestCase):
    def test_extraction_document_defines_scope_and_non_goals(self) -> None:
        text = (ROOT / "docs/extraction-03.md").read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.03 extraction baseline", text)
        self.assertIn("Accepted scope", text)
        self.assertIn("Explicit non-goals", text)
        self.assertIn("not a complete runner migration", text)
        self.assertIn("RepoDossier remains unchanged", text)

    def test_console_and_metadata_modules_are_present(self) -> None:
        expected = [
            ROOT / "src/patchharbor/console.py",
            ROOT / "src/patchharbor/metadata.py",
            ROOT / "tests/test_console.py",
            ROOT / "tests/test_metadata.py",
        ]
        for path in expected:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())

    def test_metadata_foundation_accepts_new_and_legacy_markers(self) -> None:
        from patchharbor.metadata import DEFAULT_MARKER, LEGACY_MARKER, validate_patch_text

        template = (
            "\n"
            "# {marker}: {{\"type\":\"patch\",\"id\":\"EXAMPLE.03\",\"title\":\"Example\",\"commit\":\"Add example\"}}\n"
            "# {marker}: {{\"type\":\"progress\",\"panel\":\"roadmap\",\"status\":\"active\",\"file\":\"docs/example.md\",\"label\":\"Roadmap\"}}\n"
            "# {marker}: {{\"type\":\"progress\",\"panel\":\"milestone\",\"status\":\"active\",\"file\":\"docs/example.md\",\"label\":\"Milestone\"}}\n"
            "# {marker}: {{\"type\":\"display\",\"context\":2,\"layout\":\"side-by-side\",\"frame\":false}}\n"
        )
        for marker in (DEFAULT_MARKER, LEGACY_MARKER):
            with self.subTest(marker=marker):
                self.assertTrue(validate_patch_text(template.format(marker=marker)).ok)

    def test_console_footer_foundation_is_deterministic_without_color(self) -> None:
        from patchharbor.console import FooterItem, render_footer

        footer = render_footer([FooterItem("Done", "accepted", "green")], width=30, color=False)
        self.assertIn("Done: accepted", footer)
        self.assertNotIn("\\033[", footer)
        self.assertTrue(footer.startswith("=" * 30))

    def test_target_cli_doctor_still_accepts_repository_root(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-m", "patchharbor", "doctor", "--repo", str(ROOT)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: ok", result.stdout)

    def test_acceptance_files_do_not_store_local_private_values(self) -> None:
        checked = [
            ROOT / "docs/extraction-03.md",
            ROOT / "tests/test_extraction_acceptance.py",
        ]
        text = "\\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
