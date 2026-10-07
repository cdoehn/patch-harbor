"""Bounded canonical runtime ZIP metadata, shared by legacy wheel and PYZ."""
import struct


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def bounded_directory(raw: bytes, policy, *, max_entries: int = 1000) -> int:
    """Bound metadata allocation before ZipFile builds its complete member list.

    This only preflights the fixed canonical envelope; ZipFile and the profile
    checks below still validate every header and all content. A forged small
    EOCD count cannot hide extra central-directory entries.
    """
    end = len(raw) - 22
    _require(end >= 0, "truncated runtime ZIP boundary")
    signature, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from(
        "<4s4H2IH", raw, end)
    _require(signature == b"PK\x05\x06" and disk == directory_disk == comment == 0
             and disk_count == count and 0 < count <= min(max_entries, policy.max_zip_entries),
             "unsupported runtime ZIP directory or entry budget")
    _require(offset + size == end and count * 47 <= size <= count * (46 + 512),
             "runtime ZIP directory budget or bounds exceeded")
    cursor = offset
    for _ in range(count):
        _require(cursor + 46 <= end and raw[cursor:cursor + 4] == b"PK\x01\x02",
                 "invalid runtime ZIP directory member")
        name, extra, comment = struct.unpack_from("<3H", raw, cursor + 28)
        _require(0 < name <= 512 and extra == comment == 0, "noncanonical runtime ZIP directory data")
        cursor += 46 + name
    _require(cursor == end, "runtime ZIP directory count mismatch")
    return count
