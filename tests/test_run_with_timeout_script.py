from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_with_timeout.sh"


class RunWithTimeoutScriptTests(unittest.TestCase):
    def run_wrapper(self, *arguments: str, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

    def test_script_is_executable_and_has_valid_bash_syntax(self) -> None:
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_successful_command_runs_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "attempts"
            command = f'printf "x\\n" >> "$1"'
            result = self.run_wrapper(
                "--timeout", "2s",
                "--attempts", "3",
                "--",
                "bash", "-c", command, "bash", str(marker),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "x\n")

    def test_ordinary_failure_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "attempts"
            command = f'printf "x\\n" >> "$1"; exit 7'
            result = self.run_wrapper(
                "--timeout", "2s",
                "--attempts", "3",
                "--",
                "bash", "-c", command, "bash", str(marker),
            )
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "x\n")
            self.assertIn("not retrying", result.stderr)

    def test_timeout_restarts_only_up_to_configured_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "attempts"
            command = f'printf "x\\n" >> "$1"; sleep 5'
            result = self.run_wrapper(
                "--timeout", "0.1s",
                "--kill-after", "0.1s",
                "--attempts", "2",
                "--retry-delay", "0.01s",
                "--",
                "bash", "-c", command, "bash", str(marker),
            )
            self.assertIn(result.returncode, {124, 137}, result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "x\nx\n")
            self.assertIn("attempt 2/2", result.stderr)
            self.assertIn("all 2 attempt(s)", result.stderr)


if __name__ == "__main__":
    unittest.main()
