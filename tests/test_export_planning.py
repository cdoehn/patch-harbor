from __future__ import annotations

import unittest

from patchharbor.export_model import ExportArtifact, ExportJob
from patchharbor.export_planning import (
    DEFAULT_EXPORT_PHASE_ORDER,
    ExportPlan,
    ExportPlanError,
    PlannedExportArtifact,
    create_export_plan,
    create_export_plan_from_mappings,
)


class PatchHarborExportPlanningTests(unittest.TestCase):
    def make_jobs(self) -> tuple[ExportJob, ExportJob, ExportJob]:
        return (
            ExportJob(
                "full",
                ("tool", "full"),
                artifacts=(ExportArtifact("full.txt", required=True),),
            ),
            ExportJob(
                "ai",
                ("tool", "ai"),
                artifacts=(ExportArtifact("ai.txt"),),
            ),
            ExportJob("docs", ("tool", "docs")),
        )

    def test_export_plan_selects_all_jobs_by_default_in_declared_order(self) -> None:
        jobs = self.make_jobs()

        plan = create_export_plan(jobs)

        self.assertIsInstance(plan, ExportPlan)
        self.assertEqual(plan.jobs, jobs)
        self.assertEqual(plan.requested_names, ("full", "ai", "docs"))
        self.assertEqual(plan.selected_jobs, jobs)
        self.assertEqual(plan.selected_names, ("full", "ai", "docs"))
        self.assertFalse(plan.dry_run)
        self.assertIsNone(plan.output_directory)
        self.assertEqual(plan.phase_order, DEFAULT_EXPORT_PHASE_ORDER)

    def test_export_plan_selects_requested_jobs_in_requested_order(self) -> None:
        jobs = self.make_jobs()

        plan = create_export_plan(jobs, requested_names=("ai", "full"), dry_run=True, output_directory="exports")

        self.assertEqual(plan.requested_names, ("ai", "full"))
        self.assertEqual(plan.selected_names, ("ai", "full"))
        self.assertEqual(tuple(job.command for job in plan.selected_jobs), (("tool", "ai"), ("tool", "full")))
        self.assertTrue(plan.dry_run)
        self.assertEqual(plan.output_directory, "exports")

    def test_export_plan_collects_artifacts_from_selected_jobs_only(self) -> None:
        jobs = self.make_jobs()

        plan = create_export_plan(jobs, requested_names=("ai", "full"))

        self.assertEqual(tuple(artifact.job_name for artifact in plan.artifacts), ("ai", "full"))
        self.assertEqual(tuple(artifact.source_path for artifact in plan.artifacts), ("ai.txt", "full.txt"))
        self.assertEqual(tuple(artifact.destination_path for artifact in plan.artifacts), ("ai.txt", "full.txt"))
        self.assertEqual(tuple(artifact.required for artifact in plan.artifacts), (False, True))
        self.assertTrue(all(isinstance(artifact, PlannedExportArtifact) for artifact in plan.artifacts))

    def test_export_plan_round_trips_to_serializable_mapping(self) -> None:
        plan = create_export_plan(
            self.make_jobs(),
            requested_names=("full",),
            dry_run=True,
            output_directory="downloads",
            environment={"MODE": "test"},
        )

        mapping = plan.to_mapping()

        self.assertEqual(mapping["requested_names"], ["full"])
        self.assertEqual(mapping["selected_names"], ["full"])
        self.assertEqual(mapping["dry_run"], True)
        self.assertEqual(mapping["output_directory"], "downloads")
        self.assertEqual(mapping["environment"], {"MODE": "test"})
        self.assertEqual(mapping["phase_order"], list(DEFAULT_EXPORT_PHASE_ORDER))
        self.assertEqual(mapping["selected_jobs"][0]["name"], "full")
        self.assertEqual(mapping["artifacts"][0]["job_name"], "full")
        self.assertEqual(mapping["artifacts"][0]["source_path"], "full.txt")

    def test_export_plan_from_mappings_uses_export_job_model_contract(self) -> None:
        plan = create_export_plan_from_mappings(
            [
                {"name": "summary", "command": ["tool", "summary"], "artifacts": [{"source_path": "summary.txt"}]},
                {"name": "detail", "command": ["tool", "detail"]},
            ],
            requested_names=("detail",),
        )

        self.assertEqual(plan.selected_names, ("detail",))
        self.assertEqual(plan.selected_jobs[0].command, ("tool", "detail"))
        self.assertEqual(plan.artifacts, ())

    def test_export_plan_rejects_unknown_or_duplicate_selection(self) -> None:
        jobs = self.make_jobs()

        with self.assertRaisesRegex(ExportPlanError, "unknown export job: missing"):
            create_export_plan(jobs, requested_names=("missing",))
        with self.assertRaisesRegex(ExportPlanError, "duplicate requested_names: full"):
            create_export_plan(jobs, requested_names=("full", "full"))
        with self.assertRaisesRegex(ExportPlanError, "duplicate export job names: full"):
            create_export_plan([ExportJob("full", ("tool", "one")), ExportJob("full", ("tool", "two"))])

    def test_export_plan_validates_paths_environment_and_phase_order(self) -> None:
        jobs = self.make_jobs()

        with self.assertRaisesRegex(ExportPlanError, "export plan output_directory must be relative"):
            create_export_plan(jobs, output_directory="/absolute")
        with self.assertRaisesRegex(ExportPlanError, "export plan output_directory must not contain"):
            create_export_plan(jobs, output_directory="../escape")
        with self.assertRaisesRegex(ExportPlanError, "export plan dry_run must be a boolean"):
            ExportPlan(jobs=jobs, requested_names=("full",), selected_jobs=(jobs[0],), artifacts=(), dry_run="yes")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportPlanError, "export plan phase_order must not be empty"):
            create_export_plan(jobs, phase_order=())
        with self.assertRaisesRegex(ExportPlanError, "export plan environment values must be strings"):
            create_export_plan(jobs, environment={"A": 1})  # type: ignore[dict-item]

    def test_export_plan_rejects_inconsistent_manual_plan_instances(self) -> None:
        first, second, _third = self.make_jobs()

        with self.assertRaisesRegex(ExportPlanError, "selected_jobs must match requested_names order"):
            ExportPlan(jobs=(first, second), requested_names=("second",), selected_jobs=(first,), artifacts=())
        with self.assertRaisesRegex(ExportPlanError, "selected job is not part of jobs"):
            ExportPlan(jobs=(first,), requested_names=("ai",), selected_jobs=(second,), artifacts=())
        with self.assertRaisesRegex(ExportPlanError, "export plan artifacts must contain PlannedExportArtifact"):
            ExportPlan(jobs=(first,), requested_names=("full",), selected_jobs=(first,), artifacts=(object(),))  # type: ignore[arg-type]

    def test_export_planning_does_not_store_repodossier_specific_defaults(self) -> None:
        import patchharbor.export_planning as export_planning

        module_source = open(export_planning.__file__, encoding="utf-8").read()
        forbidden = [
            "repodossier",
            "REPODOSSIER_BIN",
            "full.txt",
            "ai.txt",
            "docs.txt",
            "changed.txt",
            "patch-rules.md",
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, module_source)


if __name__ == "__main__":
    unittest.main()
