"""Native full-index Git literal patches from already captured immutable bytes."""
from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import zlib

from patchharbor.resource_policy import DEFAULT_RESOURCE_POLICY
from patchharbor.safe_export_types import SafeExportError, SafeExportErrorCode


def _quote(path: bytes) -> bytes:
    # Git's C/octal path notation; quoting both sides also handles spaces/UTF-8.
    return b'"' + b''.join(bytes((b,)) if 32 <= b < 127 and b not in (34, 92)
                           else ('\\%03o' % b).encode('ascii') for b in path) + b'"'


def _oid(raw: bytes, algorithm: str) -> bytes:
    return hashlib.new(algorithm, b'blob ' + str(len(raw)).encode() + b'\0' + raw,
                       usedforsecurity=False).hexdigest().encode()


def _literal(raw: bytes) -> bytes:
    if len(raw) > DEFAULT_RESOURCE_POLICY.max_content_bytes:
        raise SafeExportError(SafeExportErrorCode.RESOURCE_LIMIT, 'safe delta content exceeds file budget')
    data = zlib.compress(raw)
    output = BytesIO()
    output.write(b'literal ' + str(len(raw)).encode() + b'\n')
    for offset in range(0, len(data), 52):
        chunk = data[offset:offset + 52]
        size = len(chunk)
        output.write(bytes((size + (64 if size <= 26 else 70),)))
        output.write(base64.b85encode(chunk, pad=True) + b'\n')
    output.write(b'\n')
    return output.getvalue()


def literal_patch(before: dict[bytes, tuple[bytes, bytes]],
                  after: dict[bytes, tuple[bytes, bytes]], *, algorithm: str) -> bytes:
    output = BytesIO()
    zero = b'0' * (40 if algorithm == 'sha1' else 64)
    for path in sorted(before.keys() | after.keys()):
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        output.write(b'diff --git ' + _quote(b'a/' + path) + b' ' + _quote(b'b/' + path) + b'\n')
        if old is None:
            output.write(b'new file mode ' + new[0] + b'\n')
        elif new is None:
            output.write(b'deleted file mode ' + old[0] + b'\n')
        elif old[0] != new[0]:
            output.write(b'old mode ' + old[0] + b'\nnew mode ' + new[0] + b'\n')
        if old is not None and new is not None and old[1] == new[1]:
            continue  # A mode-only transition needs no allocation or content block.
        old_raw, new_raw = old[1] if old else b'', new[1] if new else b''
        output.write(b'index ' + (_oid(old_raw, algorithm) if old else zero) + b'..'
                     + (_oid(new_raw, algorithm) if new else zero))
        if old is not None and new is not None and old[0] == new[0]:
            output.write(b' ' + old[0])
        output.write(b'\nGIT binary patch\n' + _literal(new_raw) + _literal(old_raw))
        if output.tell() > DEFAULT_RESOURCE_POLICY.max_content_bytes:
            raise SafeExportError(SafeExportErrorCode.RESOURCE_LIMIT, 'safe delta exceeds content budget')
    return output.getvalue()
