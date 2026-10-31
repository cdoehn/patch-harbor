"""PatchHarbor CLI entrypoint: UTF-8 streams, parsing and explicit dispatch."""

from __future__ import annotations

from collections.abc import Sequence
import sys
from typing import TextIO

import patchharbor.api as api
from patchharbor.errors import format_tool_message
from patchharbor.exit_status import ExitCode
from patchharbor.cli_parser import (
    _build_parser,
)
from patchharbor.cli_commands import (
    _apply_command,
    _bundle_command,
    _configuration_command,
    _context_command,
    _pack_command,
    _package_command,
    _register_command,
    _registry_list_command,
    _run_command,
    _unregister_command,
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

    presentation = {
        "stdout": actual_stdout, "stderr": actual_stderr,
        "verbose": args.verbose, "force_plain": args.plain, "no_color": args.no_color,
    }

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
        return _configuration_command(
            api.configure_exchange_directory, args.directory, **presentation,
        )

    if args.command == "configure" and args.configure_command == "bundle-suffix":
        if (args.suffix is None) == (not args.clear):
            print(
                format_tool_message("specify either a bundle suffix or --clear"),
                file=actual_stderr,
            )
            return 2
        return _configuration_command(
            api.configure_bundle_suffix, "" if args.clear else args.suffix, **presentation,
        )
    if args.command == "configure" and args.configure_command == "archive-dir":
        if (args.name is None) == (not args.clear):
            print(format_tool_message("specify either an archive folder name or --clear"), file=actual_stderr)
            return int(ExitCode.USAGE_ERROR)
        return _configuration_command(
            api.configure_archive_directory, "" if args.clear else args.name, **presentation,
        )
    if args.command == "configure" and args.configure_command == "show":
        return _configuration_command(api.configuration, **presentation)

    if args.command == "register":
        return _register_command(args.repository, new_id=args.new_id, **presentation)

    if args.command == "registry" and args.registry_command == "list":
        return _registry_list_command(json_output=args.json_output, **presentation)

    if args.command == "unregister":
        return _unregister_command(args.repository_or_repo_id, **presentation)

    if args.command == "context":
        return _context_command(args.repository, json_output=args.json_output, **presentation)

    if args.command == 'pack':
        return _pack_command(args, stdout=actual_stdout, stderr=actual_stderr)

    if args.command in ("inspect", "validate"):
        return _package_command(
            args.command, args.patch_zip, json_output=args.json_output,
            repository=getattr(args, "repository", None),
            reference_bundle=getattr(args, "reference_bundle", None), **presentation,
        )

    if args.command == "bundle":
        return _bundle_command(
            args.repository, output_directory=args.output_dir,
            json_output=args.json_output, **presentation,
        )

    if args.command == "apply":
        return _apply_command(
            args.patch_zip, dry_run=args.dry_run, timeout_seconds=args.timeout,
            output_directory=args.output_dir, json_output=args.json_output,
            automatic=args.automatic, **presentation,
        )

    if args.command == "fs" and args.fs_command == "run":
        return _run_command(
            args.path, args.timeout, log_enabled=args.log, parser=parser,
            stdin=actual_stdin, **presentation,
        )

    parser.error("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
