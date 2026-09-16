#!/usr/bin/env python3
"""CLI shim for the repository's development-only pytest launcher."""
from __future__ import annotations

# Direct script execution and `python -m tools.run_tests` both work without
# inserting permanent sys.path entries into a caller's process.
if __package__:
    from .test_runner import main
else:
    from test_runner import main

if __name__ == "__main__":
    raise SystemExit(main())
