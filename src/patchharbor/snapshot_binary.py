"""Strict bounded Git binary-patch decoding, without a Git dependency."""
from __future__ import annotations

import base64
from io import BytesIO
import re
import zlib

from patchharbor.snapshot_budget import SnapshotBudget
from patchharbor.snapshot_types import ResultSnapshotError, SnapshotErrorCode

_HEADER = re.compile(rb'(literal|delta) (0|[1-9][0-9]*)\n')


def invalid(message: str) -> ResultSnapshotError:
    return ResultSnapshotError(SnapshotErrorCode.INVALID_PATCH, message)


def _integer(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 64, 7):
        if offset >= len(data):
            raise invalid('truncated binary delta integer')
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if not byte & 128:
            if value >= 1 << 64:
                break
            return value, offset
    raise invalid('binary delta integer overflow')


def apply_delta(data: bytes, original: bytes, budget: SnapshotBudget) -> bytes:
    source_size, offset = _integer(data, 0)
    target_size, offset = _integer(data, offset)
    if source_size != len(original):
        raise invalid('binary delta source size mismatch')
    budget.require(target_size)
    out = BytesIO()
    while offset < len(data):
        instruction = data[offset]
        offset += 1
        if instruction & 128:
            position, count = 0, 0
            for bit in range(7):
                if instruction & (1 << bit):
                    if offset >= len(data):
                        raise invalid('truncated binary copy instruction')
                    if bit < 4:
                        position |= data[offset] << (8 * bit)
                    else:
                        count |= data[offset] << (8 * (bit - 4))
                    offset += 1
            count = count or 0x10000
            if position + count > len(original):
                raise invalid('binary copy outside source')
            if out.tell() + count > target_size:
                raise invalid('binary copy exceeds target size')
            out.write(memoryview(original)[position:position + count])
        elif instruction:
            if offset + instruction > len(data) or out.tell() + instruction > target_size:
                raise invalid('truncated or oversized binary insertion')
            out.write(memoryview(data)[offset:offset + instruction])
            offset += instruction
        else:
            raise invalid('invalid zero binary delta instruction')
    if out.tell() != target_size:
        raise invalid('binary delta target size mismatch')
    budget.take(target_size)
    return out.getvalue()


def read_block(stream: BytesIO, original: bytes, budget: SnapshotBudget) -> bytes:
    header = _HEADER.fullmatch(stream.readline())
    if header is None:
        raise invalid('missing literal/delta binary header')
    size = int(header[2])
    budget.require(size)
    encoded = bytearray()
    while True:
        line = stream.readline()
        if line == b'\n':
            break
        if not line or not line.endswith(b'\n'):
            raise invalid('unterminated binary block')
        prefix = line[0]
        count = prefix - 64 if 65 <= prefix <= 90 else prefix - 70 if 97 <= prefix <= 122 else 0
        if not count or len(line) != 2 + ((count + 3) // 4) * 5:
            raise invalid('invalid binary base85 line length')
        try:
            decoded = base64.b85decode(line[1:-1])
        except ValueError as exc:
            raise invalid('invalid binary base85 data') from exc
        if any(decoded[count:]):
            raise invalid('nonzero binary base85 padding')
        if len(encoded) + count > budget.policy.max_content_bytes:
            raise ResultSnapshotError(SnapshotErrorCode.RESOURCE_LIMIT, 'compressed binary block exceeds limit')
        encoded.extend(decoded[:count])
    try:
        decoder = zlib.decompressobj()
        data = decoder.decompress(encoded, size + 1)
    except zlib.error as exc:
        raise invalid('invalid binary compression') from exc
    if len(data) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise invalid('binary expansion size or stream boundary mismatch')
    budget.take(size)
    return data if header[1] == b'literal' else apply_delta(data, original, budget)
