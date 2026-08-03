from __future__ import annotations

import io
from pathlib import Path
import tempfile

import pytest

from patchharbor.output import ProcessOutputCapture, temporary_run_log


def _capture(raw_output: bytes) -> ProcessOutputCapture:
    capture = ProcessOutputCapture(io.BytesIO(raw_output))
    capture.start()
    capture.finish()
    return capture


def test_output_capture_keeps_last_ten_and_exposes_last_five() -> None:
    capture = _capture(
        "".join(f"line-{number}\n" for number in range(1, 13)).encode()
    )

    assert capture.retained_lines == tuple(
        f"line-{number}\n" for number in range(3, 13)
    )
    assert capture.visible_lines == tuple(
        f"line-{number}\n" for number in range(8, 13)
    )
    assert capture.discarded_line_count == 2


def test_output_capture_preserves_final_line_without_newline() -> None:
    capture = _capture(b"first\nfinal-without-newline")

    assert capture.retained_lines == ("first\n", "final-without-newline")
    assert capture.discarded_line_count == 0


def test_output_capture_decodes_and_normalizes_lines() -> None:
    raw_output = "first-€\r\n".encode() + b"invalid-\xff\rfinal"
    capture = _capture(raw_output)

    assert capture.retained_lines == (
        "first-€\n",
        "invalid-�\n",
        "final",
    )
    assert capture.finished


def test_output_capture_bounds_large_output() -> None:
    capture = _capture(
        "".join(f"line-{number}\n" for number in range(1, 20_001)).encode()
    )

    assert capture.retained_lines == tuple(
        f"line-{number}\n" for number in range(19_991, 20_001)
    )
    assert capture.visible_lines == tuple(
        f"line-{number}\n" for number in range(19_996, 20_001)
    )
    assert capture.discarded_line_count == 19_990


def test_output_capture_reports_binary_stream_read_errors() -> None:
    class BrokenStream(io.BytesIO):
        def read1(self, size: int = -1) -> bytes:
            raise OSError("read failed")

    capture = ProcessOutputCapture(BrokenStream())
    capture.start()

    with pytest.raises(OSError, match="cannot read script output: read failed"):
        capture.finish()

    assert capture.finished


def test_output_capture_streams_every_line_to_each_live_destination() -> None:
    first = io.StringIO()
    second = io.StringIO()
    capture = ProcessOutputCapture(
        io.BytesIO(b"one\ntwo\nthree"),
        live_text_streams=(first, second),
    )

    capture.start()
    capture.finish()

    assert first.getvalue() == "one\ntwo\nthree"
    assert second.getvalue() == "one\ntwo\nthree"
    assert capture.retained_lines == ("one\n", "two\n", "three")


def test_temporary_run_logs_are_unique_and_use_the_system_temp_directory() -> None:
    with temporary_run_log() as first:
        first.path.write_text("first", encoding="utf-8")
    with temporary_run_log() as second:
        second.path.write_text("second", encoding="utf-8")

    try:
        assert first.path != second.path
        assert first.path.parent == Path(tempfile.gettempdir())
        assert second.path.parent == Path(tempfile.gettempdir())
    finally:
        first.path.unlink(missing_ok=True)
        second.path.unlink(missing_ok=True)
