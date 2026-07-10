from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_DOC = TARGET_ROOT / "docs" / "dual-repo-recovery-acceptance.md"
FAILURE_DOC = TARGET_ROOT / "docs" / "dual-repo-failure-boundary-acceptance.md"
BOUNDARY_DOC = TARGET_ROOT / "docs" / "dual-repo-boundary-acceptance.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"


def _pyproject_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']\s*$', text, re.M)
    if not match:
        return ""
    return match.group(1)


def _source_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_source = os.environ.get("PATCHHARBOR_SOURCE_REPO")
    if env_source:
        candidates.append(Path(env_source).expanduser())
    candidates.append(TARGET_ROOT.parent / "repo_dossier")
    candidates.append(TARGET_ROOT.parent / "repodossier")
    return candidates


def _discover_source_repo() -> Path:
    for candidate in _source_candidates():
        path = candidate.resolve()
        if (
            (path / "pyproject.toml").is_file()
            and (path / "src" / "repodossier").is_dir()
            and _pyproject_name(path / "pyproject.toml") == "repodossier"
        ):
            return path
    raise AssertionError("RepoDossier source checkout was not discoverable")


def _source_status(source: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def _write_failing_patch(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# patchharbor-meta: {\"type\":\"patch\",\"id\":\"PATCHHARBOR.RECOVERY16B3.FAIL\",\"title\":\"Recovery fail 16b3\",\"commit\":\"Recovery fail 16b3\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"roadmap\",\"status\":\"active\",\"file\":\"docs/dual-repo-recovery-acceptance.md\",\"label\":\"Milestone 16 recovery\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"milestone\",\"status\":\"active\",\"file\":\"docs/dual-repo-recovery-acceptance.md\",\"label\":\"Recovery failure\"}",
                "# patchharbor-meta: {\"type\":\"display\",\"context\":0}",
                "set -euo pipefail",
                ': "${PATCHHARBOR_FAILURE_MARKER:?missing PATCHHARBOR_FAILURE_MARKER}"',
                'printf "recovery-failure-marker\\n" > "$PATCHHARBOR_FAILURE_MARKER"',
                "exit 23",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_success_patch(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# patchharbor-meta: {\"type\":\"patch\",\"id\":\"PATCHHARBOR.RECOVERY16B3.SUCCESS\",\"title\":\"Recovery success 16b3\",\"commit\":\"Recovery success 16b3\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"roadmap\",\"status\":\"active\",\"file\":\"docs/dual-repo-recovery-acceptance.md\",\"label\":\"Milestone 16 recovery\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"milestone\",\"status\":\"active\",\"file\":\"docs/dual-repo-recovery-acceptance.md\",\"label\":\"Recovery success\"}",
                "# patchharbor-meta: {\"type\":\"display\",\"context\":0}",
                "set -euo pipefail",
                ': "${PATCHHARBOR_RECOVERY_MARKER:?missing PATCHHARBOR_RECOVERY_MARKER}"',
                'printf "recovery-success-marker\\n" > "$PATCHHARBOR_RECOVERY_MARKER"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_patchharbor(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    effective_env = os.environ.copy()
    effective_env["PYTHONPATH"] = f"{TARGET_ROOT / 'src'}{os.pathsep}{effective_env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    if env:
        effective_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "patchharbor", *args],
        cwd=TARGET_ROOT,
        env=effective_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PatchHarborDualRepoRecoveryAcceptanceTests(unittest.TestCase):
    def test_recovery_doc_exists_and_records_16b3_contract(self) -> None:
        self.assertTrue(RECOVERY_DOC.is_file())
        text = RECOVERY_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16b3 – Dual repo recovery acceptance",
            "PATCHHARBOR.16b1 accepted the normal dual-repo boundary",
            "PATCHHARBOR.16b2 accepted the failure boundary",
            "Recovery contract",
            "PATCHHARBOR.16c1",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_recovery_links_from_failure_boundary_and_public_docs(self) -> None:
        for path in [FAILURE_DOC, BOUNDARY_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16b3 applied", text)
                self.assertIn("docs/dual-repo-recovery-acceptance.md", text)
                self.assertIn("tests/test_dual_repo_recovery_acceptance.py", text)

    def test_recovery_after_failing_runner_is_contained_and_keeps_source_status(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo = temp_root / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            fail_patch = temp_root / "failing_recovery_patch.sh"
            success_patch = temp_root / "successful_recovery_patch.sh"
            failure_marker = repo / "failure-marker.txt"
            recovery_marker = repo / "recovery-marker.txt"
            _write_failing_patch(fail_patch)
            _write_success_patch(success_patch)

            failed = _run_patchharbor(
                "run-script",
                str(fail_patch),
                "--workdir",
                str(repo),
                "--env",
                f"PATCHHARBOR_FAILURE_MARKER={failure_marker}",
                "--timeout-seconds",
                "10",
            )
            self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
            self.assertTrue(failure_marker.is_file())
            self.assertEqual(failure_marker.read_text(encoding="utf-8"), "recovery-failure-marker\n")

            recovered = _run_patchharbor(
                "run-script",
                str(success_patch),
                "--workdir",
                str(repo),
                "--env",
                f"PATCHHARBOR_RECOVERY_MARKER={recovery_marker}",
                "--timeout-seconds",
                "10",
            )
            self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)
            self.assertTrue(recovery_marker.is_file())
            self.assertEqual(recovery_marker.read_text(encoding="utf-8"), "recovery-success-marker\n")

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_no_execute_recovery_preflight_does_not_write_markers(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo = temp_root / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            success_patch = temp_root / "successful_recovery_patch.sh"
            recovery_marker = repo / "recovery-marker-no-execute.txt"
            _write_success_patch(success_patch)

            result = _run_patchharbor(
                "run-script",
                str(success_patch),
                "--no-execute",
                "--workdir",
                str(repo),
                "--env",
                f"PATCHHARBOR_RECOVERY_MARKER={recovery_marker}",
                "--timeout-seconds",
                "10",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(recovery_marker.exists())

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_recovery_non_goals_keep_runtime_and_source_out_of_scope(self) -> None:
        text = RECOVERY_DOC.read_text(encoding="utf-8")
        expected = [
            "PATCHHARBOR.16b3 does not",
            "change PatchHarbor runtime code",
            "change RepoDossier runtime code",
            "change source wrappers",
            "change aliases",
            "edit shell rc files",
            "apply downloaded patches",
            "write real RepoDossier exports",
            "change version numbers",
        ]
        for marker in expected:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_recovery_acceptance_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                RECOVERY_DOC,
                FAILURE_DOC,
                BOUNDARY_DOC,
                PUBLIC_READINESS,
                Path(__file__).resolve(),
            ]
        )
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "Example" + "Machine",
            "~/" + "Projects",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
