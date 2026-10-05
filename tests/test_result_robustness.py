"""Bounded malformed inputs and real mixed-version/legacy Exchange behavior."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from zipfile import ZipFile

import pytest

from patchharbor import api, result_runtime
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.exchange import ExchangeArtifactKind, _classify_content
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import read_result_reference
from tests.platform_support import PROJECT_ROOT, project_environment, run_cli
from tests.result_runtime_support import attach_runtime, format2_entries, replace_wheel
from tests.test_reference_validation import edit_document, write_reference
from tests.test_result_format2 import canonical
from tests.test_runtime_artifact import prepared


@pytest.mark.parametrize("fault", ["entries", "forged_count", "count_mismatch", "disk",
                                    "name_length", "extra", "comment", "directory_size", "directory_offset"])
def test_inner_directory_is_bounded_before_zipfile_allocates_members(canonical, tmp_path, monkeypatch, fault):
    raw = bytearray(canonical)
    end = len(raw) - 22
    count = struct.unpack_from("<H", raw, end + 10)[0]
    offset = struct.unpack_from("<I", raw, end + 16)[0]
    if fault in {"entries", "forged_count", "count_mismatch"}:
        count = {"entries": 1001, "forged_count": 1, "count_mismatch": count + 1}[fault]
        struct.pack_into("<HH", raw, end + 8, count, count)
    elif fault == "disk": struct.pack_into("<H", raw, end + 4, 1)
    elif fault == "name_length": struct.pack_into("<H", raw, offset + 28, 513)
    elif fault == "extra": struct.pack_into("<H", raw, offset + 30, 1)
    elif fault == "comment": struct.pack_into("<H", raw, offset + 32, 1)
    elif fault == "directory_size": struct.pack_into("<I", raw, end + 12, 2**32 - 1)
    elif fault == "directory_offset": struct.pack_into("<I", raw, end + 16, 2**32 - 1)
    files, _ = format2_entries(canonical)
    replace_wheel(files, bytes(raw))
    path = tmp_path / "result.zip"; write_reference(path, files)
    monkeypatch.setattr(result_runtime, "ZipFile", lambda *a, **k: pytest.fail("unbounded directory allocated ZipInfo objects"))
    with pytest.raises(api.PatchHarborError) as caught:
        read_result_reference(path)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR


@pytest.mark.parametrize("limit", ["wheel", "recipe"])
def test_wheel_and_recipe_limits_precede_their_reads(canonical, tmp_path, monkeypatch, limit):
    files, _ = format2_entries(canonical)
    path = tmp_path / "result.zip"; write_reference(path, files)
    if limit == "wheel":
        monkeypatch.setattr(result_runtime.wheel, "MAX_WHEEL_BYTES", len(canonical) - 1)
        monkeypatch.setattr(result_runtime, "ZipFile", lambda *a, **k: pytest.fail("oversize wheel opened"))
    else:
        with ZipFile(BytesIO(canonical)) as archive:
            recipe_size = archive.getinfo(result_runtime.wheel.RECIPE_PATH).file_size
        monkeypatch.setattr(result_runtime.wheel, "MAX_RECIPE_BYTES", recipe_size - 1)
        original = result_runtime._read_wheel
        def guarded(*args, **kwargs):
            with monkeypatch.context() as guard:
                guard.setattr(ZipFile, "read", lambda *a, **k: pytest.fail("oversize recipe read"))
                return original(*args, **kwargs)
        monkeypatch.setattr(result_runtime, "_read_wheel", guarded)
    with pytest.raises(api.PatchHarborError): read_result_reference(path)


@pytest.mark.parametrize("unicode_path", [False, True])
def test_deep_json_cannot_abort_exchange_classification(tmp_path, monkeypatch, unicode_path):
    files, _ = format2_entries(None)
    files["manifest.json"] = (b'{"marker":"patch-harbor-result-bundle","nested":' +
                              b'[' * 2000 + b'0' + b']' * 2000 + b'}')
    if unicode_path: files["base/Grüße.txt"] = files.pop("base/tracked.txt")
    path = tmp_path / "input.zip"; write_reference(path, files)
    # Interpreter recursion thresholds differ; a type hint is permissible, an
    # executable candidate is not. Exercise the overflow boundary explicitly too.
    assert _classify_content(path, path.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY).kind is not ExchangeArtifactKind.PATCH_PACKAGE
    with pytest.raises(api.PatchHarborError): read_result_reference(path)
    def overflow(*args, **kwargs): raise RecursionError("JSON nesting limit")
    monkeypatch.setattr(json, "loads", overflow)
    assert _classify_content(path, path.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY).kind is ExchangeArtifactKind.OTHER


@pytest.mark.parametrize("fault", ["duplicate", "case_file", "case_directory", "extra_wheel", "nested_archive", "traversal", "both_markers"])
def test_outer_runtime_inventory_failures_never_become_patch_candidates(canonical, tmp_path, fault):
    from tests.test_patch_inspection import MANIFEST
    files, _ = format2_entries(canonical)
    if fault == "case_file": files["runtime/Runtime.json"] = files["runtime/runtime.json"]
    elif fault == "case_directory": files["Runtime/other.txt"] = b"ambiguous directory"
    elif fault == "extra_wheel": files["runtime/second.whl"] = canonical
    elif fault == "nested_archive": files["runtime/nested.zip"] = canonical
    elif fault == "traversal": files["runtime/../outside.py"] = b"bad"
    elif fault == "both_markers":
        files["patch.json"] = json.dumps(MANIFEST).encode()
        files["run.sh"] = b"# PATCHHARBOR\n"
    path = tmp_path / "input.zip"; write_reference(path, files)
    if fault == "duplicate":
        with ZipFile(path, "a") as archive, pytest.warns(UserWarning):
            archive.writestr("runtime/runtime.json", files["runtime/runtime.json"])
    assert _classify_content(path, path.read_bytes(), resource_policy=DEFAULT_RESOURCE_POLICY).kind is not ExchangeArtifactKind.PATCH_PACKAGE
    with pytest.raises(api.PatchHarborError): read_result_reference(path)
    # The archive boundary rejects instead of downgrading corrupt runtime data
    # to a successfully checked unavailable reference.
    from patchharbor.zip_payloads import ZipPayloadError
    with pytest.raises((ValueError, KeyError, ZipPayloadError)):
        parse_archive_evidence(path.read_bytes(), path)


@pytest.fixture(scope="module")
def legacy_source(tmp_path_factory):
    root = tmp_path_factory.mktemp("frozen-result-reader")
    shutil.copytree(PROJECT_ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
    fixtures = Path(__file__).parent / "fixtures/result_format1"
    provenance = json.loads((fixtures / "provenance.json").read_bytes())
    for name, record in provenance["files"].items():
        raw = (fixtures / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"]
        (root / record["source_path"]).write_bytes(raw)
    return root / "src", provenance


@pytest.mark.e2e
@pytest.mark.parametrize("reader", ["current", "frozen_format1"])
@pytest.mark.parametrize("state", ["embedded", "unavailable", "corrupt", "future"])
def test_mixed_exchange_uses_actual_current_and_frozen_reader_decisions(canonical, legacy_source, tmp_path, reader, state):
    from tests.test_exchange_archive_e2e import _world, _bundle, _advance, ARCHIVE
    from tests.registration_support import git
    env, exchange, repo, _ = _world(tmp_path)
    old = _bundle(repo, env)
    with ZipFile(old) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    files = attach_runtime(files, None if state == "unavailable" else canonical)
    if state == "corrupt": files["runtime/runtime.json"] += b"corrupt"
    elif state == "future": edit_document(files, "manifest.json", lambda d: d.update(format_version=3))
    result = exchange / "result-disguised-as-patch.zip"; write_reference(result, files)
    wheel = exchange / "wheel-disguised-as-patch.zip"; wheel.write_bytes(canonical)
    before = {p: p.read_bytes() for p in (old, result, wheel)}
    _advance(repo)
    head = git(repo, "rev-parse", "HEAD").stdout
    if reader == "frozen_format1":
        source, provenance = legacy_source
        env = {**env, "PYTHONPATH": str(source)}
        # Prove that the child uses the frozen code, not an installed/current
        # module accidentally shadowing the fixture through PYTHONPATH.
        probe = subprocess.run([sys.executable, "-c", """
import hashlib, json
from pathlib import Path
import patchharbor.result_reader as reader
import patchharbor.exchange as exchange
import patchharbor.archive_evidence as archive
print(json.dumps({Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                  for m in (reader, exchange, archive)}))
"""], cwd=repo, env=project_environment(env), capture_output=True, text=True)
        assert probe.returncode == 0, probe.stderr
        assert json.loads(probe.stdout) == {name: row["sha256"] for name, row in provenance["files"].items()}
    scanned = run_cli(repo, "apply", "--json", environment_overrides=env)
    assert scanned.returncode == 10, scanned.stdout + scanned.stderr
    assert git(repo, "rev-parse", "HEAD").stdout == head
    assert not old.exists() and (exchange / ARCHIVE / old.name).read_bytes() == before[old]
    should_archive = reader == "current" and state == "embedded"
    assert result.exists() == (not should_archive)
    kept = exchange / ARCHIVE / result.name if should_archive else result
    assert kept.read_bytes() == before[result]
    assert wheel.read_bytes() == before[wheel]
    assert not (exchange / ARCHIVE / wheel.name).exists()


@pytest.mark.e2e
def test_mixed_exchange_selects_only_real_patch_and_writer_remains_format1(canonical, tmp_path):
    from tests.test_exchange_archive_e2e import _world
    from tests.test_exchange_e2e import _write_custom_package
    env, exchange, repo, context = _world(tmp_path)
    for name, data in (("embedded.zip", canonical), ("unavailable.zip", None)):
        files, _ = format2_entries(data)
        write_reference(exchange / name, files)
    (exchange / "standalone.zip").write_bytes(canonical)
    patch = exchange / "actual.patch.zip"
    _write_custom_package(patch, context, posix_entrypoint="printf ran > executed.txt",
                          powershell_entrypoint="[System.IO.File]::WriteAllText('executed.txt', 'ran')")
    result = run_cli(repo, "apply", "--json", environment_overrides=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "executed.txt").read_bytes() == b"ran"
    document = json.loads(result.stdout)
    produced = Path(document["result"]["result_bundle"]["path"])
    with ZipFile(produced) as archive:
        assert json.loads(archive.read("manifest.json"))["format_version"] == 1
        assert not any(name.startswith("runtime/") for name in archive.namelist())
    assert (exchange / "embedded.zip").is_file() and (exchange / "unavailable.zip").is_file()
