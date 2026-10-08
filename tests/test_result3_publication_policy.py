"""New runtime states keep the existing typed, finite Result publication policy."""
from hashlib import sha256
from zipfile import ZipFile

import pytest

from patchharbor import result_bundle_writer as writer, result_reader as reader
from patchharbor import result_resources as resources, result_verification as verification
from patchharbor.platform.filesystem import FileChangedDuringRead
from tests.test_result_bundle_publication import _publish, prepare_result_bundle_publication, UUID
from tests.test_result_runtime_writer import artifact


@pytest.mark.parametrize('state',['embedded','unavailable'])
@pytest.mark.parametrize('fault',['transient','integrity'])
def test_new_runtime_states_keep_typed_retry_and_hash_publication_boundary(tmp_path,monkeypatch,artifact,state,fault):
    payload=resources.runtime_payload(artifact if state=='embedded' else None,
                                      reason=None if state=='embedded' else 'source_not_prepared')
    target=prepare_result_bundle_publication(tmp_path/'result.zip',run_id=UUID('12345678-1234-4234-8234-123456789abc'))
    sleeps=[];captures=[];published=[]
    monkeypatch.setattr(verification,'sleep',sleeps.append)
    monkeypatch.setattr(verification,'publication_wait_budget',lambda path:300)
    original_capture=reader.read_stable_regular_file_with_sha256
    def capture(*args,**kwargs):
        captures.append(True)
        if fault=='transient' and len(captures)==1:
            raise FileChangedDuringRead(category='initial-open-state-mismatch')
        return original_capture(*args,**kwargs)
    monkeypatch.setattr(reader,'read_stable_regular_file_with_sha256',capture)
    original_write=writer._write_entry
    def write(archive,name,content,**kwargs):
        if fault=='integrity' and name=='runtime/runtime.json':content+=b'changed'
        return original_write(archive,name,content,**kwargs)
    monkeypatch.setattr(writer,'_write_entry',write)
    if fault=='integrity':
        with pytest.raises(verification.ResultVerificationError):
            _publish(target,runtime=payload,before_publish=published.append)
        assert sleeps==[] and not published
        assert not target.final_path.exists() and not target.temporary_path.exists()
    else:
        _publish(target,runtime=payload,before_publish=published.append)
        assert sleeps==[2]
        actual=target.final_path.read_bytes()
        assert published==[sha256(actual).hexdigest()]
        facts,digest=reader.read_result_reference(target.final_path)
        assert facts.format_version==3 and facts.runtime.status==state and digest==published[0]
        with ZipFile(target.final_path) as archive:
            assert not any(n.startswith('runtime/') and n.endswith('.whl') for n in archive.namelist())
        assert not target.temporary_path.exists()
