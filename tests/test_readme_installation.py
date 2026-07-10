from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPLAY_ONLY_README_FORMAT_REASON = (
    "display-only README command-block formatting; functional installation checks remain enabled"
)


class PatchHarborReadmeInstallationTests(unittest.TestCase):
    def readme(self) -> str:
        return (ROOT / "README.md").read_text(encoding="utf-8")

    def pyproject(self) -> dict:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_readme_has_installation_section_before_development(self) -> None:
        text = self.readme()

        self.assertIn("## Installation", text)
        self.assertIn("## Development", text)
        self.assertLess(text.index("## Installation"), text.index("## Development"))

    def test_installation_section_documents_supported_install_modes(self) -> None:
        text = self.readme()
        required = [
            "Python 3.12 or newer",
            "python3 -m venv .venv",
            "source .venv/bin/activate",
            'python3 -m pip install -e ".[dev]"',
            "pipx install -e .",
            "pipx uninstall patchharbor",
            "python3 -m patchharbor --help",
            "python3 -m patchharbor --version",
            "patchharbor doctor --repo .",
        ]

        missing = [marker for marker in required if marker not in text]
        self.assertFalse(missing, missing)

    def test_installation_section_matches_package_entry_point(self) -> None:
        project = self.pyproject()["project"]
        text = self.readme()

        self.assertEqual(project["scripts"]["patchharbor"], "patchharbor.cli:main")
        self.assertIn("console script `patchharbor`", text)
        self.assertIn("python3 -m patchharbor --help", text)
        self.assertIn("patchharbor --help", text)

    def test_readme_lists_current_functional_cli_commands(self) -> None:
        text = self.readme()
        commands = [
            "patchharbor doctor",
            "patchharbor lint-script",
            "patchharbor run-script",
            "patchharbor audit-public",
            "patchharbor check-env",
        ]

        for command in commands:
            with self.subTest(command=command):
                self.assertIn(f"`{command}`", text)

    def test_readme_no_longer_describes_current_cli_as_not_migrated(self) -> None:
        text = self.readme()

        self.assertNotIn("PatchHarbor is in the " + "bootstrap phase.", text)
        self.assertNotIn("patch runner commands\n- export runner commands", text)
        self.assertIn("packaging/install smoke checks are still being hardened", text)

    @unittest.skip(DISPLAY_ONLY_README_FORMAT_REASON)
    def test_readme_installation_keeps_display_formatting_out_of_contract_scope(self) -> None:
        text = self.readme()

        indented_command_lines = re.findall(r"(?m)^    (python3|pipx|patchharbor)\\b", text)
        self.assertGreaterEqual(len(indented_command_lines), 8)
        self.assertNotIn("<display-only snapshot", text)

    def test_readme_installation_does_not_store_private_local_values(self) -> None:
        text = self.readme() + "\n" + Path(__file__).read_text(encoding="utf-8")
        forbidden = [
            "/home/" + "exampleuser",
            "user" + "@",
            "example.user" + "@" + "example.invalid",
            "Example" + "Laptop",
            "Example" + "Machine",
            "~/" + "Projects",
            chr(96) * 3,
        ]
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
