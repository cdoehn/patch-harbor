"""Local profiling common; no implicit collection or network access."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path


def utc():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def local_path(path):
    path = Path(os.path.abspath(path))
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('diagnostic paths must not be symbolic links')
    return path


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be positive and finite')
    return number


def count(value):
    number = int(value)
    if not 1 <= number <= 1000:
        raise argparse.ArgumentTypeError('must be between 1 and 1000')
    return number
