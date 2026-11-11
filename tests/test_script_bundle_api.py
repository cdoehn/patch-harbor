"""Independent script execution, deprecation routing and current API names."""
from __future__ import annotations

from io import StringIO
from pathlib import Path
import warnings
from zipfile import ZipFile

import pytest

from patchharbor import api, bundles, models
from patchharbor.cli import main
from patchharbor.sources import file_input_artifact
from tests.platform_support import native_script, native_value


def test_script_bundle_executes_ordered_scripts_with_binary_payload(tmp_path):
    source = tmp_path / "scripts.zip"
    cwd = tmp_path / "output"
    cwd.mkdir()
    payload = b"\x00\xff\r\nexact bytes\x00"
    with ZipFile(source, "w") as archive:
        archive.writestr(native_value("z-first.sh", "z-first.ps1"), native_script(
            "cp payload.bin copied.bin\nprintf 'first\\n' >> order.txt",
            "Copy-Item payload.bin copied.bin\n[IO.File]::AppendAllText('order.txt', 'first' + [Environment]::NewLine)",
        ))
        archive.writestr("payload.bin", payload)
        archive.writestr(native_value("a-second.sh", "a-second.ps1"), native_script(
            "printf 'second\\n' >> order.txt",
            "[IO.File]::AppendAllText('order.txt', 'second' + [Environment]::NewLine)",
        ))

    bundle = bundles.resolve_script_bundle(file_input_artifact(source))
    assert isinstance(bundle, models.ScriptBundle)
    assert len(bundle.scripts) == 2 and len(bundle.payloads) == 1
    assert not hasattr(models, "PatchBundle")
    assert not hasattr(bundles, "resolve_patch_bundle")
    assert not hasattr(api, "run") and "run" not in api.__all__
    with pytest.warns(FutureWarning) as caught:
        result = api.run_scripts(source, cwd=cwd)
    assert len(caught) == 1 and Path(caught[0].filename) == Path(__file__)
    assert result.success and result.exit_code == 0
    assert (cwd / "copied.bin").read_bytes() == payload
    assert (cwd / "order.txt").read_text().splitlines() == ["first", "second"]
    assert not (cwd / ".patchharbor").exists()
    assert not list(cwd.glob("*.zip"))


@pytest.mark.parametrize("exit_code", [0, 17])
def test_cli_deprecation_uses_caller_stderr_on_each_invocation(tmp_path, monkeypatch, exit_code):
    monkeypatch.chdir(tmp_path)
    script = native_script(f"exit {exit_code}", f"exit {exit_code}")
    initial_filters = list(warnings.filters)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(2):
            stderr = StringIO()
            code = main(["fs", "run", "--plain"], stdin=StringIO(script),
                        stdout=StringIO(), stderr=stderr)
            assert code == exit_code
            assert stderr.getvalue()  # warning channel, not console wording
            assert not stderr.closed
        assert not caught  # one CLI notice, no duplicate library warning
    assert warnings.filters == initial_filters


def test_cli_failure_restores_library_warning_context(tmp_path, monkeypatch):
    script = native_script("exit 0", "exit 0")
    def fail(*args, **kwargs):
        raise RuntimeError("simulated caller failure")
    with monkeypatch.context() as scoped:
        scoped.setattr(api, "run_scripts", fail)
        with pytest.raises(RuntimeError):
            main(["fs", "run"], stdin=StringIO(script), stdout=StringIO(), stderr=StringIO())
    with pytest.warns(FutureWarning):
        assert api.run_scripts(StringIO(script), cwd=tmp_path).success
