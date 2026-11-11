#!/usr/bin/env python3
"""Explicit, local test diagnostics; importing this entrypoint starts no work."""
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.profiling.application import main

if __name__ == '__main__':
    raise SystemExit(main())
