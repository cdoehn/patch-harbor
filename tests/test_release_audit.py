"""Machine-readable installation declarations; built artifacts are checked in E2E."""
from __future__ import annotations

from importlib import import_module
try:
    import tomllib
except ModuleNotFoundError:  # Explicit build/dev dependency on Python 3.10 only.
    import tomli as tomllib

from tests.platform_support import PROJECT_ROOT


def test_release_entry_point_and_runtime_dependency_contract_are_exact() -> None:
    configuration = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = configuration["project"]
    assert project["scripts"] == {
        "patchharbor": "patchharbor.cli:main",
        "patchharbor-watcher": "patchharbor_watcher.cli:main",
    }
    for target in project["scripts"].values():
        module, function = target.split(":")
        assert callable(getattr(import_module(module), function))
    assert project["dependencies"] == []
    assert configuration["tool"]["setuptools"]["data-files"] == {
        "share/patchharbor": ["CHAT_INSTRUCTIONS.md", "docs/python-api.md"]
    }
    for resources in configuration["tool"]["setuptools"]["data-files"].values():
        for resource in resources:
            assert (PROJECT_ROOT / resource).read_text(encoding="utf-8")
    assert configuration["build-system"]["build-backend"] == "build_backend"
    assert configuration["build-system"]["backend-path"] == ["."]
