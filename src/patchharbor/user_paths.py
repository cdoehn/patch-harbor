"""Platform-appropriate user paths needed by PatchHarbor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path

from patchharbor.errors import (
    PatchHarborError,
    configuration_error,
    registry_error,
)
from patchharbor.platform.paths import physically_canonicalize
from patchharbor.platform.runtime import is_windows


@dataclass(frozen=True)
class RegistrationUserPaths:
    """Canonical configuration and lock locations for registration."""

    configuration_directory: Path
    lock_directory: Path

    @property
    def registry_path(self) -> Path:
        return self.configuration_directory / "registry.json"

    @property
    def registry_lock_path(self) -> Path:
        return self.lock_directory / "registry.lock"

    @property
    def state_directory(self) -> Path:
        """Return the user-specific PatchHarbor state directory."""
        return self.lock_directory.parent

    @property
    def exchange_state_directory(self) -> Path:
        """Return the directory containing shared Exchange processing state."""
        return self.state_directory / "exchange"

    @property
    def exchange_state_path(self) -> Path:
        """Return the atomically replaced Exchange processing document."""
        return self.exchange_state_directory / "state.json"

    @property
    def exchange_state_lock_path(self) -> Path:
        """Return the shared Exchange processing lock file."""
        return self.lock_directory / "exchange.lock"


_ErrorFactory = Callable[[str], PatchHarborError]


def _user_paths(
    *,
    error_factory: _ErrorFactory,
    purpose: str,
) -> RegistrationUserPaths:
    if is_windows():
        app_data = os.environ.get("APPDATA")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not app_data or not local_app_data:
            raise error_factory(
                f"APPDATA and LOCALAPPDATA are required for {purpose}"
            )
        configuration = Path(app_data) / "PatchHarbor"
        locks = Path(local_app_data) / "PatchHarbor" / "locks"
    else:
        home_value = os.environ.get("HOME")
        if not home_value:
            raise error_factory(f"HOME is required for {purpose}")
        home = Path(home_value)
        configuration = Path(
            os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))
        ) / "patchharbor"
        state = Path(
            os.environ.get(
                "XDG_STATE_HOME",
                str(home / ".local" / "state"),
            )
        ) / "patchharbor"
        locks = state / "locks"

    try:
        configuration.mkdir(parents=True, exist_ok=True)
        locks.mkdir(parents=True, exist_ok=True)
        canonical_configuration = physically_canonicalize(
            configuration,
            must_exist=True,
        )
        canonical_locks = physically_canonicalize(locks, must_exist=True)
    except (OSError, RuntimeError) as exc:
        raise error_factory(
            f"cannot create PatchHarbor user directory: {exc}"
        ) from exc

    return RegistrationUserPaths(
        configuration_directory=canonical_configuration,
        lock_directory=canonical_locks,
    )


def registration_user_paths() -> RegistrationUserPaths:
    """Create user paths whose failures belong to the registry boundary."""
    return _user_paths(
        error_factory=registry_error,
        purpose="registration",
    )


def configuration_user_paths() -> RegistrationUserPaths:
    """Create user paths whose failures belong to the config boundary."""
    return _user_paths(
        error_factory=configuration_error,
        purpose="configuration",
    )
