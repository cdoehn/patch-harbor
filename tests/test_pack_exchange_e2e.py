"""The real automatic consumer sees only the completed exclusive publication."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from patchharbor import api
from patchharbor.platform.pack_output import OwnedPackFile
from tests.platform_support import native_python_script, native_value
from tests.registration_support import create_repository

pytestmark=pytest.mark.e2e


def test_automatic_exchange_consumer_ignores_partial_then_applies_complete_pack(tmp_path,monkeypatch):
    repo=create_repository(tmp_path/'repo');api.register(repo)
    exchange=tmp_path/'exchange';api.configure_exchange_directory(exchange,repository=repo)
    reference=api.bundle(repo).path
    contents=tmp_path/'contents';contents.mkdir();entry=native_value('run.sh','run.ps1')
    (contents/'payload.bin').write_bytes(b'complete-payload')
    (contents/entry).write_text(native_python_script(
        "from pathlib import Path; assert Path('payload.bin').read_bytes()==b'complete-payload'"))
    before_publish=Event();continue_publish=Event();original=OwnedPackFile.publish
    def pause(self,name):
        before_publish.set()
        assert continue_publish.wait(60),'consumer did not release publication'
        return original(self,name)
    monkeypatch.setattr(OwnedPackFile,'publish',pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(api.pack_patch,contents,reference_bundle=reference,entrypoint=entry,output_directory=exchange)
        try:
            assert before_publish.wait(60),'pack did not reach publication'
            assert len(list(exchange.glob('.patchharbor-pack-*.partial')))==1
            absent=api.apply_next()
            assert absent.process_exit_code==10
            assert not absent.primary_result.entrypoint_started
            assert not (repo/'payload.bin').exists()
        finally:
            continue_publish.set()
        packed=task.result(timeout=60)
    assert packed.validation.binding_matches and packed.path.is_file()
    applied=api.apply_next()
    assert applied.success and applied.primary_result.entrypoint_started
    assert applied.primary_result.entrypoint_exit_code==0
    assert (repo/'payload.bin').read_bytes()==b'complete-payload'
    assert not list(exchange.glob('.patchharbor-pack-*.partial'))
