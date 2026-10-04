"""Conservative DACL readback comparison for private Windows test fixtures.

Set-Acl applies Windows' automatic inheritance model. It may add AI and reorder
adjacent ordinary allow ACEs with identical flags. Neither change grants rights.
Keep every ACE (including duplicates), its mask, SID and flags; never move an
allow across a deny, an object/callback ACE, or a different inheritance group.
This is not a general SDDL parser or a product permission policy.
"""
from __future__ import annotations

import json
from pathlib import Path
import re


def _dacl(sddl: str) -> tuple[frozenset[str], tuple[str, ...]]:
    match = re.fullmatch(r"D:((?:P|AR|AI)*)(.*)", sddl)
    if match is None:
        raise ValueError("unsupported fixture DACL")
    flags = re.findall(r"P|AR|AI", match[1])
    if len(flags) != len(set(flags)):
        raise ValueError("duplicate DACL control flag")
    tail = match[2]
    aces = re.findall(r"\([^()]*\)", tail)
    if "".join(aces) != tail:
        raise ValueError("unsupported fixture ACE representation")
    normalized: list[str] = []
    group: list[str] = []
    group_flags = None
    for ace in aces:
        fields = ace[1:-1].split(";")
        # Only adjacent, ordinary access-allowed ACEs with identical flags
        # commute. Everything else is an order-sensitive barrier.
        simple_allow = (len(fields) == 6 and fields[0] == "A"
                        and fields[2] and not fields[3] and not fields[4] and fields[5])
        if not simple_allow or fields[1] != group_flags:
            normalized.extend(sorted(group))
            group = []
            group_flags = fields[1] if simple_allow else None
        if simple_allow:
            group.append(ace)
        else:
            normalized.append(ace)
    normalized.extend(sorted(group))
    return frozenset(flags), tuple(normalized)


def restored_dacl_matches(expected: str, actual: str) -> bool:
    """Allow only documented auto-inheritance conversion and commuting allows."""
    if expected == actual:
        return True
    try:
        before_flags, before_aces = _dacl(expected)
        after_flags, after_aces = _dacl(actual)
    except ValueError:
        return False
    # AI can be added by Windows, never silently lost. Protection and the
    # auto-inherit request flag must stay identical.
    return (after_flags in (before_flags, before_flags | {"AI"})
            and before_aces == after_aces)


def verify_restored_dacls(journal: Path, readback: str) -> None:
    """Require complete native readback; a zero process exit alone is no proof."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate ACL report field")
            result[key] = value
        return result

    def inventory(document):
        if (type(document) is not dict or set(document) != {"root", "entries"}
                or type(document["root"]) is not str or not document["root"]
                or type(document["entries"]) is not list or not document["entries"]):
            raise ValueError("incomplete ACL report")
        entries = {}
        for row in document["entries"]:
            if (type(row) is not dict or set(row) != {"path", "sddl"}
                    or any(type(row[key]) is not str or not row[key] for key in row)
                    or row["path"].casefold() in entries):
                raise ValueError("invalid or duplicate ACL report entry")
            entries[row["path"].casefold()] = row["sddl"]
        if document["root"].casefold() not in entries:
            raise ValueError("ACL report omits the fixture root")
        return document["root"], entries

    try:
        root, expected = inventory(json.loads(journal.read_text(encoding="utf-8"), object_pairs_hook=unique))
        actual_root, actual = inventory(json.loads(readback, object_pairs_hook=unique))
        if root != actual_root or expected.keys() != actual.keys():
            raise ValueError("ACL readback does not match the saved fixture inventory")
        for path, sddl in expected.items():
            if not restored_dacl_matches(sddl, actual[path]):
                raise ValueError(f"Restored DACL differs for {path!r}: expected {sddl!r}; actual {actual[path]!r}")
    except (ValueError, OSError) as error:
        raise RuntimeError(f"native ACL restoration verification failed: {error}") from error
