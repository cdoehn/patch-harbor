"""Opt-in prepared producer for archive/recovery proofs that require no warnings.

Source-checkout Result tests deliberately keep their unavailable-runtime path.
These fixtures use resources from a real build, with the same source code as the
in-process tests, and route child CLIs through that built distribution too.
"""
from __future__ import annotations

import subprocess
import sys
from zipfile import ZipFile

import pytest

from patchharbor import result_resources
from patchharbor.runtime_artifact import RuntimeProvider
from patchharbor.runtime_wheel import RECIPE_PATH, parse_recipe, producer_id
from scripts.build_release import _copy_release_inputs
from tests import platform_support


@pytest.fixture(scope="session")
def built_result_source(tmp_path_factory):
    root = tmp_path_factory.mktemp("result-producer")
    source, output, installed = root / "source", root / "dist", root / "installed"
    source.mkdir()
    _copy_release_inputs(source)
    build = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(output)],
        cwd=source, capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    # A trusted locally built fixture, never an untrusted Result wheel.
    with ZipFile(next(output.glob("*.whl"))) as wheel:
        wheel.extractall(installed)
    return installed


@pytest.fixture
def unavailable_result_producer(monkeypatch):
    """Select the source fallback explicitly, including inside installed tests."""
    def provider():
        captured = RuntimeProvider()
        captured._producer_id = None
        return captured

    assert provider().capture().reason == "source_not_prepared"
    monkeypatch.setattr(result_resources, "RuntimeProvider", provider)


@pytest.fixture
def prepared_result_producer(built_result_source, monkeypatch):
    identity = producer_id(parse_recipe((built_result_source / RECIPE_PATH).read_bytes()))

    def provider():
        captured = RuntimeProvider()
        captured._root = built_result_source
        captured._producer_id = identity
        return captured

    assert provider().capture().status == "embedded"
    monkeypatch.setattr(result_resources, "RuntimeProvider", provider)
    monkeypatch.setattr(platform_support, "CLI_SOURCE_PATH", built_result_source)
    return built_result_source
