from __future__ import annotations

import unittest

from patchharbor.export_model import (
    ExportArtifact,
    ExportJob,
    ExportModelError,
    export_job_from_mapping,
    export_job_index,
    export_jobs_from_mappings,
)


class PatchHarborExportModelTests(unittest.TestCase):
    def test_export_artifact_defaults_destination_to_source_path(self) -> None:
        artifact = ExportArtifact("reports/full.txt")

        self.assertEqual(artifact.source_path, "reports/full.txt")
        self.assertEqual(artifact.destination_path, "reports/full.txt")
        self.assertFalse(artifact.required)
        self.assertEqual(
            artifact.to_mapping(),
            {
                "source_path": "reports/full.txt",
                "destination_path": "reports/full.txt",
                "required": False,
            },
        )

    def test_export_artifact_round_trips_from_mapping(self) -> None:
        artifact = ExportArtifact.from_mapping(
            {
                "source_path": "build/result.txt",
                "destination_path": "result.txt",
                "required": True,
                "description": "Generated result",
            }
        )

        self.assertEqual(artifact.source_path, "build/result.txt")
        self.assertEqual(artifact.destination_path, "result.txt")
        self.assertTrue(artifact.required)
        self.assertEqual(artifact.description, "Generated result")
        self.assertEqual(ExportArtifact.from_mapping(artifact.to_mapping()), artifact)

    def test_export_artifact_rejects_invalid_paths_and_values(self) -> None:
        invalid_values = [
            "",
            ".",
            "/absolute.txt",
            "../escape.txt",
            "nested/../escape.txt",
            "nested\\windows.txt",
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ExportModelError):
                    ExportArtifact(value)

        with self.assertRaisesRegex(ExportModelError, "destination_path must be relative"):
            ExportArtifact("source.txt", destination_path="/out.txt")
        with self.assertRaisesRegex(ExportModelError, "artifact required must be a boolean"):
            ExportArtifact("source.txt", required="yes")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportModelError, "export artifact must be a mapping"):
            ExportArtifact.from_mapping(["bad"])  # type: ignore[arg-type]

    def test_export_job_validates_and_serializes_generic_command_contract(self) -> None:
        artifact = ExportArtifact("output/full.txt", destination_path="full.txt", required=True)
        job = ExportJob(
            name="full",
            command=("tool", "export", "--format", "full"),
            artifacts=(artifact,),
            environment={"TOOL_MODE": "full"},
            description="Full export",
        )

        self.assertEqual(job.name, "full")
        self.assertEqual(job.command, ("tool", "export", "--format", "full"))
        self.assertEqual(job.artifacts, (artifact,))
        self.assertEqual(job.environment["TOOL_MODE"], "full")
        self.assertEqual(
            job.to_mapping(),
            {
                "name": "full",
                "command": ["tool", "export", "--format", "full"],
                "artifacts": [artifact.to_mapping()],
                "environment": {"TOOL_MODE": "full"},
                "description": "Full export",
            },
        )

    def test_export_job_round_trips_from_mapping(self) -> None:
        mapping = {
            "name": "summary",
            "command": ["tool", "summary"],
            "artifacts": [
                {
                    "source_path": "summary.txt",
                    "destination_path": "summary.txt",
                    "required": False,
                }
            ],
        }

        job = export_job_from_mapping(mapping)

        self.assertEqual(job.name, "summary")
        self.assertEqual(job.command, ("tool", "summary"))
        self.assertEqual(job.artifacts[0].source_path, "summary.txt")
        self.assertEqual(ExportJob.from_mapping(job.to_mapping()), job)

    def test_export_job_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ExportModelError, "export job name"):
            ExportJob("", ("tool",))
        with self.assertRaisesRegex(ExportModelError, "export job command must be a sequence"):
            ExportJob("x", "tool")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportModelError, "export job command must not be empty"):
            ExportJob("x", ())
        with self.assertRaisesRegex(ExportModelError, "export job artifacts must be ExportArtifact or mapping values"):
            ExportJob("x", ("tool",), artifacts=("bad",))  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportModelError, "export job environment values must be strings"):
            ExportJob("x", ("tool",), environment={"A": 1})  # type: ignore[arg-type]
        with self.assertRaisesRegex(ExportModelError, "export job must be a mapping"):
            ExportJob.from_mapping("bad")  # type: ignore[arg-type]

    def test_export_jobs_from_mappings_validates_duplicates(self) -> None:
        jobs = export_jobs_from_mappings(
            [
                {"name": "full", "command": ["tool", "full"]},
                {"name": "ai", "command": ["tool", "ai"]},
            ]
        )

        self.assertEqual(tuple(job.name for job in jobs), ("full", "ai"))

        with self.assertRaisesRegex(ExportModelError, "duplicate export job name: full"):
            export_jobs_from_mappings(
                [
                    {"name": "full", "command": ["tool", "full"]},
                    {"name": "full", "command": ["tool", "other"]},
                ]
            )

    def test_export_job_index_accepts_jobs_and_mappings(self) -> None:
        first = ExportJob("first", ("tool", "one"))
        index = export_job_index(
            [
                first,
                {"name": "second", "command": ["tool", "two"]},
            ]
        )

        self.assertEqual(set(index), {"first", "second"})
        self.assertEqual(index["first"], first)
        self.assertEqual(index["second"].command, ("tool", "two"))

        with self.assertRaisesRegex(ExportModelError, "duplicate export job name: first"):
            export_job_index([first, ExportJob("first", ("tool", "again"))])
        with self.assertRaisesRegex(ExportModelError, "export jobs must be ExportJob or mapping values"):
            export_job_index([object()])  # type: ignore[list-item]

    def test_export_model_does_not_store_repodossier_specific_defaults(self) -> None:
        import patchharbor.export_model as export_model

        text = export_model.__file__
        module_source = open(text, encoding="utf-8").read()
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
