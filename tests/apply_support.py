"""Shared apply fixtures and behavior probes."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile
from zipfile import ZipFile

import pytest

from patchharbor import api

from tests.platform_support import native_script, native_value
from tests.registration_support import create_repository


def write_package(path: Path, context: api.RepositoryContext, *, exit_code: int = 0) -> None:
    entrypoint = native_value("run.sh", "run.ps1")
    manifest = {
        "marker": "patch-harbor", "format_version": 1,
        "repo_id": str(context.repo_id), "base_commit": str(context.base_commit),
        "state_fingerprint": context.state_fingerprint,
        "fingerprint_algorithm": context.fingerprint_algorithm, "entrypoint": entrypoint,
    }
    body = native_script(
        f"printf 'api-child\\n'; printf 'api-stderr\\n' >&2; exit {exit_code}",
        f"[Console]::Out.WriteLine('api-child'); [Console]::Error.WriteLine('api-stderr'); exit {exit_code}",
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps(manifest))
        archive.writestr(entrypoint, body)


@pytest.fixture
def repository(tmp_path):
    repository = create_repository(tmp_path / "foreign-project")
    api.register(repository)
    exchange = tmp_path / "exchange"
    api.configure_exchange_directory(exchange, repository=repository)
    return repository, exchange


def package(repository, exchange, *, exit_code=0):
    context = api.context(repository)
    entrypoint = native_value("run.sh", "run.ps1")
    manifest = {"marker": "patch-harbor", "format_version": 1,
                **{key: str(getattr(context, key)) for key in
                   ("repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm")},
                "entrypoint": entrypoint}
    path = exchange / "test-patch.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("patch.json", json.dumps(manifest))
        archive.writestr(entrypoint, native_script(f"exit {exit_code}", f"exit {exit_code}"))
    return path
