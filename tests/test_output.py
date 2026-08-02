from __future__ import annotations

from patchharbor.output import RollingLineBuffer


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


def test_rolling_line_buffer_preserves_final_line_without_newline() -> None:
    buffer = RollingLineBuffer()

    buffer.append("first\n")
    buffer.append("final-without-newline")

    assert buffer.retained_lines == ("first\n", "final-without-newline")
