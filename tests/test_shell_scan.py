from __future__ import annotations

import unittest
from pathlib import Path

from patchharbor.shell_scan import (
    HeredocStart,
    ShellCodeLine,
    find_heredoc_starts,
    is_heredoc_terminator,
    iter_shell_code_lines_outside_heredocs,
    shell_text_outside_heredocs,
)


class PatchHarborShellScanTests(unittest.TestCase):
    def test_iter_shell_code_lines_returns_normal_lines_with_numbers(self) -> None:
        lines = iter_shell_code_lines_outside_heredocs("set -e\npytest\n")
        self.assertEqual(
            lines,
            (
                ShellCodeLine(1, "set -e"),
                ShellCodeLine(2, "pytest"),
            ),
        )

    def test_iter_shell_code_lines_skips_simple_heredoc_body_and_terminator(self) -> None:
        text = "cat <<EOF\npayload git diff\nEOF\ngit --no-pager diff\n"
        lines = iter_shell_code_lines_outside_heredocs(text)
        self.assertEqual(
            lines,
            (
                ShellCodeLine(1, "cat <<EOF"),
                ShellCodeLine(4, "git --no-pager diff"),
            ),
        )

    def test_iter_shell_code_lines_supports_quoted_delimiter(self) -> None:
        text = "cat <<'EOF'\nplain git diff inside payload\nEOF\necho done\n"
        lines = iter_shell_code_lines_outside_heredocs(text)
        self.assertEqual(lines[-1], ShellCodeLine(4, "echo done"))
        self.assertEqual(len(lines), 2)

    def test_iter_shell_code_lines_supports_dash_operator_tab_stripping(self) -> None:
        text = "cat <<-EOF\n\tpayload\n\tEOF\necho after\n"
        lines = iter_shell_code_lines_outside_heredocs(text)
        self.assertEqual(
            lines,
            (
                ShellCodeLine(1, "cat <<-EOF"),
                ShellCodeLine(4, "echo after"),
            ),
        )

    def test_find_heredoc_starts_detects_multiple_delimiters_on_one_line(self) -> None:
        starts = find_heredoc_starts("cat <<ONE <<-TWO", line_number=9)
        self.assertEqual(
            starts,
            (
                HeredocStart("ONE", 9, False),
                HeredocStart("TWO", 9, True),
            ),
        )

    def test_iter_shell_code_lines_handles_multiple_heredocs_in_command_order(self) -> None:
        text = "cat <<ONE <<TWO\none body\nONE\ntwo body\nTWO\necho after\n"
        lines = iter_shell_code_lines_outside_heredocs(text)
        self.assertEqual(
            lines,
            (
                ShellCodeLine(1, "cat <<ONE <<TWO"),
                ShellCodeLine(6, "echo after"),
            ),
        )

    def test_find_heredoc_starts_ignores_here_strings(self) -> None:
        self.assertEqual(find_heredoc_starts("cat <<< \"$value\""), ())

    def test_find_heredoc_starts_ignores_comments_and_quoted_text(self) -> None:
        self.assertEqual(find_heredoc_starts("# cat <<EOF"), ())
        self.assertEqual(find_heredoc_starts("echo 'cat <<EOF'"), ())
        self.assertEqual(find_heredoc_starts('echo "cat <<EOF"'), ())

    def test_find_heredoc_starts_keeps_quoted_delimiter_when_operator_is_unquoted(self) -> None:
        starts = find_heredoc_starts('cat <<"EOF"', line_number=3)
        self.assertEqual(starts, (HeredocStart("EOF", 3, False),))

    def test_shell_text_outside_heredocs_joins_only_code_lines(self) -> None:
        text = "cat <<EOF\nhidden\nEOF\necho visible\n"
        self.assertEqual(shell_text_outside_heredocs(text), "cat <<EOF\necho visible")

    def test_is_heredoc_terminator_respects_tab_stripping_only_when_requested(self) -> None:
        self.assertTrue(is_heredoc_terminator("EOF", "EOF"))
        self.assertFalse(is_heredoc_terminator("\tEOF", "EOF"))
        self.assertTrue(is_heredoc_terminator("\tEOF", "EOF", strip_tabs=True))
        self.assertFalse(is_heredoc_terminator(" EOF", "EOF", strip_tabs=True))

    def test_public_dataclasses_reject_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            ShellCodeLine(0, "bad")
        with self.assertRaises(ValueError):
            ShellCodeLine(1, 5)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            HeredocStart("", 1)
        with self.assertRaises(ValueError):
            HeredocStart("EOF", 0)
        with self.assertRaises(ValueError):
            HeredocStart("EOF", 1, strip_tabs="yes")  # type: ignore[arg-type]

    def test_public_functions_reject_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            find_heredoc_starts(5)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            find_heredoc_starts("cat <<EOF", line_number=0)
        with self.assertRaises(ValueError):
            iter_shell_code_lines_outside_heredocs(5)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            is_heredoc_terminator(5, "EOF")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            is_heredoc_terminator("EOF", "")

    def test_shell_scan_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/shell_scan.py",
            root / "tests/test_shell_scan.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
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
