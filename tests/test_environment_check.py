from __future__ import annotations

from pathlib import Path
import unittest

from patchharbor.environment_check import (
    EnvironmentCheck,
    EnvironmentCheckError,
    EnvironmentCheckResult,
    EnvironmentCheckSpec,
    environment_check_from_mapping,
    environment_check_result_from_mappings,
    environment_check_spec_from_mapping,
)


class PatchHarborEnvironmentCheckModelTests(unittest.TestCase):
    def test_check_validates_status_and_serializes_generic_contract(self) -> None:
        check = EnvironmentCheck(
            name="python",
            ok=True,
            detail="Python 3.12",
            hint="install Python",
            required=True,
            category="runtime",
            metadata={"source": "sys.executable"},
        )

        self.assertEqual(check.status, "ok")
        self.assertFalse(check.failed)
        self.assertFalse(check.blocking)
        self.assertEqual(
            check.to_mapping(),
            {
                "name": "python",
                "ok": True,
                "detail": "Python 3.12",
                "hint": "install Python",
                "required": True,
                "category": "runtime",
                "metadata": {"source": "sys.executable"},
            },
        )
        self.assertEqual(environment_check_from_mapping(check.to_mapping()), check)

    def test_required_and_optional_failures_have_different_status(self) -> None:
        required = EnvironmentCheck("git user.name", False, "not configured", required=True)
        optional = EnvironmentCheck("pipx", False, "not found", required=False)

        self.assertEqual(required.status, "fail")
        self.assertTrue(required.blocking)
        self.assertEqual(optional.status, "warn")
        self.assertFalse(optional.blocking)

    def test_result_summarizes_required_and_optional_failures(self) -> None:
        result = EnvironmentCheckResult(
            (
                EnvironmentCheck("python", True, "ok", category="runtime"),
                EnvironmentCheck("git user.email", False, "missing", category="git"),
                EnvironmentCheck("pipx", False, "missing", required=False, category="tooling"),
            ),
            metadata={"repo": "sample"},
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.failed)
        self.assertEqual(result.total_count, 3)
        self.assertEqual(result.ok_count, 1)
        self.assertEqual(result.failed_count, 2)
        self.assertEqual(result.required_failed_count, 1)
        self.assertEqual(result.optional_failed_count, 1)
        self.assertEqual([check.name for check in result.blocking_checks()], ["git user.email"])
        self.assertEqual(set(result.checks_by_category()), {"runtime", "git", "tooling"})
        self.assertEqual(
            result.summary(),
            {
                "ok": False,
                "total": 3,
                "passed": 1,
                "failed": 2,
                "required_failed": 1,
                "optional_failed": 1,
            },
        )
        self.assertEqual(result.to_mapping()["metadata"], {"repo": "sample"})

    def test_result_accepts_check_mappings(self) -> None:
        result = environment_check_result_from_mappings(
            [
                {"name": "repo root", "ok": True, "detail": "/work/project"},
                {"name": "optional tool", "ok": False, "detail": "missing", "required": False},
            ],
            metadata={"mode": "doctor"},
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(result.optional_failed_count, 1)
        self.assertEqual(result.required_failed_count, 0)
        self.assertEqual(result.metadata, {"mode": "doctor"})

    def test_spec_validates_command_file_and_custom_checks(self) -> None:
        command = EnvironmentCheckSpec(
            name="pytest",
            check_type="command",
            command=("python", "-m", "pytest", "--version"),
            hint="install test dependencies",
            category="tooling",
        )
        file_spec = EnvironmentCheckSpec(name="workflow rules", check_type="file", path="scripts/rules.json")
        custom = EnvironmentCheckSpec(name="repo root", check_type="custom", required=True)

        self.assertEqual(command.command, ("python", "-m", "pytest", "--version"))
        self.assertEqual(command.to_mapping()["command"], ["python", "-m", "pytest", "--version"])
        self.assertEqual(environment_check_spec_from_mapping(command.to_mapping()), command)
        self.assertEqual(file_spec.path, "scripts/rules.json")
        self.assertEqual(custom.check_type, "custom")

    def test_invalid_checks_are_rejected(self) -> None:
        with self.assertRaisesRegex(EnvironmentCheckError, "name"):
            EnvironmentCheck("", True, "ok")
        with self.assertRaisesRegex(EnvironmentCheckError, "ok"):
            EnvironmentCheck("python", "yes", "ok")  # type: ignore[arg-type]
        with self.assertRaisesRegex(EnvironmentCheckError, "detail"):
            EnvironmentCheck("python", True, "")
        with self.assertRaisesRegex(EnvironmentCheckError, "required"):
            EnvironmentCheck("tool", False, "missing", required="yes")  # type: ignore[arg-type]
        with self.assertRaisesRegex(EnvironmentCheckError, "metadata values"):
            EnvironmentCheck("tool", True, "ok", metadata={"bad": 1})  # type: ignore[dict-item]
        with self.assertRaisesRegex(EnvironmentCheckError, "must be a mapping"):
            EnvironmentCheck.from_mapping("bad")  # type: ignore[arg-type]

    def test_invalid_specs_are_rejected(self) -> None:
        with self.assertRaisesRegex(EnvironmentCheckError, "type must be one of"):
            EnvironmentCheckSpec("tool", "unknown")
        with self.assertRaisesRegex(EnvironmentCheckError, "requires a command"):
            EnvironmentCheckSpec("tool", "command")
        with self.assertRaisesRegex(EnvironmentCheckError, "requires a path"):
            EnvironmentCheckSpec("rules", "file")
        with self.assertRaisesRegex(EnvironmentCheckError, "command must be an iterable"):
            EnvironmentCheckSpec("tool", "command", command="python")  # type: ignore[arg-type]
        with self.assertRaisesRegex(EnvironmentCheckError, "spec must be a mapping"):
            EnvironmentCheckSpec.from_mapping("bad")  # type: ignore[arg-type]

    def test_model_files_do_not_store_source_specific_defaults(self) -> None:
        checked = [
            Path(__file__).resolve().parents[1] / "src/patchharbor/environment_check.py",
            Path(__file__).resolve(),
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        forbidden = [
            "Repo" + "Dossier",
            "repo" + "dossier",
            "check_dev_" + "environment.py",
            "repo" + "dossier",
            "c " + "runner",
            "r " + "runner",
            "market_" + "research",
            "/home/" + "christian",
            "christian" + "@",
            "christian.doehn" + "@" + "gmail.com",
            "Think" + "Pad",
            "Blade-" + "15",
            "~/" + "Projekte",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
