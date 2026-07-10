from __future__ import annotations

import unittest

from patchharbor.metadata import (
    DEFAULT_MARKER,
    LEGACY_MARKER,
    MetadataError,
    MetadataRecord,
    MetadataValidationResult,
    parse_metadata_lines,
    records_by_type,
    validate_patch_metadata,
    validate_patch_text,
)


VALID_TEXT = '''
# patchharbor-meta: {"type":"patch","id":"EXAMPLE.01","title":"Example patch","commit":"Add example patch"}
# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Example roadmap"}
# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Example milestone"}
# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}
'''


class PatchHarborMetadataTests(unittest.TestCase):
    def test_parse_metadata_lines_finds_patchharbor_records(self) -> None:
        records = parse_metadata_lines(VALID_TEXT)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].type, "patch")
        self.assertEqual(records[0].marker, DEFAULT_MARKER)
        self.assertEqual(records[0].data["id"], "EXAMPLE.01")
        self.assertGreater(records[0].line_number, 0)

    def test_parse_metadata_lines_accepts_legacy_marker(self) -> None:
        text = VALID_TEXT.replace(DEFAULT_MARKER, LEGACY_MARKER)
        records = parse_metadata_lines(text)
        self.assertEqual(len(records), 4)
        self.assertEqual({record.marker for record in records}, {LEGACY_MARKER})

    def test_invalid_json_raises_metadata_error(self) -> None:
        with self.assertRaises(MetadataError):
            parse_metadata_lines('# patchharbor-meta: {"type":')

    def test_non_object_json_raises_metadata_error(self) -> None:
        with self.assertRaises(MetadataError):
            parse_metadata_lines("# patchharbor-meta: []")

    def test_missing_type_raises_metadata_error(self) -> None:
        with self.assertRaises(MetadataError):
            parse_metadata_lines('# patchharbor-meta: {"id":"EXAMPLE.01"}')

    def test_empty_type_raises_metadata_error(self) -> None:
        with self.assertRaises(MetadataError):
            parse_metadata_lines('# patchharbor-meta: {"type":""}')

    def test_records_by_type_groups_records(self) -> None:
        grouped = records_by_type(parse_metadata_lines(VALID_TEXT))
        self.assertIn("patch", grouped)
        self.assertIn("progress", grouped)
        self.assertEqual(len(grouped["progress"]), 2)

    def test_validate_patch_metadata_accepts_required_contract(self) -> None:
        result = validate_patch_metadata(parse_metadata_lines(VALID_TEXT))
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, ())

    def test_validate_patch_text_accepts_required_contract(self) -> None:
        result = validate_patch_text(VALID_TEXT)
        self.assertTrue(result.ok)

    def test_validate_patch_text_requires_patch_record(self) -> None:
        text = VALID_TEXT.replace('"type":"patch"', '"type":"note"')
        result = validate_patch_text(text)
        self.assertFalse(result.ok)
        self.assertIn("expected exactly one patch metadata record", result.errors)

    def test_validate_patch_text_requires_roadmap_progress(self) -> None:
        text = '''
# patchharbor-meta: {"type":"patch","id":"EXAMPLE.01","title":"Example patch","commit":"Add example patch"}
# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Example milestone"}
# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}
'''
        result = validate_patch_text(text)
        self.assertFalse(result.ok)
        self.assertIn("missing roadmap progress metadata record", result.errors)

    def test_validate_patch_text_requires_milestone_progress(self) -> None:
        text = '''
# patchharbor-meta: {"type":"patch","id":"EXAMPLE.01","title":"Example patch","commit":"Add example patch"}
# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Example roadmap"}
# patchharbor-meta: {"type":"display","context":2,"layout":"side-by-side","frame":false}
'''
        result = validate_patch_text(text)
        self.assertFalse(result.ok)
        self.assertIn("missing milestone progress metadata record", result.errors)

    def test_validate_patch_text_requires_display_record(self) -> None:
        text = '''
# patchharbor-meta: {"type":"patch","id":"EXAMPLE.01","title":"Example patch","commit":"Add example patch"}
# patchharbor-meta: {"type":"progress","panel":"roadmap","status":"active","file":"docs/example.md","label":"Example roadmap"}
# patchharbor-meta: {"type":"progress","panel":"milestone","status":"active","file":"docs/example.md","label":"Example milestone"}
'''
        result = validate_patch_text(text)
        self.assertFalse(result.ok)
        self.assertIn("expected exactly one display metadata record", result.errors)

    def test_validation_result_raise_for_errors(self) -> None:
        result = MetadataValidationResult(records=(), errors=("example error",))
        with self.assertRaises(MetadataError):
            result.raise_for_errors()

    def test_metadata_record_require_string_returns_value(self) -> None:
        record = MetadataRecord(type="patch", data={"id": "EXAMPLE.01"}, line_number=1, marker=DEFAULT_MARKER)
        self.assertEqual(record.require_string("id"), "EXAMPLE.01")

    def test_metadata_record_require_string_rejects_missing_or_empty_value(self) -> None:
        record = MetadataRecord(type="patch", data={"id": ""}, line_number=1, marker=DEFAULT_MARKER)
        with self.assertRaises(MetadataError):
            record.require_string("id")
        with self.assertRaises(MetadataError):
            record.require_string("title")

    def test_metadata_files_do_not_store_local_private_values(self) -> None:
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        text = "\n".join(
            [
                (root / "src/patchharbor/metadata.py").read_text(encoding="utf-8"),
                (root / "tests/test_metadata.py").read_text(encoding="utf-8"),
            ]
        )
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
