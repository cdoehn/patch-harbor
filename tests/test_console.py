from __future__ import annotations

import io
import unittest

from patchharbor.console import FooterItem, colorize, colors_enabled, print_footer, render_footer


class PatchHarborConsoleTests(unittest.TestCase):
    def test_colorize_can_be_disabled(self) -> None:
        self.assertEqual(colorize("hello", "green", enabled=False), "hello")

    def test_colorize_ignores_unknown_color(self) -> None:
        self.assertEqual(colorize("hello", "unknown", enabled=True), "hello")

    def test_colorize_wraps_known_color_when_enabled(self) -> None:
        rendered = colorize("hello", "green", enabled=True)
        self.assertIn("hello", rendered)
        self.assertTrue(rendered.startswith("\033[32m"))
        self.assertTrue(rendered.endswith("\033[0m"))

    def test_colors_enabled_respects_no_color(self) -> None:
        stream = io.StringIO()
        stream.isatty = lambda: True
        self.assertFalse(colors_enabled(stream, env={"NO_COLOR": "1"}))

    def test_colors_enabled_respects_force_color(self) -> None:
        stream = io.StringIO()
        stream.isatty = lambda: False
        self.assertTrue(colors_enabled(stream, env={"FORCE_COLOR": "1"}))

    def test_colors_enabled_uses_stream_tty_by_default(self) -> None:
        stream = io.StringIO()
        stream.isatty = lambda: True
        self.assertTrue(colors_enabled(stream, env={}))

    def test_render_footer_is_plain_by_default(self) -> None:
        footer = render_footer(
            [
                FooterItem("Done", "first task", "green"),
                FooterItem("Next", "second task", "yellow"),
            ],
            width=24,
            color=False,
        )
        self.assertIn("Done: first task", footer)
        self.assertIn("Next: second task", footer)
        self.assertNotIn("\033[", footer)
        self.assertTrue(footer.startswith("=" * 24))
        self.assertTrue(footer.endswith("=" * 24))

    def test_render_footer_can_color_labels(self) -> None:
        footer = render_footer([FooterItem("Done", "task", "green")], color=True)
        self.assertIn("\033[32mDone\033[0m: task", footer)

    def test_render_footer_has_minimum_width(self) -> None:
        footer = render_footer([FooterItem("Done", "task")], width=1, color=False)
        first_line = footer.splitlines()[0]
        self.assertEqual(len(first_line), 20)

    def test_print_footer_writes_to_stream(self) -> None:
        stream = io.StringIO()
        print_footer([FooterItem("Done", "task", "green")], stream=stream, width=22)
        self.assertIn("Done: task", stream.getvalue())

    def test_test_file_does_not_store_local_private_values(self) -> None:
        text = __import__("pathlib").Path(__file__).read_text(encoding="utf-8")
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
