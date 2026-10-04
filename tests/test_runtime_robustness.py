"""Provenance, bounded reads and concurrent request ownership."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import io
import json
from threading import Barrier
from zipfile import ZipFile

import pytest

from patchharbor import runtime_artifact as provider_module
from patchharbor import runtime_wheel as runtime
from patchharbor.runtime_artifact import RuntimeProvider
from tests.test_runtime_artifact import prepared, _capture, _provider_tree, _recipe, _rewrite_recipe


def test_loaded_producer_rejects_coherent_same_version_replacement(prepared, tmp_path):
    provider = _provider_tree(prepared, tmp_path)
    pinned = provider.capture()
    pending = RuntimeProvider()
    pending._root, pending._producer_id = provider._root, provider._producer_id
    recipe = _recipe(prepared)
    payloads = {entry.path: prepared[entry.source] for entry in recipe.entries}
    payloads[runtime.CHAT_PATH] += b"\nUpdated producer template.\n"
    initial = runtime.prepare_recipe(payloads, version=recipe.version, requires_python=recipe.requires_python)
    payloads[runtime.IDENTITY_PATH] = runtime.identity_module(runtime.producer_id(initial))
    changed = runtime.prepare_recipe(payloads, version=recipe.version, requires_python=recipe.requires_python)
    payloads[runtime.RECIPE_PATH] = changed.data
    next_process = _provider_tree(payloads, tmp_path)
    assert pending.capture().reason == "source_changed"
    assert pending.capture().artifact is None
    assert provider.capture() is pinned
    assert pinned.artifact.chat_template == prepared[runtime.CHAT_PATH]
    current = next_process.capture()
    assert current.status == "embedded"
    assert current.artifact.recipe.version == pinned.artifact.recipe.version
    assert current.artifact.recipe.content_id != pinned.artifact.recipe.content_id
    assert current.artifact.wheel_sha256 != pinned.artifact.wheel_sha256
    assert current.artifact.chat_template == payloads[runtime.CHAT_PATH]
    with pytest.raises(FrozenInstanceError):
        pinned.artifact.wheel_sha256 = "changed"


def test_installation_directory_named_src_is_supported(prepared, tmp_path):
    assert _provider_tree(prepared, tmp_path / "src").capture().status == "embedded"


@pytest.mark.parametrize("cache", ["absent", "corrupt"])
def test_concurrent_requests_need_no_cache_or_temporary_files(prepared, tmp_path, monkeypatch, cache):
    provider = _provider_tree(prepared, tmp_path / "installation")
    cache_path = tmp_path / "cache"
    if cache == "corrupt":
        cache_path.write_bytes(b"not a directory or valid cache")
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_path))
    monkeypatch.setenv("TMPDIR", str(cache_path))
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    calls = []
    original = provider_module.materialize
    def counted(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(provider_module, "materialize", counted)
    barrier = Barrier(8)
    def capture(_):
        barrier.wait(timeout=30)
        return provider.capture()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(capture, range(8)))
    assert results[0].status == "embedded"
    assert all(result is results[0] for result in results) and len(calls) == 1
    def independent(_):
        other = RuntimeProvider()
        other._root, other._producer_id = provider._root, provider._producer_id
        return other.capture()
    with ThreadPoolExecutor(max_workers=4) as pool:
        separate = list(pool.map(independent, range(4)))
    assert all(result == results[0] and result is not results[0] for result in separate)
    assert len(calls) == 5
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("budget", ["MAX_WHEEL_BYTES", "MAX_CONTENT_BYTES"])
def test_exact_archive_budget_includes_record_before_any_resource_read(prepared, monkeypatch, budget):
    recipe = _recipe(prepared)
    raw = _capture(prepared)
    with ZipFile(io.BytesIO(raw)) as wheel:
        size = len(raw) if budget == "MAX_WHEEL_BYTES" else sum(info.file_size for info in wheel.infolist())
    monkeypatch.setattr(runtime, budget, size)
    assert _capture(prepared) == raw
    monkeypatch.setattr(runtime, budget, size - 1)
    def forbidden(*args):
        pytest.fail("over-budget recipe caused a resource read")
    with pytest.raises(runtime.RuntimeLimitError):
        runtime.materialize(recipe, forbidden)


@pytest.mark.parametrize("field,value", [("version", "9.9"), ("entries", ()), ("content_id", "0" * 64)])
def test_constructed_recipe_cannot_bypass_validated_bytes(prepared, field, value):
    recipe = replace(_recipe(prepared), **{field: value})
    def forbidden(*args):
        pytest.fail("forged recipe caused a resource read")
    with pytest.raises(runtime.RuntimeDataError):
        runtime.materialize(recipe, forbidden)


@pytest.mark.parametrize("paths", [("patchharbor/Branch/a.py", "patchharbor/branch/b.py"),
                                  ("patchharbor/A.py", "patchharbor/a.py")])
def test_case_ambiguous_inventory_is_not_portable(prepared, paths):
    doc = json.loads(prepared[runtime.RECIPE_PATH])
    for name in paths:
        doc["entries"].append({"path": name, "source": name, "size": 0, "sha256": runtime.sha256(b"")})
    doc["entries"].sort(key=lambda entry: entry["path"])
    with pytest.raises(runtime.RuntimeDataError):
        runtime.parse_recipe(_rewrite_recipe(doc))


def test_rehashed_identity_module_is_data_not_executed_code(prepared, tmp_path):
    recipe = _recipe(prepared)
    payloads = {entry.path: prepared[entry.source] for entry in recipe.entries}
    payloads[runtime.IDENTITY_PATH] = b"raise AssertionError('must never execute described code')\n"
    changed = runtime.prepare_recipe(payloads, version=recipe.version, requires_python=recipe.requires_python)
    payloads[runtime.RECIPE_PATH] = changed.data
    result = _provider_tree(payloads, tmp_path).capture()
    assert result.status == "unavailable" and result.reason == "resources_invalid"


@pytest.mark.parametrize("failure", [RuntimeError("programming error"), KeyboardInterrupt(), SystemExit(9)])
def test_unexpected_errors_and_cancellation_are_visible_and_release_lock(prepared, tmp_path, monkeypatch, failure):
    provider = _provider_tree(prepared, tmp_path)
    original = provider._read
    def broken(*args):
        raise failure
    monkeypatch.setattr(provider, "_read", broken)
    with pytest.raises(type(failure)):
        provider.capture()
    monkeypatch.setattr(provider, "_read", original)
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(provider.capture).result(timeout=30).status == "embedded"


def test_parent_directory_replaced_during_resource_read_is_rejected(prepared, tmp_path, monkeypatch):
    provider = _provider_tree(prepared, tmp_path)
    original = provider_module.read_stable_regular_file_bounded
    def replaced(path, **kwargs):
        result = original(path, **kwargs)
        if path.name == "recipe.json":
            old = path.parent.with_name("saved-runtime")
            path.parent.rename(old)
            path.parent.mkdir()
        return result
    monkeypatch.setattr(provider_module, "read_stable_regular_file_bounded", replaced)
    assert provider.capture().reason == "resources_invalid"


@pytest.mark.parametrize("raw", [b'{"marker":1,"marker":2}', b'{"marker":NaN}', b'[' * 2000])
def test_invalid_json_never_reaches_resource_reads(prepared, tmp_path, raw):
    provider = _provider_tree(prepared, tmp_path)
    (tmp_path / runtime.RECIPE_PATH).write_bytes(raw)
    assert provider.capture().reason == "resources_invalid"


def test_unavailable_capture_is_pinned_per_request(prepared, tmp_path):
    provider = _provider_tree(prepared, tmp_path)
    target = tmp_path / runtime.CHAT_PATH
    target.unlink()
    result = provider.capture()
    assert result.reason == "resources_missing"
    target.write_bytes(prepared[runtime.CHAT_PATH])
    assert provider.capture() is result
    assert _provider_tree(prepared, tmp_path).capture().status == "embedded"


@pytest.mark.parametrize("requirement", ["garbage", "3.12", ">=", "~=3", "~=3.dev1", ">=3.*", ">=3.12,", "==3.*.*"])
def test_invalid_python_requirement_is_rejected(prepared, requirement):
    doc = json.loads(prepared[runtime.RECIPE_PATH])
    doc["requires_python"] = requirement
    with pytest.raises(runtime.RuntimeDataError):
        runtime.parse_recipe(_rewrite_recipe(doc))


@pytest.mark.parametrize("requirement", [">=3.12", ">=3.12, <4", "~=3.12", "==3.12.*", "!=3.13.0rc1"])
def test_supported_python_requirement_profile(prepared, requirement):
    doc = json.loads(prepared[runtime.RECIPE_PATH])
    doc["requires_python"] = requirement
    assert runtime.parse_recipe(_rewrite_recipe(doc)).requires_python == requirement


def test_oversized_installed_recipe_is_a_resource_limit(prepared, tmp_path):
    provider = _provider_tree(prepared, tmp_path)
    (tmp_path / runtime.RECIPE_PATH).write_bytes(b" " * (runtime.MAX_RECIPE_BYTES + 1))
    assert provider.capture().reason == "resource_limit"
