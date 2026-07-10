from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patchharbor.patch_lint_rules import (
    RULE_FOOTER,
    RULE_GIT_NO_PAGER,
    RULE_MARKDOWN_FENCE,
    RULE_TEST_EXECUTION,
    lint_git_pager_commands,
    lint_markdown_fence_literals,
    lint_missing_footer,
    lint_missing_test_execution,
    lint_patch_file,
    lint_patch_text,
)


class PatchHarborPatchLintRulesTests(unittest.TestCase):
    def test_git_pager_rule_flags_plain_git_diff_and_log(self) -> None:
        result = lint_git_pager_commands("git diff\ngit log --oneline\n")
        self.assertEqual([finding.rule_id for finding in result.findings], [RULE_GIT_NO_PAGER, RULE_GIT_NO_PAGER])
        self.assertEqual([finding.line_number for finding in result.findings], [1, 2])
        self.assertEqual(result.findings[0].data["command"], "git diff")
        self.assertEqual(result.findings[1].data["command"], "git log")

    def test_git_pager_rule_flags_control_keyword_commands(self) -> None:
        text = (
            "if git log --oneline; then\n"
            "while git diff --check; do\n"
            "until git log; do\n"
            "! git diff\n"
            "time git log\n"
            "command git diff\n"
        )
        result = lint_git_pager_commands(text)
        self.assertEqual(len(result.findings), 6)
        self.assertEqual([finding.line_number for finding in result.findings], [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            [finding.data["command"] for finding in result.findings],
            ["git log", "git diff", "git log", "git diff", "git log", "git diff"],
        )

    def test_git_pager_rule_flags_env_prefixed_unsafe_commands(self) -> None:
        text = "env FOO=bar git log\nFOO=bar git diff\n"
        result = lint_git_pager_commands(text)
        self.assertEqual(len(result.findings), 2)
        self.assertEqual([finding.data["command"] for finding in result.findings], ["git log", "git diff"])

    def test_git_pager_rule_checks_multiple_commands_on_same_line_independently(self) -> None:
        text = "echo ok; git diff\ntrue && git log\nfalse || git diff\n"
        result = lint_git_pager_commands(text)
        self.assertEqual(len(result.findings), 3)
        self.assertEqual([finding.line_number for finding in result.findings], [1, 2, 3])
        self.assertEqual(
            [finding.data["command"] for finding in result.findings],
            ["git diff", "git log", "git diff"],
        )

    def test_git_pager_rule_safe_command_does_not_hide_later_unsafe_command(self) -> None:
        text = "git --no-pager status; git diff\nGIT_PAGER=cat echo ok; git log\n"
        result = lint_git_pager_commands(text)
        self.assertEqual(len(result.findings), 2)
        self.assertEqual([finding.line_number for finding in result.findings], [1, 2])
        self.assertEqual(
            [finding.data["command"] for finding in result.findings],
            ["git diff", "git log"],
        )

    def test_git_pager_rule_column_points_to_git_command(self) -> None:
        cases = {
            "git diff": 1,
            "if git log --oneline; then": 4,
            "echo ok; git diff": 10,
            "true && git log": 9,
            "false || git diff": 10,
        }
        for text, expected_column in cases.items():
            with self.subTest(text=text):
                result = lint_git_pager_commands(text + "\n")
                self.assertEqual(result.findings[0].column, expected_column)

    def test_git_pager_rule_ignores_safe_no_pager_and_git_pager_env(self) -> None:
        text = "git --no-pager diff\nGIT_PAGER=cat git log --oneline\nenv GIT_PAGER=cat git log\n"
        self.assertEqual(lint_git_pager_commands(text).findings, ())

    def test_git_pager_rule_ignores_comments_quotes_and_heredoc_payload(self) -> None:
        text = (
            "# git diff\n"
            "echo 'git diff'\n"
            "cat <<EOF\n"
            "git log --oneline\n"
            "EOF\n"
            "git --no-pager log --oneline\n"
        )
        self.assertEqual(lint_git_pager_commands(text).findings, ())

    def test_footer_rule_accepts_print_footer_with_trap_outside_heredoc(self) -> None:
        text = "print_footer() {\n  echo done\n}\ntrap print_footer EXIT\n"
        self.assertEqual(lint_missing_footer(text).findings, ())

    def test_footer_rule_flags_missing_footer_contract(self) -> None:
        result = lint_missing_footer("echo no footer\n")
        self.assertEqual(result.findings[0].rule_id, RULE_FOOTER)
        self.assertIn("print_footer", result.findings[0].message)

    def test_footer_rule_ignores_footer_text_inside_heredoc(self) -> None:
        text = "cat <<EOF\nprint_footer() {\n}\ntrap print_footer EXIT\nEOF\n"
        result = lint_missing_footer(text)
        self.assertEqual(result.findings[0].rule_id, RULE_FOOTER)

    def test_test_execution_rule_accepts_common_test_commands(self) -> None:
        accepted = [
            "python3 -m compileall src tests\n",
            "python -m unittest discover -s tests\n",
            "python3 -m pytest\n",
            "bash -n patch.sh\n",
        ]
        for text in accepted:
            with self.subTest(text=text):
                self.assertEqual(lint_missing_test_execution(text).findings, ())

    def test_test_execution_rule_flags_missing_tests(self) -> None:
        result = lint_missing_test_execution("echo no tests\n")
        self.assertEqual(result.findings[0].rule_id, RULE_TEST_EXECUTION)

    def test_test_execution_rule_ignores_test_words_inside_heredoc(self) -> None:
        text = "cat <<EOF\npython3 -m compileall src tests\nEOF\necho done\n"
        result = lint_missing_test_execution(text)
        self.assertEqual(result.findings[0].rule_id, RULE_TEST_EXECUTION)

    def test_markdown_fence_rule_flags_literal_fence_sequence(self) -> None:
        fence = chr(96) * 3
        result = lint_markdown_fence_literals("echo before\n" + fence + "bash\n")
        self.assertEqual(result.findings[0].rule_id, RULE_MARKDOWN_FENCE)
        self.assertEqual(result.findings[0].line_number, 2)

    def test_markdown_fence_rule_allows_dynamic_construction_without_literal(self) -> None:
        text = "fence = chr(96) * 3\n"
        self.assertEqual(lint_markdown_fence_literals(text).findings, ())

    def test_lint_patch_text_combines_generic_rules(self) -> None:
        fence = chr(96) * 3
        result = lint_patch_text("git diff\n" + fence + "\n")
        rule_ids = {finding.rule_id for finding in result.findings}
        self.assertIn(RULE_GIT_NO_PAGER, rule_ids)
        self.assertIn(RULE_FOOTER, rule_ids)
        self.assertIn(RULE_TEST_EXECUTION, rule_ids)
        self.assertIn(RULE_MARKDOWN_FENCE, rule_ids)

    def test_lint_patch_file_reads_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patch.sh"
            path.write_text("git log\n", encoding="utf-8")
            result = lint_patch_file(path)
        self.assertIn(RULE_GIT_NO_PAGER, {finding.rule_id for finding in result.findings})

    def test_patch_lint_rule_files_do_not_store_local_private_values(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checked = [
            root / "src/patchharbor/patch_lint_rules.py",
            root / "tests/test_patch_lint_rules.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "~/" + "Projects",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
