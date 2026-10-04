"""Synthetic Result-2 inputs over actual canonical wheels; no product writer 2."""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from patchharbor import runtime_wheel as wheel
from tests.test_reference_validation import edit_document, reference_entries


def descriptor(path: str, content: bytes) -> dict:
    return {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def attach_runtime(files: dict[str, bytes], raw: bytes | None) -> dict[str, bytes]:
    files = dict(files)
    manifest = json.loads(files["manifest.json"])
    manifest["format_version"] = 2
    if raw is None:
        doc = json.loads((Path(__file__).parent / "fixtures/result_runtime_unavailable.json").read_bytes())
        edit_document(files, "logs/run.json", lambda run: run.update(warnings=["runtime unavailable"]))
    else:
        with ZipFile(BytesIO(raw)) as archive:
            recipe = wheel.parse_recipe(archive.read(wheel.RECIPE_PATH))
        path = "runtime/" + recipe.wheel_name
        files[path] = raw
        doc = {
            "marker": "patch-harbor-runtime", "format_version": 1,
            "status": "embedded", "reason": None, "distribution": "patchharbor",
            "version": recipe.version, "requires_python": recipe.requires_python,
            "content_id": recipe.content_id, "content_id_algorithm": wheel.CONTENT_ALGORITHM,
            "wheel": descriptor(path, raw), "tags": ["py3-none-any"], "runtime_dependencies": [],
            "provenance": {"mode": "canonical_resources", "source_commit": recipe.source_commit,
                           "recipe_format_version": 1},
            "capabilities": {"operations": ["inspect_patch", "validate_patch"],
                             "patch_formats": [1], "result_formats": [1, 2]},
        }
    metadata_path = "runtime/runtime.json"
    files[metadata_path] = json.dumps(doc).encode()
    manifest["runtime"] = {"status": doc["status"], "reason": doc["reason"],
                           "metadata": descriptor(metadata_path, files[metadata_path]), "wheel": doc["wheel"]}
    files["manifest.json"] = json.dumps(manifest).encode()
    return files


def format2_entries(raw: bytes | None, **options):
    files, binding = reference_entries(handoff=True, **options)
    return attach_runtime(files, raw), binding


def edit_metadata(files, mutate):
    edit_document(files, "runtime/runtime.json", mutate)
    edit_document(files, "manifest.json", lambda manifest: manifest["runtime"].update(
        metadata=descriptor("runtime/runtime.json", files["runtime/runtime.json"])))


def replace_wheel(files, raw):
    doc = json.loads(files["runtime/runtime.json"])
    name = doc["wheel"]["path"]
    files[name] = raw
    item = descriptor(name, raw)
    edit_metadata(files, lambda metadata: metadata.update(wheel=item))
    edit_document(files, "manifest.json", lambda manifest: manifest["runtime"].update(wheel=item))


def rewrite_wheel(raw, mutate, *, transform=None):
    with ZipFile(BytesIO(raw)) as archive:
        items = [(info, archive.read(info)) for info in archive.infolist()]
    mutate(items)
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
        for info, content in items:
            if transform:
                transform(info)
            archive.writestr(info, content)
    return stream.getvalue()
