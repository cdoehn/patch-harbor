"""Canonical non-interactive Git command boundary."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from patchharbor.errors import PatchHarborError, repository_resolution_error


_REDIRECTING_GIT_ENVIRONMENT = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_DIR",
    "GIT_DIFF_OPTS",
    "GIT_EXTERNAL_DIFF",
    "GIT_GLOB_PATHSPECS",
    "GIT_ICASE_PATHSPECS",
    "GIT_INDEX_FILE",
    "GIT_LITERAL_PATHSPECS",
    "GIT_NAMESPACE",
    "GIT_NOGLOB_PATHSPECS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_WORK_TREE",
)

_CANONICAL_GIT_PREFIX = (
    "git",
    "--no-pager",
    "-c",
    "color.ui=false",
    "-c",
    "diff.external=",
    "-c",
    "diff.renames=false",
    "-c",
    "status.renames=false",
)


CANONICAL_DIFF_ARGUMENTS = (
    "--no-renames",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
)


def _error(message: str) -> PatchHarborError:
    return repository_resolution_error(message)


def _controlled_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in _REDIRECTING_GIT_ENVIRONMENT:
        environment.pop(name, None)
    environment.pop("GIT_CONFIG_PARAMETERS", None)
    environment.pop("GIT_CONFIG_COUNT", None)
    for name in tuple(environment):
        if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(name, None)
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
        }
    )
    return environment


def run_git_bytes(
    *arguments: str,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    accepted_returncodes: tuple[int, ...] = (0,),
) -> bytes:
    """Run one canonical Git query and return stdout unchanged."""
    command = [*_CANONICAL_GIT_PREFIX, *arguments]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=_controlled_environment(),
            stdin=subprocess.DEVNULL if input_bytes is None else None,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise _error("git executable is not available") from exc
    except OSError as exc:
        raise _error(f"cannot start git: {exc}") from exc

    if completed.returncode not in accepted_returncodes:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise _error(f"git query failed{suffix}")
    return completed.stdout


def nul_records(raw: bytes, description: str) -> tuple[bytes, ...]:
    """Split one NUL-terminated Git byte stream without decoding paths."""
    if not raw:
        return ()
    if not raw.endswith(b"\0"):
        raise _error(f"git returned malformed {description}")
    return tuple(raw[:-1].split(b"\0"))


def read_boolean_config(
    repository: Path,
    name: str,
    *,
    missing: bool = False,
) -> bool:
    """Read one Git boolean; an absent value has the specified default."""
    value = run_git_bytes(
        "config",
        "--bool",
        "--null",
        "--get",
        name,
        cwd=repository,
        accepted_returncodes=(0, 1),
    )
    if not value:
        return missing
    if value == b"true\0":
        return True
    if value == b"false\0":
        return False
    raise _error(f"git returned an invalid {name} value")
