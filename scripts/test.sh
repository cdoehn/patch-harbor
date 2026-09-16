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
# uv-created virtual environments may not contain pip. Bootstrap only the
# local development environment, never the productive pipx installation.
if ! python -m pip --version >/dev/null 2>&1; then
    python -m ensurepip --upgrade
fi
python -m pip install --disable-pip-version-check -e '.[dev]'

exec python tools/run_tests.py "$@"
