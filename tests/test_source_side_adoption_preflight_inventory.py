from __future__ import annotations

from pathlib import Path
import unittest


class PatchHarborSourceSideAdoptionPreflightInventoryTests(unittest.TestCase):
    def test_preflight_inventory_document_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-side-adoption-preflight-inventory.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.09a source-side adoption preflight inventory", text)
        self.assertIn("This step is still non-mutating", text)

    def test_inventory_defines_repository_roles(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-preflight-inventory.md").read_text(encoding="utf-8")
        required = [
            "PatchHarbor target repository",
            "RepoDossier source repository",
            "owns generic runner",
            "may receive additive wrapper files",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_lists_required_preflight_checks(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-preflight-inventory.md").read_text(encoding="utf-8")
        required = [
            "source repository path resolves to RepoDossier",
            "target repository path resolves to PatchHarbor",
            "both repositories are Git repositories",
            "both repositories have Git identity configured",
            "existing source download runner still exists",
            "PatchHarbor CLI exposes `run-script`",
            "PatchHarbor target tests are green",
            "RepoDossier source tests are green",
            "migration roadmap and migration milestones are present",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_lists_source_files_to_preserve(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-preflight-inventory.md").read_text(encoding="utf-8")
        required = [
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/install_aliases.sh",
            "scripts/dev/r.sh",
            "scripts/dev/run_repodossier_exports.sh",
            "scripts/dev/repo_patch_helper.py",
            "scripts/dev/show_progress_context.py",
        ]
        for path in required:
            with self.subTest(path=path):
                self.assertIn(path, text)

    def test_inventory_defines_expected_next_wrapper(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-preflight-inventory.md").read_text(encoding="utf-8")
        self.assertIn("scripts/dev/run_patchharbor_patch.sh", text)
        self.assertIn('exec patchharbor run-script "$@"', text)
        self.assertIn("additive and reversible", text)
        self.assertIn("must not change the current local download runner", text)

    def test_inventory_defines_focused_checks_for_next_patch(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-preflight-inventory.md").read_text(encoding="utf-8")
        required = [
            "test -f scripts/dev/run_latest_download_patch.sh",
            "test -f scripts/dev/install_aliases.sh",
            "test -f scripts/dev/run_patchharbor_patch.sh",
            "bash -n scripts/dev/run_patchharbor_patch.sh",
            'grep -q "patchharbor run-script" scripts/dev/run_patchharbor_patch.sh',
            "grep -q '\"$@\"' scripts/dev/run_patchharbor_patch.sh",
        ]
        for command in required:
            with self.subTest(command=command):
                self.assertIn(command, text)

    def test_inventory_defines_source_patch_guardrails(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-preflight-inventory.md").read_text(encoding="utf-8")
        required = [
            "which repository is modified",
            "which source files are touched",
            "whether the patch is additive or replacing behavior",
            "how rollback works",
            "which focused tests prove the change",
            "whether aliases are changed",
            "whether export scripts are untouched",
            "whether the old local runner is preserved",
            "how private and source-specific values are guarded",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_inventory_keeps_current_step_non_mutating(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-preflight-inventory.md").read_text(encoding="utf-8")
        non_goals = [
            "no RepoDossier file changes",
            "no source repository commits",
            "no wrapper file writes",
            "no alias installation",
            "no shell rc-file changes",
            "no download-folder mutation",
            "no export runner migration",
            "no replacement of the current local runner",
            "no deletion of old source scripts",
        ]
        for phrase in non_goals:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_preflight_inventory_files_do_not_store_private_local_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-side-adoption-preflight-inventory.md",
            root / "tests/test_source_side_adoption_preflight_inventory.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
