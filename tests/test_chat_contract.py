from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from patchharbor.cli import _build_parser as build_core_parser
from patchharbor.parser import REQUIRED_MARKER
from patchharbor.patch_manifest import (
    PATCH_FORMAT_VERSION,
    PATCH_MANIFEST_NAME,
    PATCH_MARKER,
)
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.state_fingerprint import FINGERPRINT_ALGORITHM
from patchharbor_watcher.cli import _build_parser as build_watcher_parser
from tests.platform_support import PROJECT_ROOT


CHAT_PATH = PROJECT_ROOT / "CHAT_INSTRUCTIONS.md"
SPEC_PATH = PROJECT_ROOT / "spec" / "SPECIFICATION.md"
README_PATH = PROJECT_ROOT / "README.md"
PLAN_PATH = PROJECT_ROOT / "planning" / "1.1.1" / "commit-plan.md"
PATCH_READY = "🟩🟩 PATCH BEREIT 🟩🟩"
WARNING_HEADER = "🟨🟨 PATCHHARBOR WARNUNG 🟨🟨\nCODE: <WARNING_CODE>"
STOP_HEADER = "🟥🟥 PATCHHARBOR STOP 🟥🟥\nCODE: <STOP_CODE>"
EXPECTED_WARNING_CODES = {
    "NON_BLOCKING_ASSUMPTION",
    "PLAN_SPEC_MINOR_DEVIATION",
    "REDUCED_TEST_SCOPE",
}
EXPECTED_STOP_CODES = {
    "PATCH_CREATION_FAILED",
    "PLAN_AMBIGUOUS",
    "PLAN_NOT_FOUND",
    "PLAN_POSITION_UNKNOWN",
    "PLAN_SPEC_CONFLICT",
    "REPOSITORY_STATE_INCOMPLETE",
    "REQUIREMENT_AMBIGUOUS",
    "SPEC_AMBIGUOUS",
    "UNSAFE_OR_IMPOSSIBLE",
}
EXPECTED_HEADINGS = [
    "## 1. Deine Aufgabe und die Sicherheitsgrenze",
    "## 2. Erforderliche Eingaben",
    "## 3. Result Bundle vollständig auswerten",
    "## 4. Zielversion, Commit-Plan und Spezifikation finden",
    "## 5. Spezifikation, Plan, Code und Auftrag abgleichen",
    "## 6. Commit-Art und Zähler",
    "## 7. Genau ein sicheres Patch-Paket erzeugen",
    "## 8. Tests, Commit und lokale Ausführung",
    "## 9. Result Bundle nach Apply auswerten",
    "## 10. Standardisierte Warning- und STOP-Ausgaben",
    "## 11. Verbindliche schmale Patch-Bereit-UI",
    "## 12. Verantwortungsgrenzen im Gesamtsystem",
]
EXPECTED_COMMAND_BLOCK = "\n".join(
    (
        "patchharbor configure exchange-directory VERZEICHNIS",
        "patchharbor configure bundle-suffix .txt",
        "patchharbor configure bundle-suffix --clear",
        "patchharbor configure archive-dir PatchHarbor-Archive",
        "patchharbor configure archive-dir --clear",
        "patchharbor configure show",
        "patchharbor register [REPOSITORY]",
        "patchharbor registry list",
        "patchharbor unregister REPOSITORY_OR_REPO_ID",
        "patchharbor context [REPOSITORY]",
        "patchharbor bundle [REPOSITORY]",
        "patchharbor apply [PATCH_ZIP]",
        "patchharbor apply --dry-run [PATCH_ZIP]",
        "patchharbor fs run QUELLE",
        "patchharbor-watcher",
    )
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fenced_blocks(document: str, language: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            rf"^```{re.escape(language)}\n(.*?)\n```$",
            document,
            flags=re.MULTILINE | re.DOTALL,
        )
    )


def _section(document: str, heading: str, next_heading: str | None) -> str:
    start = document.index(heading)
    end = len(document) if next_heading is None else document.index(
        next_heading,
        start + len(heading),
    )
    return document[start:end]


def _normalise_space(value: str) -> str:
    return " ".join(value.split())


def test_chat_contract_is_canonical_versioned_and_compact() -> None:
    raw = CHAT_PATH.read_bytes()
    document = raw.decode("utf-8")

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert len(raw) <= 28 * 1024
    assert all(line.rstrip() == line for line in document.splitlines())
    assert (PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8") == (
        "/CHAT_INSTRUCTIONS.md text eol=lf\n"
        "/README.md text eol=lf\n"
    )
    assert document.startswith(
        "# PatchHarbor 1.2.0 – Chat-Initialisierung\n\n"
        "**Vertragsversion:** 1.2.0<br>\n"
        f"**Patch-Paketmarker:** `{PATCH_MARKER}`<br>\n"
        f"**Patch-Paketformat:** `{PATCH_FORMAT_VERSION}`<br>\n"
        "**Result-Bundle-Marker:** `patch-harbor-result-bundle`<br>\n"
        f"**Fingerprint-Algorithmus:** `{FINGERPRINT_ALGORITHM}`<br>\n"
        f"**Entrypoint-Pflichtmarker:** `{REQUIRED_MARKER}`\n"
    )
    assert re.findall(r"^## .+$", document, flags=re.MULTILINE) == (
        EXPECTED_HEADINGS
    )
    assert "1.1.0" not in document
    assert _text(PLAN_PATH).count("`CHAT_INSTRUCTIONS.md`") >= 1


def test_chat_manifest_and_resource_contract_match_runtime_constants() -> None:
    document = _text(CHAT_PATH)
    json_blocks = _fenced_blocks(document, "json")
    assert len(json_blocks) == 1
    manifest = json.loads(json_blocks[0])

    assert list(manifest) == [
        "marker",
        "format_version",
        "repo_id",
        "base_commit",
        "state_fingerprint",
        "fingerprint_algorithm",
        "entrypoint",
    ]
    assert manifest["marker"] == PATCH_MARKER
    assert manifest["format_version"] == PATCH_FORMAT_VERSION
    assert manifest["fingerprint_algorithm"] == FINGERPRINT_ALGORITHM
    assert manifest["entrypoint"] == "run.sh"
    assert manifest["entrypoint"] != PATCH_MANIFEST_NAME
    assert f"exakt diese sieben Felder" in document
    assert f"Skriptmarker `{REQUIRED_MARKER}`" in document

    policy = DEFAULT_RESOURCE_POLICY
    mib = 1024 * 1024
    formatted_entries = f"{policy.max_zip_entries:,}".replace(",", ".")
    expected_limits = (
        f"Warning ab {policy.warning_bytes // mib} MiB pro Inhalt, höchstens "
        f"{policy.max_input_artifact_bytes // mib} MiB pro Eingabeartefakt "
        f"oder ZIP-Eintrag, höchstens {policy.max_zip_total_bytes // mib} MiB "
        f"unkomprimierte ZIP-Gesamtdaten und höchstens "
        f"{formatted_entries} ZIP-Einträge"
    )
    assert expected_limits in _normalise_space(document)

    result_marker = "patch-harbor-result-bundle"
    for relative_path in (
        "src/patchharbor/exchange.py",
        "src/patchharbor/result_bundle.py",
    ):
        assert f'"{result_marker}"' in _text(PROJECT_ROOT / relative_path)


def test_chat_public_commands_are_real_and_use_correct_optionality() -> None:
    document = _text(CHAT_PATH)
    text_blocks = _fenced_blocks(document, "text")
    assert text_blocks[0] == EXPECTED_COMMAND_BLOCK

    parser = build_core_parser()
    valid_arguments = (
        ["configure", "exchange-directory", "exchange"],
        ["configure", "show"],
        ["configure", "archive-dir", "PatchHarbor-Archive"],
        ["configure", "archive-dir", "--clear"],
        ["register"],
        ["registry", "list"],
        ["unregister", "repository-or-id"],
        ["context"],
        ["bundle"],
        ["apply"],
        ["apply", "--dry-run"],
        ["fs", "run", "source"],
    )
    for arguments in valid_arguments:
        parser.parse_args(arguments)
    build_watcher_parser().parse_args([])

    with pytest.raises(SystemExit):
        parser.parse_args(["unregister"])

    for invented in (
        "patchharbor chat",
        "patchharbor commit",
        "patchharbor plan",
        "patchharbor rollback",
        "patchharbor test",
    ):
        assert invented not in text_blocks[0]


def test_chat_contract_distinguishes_manual_explicit_and_watcher_selection() -> None:
    document = _normalise_space(_text(CHAT_PATH))

    assert (
        "Ein manueller parameterloser `apply` löst zuerst das aktuelle "
        "Arbeitsverzeichnis einschließlich Repository-Unterverzeichnissen auf"
        in document
    )
    assert "ausschließlich Pakete für genau diese registrierte Repository-Instanz" in (
        document
    )
    assert "Unicode-NFC-normalisierte Dateiname deterministisch" in document
    assert "Der Watcher bleibt dagegen global für alle registrierten Repositorys" in (
        document
    )
    assert "Ein expliziter `PATCH_ZIP` darf weiterhin über seine `repo_id`" in document


def test_chat_and_spec_share_commit_warning_stop_and_ui_contracts() -> None:
    chat = _text(CHAT_PATH)
    specification = _text(SPEC_PATH)
    warning_section = _section(
        chat,
        EXPECTED_HEADINGS[9],
        EXPECTED_HEADINGS[10],
    )
    spec_warning_section = _section(
        specification,
        "### 26.7 Standardisierte Warning- und Stop-Ausgaben",
        "### 26.8 Verbindliche schmale Patch-Bereit-UI",
    )

    chat_text_blocks = _fenced_blocks(warning_section, "text")
    spec_text_blocks = _fenced_blocks(spec_warning_section, "text")
    assert chat_text_blocks == (WARNING_HEADER, STOP_HEADER)
    assert spec_text_blocks == chat_text_blocks

    warning_part, stop_part = warning_section.split(
        "Eine blockierende Situation beginnt exakt mit:",
        maxsplit=1,
    )
    warning_codes = set(
        re.findall(r"^- `([A-Z0-9_]+)`", warning_part, flags=re.MULTILINE)
    )
    stop_codes = set(
        re.findall(r"^- `([A-Z0-9_]+)`", stop_part, flags=re.MULTILINE)
    )
    assert warning_codes == EXPECTED_WARNING_CODES
    assert stop_codes == EXPECTED_STOP_CODES
    for code in warning_codes | stop_codes:
        assert f"`{code}`" in spec_warning_section

    commit_section = _section(chat, EXPECTED_HEADINGS[5], EXPECTED_HEADINGS[6])
    assert re.findall(r"^### `([^`]+)`$", commit_section, flags=re.MULTILINE) == [
        "PLAN",
        "FIX",
        "OFF-PLAN",
    ]
    for fragment in (
        "<PLAN-ID>-FIX<n>",
        "Ein Fix erhöht weder Gesamtzahl noch erreichte Position",
        "-- / <Gesamtzahl>",
        "-- / --",
    ):
        assert fragment in commit_section
        assert fragment in specification
    assert "Verändere den Plan-Zähler nicht" in commit_section
    assert "Ein Off-Plan-Commit verändert den Plan-Zähler nicht" in specification

    chat_ui = _fenced_blocks(
        _section(chat, EXPECTED_HEADINGS[10], EXPECTED_HEADINGS[11]),
        "text",
    )
    spec_ui = _fenced_blocks(
        _section(
            specification,
            "### 26.8 Verbindliche schmale Patch-Bereit-UI",
            "### 26.9 Auswertung nach lokalem Apply",
        ),
        "text",
    )
    assert len(chat_ui) == len(spec_ui) == 1
    assert chat_ui[0] == spec_ui[0]


def test_patch_ready_ui_is_narrow_ordered_and_download_safe() -> None:
    document = _text(CHAT_PATH)
    ui_section = _section(
        document,
        EXPECTED_HEADINGS[10],
        EXPECTED_HEADINGS[11],
    )
    (ui,) = _fenced_blocks(ui_section, "text")
    lines = ui.splitlines()

    assert lines[0] == PATCH_READY
    assert lines[-1] == PATCH_READY
    assert ui.count(PATCH_READY) == 2
    assert max(len(line) for line in lines) <= 60
    assert lines[2:5] == ["🟩 PLAN", "🟩 1.a.W", "🟩 1 / 12"]

    labels = ["Commit:", "Plan:", "Spec:", "Änderungen:", "Tests:", "Noch offen:"]
    label_positions = [lines.index(label) for label in labels]
    assert label_positions == sorted(label_positions)

    changes_start = lines.index("Änderungen:") + 1
    tests_start = lines.index("Tests:")
    changes = [
        line
        for line in lines[changes_start:tests_start]
        if line.startswith("• ")
    ]
    assert 5 <= len(changes) <= 10

    tests_end = lines.index("Noch offen:")
    planned_tests = [
        line
        for line in lines[tests_start + 1 : tests_end]
        if line.startswith("• ")
    ]
    assert planned_tests
    assert not re.search(
        r"Tests?.*(erfolgreich|grün)",
        ui,
        flags=re.IGNORECASE,
    )

    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", ui)
    assert links == [
        ("Patch herunterladen", "sandbox:/pfad/zum/patch.zip")
    ]
    assert "Es gibt genau einen Download-Link zu genau einer Patch-Datei." in (
        ui_section
    )
    assert (
        "`PATCH BEREIT` erscheint erst, wenn die verlinkte Datei tatsächlich "
        "existiert."
    ) in ui_section


def test_chat_contract_carries_retry_filename_and_identifier_presentation() -> None:
    chat = _text(CHAT_PATH)
    specification = _text(SPEC_PATH)
    readme = _text(README_PATH)
    compact_chat = _normalise_space(chat)

    for document in (chat, specification, readme):
        assert "<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip" in document
        assert "<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip" in document
    assert "höchsten `mtime_ns`" in compact_chat
    assert "fehlgeschlagenen Patch darf der manuelle Aufruf bewusst" in compact_chat
    assert "fehlgeschlagene Pakete nicht erneut pollt" in compact_chat
    assert "sechs Zeichen plus `…`" in specification
    assert "vollständigen JSON-Werte" in chat
    assert "`register`-, `context`- oder `registry list`-Kurzansicht" in chat
    assert "patchharbor context --json" in chat
    assert "Rekonstruiere niemals vollständige" in chat
    assert "keine kopierbare Maschinenrepräsentation" in specification
    assert "Kontextblock zum Kopieren in den Chat" not in specification
    assert "--retry-failed" not in build_core_parser().format_help()


def test_result_bundle_and_responsibility_boundaries_match_spec_and_readme() -> None:
    chat = _text(CHAT_PATH)
    specification = _text(SPEC_PATH)
    readme = _text(README_PATH)

    bundle_section = _section(chat, EXPECTED_HEADINGS[2], EXPECTED_HEADINGS[3])
    for required in (
        "`manifest.json`",
        "`context.json`",
        "`base/`",
        "`changes/staged.patch`",
        "`changes/unstaged.patch`",
        "`untracked/`",
        "`logs/run.json`",
        "`logs/execution.log`",
    ):
        assert required in bundle_section
        assert required in specification

    for shared_boundary in (
        "PatchHarbor ist keine Sandbox",
        "keine globale automatische Rückabwicklung",
        "keine Git-Historie",
    ):
        assert shared_boundary in chat

    assert "PatchHarbor is not a sandbox" in readme
    assert "not automatically rolled back" in readme
    assert "without Git history" in readme
    assert "PatchHarbor does not run target-project tests or create Git commits" in (
        readme
    )
    assert "Es verwaltet außerdem keine fachlichen Tests, Git-Commits" in chat
    assert "Lokale Repository- und Exchange-Pfade" in chat
    assert "Pfad und Exchange-Pfad dienen nur Kommandozeilenbeispielen" in specification


def test_chat_contract_remains_documentation_not_runtime_orchestration() -> None:
    forbidden_runtime_terms = (
        "CHAT_INSTRUCTIONS.md",
        "PATCHHARBOR WARNUNG",
        "PATCHHARBOR STOP",
        PATCH_READY,
        "PLAN_SPEC_MINOR_DEVIATION",
    )
    for package_root in (
        PROJECT_ROOT / "src" / "patchharbor",
        PROJECT_ROOT / "src" / "patchharbor_watcher",
    ):
        for path in package_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for term in forbidden_runtime_terms:
                if term == "CHAT_INSTRUCTIONS.md" and path.name == "bundle_handoff.py":
                    continue  # Passive output file roles, not workflow execution.
                assert term not in source, f"{term!r} leaked into {path}"


def test_archive_contract_has_no_blanket_prohibition_conflicting_with_maintenance() -> None:
    document = _text(CHAT_PATH)
    assert "PatchHarbor selbst verschiebt, löscht, archiviert, sortiert oder benennt keine" not in document
    assert "Es löscht keine\nBundles" in document
    assert "State-/Git-Prüfung vor jedem Verschieben" in document
