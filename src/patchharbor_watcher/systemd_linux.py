"""Linux systemd user-unit installation for the separate watcher."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from patchharbor.physical_paths import physically_canonicalize
from patchharbor.platform.filesystem import (
    FileSystemOperationError,
    PathKind,
    atomic_replace_bytes,
    path_kind,
)


SYSTEMD_USER_UNIT_NAME = "patchharbor-watcher.service"


class WatcherSystemdError(RuntimeError):
    """The systemd user unit cannot be created safely."""


def _require_linux() -> None:
    if os.name != "posix" or not sys.platform.startswith("linux"):
        raise WatcherSystemdError(
            "systemd user-unit installation is supported only on Linux"
        )


def _systemd_user_unit_directory() -> Path:
    home_value = os.environ.get("HOME")
    if not home_value:
        raise WatcherSystemdError("HOME is required for systemd user units")
    configuration_root = Path(
        os.environ.get("XDG_CONFIG_HOME", os.fspath(Path(home_value) / ".config"))
    )
    return configuration_root / "systemd" / "user"


def _quote_exec_argument(value: str) -> str:
    if any(character in value for character in ("\x00", "\n", "\r")):
        raise WatcherSystemdError("systemd executable path is invalid")
    escaped = value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_systemd_user_unit(python_executable: Path) -> bytes:
    """Render a minimal user service that runs the configured watcher."""
    executable = _quote_exec_argument(os.fspath(python_executable))
    return (
        "[Unit]\n"
        "Description=PatchHarbor Watcher\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={executable} -m patchharbor_watcher.cli\n"
        "Environment=PYTHONUNBUFFERED=1\n"
        "Restart=on-failure\n"
        "RestartSec=2\n"
        "StandardOutput=journal\n"
        "StandardError=journal\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    ).encode("utf-8")


def install_systemd_user_unit(
    python_executable: Path | None = None,
) -> Path:
    """Install, but never enable, the PatchHarbor systemd user unit."""
    _require_linux()
    requested_executable = (
        Path(sys.executable) if python_executable is None else python_executable
    ).expanduser()
    executable = Path(os.path.abspath(requested_executable))
    try:
        if not executable.is_file():
            raise WatcherSystemdError("Python executable is not a file")
        unit_directory = _systemd_user_unit_directory()
        unit_directory.mkdir(parents=True, exist_ok=True)
        canonical_unit_directory = physically_canonicalize(
            unit_directory,
            must_exist=True,
        )
        if path_kind(canonical_unit_directory) is not PathKind.DIRECTORY:
            raise WatcherSystemdError(
                "systemd user-unit directory is not a directory"
            )
        unit_path = canonical_unit_directory / SYSTEMD_USER_UNIT_NAME
        if path_kind(unit_path) not in {
            PathKind.MISSING,
            PathKind.REGULAR_FILE,
        }:
            raise WatcherSystemdError(
                "systemd user unit is not a regular file"
            )
        atomic_replace_bytes(unit_path, render_systemd_user_unit(executable))
    except WatcherSystemdError:
        raise
    except (FileSystemOperationError, OSError, RuntimeError) as exc:
        raise WatcherSystemdError(
            "cannot install systemd user unit"
        ) from exc
    return unit_path
