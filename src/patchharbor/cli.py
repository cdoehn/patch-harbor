"""PatchHarbor command-line interface."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path
import sys
from typing import Any, TextIO

from patchharbor import __version__
from patchharbor.application import (
    bundle_repository,
    register_repository,
    registered_repositories,
    repository_context,
    run_script_path,
    run_standard_input,
    resolve_patch_package,
    unregister_repository,
    validate_patch_package_repository,
)
from patchharbor.context_output import context_json_result, write_context_block
from patchharbor.errors import (
    ExitCode,
    PatchHarborError,
    format_tool_message,
    format_tool_warning,
)
from patchharbor.execution import DEFAULT_TIMEOUT_SECONDS
from patchharbor.json_document import serialize_json_document
from patchharbor.output import OutputTargets
from patchharbor.platform.errors import describe_os_error
from patchharbor.presentation import (
    TerminalDashboard,
    terminal_supports_dashboard,
)
from patchharbor.run_log import temporary_run_log
from patchharbor.run_report import (
    RunReport,
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


def _positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if seconds <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return seconds


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchharbor",
        description=(
            "Run generated Bash and PowerShell scripts or ZIP "
            "PatchBundles with controlled execution."
        ),
        epilog=(
            "Use 'patchharbor fs run --help' for input formats, "
            "execution rules, and run options."
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

    register_parser = commands.add_parser(
        "register",
        help="register one local Git repository instance",
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
    )
    registry_list_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="write the versioned machine-readable result",
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
        help="write the versioned machine-readable result",
    )

    bundle_parser = commands.add_parser(
        "bundle",
        help="create a Result Bundle for one registered repository",
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
        help="publish the Result Bundle in this directory",
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
    )
    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="validate the patch package without changing a repository",
    )
    apply_parser.add_argument(
        "patch_zip",
        type=Path,
        metavar="PATCH_ZIP",
        help="ZIP patch package containing a root patch.json",
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
        "--plain",
        action="store_true",
        help="stream simple text output even when standard output is a terminal",
    )
    run_parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable colors in the terminal dashboard",
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


def _register_command(
    path: Path | None,
    *,
    new_id: bool,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        context = register_repository(
            path or Path.cwd(),
            new_id=new_id,
        )
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exc.exit_code)

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
) -> dict[str, object]:
    structured_error: dict[str, object] | None = None
    if error is not None:
        report = error.run_report if isinstance(error.run_report, RunReport) else None
        report_error = (
            None if report is None else report.result_bundle.error
        )
        emergency_path = (
            error.emergency_diagnostics_path
            if report is None
            else report.result_bundle.emergency_diagnostics_path
        )
        structured_error = {
            "kind": error.error_kind.value,
            "message": sanitize_structured_text(report_error or str(error)),
            "patchharbor_error_code": int(error.exit_code),
            "emergency_diagnostics_path": physical_absolute_path_text(
                emergency_path
            ),
        }
    return {
        "output_version": 1,
        "command": command,
        "success": process_exit_code == 0,
        "result": result,
        "error": structured_error,
        "process_exit_code": process_exit_code,
    }


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
) -> int:
    try:
        result = registered_repositories()
    except PatchHarborError as exc:
        exit_code = int(exc.exit_code)
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
                f"{repository.repo_id}\t{repository.status.value}\t"
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
) -> int:
    try:
        context = repository_context(path or Path.cwd())
    except PatchHarborError as exc:
        exit_code = int(exc.exit_code)
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
    error: PatchHarborError,
    stderr: TextIO,
) -> None:
    if error.emergency_diagnostics_path is not None:
        print(
            format_tool_message(
                f"emergency diagnostics: {error.emergency_diagnostics_path}"
            ),
            file=stderr,
        )
    elif error.emergency_diagnostics_failed:
        print(
            format_tool_message("emergency diagnostics could not be saved"),
            file=stderr,
        )


def _bundle_command(
    path: Path | None,
    *,
    output_directory: Path | None,
    json_output: bool,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        result = bundle_repository(
            path or Path.cwd(),
            output_directory=output_directory,
        )
    except PatchHarborError as exc:
        exit_code = int(exc.exit_code)
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
        _write_emergency_diagnostics_notice(exc, stderr)
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
        print(f"run_id: {result.run_id}", file=stdout)
        print(f"result_bundle_path: {result.path}", file=stdout)
    return 0


def _apply_command(
    path: Path,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        package = resolve_patch_package(path)
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exc.exit_code)

    for warning in package.warnings:
        print(format_tool_warning(warning), file=stderr)

    try:
        context = validate_patch_package_repository(package)
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        report = exc.run_report if isinstance(exc.run_report, RunReport) else None
        if report is not None and report.result_bundle.path is not None:
            print(
                format_tool_message(
                    f"result bundle: {report.result_bundle.path}"
                ),
                file=stderr,
            )
        _write_emergency_diagnostics_notice(exc, stderr)
        return int(exc.exit_code)

    print(f"validated_patch_package: {path}", file=stdout)
    print(f"repository_path: {context.repository_path}", file=stdout)
    return 0


def _unregister_command(
    selector: str,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        repo_id, repository_path = unregister_repository(
            selector,
            cwd=Path.cwd(),
        )
    except PatchHarborError as exc:
        print(format_tool_message(str(exc)), file=stderr)
        return int(exc.exit_code)

    print(f"repo_id: {repo_id}", file=stdout)
    print(f"repository_path: {repository_path}", file=stdout)
    return 0


def _execute_request(
    path: Path | None,
    *,
    cwd: Path,
    timeout_seconds: float,
    stdin: TextIO,
    stdout: TextIO,
    output: OutputTargets,
    dashboard: TerminalDashboard | None,
) -> tuple[int, str | None]:
    try:
        if path is not None:
            return (
                run_script_path(
                    path,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                    selection_input=stdin,
                    selection_output=stdout,
                    output=output,
                    presentation=dashboard,
                ),
                None,
            )
        return (
            run_standard_input(
                stdin,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                output=output,
                presentation=dashboard,
            ),
            None,
        )
    except PatchHarborError as exc:
        return int(exc.exit_code), str(exc)


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
) -> int:
    if path is None and stdin.isatty():
        parser.error("PATH is required when standard input is a terminal")

    cwd = Path.cwd()
    plain_output = force_plain or not terminal_supports_dashboard(stdout)
    dashboard = (
        None
        if plain_output
        else TerminalDashboard(stdout, color_enabled=not no_color)
    )
    log_context = temporary_run_log() if log_enabled else nullcontext(None)
    log_path: Path | None = None
    exit_code = 0
    tool_error: str | None = None

    try:
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

                output = OutputTargets(
                    visible_text_stream=stdout,
                    live_text_stream=(stdout if plain_output else None),
                    raw_output_stream=(
                        None if run_log is None else run_log.raw_output_stream
                    ),
                    warning_text_stream=(stderr if plain_output else None),
                    warning_observer=(
                        None if run_log is None else run_log.write_warning
                    ),
                    line_observer=(
                        None if dashboard is None else dashboard.update_output
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
                        dashboard=dashboard,
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

        dashboard_active = dashboard is not None and dashboard.started
        if dashboard_active:
            try:
                dashboard.finish(
                    exit_code=exit_code,
                    tool_error=tool_error,
                    log_path=log_path,
                )
            except OSError as exc:
                print(
                    format_tool_message(
                        "cannot restore terminal: "
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
    finally:
        if dashboard is not None:
            dashboard.close()


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

    if args.command == "register":
        return _register_command(
            args.repository,
            new_id=args.new_id,
            stdout=actual_stdout,
            stderr=actual_stderr,
        )

    if args.command == "registry" and args.registry_command == "list":
        return _registry_list_command(
            json_output=args.json_output,
            stdout=actual_stdout,
            stderr=actual_stderr,
        )

    if args.command == "unregister":
        return _unregister_command(
            args.repository_or_repo_id,
            stdout=actual_stdout,
            stderr=actual_stderr,
        )

    if args.command == "context":
        return _context_command(
            args.repository,
            json_output=args.json_output,
            stdout=actual_stdout,
            stderr=actual_stderr,
        )

    if args.command == "bundle":
        return _bundle_command(
            args.repository,
            output_directory=args.output_dir,
            json_output=args.json_output,
            stdout=actual_stdout,
            stderr=actual_stderr,
        )

    if args.command == "apply":
        return _apply_command(
            args.patch_zip,
            stdout=actual_stdout,
            stderr=actual_stderr,
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
        )

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
