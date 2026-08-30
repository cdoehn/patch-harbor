"""Console entry point for the separate PatchHarbor Watcher component."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import TextIO

from patchharbor.configuration import (
    load_configuration,
    revalidate_exchange_directory,
)
from patchharbor.errors import PatchHarborError
from patchharbor.user_paths import configuration_user_paths
from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
from patchharbor_watcher.lifecycle import (
    WatcherStopController,
    installed_stop_signals,
)
from patchharbor_watcher.loop import run_shared_exchange_watcher


def _load_exchange_directory() -> Path:
    """Load the one shared Core Exchange directory for watcher startup."""
    configuration = revalidate_exchange_directory(
        load_configuration(configuration_user_paths())
    )
    return configuration.exchange_directory


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
        allow_abbrev=False,
        description=(
            "Continuously invoke PatchHarbor's parameterless automatic Apply "
            "mode for the shared Exchange directory from PatchHarbor config.json."
        ),
        epilog=(
            "Configure Exchange first with 'patchharbor configure "
            "exchange-directory DIRECTORY'. Run in the foreground or install "
            "the optional Linux systemd user unit; the installer does not "
            "enable or start it. Use manual 'patchharbor apply' on "
            "Termux/Android."
        ),
    )
    parser.add_argument(
        "--install-systemd-user-unit",
        action="store_true",
        help=(
            "install the Linux systemd user unit after Exchange is configured; "
            "do not enable or start it"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=_positive_seconds,
        default=1.0,
        metavar="SECONDS",
        help="seconds between Core apply requests (default: 1.0)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Install or run the thin shared-Exchange watcher."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    actual_stdout = sys.stdout if stdout is None else stdout
    actual_stderr = sys.stderr if stderr is None else stderr
    stop_controller = WatcherStopController()

    try:
        exchange_directory = _load_exchange_directory()
        if arguments.install_systemd_user_unit:
            unit_path = _install_systemd_user_unit()
            print(unit_path, file=actual_stdout)
            return 0

        with installed_stop_signals(stop_controller):
            run_shared_exchange_watcher(
                exchange_directory,
                delegate=delegate_to_automatic_apply,
                poll_interval_seconds=arguments.poll_interval,
                log_stream=actual_stdout,
                error_stream=actual_stderr,
                stop_requested=stop_controller.stop_requested,
                wait_between_polls=stop_controller.wait,
            )
    except KeyboardInterrupt:
        return 130
    except (PatchHarborError, OSError, RuntimeError, ValueError) as exc:
        print(f"patchharbor-watcher: {exc}", file=actual_stderr)
        return 1
    return 130 if stop_controller.was_interrupted() else 0


if __name__ == "__main__":
    raise SystemExit(main())
