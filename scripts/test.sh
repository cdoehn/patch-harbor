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

test_timeout_seconds="${PATCHHARBOR_TEST_TIMEOUT_SECONDS:-120}"
suite_timeout_seconds="${PATCHHARBOR_TEST_SUITE_TIMEOUT_SECONDS:-600}"
test_durations="${PATCHHARBOR_TEST_DURATIONS:-10}"

timeout "${suite_timeout_seconds}s" \
    python -m pytest -q \
        --timeout="$test_timeout_seconds" \
        --durations="$test_durations" \
        tests
