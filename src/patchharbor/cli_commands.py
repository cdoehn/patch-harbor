"""CLI handlers using the public API and shared output boundaries."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any, TextIO

import patchharbor.api as api
from patchharbor.api import PatchHarborError, ResultBundleStatus
from patchharbor.context_output import context_json_result, write_context_block
from patchharbor.errors import format_tool_message
from patchharbor.exit_status import ExitCode, exit_code_for_error
from patchharbor.identifier_presentation import shorten_identifier
from patchharbor.inspection_output import (
    inspection_json_result,
    validation_json_result,
    pack_json_result,
)
from patchharbor.platform.errors import describe_os_error
from patchharbor.presentation import (
    SanitizedTextStream,
    StreamingConsole,
    select_directory_candidate,
)
from patchharbor.run_log import temporary_run_log
from patchharbor.cli_output import (
    _console_scope,
    _json_envelope,
    _output_streams_for_presentation,
    _presented_completion,
    _progress_observer,
    _write_apply_completion,
    _write_command_error,
    _write_emergency_diagnostics_notice,
    _write_json_document,
)


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
        return _write_command_error(
            command, exc, json_output=json_output, stdout=stdout, stderr=stderr,
            output_version=2,
        )
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
        return _write_command_error(
            "registry.list", exc, json_output=json_output, stdout=stdout, stderr=stderr,
        )

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
        return _write_command_error(
            "context", exc, json_output=json_output, stdout=stdout, stderr=stderr,
        )

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
        exit_code = _write_command_error(
            "bundle", exc, json_output=json_output, stdout=stdout, stderr=stderr,
        )
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


def _configuration_command(
    operation: Callable[..., api.ConfigurationResult], *values: Path | str,
    stdout: TextIO, stderr: TextIO, verbose: bool = False,
    force_plain: bool = False, no_color: bool = False,
) -> int:
    """Share the observer, error and output boundary for local settings."""
    try:
        with _console_scope(
            stdout, stderr=stderr, enabled=verbose,
            color_enabled=not no_color, plain=force_plain, verbose=verbose,
        ) as console:
            configuration = operation(*values, observer=_progress_observer(console))
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
