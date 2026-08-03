"""Secure lifecycle and byte-exact content for one optional run log."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import BinaryIO


class RunLog:
    """One persistent temp log containing metadata and raw script bytes."""

    def __init__(self, path: Path, stream: BinaryIO) -> None:
        self.path = path
        self._stream = stream
        self._closed = False

    @property
    def raw_output_stream(self) -> BinaryIO:
        """Return the binary sink used by process output capture."""
        if self._closed:
            raise OSError("run log is closed")
        return self._stream

    @property
    def closed(self) -> bool:
        return self._closed

    def write_header(
        self,
        *,
        source_name: str,
        cwd: Path,
        timeout_seconds: float,
        plain_output: bool,
        color_enabled: bool,
    ) -> None:
        self._write_text(
            "PatchHarbor run log\n"
            f"started_utc: {datetime.now(timezone.utc).isoformat()}\n"
            f"source: {json.dumps(source_name, ensure_ascii=False)}\n"
            "working_directory: "
            f"{json.dumps(str(cwd), ensure_ascii=False)}\n"
            f"timeout_seconds: {timeout_seconds:g}\n"
            f"plain_output: {str(plain_output).lower()}\n"
            f"color_enabled: {str(color_enabled).lower()}\n"
            "--- merged script output ---\n"
        )

    def write_result(
        self,
        *,
        exit_code: int,
        tool_error: str | None,
    ) -> None:
        text = "\n--- run result ---\n" f"exit_code: {exit_code}\n"
        if tool_error is not None:
            text += f"tool_error: {json.dumps(tool_error, ensure_ascii=False)}\n"
        text += f"finished_utc: {datetime.now(timezone.utc).isoformat()}\n"
        self._write_text(text)

    def _write_text(self, text: str) -> None:
        if self._closed:
            raise OSError("run log is closed")
        data = text.encode("utf-8")
        written = self._stream.write(data)
        if written is not None and written != len(data):
            raise OSError("short write to run log")
        self._stream.flush()

    def close(self) -> None:
        """Flush and close exactly once."""
        if self._closed:
            return
        error: Exception | None = None
        try:
            self._stream.flush()
        except Exception as exc:
            error = exc
        try:
            self._stream.close()
        except Exception as exc:
            if error is None:
                error = exc
        self._closed = True
        if error is not None:
            raise OSError(f"cannot close run log: {error}") from error


@contextmanager
def temporary_run_log() -> Iterator[RunLog]:
    """Create a unique run log that remains after success or failure."""
    descriptor, raw_path = tempfile.mkstemp(
        prefix="patchharbor-",
        suffix=".log",
    )
    path = Path(raw_path)
    try:
        stream = os.fdopen(descriptor, "wb")
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        path.unlink(missing_ok=True)
        raise

    run_log = RunLog(path, stream)
    primary_error: BaseException | None = None
    try:
        yield run_log
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            run_log.close()
        except OSError:
            if primary_error is None:
                raise
