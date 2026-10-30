"""Exact CLI grammar, organized by command family."""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

from patchharbor import __version__
from patchharbor.api import DEFAULT_TIMEOUT_SECONDS


class _ExactArgumentParser(argparse.ArgumentParser):
    """Disable argparse option abbreviations for the public CLI contract."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)
        self.add_argument(
            "-v", "--verbose", action="store_true", default=argparse.SUPPRESS,
            help="show all internal file, ZIP, Git and state activity",
        )
        self.add_argument(
            "--plain", action="store_true", default=argparse.SUPPRESS,
            help="use undecorated, colorless output",
        )
        self.add_argument(
            "--no-color", action="store_true", default=argparse.SUPPRESS,
            help="disable console colors",
        )


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return seconds


def _explicit_package_path(value: str) -> Path:
    if not value or "\x00" in value:
        raise argparse.ArgumentTypeError("must be a nonempty file path without NUL")
    return Path(value)


class _PackModeAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        name, separator, digits = value.rpartition('=')
        if not separator or not name or re.fullmatch(r'[0-7]{4}', digits) is None:
            raise argparse.ArgumentError(self, 'expected PACKAGE_PATH=0644 with four octal digits')
        modes = dict(getattr(namespace, self.dest, None) or {})
        if name in modes:
            raise argparse.ArgumentError(self, 'duplicate mode path')
        modes[name] = int(digits, 8)
        setattr(namespace, self.dest, modes)


def _pack_entrypoint(value: str) -> str:
    if not value:
        raise argparse.ArgumentTypeError('entrypoint must be nonempty')
    return value


def _add_configuration_commands(commands) -> None:
    configure_parser = commands.add_parser(
        "configure",
        help="configure the current repository settings",
        description=(
            "Manage this repository's .patchharbor/config.json for Result "
            "Bundles, automatic Apply discovery, and the optional watcher."
        ),
        epilog=(
            "Exchange directories may be shared by repositories but must not overlap "
            "any registered repository."
        ),
    )
    configure_commands = configure_parser.add_subparsers(
        dest="configure_command",
        required=True,
        metavar="COMMAND",
    )
    exchange_directory_parser = configure_commands.add_parser(
        "exchange-directory",
        help="set the repository exchange directory",
        description=(
            "Create when necessary, validate, physically resolve, and "
            "persist the repository Exchange directory in config.json."
        ),
    )
    exchange_directory_parser.add_argument(
        "directory",
        type=Path,
        metavar="DIRECTORY",
        help="exchange directory to persist in config.json",
    )
    suffix_parser = configure_commands.add_parser(
        "bundle-suffix",
        help="set or clear the persistent filename suffix for all bundles",
        description=(
            "Append SUFFIX literally after .zip for every new bundle, including "
            "automatic Result Bundles and explicit output directories. "
            "ZIP contents and package validation are unchanged. "
            "Example: patchharbor configure bundle-suffix .txt"
        ),
    )
    suffix_parser.add_argument(
        "suffix", nargs="?", metavar="SUFFIX",
        help="portable filename suffix, for example .txt (maximum 32 characters)",
    )
    suffix_parser.add_argument(
        "--clear", action="store_true", help="disable the configured bundle suffix",
    )
    archive_parser = configure_commands.add_parser(
        "archive-dir",
        help="set or disable the Exchange archive subfolder",
        description=(
            "Archive only provably obsolete bundles inside the Exchange directory. "
            "Default: PatchHarbor-Archive. NAME must be one portable folder name, "
            "not a path. An empty name or --clear disables archival. A leading "
            "dot is accepted unchanged; no Windows Hidden attribute is set."
        ),
    )
    archive_parser.add_argument("name", nargs="?", metavar="NAME")
    archive_parser.add_argument("--clear", action="store_true", help="disable automatic archival")
    configure_commands.add_parser(
        "show",
        help="show the current repository configuration",
        description=(
            "Show the active repository config.json path and the canonical "
            "Exchange directory, bundle suffix and archive directory (empty when disabled)."
        ),
    )



def _add_repository_commands(commands) -> None:
    register_parser = commands.add_parser(
        "register",
        help="register one local Git repository instance",
        description=(
            "Register one physical Git repository instance with a committed "
            "HEAD. Registration writes .patchharbor/id and a central UUID "
            "mapping; it does not configure the Exchange directory."
        ),
        epilog=(
            "The success summary shortens technical identifiers. Run "
            "'patchharbor context --json' in the registered repository, or "
            "'patchharbor context --json REPOSITORY' elsewhere, for complete "
            "values. Register itself has no --json option."
        ),
    )
    register_parser.add_argument(
        "repository",
        type=Path,
        nargs="?",
        metavar="REPOSITORY",
        help="Git repository; defaults to the current directory",
    )

    register_parser.add_argument(
        "--new-id",
        action="store_true",
        help="replace this local instance identity with a new UUID",
    )

    registry_parser = commands.add_parser(
        "registry",
        help="inspect registered local repository instances",
    )
    registry_commands = registry_parser.add_subparsers(
        dest="registry_command",
        required=True,
        metavar="COMMAND",
    )
    registry_list_parser = registry_commands.add_parser(
        "list",
        help="list registered local repository instances",
        description=(
            "List registrations as human-readable rows with shortened "
            "repository UUIDs."
        ),
        epilog=(
            "Use --json for full repository UUIDs. Short display prefixes are "
            "not accepted by unregister; use the full UUID or repository path."
        ),
    )
    registry_list_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help=(
            "write full repository UUIDs in the versioned machine-readable "
            "result"
        ),
    )

    unregister_parser = commands.add_parser(
        "unregister",
        help="remove one central repository registration",
    )
    unregister_parser.add_argument(
        "repository_or_repo_id",
        metavar="REPOSITORY_OR_REPO_ID",
        help="registered repository path or canonical repository UUID",
    )

    context_parser = commands.add_parser(
        "context",
        help="describe one registered repository state",
        description=(
            "Print a human-readable repository summary without creating a "
            "Result Bundle. Long technical identifiers are shortened to six "
            "characters plus an ellipsis."
        ),
        epilog=(
            "Use --json for the complete repository UUID, base commit, and "
            "state fingerprint. The shortened display is not machine input."
        ),
    )
    context_parser.add_argument(
        "repository",
        type=Path,
        nargs="?",
        metavar="REPOSITORY",
        help="registered Git repository; defaults to the current directory",
    )
    context_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help=(
            "write complete identifiers in the versioned machine-readable "
            "result"
        ),
    )



def _add_package_commands(commands) -> None:
    for name in ("inspect", "validate"):
        package_parser = commands.add_parser(
            name,
            help=f"{name} one explicit patch package without executing it",
            description=(
                "Check an explicit package without execution or publication. "
                "Validate can additionally compare one explicit repository or Result reference."
            ),
        )
        package_parser.add_argument("patch_zip", type=_explicit_package_path, metavar="PATCH_ZIP")
        package_parser.add_argument("--json", action="store_true", dest="json_output",
                                    help="write the version-2 machine-readable result")
        if name == "validate":
            binding = package_parser.add_mutually_exclusive_group()
            binding.add_argument("--repository", type=_explicit_package_path, metavar="REPOSITORY")
            binding.add_argument("--reference-bundle", type=_explicit_package_path, metavar="RESULT_ZIP")

    pack_parser = commands.add_parser(
        'pack', help='create and validate a patch package from explicit prepared contents',
        description='Pack selected contents against a Result reference; never execute or replace a target.',
    )
    pack_parser.add_argument('content_directory', type=_explicit_package_path, metavar='CONTENT_DIRECTORY')
    pack_parser.add_argument('--reference-bundle', required=True, type=_explicit_package_path, metavar='RESULT_ZIP')
    pack_parser.add_argument('--entrypoint', required=True, type=_pack_entrypoint, metavar='PACKAGE_PATH')
    pack_target = pack_parser.add_mutually_exclusive_group(required=True)
    pack_target.add_argument('--output', type=_explicit_package_path, metavar='PATCH_ZIP')
    pack_target.add_argument('--output-dir', type=_explicit_package_path, metavar='DIRECTORY')
    pack_parser.add_argument('--mode', action=_PackModeAction, dest='modes', metavar='PACKAGE_PATH=0644')
    pack_parser.add_argument('--json', action='store_true', dest='json_output')



def _add_bundle_apply_commands(commands) -> None:
    bundle_parser = commands.add_parser(
        "bundle",
        help="create a Result Bundle for one registered repository",
        description=(
            "Capture the complete current repository state: the base commit, "
            "staged and unstaged changes, and non-ignored untracked regular "
            "files."
        ),
        epilog=(
            "Without --output-dir, publish in the configured Exchange "
            "directory. The configured bundle suffix is appended after .zip. "
            "Result Bundles include fresh chat handoff and local environment data, contain no Git history and may contain secrets."
        ),
    )
    bundle_parser.add_argument(
        "repository",
        type=Path,
        nargs="?",
        metavar="REPOSITORY",
        help="registered Git repository; defaults to the current directory",
    )
    bundle_parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="DIRECTORY",
        help="override the configured Exchange directory for this bundle",
    )
    bundle_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="write the versioned machine-readable result",
    )

    apply_parser = commands.add_parser(
        "apply",
        help="validate or apply one repository-bound patch package",
        description=(
            "Validate or apply one repository-bound ZIP patch package. A "
            "manual call without PATCH_ZIP resolves the current working "
            "directory to one registered repository, then selects its newest "
            "eligible Exchange package by mtime_ns. Equal timestamps use a "
            "deterministic normalized-filename tie-breaker."
        ),
        epilog=(
            "An explicit PATCH_ZIP bypasses parameterless discovery and may "
            "resolve another registered repository through its repo_id. The "
            "watcher's internal automatic mode remains global across all "
            "registered repositories. An explicit --output-dir overrides only "
            "the Result Bundle destination. Apply attempts a Result Bundle "
            "after repository resolution; earlier writes are not globally "
            "rolled back after a later failure."
        ),
    )
    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the patch package without changing a repository",
    )
    apply_parser.add_argument(
        "--timeout",
        type=_positive_seconds,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "stop the entrypoint after this many seconds "
            f"(default: {DEFAULT_TIMEOUT_SECONDS:g})"
        ),
    )
    apply_parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="DIRECTORY",
        help=(
            "override the configured Exchange directory for an attempted "
            "Result Bundle"
        ),
    )


    apply_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="write the versioned machine-readable result",
    )
    apply_parser.add_argument(
        "--automatic",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    apply_parser.add_argument(
        "patch_zip",
        type=Path,
        nargs="?",
        metavar="PATCH_ZIP",
        help=(
            "explicit ZIP package containing a root patch.json; when omitted, "
            "use the current registered repository and its newest eligible "
            "Exchange package"
        ),
    )



def _add_fs_commands(commands) -> None:
    fs_parser = commands.add_parser(
        "fs",
        help="run from the file system or standard input",
    )
    fs_commands = fs_parser.add_subparsers(
        dest="fs_command",
        required=True,
        metavar="COMMAND",
    )

    run_parser = fs_commands.add_parser(
        "run",
        help=(
            "run scripts from a file, ZIP PatchBundle, directory, "
            "or standard input"
        ),
        description=(
            "Run generated Bash or PowerShell scripts from a file, "
            "ZIP PatchBundle, directory, or standard input."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Script contract:\n"
            "  A script must contain a line exactly equal to "
            "'# PATCHHARBOR'.\n"
            "\n"
            "Input behavior:\n"
            "  PATH may name one script, a ZIP PatchBundle, or a "
            "directory.\n"
            "  Omit PATH to read one script or ZIP PatchBundle from "
            "standard input.\n"
            "  ZIP PatchBundles may contain ordered scripts and byte-exact "
            "payload files.\n"
            "\n"
            "Execution behavior:\n"
            "  Scripts run in the current working directory.\n"
            "  Oversized inputs and unsafe ZIP PatchBundles are rejected "
            "before any script starts."
        ),
    )
    run_parser.add_argument(
        "--timeout",
        type=_positive_seconds,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "stop the script after this many seconds "
            f"(default: {DEFAULT_TIMEOUT_SECONDS:g})"
        ),
    )


    run_parser.add_argument(
        "--log",
        action="store_true",
        help=(
            "write complete merged script output and run metadata "
            "to a temporary log"
        ),
    )
    run_parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        metavar="PATH",
        help=(
            "script or ZIP PatchBundle file, or directory; "
            "omit to read standard input"
        ),
    )



def _build_parser() -> argparse.ArgumentParser:
    parser = _ExactArgumentParser(
        prog="patchharbor",
        description=(
            "Register local Git repository instances, exchange complete "
            "Result Bundles, and validate or apply repository-bound ZIP "
            "patch packages. The separate 'fs run' command executes "
            "explicit scripts and ZIP PatchBundles."
        ),
        epilog=(
            "Configure the repository Exchange directory once with "
            "'patchharbor configure exchange-directory DIRECTORY'. "
            "Use 'patchharbor COMMAND --help' for one command's complete "
            "options."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the installed PatchHarbor version and exit",
    )
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="COMMAND",
    )

    _add_configuration_commands(commands)
    _add_repository_commands(commands)
    _add_package_commands(commands)
    _add_bundle_apply_commands(commands)
    _add_fs_commands(commands)
    return parser
