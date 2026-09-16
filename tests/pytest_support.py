"""Small development-launcher test helper, with no scheduling or aggregation."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import sys

from tests.platform_support import PROJECT_ROOT


def run_development_tests(
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment_overrides: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if environment_overrides:
        environment.update(environment_overrides)
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools" / "run_tests.py"), *arguments],
        cwd=cwd, env=environment, text=True,
        capture_output=True, check=False,
    )
