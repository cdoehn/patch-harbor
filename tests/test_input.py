from __future__ import annotations

from io import StringIO
from pathlib import Path

from patchharbor.bundles import resolve_patch_bundle
from patchharbor.sources import file_input_artifact, stdin_input_artifact


def test_file_and_stdin_resolve_through_the_same_artifact_bundle_shape(
    tmp_path: Path,
) -> None:
    script_text = "# PATCHHARBOR\n"
    script_path = tmp_path / "example.sh"
    script_path.write_text(script_text, encoding="utf-8")

    file_artifact = file_input_artifact(script_path)
    assert file_artifact.path == script_path
    assert not file_artifact.remove_after_use

    with stdin_input_artifact(StringIO(script_text)) as stdin_artifact:
        temporary_path = stdin_artifact.path
        assert temporary_path.exists()
        assert stdin_artifact.remove_after_use

        file_bundle = resolve_patch_bundle(file_artifact)
        stdin_bundle = resolve_patch_bundle(stdin_artifact)

        assert len(file_bundle.scripts) == 1
        assert len(stdin_bundle.scripts) == 1
        assert file_bundle.scripts[0].script.text == script_text
        assert stdin_bundle.scripts[0].script.text == script_text
        assert file_bundle.scripts[0].suffix == ".sh"
        assert stdin_bundle.scripts[0].suffix in {".sh", ".ps1"}

    assert not temporary_path.exists()
