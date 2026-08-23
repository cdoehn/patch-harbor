from __future__ import annotations

from codecs import BOM_UTF8
from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.interpreters as interpreters
from patchharbor.interpreters import (
    build_interpreter_command,
    encode_script_file,
    resolve_interpreter,
    select_interpreter,
)


@pytest.mark.parametrize(
    ("shebang", "executable", "suffix"),
    (
        ("#!/bin/bash", "bash", ".sh"),
        ("#!/usr/bin/bash", "bash", ".sh"),
        ("#!/usr/bin/env bash", "bash", ".sh"),
        ("#!powershell", "powershell.exe", ".ps1"),
        ("#!powershell.exe", "powershell.exe", ".ps1"),
        ("#!/usr/bin/env powershell", "powershell.exe", ".ps1"),
        ("#!/usr/bin/env powershell.exe", "powershell.exe", ".ps1"),
        ("#!pwsh", "pwsh", ".ps1"),
        ("#!pwsh.exe", "pwsh", ".ps1"),
        ("#!/usr/bin/pwsh", "pwsh", ".ps1"),
        ("#!/usr/bin/env pwsh", "pwsh", ".ps1"),
        ("#!/usr/bin/env pwsh.exe", "pwsh", ".ps1"),
    ),
)
def test_supported_shebang_selects_whitelisted_interpreter(
    shebang: str,
    executable: str,
    suffix: str,
) -> None:
    selected = select_interpreter(f"{shebang}\n# PATCHHARBOR\n")

    assert selected.executable == executable
    assert selected.script_suffix == suffix


@pytest.mark.parametrize(
    ("os_name", "expected_executable"),
    (("posix", "bash"), ("nt", "powershell.exe")),
)
def test_missing_shebang_uses_platform_default(
    os_name: str,
    expected_executable: str,
) -> None:
    selected = select_interpreter(
        "# PATCHHARBOR\n",
        os_name=os_name,
    )

    assert selected.executable == expected_executable


@pytest.mark.parametrize(
    "shebang",
    (
        "#!/usr/bin/env python3",
        "#!/usr/bin/env bash -e",
        "#!powershell.exe -ExecutionPolicy Bypass",
        "#!pwsh -NoProfile",
        "#!",
    ),
)
def test_unknown_or_extended_shebang_is_rejected(shebang: str) -> None:
    with pytest.raises(PatchHarborError) as raised:
        select_interpreter(f"{shebang}\n# PATCHHARBOR\n")

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert str(raised.value).startswith(
        "unsupported script interpreter in shebang: "
    )


def test_missing_interpreter_is_reported_during_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = select_interpreter("#!/usr/bin/env bash\n# PATCHHARBOR\n")
    monkeypatch.setattr(interpreters, "find_executable", lambda executable: None)

    with pytest.raises(PatchHarborError) as raised:
        resolve_interpreter(selected)

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert str(raised.value) == "script interpreter not found: bash"


@pytest.mark.parametrize(
    ("shebang", "expected_prefix"),
    (
        ("#!powershell.exe", BOM_UTF8),
        ("#!pwsh", b""),
        ("#!/usr/bin/env bash", b""),
    ),
)
def test_private_script_encoding_matches_interpreter_utf8_contract(
    shebang: str,
    expected_prefix: bytes,
) -> None:
    script = f"{shebang}\n# PATCHHARBOR\nWrite-Output 'Gr\u00fc\u00dfe'\n"
    selected = select_interpreter(script)

    encoded = encode_script_file(script, selected)

    assert encoded == expected_prefix + script.encode("utf-8")


def test_bash_command_contains_only_executable_and_script(
    tmp_path: Path,
) -> None:
    selected = select_interpreter("#!/usr/bin/env bash\n# PATCHHARBOR\n")
    script_path = tmp_path / "private" / "script.sh"
    executable_path = str(tmp_path / "bin" / "bash")
    command = build_interpreter_command(
        selected,
        executable_path,
        script_path,
    )

    assert command == [executable_path, str(script_path)]


@pytest.mark.parametrize("shebang", ("#!powershell.exe", "#!pwsh"))
def test_powershell_command_has_fixed_noninteractive_arguments_without_bypass(
    shebang: str,
    tmp_path: Path,
) -> None:
    selected = select_interpreter(f"{shebang}\n# PATCHHARBOR\n")
    script_path = tmp_path / "private" / "script.ps1"
    executable_path = str(tmp_path / "bin" / selected.executable)
    command = build_interpreter_command(
        selected,
        executable_path,
        script_path,
    )

    assert command == [
        executable_path,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(script_path),
    ]
    lowered = {argument.casefold() for argument in command}
    assert "-executionpolicy" not in lowered
    assert "bypass" not in lowered
