from __future__ import annotations

from io import StringIO
from pathlib import Path

from patchharbor.bundles import resolve_patch_bundle
from patchharbor.sources import file_input_artifact, stdin_input_artifact


def test_file_and_stdin_resolve_through_the_same_bundle_semantics(
    tmp_path: Path,
) -> None:
    script_text = "# PATCHHARBOR\n"
    script_path = tmp_path / "example.sh"
    script_path.write_text(script_text, encoding="utf-8")

    file_bundle = resolve_patch_bundle(file_input_artifact(script_path))

    with stdin_input_artifact(StringIO(script_text)) as stdin_artifact:
        temporary_path = stdin_artifact.path
        assert temporary_path.exists()
        stdin_bundle = resolve_patch_bundle(stdin_artifact)

    assert not temporary_path.exists()
    assert len(file_bundle.scripts) == 1
    assert len(stdin_bundle.scripts) == 1
    assert file_bundle.scripts[0].text == script_text
    assert stdin_bundle.scripts[0].text == script_text
    assert file_bundle.scripts[0].display_name == str(script_path)
    assert stdin_bundle.scripts[0].display_name == "standard input"
