from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from patchharbor.runner_preflight import (
    PatchMetadataEntry,
    check_metadata_file,
    check_metadata_text,
    check_repeat_success,
    check_script_freshness,
    collect_patch_metadata_entries,
    first_patch_id,
    metadata_summary,
    patch_entries,
    run_preflight_checks,
)
from patchharbor.runner_status import RunnerStatusError


VALID_SCRIPT = """#!/usr/bin/env bash
# patchharbor-meta: {"type":"patch","id":"PATCHHARBOR.06c","title":"Runner preflight","commit":"Add runner preflight APIs"}
# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Roadmap"}
# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Milestone"}
# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}
set -euo pipefail
"""


class PatchHarborRunnerPreflightTests(unittest.TestCase):
    def test_collect_patch_metadata_entries_reads_patchharbor_metadata(self) -> None:
        entries = collect_patch_metadata_entries(VALID_SCRIPT)
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0].prefix, "patchharbor-meta")
        self.assertEqual(entries[0].type, "patch")
        self.assertEqual(entries[0].patch_id, "PATCHHARBOR.06c")

    def test_collect_patch_metadata_entries_supports_legacy_metadata_prefix(self) -> None:
        text = (
            '# repodossier-meta: {"type":"patch","id":"LEGACY.01","title":"Legacy","commit":"Add legacy"}\n'
            '# repodossier-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Roadmap"}\n'
            '# repodossier-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Milestone"}\n'
            '# repodossier-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}\n'
        )
        entries = collect_patch_metadata_entries(text)
        self.assertEqual(entries[0].prefix, "repodossier-meta")
        self.assertEqual(entries[0].patch_id, "LEGACY.01")

    def test_collect_patch_metadata_entries_rejects_invalid_json(self) -> None:
        with self.assertRaises(RunnerStatusError):
            collect_patch_metadata_entries('# patchharbor-meta: {"type":\n')

    def test_collect_patch_metadata_entries_rejects_non_object_json(self) -> None:
        with self.assertRaises(RunnerStatusError):
            collect_patch_metadata_entries("# patchharbor-meta: []\n")

    def test_collect_patch_metadata_entries_rejects_empty_payload(self) -> None:
        with self.assertRaises(RunnerStatusError):
            collect_patch_metadata_entries("# patchharbor-meta:\n")

    def test_collect_patch_metadata_entries_rejects_known_prefix_with_garbage(self) -> None:
        with self.assertRaises(RunnerStatusError):
            collect_patch_metadata_entries("# repodossier-meta: not-json\n")

    def test_collect_patch_metadata_entries_rejects_missing_type_field(self) -> None:
        with self.assertRaises(RunnerStatusError):
            collect_patch_metadata_entries('# patchharbor-meta: {"id":"PATCHHARBOR.06c"}\n')

    def test_patch_entries_and_first_patch_id_filter_metadata(self) -> None:
        entries = collect_patch_metadata_entries(VALID_SCRIPT)
        patches = patch_entries(entries)
        self.assertEqual(len(patches), 1)
        self.assertEqual(first_patch_id(entries), "PATCHHARBOR.06c")

    def test_patch_metadata_entry_validates_values(self) -> None:
        with self.assertRaises(RunnerStatusError):
            PatchMetadataEntry("bad", {}, 1)
        with self.assertRaises(RunnerStatusError):
            PatchMetadataEntry("patchharbor-meta", [], 1)  # type: ignore[arg-type]
        with self.assertRaises(RunnerStatusError):
            PatchMetadataEntry("patchharbor-meta", {}, 0)

    def test_metadata_summary_is_stable(self) -> None:
        entries = collect_patch_metadata_entries(VALID_SCRIPT)
        self.assertEqual(
            metadata_summary(entries),
            (
                "line 2: patchharbor-meta: patch:PATCHHARBOR.06c",
                "line 3: patchharbor-meta: progress",
                "line 4: patchharbor-meta: progress",
                "line 5: patchharbor-meta: display",
            ),
        )

    def test_check_metadata_text_passes_valid_metadata_contract(self) -> None:
        phase = check_metadata_text(VALID_SCRIPT)
        self.assertEqual(phase.phase, "metadata")
        self.assertEqual(phase.status, "passed")
        self.assertIn("PATCHHARBOR.06c", phase.message or "")

    def test_check_metadata_text_fails_missing_metadata(self) -> None:
        phase = check_metadata_text("#!/usr/bin/env bash\n")
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "metadata.missing")

    def test_check_metadata_text_fails_invalid_json(self) -> None:
        phase = check_metadata_text('# patchharbor-meta: {"type":\n')
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "metadata.invalid")

    def test_check_metadata_text_fails_incomplete_contract(self) -> None:
        phase = check_metadata_text('# patchharbor-meta: {"type":"patch","id":"PATCHHARBOR.06c"}\n')
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "metadata.invalid_contract")
        self.assertIn("commit", phase.issues[0].message)

    def test_check_metadata_text_fails_duplicate_patch_records(self) -> None:
        text = (
            '# patchharbor-meta: {"type":"patch","id":"PATCHHARBOR.06c","title":"One","commit":"Add one"}\n'
            '# patchharbor-meta: {"type":"patch","id":"PATCHHARBOR.06c-2","title":"Two","commit":"Add two"}\n'
            '# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Roadmap"}\n'
            '# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Milestone"}\n'
            '# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}\n'
        )
        phase = check_metadata_text(text)
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "metadata.invalid_contract")
        self.assertIn("expected exactly one patch metadata record", phase.issues[0].message)

    def test_check_metadata_file_wraps_read_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            phase = check_metadata_file(Path(tmp) / "missing.sh")
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "file.read_error")

    def test_check_script_freshness_passes_fresh_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text(VALID_SCRIPT, encoding="utf-8")
            os.utime(path, (100.0, 100.0))
            phase = check_script_freshness(path, max_age_seconds=10, now=105)
        self.assertEqual(phase.status, "passed")
        self.assertIn("script fresh", phase.message or "")

    def test_check_script_freshness_fails_stale_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text(VALID_SCRIPT, encoding="utf-8")
            os.utime(path, (100.0, 100.0))
            phase = check_script_freshness(path, max_age_seconds=10, now=120)
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "freshness.too_old")
        self.assertEqual(phase.issues[0].data["max_age_seconds"], 10.0)

    def test_check_script_freshness_wraps_stat_errors_and_validates_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            phase = check_script_freshness(Path(tmp) / "missing.sh", max_age_seconds=10, now=120)
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "file.stat_error")
        with self.assertRaises(RunnerStatusError):
            check_script_freshness("patch.sh", max_age_seconds=-1)

    def test_check_script_freshness_validates_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text(VALID_SCRIPT, encoding="utf-8")
            with self.assertRaises(RunnerStatusError):
                check_script_freshness(path, max_age_seconds=10, now="bad")  # type: ignore[arg-type]

    def test_check_repeat_success_passes_new_patch_id(self) -> None:
        phase = check_repeat_success("PATCHHARBOR.06c", ("PATCHHARBOR.06b",))
        self.assertEqual(phase.status, "passed")
        self.assertIn("not repeated", phase.message or "")

    def test_check_repeat_success_fails_repeated_patch_id(self) -> None:
        phase = check_repeat_success("PATCHHARBOR.06c", ("PATCHHARBOR.06c",))
        self.assertEqual(phase.status, "failed")
        self.assertEqual(phase.issues[0].code, "repeat.already_applied")
        self.assertEqual(phase.issues[0].data["patch_id"], "PATCHHARBOR.06c")

    def test_check_repeat_success_can_skip_without_patch_id(self) -> None:
        phase = check_repeat_success(None, ())
        self.assertEqual(phase.status, "skipped")

    def test_check_repeat_success_validates_inputs(self) -> None:
        with self.assertRaises(RunnerStatusError):
            check_repeat_success("", ())
        with self.assertRaises(RunnerStatusError):
            check_repeat_success("PATCH", ("",))
        with self.assertRaises(RunnerStatusError):
            check_repeat_success("PATCHHARBOR.06c", "PATCHHARBOR.06b")  # type: ignore[arg-type]

    def test_run_preflight_checks_combines_metadata_repeat_and_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text(VALID_SCRIPT, encoding="utf-8")
            os.utime(path, (100.0, 100.0))
            result = run_preflight_checks(path, successful_patch_ids=("PATCHHARBOR.06b",), max_age_seconds=20, now=105)
        self.assertTrue(result.ok)
        self.assertEqual(result.phase_names(), ("metadata", "repeat", "freshness"))

    def test_run_preflight_checks_fails_repeated_patch_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text(VALID_SCRIPT, encoding="utf-8")
            result = run_preflight_checks(path, successful_patch_ids=("PATCHHARBOR.06c",), max_age_seconds=None)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.by_phase()["repeat"].issues[0].code, "repeat.already_applied")
        self.assertEqual(result.by_phase()["freshness"].status, "skipped")

    def test_run_preflight_checks_handles_read_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_preflight_checks(Path(tmp) / "missing.sh", successful_patch_ids=(), max_age_seconds=10)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.by_phase()["metadata"].issues[0].code, "file.read_error")
        self.assertEqual(result.by_phase()["repeat"].status, "skipped")
        self.assertEqual(result.by_phase()["freshness"].status, "skipped")

    def test_runner_preflight_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/runner_preflight.py",
            root / "tests/test_runner_preflight.py",
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
