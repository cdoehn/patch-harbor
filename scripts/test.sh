#!/usr/bin/env bash
set -Eeuo pipefail

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

python_command="${PYTHON:-python3}"
if [[ ! -x .venv/bin/python ]]; then
    "$python_command" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --disable-pip-version-check -e '.[dev]'

exec python tools/run_tests.py "$@"
