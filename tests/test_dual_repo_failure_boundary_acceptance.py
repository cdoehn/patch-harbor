from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_DOC = TARGET_ROOT / "docs" / "dual-repo-failure-boundary-acceptance.md"
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


def _write_failing_smoke_patch(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# patchharbor-meta: {\"type\":\"patch\",\"id\":\"PATCHHARBOR.FAILURE16B2\",\"title\":\"Failure 16b2\",\"commit\":\"Failure 16b2\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"roadmap\",\"status\":\"active\",\"file\":\"docs/dual-repo-failure-boundary-acceptance.md\",\"label\":\"Milestone 16 failure boundary\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"milestone\",\"status\":\"active\",\"file\":\"docs/dual-repo-failure-boundary-acceptance.md\",\"label\":\"Failure boundary\"}",
                "# patchharbor-meta: {\"type\":\"display\",\"context\":0}",
                "set -euo pipefail",
                ': "${PATCHHARBOR_FAILURE_MARKER:?missing PATCHHARBOR_FAILURE_MARKER}"',
                'printf "failure-boundary-marker\\n" > "$PATCHHARBOR_FAILURE_MARKER"',
                "exit 23",
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


class PatchHarborDualRepoFailureBoundaryAcceptanceTests(unittest.TestCase):
    def test_failure_boundary_doc_exists_and_records_16b2_contract(self) -> None:
        self.assertTrue(ACCEPTANCE_DOC.is_file())
        text = ACCEPTANCE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16b2 – Dual repo failure boundary acceptance",
            "PATCHHARBOR.16b1 accepted the normal dual-repo boundary",
            "Failure-boundary contract",
            "run-script --no-execute",
            "PATCHHARBOR.16b3",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_failure_boundary_links_from_boundary_and_public_readiness_docs(self) -> None:
        for path in [BOUNDARY_DOC, PUBLIC_READINESS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16b2 applied", text)
                self.assertIn("docs/dual-repo-failure-boundary-acceptance.md", text)
                self.assertIn("tests/test_dual_repo_failure_boundary_acceptance.py", text)

    def test_failing_runner_smoke_is_contained_in_temporary_repo_and_keeps_source_status(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo = temp_root / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            patch = temp_root / "failing_patch.sh"
            marker = repo / "failure-marker.txt"
            _write_failing_smoke_patch(patch)

            result = _run_patchharbor(
                "run-script",
                str(patch),
                "--workdir",
                str(repo),
                "--env",
                f"PATCHHARBOR_FAILURE_MARKER={marker}",
                "--timeout-seconds",
                "10",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(marker.is_file())
            self.assertEqual(marker.read_text(encoding="utf-8"), "failure-boundary-marker\n")

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_no_execute_runner_smoke_preflights_failing_body_without_marker_write(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo = temp_root / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            patch = temp_root / "failing_patch.sh"
            marker = repo / "failure-marker-no-execute.txt"
            _write_failing_smoke_patch(patch)

            result = _run_patchharbor(
                "run-script",
                str(patch),
                "--no-execute",
                "--workdir",
                str(repo),
                "--env",
                f"PATCHHARBOR_FAILURE_MARKER={marker}",
                "--timeout-seconds",
                "10",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(marker.exists())

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_failure_boundary_non_goals_keep_runtime_and_source_out_of_scope(self) -> None:
        text = ACCEPTANCE_DOC.read_text(encoding="utf-8")
        expected = [
            "PATCHHARBOR.16b2 does not",
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

    def test_failure_boundary_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                ACCEPTANCE_DOC,
                BOUNDARY_DOC,
                PUBLIC_READINESS,
                Path(__file__).resolve(),
            ]
        )
        forbidden = [
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
