"""Focused test support for repository-registration behavior."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run Git with deterministic text decoding in one test repository."""
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
    )


def create_repository(
    path: Path,
    *,
    with_commit: bool = True,
    object_format: str | None = None,
) -> Path:
    """Create one real repository suitable for registration tests."""
    path.mkdir()
    init_arguments = ["git", "init", "--quiet"]
    if object_format is not None:
        init_arguments.append(f"--object-format={object_format}")
    initialized = subprocess.run(
        init_arguments,
        cwd=path,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        check=False,
    )
    if initialized.returncode != 0:
        if object_format == "sha256":
            pytest.skip("installed Git does not support SHA-256 repositories")
        initialized.check_returncode()
    git(path, "config", "user.name", "PatchHarbor Test")
    git(path, "config", "user.email", "patchharbor@example.invalid")
    if with_commit:
        (path / "tracked.txt").write_bytes(b"base\n")
        git(path, "add", "tracked.txt")
        git(path, "commit", "--quiet", "-m", "base")
    return path


def isolated_user_environment(root: Path) -> dict[str, str]:
    """Return platform-native user directories isolated below ``root``."""
    if os.name == "nt":
        return {
            "APPDATA": str(root / "appdata"),
            "LOCALAPPDATA": str(root / "localappdata"),
        }
    return {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_STATE_HOME": str(root / "state"),
    }


def user_configuration_path(environment: dict[str, str]) -> Path:
    """Return the isolated shared config.json path for one test environment."""
    if os.name == "nt":
        return Path(environment["APPDATA"]) / "PatchHarbor" / "config.json"
    return Path(environment["XDG_CONFIG_HOME"]) / "patchharbor" / "config.json"


def configured_exchange_directory(environment: dict[str, str]) -> Path:
    """Read the canonical exchange directory from one test config.json."""
    document = json.loads(
        user_configuration_path(environment).read_text(encoding="utf-8")
    )
    return Path(document["exchange_directory"])


def exchange_state_path(environment: dict[str, str]) -> Path:
    """Return the shared persistent Exchange processing document."""
    if os.name == "nt":
        state = Path(environment["LOCALAPPDATA"]) / "PatchHarbor"
    else:
        state = Path(environment["XDG_STATE_HOME"]) / "patchharbor"
    return state / "exchange" / "state.json"


def write_exchange_configuration(
    environment: dict[str, str],
    directory: Path,
) -> Path:
    """Create one exact format-1 exchange configuration for subprocess tests."""
    directory.mkdir(parents=True, exist_ok=True)
    canonical = directory.resolve()
    path = user_configuration_path(environment)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "exchange_directory": str(canonical),
                "format_version": 1,
            },
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return canonical


def set_isolated_user_environment(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> None:
    """Install isolated registration user paths for an in-process test."""
    for name, value in isolated_user_environment(root).items():
        monkeypatch.setenv(name, value)


def local_exclude_path(repository: Path) -> Path:
    """Resolve Git's repository-local exclude file physically."""
    raw = git(
        repository,
        "rev-parse",
        "--git-path",
        "info/exclude",
    ).stdout.strip()
    path = Path(raw)
    if not path.is_absolute():
        path = repository / path
    return path.resolve()


_REPOSITORY_LOCK_HOLDER_PROGRAM = r"""
import sys

from patchharbor.models import RepositoryId
from patchharbor.locks import repository_lock
from patchharbor.user_paths import registration_user_paths

repo_id = RepositoryId(sys.argv[1])
mode = sys.argv[2]
with repository_lock(registration_user_paths(), repo_id):
    print("ready", flush=True)
    if sys.stdin.buffer.read(1) != b"x":
        raise RuntimeError("release token missing")
    if mode == "error":
        raise RuntimeError("expected holder failure")
"""


_REPOSITORY_LOCK_PROBE_PROGRAM = r"""
import sys

from patchharbor.errors import PatchHarborError
from patchharbor.models import RepositoryId
from patchharbor.locks import repository_lock
from patchharbor.user_paths import registration_user_paths

try:
    with repository_lock(
        registration_user_paths(),
        RepositoryId(sys.argv[1]),
    ):
        pass
except PatchHarborError as exc:
    raise SystemExit(int(exc.exit_code))
"""


def start_repository_lock_holder(
    repo_id: str,
    *,
    environment: dict[str, str],
    mode: str = "normal",
) -> subprocess.Popen[str]:
    """Start one synchronized process holding the repository lock."""
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _REPOSITORY_LOCK_HOLDER_PROGRAM,
            repo_id,
            mode,
        ],
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="strict",
    )
    assert holder.stdout is not None
    assert holder.stdout.readline() == "ready\n"
    return holder


def release_repository_lock_holder(holder: subprocess.Popen[str]) -> int:
    """Release a synchronized holder and return its process exit code."""
    assert holder.stdin is not None
    holder.stdin.write("x")
    holder.stdin.flush()
    holder.stdin.close()
    return holder.wait(timeout=10)


def stop_repository_lock_holder(holder: subprocess.Popen[str]) -> None:
    """Ensure a lock-holder process cannot survive a failed test."""
    if holder.poll() is None:
        holder.kill()
        holder.wait(timeout=10)


def probe_repository_lock(repo_id: str, environment: dict[str, str]) -> int:
    """Try one immediate repository lock acquisition in a real process."""
    completed = subprocess.run(
        [sys.executable, "-c", _REPOSITORY_LOCK_PROBE_PROGRAM, repo_id],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        timeout=10,
        check=False,
    )
    return completed.returncode


_REGISTRY_LOCK_HOLDER_PROGRAM = r"""
import sys

from patchharbor.locks import registry_lock
from patchharbor.user_paths import registration_user_paths

mode = sys.argv[1]
with registry_lock(registration_user_paths()):
    print("ready", flush=True)
    if sys.stdin.buffer.read(1) != b"x":
        raise RuntimeError("release token missing")
    if mode == "error":
        raise RuntimeError("expected holder failure")
"""


_REGISTRY_LOCK_PROBE_PROGRAM = r"""
from patchharbor.errors import PatchHarborError
from patchharbor.locks import registry_lock
from patchharbor.user_paths import registration_user_paths

try:
    with registry_lock(registration_user_paths()):
        pass
except PatchHarborError as exc:
    raise SystemExit(int(exc.exit_code))
"""


def start_registry_lock_holder(
    *,
    environment: dict[str, str],
    mode: str = "normal",
) -> subprocess.Popen[str]:
    """Start one synchronized process holding the global registry lock."""
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _REGISTRY_LOCK_HOLDER_PROGRAM,
            mode,
        ],
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="strict",
    )
    assert holder.stdout is not None
    assert holder.stdout.readline() == "ready\n"
    return holder


def release_registry_lock_holder(holder: subprocess.Popen[str]) -> int:
    """Release a synchronized registry-lock holder."""
    return release_repository_lock_holder(holder)


def stop_registry_lock_holder(holder: subprocess.Popen[str]) -> None:
    """Ensure a registry-lock holder cannot survive a failed test."""
    stop_repository_lock_holder(holder)


def probe_registry_lock(environment: dict[str, str]) -> int:
    """Try one immediate global registry-lock acquisition in a real process."""
    completed = subprocess.run(
        [sys.executable, "-c", _REGISTRY_LOCK_PROBE_PROGRAM],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="strict",
        timeout=10,
        check=False,
    )
    return completed.returncode
