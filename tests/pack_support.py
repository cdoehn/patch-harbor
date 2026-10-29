"""Shared pack fixtures and behavior probes."""
from __future__ import annotations

import pytest

from patchharbor import api

from tests.result_runtime_support import attach_runtime
from tests.reference_support import edit_document, reference_entries, write_reference


SCRIPT=b'#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n'


def _reference(tmp_path, *, kind="bundle", dirty=False, handoff=True, version=1, suffix=".txt"):
    files, binding = reference_entries(kind=kind, dirty=dirty, handoff=handoff)
    edit_document(files, "context.json", lambda doc: doc.update(bundle_suffix=suffix))
    if handoff:
        edit_document(files, "environment.json", lambda doc: doc.update(
            bundle_suffix=suffix, repository_path="/foreign/missing/repository",
            captured_at="2026-10-03T12:00:00Z", repository_name="recorded-repo",
            exchange_directory="/foreign/exchange", output_directory=None,
            runtime={"system": "ForeignOS", "python_version": "3.12.0", "unknown": None,
                     "extra": {"items": [1, {"nested": True}]}}))
    if version == 2:
        files = attach_runtime(files, None)
    path = tmp_path / "reference.zip"
    write_reference(path, files)
    return path, files, binding


@pytest.fixture
def request_files(tmp_path):
    reference, _, _ = _reference(tmp_path)
    contents = tmp_path / 'contents'; contents.mkdir()
    (contents / 'run.sh').write_bytes(SCRIPT)
    (contents / 'binary').write_bytes(b'\0\xff\r\n')
    output = tmp_path / 'out'; output.mkdir()
    return contents, reference, output


def pack(files, **kwargs):
    contents, reference, output = files
    options = dict(reference_bundle=reference, entrypoint='run.sh', output_directory=output)
    options.update(kwargs)
    if 'output' in kwargs:
        options.pop('output_directory')
    return api.pack_patch(contents, **options)
