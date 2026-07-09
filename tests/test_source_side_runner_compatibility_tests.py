from __future__ import annotations

from pathlib import Path
import unittest

from patchharbor.compat_config import AliasSpec, CompatibilityConfig, WrapperSpec
from patchharbor.compat_planning import plan_compatibility
from patchharbor.compat_rendering import render_alias_line, render_wrapper_script


class PatchHarborSourceSideRunnerCompatibilityTestsPlanTests(unittest.TestCase):
    def test_runner_compatibility_tests_plan_document_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-side-runner-compatibility-tests.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.08d source-side runner compatibility tests plan", text)
        self.assertIn("This step is a test plan only", text)

    def test_plan_lists_required_future_source_side_tests(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-compatibility-tests.md").read_text(encoding="utf-8")
        required = [
            "existing runner preservation",
            "additive wrapper file",
            "wrapper syntax",
            "wrapper delegation",
            "argument forwarding",
            "no alias side effect",
            "no lifecycle mutation",
            "export isolation",
            "private-value guard",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_plan_records_future_source_side_commands(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-compatibility-tests.md").read_text(encoding="utf-8")
        required = [
            "test -f scripts/dev/run_latest_download_patch.sh",
            "test -f scripts/dev/run_patchharbor_patch.sh",
            "bash -n scripts/dev/run_patchharbor_patch.sh",
            'grep -q "patchharbor run-script" scripts/dev/run_patchharbor_patch.sh',
            "grep -q '\"$@\"' scripts/dev/run_patchharbor_patch.sh",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_plan_keeps_wrapper_thin_and_explicit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-compatibility-tests.md").read_text(encoding="utf-8")
        required = [
            'exec patchharbor run-script "$@"',
            "It should not perform download discovery",
            "done or failed movement",
            "alias installation",
            "export execution",
            "shell configuration edits",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_plan_keeps_current_step_non_mutating(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-side-runner-compatibility-tests.md").read_text(encoding="utf-8")
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

    def test_target_side_apis_can_model_and_render_future_test_subject(self) -> None:
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
        self.assertIn('exec patchharbor run-script "$@"', rendered.content)
        self.assertEqual(render_alias_line(alias), "alias patchharbor-patch=scripts/dev/run_patchharbor_patch.sh")
        self.assertEqual([action.action for action in plan.actions], ["ensure_lifecycle", "create_wrapper", "create_alias"])

    def test_target_side_proof_does_not_write_future_source_wrapper(self) -> None:
        root = Path(__file__).resolve().parents[1]
        wrapper = WrapperSpec(
            name="patchharbor-patch-runner",
            kind="runner",
            relative_path="scripts/dev/run_patchharbor_patch.sh",
            command=("patchharbor", "run-script"),
        )
        render_wrapper_script(wrapper)
        self.assertFalse((root / "scripts/dev/run_patchharbor_patch.sh").exists())

    def test_test_plan_files_do_not_store_private_local_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-side-runner-compatibility-tests.md",
            root / "tests/test_source_side_runner_compatibility_tests.py",
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
