from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from patchharbor.run_log import temporary_run_log


def test_run_log_is_unique_and_persists_after_success(
    tmp_path: Path,
) -> None:
    with temporary_run_log() as first:
        first_path = first.path
        first.write_header(
            source_name="script.sh",
            cwd=tmp_path,
            timeout_seconds=300,
        )
        first.raw_output_stream.write(b"first\n")
        first.write_result(exit_code=0, tool_error=None)
    with temporary_run_log() as second:
        second_path = second.path

    try:
        assert first_path != second_path
        assert first_path.parent == Path(tempfile.gettempdir())
        assert second_path.parent == Path(tempfile.gettempdir())
        assert first_path.exists()
        assert second_path.exists()
    finally:
        first_path.unlink(missing_ok=True)
        second_path.unlink(missing_ok=True)


def test_run_log_preserves_raw_bytes_between_utf8_metadata(
    tmp_path: Path,
) -> None:
    with temporary_run_log() as run_log:
        log_path = run_log.path
        run_log.write_header(
            source_name="binary-output.sh",
            cwd=tmp_path,
            timeout_seconds=12,
        )
        run_log.raw_output_stream.write(b"bad-\xff-output\n")
        run_log.write_result(exit_code=7, tool_error="output failed")

    try:
        data = log_path.read_bytes()
        assert b"PatchHarbor run log\n" in data
        assert b"bad-\xff-output\n" in data
        assert b"--- result ---\n" in data
        assert b"exit_code: 7\n" in data
        assert b'tool_error: "output failed"\n' in data
    finally:
        log_path.unlink(missing_ok=True)


def test_run_log_closes_and_remains_available_when_body_fails() -> None:
    log_path: Path | None = None
    with pytest.raises(RuntimeError, match="primary failure"):
        with temporary_run_log() as run_log:
            log_path = run_log.path
            run_log.raw_output_stream.write(b"before failure\n")
            raise RuntimeError("primary failure")

    assert log_path is not None
    try:
        assert log_path.read_bytes() == b"before failure\n"
    finally:
        log_path.unlink(missing_ok=True)
