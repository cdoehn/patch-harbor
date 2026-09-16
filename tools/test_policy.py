"""Shared development execution policy. CPU selection/scheduling belong to xdist."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKERS = "auto"
EVIDENCE_PLUGIN = "tools.test_evidence"
MODE_VERIFICATION_MATRIX = (("0", "0"), ("2", "0"), ("4", "0"), ("auto", "0"),
                            ("2", "1"), ("4", "42"), ("auto", "314159"))


def process_exit_code(returncode: int) -> int:
    """Preserve ordinary status and translate POSIX signal return codes."""
    return returncode if returncode >= 0 else 128 - returncode
