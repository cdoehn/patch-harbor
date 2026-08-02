from __future__ import annotations

import io

import pytest

from patchharbor.output import ProcessOutputCapture, RollingLineBuffer


def test_rolling_line_buffer_keeps_last_ten_and_exposes_last_five() -> None:
    buffer = RollingLineBuffer()

    for number in range(1, 13):
        buffer.append(f"line-{number}\n")

    assert buffer.retained_lines == tuple(
        f"line-{number}\n" for number in range(3, 13)
    )
    assert buffer.visible_lines == tuple(
        f"line-{number}\n" for number in range(8, 13)
    )
    assert buffer.discarded_line_count == 2


def test_rolling_line_buffer_preserves_final_line_without_newline() -> None:
    buffer = RollingLineBuffer()

    buffer.append("first\n")
    buffer.append("final-without-newline")

    assert buffer.retained_lines == ("first\n", "final-without-newline")
    assert buffer.discarded_line_count == 0


def test_output_capture_separates_chunk_decoding_and_line_building() -> None:
    raw_output = "first-€\r\n".encode() + b"invalid-\xff\rfinal"
    capture = ProcessOutputCapture(io.BytesIO(raw_output), chunk_size=1)

    capture.start()
    capture.finish()

    assert capture.buffer.retained_lines == (
        "first-€\n",
        "invalid-�\n",
        "final",
    )
    assert capture.finished


def test_output_capture_reports_binary_stream_read_errors() -> None:
    class BrokenStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            raise OSError("read failed")

    capture = ProcessOutputCapture(BrokenStream())
    capture.start()

    with pytest.raises(OSError, match="cannot read script output: read failed"):
        capture.finish()

    assert capture.finished
