"""Behavioral checks for prepared resources and the canonical wheel contract."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile, ZIP_STORED

import pytest

from patchharbor.runtime_artifact import RuntimeProvider
from patchharbor import runtime_wheel as runtime
from patchharbor.platform.filesystem import FileReadLimitExceeded, read_stable_regular_file_bounded
from scripts.build_release import _copy_release_inputs


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp("runtime-build")
    source, output = root / "source", root / "dist"
    source.mkdir()
    _copy_release_inputs(source)
    completed = subprocess.run([sys.executable, "-m", "build", "--wheel", "--sdist", "--no-isolation",
                                "--outdir", str(output)], cwd=source, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    with ZipFile(next(output.glob("*.whl"))) as wheel:
        payloads = {name: wheel.read(name) for name in wheel.namelist()}
    return payloads


def _recipe(payloads):
    return runtime.parse_recipe(payloads[runtime.RECIPE_PATH])


def _capture(payloads):
    return runtime.materialize(_recipe(payloads), lambda name, size: payloads[name])


def _rewrite_recipe(document):
    unsigned = {key: value for key, value in document.items() if key != "content_id"}
    encode = lambda doc: (json.dumps(doc, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
    document["content_id"] = runtime.sha256(encode(unsigned))
    return encode(document)


def test_canonical_archive_has_complete_valid_record_and_no_recursion(prepared):
    raw = _capture(prepared)
    assert raw == _capture(prepared)
    recipe = _recipe(prepared)
    assert runtime.sha256(raw) != recipe.content_id
    with ZipFile(io.BytesIO(raw)) as wheel:
        names = wheel.namelist()
        assert names == sorted(names, key=lambda name: (name.startswith(recipe.dist_info + "/"), name))
        assert set(names) == {entry.path for entry in recipe.entries} | {runtime.RECIPE_PATH, recipe.dist_info + "/RECORD"}
        assert all(info.compress_type == ZIP_STORED and info.date_time == (1980, 1, 1, 0, 0, 0)
                   and info.external_attr == 0o100644 << 16 and not info.extra for info in wheel.infolist())
        assert not any(name.endswith((".whl", ".pyc", ".pth")) or ".data/" in name for name in names)
        records = list(csv.reader(io.StringIO(wheel.read(recipe.dist_info + "/RECORD").decode())))
        assert len(records) == len(names)
        assert {row[0] for row in records} == set(names)
        for name, digest, size in records:
            if name.endswith("/RECORD"):
                assert (digest, size) == ("", "")
            else:
                data = wheel.read(name)
                assert int(size) == len(data)
                assert digest == "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        # A second generation reads the recipe and its sources from the wheel,
        # not installer RECORD or the original setuptools transport.
        assert runtime.materialize(runtime.parse_recipe(wheel.read(runtime.RECIPE_PATH)),
                                   lambda name, size: wheel.read(name)) == raw


@pytest.mark.parametrize("name", ["patchharbor/api.py", runtime.CHAT_PATH,
                                  "patchharbor/_runtime/metadata/METADATA"])
def test_modified_resource_is_rejected(prepared, name):
    corrupted = dict(prepared)
    corrupted[name] += b"changed"
    with pytest.raises(runtime.RuntimeDataError):
        _capture(corrupted)


@pytest.mark.parametrize("target", ["../escape.py", "/tmp/escape.py", "foreign.py", "foreign/a.py",
                                   "patchharbor/evil.pth", "patchharbor/native.so", "patchharbor/__pycache__/x.py",
                                   "patchharbor/sitecustomize.py", "patchharbor/CON.py", "patchharbor/x./a.py",
                                   "patchharbor/_runtime/earlier.whl", "patchharbor-1.2.1.dist-info/INSTALLER"])
def test_untrusted_inventory_paths_are_rejected_before_read(prepared, target):
    doc = json.loads(prepared[runtime.RECIPE_PATH])
    doc["entries"][0]["path"] = target
    with pytest.raises(runtime.RuntimeDataError):
        runtime.parse_recipe(_rewrite_recipe(doc))


@pytest.mark.parametrize("field,value", [("format_version", True), ("format_version", 2),
                                        ("content_id", "0" * 64), ("unknown", "x"),
                                        ("version", "../1.0"), ("source_commit", "abc")])
def test_recipe_closed_schema_and_identity(prepared, field, value):
    doc = json.loads(prepared[runtime.RECIPE_PATH])
    doc[field] = value
    with pytest.raises(runtime.RuntimeDataError):
        runtime.parse_recipe((json.dumps(doc) + "\n").encode())


@pytest.mark.parametrize("mutation", ["bool_size", "negative_size", "oversize", "duplicate", "missing", "mapping"])
def test_recipe_inventory_and_budget(prepared, mutation):
    doc = json.loads(prepared[runtime.RECIPE_PATH])
    if mutation == "bool_size":
        doc["entries"][0]["size"] = True
    elif mutation == "negative_size":
        doc["entries"][0]["size"] = -1
    elif mutation == "oversize":
        doc["entries"][0]["size"] = runtime.MAX_CONTENT_BYTES + 1
    elif mutation == "duplicate":
        doc["entries"].append(doc["entries"][0])
    elif mutation == "missing":
        doc["entries"] = [entry for entry in doc["entries"] if entry["path"] != runtime.CHAT_PATH]
    else:
        doc["entries"][0]["source"] = "patchharbor/api.py"
    with pytest.raises(runtime.RuntimeDataError):
        runtime.parse_recipe(_rewrite_recipe(doc))


def test_content_id_covers_changed_code_of_same_version(prepared):
    recipe = _recipe(prepared)
    payloads = {entry.path: prepared[entry.source] for entry in recipe.entries}
    payloads["patchharbor/api.py"] += b"\n# different build\n"
    other = runtime.prepare_recipe(payloads, version=recipe.version, requires_python=recipe.requires_python)
    assert other.version == recipe.version
    assert other.content_id != recipe.content_id


def _provider_tree(prepared, root):
    for entry in _recipe(prepared).entries:
        path = root / entry.source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(prepared[entry.source])
    (root / runtime.RECIPE_PATH).write_bytes(prepared[runtime.RECIPE_PATH])
    provider = RuntimeProvider()
    provider._root = root
    provider._producer_id = runtime.producer_id(_recipe(prepared))
    return provider


def test_request_pins_once_and_fresh_request_rejects_changed_installation(prepared, tmp_path, monkeypatch):
    provider = _provider_tree(prepared, tmp_path)
    calls = []
    original = provider._read
    def read(name, size):
        calls.append(name)
        return original(name, size)
    monkeypatch.setattr(provider, "_read", read)
    result = provider.capture()
    assert result.status == "embedded" and result.reason is None
    count = len(calls)
    (tmp_path / "patchharbor/api.py").write_bytes(b"changed")
    assert provider.capture() is result and len(calls) == count
    other = RuntimeProvider()
    other._root = tmp_path
    other._producer_id = provider._producer_id
    assert other.capture().reason == "resources_invalid"
    assert result.artifact.chat_template == prepared[runtime.CHAT_PATH]


@pytest.mark.parametrize("missing", [runtime.RECIPE_PATH, "patchharbor/api.py"])
def test_missing_resource_produces_structured_unavailable(prepared, tmp_path, missing):
    provider = _provider_tree(prepared, tmp_path)
    (tmp_path / missing).unlink()
    result = provider.capture()
    assert result.status == "unavailable" and result.artifact is None
    assert result.reason == "resources_missing"


def test_source_mode_does_not_build_or_search_caches():
    provider = RuntimeProvider()
    assert provider.capture().reason == "source_not_prepared"


def test_recipe_size_limit_precedes_parsing():
    with pytest.raises(runtime.RuntimeLimitError):
        runtime.parse_recipe(b" " * (runtime.MAX_RECIPE_BYTES + 1))


@pytest.mark.parametrize("change", ["dependency", "entrypoint", "python", "wheel_tag"])
def test_consistently_rehashed_but_incompatible_metadata_is_rejected(prepared, change):
    recipe = _recipe(prepared)
    payloads = {entry.path: prepared[entry.source] for entry in recipe.entries}
    name = recipe.dist_info + "/METADATA"
    if change == "dependency":
        payloads[name] = b"Requires-Dist: requests\n" + payloads[name]
    elif change == "python":
        payloads[name] = payloads[name].replace(b"Requires-Python: >=3.12", b"Requires-Python: >=3.15")
    elif change == "entrypoint":
        name = recipe.dist_info + "/entry_points.txt"
        payloads[name] += b"evil = foreign:main\n"
    else:
        name = recipe.dist_info + "/WHEEL"
        payloads[name] = payloads[name].replace(b"py3-none-any", b"py3-none-win_amd64")
    payloads[runtime.RESOURCE_ROOT + "metadata/" + name.split("/", 1)[1]] = payloads[name]
    modified = runtime.prepare_recipe(payloads, version=recipe.version, requires_python=recipe.requires_python)
    with pytest.raises(runtime.RuntimeDataError):
        runtime.materialize(modified, lambda name, size: payloads[name])


def test_provider_does_not_write_or_start_processes(prepared, tmp_path, monkeypatch):
    provider = _provider_tree(prepared, tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    original_open = os.open
    def readonly(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return original_open(path, flags, *args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail("provider started an external process")
    monkeypatch.setattr(os, "open", readonly)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert provider.capture().status == "embedded"
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("data,limit", [(b"", 0), (b"abc", 3), (b"abc", 2)])
def test_bounded_native_file_reader(data, limit, tmp_path):
    path = tmp_path / "resource"
    path.write_bytes(data)
    if len(data) > limit:
        with pytest.raises(FileReadLimitExceeded):
            read_stable_regular_file_bounded(path, max_bytes=limit)
    else:
        assert read_stable_regular_file_bounded(path, max_bytes=limit).content == data


def test_runtime_symlink_is_unavailable(prepared, tmp_path):
    provider = _provider_tree(prepared, tmp_path)
    path = tmp_path / "patchharbor/api.py"
    original = tmp_path / "saved-code"
    path.rename(original)
    try:
        path.symlink_to(original)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    result = provider.capture()
    assert result.status == "unavailable" and result.reason == "resources_invalid"
