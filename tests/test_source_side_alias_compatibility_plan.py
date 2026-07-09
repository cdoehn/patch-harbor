from __future__ import annotations

from pathlib import Path
import unittest

from patchharbor.compat_config import AliasSpec, CompatibilityConfig, WrapperSpec
from patchharbor.compat_planning import plan_compatibility
from patchharbor.compat_rendering import render_alias_line, render_compatibility_preview


class PatchHarborSourceSideAliasCompatibilityPlanTests(unittest.TestCase):
    def test_alias_compatibility_plan_document_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-side-alias-compatibility-plan.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.08c source-side alias compatibility plan", text)
        self.assertIn("This step is a plan only", text)

    def test_plan_lists_alias_candidates(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-alias-compatibility-plan.md").read_text(encoding="utf-8")
        required = [
            "`c`",
            "`r`",
            "`patchharbor-patch`",
            "preserve first",
            "defer until export migration is planned",
            "optional additive alias",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_plan_defines_preferred_future_shape(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-alias-compatibility-plan.md").read_text(encoding="utf-8")
        required = [
            "Keep the existing `c` alias behavior unchanged",
            "Add or document an explicit compatibility alias",
            "consider whether `c` should point to the new source wrapper",
            "Never write machine-local paths into tracked files",
            "Never edit shell rc files outside an explicit alias-installation command",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_plan_records_required_safeguards(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-alias-compatibility-plan.md").read_text(encoding="utf-8")
        required = [
            "the existing alias installer still exists",
            "the alias update is additive or explicitly reversible",
            "the old convenience command is not silently broken",
            "shell rc-file edits happen only when the installer is executed by the user",
            "export aliases are not changed",
            "focused source-side tests run before the full suite",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_plan_keeps_current_step_non_mutating(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-alias-compatibility-plan.md").read_text(encoding="utf-8")
        non_goals = [
            "no RepoDossier file changes",
            "no source repository commits",
            "no alias installation",
            "no shell rc-file changes",
            "no wrapper file writes",
            "no replacement of the current convenience alias",
            "no export alias migration",
            "no download-folder mutation",
            "no deletion of old source scripts",
        ]
        for phrase in non_goals:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_existing_rendering_apis_can_model_the_draft_alias_without_installing_it(self) -> None:
        alias = AliasSpec("patchharbor-patch", ("scripts/dev/run_patchharbor_patch.sh",))
        self.assertEqual(render_alias_line(alias), "alias patchharbor-patch=scripts/dev/run_patchharbor_patch.sh")

        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / ".bashrc").exists())
        self.assertFalse((root / ".zshrc").exists())

    def test_config_planning_can_model_later_alias_creation(self) -> None:
        config = CompatibilityConfig(
            source_name="RepoDossier",
            wrappers=(
                WrapperSpec(
                    name="patchharbor-patch-runner",
                    kind="runner",
                    relative_path="scripts/dev/run_patchharbor_patch.sh",
                    command=("patchharbor", "run-script"),
                ),
            ),
            aliases=(AliasSpec("patchharbor-patch", ("scripts/dev/run_patchharbor_patch.sh",)),),
        )
        plan = plan_compatibility(config, existing_wrapper_paths=("scripts/dev/run_patchharbor_patch.sh",), existing_aliases=())

        self.assertEqual([action.action for action in plan.actions], ["ensure_lifecycle", "update_wrapper", "create_alias"])
        self.assertEqual(plan.actions_for_target("patchharbor-patch")[0].action, "create_alias")
        preview = render_compatibility_preview(config, plan)
        self.assertIn("planned actions: 3", preview)

    def test_plan_files_do_not_store_private_local_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-side-alias-compatibility-plan.md",
            root / "tests/test_source_side_alias_compatibility_plan.py",
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
