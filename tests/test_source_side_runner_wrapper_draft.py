from __future__ import annotations

from pathlib import Path
import unittest

from patchharbor.compat_config import AliasSpec, CompatibilityConfig, WrapperSpec
from patchharbor.compat_planning import plan_compatibility
from patchharbor.compat_rendering import render_alias_line, render_wrapper_script


class PatchHarborSourceSideRunnerWrapperDraftTests(unittest.TestCase):
    def test_runner_wrapper_draft_document_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-side-runner-wrapper-draft.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.08b source-side runner wrapper draft", text)
        self.assertIn("This step is a draft only", text)

    def test_draft_names_additive_wrapper_and_preserves_current_runner(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-wrapper-draft.md").read_text(encoding="utf-8")
        required = [
            "scripts/dev/run_patchharbor_patch.sh",
            "scripts/dev/run_latest_download_patch.sh",
            "preserve initially",
            "can be added without deleting the current runner",
            "replace only after parity checks",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_draft_command_shape_uses_explicit_patchharbor_runner(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-wrapper-draft.md").read_text(encoding="utf-8")
        required = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'exec patchharbor run-script "$@"',
            "Source-specific download discovery",
            "alias installation are not added",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_draft_records_required_safeguards(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-wrapper-draft.md").read_text(encoding="utf-8")
        required = [
            "the existing local download runner still exists",
            "the new wrapper is additive and reversible",
            "the wrapper calls `patchharbor run-script`",
            "the wrapper passes caller arguments through",
            "the wrapper does not install aliases",
            "the wrapper does not touch export scripts",
            "focused source-side tests run before the full suite",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_draft_keeps_current_step_non_mutating(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-wrapper-draft.md").read_text(encoding="utf-8")
        non_goals = [
            "no RepoDossier file changes",
            "no source repository commits",
            "no wrapper file writes",
            "no alias installation",
            "no shell rc-file changes",
            "no download-folder mutation",
            "no replacement of the current local runner",
            "no export runner migration",
            "no deletion of old source scripts",
        ]
        for phrase in non_goals:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_existing_rendering_apis_can_render_the_draft_wrapper_without_writing_file(self) -> None:
        wrapper = WrapperSpec(
            name="patchharbor-patch-runner",
            kind="runner",
            relative_path="scripts/dev/run_patchharbor_patch.sh",
            command=("patchharbor", "run-script"),
        )
        rendered = render_wrapper_script(wrapper)

        self.assertEqual(rendered.relative_path, "scripts/dev/run_patchharbor_patch.sh")
        self.assertIn('exec patchharbor run-script "$@"', rendered.content)

        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "scripts/dev/run_patchharbor_patch.sh").exists())

    def test_config_planning_can_model_the_later_source_wrapper(self) -> None:
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

        self.assertEqual([action.action for action in plan.actions], ["ensure_lifecycle", "create_wrapper", "create_alias"])
        alias = config.alias_by_name("patchharbor-patch")
        assert alias is not None
        self.assertEqual(render_alias_line(alias), "alias patchharbor-patch=scripts/dev/run_patchharbor_patch.sh")

    def test_draft_files_do_not_store_private_local_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-side-runner-wrapper-draft.md",
            root / "tests/test_source_side_runner_wrapper_draft.py",
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
