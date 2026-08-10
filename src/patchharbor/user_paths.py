"""Platform-appropriate user paths needed by repository registration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from patchharbor.errors import PatchHarborError, registry_error
from patchharbor.physical_paths import physically_canonicalize


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
    def result_directory(self) -> Path:
        """Return the default user-specific Result Bundle directory."""
        return self.lock_directory.parent / "results"


def _error(message: str) -> PatchHarborError:
    return registry_error(message)


def registration_user_paths() -> RegistrationUserPaths:
    """Create and physically canonicalize registration-owned user paths."""
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not app_data or not local_app_data:
            raise _error(
                "APPDATA and LOCALAPPDATA are required for registration"
            )
        configuration = Path(app_data) / "PatchHarbor"
        locks = Path(local_app_data) / "PatchHarbor" / "locks"
    else:
        home_value = os.environ.get("HOME")
        if not home_value:
            raise _error("HOME is required for registration")
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
        raise _error(f"cannot create PatchHarbor user directory: {exc}") from exc

    return RegistrationUserPaths(
        configuration_directory=canonical_configuration,
        lock_directory=canonical_locks,
    )
