from __future__ import annotations

import io

import pytest

from patchharbor.output import OutputTargets, ProcessOutputCapture


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


def test_output_capture_streams_decoded_lines_to_plain_destination() -> None:
    destination = io.StringIO()
    capture = ProcessOutputCapture(
        io.BytesIO(b"one\ntwo\nthree"),
        live_text_stream=destination,
    )

    capture.start()
    capture.finish()

    assert destination.getvalue() == "one\ntwo\nthree"
    assert capture.retained_lines == ("one\n", "two\n", "three")


def test_output_capture_keeps_raw_log_bytes_separate_from_ui_text() -> None:
    raw_output = b"first\r\nbad-\xff\rfinal"
    plain_destination = io.StringIO()
    raw_destination = io.BytesIO()
    capture = ProcessOutputCapture(
        io.BytesIO(raw_output),
        live_text_stream=plain_destination,
        raw_output_stream=raw_destination,
    )

    capture.start()
    capture.finish()

    assert raw_destination.getvalue() == raw_output
    assert plain_destination.getvalue() == "first\nbad-�\nfinal"
    assert capture.retained_lines == ("first\n", "bad-�\n", "final")


def test_output_targets_choose_plain_or_bounded_output() -> None:
    bounded = io.StringIO()
    plain = io.StringIO()
    bounded_targets = OutputTargets(visible_text_stream=bounded)
    plain_targets = OutputTargets(
        visible_text_stream=bounded,
        live_text_stream=plain,
    )

    bounded_targets.write_visible_lines(("bounded\n",))
    plain_targets.write_visible_lines(("must-not-be-replayed\n",))

    assert bounded.getvalue() == "bounded\n"
    assert plain.getvalue() == ""


def test_output_capture_notifies_dashboard_with_bounded_snapshots() -> None:
    observed: list[tuple[tuple[str, ...], int]] = []
    capture = ProcessOutputCapture(
        io.BytesIO(
            "".join(f"line-{number}\n" for number in range(1, 13)).encode()
        ),
        line_observer=lambda lines, discarded: observed.append(
            (lines, discarded)
        ),
    )

    capture.start()
    capture.finish()

    assert observed
    assert observed[-1] == (
        tuple(f"line-{number}\n" for number in range(8, 13)),
        2,
    )


def test_output_targets_write_and_observe_warnings() -> None:
    warnings = io.StringIO()
    observed: list[str] = []
    targets = OutputTargets(
        visible_text_stream=io.StringIO(),
        warning_text_stream=warnings,
        warning_observer=observed.append,
    )

    targets.write_warnings(("first", "second"))

    assert warnings.getvalue() == (
        "patchharbor: warning: first\n"
        "patchharbor: warning: second\n"
    )
    assert observed == ["first", "second"]
