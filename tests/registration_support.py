"""Focused test support for repository-registration behavior."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

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


def create_repository(path: Path, *, with_commit: bool = True) -> Path:
    """Create one real repository suitable for registration tests."""
    path.mkdir()
    git(path, "init", "--quiet")
    git(path, "config", "user.name", "PatchHarbor Test")
    git(path, "config", "user.email", "patchharbor@example.invalid")
    if with_commit:
        (path / "tracked.txt").write_text("base\n", encoding="utf-8")
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
