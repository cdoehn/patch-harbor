"""Shared archive fixtures and behavior probes."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

from patchharbor.configuration import load_configuration
from patchharbor.configuration_context import configuration_paths_for_id
from patchharbor.registry import load_registry
from patchharbor.exchange import scan_exchange_directory
from patchharbor.user_paths import configuration_user_paths

from tests.platform_support import run_cli
from tests.registration_support import create_repository, git
from tests.exchange_support import _register_context
from tests.exchange_support import _configure_user, _write_custom_package


def _inputs(env, exchange, monkeypatch):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    paths = configuration_user_paths()
    registry = load_registry(paths)
    local = configuration_paths_for_id(registry.repositories[0].repo_id, registry)
    configuration = load_configuration(local)
    artifacts = scan_exchange_directory(exchange, paths=paths)
    return paths, configuration, artifacts

ARCHIVE = "PatchHarbor-Archive"


def _world(tmp_path):
    environment, exchange = _configure_user(tmp_path)
    repository = create_repository(tmp_path / "repo-a")
    context = _register_context(repository, environment)
    return environment, exchange, repository, context


def _bundle(repository, environment):
    completed = run_cli(repository, "bundle", "--json", environment_overrides=environment)
    assert completed.returncode == 0, completed.stderr
    return Path(json.loads(completed.stdout)["result"]["result_bundle_path"])


def _advance(repository, message="next state"):
    git(repository, "commit", "--allow-empty", "-m", message)


def _scan(repository, environment, *, automatic=False):
    arguments = ("--automatic",) if automatic else ()
    return run_cli(repository, "apply", "--json", *arguments, environment_overrides=environment)


def _committing_patch(path, context):
    _write_custom_package(
        path, context,
        posix_entrypoint="git commit --allow-empty -m archive-test >/dev/null",
        powershell_entrypoint="git commit --allow-empty -m archive-test; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
    )


def _rewrite(path, mutate):
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    mutate(files)
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
