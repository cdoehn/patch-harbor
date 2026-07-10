from __future__ import annotations

import unittest

from patchharbor.export_display import (
    ExportDisplayError,
    format_export_command,
    render_export_artifact_table,
    render_export_job_table,
    render_export_plan,
    render_export_plan_summary,
)
from patchharbor.export_model import ExportArtifact, ExportJob
from patchharbor.export_planning import DEFAULT_EXPORT_PHASE_ORDER, create_export_plan


class PatchHarborExportDisplayTests(unittest.TestCase):
    def make_jobs(self) -> tuple[ExportJob, ExportJob]:
        return (
            ExportJob(
                "full",
                ("tool", "full", "--output", "full export.txt"),
                artifacts=(ExportArtifact("full.txt", required=True, description="complete export"),),
                description="Complete export",
            ),
            ExportJob(
                "ai",
                ("tool", "export-ai"),
                artifacts=(ExportArtifact("ai.txt", destination_path="exports/ai.txt"),),
            ),
        )

    def test_format_export_command_quotes_only_when_needed(self) -> None:
        self.assertEqual(format_export_command(("tool", "full", "--flag")), "tool full --flag")
        self.assertEqual(format_export_command(("tool", "full export.txt")), "tool 'full export.txt'")
        self.assertEqual(format_export_command(("tool", "Bob's export")), "tool 'Bob'\"'\"'s export'")

    def test_render_export_job_table_displays_generic_job_fields(self) -> None:
        table = render_export_job_table(self.make_jobs())

        self.assertIn("name", table)
        self.assertIn("command", table)
        self.assertIn("artifacts", table)
        self.assertIn("description", table)
        self.assertIn("full", table)
        self.assertIn("tool full --output 'full export.txt'", table)
        self.assertIn("Complete export", table)
        self.assertIn("ai", table)
        self.assertIn("tool export-ai", table)

    def test_render_export_plan_summary_displays_selection_dry_run_and_phase_contract(self) -> None:
        plan = create_export_plan(
            self.make_jobs(),
            requested_names=("ai", "full"),
            dry_run=True,
            output_directory="downloads",
            environment={"MODE": "test"},
        )

        summary = render_export_plan_summary(plan)

        self.assertIn("Export plan", summary)
        self.assertIn("requested: ai, full", summary)
        self.assertIn("selected: ai, full", summary)
        self.assertIn("dry_run: yes", summary)
        self.assertIn("output_directory: downloads", summary)
        self.assertIn("environment: 1", summary)
        self.assertIn(f"phases: {', '.join(DEFAULT_EXPORT_PHASE_ORDER)}", summary)
        self.assertIn("artifacts: 2", summary)

    def test_render_export_artifact_table_displays_planned_artifacts(self) -> None:
        plan = create_export_plan(self.make_jobs(), requested_names=("ai", "full"))

        table = render_export_artifact_table(plan)

        self.assertIn("job", table)
        self.assertIn("source", table)
        self.assertIn("destination", table)
        self.assertIn("required", table)
        self.assertIn("ai.txt", table)
        self.assertIn("exports/ai.txt", table)
        self.assertIn("full.txt", table)
        self.assertIn("yes", table)
        self.assertIn("no", table)

    def test_render_export_plan_can_include_or_omit_sections(self) -> None:
        plan = create_export_plan(self.make_jobs(), requested_names=("full",))

        full = render_export_plan(plan)
        summary_only = render_export_plan(plan, include_jobs=False, include_artifacts=False)

        self.assertIn("Export plan", full)
        self.assertIn("Jobs", full)
        self.assertIn("Artifacts", full)
        self.assertIn("full.txt", full)
        self.assertIn("Export plan", summary_only)
        self.assertNotIn("Jobs", summary_only)
        self.assertNotIn("Artifacts", summary_only)

    def test_display_helpers_validate_inputs_without_guessing_contracts(self) -> None:
        with self.assertRaisesRegex(ExportDisplayError, "export command must not be empty"):
            format_export_command(())
        with self.assertRaisesRegex(ExportDisplayError, "export command must be a sequence"):
            format_export_command("tool full")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportDisplayError, "export jobs must not be empty"):
            render_export_job_table(())
        with self.assertRaisesRegex(ExportDisplayError, "export jobs must contain ExportJob values"):
            render_export_job_table((object(),))  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportDisplayError, "require an ExportPlan"):
            render_export_plan(object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportDisplayError, "include_jobs must be a boolean"):
            render_export_plan(create_export_plan(self.make_jobs()), include_jobs="yes")  # type: ignore[arg-type]

    def test_export_display_does_not_store_repodossier_specific_defaults(self) -> None:
        import patchharbor.export_display as export_display

        module_source = open(export_display.__file__, encoding="utf-8").read()
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
