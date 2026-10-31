"""Bounded malformed inputs and real mixed-version/legacy Exchange behavior."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import struct
from zipfile import ZipFile

import pytest

from patchharbor import api, runtime_pyz as pyz
from patchharbor.archive_evidence import parse_archive_evidence
from patchharbor.exchange import ExchangeArtifactKind, _classify_content
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.result_reader import read_result_reference
from tests.platform_support import run_cli
from tests.result_runtime_support import replace_pyz
from tests.result_pyz_support import canonical, format3
from tests.reference_support import edit_document, write_reference


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
    files, _ = format3(canonical)
    replace_pyz(files, bytes(raw))
    path = tmp_path / "result.zip"; write_reference(path, files)
    monkeypatch.setattr(pyz, "ZipFile", lambda *a, **k: pytest.fail("unbounded directory allocated ZipInfo objects"))
    with pytest.raises(api.PatchHarborError) as caught:
        read_result_reference(path)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR


@pytest.mark.parametrize("limit", ["pyz", "recipe"])
def test_pyz_and_recipe_limits_precede_their_reads(canonical, tmp_path, monkeypatch, limit):
    files, _ = format3(canonical)
    path = tmp_path / "result.zip"; write_reference(path, files)
    if limit == "pyz":
        monkeypatch.setattr(pyz, "MAX_PYZ_BYTES", len(canonical) - 1)
        monkeypatch.setattr(pyz, "ZipFile", lambda *a, **k: pytest.fail("oversize PYZ opened"))
    else:
        with ZipFile(BytesIO(canonical)) as archive:
            recipe_size = archive.getinfo(pyz.RECIPE_PATH).file_size
        monkeypatch.setattr(pyz, "MAX_RECIPE_BYTES", recipe_size - 1)
        original = pyz.read_pyz
        def guarded(*args, **kwargs):
            with monkeypatch.context() as guard:
                guard.setattr(ZipFile, "read", lambda *a, **k: pytest.fail("oversize recipe read"))
                return original(*args, **kwargs)
        monkeypatch.setattr(pyz, "read_pyz", guarded)
    with pytest.raises(api.PatchHarborError): read_result_reference(path)


@pytest.mark.parametrize("unicode_path", [False, True])
def test_deep_json_cannot_abort_exchange_classification(tmp_path, monkeypatch, unicode_path):
    files, _ = format3(None)
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
    from tests.patch_inspection_support import MANIFEST
    files, _ = format3(canonical)
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


@pytest.mark.e2e
def test_mixed_exchange_selects_only_real_patch_and_writer_produces_current_format(canonical, tmp_path):
    from tests.archive_support import _world
    from tests.exchange_support import _write_custom_package
    env, exchange, repo, context = _world(tmp_path)
    for name, data in (("embedded.zip", canonical), ("unavailable.zip", None)):
        files, _ = format3(data)
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
        assert json.loads(archive.read("manifest.json"))["format_version"] == 3
        assert json.loads(archive.read("runtime/runtime.json"))["reason"] == "source_not_prepared"
    assert (exchange / "embedded.zip").is_file() and (exchange / "unavailable.zip").is_file()
