"""Apply the producer's full-index Git diff syntax exactly to immutable trees."""
from __future__ import annotations

import hashlib
from io import BytesIO
import re
from types import MappingProxyType

from patchharbor.errors import PatchHarborError
from patchharbor.models import GitObjectFormat, GitObjectId
from patchharbor.repository_paths import RepositoryRelativePath, validate_repository_paths
from patchharbor.resource_policy import MAX_RESULT_FILES
from patchharbor.snapshot_binary import invalid, read_block
from patchharbor.snapshot_budget import SnapshotBudget
from patchharbor.snapshot_types import ResultSnapshotError, SnapshotErrorCode, SnapshotFile, SnapshotLayer

_INDEX = re.compile(rb'index ([0-9a-f]+)\.\.([0-9a-f]+)(?: (100644|100755))?\n')
_HUNK = re.compile(rb'@@ -(0|[1-9][0-9]*)(?:,(0|[1-9][0-9]*))? \+(0|[1-9][0-9]*)(?:,(0|[1-9][0-9]*))? @@[^\n]*\n')
_ESCAPES = {ord(c): value for c, value in {'a':7, 'b':8, 't':9, 'n':10, 'v':11, 'f':12, 'r':13, '"':34, '\\':92}.items()}
_NO_LF = b'\\ No newline at end of file\n'


def _peek(stream: BytesIO) -> bytes:
    position = stream.tell()
    value = stream.readline()
    stream.seek(position)
    return value


def _quoted(raw: bytes) -> tuple[bytes, bytes]:
    if not raw.startswith(b'"'):
        raise invalid('missing quoted Git path')
    out = bytearray()
    offset = 1
    while offset < len(raw):
        value = raw[offset]
        offset += 1
        if value == 34:
            return bytes(out), raw[offset:]
        if value == 92:
            if offset >= len(raw):
                break
            value = raw[offset]
            offset += 1
            if value in _ESCAPES:
                value = _ESCAPES[value]
            elif 48 <= value <= 55:
                octal = bytes((value,)) + raw[offset:offset + 2]
                if len(octal) != 3 or any(c < 48 or c > 55 for c in octal):
                    raise invalid('invalid Git octal path escape')
                value = int(octal, 8)
                offset += 2
                if value > 255:
                    raise invalid('Git octal path escape overflows a byte')
            else:
                raise invalid('unsupported Git path escape')
        out.append(value)
    raise invalid('unterminated quoted Git path')


def _path(raw: bytes) -> str:
    try:
        return RepositoryRelativePath(raw).decoded
    except PatchHarborError as exc:
        raise ResultSnapshotError(SnapshotErrorCode.PATH_COLLISION, 'unsafe reconstruction path') from exc


def _diff_path(line: bytes) -> str:
    if not line.startswith(b'diff --git ') or not line.endswith(b'\n'):
        raise ResultSnapshotError(SnapshotErrorCode.UNSUPPORTED_PATCH, 'expected a full Git diff header')
    raw = line[len(b'diff --git '):-1]
    if raw.startswith(b'"'):
        left, tail = _quoted(raw)
        if not tail.startswith(b' '):
            raise invalid('invalid quoted diff separator')
        right, rest = _quoted(tail[1:])
        if rest:
            raise invalid('trailing diff path data')
    else:
        length = (len(raw) - 5) // 2
        name = raw[2:2 + length]
        if raw != b'a/' + name + b' b/' + name:
            raise ResultSnapshotError(SnapshotErrorCode.UNSUPPORTED_PATCH, 'noncanonical or renamed diff path')
        left, right = b'a/' + name, b'b/' + name
    if not left.startswith(b'a/') or right != b'b/' + left[2:]:
        raise ResultSnapshotError(SnapshotErrorCode.UNSUPPORTED_PATCH, 'diff requires identical a/ and b/ paths')
    return _path(left[2:])


def _file_header(line: bytes, marker: bytes, expected: bytes) -> None:
    if not line.startswith(marker) or not line.endswith(b'\n'):
        raise invalid('missing text file header')
    raw = line[len(marker):-1]
    if raw.endswith(b'\t'):
        raw = raw[:-1]
    if raw.startswith(b'"'):
        raw, rest = _quoted(raw)
        if rest:
            raise invalid('trailing text path data')
    if raw != expected:
        raise invalid('text file header disagrees with diff path')


def blob_id(raw: bytes, algorithm: GitObjectFormat) -> GitObjectId:
    digest = hashlib.new(algorithm.value)
    digest.update(b'blob ' + str(len(raw)).encode('ascii') + b'\0')
    digest.update(raw)
    return GitObjectId(digest.hexdigest(), algorithm)


def file_value(path: str, mode: str, raw: bytes, algorithm: GitObjectFormat) -> SnapshotFile:
    return SnapshotFile(path, mode, raw, hashlib.sha256(raw).hexdigest(), blob_id(raw, algorithm))


def layer(name: str, files: dict[str, SnapshotFile]) -> SnapshotLayer:
    if len(files) > MAX_RESULT_FILES:
        raise ResultSnapshotError(SnapshotErrorCode.RESOURCE_LIMIT, 'snapshot layer has too many files')
    try:
        paths = validate_repository_paths(p.encode('utf-8') for p in files)
    except PatchHarborError as exc:
        raise ResultSnapshotError(SnapshotErrorCode.PATH_COLLISION, 'nonportable snapshot collision') from exc
    keys = {p.collision_key for p in paths}
    for path in paths:
        parts = path.collision_key.split('/')
        if any('/'.join(parts[:i]) in keys for i in range(1, len(parts))):
            raise ResultSnapshotError(SnapshotErrorCode.PATH_COLLISION, 'snapshot file/directory collision')
    return SnapshotLayer(name, MappingProxyType({p.decoded: files[p.decoded] for p in paths}))


def _text(stream: BytesIO, original: bytes, budget: SnapshotBudget) -> bytes:
    source = BytesIO(original)
    out = BytesIO()
    old_line, new_line = 0, 0
    hunks = 0

    def write(raw: bytes) -> None:
        budget.require_file(out.tell() + len(raw))
        budget.take(len(raw))
        out.write(raw)

    while _peek(stream).startswith(b'@@'):
        hunk = _HUNK.fullmatch(stream.readline())
        if hunk is None:
            raise invalid('malformed text hunk range')
        old_start, old_count, new_start, new_count = (int(x) if x is not None else 1 for x in hunk.groups())
        if (old_count and not old_start) or (new_count and not new_start):
            raise invalid('invalid nonempty hunk origin')
        old_position = old_start - bool(old_count)
        new_position = new_start - bool(new_count)
        if old_position < old_line:
            raise invalid('overlapping or reordered hunks')
        while old_line < old_position:
            raw = source.readline()
            if not raw or not raw.endswith(b'\n'):
                raise invalid('hunk starts past the source lines')
            write(raw)
            old_line += 1
            new_line += 1
        if new_line != new_position:
            raise invalid('hunk target offset mismatch')
        removed, added = 0, 0
        while removed < old_count or added < new_count:
            row = stream.readline()
            if not row.endswith(b'\n') or row[:1] not in (b' ', b'-', b'+'):
                raise invalid('truncated or malformed text hunk')
            prefix, raw = row[:1], row[1:]
            if _peek(stream) == _NO_LF:
                stream.readline()
                raw = raw[:-1]
                if not raw:
                    raise invalid("empty no-LF line")
            if prefix != b'+':
                removed += 1
                old_line += 1
                if source.readline() != raw:
                    raise invalid('text hunk source/context mismatch')
            if prefix != b'-':
                added += 1
                new_line += 1
                # No-LF output must be the final line of the reconstructed file.
                if out.tell() and out.getbuffer()[out.tell() - 1] != 10:
                    raise invalid('text hunk appends after a line without LF')
                write(raw)
            if removed > old_count or added > new_count:
                raise invalid('text hunk range count mismatch')
        hunks += 1
    if not hunks:
        raise invalid('text change has no hunks')
    # Copy the remaining bytes in bounded chunks, never split a huge file into
    # millions of Python line objects.
    raw = source.read(65536)
    if raw and out.tell() and out.getbuffer()[out.tell() - 1] != 10:
        raise invalid('unchanged suffix follows a line without LF')
    while raw:
        write(raw)
        raw = source.read(65536)
    return out.getvalue()


def apply_patch(previous: SnapshotLayer, patch: bytes, name: str,
                algorithm: GitObjectFormat, budget: SnapshotBudget) -> SnapshotLayer:
    stream = BytesIO(patch)
    files = dict(previous.files)
    changed: set[str] = set()
    width = len(str(blob_id(b'', algorithm)))
    zero = '0' * width
    while _peek(stream):
        path = _diff_path(stream.readline())
        if path in changed:
            raise invalid('duplicate file diff in one layer')
        changed.add(path)
        original = previous.files.get(path)
        old_mode = original.mode if original is not None else None
        new_mode = old_mode
        transition = None
        for label in (b'new file mode ', b'deleted file mode ', b'old mode '):
            if _peek(stream).startswith(label):
                raw_mode = stream.readline()[len(label):]
                if raw_mode not in (b'100644\n', b'100755\n'):
                    raise ResultSnapshotError(SnapshotErrorCode.UNSUPPORTED_PATCH, 'unsupported Git file mode')
                mode = raw_mode[:-1].decode('ascii')
                transition = label
                if label == b'new file mode ':
                    if original is not None:
                        raise invalid('new file replaces an existing path')
                    new_mode = mode
                else:
                    if original is None or mode != old_mode:
                        raise invalid('old Git mode mismatch')
                    if label == b'deleted file mode ':
                        new_mode = None
                    else:
                        row = stream.readline()
                        if row not in (b'new mode 100644\n', b'new mode 100755\n'):
                            raise invalid('missing supported new mode')
                        new_mode = row[len(b'new mode '):-1].decode('ascii')
                        if new_mode == old_mode:
                            raise invalid('unchanged mode change')
                break
        identity = None
        if _peek(stream).startswith(b'index '):
            identity = _INDEX.fullmatch(stream.readline())
            if identity is None or len(identity[1]) != width or len(identity[2]) != width:
                raise invalid('missing full object identities')
            before, after = identity[1].decode(), identity[2].decode()
            if before != (str(original.object_id) if original is not None else zero):
                raise invalid('old blob identity mismatch')
            if identity[3] is not None:
                if transition is not None or identity[3].decode() != old_mode:
                    raise invalid('index mode mismatch')
            elif transition is None:
                raise invalid('index lacks unchanged mode')
            if (after == zero) != (new_mode is None):
                raise invalid('deleted blob identity mismatch')
        old_bytes = original.content if original else b''
        following = _peek(stream)
        if following == b'GIT binary patch\n':
            if identity is None:
                raise invalid('binary change lacks identities')
            stream.readline()
            raw = read_block(stream, old_bytes, budget)
            reverse = read_block(stream, raw, budget)
            if reverse != old_bytes:
                raise invalid('binary reverse patch disagrees with source')
        elif following.startswith(b'--- '):
            if identity is None:
                raise invalid('text change lacks identities')
            encoded = path.encode('utf-8')
            _file_header(stream.readline(), b'--- ', b'a/' + encoded if original else b'/dev/null')
            _file_header(stream.readline(), b'+++ ', b'b/' + encoded if new_mode else b'/dev/null')
            raw = _text(stream, old_bytes, budget)
        elif following and not following.startswith(b'diff --git '):
            raise ResultSnapshotError(SnapshotErrorCode.UNSUPPORTED_PATCH, 'unknown change syntax')
        else:
            raw = old_bytes
            if transition is None:
                raise invalid('empty file change')
            if transition != b'old mode ' and (identity is None or raw):
                raise invalid('nonempty add/delete without content changes')
        if original is None and transition != b'new file mode ':
            raise invalid('change references a missing base file')
        if identity is not None and new_mode is not None and str(blob_id(raw, algorithm)) != after:
            raise invalid('new blob identity mismatch')
        if original is not None and new_mode == old_mode and raw == old_bytes:
            raise invalid("no-op file diff")
        if new_mode is None:
            if raw or original is None:
                raise invalid('deleted file has remaining content')
            del files[path]
        else:
            files[path] = file_value(path, new_mode, raw, algorithm)
        # Adds may sort before deletes. Bound the temporary union while allowing
        # a valid final layer at its file-count ceiling. layer() checks the result.
        if len(files) > MAX_RESULT_FILES + len(previous.files):
            raise ResultSnapshotError(SnapshotErrorCode.RESOURCE_LIMIT, 'too many reconstructed files')
    return layer(name, files)
