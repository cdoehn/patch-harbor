"""Malformed binary programs cannot bypass decoded size or source bounds."""
from dataclasses import replace
from io import BytesIO
import base64
import zlib

import pytest

from patchharbor import api
from patchharbor.snapshot_binary import apply_delta, read_block
from patchharbor.snapshot_budget import SnapshotBudget
from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY


def encoded_block(kind,raw,*,declared=None,trailing=b''):
    compressed=zlib.compress(raw)+trailing
    rows=[]
    for offset in range(0,len(compressed),52):
        part=compressed[offset:offset+52];n=len(part)
        prefix=bytes([n+64 if n<=26 else n+70])
        rows.append(prefix+base64.b85encode(part+b'\0'*((-n)%4))+b'\n')
    return kind+b' '+str(len(raw) if declared is None else declared).encode()+b'\n'+b''.join(rows)+b'\n'


@pytest.mark.parametrize('program',[
    b'',b'\x80',b'\x83\x00\x01\x01x',b'\x80'*12,b'\x04\x01\x01x', # missing/overflow/wrong source
    b'\x03\x01\x00',b'\x03\x01\x01',b'\x03\x01\x02xy', # invalid/truncated/overrun insert
    b'\x03\x01\x91',b'\x03\x01\x91\x03\x01', # truncated/outside-source copy
    b'\x03\x01\x90\x02',b'\x03\x02\x01x', # target over/underflow
])
def test_invalid_delta_programs_are_rejected(program):
    with pytest.raises(api.ResultSnapshotError) as caught:apply_delta(program,b'abc',SnapshotBudget())
    assert caught.value.code is api.SnapshotErrorCode.INVALID_PATCH


def test_copy_default_size_and_insert_are_implemented():
    # Independently constructed Git delta: source=65536 target=65537,
    # copy instruction with implicit 64-KiB size, then one literal byte.
    original=b'x'*65536
    program=b'\x80\x80\x04\x81\x80\x04\x80\x01!'
    assert apply_delta(program,original,SnapshotBudget())==original+b'!'


@pytest.mark.parametrize('case',['short','long','trailing','truncated','budget','delta_target_budget'])
def test_binary_expansion_is_bounded_and_exact(case):
    policy=replace(DEFAULT_RESOURCE_POLICY,warning_bytes=1,max_input_artifact_bytes=1000,max_content_bytes=100,max_zip_total_bytes=200)
    if case=='short':raw=encoded_block(b'literal',b'abc',declared=4)
    elif case=='long':raw=encoded_block(b'literal',b'abc',declared=2)
    elif case=='trailing':raw=encoded_block(b'literal',b'abc',trailing=b'extra')
    elif case=='truncated':raw=encoded_block(b'literal',b'abc')[:-3]
    elif case=='budget':raw=encoded_block(b'literal',b'x'*10000)
    else:raw=encoded_block(b'delta',b'\x03\xe8\x07\x01x') # declared target 1000
    with pytest.raises(api.ResultSnapshotError) as caught:read_block(BytesIO(raw),b'abc',SnapshotBudget(policy))
    expected=api.SnapshotErrorCode.RESOURCE_LIMIT if case in ('budget','delta_target_budget') else api.SnapshotErrorCode.INVALID_PATCH
    assert caught.value.code is expected
