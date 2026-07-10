from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from patchharbor.compat_config import AliasSpec, CompatibilityConfig, LifecycleDefaults, WrapperSpec
from patchharbor.compat_planning import (
    CompatibilityPlan,
    CompatibilityPlanAction,
    CompatibilityPlanningError,
    empty_plan,
    plan_alias_actions,
    plan_compatibility,
    plan_lifecycle_actions,
    plan_wrapper_actions,
)


def sample_config() -> CompatibilityConfig:
    return CompatibilityConfig(
        source_name="example-project",
        wrappers=(
            WrapperSpec("patch-runner", "runner", "scripts/dev/run_patch.sh", ("patchharbor", "run-script")),
            WrapperSpec("export-runner", "export", "scripts/dev/export.sh", ("patchharbor", "export"), enabled=False),
        ),
        aliases=(
            AliasSpec("run-patch", ("scripts/dev/run_patch.sh",)),
            AliasSpec("run-export", ("scripts/dev/export.sh",)),
        ),
        lifecycle=LifecycleDefaults(downloads_dirname="downloads", done_dirname="done", failed_dirname="failed"),
    )


class PatchHarborCompatibilityPlanningTests(unittest.TestCase):
    def test_plan_action_validates_and_renders(self) -> None:
        action = CompatibilityPlanAction("create_wrapper", "scripts/dev/run_patch.sh", "wrapper path is missing", payload={"name": "patch-runner"})
        self.assertEqual(action.render(), "create_wrapper: scripts/dev/run_patch.sh - wrapper path is missing")
        self.assertEqual(action.to_mapping()["payload"], {"name": "patch-runner"})
        with self.assertRaises(CompatibilityPlanningError):
            CompatibilityPlanAction("bad", "target", "reason")
        with self.assertRaises(CompatibilityPlanningError):
            CompatibilityPlanAction("create_wrapper", "", "reason")
        with self.assertRaises(CompatibilityPlanningError):
            CompatibilityPlanAction("create_wrapper", "target", "")
        with self.assertRaises(CompatibilityPlanningError):
            CompatibilityPlanAction("create_wrapper", "target", "reason", payload={"": "bad"})

    def test_empty_plan_has_stable_rendering(self) -> None:
        plan = empty_plan("example-project")
        self.assertFalse(plan.has_actions)
        self.assertEqual(plan.render_lines(), ("compatibility plan for example-project: no actions",))
        self.assertEqual(plan.to_mapping(), {"source_name": "example-project", "actions": []})

    def test_plan_lifecycle_actions_only_plans_names_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = sample_config()
            actions = plan_lifecycle_actions(config)

            self.assertEqual(len(actions), 1)
            self.assertEqual(actions[0].action, "ensure_lifecycle")
            self.assertEqual(actions[0].target, "downloads")
            self.assertEqual(actions[0].payload["done_dirname"], "done")
            self.assertFalse((root / "downloads").exists())
            self.assertFalse((root / "done").exists())
            self.assertFalse((root / "failed").exists())

    def test_plan_wrapper_actions_creates_updates_and_skips(self) -> None:
        config = sample_config()
        actions = plan_wrapper_actions(config, existing_wrapper_paths=("scripts/dev/run_patch.sh",))
        self.assertEqual([action.action for action in actions], ["update_wrapper", "skip_wrapper"])
        self.assertEqual(actions[0].target, "scripts/dev/run_patch.sh")
        self.assertEqual(actions[1].target, "scripts/dev/export.sh")

        create_actions = plan_wrapper_actions(config, existing_wrapper_paths=())
        self.assertEqual([action.action for action in create_actions], ["create_wrapper", "skip_wrapper"])

    def test_plan_wrapper_actions_can_hide_disabled_wrappers(self) -> None:
        actions = plan_wrapper_actions(sample_config(), include_disabled=False)
        self.assertEqual([action.action for action in actions], ["create_wrapper"])

    def test_plan_alias_actions_creates_and_updates(self) -> None:
        actions = plan_alias_actions(sample_config(), existing_aliases=("run-patch",))
        self.assertEqual([action.action for action in actions], ["update_alias", "create_alias"])
        self.assertEqual(actions[0].target, "run-patch")
        self.assertEqual(actions[1].target, "run-export")

    def test_plan_compatibility_combines_lifecycle_wrappers_and_aliases(self) -> None:
        plan = plan_compatibility(
            sample_config(),
            existing_wrapper_paths=("scripts/dev/run_patch.sh",),
            existing_aliases=("run-patch",),
        )
        self.assertTrue(plan.has_actions)
        self.assertEqual(plan.source_name, "example-project")
        self.assertEqual(
            [action.action for action in plan.actions],
            ["ensure_lifecycle", "update_wrapper", "skip_wrapper", "update_alias", "create_alias"],
        )
        self.assertEqual(len(plan.actions_by_type("update_wrapper")), 1)
        self.assertEqual(len(plan.actions_for_target("run-patch")), 1)
        self.assertIn("compatibility plan for example-project:", plan.render_lines()[0])

    def test_planning_validates_inputs(self) -> None:
        with self.assertRaises(CompatibilityPlanningError):
            plan_compatibility("bad")  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityPlanningError):
            plan_wrapper_actions(sample_config(), existing_wrapper_paths="scripts/dev/run_patch.sh")  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityPlanningError):
            plan_wrapper_actions(sample_config(), existing_wrapper_paths=("/absolute.sh",))
        with self.assertRaises(CompatibilityPlanningError):
            plan_wrapper_actions(sample_config(), include_disabled="yes")  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityPlanningError):
            plan_alias_actions(sample_config(), existing_aliases="run-patch")  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityPlanningError):
            CompatibilityPlan("example-project", actions=("bad",))  # type: ignore[arg-type]
        with self.assertRaises(CompatibilityPlanningError):
            CompatibilityPlan("example-project").actions_by_type("bad")
        with self.assertRaises(CompatibilityPlanningError):
            CompatibilityPlan("example-project").actions_for_target("")

    def test_plan_mapping_is_plain_data(self) -> None:
        plan = plan_compatibility(sample_config())
        mapping = plan.to_mapping()
        self.assertEqual(mapping["source_name"], "example-project")
        self.assertIsInstance(mapping["actions"], list)
        self.assertEqual(mapping["actions"][0]["action"], "ensure_lifecycle")

    def test_compat_planning_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/compat_planning.py",
            root / "tests/test_compat_planning.py",
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
