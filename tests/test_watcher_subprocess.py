from __future__ import annotations

import os
from pathlib import Path
import sys

from patchharbor_watcher.apply_boundary import (
    DEFAULT_APPLY_COMMAND,
    delegate_to_apply,
)


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_default_apply_boundary_uses_the_current_installation() -> None:
    assert DEFAULT_APPLY_COMMAND == (
        sys.executable,
        "-m",
        "patchharbor.cli",
    )


def test_public_apply_boundary_returns_valid_json_object_and_exit_code(
    tmp_path: Path,
) -> None:
    patch_path = tmp_path / "patch.zip"
    patch_path.write_bytes(b"unchanged")
    stub = tmp_path / "stub.py"
    _write_stub(
        stub,
        """\
import json
import sys
print(json.dumps({"argv": sys.argv[1:]}))
raise SystemExit(9)
""",
    )

    completion = delegate_to_apply(
        patch_path,
        apply_command=(sys.executable, os.fspath(stub)),
    )

    assert completion.process_exit_code == 9
    assert completion.apply_result == {
        "argv": ["apply", "--json", os.fspath(patch_path)]
    }
    assert completion.invalid_response_text is None


def test_public_apply_boundary_preserves_non_object_response_as_invalid(
    tmp_path: Path,
) -> None:
    patch_path = tmp_path / "patch.zip"
    patch_path.write_bytes(b"unchanged")
    stub = tmp_path / "stub.py"
    _write_stub(
        stub,
        """\
import sys
sys.stdout.buffer.write(b"not-json\\xff")
sys.stderr.buffer.write(b"diagnostic\\xff")
raise SystemExit(4)
""",
    )

    completion = delegate_to_apply(
        patch_path,
        apply_command=(sys.executable, os.fspath(stub)),
    )

    assert completion.process_exit_code == 4
    assert completion.apply_result is None
    assert completion.invalid_response_text is not None
    assert completion.stderr_text


def test_public_apply_boundary_supports_parameterless_exchange_discovery(
    tmp_path: Path,
) -> None:
    from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply

    stub = tmp_path / "stub.py"
    _write_stub(
        stub,
        """\
import json
import sys
print(json.dumps({"argv": sys.argv[1:]}))
raise SystemExit(0)
""",
    )

    completion = delegate_to_automatic_apply(
        apply_command=(sys.executable, os.fspath(stub)),
    )

    assert completion.process_exit_code == 0
    assert completion.apply_result == {"argv": ["apply", "--json"]}
    assert completion.invalid_response_text is None
