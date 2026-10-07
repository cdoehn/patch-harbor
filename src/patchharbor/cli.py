"""PatchHarbor command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, nullcontext
import math
import re
from pathlib import Path
import sys
from typing import Any, BinaryIO, TextIO

from patchharbor import __version__
import patchharbor.api as api
from patchharbor.api import (
    DEFAULT_TIMEOUT_SECONDS, PatchHarborError, ResultBundleStatus, RunReport,
)
from patchharbor.context_output import context_json_result, write_context_block
from patchharbor.errors import format_tool_message
from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.identifier_presentation import shorten_identifier
from patchharbor.inspection_output import inspection_json_result, validation_json_result, pack_json_result
from patchharbor.json_document import serialize_json_document
from patchharbor.platform.errors import describe_os_error
from patchharbor.presentation import (
    PresentedCompletion,
    PresentedStatus,
    SanitizedTextStream,
    StreamingConsole,
    select_directory_candidate,
)
from patchharbor.run_log import temporary_run_log
from patchharbor.run_report import (
    physical_absolute_path_text,
    sanitize_structured_text,
)


def _configure_utf8_standard_stream(stream: TextIO, *, errors: str) -> None:
    """Use deterministic UTF-8 for real process standard streams when possible."""
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors=errors)
    except (OSError, ValueError):
        # Embedded or already detached streams may not be reconfigurable.
        pass


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

    return parser


def _write_configuration(
    configuration_path: Path,
    exchange_directory: Path | None,
    *,
    bundle_suffix: str,
    archive_directory: str,
    stdout: TextIO,
) -> None:
    print(f"configuration_path: {configuration_path}", file=stdout)
    print(f"exchange_directory: {exchange_directory if exchange_directory is not None else 'not configured'}", file=stdout)
    print(f"bundle_suffix: {bundle_suffix}", file=stdout)
    print(f"archive_directory: {archive_directory}", file=stdout)


def _configure_exchange_directory_command(
    directory: Path,
    *,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            configuration = api.configure_exchange_directory(
                directory, observer=_progress_observer(console),
            )
            configuration_path = configuration.path
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exit_code_for_error(exc))

    _write_configuration(
        configuration_path,
        configuration.exchange_directory,
        bundle_suffix=configuration.bundle_suffix,
        archive_directory=configuration.archive_directory,
        stdout=stdout,
    )
    return 0


def _configure_bundle_suffix_command(
    suffix: str,
    *,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            configuration = api.configure_bundle_suffix(suffix, observer=_progress_observer(console))
            configuration_path = configuration.path
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exit_code_for_error(exc))
    _write_configuration(
        configuration_path,
        configuration.exchange_directory,
        bundle_suffix=configuration.bundle_suffix,
        archive_directory=configuration.archive_directory,
        stdout=stdout,
    )
    return 0


def _configure_archive_directory_command(
    name: str, *, stdout: TextIO, stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            configuration = api.configure_archive_directory(name, observer=_progress_observer(console))
            configuration_path = configuration.path
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exit_code_for_error(exc))
    _write_configuration(
        configuration_path, configuration.exchange_directory,
        bundle_suffix=configuration.bundle_suffix,
        archive_directory=configuration.archive_directory, stdout=stdout,
    )
    return 0


def _configure_show_command(
    *,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            configuration = api.configuration(observer=_progress_observer(console))
            configuration_path = configuration.path
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exit_code_for_error(exc))

    _write_configuration(
        configuration_path,
        configuration.exchange_directory,
        bundle_suffix=configuration.bundle_suffix,
        archive_directory=configuration.archive_directory,
        stdout=stdout,
    )
    return 0


def _register_command(
    path: Path | None,
    *,
    new_id: bool,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            context = api.register(
                path or Path.cwd(), new_id=new_id, observer=_progress_observer(console),
            )
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exit_code_for_error(exc))

    write_context_block(context, stdout)
    return 0


def _write_json_document(document: dict[str, object], stream: TextIO) -> None:
    stream.write(serialize_json_document(document))


def _json_envelope(
    command: str,
    *,
    result: dict[str, object] | None,
    error: PatchHarborError | None,
    process_exit_code: int,
    output_version: int = 1,
) -> dict[str, object]:
    structured_error: dict[str, object] | None = None
    if error is not None:
        report = error.run_report if isinstance(error.run_report, RunReport) else None
        emergency_path = (
            error.emergency_diagnostics_path
            if report is None
            else report.result_bundle.emergency_diagnostics_path
        )
        structured_error = {
            "kind": error.error_kind.value,
            "message": sanitize_structured_text(str(error)),
            "patchharbor_error_code": int(exit_code_for_error(error)),
            "emergency_diagnostics_path": physical_absolute_path_text(
                emergency_path
            ),
        }
    return {
        "output_version": output_version,
        "command": command,
        "success": process_exit_code == 0,
        "result": result,
        "error": structured_error,
        "process_exit_code": process_exit_code,
    }


def _package_command(
    command: str, path: Path, *, json_output: bool, stdout: TextIO, stderr: TextIO,
    verbose: bool = False, force_plain: bool = False, no_color: bool = False,
    repository: Path | None = None, reference_bundle: Path | None = None,
) -> int:
    report: api.PatchValidationResult | None = None
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=not json_output,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            if command == "inspect":
                info = api.inspect_patch(path, observer=_progress_observer(console))
            else:
                options = {}
                if repository is not None:
                    options["repository"] = repository
                if reference_bundle is not None:
                    options["reference_bundle"] = reference_bundle
                report = api.validate_patch(path, **options, observer=_progress_observer(console))
                info = report.inspection
    except PatchHarborError as exc:
        code = int(exit_code_for_error(exc))
        if json_output:
            _write_json_document(_json_envelope(command, result=None, error=exc,
                                                process_exit_code=code, output_version=2), stdout)
        else:
            print(format_tool_message(str(exc)), file=stderr)
        return code
    if json_output:
        result = inspection_json_result(info) if report is None else validation_json_result(report)
        _write_json_document(_json_envelope(command, result=result, error=None,
                                            process_exit_code=0, output_version=2), stdout)
    else:
        print(f"package_sha256: {info.package_sha256}", file=stdout)
        print(f"package_size: {info.package_size}", file=stdout)
        print(f"entrypoint: {info.entrypoint}", file=stdout)
        print(f"entries: {len(info.entries)}", file=stdout)
        print(f"scope: {'package' if report is None else report.scope.value}", file=stdout)
        if report is not None:
            print(f"binding_matches: {report.binding_matches}", file=stdout)
            print("not_checked: " + ", ".join(report.not_checked), file=stdout)
        for warning in info.warnings:
            print(format_tool_message(warning), file=stderr)
    return 0


def _pack_output_diagnostic(stderr: TextIO, error: BaseException, packed: api.PatchPackResult | None) -> None:
    detail = 'pack output could not be delivered: ' + str(error)
    if packed is not None:
        detail += f'; already published: {packed.path}; sha256: {packed.package_sha256}'
    try:
        print(format_tool_message(detail), file=stderr)
        stderr.flush()
    except (OSError, UnicodeError, KeyboardInterrupt):
        pass


def _pack_command(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    # Keep this operation's output boundary separate from all existing commands.
    packed = None
    error = None
    try:
        packed = api.pack_patch(
            args.content_directory, reference_bundle=args.reference_bundle,
            entrypoint=args.entrypoint, output=args.output,
            output_directory=args.output_dir, modes=args.modes, observer=None,
        )
    except PatchHarborError as exc:
        error = exc
    except KeyboardInterrupt as exc:
        error = PatchHarborError('pack interrupted before a confirmed result', api.FailureReason.INTERRUPTED)
        error.__cause__ = exc
    code = 0 if error is None else int(exit_code_for_error(error))
    try:
        if args.json_output:
            _write_json_document(_json_envelope(
                'pack', result=None if packed is None else pack_json_result(packed),
                error=error, process_exit_code=code, output_version=2,
            ), stdout)
        elif packed is not None:
            print(str(packed.path), file=stdout)
            print('sha256: ' + packed.package_sha256, file=stdout)
            for warning in packed.warnings:
                print(format_tool_message(warning), file=stderr)
        else:
            print(format_tool_message(str(error)), file=stderr)
        stdout.flush()
        stderr.flush()
    except (OSError, UnicodeError) as exc:
        _pack_output_diagnostic(stderr, exc, packed)
        return int(ExitCode.EXECUTION_ERROR)
    except KeyboardInterrupt as exc:
        _pack_output_diagnostic(stderr, exc, packed)
        return int(ExitCode.INTERRUPTED)
    return code


def _registry_list_json_result(
    result: Any,
) -> dict[str, object]:
    return {
        "repositories": [
            {
                "repo_id": str(repository.repo_id),
                "repository_path": str(repository.repository_path),
                "status": repository.status.value,
            }
            for repository in result.repositories
        ]
    }


def _registry_list_command(
    *,
    json_output: bool,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose and not json_output,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            result = api.repositories(observer=_progress_observer(console))
    except PatchHarborError as exc:
        exit_code = int(exit_code_for_error(exc))
        if json_output:
            _write_json_document(
                _json_envelope(
                    "registry.list",
                    result=None,
                    error=exc,
                    process_exit_code=exit_code,
                ),
                stdout,
            )
        else:
            print(format_tool_message(str(exc)), file=stderr)
        return exit_code

    if json_output:
        _write_json_document(
            _json_envelope(
                "registry.list",
                result=_registry_list_json_result(result),
                error=None,
                process_exit_code=0,
            ),
            stdout,
        )
    else:
        for repository in result.repositories:
            print(
                f"{shorten_identifier(repository.repo_id)}\t"
                f"{repository.status.value}\t"
                f"{repository.repository_path}",
                file=stdout,
            )
    return 0


def _context_command(
    path: Path | None,
    *,
    json_output: bool,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose and not json_output,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            context = api.context(path or Path.cwd(), observer=_progress_observer(console))
    except PatchHarborError as exc:
        exit_code = int(exit_code_for_error(exc))
        if json_output:
            _write_json_document(
                _json_envelope(
                    "context",
                    result=None,
                    error=exc,
                    process_exit_code=exit_code,
                ),
                stdout,
            )
        else:
            print(format_tool_message(str(exc)), file=stderr)
        return exit_code

    if json_output:
        _write_json_document(
            _json_envelope(
                "context",
                result=context_json_result(context),
                error=None,
                process_exit_code=0,
            ),
            stdout,
        )
    else:
        write_context_block(context, stdout)
    return 0


def _write_emergency_diagnostics_notice(
    path: Path | None,
    *,
    failed: bool,
    stderr: TextIO,
) -> None:
    """Expose one best-effort diagnostics outcome without duplicating wording."""
    if path is not None:
        print(
            format_tool_message(f"emergency diagnostics: {path}"),
            file=stderr,
        )
    elif failed:
        print(
            format_tool_message("emergency diagnostics could not be saved"),
            file=stderr,
        )


def _write_apply_completion(
    report: RunReport,
    *,
    json_output: bool,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Render one completed Apply run solely from its immutable report."""
    if json_output:
        _write_json_document(report.apply_json_envelope(), stdout)
    else:
        tool_error = report.completion_tool_error
        if tool_error is not None:
            print(format_tool_message(tool_error.message), file=stderr)
            if report.result_bundle.path is not None:
                print(
                    format_tool_message(
                        f"result bundle: {report.result_bundle.path}"
                    ),
                    file=stderr,
                )
        else:
            print(
                f"run_id: {shorten_identifier(report.run_id_text)}",
                file=stdout,
            )
            print(f"repository_path: {report.resolved_repository}", file=stdout)
            print(f"result_bundle_path: {report.result_bundle.path}", file=stdout)
    _write_emergency_diagnostics_notice(
        report.result_bundle.emergency_diagnostics_path,
        failed=report.result_bundle.status is ResultBundleStatus.FAILED,
        stderr=stderr,
    )
    return report.process_exit_code


def _bundle_command(
    path: Path | None,
    *,
    output_directory: Path | None,
    json_output: bool,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(stdout, stderr=stderr, enabled=not json_output, color_enabled=not no_color, plain=force_plain, verbose=verbose) as console:
            result = api.bundle(
                path or Path.cwd(), output_directory=output_directory,
                observer=_progress_observer(console),
            )
    except PatchHarborError as exc:
        exit_code = int(exit_code_for_error(exc))
        if json_output:
            _write_json_document(
                _json_envelope(
                    "bundle",
                    result=None,
                    error=exc,
                    process_exit_code=exit_code,
                ),
                stdout,
            )
        else:
            print(format_tool_message(str(exc)), file=stderr)
        _write_emergency_diagnostics_notice(
            exc.emergency_diagnostics_path,
            failed=exc.emergency_diagnostics_failed,
            stderr=stderr,
        )
        return exit_code

    if json_output:
        _write_json_document(
            _json_envelope(
                "bundle",
                result=result.report.manual_bundle_result(),
                error=None,
                process_exit_code=0,
            ),
            stdout,
        )
    else:
        print(f"run_id: {shorten_identifier(result.run_id)}", file=stdout)
        print(f"result_bundle_path: {result.path}", file=stdout)
    return 0


def _presented_completion(
    *,
    exit_code: int,
    tool_error: str | None,
    log_path: Path | None = None,
    result_path: Path | None = None,
) -> PresentedCompletion:
    """Choose one completion state before crossing into presentation."""
    if tool_error is not None:
        status = PresentedStatus.ERROR
    elif exit_code == 0:
        status = PresentedStatus.SUCCESS
    else:
        status = PresentedStatus.FAILED
    return PresentedCompletion(
        status=status,
        exit_code=exit_code,
        detail=tool_error,
        log_path=log_path,
        result_path=result_path,
    )


@contextmanager
def _console_scope(
    stdout: TextIO, *, enabled: bool, color_enabled: bool,
    stderr: TextIO | None = None,
    plain: bool = False,
    verbose: bool = False,
) -> Iterator[StreamingConsole | None]:
    """Start observation before discovery and release it on every exit path."""
    try:
        terminal = stdout.isatty() and not plain
    except (AttributeError, OSError):
        terminal = False
    console = (
        StreamingConsole(
            stdout if terminal or stderr is None else stderr,
            color_enabled=color_enabled and terminal, plain=plain,
            child_output=None if terminal else stdout, verbose=verbose,
        ) if enabled else None
    )
    try:
        if console is not None:
            console.activity("PATCHHARBOR", "Starting request", "heading")
        yield console
    finally:
        if console is not None:
            console.close()


def _progress_observer(console: StreamingConsole | None) -> api.ProgressObserver | None:
    """Pass this invocation's presentation explicitly through the API boundary."""
    return None if console is None else console.observe


def _output_streams_for_presentation(
    *, visible_stdout: TextIO, visible_stderr: TextIO,
    console: StreamingConsole | None, suppress_visible_output: bool = False,
    raw_output_stream: BinaryIO | None = None,
    warning_observer: Callable[[str], None] | None = None,
) -> api.OutputStreams:
    """Keep machine JSON and raw bytes separate from human streaming output."""
    if suppress_visible_output:
        return api.OutputStreams(raw=raw_output_stream, on_warning=warning_observer)
    return api.OutputStreams(
        text=visible_stdout if console is None else console.child_stream,
        raw=raw_output_stream,
        warnings=visible_stderr if console is None else console.warning_stream,
        on_warning=warning_observer,
    )


def _apply_command(
    path: Path | None,
    *,
    dry_run: bool,
    timeout_seconds: float,
    output_directory: Path | None,
    force_plain: bool,
    no_color: bool,
    json_output: bool,
    automatic: bool,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
) -> int:
    visible_stdout = stdout if json_output else SanitizedTextStream(stdout)
    visible_stderr = SanitizedTextStream(stderr)
    with _console_scope(
        stdout,
        stderr=stderr,
        enabled=not json_output,
        color_enabled=not no_color,
        plain=force_plain,
        verbose=verbose,
    ) as console:
        output = _output_streams_for_presentation(
            visible_stdout=visible_stdout,
            visible_stderr=visible_stderr,
            console=console,
            suppress_visible_output=json_output,
        )
        try:
            if automatic:
                report = api.apply_next(
                    dry_run=dry_run, timeout=timeout_seconds,
                    output_directory=output_directory, output=output,
                    observer=_progress_observer(console),
                )
            else:
                report = api.apply(
                    path, dry_run=dry_run, timeout=timeout_seconds,
                    output_directory=output_directory, output=output,
                    observer=_progress_observer(console),
                )
        except OSError as exc:
            operation = (
                "cannot render terminal console"
                if console is not None
                else "cannot write PatchHarbor output"
            )
            print(
                format_tool_message(
                    f"{operation}: {describe_os_error(exc)}"
                ),
                file=visible_stderr,
            )
            return int(ExitCode.EXECUTION_ERROR)

        if console is None or not console.started:
            return _write_apply_completion(
                report,
                json_output=json_output,
                stdout=visible_stdout,
                stderr=visible_stderr,
            )

        tool_error = report.completion_tool_error
        try:
            console.finish(
                _presented_completion(
                    exit_code=report.process_exit_code,
                    tool_error=(
                        None if tool_error is None else tool_error.message
                    ),
                    result_path=report.result_bundle.path,
                )
            )
        except OSError as exc:
            print(
                format_tool_message(
                    "cannot write streaming console: " f"{describe_os_error(exc)}"
                ),
                file=visible_stderr,
            )
            return int(ExitCode.EXECUTION_ERROR)
        if console.separate_child_output:
            return _write_apply_completion(
                report, json_output=False, stdout=visible_stdout, stderr=visible_stderr,
            )
        _write_emergency_diagnostics_notice(
            report.result_bundle.emergency_diagnostics_path,
            failed=report.result_bundle.status is ResultBundleStatus.FAILED,
            stderr=visible_stderr,
        )
        return report.process_exit_code


def _unregister_command(
    selector: str,
    *,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
    force_plain: bool = False,
    no_color: bool = False,
) -> int:
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            result = api.unregister(
                selector, cwd=Path.cwd(), observer=_progress_observer(console),
            )
            repo_id, repository_path = result.repo_id, result.repository_path
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exit_code_for_error(exc))

    print(f"repo_id: {shorten_identifier(repo_id)}", file=stdout)
    print(f"repository_path: {repository_path}", file=stdout)
    return 0


def _execute_request(
    path: Path | None,
    *,
    cwd: Path,
    timeout_seconds: float,
    stdin: TextIO,
    stdout: TextIO,
    output: api.OutputStreams,
    console: StreamingConsole | None,
) -> tuple[int, str | None]:
    try:
        result = api.run(
            path if path is not None else stdin,
            cwd=cwd, timeout=timeout_seconds,
            select_candidate=lambda candidates: select_directory_candidate(
                candidates, input_stream=stdin,
                output_stream=(stdout if console is None else console.selection_stream),
            ),
            output=output, observer=_progress_observer(console),
        )
        return result.exit_code, None
    except PatchHarborError as exc:
        return int(exit_code_for_error(exc)), str(exc)


def _run_command(
    path: Path | None,
    timeout_seconds: float,
    *,
    force_plain: bool,
    no_color: bool,
    log_enabled: bool,
    parser: argparse.ArgumentParser,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    verbose: bool = False,
) -> int:
    if path is None and stdin.isatty():
        parser.error("PATH is required when standard input is a terminal")

    cwd = Path.cwd()
    log_context = temporary_run_log() if log_enabled else nullcontext(None)
    log_path: Path | None = None
    exit_code = 0
    tool_error: str | None = None

    with _console_scope(
        stdout,
        stderr=stderr,
        enabled=True,
        color_enabled=not no_color,
        plain=force_plain,
        verbose=verbose,
    ) as console:
        try:
            with log_context as run_log:
                if run_log is not None:
                    log_path = run_log.path
                    run_log.write_header(
                        source_name=(
                            "standard input" if path is None else str(path)
                        ),
                        cwd=cwd,
                        timeout_seconds=timeout_seconds,
                    )

                output = _output_streams_for_presentation(
                    visible_stdout=stdout,
                    visible_stderr=stderr,
                    console=console,
                    raw_output_stream=(
                        None if run_log is None else run_log.raw_output_stream
                    ),
                    warning_observer=(
                        None if run_log is None else run_log.write_warning
                    ),
                )
                try:
                    exit_code, tool_error = _execute_request(
                        path,
                        cwd=cwd,
                        timeout_seconds=timeout_seconds,
                        stdin=stdin,
                        stdout=stdout,
                        output=output,
                        console=console,
                    )
                except KeyboardInterrupt:
                    exit_code = int(ExitCode.INTERRUPTED)
                    tool_error = "request aborted by user"

                if run_log is not None:
                    run_log.write_result(
                        exit_code=exit_code,
                        tool_error=tool_error,
                    )
        except KeyboardInterrupt:
            exit_code = int(ExitCode.INTERRUPTED)
            tool_error = "request aborted by user"
        except OSError as exc:
            tool_error = (
                "cannot write PatchHarbor output: "
                f"{describe_os_error(exc)}"
            )
            exit_code = int(ExitCode.EXECUTION_ERROR)

        if console is not None and console.started:
            try:
                console.finish(
                    _presented_completion(
                        exit_code=exit_code,
                        tool_error=tool_error,
                        log_path=None,
                    )
                )
            except OSError as exc:
                print(
                    format_tool_message(
                        "cannot write streaming console: "
                        f"{describe_os_error(exc)}"
                    ),
                    file=stderr,
                )
                exit_code = int(ExitCode.EXECUTION_ERROR)
        else:
            if tool_error is not None:
                print(format_tool_message(tool_error), file=stderr)
        if log_path is not None:
            print(format_tool_message(f"log: {log_path}"), file=stderr)

        return exit_code


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the PatchHarbor CLI."""
    actual_stdin = sys.stdin if stdin is None else stdin
    actual_stdout = sys.stdout if stdout is None else stdout
    actual_stderr = sys.stderr if stderr is None else stderr
    if stdin is None:
        _configure_utf8_standard_stream(actual_stdin, errors="strict")
    if stdout is None:
        _configure_utf8_standard_stream(actual_stdout, errors="replace")
    if stderr is None:
        _configure_utf8_standard_stream(actual_stderr, errors="replace")

    parser = _build_parser()
    args = parser.parse_args(argv)
    for option in ("verbose", "plain", "no_color"):
        if not hasattr(args, option):
            setattr(args, option, False)

    if (
        args.command == "apply"
        and args.automatic
        and args.patch_zip is not None
    ):
        parser.error("internal --automatic mode does not accept PATCH_ZIP")

    if (
        args.command == "configure"
        and args.configure_command == "exchange-directory"
    ):
        return _configure_exchange_directory_command(
            args.directory,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )

    if args.command == "configure" and args.configure_command == "bundle-suffix":
        if (args.suffix is None) == (not args.clear):
            print(
                format_tool_message("specify either a bundle suffix or --clear"),
                file=actual_stderr,
            )
            return 2
        return _configure_bundle_suffix_command(
            "" if args.clear else args.suffix,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )
    if args.command == "configure" and args.configure_command == "archive-dir":
        if (args.name is None) == (not args.clear):
            print(format_tool_message("specify either an archive folder name or --clear"), file=actual_stderr)
            return int(ExitCode.USAGE_ERROR)
        return _configure_archive_directory_command(
            "" if args.clear else args.name, stdout=actual_stdout, stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )
    if args.command == "configure" and args.configure_command == "show":
        return _configure_show_command(
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )

    if args.command == "register":
        return _register_command(
            args.repository,
            new_id=args.new_id,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )

    if args.command == "registry" and args.registry_command == "list":
        return _registry_list_command(
            json_output=args.json_output,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )

    if args.command == "unregister":
        return _unregister_command(
            args.repository_or_repo_id,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )

    if args.command == "context":
        return _context_command(
            args.repository,
            json_output=args.json_output,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
        )

    if args.command == 'pack':
        return _pack_command(args, stdout=actual_stdout, stderr=actual_stderr)

    if args.command in ("inspect", "validate"):
        return _package_command(
            args.command, args.patch_zip, json_output=args.json_output,
            stdout=actual_stdout, stderr=actual_stderr,
            verbose=args.verbose, force_plain=args.plain, no_color=args.no_color,
            repository=getattr(args, "repository", None),
            reference_bundle=getattr(args, "reference_bundle", None),
        )

    if args.command == "bundle":
        return _bundle_command(
            args.repository,
            output_directory=args.output_dir,
            json_output=args.json_output,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=getattr(args, "verbose", False),
            force_plain=args.plain, no_color=args.no_color,
        )

    if args.command == "apply":
        return _apply_command(
            args.patch_zip,
            dry_run=args.dry_run,
            timeout_seconds=args.timeout,
            output_directory=args.output_dir,
            force_plain=args.plain,
            no_color=args.no_color,
            json_output=args.json_output,
            automatic=args.automatic,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=getattr(args, "verbose", False),
        )

    if args.command == "fs" and args.fs_command == "run":
        return _run_command(
            args.path,
            args.timeout,
            force_plain=args.plain,
            no_color=args.no_color,
            log_enabled=args.log,
            parser=parser,
            stdin=actual_stdin,
            stdout=actual_stdout,
            stderr=actual_stderr,
            verbose=getattr(args, "verbose", False),
        )

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
