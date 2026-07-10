from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _old_private_patterns() -> list[str]:
    old_user = "chris" + "tian"
    old_person = old_user + "." + "doehn"
    old_mail_host = "g" + "mail" + "." + "com"
    return [
        old_person + "@" + old_mail_host,
        old_person,
        "/home/" + old_user,
        old_user + "@",
        old_user,
        "Chris" + "tian",
        "Example" + "Laptop",
        "Blade" + "-" + "15",
        "Pro" + "jekte",
        "Wer" + "nau",
        chr(34) + "/home/" + chr(34) + " + " + chr(34) + old_user + chr(34),
        chr(34) + old_user + chr(34) + " + " + chr(34) + "@" + chr(34),
        chr(34) + old_person + chr(34) + " + " + chr(34) + "@" + chr(34) + " + " + chr(34) + old_mail_host + chr(34),
        chr(34) + "Think" + chr(34) + " + " + chr(34) + "Pad" + chr(34),
        chr(34) + "Blade-" + chr(34) + " + " + chr(34) + "15" + chr(34),
        chr(34) + "~/" + chr(34) + " + " + chr(34) + "Pro" + "jekte" + chr(34),
    ]


def _tracked_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    files: list[Path] = []
    for line in result.stdout.splitlines():
        path = ROOT / line
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\\x00" in data[:4096]:
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        files.append(path)
    return files


class PrivateDataCleanupTests(unittest.TestCase):
    def test_project_name_is_expected(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "patchharbor"', text)

    def test_tracked_text_files_do_not_contain_old_private_patterns(self) -> None:
        offenders: list[tuple[str, str]] = []
        for path in _tracked_text_files():
            text = path.read_text(encoding="utf-8")
            for pattern in _old_private_patterns():
                if pattern in text:
                    offenders.append((str(path.relative_to(ROOT)), pattern))
        self.assertEqual(offenders, [])

    def test_privacy_cleanup_document_exists(self) -> None:
        doc = ROOT / "docs" / "private-data-cleanup.md"
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8")
        self.assertIn("Private data cleanup", text)
        self.assertIn("PATCHHARBOR.PRIVACY1", text)


if __name__ == "__main__":
    unittest.main()
