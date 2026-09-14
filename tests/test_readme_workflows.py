from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from patchharbor.cli import _build_parser as build_core_parser
from patchharbor_watcher.cli import _build_parser as build_watcher_parser
from tests.platform_support import PROJECT_ROOT


README_PATH = PROJECT_ROOT / "README.md"
CHAT_PATH = PROJECT_ROOT / "CHAT_INSTRUCTIONS.md"


def _readme() -> str:
    return README_PATH.read_text(encoding="utf-8")


def _compact(value: str) -> str:
    return " ".join(value.split())


def _fenced_blocks(document: str, language: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            rf"^```{re.escape(language)}\n(.*?)\n```$",
            document,
            flags=re.MULTILINE | re.DOTALL,
        )
    )


def _subparser(
    parser: argparse.ArgumentParser,
    *commands: str,
) -> argparse.ArgumentParser:
    current = parser
    for command in commands:
        action = next(
            candidate
            for candidate in current._actions
            if isinstance(candidate, argparse._SubParsersAction)
        )
        current = action.choices[command]
    return current


def test_readme_is_canonical_and_documents_the_closed_global_configuration() -> None:
    raw = README_PATH.read_bytes()
    document = raw.decode("utf-8")

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert all(line.rstrip() == line for line in document.splitlines())
    assert "one shared Exchange directory per operating-system user" in document
    assert "not configured per repository" in document
    assert "`patchharbor register` never asks for it" in document
    assert "${XDG_CONFIG_HOME:-$HOME/.config}/patchharbor/config.json" in document
    assert "%APPDATA%\\PatchHarbor\\config.json" in document
    assert "patchharbor configure exchange-directory ~/Downloads" in document
    assert "patchharbor configure show" in document
    assert "`watcher.json` and\n`paths.json` are not configuration sources" in document

    json_blocks = _fenced_blocks(document, "json")
    assert len(json_blocks) == 1
    assert json.loads(json_blocks[0]) == {
        "exchange_directory": "/absolute/path/to/exchange",
        "format_version": 3,
        "bundle_suffix": "",
        "archive_directory": "PatchHarbor-Archive",
    }


def test_readme_covers_all_repository_and_chat_initialization_cases() -> None:
    document = _readme()

    for heading in (
        "### New Git repository",
        "### Existing unregistered repository",
        "### Already registered repository",
        "## Initialize a new development chat",
    ):
        assert heading in document

    assert "A repository must be a local Git repository with a committed `HEAD`" in (
        document
    )
    assert "patchharbor register" in document
    assert "patchharbor register --new-id" in document
    assert "patchharbor registry list" in document
    assert "patchharbor unregister REPOSITORY_OR_REPO_ID" in document
    assert "the version-matching `CHAT_INSTRUCTIONS.md`" in document
    assert "the newest Result Bundle produced by `patchharbor bundle`" in document
    assert "These paths are informational" in document
    assert "no extra command or separate" in document
    assert "`logs/run.json`" in document
    assert "`logs/execution.log`" in document
    assert "including the context printed by `patchharbor register`" in document
    assert "do not copy it into `patch.json`" in document
    assert "`register` itself deliberately has no `--json` option" in document
    assert "For standard chat initialization, upload that Result" in document
    assert "`context.json` is the authoritative source" in document
    assert "patchharbor registry list --json" in document
    assert "six-character display prefix is never a valid repository selector" in (
        _compact(document)
    )

    chat = CHAT_PATH.read_text(encoding="utf-8")
    assert "Lokale Repository- und Exchange-Pfade" in chat
    assert "niemals als Repository-Zuordnung" in chat
    assert "local repository path or Exchange path" in document


def test_readme_covers_manual_overrides_termux_and_watcher_workflows() -> None:
    document = _readme()
    compact = _compact(document)

    for command in (
        "patchharbor apply --dry-run",
        "patchharbor apply\n",
        "patchharbor bundle --output-dir /path/to/results /path/to/repository",
        "patchharbor apply --dry-run --output-dir /path/to/results /path/to/patch.zip",
        "patchharbor apply --output-dir /path/to/results /path/to/patch.zip",
        "patchharbor fs run /path/to/script-or-bundle",
        "patchharbor-watcher --install-systemd-user-unit",
        "systemctl --user enable --now patchharbor-watcher.service",
        "journalctl --user -u patchharbor-watcher.service",
    ):
        assert command in document

    assert (
        "first resolves the current working directory to exactly one registered "
        "Git repository" in compact
    )
    assert "Calls from any subdirectory of that repository" in compact
    assert "without scanning for a fallback package" in compact
    assert "greatest nanosecond modification time (`mtime_ns`) wins" in compact
    assert (
        "Equal `mtime_ns` values use the lexicographically first filename after "
        "Unicode NFC normalization" in compact
    )
    assert "newer foreign, state-mismatched, or replay-ineligible package" in compact
    assert "Its selection scope remains global" in compact
    assert "does not use the watcher's current working directory" in compact
    assert "resolve another registered repository" in compact
    assert "default timeout for one script or repository entrypoint is 10,800 seconds" in (
        compact
    )
    assert "Use manual mode on Termux" in compact
    assert "No Termux-specific watcher support is claimed" in compact
    assert "patchharbor-watcher --configure" not in document
    assert "input-directory argument" in document
    assert "with complete obsolescence proofs" in compact
    assert "nothing is deleted" in compact
    assert "unsupported safe rename leaves the source in place" in compact
    assert "A failed package can be retried by another deliberate manual" in compact
    assert "is not immediately repeated by the watcher" in compact
    assert "<Repository>_Patch_<HHMMSS>_<MMDD>_<ID6>.zip" in document
    assert "<Repository>_Result_<HHMMSS>_<MMDD>_<ID6>.zip" in document
    assert "first six characters plus `…`" in document


def test_core_help_explains_the_documented_exchange_workflow() -> None:
    parser = build_core_parser()
    top_help = _compact(parser.format_help())
    configure_help = _compact(_subparser(parser, "configure").format_help())
    exchange_help = _compact(
        _subparser(parser, "configure", "exchange-directory").format_help()
    )
    show_help = _compact(_subparser(parser, "configure", "show").format_help())
    register_help = _compact(_subparser(parser, "register").format_help())
    registry_list_help = _compact(
        _subparser(parser, "registry", "list").format_help()
    )
    context_help = _compact(_subparser(parser, "context").format_help())
    bundle_help = _compact(_subparser(parser, "bundle").format_help())
    apply_help = _compact(_subparser(parser, "apply").format_help())

    assert "Register local Git repository instances" in top_help
    assert "patchharbor configure exchange-directory DIRECTORY" in top_help
    assert ".patchharbor/config.json" in configure_help
    assert "may be shared by repositories" in configure_help
    assert "persist the repository Exchange directory in config.json" in exchange_help
    assert "active repository config.json path" in show_help
    assert "committed HEAD" in register_help
    assert "does not configure the Exchange directory" in register_help
    assert "success summary shortens technical identifiers" in register_help
    assert "patchharbor context --json REPOSITORY" in register_help
    assert "Register itself has no --json option" in register_help
    assert "human-readable rows with shortened repository UUIDs" in (
        registry_list_help
    )
    assert "Use --json for full repository UUIDs" in registry_list_help
    assert "not accepted by unregister" in registry_list_help
    assert "human-readable repository summary" in context_help
    assert "six characters plus an ellipsis" in context_help
    assert "Use --json for the complete repository UUID" in context_help
    assert "shortened display is not machine input" in context_help
    assert "staged and unstaged changes" in bundle_help
    assert "non-ignored untracked regular files" in bundle_help
    assert "Without --output-dir, publish in the configured Exchange directory" in (
        bundle_help
    )
    assert "contain no Git history and may contain secrets" in bundle_help
    assert (
        "manual call without PATCH_ZIP resolves the current working directory "
        "to one registered repository" in apply_help
    )
    assert "selects its newest eligible Exchange package by mtime_ns" in apply_help
    assert "deterministic normalized-filename tie-breaker" in apply_help
    assert "An explicit PATCH_ZIP bypasses parameterless discovery" in apply_help
    assert "may resolve another registered repository through its repo_id" in apply_help
    assert "watcher's internal automatic mode remains global" in apply_help
    assert "earlier writes are not globally rolled back" in apply_help
    assert "default: 10800" in apply_help


def test_watcher_help_explains_repository_config_systemd_and_termux_boundary() -> None:
    help_text = _compact(build_watcher_parser().format_help())

    assert "parameterless automatic Apply mode" in help_text
    assert "Exchange directories of all registered repositories" in help_text
    assert "patchharbor configure exchange-directory DIRECTORY" in help_text
    assert "installer does not enable or start it" in help_text
    assert "manual 'patchharbor apply' on Termux/Android" in help_text
    assert "--configure" not in help_text
    assert "INPUT_DIRECTORY" not in help_text


def test_archive_documentation_matches_fail_safe_configuration_and_scope() -> None:
    document = _readme()
    compact = _compact(document)
    for command in (
        "patchharbor configure archive-dir PatchHarbor-Archive",
        "patchharbor configure archive-dir .PatchHarbor-Archive",
        "patchharbor configure archive-dir --clear",
        'patchharbor configure archive-dir ""',
    ):
        assert command in document
    for rule in (
        "a timestamp, filename or mere successful exit is never enough",
        "legacy records without a completion receipt",
        "the watcher remains global",
        "dry-run never archives",
        "the archive is never scanned recursively",
        "no copy-and-delete fallback",
        "does not set a hidden attribute",
    ):
        assert rule in compact.lower()


def test_spec_has_no_obsolete_blanket_archive_prohibition() -> None:
    specification = (PROJECT_ROOT / "spec" / "SPECIFICATION.md").read_text(encoding="utf-8")
    for obsolete in (
        "keine Dateien im Exchange-Ordner archivieren",
        "Er verschiebt, löscht, archiviert oder sortiert dort keine Datei",
        "PatchHarbor verschiebt, löscht, archiviert oder sortiert Exchange-Dateien nicht",
    ):
        assert obsolete not in specification
    assert "Nachweisbasierte Exchange-Archivierung" in specification
