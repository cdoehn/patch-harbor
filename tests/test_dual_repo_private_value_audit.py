from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = TARGET_ROOT / "docs" / "dual-repo-private-value-audit.md"
PUBLIC_READINESS = TARGET_ROOT / "docs" / "public-readiness-acceptance.md"
BOUNDARY_DOC = TARGET_ROOT / "docs" / "dual-repo-boundary-acceptance.md"
FAILURE_DOC = TARGET_ROOT / "docs" / "dual-repo-failure-boundary-acceptance.md"
RECOVERY_DOC = TARGET_ROOT / "docs" / "dual-repo-recovery-acceptance.md"
EXPORT_DOC = TARGET_ROOT / "docs" / "dual-repo-export-smoke.md"

TARGET_AUDIT_PATHS = [
    "docs/dual-repo-discovery-smoke.md",
    "docs/dual-repo-patch-runner-smoke.md",
    "docs/dual-repo-source-wrapper-smoke.md",
    "docs/dual-repo-export-smoke.md",
    "docs/dual-repo-private-value-audit.md",
    "docs/dual-repo-boundary-acceptance.md",
    "docs/dual-repo-failure-boundary-acceptance.md",
    "docs/dual-repo-recovery-acceptance.md",
    "docs/public-readiness-acceptance.md",
    "tests/test_dual_repo_private_value_audit.py",
]


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


def _private_patterns() -> list[tuple[str, str]]:
    return [
        ("local-home", "/home/" + "christian"),
        ("local-email", "christian.doehn" + "@" + "gmail.com"),
        ("local-user-at", "christian" + "@"),
        ("thinkpad", "Think" + "Pad"),
        ("blade", "Blade-" + "15"),
        ("local-project-shortcut", "~/" + "Projekte"),
    ]


def _run_patchharbor_audit(repo: Path, targets: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{TARGET_ROOT / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)

    args = [sys.executable, "-m", "patchharbor", "audit-public", "--repo", str(repo)]
    for name, value in _private_patterns():
        args.extend(["--pattern", f"{name}={value}"])
    for target in targets:
        args.extend(["--target", target])

    return subprocess.run(
        args,
        cwd=TARGET_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class PatchHarborDualRepoPrivateValueAuditTests(unittest.TestCase):
    def test_private_value_audit_doc_exists_and_records_plan_correct_16a4_contract(self) -> None:
        self.assertTrue(AUDIT_DOC.is_file())
        text = AUDIT_DOC.read_text(encoding="utf-8")
        required = [
            "PATCHHARBOR.16a4 – Dual repo private value audit",
            "PATCHHARBOR.16a4-fix2",
            "Dual Repo Private Value Audit",
            "Add dual repository private value audit",
            "PATCHHARBOR.16b1-fix1 – Migration Rollback Notes",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_source_plan_defines_16a4_private_value_audit_and_commit(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        plan = (source / "planning" / "milestones_migration.md").read_text(encoding="utf-8")
        idx = plan.find("PATCHHARBOR.16a4")
        self.assertGreaterEqual(idx, 0)
        window = plan[idx : idx + 500]
        self.assertIn("Dual Repo Private Value Audit", window)
        self.assertIn("Add dual repository private value audit", window)

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_related_docs_link_to_plan_correct_private_value_audit(self) -> None:
        for path in [PUBLIC_READINESS, BOUNDARY_DOC, FAILURE_DOC, RECOVERY_DOC, EXPORT_DOC]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("PATCHHARBOR.16a4-fix2 applied", text)
                self.assertIn("docs/dual-repo-private-value-audit.md", text)
                self.assertIn("tests/test_dual_repo_private_value_audit.py", text)

    def test_patchharbor_audit_public_reports_no_private_values_in_milestone_16_target_docs(self) -> None:
        for relative in TARGET_AUDIT_PATHS:
            with self.subTest(relative=relative):
                self.assertTrue((TARGET_ROOT / relative).is_file())

        result = _run_patchharbor_audit(TARGET_ROOT, TARGET_AUDIT_PATHS)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("status: ok", result.stdout)
        self.assertIn("findings: 0", result.stdout)

    def test_private_value_audit_is_read_only_for_source(self) -> None:
        source = _discover_source_repo()
        before = _source_status(source)

        for relative in [
            "planning/milestones_migration.md",
            "scripts/dev/run_latest_download_patch.sh",
            "scripts/dev/run_patchharbor_patch.sh",
            "scripts/dev/r.sh",
            "scripts/dev/run_repodossier_exports.sh",
        ]:
            with self.subTest(relative=relative):
                path = source / relative
                self.assertTrue(path.exists())
                if path.is_file():
                    _ = path.read_text(encoding="utf-8")

        after = _source_status(source)
        self.assertEqual(after, before)

    def test_private_value_audit_does_not_store_private_local_values_or_fences(self) -> None:
        text = "\n".join((TARGET_ROOT / relative).read_text(encoding="utf-8") for relative in TARGET_AUDIT_PATHS)
        for _name, value in _private_patterns():
            with self.subTest(value=value):
                self.assertNotIn(value, text)
        self.assertNotIn(chr(96) * 3, text)


if __name__ == "__main__":
    unittest.main()
