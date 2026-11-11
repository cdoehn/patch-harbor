"""Public deprecated-runner boundaries exercised through real native scripts."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO, StringIO
from pathlib import Path
import stat
from threading import Event
import warnings
from zipfile import ZipFile, ZipInfo

import pytest

from patchharbor import api, cli
from tests.platform_support import native_python_script, native_script, native_value


def _zip_stream(entries: list[tuple[str | ZipInfo, str | bytes]]) -> BytesIO:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    stream.seek(0)
    return stream


@pytest.mark.parametrize("source_kind", ["file", "stream"])
@pytest.mark.parametrize("exit_code", [17, 124, 130])
def test_real_script_exit_stops_bundle_without_becoming_tool_failure(tmp_path, source_kind, exit_code):
    cwd = tmp_path / "work"
    cwd.mkdir()
    payload = b"\x00\xff\r\nbyte-exact payload\x00"
    stream = _zip_stream([
        (native_value("z-first.sh", "z-first.ps1"), native_python_script(
            "from pathlib import Path\n"
            "Path('copied.bin').write_bytes(Path('payload.bin').read_bytes())\n"
            "print('from script', flush=True)\n"
            f"raise SystemExit({exit_code})\n"
        )),
        ("payload.bin", payload),
        (native_value("a-second.sh", "a-second.ps1"), native_python_script(
            "from pathlib import Path\nPath('second-ran').touch()\n"
        )),
    ])
    source = stream
    if source_kind == "file":
        source = tmp_path / "scripts.zip"
        source.write_bytes(stream.getvalue())
    text, raw, notices = StringIO(), BytesIO(), StringIO()
    with pytest.warns(FutureWarning):
        result = api.run_scripts(source, cwd=cwd, output=api.OutputStreams(text, raw, notices))
    assert not result.success and result.exit_code == exit_code
    assert (cwd / "copied.bin").read_bytes() == payload
    assert not (cwd / "second-ran").exists()
    assert text.getvalue().splitlines() == ["from script"]
    assert raw.getvalue().splitlines() == [b"from script"]
    assert not any(sink.closed for sink in (stream, text, raw, notices))
    assert {p.name for p in cwd.iterdir()} == {"payload.bin", "copied.bin"}


def test_real_timeout_remains_tool_failure_and_stops_remaining_scripts(tmp_path):
    stream = _zip_stream([
        (native_value("first.sh", "first.ps1"),
         native_script("sleep 30", "Start-Sleep -Seconds 30")),
        (native_value("second.sh", "second.ps1"), native_python_script(
            "from pathlib import Path\nPath('second-ran').touch()\n"
        )),
    ])
    with pytest.warns(FutureWarning), pytest.raises(api.PatchHarborError) as caught:
        api.run_scripts(stream, cwd=tmp_path, timeout=native_value(0.3, 3.0))
    assert caught.value.reason is api.FailureReason.TIMEOUT
    assert not stream.closed and not list(tmp_path.iterdir())


@pytest.mark.parametrize("fault", ["traversal", "case-collision", "symlink"])
def test_unsafe_archive_is_rejected_before_payloads_or_scripts(tmp_path, fault):
    cwd = tmp_path / "work"
    cwd.mkdir()
    entries = [
        (native_value("run.sh", "run.ps1"), native_python_script(
            "from pathlib import Path\nPath('executed').touch()\n"
        )),
        ("safe.bin", b"must not be written before full validation"),
    ]
    if fault == "traversal":
        entries.append(("../escape.txt", b"outside"))
    elif fault == "case-collision":
        entries.extend([("A.txt", b"first"), ("a.txt", b"second")])
    else:
        link = ZipInfo("link.bin")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        entries.append((link, b"target"))
    stream = _zip_stream(entries)
    with pytest.warns(FutureWarning), pytest.raises(api.PatchHarborError) as caught:
        api.run_scripts(stream, cwd=cwd)
    assert caught.value.reason is api.FailureReason.SOURCE_ERROR
    assert not list(cwd.iterdir()) and not (tmp_path / "escape.txt").exists()
    assert not stream.closed


@pytest.mark.parametrize("source_kind", ["file", "stream"])
def test_missing_marker_never_executes_script(tmp_path, source_kind):
    cwd = tmp_path / "work"
    cwd.mkdir()
    text = native_python_script("from pathlib import Path\nPath('executed').touch()\n")
    text = text.replace("# PATCHHARBOR\n", "", 1)
    source = StringIO(text)
    if source_kind == "file":
        source = tmp_path / native_value("unmarked.sh", "unmarked.ps1")
        source.write_text(text, encoding="utf-8")
    with pytest.warns(FutureWarning), pytest.raises(api.PatchHarborError) as caught:
        api.run_scripts(source, cwd=cwd)
    assert caught.value.reason is api.FailureReason.NO_VALID_SCRIPT
    assert not list(cwd.iterdir())
    if source_kind == "stream":
        assert not source.closed


def test_payload_target_conflict_prevents_earlier_payload_and_script(tmp_path):
    (tmp_path / "blocked").mkdir()
    stream = _zip_stream([
        (native_value("run.sh", "run.ps1"), native_python_script(
            "from pathlib import Path\nPath('executed').touch()\n"
        )),
        ("earlier.bin", b"must stay absent"),
        ("blocked", b"cannot replace a directory"),
    ])
    with pytest.warns(FutureWarning), pytest.raises(api.PatchHarborError) as caught:
        api.run_scripts(stream, cwd=tmp_path)
    assert caught.value.reason is api.FailureReason.PAYLOAD_PREPARATION_ERROR
    assert {p.name for p in tmp_path.iterdir()} == {"blocked"}
    assert not list((tmp_path / "blocked").iterdir()) and not stream.closed


def test_selected_directory_candidate_is_revalidated_before_execution(tmp_path):
    sources, cwd = tmp_path / "sources", tmp_path / "work"
    sources.mkdir()
    cwd.mkdir()
    script = native_python_script("from pathlib import Path\nPath('executed').touch()\n")
    for name in ("first", "second"):
        (sources / native_value(name + ".sh", name + ".ps1")).write_text(script, encoding="utf-8")
    replacement = _zip_stream([
        (native_value("run.sh", "run.ps1"), script), ("../escape.txt", b"outside"),
    ]).getvalue()
    selected = []

    def select(candidates):
        selected.append(candidates[0].path)
        candidates[0].path.write_bytes(replacement)
        return candidates[0]

    with pytest.warns(FutureWarning), pytest.raises(api.PatchHarborError) as caught:
        api.run_scripts(sources, cwd=cwd, select_candidate=select)
    assert len(selected) == 1 and caught.value.reason is api.FailureReason.SOURCE_ERROR
    assert not list(cwd.iterdir()) and not (tmp_path / "escape.txt").exists()


def test_active_cli_notice_does_not_suppress_another_threads_api_warning(tmp_path, monkeypatch):
    entered, release = Event(), Event()
    stderr = StringIO()

    def hold_cli(*args, **kwargs):
        entered.set()
        if not release.wait(30):
            raise TimeoutError("test caller did not release the CLI request")
        return 0

    monkeypatch.setattr(cli, "_run_command", hold_cli)
    filters = list(warnings.filters)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cli.main, ["fs", "run", "--plain"],
                             stdin=StringIO(), stdout=StringIO(), stderr=stderr)
        try:
            assert entered.wait(30)
            with pytest.warns(FutureWarning) as caught:
                result = api.run_scripts(StringIO(native_script("exit 0", "exit 0")), cwd=tmp_path)
            assert result.success and len(caught) == 1
            assert Path(caught[0].filename) == Path(__file__)
        finally:
            release.set()
        assert future.result(timeout=30) == 0
    assert stderr.getvalue() and not stderr.closed
    assert warnings.filters == filters


@pytest.mark.parametrize("failure", [KeyboardInterrupt, SystemExit])
def test_cli_base_exception_restores_direct_api_warning(tmp_path, monkeypatch, failure):
    def abort(*args, **kwargs):
        raise failure()

    with monkeypatch.context() as scope:
        scope.setattr(cli, "_run_command", abort)
        with pytest.raises(failure):
            cli.main(["fs", "run"], stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    with pytest.warns(FutureWarning):
        assert api.run_scripts(StringIO(native_script("exit 0", "exit 0")), cwd=tmp_path).success
