"""Console entry point for the separate PatchHarbor Watcher component."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import TextIO

from patchharbor.path_configuration import (
    PreparedWatcherInput,
    prepare_watcher_input_directory,
)
from patchharbor.watcher import run_watcher
from patchharbor.watcher_lifecycle import (
    WatcherStopController,
    installed_stop_signals,
)
from patchharbor.watcher_subprocess import delegate_to_apply


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
        type=Path,
        metavar="INPUT_DIRECTORY",
    )
    parser.add_argument(
        "--poll-interval",
        type=_positive_seconds,
        default=1.0,
        metavar="SECONDS",
        help="seconds between non-recursive scans (default: 1.0)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the separate polling watcher."""
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    actual_stdout = sys.stdout if stdout is None else stdout
    actual_stderr = sys.stderr if stderr is None else stderr
    stop_controller = WatcherStopController()

    try:
        prepared_input = prepare_watcher_input_directory(
            arguments.input_directory
        )
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
