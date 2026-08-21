#!/usr/bin/env bash
# PATCHHARBOR
set -Eeuo pipefail

usage() {
    printf 'Usage: %s <24.04|26.04>\n' "$(basename "$0")" >&2
}

if (( $# != 1 )); then
    usage
    exit 2
fi

ubuntu_version="$1"
case "$ubuntu_version" in
    24.04|26.04)
        ;;
    *)
        usage
        exit 2
        ;;
esac

for command_name in docker timeout; do
    command -v "$command_name" >/dev/null 2>&1 || {
        printf 'patchharbor: required command not found: %s\n' "$command_name" >&2
        exit 1
    }
done

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
dockerfile="$repository_root/docker/Dockerfile.integration"
[[ -f "$dockerfile" ]] || {
    printf 'patchharbor: integration Dockerfile not found: %s\n' "$dockerfile" >&2
    exit 1
}

image_tag="patchharbor-integration:ubuntu-${ubuntu_version//./-}"
build_timeout_seconds="${PATCHHARBOR_DOCKER_BUILD_TIMEOUT_SECONDS:-2400}"
preflight_timeout_seconds="${PATCHHARBOR_DOCKER_PREFLIGHT_TIMEOUT_SECONDS:-180}"
suite_timeout_seconds="${PATCHHARBOR_DOCKER_SUITE_TIMEOUT_SECONDS:-2400}"
test_timeout_seconds="${PATCHHARBOR_TEST_TIMEOUT_SECONDS:-120}"
test_durations="${PATCHHARBOR_TEST_DURATIONS:-20}"

run_container() {
    local label="$1"
    local timeout_seconds="$2"
    shift 2
    printf 'Running %s on Ubuntu %s ...\n' "$label" "$ubuntu_version"
    timeout --foreground "${timeout_seconds}s" \
        docker run --rm --init "$image_tag" "$@"
}

run_pytest_gate() {
    local label="$1"
    local marker_expression="$2"
    run_container "$label" "$suite_timeout_seconds" \
        python -m pytest -q \
        --timeout="$test_timeout_seconds" \
        --durations="$test_durations" \
        -m "$marker_expression" \
        tests
}

printf 'Building PatchHarbor integration image for Ubuntu %s ...\n' "$ubuntu_version"
timeout --foreground "${build_timeout_seconds}s" \
    docker build \
        --file "$dockerfile" \
        --build-arg "UBUNTU_VERSION=$ubuntu_version" \
        --tag "$image_tag" \
        "$repository_root"

run_container "environment preflight" "$preflight_timeout_seconds" \
    python scripts/check_docker_integration_environment.py --require-init
run_pytest_gate \
    "core and architecture tests" \
    "not e2e and not acceptance and not platform and not packaging"
run_pytest_gate "E2E and acceptance tests" "e2e or acceptance"
run_pytest_gate "platform tests" "platform"
run_pytest_gate "packaging tests" "packaging"
