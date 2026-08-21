"""Console entry point for the separate PatchHarbor Watcher component."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import TextIO

from patchharbor.path_configuration import prepare_watcher_input_directory
from patchharbor_watcher.loop import run_watcher
from patchharbor_watcher.configuration import (
    configure_watcher_input_directory,
    load_configured_watcher_input_directory,
)
from patchharbor_watcher.lifecycle import (
    WatcherStopController,
    installed_stop_signals,
)
from patchharbor_watcher.apply_boundary import delegate_to_apply


def _install_systemd_user_unit() -> Path:
    """Load the Linux-only systemd boundary only for that explicit action."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError(
            "systemd user-unit installation is supported only on Linux"
        )
    from patchharbor_watcher.systemd_linux import install_systemd_user_unit

    return install_systemd_user_unit()


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
        prog="patchharbor-watcher",
        description=(
            "Watch one input directory and delegate stable files to "
            "'patchharbor apply --json'."
        ),
    )
    parser.add_argument(
        "input_directory",
        nargs="?",
        type=Path,
        metavar="INPUT_DIRECTORY",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--configure",
        type=Path,
        metavar="INPUT_DIRECTORY",
        help="persist the default input directory and exit",
    )
    action.add_argument(
        "--install-systemd-user-unit",
        action="store_true",
        help="install the Linux systemd user unit without enabling it",
    )
    parser.add_argument(
        "--poll-interval",
        type=_positive_seconds,
        default=1.0,
        metavar="SECONDS",
        help="seconds between non-recursive scans (default: 1.0)",
    )
    return parser


def _require_action_without_positional_input(
    parser: argparse.ArgumentParser,
    input_directory: Path | None,
    action_requested: bool,
) -> None:
    if action_requested and input_directory is not None:
        parser.error(
            "INPUT_DIRECTORY cannot be combined with a configuration action"
        )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Configure, install, or run the separate polling watcher."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    actual_stdout = sys.stdout if stdout is None else stdout
    actual_stderr = sys.stderr if stderr is None else stderr
    _require_action_without_positional_input(
        parser,
        arguments.input_directory,
        arguments.configure is not None
        or arguments.install_systemd_user_unit,
    )

    try:
        if arguments.configure is not None:
            prepared = configure_watcher_input_directory(arguments.configure)
            print(prepared.directory, file=actual_stdout)
            return 0
        if arguments.install_systemd_user_unit:
            load_configured_watcher_input_directory()
            unit_path = _install_systemd_user_unit()
            print(unit_path, file=actual_stdout)
            return 0

        prepared_input = (
            prepare_watcher_input_directory(arguments.input_directory)
            if arguments.input_directory is not None
            else load_configured_watcher_input_directory()
        )
        stop_controller = WatcherStopController()
        with installed_stop_signals(stop_controller):
            run_watcher(
                prepared_input.directory,
                delegate=delegate_to_apply,
                state_path=prepared_input.state_path,
                poll_interval_seconds=arguments.poll_interval,
                log_stream=actual_stdout,
                error_stream=actual_stderr,
                stop_requested=stop_controller.stop_requested,
                wait_between_polls=stop_controller.wait,
            )
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"patchharbor-watcher: {exc}", file=actual_stderr)
        return 1
    return 130 if stop_controller.was_interrupted() else 0


if __name__ == "__main__":
    raise SystemExit(main())
