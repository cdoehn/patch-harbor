from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from patchharbor.compat_config import AliasSpec, CompatibilityConfig, LifecycleDefaults, WrapperSpec
from patchharbor.compat_planning import plan_compatibility
from patchharbor.compat_rendering import render_alias_line, render_compatibility_preview, render_wrapper_script, render_wrappers


def sample_config() -> CompatibilityConfig:
    return CompatibilityConfig(
        source_name="example-project",
        wrappers=(
            WrapperSpec("patch-runner", "runner", "scripts/dev/run_patch.sh", ("patchharbor", "run-script")),
            WrapperSpec("export-runner", "export", "scripts/dev/export.sh", ("patchharbor", "export"), enabled=False),
        ),
        aliases=(AliasSpec("run-patch", ("scripts/dev/run_patch.sh",)),),
        lifecycle=LifecycleDefaults(downloads_dirname="downloads", done_dirname="done", failed_dirname="failed"),
    )


class PatchHarborSourceWrapperCompatibilityAcceptanceTests(unittest.TestCase):
    def test_acceptance_document_exists_and_defines_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "docs/source-wrapper-compatibility-acceptance.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("PatchHarbor.07 source-wrapper compatibility acceptance", text)
        self.assertIn("Accepted scope", text)
        self.assertIn("Explicit non-goals", text)
        self.assertIn("Compatibility boundary", text)

    def test_phase_components_are_present(self) -> None:
        root = Path(__file__).resolve().parents[1]
        required = [
            "docs/source-wrapper-compatibility-migration.md",
            "docs/source-wrapper-compatibility-acceptance.md",
            "src/patchharbor/compat_config.py",
            "src/patchharbor/compat_planning.py",
            "src/patchharbor/compat_rendering.py",
            "tests/test_compat_config.py",
            "tests/test_compat_planning.py",
            "tests/test_compat_rendering.py",
            "tests/test_source_wrapper_compatibility_acceptance.py",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((root / relative).exists(), relative)

    def test_acceptance_document_records_non_goals(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs/source-wrapper-compatibility-acceptance.md").read_text(encoding="utf-8")
        required = [
            "source-repository wrapper file writes",
            "automatic wrapper adoption",
            "alias installation",
            "shell rc-file edits",
            "download-folder mutation",
            "export runner migration",
            "source-repository commits",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_config_planning_and_rendering_work_together(self) -> None:
        config = sample_config()
        plan = plan_compatibility(config, existing_wrapper_paths=(), existing_aliases=())
        rendered = render_wrappers(config)
        alias = config.alias_by_name("run-patch")
        assert alias is not None

        self.assertEqual([action.action for action in plan.actions], ["ensure_lifecycle", "create_wrapper", "skip_wrapper", "create_alias"])
        self.assertEqual([wrapper.relative_path for wrapper in rendered], ["scripts/dev/run_patch.sh"])
        self.assertIn('exec patchharbor run-script "$@"', rendered[0].content)
        self.assertEqual(render_alias_line(alias), "alias run-patch=scripts/dev/run_patch.sh")

        preview = render_compatibility_preview(config, plan)
        self.assertIn("compatibility preview for example-project", preview)
        self.assertIn("planned actions: 4", preview)

    def test_planning_and_rendering_do_not_write_files_or_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = sample_config()
            plan = plan_compatibility(config)
            rendered = render_wrappers(config)

            self.assertTrue(plan.has_actions)
            self.assertTrue(rendered)
            self.assertFalse((root / "scripts").exists())
            self.assertFalse((root / "downloads").exists())
            self.assertFalse((root / "done").exists())
            self.assertFalse((root / "failed").exists())

    def test_disabled_wrappers_are_planned_but_not_rendered_by_default(self) -> None:
        config = sample_config()
        plan = plan_compatibility(config)
        rendered_default = render_wrappers(config)
        rendered_all = render_wrappers(config, include_disabled=True)

        self.assertIn("skip_wrapper", [action.action for action in plan.actions])
        self.assertEqual([wrapper.relative_path for wrapper in rendered_default], ["scripts/dev/run_patch.sh"])
        self.assertEqual({wrapper.relative_path for wrapper in rendered_all}, {"scripts/dev/run_patch.sh", "scripts/dev/export.sh"})

    def test_acceptance_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "docs/source-wrapper-compatibility-acceptance.md",
            root / "tests/test_source_wrapper_compatibility_acceptance.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
            "run_latest_" + "download_patch",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
