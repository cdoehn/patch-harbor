"""Small stdlib compatibility operations; no alternate public API."""
from __future__ import annotations

_NATIVE_ADD_NOTE = getattr(BaseException, "add_note", None)


def add_exception_note(error: BaseException, note: str) -> None:
    """Keep cleanup diagnostics on the original exception, including on 3.10."""
    if _NATIVE_ADD_NOTE is not None:
        _NATIVE_ADD_NOTE(error, note)
        return
    if not isinstance(note, str):
        raise TypeError("exception note must be a string")
    notes = getattr(error, "__notes__", None)
    if notes is None:
        notes = []
        error.__notes__ = notes
    if not isinstance(notes, list):
        raise TypeError("exception notes must be a list")
    notes.append(note)
