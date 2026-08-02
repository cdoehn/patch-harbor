from __future__ import annotations

import io

import pytest

from patchharbor.output import ProcessOutputCapture


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
