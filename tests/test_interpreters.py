from __future__ import annotations

from pathlib import Path

import pytest

from patchharbor.errors import ExitCode, PatchHarborError
import patchharbor.interpreters as interpreters
from patchharbor.interpreters import (
    ResolvedInterpreter,
    build_interpreter_command,
    resolve_interpreter,
    select_interpreter,
)


@pytest.mark.parametrize(
    ("shebang", "name", "executable", "suffix"),
    (
        ("#!/bin/bash", "bash", "bash", ".sh"),
        ("#!/usr/bin/bash", "bash", "bash", ".sh"),
        ("#!/usr/bin/env bash", "bash", "bash", ".sh"),
        ("#!powershell", "windows-powershell", "powershell.exe", ".ps1"),
        ("#!powershell.exe", "windows-powershell", "powershell.exe", ".ps1"),
        (
            "#!/usr/bin/env powershell",
            "windows-powershell",
            "powershell.exe",
            ".ps1",
        ),
        (
            "#!/usr/bin/env powershell.exe",
            "windows-powershell",
            "powershell.exe",
            ".ps1",
        ),
        ("#!pwsh", "powershell-7", "pwsh", ".ps1"),
        ("#!pwsh.exe", "powershell-7", "pwsh", ".ps1"),
        ("#!/usr/bin/pwsh", "powershell-7", "pwsh", ".ps1"),
        ("#!/usr/bin/env pwsh", "powershell-7", "pwsh", ".ps1"),
        ("#!/usr/bin/env pwsh.exe", "powershell-7", "pwsh", ".ps1"),
    ),
)
def test_supported_shebang_selects_whitelisted_interpreter(
    shebang: str,
    name: str,
    executable: str,
    suffix: str,
) -> None:
    selected = select_interpreter(f"{shebang}\n# PATCHHARBOR\n")

    assert selected.name == name
    assert selected.executable == executable
    assert selected.script_suffix == suffix


@pytest.mark.parametrize(
    ("os_name", "expected_name", "expected_executable"),
    (
        ("posix", "bash", "bash"),
        ("nt", "windows-powershell", "powershell.exe"),
    ),
)
def test_missing_shebang_uses_platform_default(
    os_name: str,
    expected_name: str,
    expected_executable: str,
) -> None:
    selected = select_interpreter(
        "# PATCHHARBOR\n",
        os_name=os_name,
    )

    assert selected.name == expected_name
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
    monkeypatch.setattr(interpreters.shutil, "which", lambda executable: None)

    with pytest.raises(PatchHarborError) as raised:
        resolve_interpreter(selected)

    assert raised.value.exit_code is ExitCode.INTERPRETER_ERROR
    assert str(raised.value) == "script interpreter not found: bash"


def test_bash_command_contains_only_executable_and_script() -> None:
    selected = select_interpreter("#!/usr/bin/env bash\n# PATCHHARBOR\n")
    resolved = ResolvedInterpreter(selected, "/resolved/bash")

    command = build_interpreter_command(resolved, Path("/tmp/script.sh"))

    assert command == ["/resolved/bash", "/tmp/script.sh"]


@pytest.mark.parametrize("shebang", ("#!powershell.exe", "#!pwsh"))
def test_powershell_command_has_fixed_noninteractive_arguments_without_bypass(
    shebang: str,
) -> None:
    selected = select_interpreter(f"{shebang}\n# PATCHHARBOR\n")
    resolved = ResolvedInterpreter(selected, f"/resolved/{selected.executable}")

    command = build_interpreter_command(resolved, Path("/tmp/script.ps1"))

    assert command == [
        f"/resolved/{selected.executable}",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        "/tmp/script.ps1",
    ]
    lowered = {argument.casefold() for argument in command}
    assert "-executionpolicy" not in lowered
    assert "bypass" not in lowered
