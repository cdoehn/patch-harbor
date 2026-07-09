from __future__ import annotations

from pathlib import Path
import unittest

from patchharbor.compat_config import AliasSpec, CompatibilityConfig, WrapperSpec
from patchharbor.compat_planning import plan_compatibility
from patchharbor.compat_rendering import render_alias_line, render_compatibility_preview, render_wrapper_script


class PatchHarborSourceSideAdoptionAcceptanceTests(unittest.TestCase):
    def test_acceptance_document_exists_and_defines_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-side-adoption-acceptance.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.08e source-side adoption acceptance", text)
        self.assertIn("Accepted scope", text)
        self.assertIn("Explicit non-goals", text)
        self.assertIn("Readiness for PATCHHARBOR.09", text)

    def test_phase_components_are_present(self) -> None:
        root = Path(__file__).resolve().parents[1]
        required = [
            "docs/source-side-adoption-inventory.md",
            "docs/source-side-runner-wrapper-draft.md",
            "docs/source-side-alias-compatibility-plan.md",
            "docs/source-side-runner-compatibility-tests.md",
            "docs/source-side-adoption-acceptance.md",
            "tests/test_source_side_adoption_inventory.py",
            "tests/test_source_side_runner_wrapper_draft.py",
            "tests/test_source_side_alias_compatibility_plan.py",
            "tests/test_source_side_runner_compatibility_tests.py",
            "tests/test_source_side_adoption_acceptance.py",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((root / relative).exists(), relative)

    def test_acceptance_records_source_context_planning_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-acceptance.md").read_text(encoding="utf-8")
        self.assertIn("planning/roadmap_migration.md", text)
        self.assertIn("planning/milestones_migration.md", text)
        self.assertIn("source repository", text)

    def test_acceptance_records_planned_wrapper_and_command(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-acceptance.md").read_text(encoding="utf-8")
        self.assertIn("scripts/dev/run_patchharbor_patch.sh", text)
        self.assertIn('exec patchharbor run-script "$@"', text)
        self.assertIn("Existing convenience aliases should not be silently changed", text)

    def test_acceptance_records_non_goals(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-acceptance.md").read_text(encoding="utf-8")
        non_goals = [
            "RepoDossier file changes",
            "source repository commits",
            "wrapper file writes",
            "alias installation",
            "shell rc-file changes",
            "download-folder mutation",
            "export runner migration",
            "replacement of the current local runner",
            "deletion of old source scripts",
            "automatic adoption of compatibility commands",
        ]
        for phrase in non_goals:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_acceptance_records_guardrails_for_next_phase(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-adoption-acceptance.md").read_text(encoding="utf-8")
        guardrails = [
            "which repository is modified",
            "which source files are touched",
            "how rollback works",
            "which focused tests cover the change",
            "whether aliases are changed",
            "whether old runners are preserved",
            "whether export scripts are untouched",
            "how private and source-specific values are guarded",
        ]
        for phrase in guardrails:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_existing_compatibility_apis_model_the_next_wrapper_without_writing_it(self) -> None:
        root = Path(__file__).resolve().parents[1]
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
        plan = plan_compatibility(config, existing_wrapper_paths=(), existing_aliases=())
        wrapper = config.wrapper_by_name("patchharbor-patch-runner")
        alias = config.alias_by_name("patchharbor-patch")
        assert wrapper is not None
        assert alias is not None

        rendered = render_wrapper_script(wrapper)
        preview = render_compatibility_preview(config, plan)

        self.assertEqual([action.action for action in plan.actions], ["ensure_lifecycle", "create_wrapper", "create_alias"])
        self.assertIn('exec patchharbor run-script "$@"', rendered.content)
        self.assertEqual(render_alias_line(alias), "alias patchharbor-patch=scripts/dev/run_patchharbor_patch.sh")
        self.assertIn("planned actions: 3", preview)
        self.assertFalse((root / "scripts/dev/run_patchharbor_patch.sh").exists())

    def test_acceptance_files_do_not_store_private_local_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-side-adoption-acceptance.md",
            root / "tests/test_source_side_adoption_acceptance.py",
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
