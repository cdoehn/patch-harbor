from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
SMOKE_DOC = TARGET_ROOT / "docs" / "dual-repo-patch-runner-smoke.md"
DISCOVERY_DOC = TARGET_ROOT / "docs" / "dual-repo-discovery-smoke.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"
PUBLIC_API = TARGET_ROOT / "docs" / "public-api-inventory.md"


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


def _write_smoke_patch(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "# patchharbor-meta: {\"type\":\"patch\",\"id\":\"PATCHHARBOR.SMOKE16A2\",\"title\":\"Smoke 16a2\",\"commit\":\"Smoke 16a2\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"roadmap\",\"status\":\"active\",\"file\":\"docs/dual-repo-patch-runner-smoke.md\",\"label\":\"Milestone 16 smoke\"}",
                "# patchharbor-meta: {\"type\":\"progress\",\"panel\":\"milestone\",\"status\":\"active\",\"file\":\"docs/dual-repo-patch-runner-smoke.md\",\"label\":\"Patch runner smoke\"}",
                "# patchharbor-meta: {\"type\":\"display\",\"context\":0}",
                "set -euo pipefail",
                ': "${PATCHHARBOR_SMOKE_FILE:?missing PATCHHARBOR_SMOKE_FILE}"',
                'printf "patchharbor-runner-smoke\\n" > "$PATCHHARBOR_SMOKE_FILE"',
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


class PatchHarborDualRepoPatchRunnerSmokeTests(unittest.TestCase):
    def test_smoke_doc_exists_and_records_16a2_contract(self) -> None:
        self.assertTrue(SMOKE_DOC.is_file())
        text = SMOKE_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16a2 – Dual repo patch runner smoke",
            "PATCHHARBOR.16a1 proved dual-repo discovery",
            "temporary git repository",
            "patchharbor-meta",
            "python -m patchharbor run-script",
            "PATCHHARBOR.16a3",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_target_and_source_are_discoverable_before_runner_smoke(self) -> None:
        self.assertEqual(_pyproject_name(TARGET_ROOT / "pyproject.toml"), "patchharbor")
        self.assertTrue((TARGET_ROOT / "src" / "patchharbor").is_dir())

        source = _discover_source_repo()
        self.assertEqual(_pyproject_name(source / "pyproject.toml"), "repodossier")
        self.assertTrue((source / "scripts" / "dev" / "run_latest_download_patch.sh").is_file())
        self.assertTrue((source / "scripts" / "dev" / "r.sh").is_file())

    def test_patchharbor_run_script_executes_smoke_patch_without_touching_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo = temp_root / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            patch = temp_root / "smoke_patch.sh"
            marker = repo / "runner-smoke.txt"
            _write_smoke_patch(patch)

            result = _run_patchharbor(
                "run-script",
                str(patch),
                "--workdir",
                str(repo),
                "--env",
                f"PATCHHARBOR_SMOKE_FILE={marker}",
                "--timeout-seconds",
                "10",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("PatchHarbor run-script", result.stdout)
            self.assertIn("runner status: passed", result.stdout)
            self.assertIn("phase execute: passed", result.stdout)
            self.assertEqual(marker.read_text(encoding="utf-8"), "patchharbor-runner-smoke\n")

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_patchharbor_run_script_no_execute_preflights_without_marker_write(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo = temp_root / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            patch = temp_root / "smoke_patch.sh"
            marker = repo / "runner-smoke-no-execute.txt"
            _write_smoke_patch(patch)

            result = _run_patchharbor(
                "run-script",
                str(patch),
                "--no-execute",
                "--workdir",
                str(repo),
                "--env",
                f"PATCHHARBOR_SMOKE_FILE={marker}",
                "--timeout-seconds",
                "10",
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("PatchHarbor run-script", result.stdout)
            self.assertIn("runner status: passed", result.stdout)
            self.assertIn("phase execute: skipped", result.stdout)
            self.assertFalse(marker.exists())

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_patch_runner_smoke(self) -> None:
        for path in [DISCOVERY_DOC, PUBLIC_READINESS, PUBLIC_API]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16a2 applied", text)
                self.assertIn("docs/dual-repo-patch-runner-smoke.md", text)
                self.assertIn("tests/test_dual_repo_patch_runner_smoke.py", text)

    def test_patch_runner_smoke_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SMOKE_DOC, DISCOVERY_DOC, PUBLIC_READINESS, PUBLIC_API, Path(__file__).resolve()]
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
