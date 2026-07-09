from __future__ import annotations

import unittest
from pathlib import Path

from patchharbor.runner_display import (
    FooterLine,
    ProgressDisplayItem,
    RunnerDisplayError,
    RunnerDisplayOptions,
    display_options_from_text,
    footer_lines,
    progress_items_from_text,
    render_footer,
    render_progress_context,
    render_runner_footer,
    render_runner_issue,
    render_runner_phase,
    render_runner_result,
)
from patchharbor.runner_status import RunnerIssue, RunnerPhaseResult, RunnerResult, failed_phase, passed_phase


METADATA_TEXT = """#!/usr/bin/env bash
# patchharbor-meta: {"type":"patch","id":"PATCHHARBOR.06f","title":"Display","commit":"Add display"}
# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","start":1,"end":3,"label":"Roadmap item"}
# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","start":5,"end":5,"label":"Milestone item"}
# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}
"""


class PatchHarborRunnerDisplayTests(unittest.TestCase):
    def test_display_options_from_text_reads_display_metadata(self) -> None:
        options = display_options_from_text(METADATA_TEXT)
        self.assertEqual(options.context, 2)
        self.assertEqual(options.layout, "side-by-side")
        self.assertFalse(options.frame)
        self.assertFalse(options.color)

    def test_display_options_default_when_metadata_absent(self) -> None:
        options = display_options_from_text('# patchharbor-meta: {"type":"patch","id":"P","title":"T","commit":"C"}\n')
        self.assertEqual(options, RunnerDisplayOptions())

    def test_display_options_validate_values(self) -> None:
        cases = [
            lambda: RunnerDisplayOptions(context=-1),
            lambda: RunnerDisplayOptions(context=True),  # type: ignore[arg-type]
            lambda: RunnerDisplayOptions(layout="grid"),
            lambda: RunnerDisplayOptions(frame="yes"),  # type: ignore[arg-type]
            lambda: RunnerDisplayOptions(color="yes"),  # type: ignore[arg-type]
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(RunnerDisplayError):
                    case()

    def test_progress_items_from_text_reads_roadmap_and_milestone(self) -> None:
        items = progress_items_from_text(METADATA_TEXT)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].panel, "roadmap")
        self.assertEqual(items[0].status, "active")
        self.assertEqual(items[0].label, "Roadmap item")
        self.assertEqual(items[0].location_label(), "docs/example.md:1-3")
        self.assertEqual(items[1].location_label(), "docs/example.md:5")

    def test_progress_item_mapping_render_and_validation(self) -> None:
        item = ProgressDisplayItem.from_mapping(
            {
                "panel": "context",
                "status": "active",
                "label": "Context",
                "file": "docs/context.md",
                "start": 2,
                "end": 4,
            }
        )
        self.assertEqual(item.to_mapping()["panel"], "context")
        self.assertEqual(item.render(), "context: active: Context (docs/context.md:2-4)")

        with self.assertRaises(RunnerDisplayError):
            ProgressDisplayItem.from_mapping({"panel": "bad", "status": "active", "label": "x"})
        with self.assertRaises(RunnerDisplayError):
            ProgressDisplayItem("roadmap", "active", "x", start=5, end=4)
        with self.assertRaises(RunnerDisplayError):
            ProgressDisplayItem.from_mapping({"panel": "roadmap", "status": "active", "label": "x", "start": True})

    def test_render_progress_context_stacked(self) -> None:
        items = progress_items_from_text(METADATA_TEXT)
        lines = render_progress_context(items, options=RunnerDisplayOptions(layout="stacked"))
        self.assertEqual(lines[0], "roadmap: active: Roadmap item (docs/example.md:1-3)")
        self.assertEqual(lines[1], "milestone: active: Milestone item (docs/example.md:5)")

    def test_render_progress_context_side_by_side(self) -> None:
        items = progress_items_from_text(METADATA_TEXT)
        lines = render_progress_context(items, options=RunnerDisplayOptions(layout="side-by-side"))
        self.assertIn("milestone", lines[0])
        self.assertIn("roadmap", lines[0])
        self.assertTrue(any("Milestone item" in line for line in lines))
        self.assertTrue(any("Roadmap item" in line for line in lines))

    def test_render_progress_context_can_frame_output(self) -> None:
        items = progress_items_from_text(METADATA_TEXT)
        lines = render_progress_context(items, options=RunnerDisplayOptions(layout="stacked", frame=True))
        self.assertTrue(lines[0].startswith("="))
        self.assertTrue(lines[-1].startswith("="))
        self.assertIn("Roadmap item", "\n".join(lines))

    def test_render_progress_context_empty(self) -> None:
        self.assertEqual(render_progress_context(()), ("progress: none",))

    def test_footer_lines_and_render_footer_are_stable(self) -> None:
        lines = footer_lines(
            done=("PATCHHARBOR.06e",),
            current="PATCHHARBOR.06f",
            next_step="PATCHHARBOR.06g",
            problem="fix current patch first",
            info=("target repo only",),
        )
        self.assertEqual([line.kind for line in lines], ["done", "current", "next", "info", "problem"])
        rendered = render_footer(
            done=("PATCHHARBOR.06e",),
            current="PATCHHARBOR.06f",
            next_step="PATCHHARBOR.06g",
            problem="fix current patch first",
            info=("target repo only",),
        )
        self.assertEqual(rendered[0], "Done: PATCHHARBOR.06e")
        self.assertIn("Current: PATCHHARBOR.06f", rendered)
        self.assertIn("Next: PATCHHARBOR.06g", rendered)
        self.assertIn("Problem: fix current patch first", rendered)

    def test_footer_render_can_use_color_and_frame(self) -> None:
        rendered = render_footer(
            done=("PATCHHARBOR.06e",),
            current="PATCHHARBOR.06f",
            options=RunnerDisplayOptions(frame=True, color=True),
        )
        self.assertTrue(rendered[0].startswith("="))
        self.assertIn("\033[32mDone:\033[0m PATCHHARBOR.06e", rendered)
        self.assertIn("\033[35mCurrent:\033[0m PATCHHARBOR.06f", rendered)

    def test_footer_line_validates_values(self) -> None:
        with self.assertRaises(RunnerDisplayError):
            FooterLine("bad", "Label", "Text")
        with self.assertRaises(RunnerDisplayError):
            FooterLine("done", "", "Text")
        with self.assertRaises(RunnerDisplayError):
            FooterLine("done", "Done", "")

    def test_render_runner_issue_and_phase(self) -> None:
        issue = RunnerIssue("script failed", phase="execute", code="execute.failed")
        self.assertEqual(render_runner_issue(issue), "error/execute/execute.failed: script failed")
        phase_lines = render_runner_phase(RunnerPhaseResult("execute", status="failed", message="script failed", issues=(issue,)))
        self.assertEqual(phase_lines[0], "phase execute: failed - script failed")
        self.assertIn("error/execute/execute.failed: script failed", phase_lines[1])

    def test_render_runner_result_includes_phases_and_issues(self) -> None:
        result = RunnerResult(
            status="failed",
            script_path="downloads/patch.sh",
            log_path="downloads/patch.log",
            exit_code=1,
            phases=(passed_phase("metadata"), failed_phase("execute", "script failed", code="execute.failed")),
            issues=(RunnerIssue("top-level warning", severity="warning", phase="display"),),
        )
        lines = render_runner_result(result)
        self.assertEqual(lines[0], "runner status: failed")
        self.assertIn("script: downloads/patch.sh", lines)
        self.assertIn("log: downloads/patch.log", lines)
        self.assertIn("exit code: 1", lines)
        self.assertTrue(any(line.startswith("phase metadata") for line in lines))
        self.assertTrue(any("execute.failed" in line for line in lines))
        self.assertTrue(any("top-level warning" in line for line in lines))

    def test_render_runner_footer_uses_result_status_and_first_error(self) -> None:
        failed = RunnerResult(phases=(failed_phase("execute", "script failed", code="execute.failed"),))
        footer = render_runner_footer(failed, done=("PATCHHARBOR.06e",), next_step="repair current patch")
        self.assertIn("Done: PATCHHARBOR.06e", footer)
        self.assertIn("Current: runner status failed", footer)
        self.assertIn("Next: repair current patch", footer)
        self.assertIn("Problem: script failed", footer)

        passed = RunnerResult(status="passed", phases=(passed_phase("execute"),))
        passed_footer = render_runner_footer(passed, done=("PATCHHARBOR.06e",), next_step="PATCHHARBOR.06g")
        self.assertIn("Current: runner status passed", passed_footer)
        self.assertFalse(any(line.startswith("Problem:") for line in passed_footer))


    def test_render_runner_result_derives_status_from_failed_phase(self) -> None:
        failed = RunnerResult(phases=(failed_phase("execute", "script failed", code="execute.failed"),))
        lines = render_runner_result(failed)
        self.assertEqual(lines[0], "runner status: failed")

    def test_render_runner_footer_derives_status_from_failed_phase(self) -> None:
        failed = RunnerResult(phases=(failed_phase("execute", "script failed", code="execute.failed"),))
        footer = render_runner_footer(failed, done=("PATCHHARBOR.06e",), next_step="repair current patch")
        self.assertIn("Current: runner status failed", footer)
        self.assertIn("Problem: script failed", footer)

    def test_render_runner_footer_respects_explicit_failed_status_without_phase(self) -> None:
        failed = RunnerResult(status="failed")
        footer = render_runner_footer(failed, next_step="repair current patch")
        self.assertIn("Current: runner status failed", footer)
        self.assertIn("Problem: runner failed", footer)

    def test_render_functions_reject_wrong_types(self) -> None:
        with self.assertRaises(RunnerDisplayError):
            render_runner_result("bad")  # type: ignore[arg-type]
        with self.assertRaises(RunnerDisplayError):
            render_runner_phase("bad")  # type: ignore[arg-type]
        with self.assertRaises(RunnerDisplayError):
            render_runner_issue("bad")  # type: ignore[arg-type]
        with self.assertRaises(RunnerDisplayError):
            render_runner_footer("bad")  # type: ignore[arg-type]

    def test_runner_display_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/runner_display.py",
            root / "tests/test_runner_display.py",
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
