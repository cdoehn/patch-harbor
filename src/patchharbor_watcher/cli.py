"""Console entry point for the separate PatchHarbor Watcher component."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import TextIO

import patchharbor.api as api
from patchharbor_watcher.execute_boundary import delegate_to_automatic_execute
from patchharbor_watcher.lifecycle import (
    WatcherStopController,
    installed_stop_signals,
)
from patchharbor_watcher.loop import run_repository_watcher
from patchharbor_watcher.polling import DEFAULT_POLL_INTERVAL, poll_interval, run_polling_watcher


def _poll_seconds(value):
    try:
        return poll_interval(float(value))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _install_systemd_user_unit() -> Path:
    """Load the Linux-only systemd boundary only for that explicit action."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError(
            "systemd user-unit installation is supported only on Linux"
        )
    from patchharbor_watcher.systemd_linux import install_systemd_user_unit

    return install_systemd_user_unit()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchharbor-watcher",
        allow_abbrev=False,
        description=(
            "Watch filesystem events and request scoped automatic Execute "
            "after five seconds of quiet across the Exchange directories of all registered repositories. "
            "Use 'poll' for filesystems without reliable notifications, such as CIFS."
        ),
        epilog=(
            "Register each repository and configure its Exchange with 'patchharbor configure "
            "exchange-directory DIRECTORY'. Run in the foreground or install "
            "the optional Linux systemd user unit; the installer does not "
            "enable or start it. Use manual 'patchharbor execute' on "
            "Termux/Android."
        ),
    )
    parser.add_argument(
        "--install-systemd-user-unit",
        action="store_true",
        help=(
            "install the Linux systemd user unit; "
            "do not enable or start it"
        ),
    )
    commands = parser.add_subparsers(dest='mode')
    poll = commands.add_parser('poll', allow_abbrev=False,
                               help='poll registered Exchanges without filesystem events')
    poll.add_argument('-i', '--interval', '--poll-interval', type=_poll_seconds,
                      default=DEFAULT_POLL_INTERVAL, metavar='SECONDS',
                      help='wait between completed checks; positive seconds, fractions allowed (default: 4)')
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Install or run the global trigger for repository-local Exchange settings."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.mode == 'poll' and arguments.install_systemd_user_unit:
        parser.error('poll runs in the foreground; the systemd installer creates the event-mode unit')
    actual_stdout = sys.stdout if stdout is None else stdout
    actual_stderr = sys.stderr if stderr is None else stderr
    stop_controller = WatcherStopController()

    try:
        api.repositories()  # Validate the registry; Event subscriptions refresh settings through Core.
        if arguments.install_systemd_user_unit:
            unit_path = _install_systemd_user_unit()
            print(unit_path, file=actual_stdout)
            return 0

        with installed_stop_signals(stop_controller):
            if arguments.mode == 'poll':
                run_polling_watcher(
                    delegate=delegate_to_automatic_execute,
                    log_stream=actual_stdout, error_stream=actual_stderr,
                    stop_requested=stop_controller.stop_requested, wait=stop_controller.wait,
                    interval=arguments.interval,
                )
            else:
                run_repository_watcher(
                    delegate=delegate_to_automatic_execute,
                    log_stream=actual_stdout,
                    error_stream=actual_stderr,
                    stop_requested=stop_controller.stop_requested,
                    bind_wake=stop_controller.bind_wake,
                )
    except KeyboardInterrupt:
        return 130
    except (api.PatchHarborError, OSError, RuntimeError, ValueError) as exc:
        print(f"patchharbor-watcher: {exc}", file=actual_stderr)
        return 1
    return 130 if stop_controller.was_interrupted() else 0


if __name__ == "__main__":
    raise SystemExit(main())
